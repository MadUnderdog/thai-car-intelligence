#!/usr/bin/env python3
"""
Multi-Source Assembly Script
=============================
Finds brands/models/variants with data from BOTH OEM official sources and
Thai automotive media sources, then creates cross-source assembly records
for comparison, conflict detection, and trust analysis.

Source classes:
  OEM_OFFICIAL  : SourceDocument from OFFICIAL_MANUFACTURER* sources,
                  or extractionMethod containing 'api' or 'official'
  AUTOMOTIVE_MEDIA: SourceDocument from headlightmag, autospinn,
                    autolifethailand, 9carthai domains

Outputs:
  - storage/multi-source-assembly.json  (full assembly records)
  - console report with stats
"""

import json
import os
import sys
import re
from datetime import datetime
from collections import defaultdict
from decimal import Decimal

# ---------------------------------------------------------------------------
# DB connection via psycopg2
# ---------------------------------------------------------------------------
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Installing psycopg2-binary...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary", "-q"])
    import psycopg2
    import psycopg2.extras


DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://hermes:hermes@localhost:5432/thai_car_intelligence"
)


# ── helper: convert Decimal / datetime for JSON ──────────────────────────

class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def jsonify(val):
    """Serialize a DB value for JSON safely."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, datetime):
        return val.isoformat()
    return val


# ══════════════════════════════════════════════════════════════════════════
# QUERIES — each independently joins through Price or VariantSpec
# ══════════════════════════════════════════════════════════════════════════

OEM_PRICE_SQL = """
SELECT DISTINCT
    m.id AS manufacturer_id, m."nameEn" AS brand_name,
    cm.id AS model_id, cm."nameEn" AS model_name,
    v.id AS variant_id, v."nameEn" AS variant_name,
    sd.id AS doc_id, sd.url AS doc_url,
    sd."extractionMethod" AS extraction_method,
    s."nameEn" AS source_name, s."sourceType" AS source_type, s.domain AS source_domain,
    p.id AS price_id, p.amount AS price_amount, p."priceType" AS price_type,
    NULL::uuid AS spec_id, NULL AS spec_key,
    NULL AS spec_value_en, NULL AS spec_value_th,
    NULL AS spec_value_numeric, NULL AS spec_unit, NULL AS spec_confidence
FROM "Price" p
JOIN "SourceDocument" sd ON sd.id = p."sourceDocumentId"
JOIN "Source" s ON s.id = sd."sourceId"
JOIN "Variant" v ON v.id = p."variantId"
JOIN "CarModel" cm ON cm.id = v."modelId"
JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
WHERE (
    s."sourceType" IN ('OFFICIAL_MANUFACTURER','OFFICIAL_MANUFACTURER_BROCHURE',
                        'OFFICIAL_MANUFACTURER_PRICE_LIST','OFFICIAL_MANUFACTURER_PRESS_RELEASE')
    OR sd."extractionMethod" ILIKE '%api%'
    OR sd."extractionMethod" ILIKE '%official%'
)
"""

OEM_SPEC_SQL = """
SELECT DISTINCT
    m.id AS manufacturer_id, m."nameEn" AS brand_name,
    cm.id AS model_id, cm."nameEn" AS model_name,
    v.id AS variant_id, v."nameEn" AS variant_name,
    sd.id AS doc_id, sd.url AS doc_url,
    sd."extractionMethod" AS extraction_method,
    s."nameEn" AS source_name, s."sourceType" AS source_type, s.domain AS source_domain,
    NULL::uuid AS price_id, NULL AS price_amount, NULL AS price_type,
    vs.id AS spec_id, vs.key AS spec_key,
    vs."valueEn" AS spec_value_en, vs."valueTh" AS spec_value_th,
    vs."valueNumeric" AS spec_value_numeric, vs.unit AS spec_unit,
    vs.confidence AS spec_confidence
FROM "VariantSpec" vs
JOIN "SourceDocument" sd ON sd.id = vs."sourceDocumentId"
JOIN "Source" s ON s.id = sd."sourceId"
JOIN "Variant" v ON v.id = vs."variantId"
JOIN "CarModel" cm ON cm.id = v."modelId"
JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
WHERE (
    s."sourceType" IN ('OFFICIAL_MANUFACTURER','OFFICIAL_MANUFACTURER_BROCHURE',
                        'OFFICIAL_MANUFACTURER_PRICE_LIST','OFFICIAL_MANUFACTURER_PRESS_RELEASE')
    OR sd."extractionMethod" ILIKE '%api%'
    OR sd."extractionMethod" ILIKE '%official%'
)
"""

MEDIA_PRICE_SQL = """
SELECT DISTINCT
    m.id AS manufacturer_id, m."nameEn" AS brand_name,
    cm.id AS model_id, cm."nameEn" AS model_name,
    v.id AS variant_id, v."nameEn" AS variant_name,
    sd.id AS doc_id, sd.url AS doc_url,
    sd."extractionMethod" AS extraction_method,
    s."nameEn" AS source_name, s."sourceType" AS source_type, s.domain AS source_domain,
    p.id AS price_id, p.amount AS price_amount, p."priceType" AS price_type,
    NULL::uuid AS spec_id, NULL AS spec_key,
    NULL AS spec_value_en, NULL AS spec_value_th,
    NULL AS spec_value_numeric, NULL AS spec_unit, NULL AS spec_confidence
FROM "Price" p
JOIN "SourceDocument" sd ON sd.id = p."sourceDocumentId"
JOIN "Source" s ON s.id = sd."sourceId"
JOIN "Variant" v ON v.id = p."variantId"
JOIN "CarModel" cm ON cm.id = v."modelId"
JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
WHERE (
    s.domain ILIKE '%headlightmag%'
    OR s.domain ILIKE '%autospinn%'
    OR s.domain ILIKE '%autolifethailand%'
    OR s.domain ILIKE '%9carthai%'
)
"""

MEDIA_SPEC_SQL = """
SELECT DISTINCT
    m.id AS manufacturer_id, m."nameEn" AS brand_name,
    cm.id AS model_id, cm."nameEn" AS model_name,
    v.id AS variant_id, v."nameEn" AS variant_name,
    sd.id AS doc_id, sd.url AS doc_url,
    sd."extractionMethod" AS extraction_method,
    s."nameEn" AS source_name, s."sourceType" AS source_type, s.domain AS source_domain,
    NULL::uuid AS price_id, NULL AS price_amount, NULL AS price_type,
    vs.id AS spec_id, vs.key AS spec_key,
    vs."valueEn" AS spec_value_en, vs."valueTh" AS spec_value_th,
    vs."valueNumeric" AS spec_value_numeric, vs.unit AS spec_unit,
    vs.confidence AS spec_confidence
FROM "VariantSpec" vs
JOIN "SourceDocument" sd ON sd.id = vs."sourceDocumentId"
JOIN "Source" s ON s.id = sd."sourceId"
JOIN "Variant" v ON v.id = vs."variantId"
JOIN "CarModel" cm ON cm.id = v."modelId"
JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
WHERE (
    s.domain ILIKE '%headlightmag%'
    OR s.domain ILIKE '%autospinn%'
    OR s.domain ILIKE '%autolifethailand%'
    OR s.domain ILIKE '%9carthai%'
)
"""


def fetch_rows(cursor, sql):
    """Execute SQL and return list of dicts."""
    cursor.execute(sql)
    cols = [desc[0] for desc in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ══════════════════════════════════════════════════════════════════════════
# BUILD ASSEMBLY RECORDS
# ══════════════════════════════════════════════════════════════════════════

def build_assembly(oem_rows, media_rows):
    """
    Match OEM and media data per variant+field, producing assembly records.
    
    Uses (variant_id, field) as the join key. Fields are either:
      - price:<priceType>  (for Price records)
      - spec:<spec_key>    (for VariantSpec records)
    """
    # Index OEM data by (variant_id, field_key)
    oem_index = defaultdict(list)
    for row in oem_rows:
        vid = row["variant_id"]
        if vid is None:
            continue
        if row["price_id"] and row["price_amount"] is not None:
            field_key = f"price:{row['price_type']}"
            oem_index[(vid, field_key)].append(row)
        if row["spec_id"] and row["spec_key"]:
            field_key = f"spec:{row['spec_key']}"
            oem_index[(vid, field_key)].append(row)

    # Index media data by (variant_id, field_key)
    media_index = defaultdict(list)
    for row in media_rows:
        vid = row["variant_id"]
        if vid is None:
            continue
        if row["price_id"] and row["price_amount"] is not None:
            field_key = f"price:{row['price_type']}"
            media_index[(vid, field_key)].append(row)
        if row["spec_id"] and row["spec_key"]:
            field_key = f"spec:{row['spec_key']}"
            media_index[(vid, field_key)].append(row)

    # Find overlapping (variant_id, field_key) pairs
    common_keys = set(oem_index.keys()) & set(media_index.keys())

    assembly_records = []
    cross_model_violations = []

    for (variant_id, field_key) in sorted(common_keys):
        oem_entries = oem_index[(variant_id, field_key)]
        media_entries = media_index[(variant_id, field_key)]

        # Pick best representative from each (prefer highest confidence)
        def conf(r):
            c = r.get("spec_confidence")
            return float(c) if c else 0
        oem_best = max(oem_entries, key=conf)
        media_best = max(media_entries, key=conf)

        # Cross-model contamination check
        oem_model = oem_best["model_id"]
        media_model = media_best["model_id"]
        if oem_model and media_model and oem_model != media_model:
            cross_model_violations.append({
                "variant_id": str(variant_id),
                "field_key": field_key,
                "oem_model_id": str(oem_model),
                "media_model_id": str(media_model),
            })
            continue

        # Determine source names
        source_class_oem = "OEM_OFFICIAL"
        source_class_media = "AUTOMOTIVE_MEDIA"
        source_name_oem = oem_best.get("source_name", "")
        source_name_media = media_best.get("source_name", "")

        # Extract values
        if field_key.startswith("price:"):
            val_oem = jsonify(oem_best["price_amount"])
            val_media = jsonify(media_best["price_amount"])
        else:
            val_oem = oem_best.get("spec_value_en") or oem_best.get("spec_value_th")
            val_media = media_best.get("spec_value_en") or media_best.get("spec_value_th")

        # Conflict detection (5% threshold)
        conflict_status = "consistent"
        if val_oem is not None and val_media is not None:
            if isinstance(val_oem, (int, float)) and isinstance(val_media, (int, float)):
                if val_oem != 0 and abs(val_oem - val_media) / abs(val_oem) > 0.05:
                    conflict_status = "conflict"
                elif val_oem == 0 and val_media != 0:
                    conflict_status = "conflict"
            elif str(val_oem).strip() != str(val_media).strip():
                try:
                    num_oem = float(re.sub(r"[^\d.\-]", "", str(val_oem)))
                    num_media = float(re.sub(r"[^\d.\-]", "", str(val_media)))
                    if num_oem != 0 and abs(num_oem - num_media) / abs(num_oem) > 0.05:
                        conflict_status = "conflict"
                except (ValueError, ZeroDivisionError):
                    conflict_status = "conflict"

        # Trust scoring
        trust_oem = "high" if oem_best.get("source_type", "").startswith("OFFICIAL") else "medium"
        trust_media = "medium"

        record = {
            "model_id": str(oem_best["model_id"]) if oem_best["model_id"] else None,
            "model_name": oem_best.get("model_name") or media_best.get("model_name"),
            "variant_id": str(variant_id),
            "variant_name": oem_best.get("variant_name") or media_best.get("variant_name"),
            "brand_name": oem_best.get("brand_name") or media_best.get("brand_name"),
            "field_name": field_key,
            "value_from_oem": val_oem,
            "value_from_media": val_media,
            "source_class_oem": source_class_oem,
            "source_class_media": source_class_media,
            "source_name_oem": source_name_oem,
            "source_name_media": source_name_media,
            "url_oem": oem_best.get("doc_url"),
            "url_media": media_best.get("doc_url"),
            "trust_oem": trust_oem,
            "trust_media": trust_media,
            "conflict_status": conflict_status,
            "spec_confidence_oem": jsonify(oem_best.get("spec_confidence")),
            "spec_confidence_media": jsonify(media_best.get("spec_confidence")),
            "extraction_method_oem": oem_best.get("extraction_method"),
            "extraction_method_media": media_best.get("extraction_method"),
        }
        assembly_records.append(record)

    return assembly_records, cross_model_violations


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("MULTI-SOURCE ASSEMBLY")
    print(f"Run at: {datetime.utcnow().isoformat()}Z")
    print("=" * 70)

    conn = psycopg2.connect(DB_URL)
    conn.set_session(autocommit=True)
    cur = conn.cursor()

    # ── Fetch OEM rows ────────────────────────────────────────────────────
    print("\n[1/6] Querying OEM official source documents (Prices)...")
    oem_price_rows = fetch_rows(cur, OEM_PRICE_SQL)
    print(f"  → {len(oem_price_rows)} OEM price records")

    print("[2/6] Querying OEM official source documents (Specs)...")
    oem_spec_rows = fetch_rows(cur, OEM_SPEC_SQL)
    print(f"  → {len(oem_spec_rows)} OEM spec records")

    oem_rows = oem_price_rows + oem_spec_rows
    oem_brands = set(r["brand_name"] for r in oem_rows if r["brand_name"])
    oem_variants = set(r["variant_id"] for r in oem_rows if r["variant_id"])
    print(f"  → Total: {len(oem_rows)} OEM records across {len(oem_brands)} brands, "
          f"{len(oem_variants)} unique variants")
    print(f"  → Brands: {', '.join(sorted(oem_brands))}")

    # ── Fetch Media rows ──────────────────────────────────────────────────
    print("\n[3/6] Querying Thai automotive media source documents (Prices)...")
    media_price_rows = fetch_rows(cur, MEDIA_PRICE_SQL)
    print(f"  → {len(media_price_rows)} media price records")

    print("[4/6] Querying Thai automotive media source documents (Specs)...")
    media_spec_rows = fetch_rows(cur, MEDIA_SPEC_SQL)
    print(f"  → {len(media_spec_rows)} media spec records")

    media_rows = media_price_rows + media_spec_rows
    media_brands = set(r["brand_name"] for r in media_rows if r["brand_name"])
    media_variants = set(r["variant_id"] for r in media_rows if r["variant_id"])
    print(f"  → Total: {len(media_rows)} media records across {len(media_brands)} brands, "
          f"{len(media_variants)} unique variants")
    print(f"  → Brands: {', '.join(sorted(media_brands))}")

    # ── Identify overlap brands ───────────────────────────────────────────
    overlap_brands = oem_brands & media_brands
    print(f"\n[5/6] Brands with BOTH source classes: {len(overlap_brands)}")
    for b in sorted(overlap_brands):
        oem_v = set(r["variant_id"] for r in oem_rows
                    if r["brand_name"] == b and r["variant_id"])
        med_v = set(r["variant_id"] for r in media_rows
                    if r["brand_name"] == b and r["variant_id"])
        shared = oem_v & med_v
        print(f"  • {b}: {len(oem_v)} OEM variants, {len(med_v)} media variants, "
              f"{len(shared)} overlapping variants")

    # ── Build assembly ────────────────────────────────────────────────────
    print("\n[6/6] Building multi-source assembly records...")
    assembly, cross_model_violations = build_assembly(oem_rows, media_rows)

    # Filter to overlap brands only
    assembly = [r for r in assembly if r["brand_name"] in overlap_brands]

    conflicts = [r for r in assembly if r["conflict_status"] == "conflict"]
    consistent = [r for r in assembly if r["conflict_status"] == "consistent"]

    # Group by brand
    by_brand = defaultdict(list)
    for r in assembly:
        by_brand[r["brand_name"]].append(r)

    print(f"  → Total assembly records: {len(assembly)}")
    print(f"  → Conflicts found: {len(conflicts)}")
    print(f"  → Consistent: {len(consistent)}")
    print(f"  → Cross-model violations blocked: {len(cross_model_violations)}")

    for brand in sorted(by_brand):
        records = by_brand[brand]
        brand_conflicts = [r for r in records if r["conflict_status"] == "conflict"]
        print(f"\n  ── {brand} ({len(records)} records, "
              f"{len(brand_conflicts)} conflicts) ──")
        models = set(r["model_name"] for r in records)
        for m in sorted(models):
            m_records = [r for r in records if r["model_name"] == m]
            m_conflicts = [r for r in m_records if r["conflict_status"] == "conflict"]
            print(f"    {m}: {len(m_records)} fields, {len(m_conflicts)} conflicts")
            for r in m_records[:3]:
                v_oem = r["value_from_oem"]
                v_med = r["value_from_media"]
                mark = "✗" if r["conflict_status"] == "conflict" else "✓"
                print(f"      {mark} {r['field_name']}: OEM={v_oem} vs Media={v_med} "
                      f"({r['source_name_oem']} vs {r['source_name_media']})")
            if len(m_records) > 3:
                print(f"      ... +{len(m_records)-3} more fields")

    # ── Export ────────────────────────────────────────────────────────────
    print("\nExporting assembly records...")
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "brands_with_2_classes": len(overlap_brands),
            "overlap_brands": sorted(list(overlap_brands)),
            "total_assembly_records": len(assembly),
            "conflicts_found": len(conflicts),
            "consistent": len(consistent),
            "cross_model_violations_blocked": len(cross_model_violations),
            "oem_total_records": len(oem_rows),
            "media_total_records": len(media_rows),
        },
        "brand_summaries": {},
        "assembly_records": assembly,
        "conflicts": conflicts,
        "cross_model_violations": cross_model_violations,
    }

    for brand in sorted(by_brand):
        records = by_brand[brand]
        brand_models = set(r["model_name"] for r in records)
        brand_conflicts = [r for r in records if r["conflict_status"] == "conflict"]
        output["brand_summaries"][brand] = {
            "record_count": len(records),
            "models": sorted(list(brand_models)),
            "conflict_count": len(brand_conflicts),
            "conflict_fields": [r["field_name"] for r in brand_conflicts],
        }

    out_path = os.path.join(os.path.dirname(__file__), "..", "storage", "multi-source-assembly.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, cls=CustomEncoder)
    print(f"  → Exported to: {os.path.abspath(out_path)}")

    # ── Final report ──────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(f"Brands with 2+ source classes: {len(overlap_brands)}")
    print(f"Total assembly examples:       {len(assembly)}")
    print(f"Conflicts found:               {len(conflicts)}")
    print(f"Cross-model violations blocked:{len(cross_model_violations)}")
    print("=" * 70)

    summary_json = {
        "brands_with_2_classes": len(overlap_brands),
        "examples_found": len(assembly),
        "conflicts_found": len(conflicts),
        "report_path": os.path.abspath(out_path),
    }
    print("\n--- JSON SUMMARY ---")
    print(json.dumps(summary_json, indent=2))

    cur.close()
    conn.close()
    return summary_json


if __name__ == "__main__":
    result = main()
