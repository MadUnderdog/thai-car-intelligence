#!/usr/bin/env python3
"""
reproduce_audit.py — Local invariant verification for the external web audit.

Reads the saved audit files and re-runs all mathematical/invariant checks
without network or database access. Run from the project root:

    python3 audit/external-web-audit/reproduce_audit.py

Exit code 0 = all checks pass, 1 = any check fails.
"""

import json
import os
import sys
from pathlib import Path

AUDIT_DIR = Path(__file__).parent
PASS = "✓"
FAIL = "✗"
results = []


def check(description: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    msg = f"  [{status}] {description}"
    if detail and not condition:
        msg += f" — {detail}"
    print(msg)
    results.append((description, condition))
    return condition


def load_json(filename: str) -> dict:
    path = AUDIT_DIR / filename
    with open(path) as f:
        return json.load(f)


def load_jsonl(filename: str) -> list[dict]:
    path = AUDIT_DIR / filename
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    print("=" * 60)
    print("EXTERNAL WEB AUDIT — INVARIANT VERIFICATION")
    print("=" * 60)
    print()

    # ── Load all files ──────────────────────────────────────────
    manifest = load_json("manifest.json")
    db_summary = load_json("live-db-summary.json")
    stage_recon = load_json("stage-reconciliation.json")
    price_samples = load_jsonl("price-samples.jsonl")
    spec_samples = load_jsonl("spec-samples.jsonl")

    # ── 1. Manifest integrity ───────────────────────────────────
    print("1. MANIFEST INTEGRITY")
    check("manifest.json has auditVersion",
          manifest.get("auditVersion") is not None)
    check("manifest.json has runId",
          manifest.get("runId") is not None)
    check("commitSHA matches expected 276afda",
          manifest.get("commitSHA") == "276afda")
    check("branch is fix/p1-provenance-gate",
          manifest.get("branch") == "fix/p1-provenance-gate")
    check("dbSnapshot.timestamp is present",
          manifest.get("dbSnapshot", {}).get("timestamp") is not None)
    check("dbSnapshot.postgresql contains 16",
          "16" in manifest.get("dbSnapshot", {}).get("postgresql", ""))
    check("prismaMigrations is 6",
          manifest.get("dbSnapshot", {}).get("prismaMigrations") == 6)
    print()

    # ── 2. Price samples ────────────────────────────────────────
    print("2. PRICE SAMPLES (price-samples.jsonl)")
    check("At least 30 price samples",
          len(price_samples) >= 30,
          f"got {len(price_samples)}")
    check("All price samples have id",
          all(r.get("id") for r in price_samples))
    check("All price samples have variantId",
          all(r.get("variantId") for r in price_samples))
    check("All price samples have priceType",
          all(r.get("priceType") for r in price_samples))
    check("All price samples have amount > 0",
          all(r.get("amount", 0) > 0 for r in price_samples))
    check("All price samples have isCurrent=true",
          all(r.get("isCurrent") is True for r in price_samples))
    check("All price samples have brand_name",
          all(r.get("brand_name") for r in price_samples))
    check("All price samples have model_name",
          all(r.get("model_name") for r in price_samples))
    check("All price samples have variant_name",
          all(r.get("variant_name") for r in price_samples))

    price_types = set(r["priceType"] for r in price_samples)
    check("Price types include MSRP",
          "MSRP" in price_types, f"found: {price_types}")
    check("Price types include LIST_PRICE",
          "LIST_PRICE" in price_types, f"found: {price_types}")

    price_brands = set(r["brand_name"] for r in price_samples)
    check("Price samples cover at least 3 brands",
          len(price_brands) >= 3,
          f"found {len(price_brands)}: {sorted(price_brands)}")

    amounts = [r["amount"] for r in price_samples]
    check("Price amounts within reasonable range (50K - 10M THB)",
          all(50_000 <= a <= 10_000_000 for a in amounts),
          f"min={min(amounts)}, max={max(amounts)}")

    unique_price_ids = len(set(r["id"] for r in price_samples))
    check("All price sample IDs are unique",
          unique_price_ids == len(price_samples),
          f"{unique_price_ids} unique / {len(price_samples)} total")
    print()

    # ── 3. Spec samples ─────────────────────────────────────────
    print("3. SPEC SAMPLES (spec-samples.jsonl)")
    check("At least 30 spec samples",
          len(spec_samples) >= 30,
          f"got {len(spec_samples)}")
    check("All spec samples have id",
          all(r.get("id") for r in spec_samples))
    check("All spec samples have key",
          all(r.get("key") for r in spec_samples))
    check("All spec samples have variant_name",
          all(r.get("variant_name") for r in spec_samples))
    check("All spec samples have brand_name",
          all(r.get("brand_name") for r in spec_samples))

    spec_brands = set(r["brand_name"] for r in spec_samples)
    check("Spec samples include Toyota",
          "Toyota" in spec_brands, f"found: {sorted(spec_brands)}")

    non_toyota_specs = [r for r in spec_samples if r["brand_name"] != "Toyota"]
    check("Spec samples include non-Toyota brands",
          len(non_toyota_specs) > 0,
          f"{len(non_toyota_specs)} non-Toyota specs")

    spec_keys = set(r["key"] for r in spec_samples)
    check("At least 10 unique spec keys",
          len(spec_keys) >= 10,
          f"found {len(spec_keys)}")

    confidences = [r["confidence"] for r in spec_samples if r.get("confidence") is not None]
    if confidences:
        check("All confidence values in [0, 1]",
              all(0.0 <= c <= 1.0 for c in confidences),
              f"range: {min(confidences)}-{max(confidences)}")
        check("All confidence values are 0.7 or 0.75 (consistent extraction)",
              all(c in (0.7, 0.75) for c in confidences),
              f"unique values: {sorted(set(confidences))}")

    unique_spec_ids = len(set(r["id"] for r in spec_samples))
    check("All spec sample IDs are unique",
          unique_spec_ids == len(spec_samples),
          f"{unique_spec_ids} unique / {len(spec_samples)} total")

    has_numeric = sum(1 for r in spec_samples if r.get("valueNumeric") is not None)
    check("Some specs have numeric values",
          has_numeric > 0,
          f"{has_numeric}/{len(spec_samples)} have numeric values")

    has_unit = sum(1 for r in spec_samples if r.get("unit"))
    check("Some specs have units",
          has_unit > 0,
          f"{has_unit}/{len(spec_samples)} have units")
    print()

    # ── 4. Live DB summary consistency ──────────────────────────
    print("4. LIVE DB SUMMARY CONSISTENCY")
    tables = db_summary.get("tables", {})

    check("Manufacturer count matches manifest",
          tables.get("Manufacturer", {}).get("total") ==
          manifest.get("dbTotals", {}).get("manufacturers"))
    check("CarModel count matches manifest",
          tables.get("CarModel", {}).get("total") ==
          manifest.get("dbTotals", {}).get("carModels"))
    check("Variant count matches manifest",
          tables.get("Variant", {}).get("total") ==
          manifest.get("dbTotals", {}).get("variants"))
    check("VariantSpec total matches manifest",
          tables.get("VariantSpec", {}).get("total") ==
          manifest.get("dbTotals", {}).get("variantSpecs"))
    check("Price total matches manifest",
          tables.get("Price", {}).get("total") ==
          manifest.get("dbTotals", {}).get("allPrices"))

    vs = tables.get("VariantSpec", {})
    vs_by_status = vs.get("byQuarantineStatus", {})
    active = vs_by_status.get("ACTIVE", 0)
    quarantined = vs_by_status.get("QUARANTINED", 0)
    check("VariantSpec ACTIVE + QUARANTINED = total",
          active + quarantined == vs.get("total", 0),
          f"{active} + {quarantined} = {active + quarantined} vs total {vs.get('total')}")
    check("ACTIVE specs match manifest",
          active == manifest.get("dbTotals", {}).get("activeSpecs"))
    check("QUARANTINED specs match manifest",
          quarantined == manifest.get("dbTotals", {}).get("quarantinedSpecs"))

    price = tables.get("Price", {})
    price_by_type = price.get("byPriceType", {})
    total_by_type = sum(price_by_type.values())
    check("Price by-type sum equals currentPrices",
          total_by_type == price.get("currentPrices", 0),
          f"sum={total_by_type} vs current={price.get('currentPrices')}")

    price_by_brand = price.get("byBrand", {})
    total_by_brand = sum(price_by_brand.values())
    check("Price by-brand sum equals currentPrices",
          total_by_brand == price.get("currentPrices", 0),
          f"sum={total_by_brand} vs current={price.get('currentPrices')}")
    print()

    # ── 5. Stage reconciliation ─────────────────────────────────
    print("5. STAGE RECONCILIATION")
    stages = stage_recon.get("pipelineStages", {})

    persisted = stages.get("persisted", {})
    check("Persisted manufacturers matches DB",
          persisted.get("manufacturers") == tables.get("Manufacturer", {}).get("total"))
    check("Persisted carModels matches DB",
          persisted.get("carModels") == tables.get("CarModel", {}).get("total"))
    check("Persisted variants matches DB",
          persisted.get("variants") == tables.get("Variant", {}).get("total"))
    check("Persisted variantSpecs matches DB",
          persisted.get("variantSpecs") == tables.get("VariantSpec", {}).get("total"))
    check("Persisted currentPrices matches DB",
          persisted.get("currentPrices") == tables.get("Price", {}).get("currentPrices"))
    check("Persisted sourceDocuments matches DB",
          persisted.get("sourceDocuments") == tables.get("SourceDocument", {}).get("total"))
    check("Persisted vehicleUniverse matches DB",
          persisted.get("vehicleUniverse") == tables.get("VehicleUniverse", {}).get("total"))

    promoted = stages.get("promoted", {})
    check("Promoted active specs matches DB",
          promoted.get("variantSpecsActive") == active)
    check("Promoted current prices matches DB",
          promoted.get("pricesCurrent") == price.get("currentPrices"))

    unresolved = stages.get("unresolved", {})
    rc = stages.get("raw_candidates", {})
    ej = stages.get("unresolved", {})
    check("Unresolved = researchCandidates + extractionJobs",
          ej.get("total") ==
          rc.get("count", 0) + ej.get("extractionJobsQueued", 0))

    inv = stage_recon.get("invariants", {})
    check("Invariant: variantSpecsSum documented",
          "variantSpecsSum" in inv)
    check("Invariant: pricesSum documented",
          "pricesSum" in inv)
    print()

    # ── 6. Cross-file consistency ───────────────────────────────
    print("6. CROSS-FILE CONSISTENCY")
    manifest_counts = manifest.get("dbTotals", {})
    summary_counts = {}
    for tname, tdata in tables.items():
        if isinstance(tdata, dict) and "total" in tdata:
            key = tname[0].lower() + tname[1:]  # camelCase
            if tname == "CarModel":
                key = "carModels"
            elif tname == "VariantSpec":
                key = "variantSpecs"
            elif tname == "VariantFeature":
                key = "variantFeatures"
            elif tname == "DiscoverySource":
                key = "discoverySources"
            elif tname == "ResearchCandidate":
                key = "researchCandidates"
            elif tname == "SourceDocument":
                key = "sourceDocuments"
            elif tname == "VehicleUniverse":
                key = "vehicleUniverse"
            elif tname == "ExtractionJob":
                key = "extractionJobs"
            elif tname == "Price":
                key = "allPrices"
            elif tname == "Manufacturer":
                key = "manufacturers"
            elif tname == "Variant":
                key = "variants"
            elif tname == "Source":
                key = "sources"
            summary_counts[key] = tdata["total"]

    for key, mval in manifest_counts.items():
        sval = summary_counts.get(key)
        if sval is not None:
            check(f"manifest.dbTotals.{key} == live-db-summary",
                  mval == sval,
                  f"manifest={mval}, summary={sval}")

    # Price samples should all be in the current prices pool
    check("Price samples count <= currentPrices total",
          len(price_samples) <= price.get("currentPrices", 0),
          f"sampled {len(price_samples)}, current total {price.get('currentPrices')}")

    # Spec samples should all be in the active specs pool
    check("Spec samples count <= activeSpecs total",
          len(spec_samples) <= active,
          f"sampled {len(spec_samples)}, active total {active}")
    print()

    # ── Summary ─────────────────────────────────────────────────
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    total = len(results)
    print(f"RESULTS: {passed}/{total} checks passed, {failed} failed")
    print("=" * 60)

    if failed:
        print("\nFailed checks:")
        for desc, ok in results:
            if not ok:
                print(f"  - {desc}")
        sys.exit(1)
    else:
        print("\nAll invariant checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
