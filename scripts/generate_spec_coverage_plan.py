#!/usr/bin/env python3
"""Generate audit/spec-coverage-plan.json from a fresh scan of captured artifacts.

Spec expansion must be evidence-led: this records which already-captured bytes
carry real spec fields, and which official spec pages the captured documents
themselves link to, so the next spec cycle buys acquisition only where structure
already exists. No harvesting is performed here — no page is fetched, no spec is
staged.
"""
import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR = os.path.join(REPO, "tests", "fixtures", "oem-artifacts")
OUT = os.path.join(REPO, "audit", "spec-coverage-plan.json")
REGISTRY = os.path.join(REPO, "audit", "coverage", "oem-registry.json")
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")

# spec-bearing signals only (price patterns are excluded on purpose)
MARKERS = {
    "thai_ps": r"แรงม้า",
    "torque_nm": r"\b\d{3}\s*(?:Nm|นิวตันเมตร)",
    "kw": r"\b\d{2,3}\s*kW\b",
    "kwh": r"\b\d{2,3}\s*kWh\b",
    "displacement": r"\b\d\.\d\s*(?:L|ลิตร|cc)\b",
    "fuel_consumption": r"(?:ประหยัดน้ำมัน|km/l|กม\./ลิตร)",
}
SPEC_LINK = re.compile(r'href="([^"]*(?:spec|specification|technical)[^"]*)"', re.I)

# Structured spec fields published inside the page's own data payload / spec blocks.
# Their presence is what makes an artifact a *high-confidence* spec source: the value
# sits in a named field next to the model it belongs to, instead of free prose.
STRUCTURED_KEYS = re.compile(
    r'"(?:spec\d*key|spec\d*value|maxout|maxtorque|displacement|enginetype|'
    r'fuelconsumption|torque|power|battery|capacity)"\s*:',
    re.I,
)
SPEC_BLOCK = re.compile(r'class="[^"]*(?:itemInfo|spec|engine|technical)[^"]*"', re.I)


def structure_signal(raw: str) -> dict:
    """Classify how a captured artifact carries its spec figures."""
    structured = len(STRUCTURED_KEYS.findall(raw))
    blocks = len(SPEC_BLOCK.findall(raw))
    if structured:
        kind, confidence = "structured_field", "high"
    elif blocks:
        kind, confidence = "spec_block_dom", "high"
    else:
        kind, confidence = "prose_only", "medium"
    return {"structure": kind, "structured_fields": structured,
            "spec_blocks": blocks, "confidence": confidence}


def scan():
    in_hand, links = [], {}
    for name in sorted(os.listdir(ART_DIR)):
        if not name.endswith(".html"):
            continue
        raw = open(os.path.join(ART_DIR, name), encoding="utf-8", errors="ignore").read()
        counts = {k: len(re.findall(p, raw)) for k, p in MARKERS.items()}
        spec_links = SPEC_LINK.findall(raw)
        total = sum(counts.values())
        if total:
            entry = {"artifact": f"tests/fixtures/oem-artifacts/{name}",
                     "marker_counts": counts, "marker_total": total}
            entry.update(structure_signal(raw))
            in_hand.append(entry)
        if spec_links:
            links[f"tests/fixtures/oem-artifacts/{name}"] = sorted(set(spec_links))
    in_hand.sort(key=lambda x: -x["marker_total"])
    return in_hand, links


def staged_state() -> dict:
    """Recompute the plan's current_state from the staging file itself so the
    numbers cannot drift when a new wave adds rows."""
    staging = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
    total = 0
    with_specs = 0
    brands = set()
    with open(staging, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            total += 1
            if row.get("specs"):
                with_specs += 1
                brands.add(row["identity"]["brand_normalized"])
    return {
        "rows_with_specs": with_specs,
        "total_rows": total,
        "coverage_pct": round(100.0 * with_specs / total, 1) if total else 0.0,
        "brands_with_specs": sorted(brands),
    }


def wrong_target_artifacts() -> dict:
    """Captures the registry itself marks as belonging to some other business.

    Their bytes may never feed a plan: spec links discovered inside a
    wrong-target page point at that other business, not at the brand.
    """
    with open(REGISTRY, encoding="utf-8") as f:
        reg = json.load(f)
    out = {}
    for brand in reg.get("brands", []):
        for endpoint in (brand.get("captured_endpoints") or []):
            note = endpoint.get("note") or ""
            if "WRONG-TARGET" in note.upper():
                out[endpoint.get("artifact")] = {"brand": brand.get("brand"), "note": note}
    return out


def route_safety(links: dict, excluded: dict) -> dict:
    """Which tier-2 targets are legal to fetch this cycle.

    The spec plan must never schedule a request against a host the OEM registry
    currently records as blocked or as a wrong target, before that brand's
    next_retry_at. Planning stays offline; these flags are what the next spec
    cycle has to respect.
    """
    with open(REGISTRY, encoding="utf-8") as f:
        reg = json.load(f)
    registry_hosts = {}

    def note(url, brand: dict, status: str):
        m = re.match(r"https?://([^/:]+)", url or "")
        if not m:
            return
        registry_hosts.setdefault(m.group(1).lower(), {
            "brand": brand.get("brand"),
            "access_status": status,
            "next_retry_at": brand.get("next_retry_at"),
        })

    for brand in reg.get("brands", []):
        status = brand.get("access_status") or ""
        if status == "REACHABLE" or not status:
            continue
        for url in (brand.get("source_urls") or []):
            note(url, brand, status)
        note((brand.get("blocker_evidence") or {}).get("url"), brand, status)

    tier2_hosts = {}
    for urls in links.values():
        for url in urls:
            m = re.match(r"https?://([^/:]+)", url)
            if not m:
                continue
            host = m.group(1).lower()
            record = registry_hosts.get(host)
            seen = tier2_hosts.get(host, {"targets": 0})
            seen["targets"] += 1
            seen["registry_state"] = (record or {}).get("access_status", "not_in_registry")
            seen["blocked_or_wrong_target"] = bool(record)
            seen["next_retry_at"] = (record or {}).get("next_retry_at")
            tier2_hosts[host] = seen
    return {
        "rule": "a tier-2 target whose host is registry-blocked or a wrong target is "
                "planning-only until that brand's next_retry_at; this file makes no request",
        "registry_hosts_not_reachable": registry_hosts,
        "tier2_hosts": tier2_hosts,
        "excluded_wrong_target_artifacts": excluded,
    }


def main() -> int:
    in_hand, links = scan()
    excluded = wrong_target_artifacts()
    if excluded:
        in_hand = [e for e in in_hand
                   if e["artifact"].rsplit("/", 1)[-1] not in excluded]
        links = {k: v for k, v in links.items()
                 if k.rsplit("/", 1)[-1] not in excluded}
    plan = {
        "purpose": "evidence-led spec expansion; this file stages no specs and fetches nothing",
        "current_state": {
            **staged_state(),
            "note": "recomputed from audit/data-staging/vehicle_observations.jsonl at "
                    "generation time; concentration is by source rather than "
                    "placeholder/duplicate contamination",
        },
        "tiers": [
            {
                "tier": 1,
                "name": "already-captured bytes (zero fetch)",
                "action": "parse with the same-record binding already required for prices "
                          "(model card + spec cell + mutation tests); no new acquisition",
                "evidence": in_hand,
                "why_highest_value": "the figures exist in artifacts we already hold, so cost is "
                                     "extraction + tests only, and provenance is already sidecar-backed",
            },
            {
                "tier": 2,
                "name": "official spec pages linked by captured documents",
                "action": "small, laddered acquisition of the linked URLs only, one brand per cycle, "
                          "each earning its own artifact + sidecar + adapter gate",
                "evidence": links,
                "why_second": "the link targets are published by the OEM pages we already fetched, "
                              "so the structure is known to exist before any request is made",
            },
            {
                "tier": 3,
                "name": "secondary media (AUTOMOTIVE_MEDIA / RESEARCH_UNVERIFIED)",
                "action": "only where an article's own scope proves the model, and only ever as "
                          "secondary corroboration — never promoted to official, never a source of "
                          "official spec values",
                "evidence": {
                    "registry_patterns": [
                        "\\d+ (?:แรงม้า|hp|PS) ... \\d+ (?:Nm|นิวตันเมตร)",
                    ],
                    "registry_source": "storage/thai-source-registry.json (headlightmag known_article_patterns)",
                    "captured_media_artifacts": [
                        "tests/fixtures/media-artifacts/9carthai_toyota_price.html",
                        "tests/fixtures/media-artifacts/9carthai_honda_price.html",
                        "tests/fixtures/media-artifacts/9carthai_mazda_price.html",
                    ],
                },
                "why_third": "media figures are research-unverified by construction; they may only "
                             "corroborate, so they cannot lead spec coverage",
            },
        ],
        "guardrails": [
            "no mass harvesting: one source per cycle, adapter only for real parseable structure",
            "every spec row needs same-record model binding, a resolvable locator and a mutation test",
            "placeholder-looking values are counted and reported, never promoted",
            "spec expansion never blocks Phase 1 coverage work",
        ],
        "route_safety": route_safety(links, excluded),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    print(json.dumps({
        "in_hand_artifacts": len(in_hand),
        "top": [(e["artifact"].rsplit("/", 1)[-1], e["marker_total"], e["confidence"])
                for e in in_hand[:5]],
        "linked_spec_pages": {k.rsplit("/", 1)[-1]: len(v) for k, v in links.items()},
        "tier2_hosts_flagged_blocked": [h for h, v in plan["route_safety"]["tier2_hosts"].items()
                                        if v["blocked_or_wrong_target"]],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
