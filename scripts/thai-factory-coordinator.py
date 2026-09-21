#!/usr/bin/env python3
"""
Thai Automotive Data Factory — Thin Coordinator

Uses modular components from lib/thai_factory/:
  - models: Observation, SourceAdapter, IdentityResult, ScopeResult
  - identity: IdentityResolver (two-stage)
  - scope: ScopeValidator (structured)
  - quality: Quality gates (executable invariants)
  - queue: DurableQueue (checkpoint/resume)
  - persistence: Observation persistence (DB writes)

Usage:
    python3 thai-factory-coordinator.py [--reset] [--max-per-source N] [--dry-run]
"""
import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Set
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from thai_factory.models import (
    Observation, SourceRef, DocumentSnapshot, SourceClass,
    TrustState, VerificationState, IdentityDecision, ScopeDecision,
    PriceType, SourceMetadata
)
from thai_factory.identity.resolver import IdentityResolver
from thai_factory.scope.validator import ScopeValidator
from thai_factory.quality.gates import quarantine_observations
from thai_factory.queue.durable import DurableQueue, JobState
from thai_factory.persistence.observations import persist_observations

# ─── Configuration ──────────────────────────────────────────────────

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage")
CHECKPOINT_FILE = os.path.join(STORAGE_DIR, "factory-queue-checkpoint.json")
RESULTS_FILE = os.path.join(STORAGE_DIR, "factory-coordinator-results.json")
REPORT_FILE = os.path.join(STORAGE_DIR, "factory-coordinator-report.txt")

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) Chrome/131"
REQUEST_TIMEOUT = 15
THB_MIN = 100_000
THB_MAX = 20_000_000


# ─── Source Adapters (typed) ────────────────────────────────────────

class HeadlightMagAdapter:
    def metadata(self) -> SourceMetadata:
        return SourceMetadata(
            name="HeadLight Magazine", domain="headlightmag.com",
            source_class=SourceClass.AUTOMOTIVE_MEDIA,
            trust_state=TrustState.QUALIFIED,
            verification_state=VerificationState.NOT_OFFICIAL,
            has_rss=True, has_category_pages=True,
        )

    def discover(self, max_articles=15) -> List[SourceRef]:
        refs = []
        rss_url = "https://www.headlightmag.com/feed/"
        try:
            req = Request(rss_url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                xml = resp.read().decode("utf-8", errors="replace")
            root = ET.fromstring(xml)
            for item in root.find("channel").findall("item")[:max_articles]:
                link = item.find("link")
                title = item.find("title")
                pub = item.find("pubDate")
                if link is not None and link.text:
                    refs.append(SourceRef(
                        url=link.text.strip(),
                        title=title.text.strip() if title is not None and title.text else "",
                        published_date=pub.text.strip() if pub is not None and pub.text else "",
                        source_domain="headlightmag.com",
                        discovery_method="rss",
                    ))
        except Exception:
            pass
        return refs

    def fetch(self, ref: SourceRef) -> DocumentSnapshot:
        req = Request(ref.url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        import re
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        content_hash = hashlib.sha256(text[:5000].encode()).hexdigest()[:16]
        return DocumentSnapshot(
            url=ref.url, html=html, text=text,
            content_hash=content_hash, title=ref.title,
            published_date=ref.published_date,
        )

    def extract(self, snapshot: DocumentSnapshot) -> List[Observation]:
        import re
        obs_list = []
        text = snapshot.text
        title = snapshot.title

        # Price extraction
        for m in re.finditer(r'(?:ราคา|฿|price)[:\s]*(?:เริ่มต้น|เริ่ม)?\s*(\d{1,3}(?:,\d{3}){1,3})\s*(?:บาท|฿)?', text, re.I):
            val = int(m.group(1).replace(",", ""))
            if THB_MIN <= val <= THB_MAX:
                excerpt = text[max(0, m.start()-60):m.end()+60]
                obs_list.append(Observation(
                    source_url=snapshot.url,
                    source_domain="headlightmag.com",
                    source_class=SourceClass.AUTOMOTIVE_MEDIA,
                    title=title, published_date=snapshot.published_date,
                    field="price", raw_value=m.group(1),
                    normalized_value=str(val), unit="THB",
                    price_type=PriceType.MSRP,
                    trust_state=TrustState.QUALIFIED,
                    evidence_excerpt=excerpt[:200],
                    content_hash=snapshot.content_hash,
                ))

        # Spec extraction
        spec_patterns = [
            (r'(\d{2,3})\s*(?:แรงม้า|hp|ps)\b', "power_hp", "hp"),
            (r'(\d{2,4})\s*(?:นิวตันเมตร|nm)\b', "torque_nm", "Nm"),
            (r'(\d{1,2}\.\d)\s*(?:ลิตร|liter|l)\b', "engine_l", "L"),
            (r'(\d{3,4})\s*cc\b', "engine_cc", "cc"),
        ]
        for pattern, field, unit in spec_patterns:
            for m in re.finditer(pattern, text, re.I):
                excerpt = text[max(0, m.start()-40):m.end()+40]
                obs_list.append(Observation(
                    source_url=snapshot.url,
                    source_domain="headlightmag.com",
                    source_class=SourceClass.AUTOMOTIVE_MEDIA,
                    title=title, published_date=snapshot.published_date,
                    field=field, raw_value=m.group(1),
                    normalized_value=m.group(1), unit=unit,
                    trust_state=TrustState.QUALIFIED,
                    evidence_excerpt=excerpt[:200],
                    content_hash=snapshot.content_hash,
                ))

        return obs_list


# ─── Additional adapters follow same pattern ────────────────────────

ADAPTERS = [HeadlightMagAdapter()]


# ─── Coordinator ────────────────────────────────────────────────────

def run(max_per_source: int = 15, reset: bool = False, dry_run: bool = False):
    """Main coordinator loop."""
    os.makedirs(STORAGE_DIR, exist_ok=True)

    resolver = IdentityResolver()
    validator = ScopeValidator()
    queue = DurableQueue(CHECKPOINT_FILE)

    if reset:
        queue = DurableQueue(CHECKPOINT_FILE)
        queue.jobs.clear()
        queue.save()

    print(f"{'='*70}")
    print(f"  THAI DATA FACTORY — COORDINATOR")
    print(f"  Max per source: {max_per_source}")
    print(f"  Dry run: {dry_run}")
    print(f"  Queue jobs: {len(queue.jobs)}")
    print(f"{'='*70}")

    all_observations: List[Observation] = []

    for adapter in ADAPTERS:
        meta = adapter.metadata()
        print(f"\n{'='*60}")
        print(f"  SOURCE: {meta.name} ({meta.domain})")
        print(f"  Class: {meta.source_class.value}, Trust: {meta.trust_state.value}")
        print(f"{'='*60}")

        # Phase 1: Discover
        refs = adapter.discover(max_articles=max_per_source)
        print(f"  [DISCOVER] {len(refs)} articles")

        # Enqueue
        for ref in refs:
            job_key = f"{meta.domain}|{ref.url}"
            queue.enqueue(job_key, ref.url, meta.domain)

        # Phase 2-4: Fetch + Extract + Resolve (per document)
        processed = 0
        for ref in refs:
            job_key = f"{meta.domain}|{ref.url}"
            job = queue.claim_next(meta.domain)
            if not job:
                continue

            try:
                # Fetch
                snapshot = adapter.fetch(ref)
                print(f"  [{processed+1}/{len(refs)}] FETCHED {ref.url[:60]}...")

                # Extract
                observations = adapter.extract(snapshot)

                # Ensure evidence_excerpt is always set
                for obs in observations:
                    if not obs.evidence_excerpt:
                        obs.evidence_excerpt = snapshot.text[:200]
                    if not obs.content_hash:
                        obs.content_hash = snapshot.content_hash

                print(f"    EXTRACTED {len(observations)} observations")

                # Identity resolution
                for obs in observations:
                    combined_text = f"{obs.title} {obs.evidence_excerpt}"
                    result = resolver.resolve(obs.brand or None, combined_text)
                    obs.identity_decision = result.decision
                    obs.identity_confidence = result.confidence
                    obs.identity_reason = result.reason
                    if result.decision == IdentityDecision.RESOLVED:
                        obs.brand = result.canonical_brand
                        obs.model = result.canonical_model
                    elif result.canonical_brand:
                        obs.brand = result.canonical_brand

                # Scope validation
                scope = validator.validate(snapshot.title, snapshot.text)
                for obs in observations:
                    obs.scope_decision = scope.decision
                    obs.scope_confidence = scope.confidence
                    obs.scope_reason = scope.reason
                    if scope.primary_brand and not obs.brand:
                        obs.brand = scope.primary_brand

                all_observations.extend(observations)
                queue.complete(job_key, {"observations": len(observations)})
                processed += 1

            except Exception as e:
                queue.fail(job_key, str(e), retryable=True)
                print(f"    ERROR: {e}")

            time.sleep(0.5)

        print(f"  Source complete: {processed}/{len(refs)} articles")

    # Phase 5: Quality gates
    print(f"\n{'='*70}")
    print(f"  PHASE 5: QUALITY GATES")
    print(f"{'='*70}")
    accepted, quarantined = quarantine_observations(all_observations)
    print(f"  Accepted: {len(accepted)}, Quarantined: {len(quarantined)}")

    # Phase 6: Persist
    print(f"\n{'='*70}")
    print(f"  PHASE 6: PERSIST")
    print(f"{'='*70}")
    if dry_run:
        print(f"  [DRY RUN] Skipping persistence")
        persist_stats = {"prices_inserted": 0, "specs_inserted": 0}
    else:
        persist_stats = persist_observations(accepted, dry_run=dry_run)
        print(f"  Prices: {persist_stats['prices_inserted']}")
        print(f"  Specs: {persist_stats['specs_inserted']}")

    # Phase 7: Report
    print(f"\n{'='*70}")
    print(f"  REPORT")
    print(f"{'='*70}")
    print(f"  Total observations: {len(all_observations)}")
    print(f"  Accepted: {len(accepted)}")
    print(f"  Quarantined: {len(quarantined)}")
    print(f"  Prices persisted: {persist_stats['prices_inserted']}")
    print(f"  Specs persisted: {persist_stats['specs_inserted']}")
    print(f"  Queue stats: {queue.stats()}")

    # Save results
    results = {
        "run_id": f"coordinator-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_observations": len(all_observations),
        "accepted": len(accepted),
        "quarantined": len(quarantined),
        "persist_stats": persist_stats,
        "queue_stats": queue.stats(),
        "observations": [o.to_dict() for o in accepted[:100]],  # Sample
    }
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    queue.save()
    print(f"\n  Results: {RESULTS_FILE}")
    print(f"  Queue: {CHECKPOINT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--max-per-source", type=int, default=15)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.max_per_source, args.reset, args.dry_run)
