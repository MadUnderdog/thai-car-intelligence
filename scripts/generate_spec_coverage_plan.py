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
            in_hand.append({"artifact": f"tests/fixtures/oem-artifacts/{name}",
                            "marker_counts": counts, "marker_total": total})
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


def main() -> int:
    in_hand, links = scan()
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
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    print(json.dumps({
        "in_hand_artifacts": len(in_hand),
        "top": [(e["artifact"].rsplit("/", 1)[-1], e["marker_total"]) for e in in_hand[:5]],
        "linked_spec_pages": {k.rsplit("/", 1)[-1]: len(v) for k, v in links.items()},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
