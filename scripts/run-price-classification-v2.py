#!/usr/bin/env python3
"""Comprehensive price classification v2 — classifies all 398 active prices."""
import json
import subprocess
import sys

DB = {"host": "localhost", "port": 5432, "user": "hermes", "dbname": "thai_car_intelligence"}

def query(sql, timeout=120):
    cmd = [
        "psql", "-h", DB["host"], "-p", str(DB["port"]),
        "-U", DB["user"], "-d", DB["dbname"],
        "-t", "-A", "-c", sql
    ]
    env = {"PGPASSWORD": "hermes"}
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env={**dict(__import__("os").environ), **env})
    if r.returncode != 0:
        print(f"SQL ERROR:\n{r.stderr}", file=sys.stderr)
        sys.exit(1)
    return r.stdout.strip()

# ── Main classification query ──
SQL = """
WITH
active_prices AS (
  SELECT
    p."id" AS price_id,
    p."variantId",
    p."sourceDocumentId",
    p."priceType",
    p."amount",
    p."isCurrent",
    p."quarantineStatus",
    p."validFrom",
    v."nameEn" AS variant_name,
    cm."id" AS model_id,
    cm."nameEn" AS model_name,
    m."nameEn" AS brand,
    sd."url" AS source_url,
    sd."fetchedAt" AS fetched_at
  FROM "Price" p
  JOIN "Variant" v ON p."variantId" = v."id"
  JOIN "CarModel" cm ON v."modelId" = cm."id"
  JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
  LEFT JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
  WHERE (p."quarantineStatus" = 'ACTIVE' OR p."quarantineStatus" IS NULL)
),

-- FLAG 1: URL series_code mismatch (Toyota API contamination)
url_mismatch AS (
  SELECT DISTINCT price_id
  FROM active_prices
  WHERE source_url LIKE '%toyota.co.th%series_code=%'
    AND NOT (
      lower(replace(replace(replace(replace(model_name, ' ', ''), '-', ''), '_', ''), '/', ''))
        LIKE '%' || lower(regexp_replace(regexp_replace(source_url, '.*series_code=([^&]+).*', '\\1'), '[ _-]', '', 'g')) || '%'
      OR lower(regexp_replace(regexp_replace(source_url, '.*series_code=([^&]+).*', '\\1'), '[ _-]', '', 'g'))
        LIKE '%' || lower(replace(replace(replace(replace(model_name, ' ', ''), '-', ''), '_', ''), '/', '')) || '%'
    )
),

-- FLAG 2: Cross-source conflict (3+ sources, >20% spread)
variant_source_stats AS (
  SELECT
    "variantId",
    COUNT(DISTINCT "sourceDocumentId") AS src_count,
    MIN("amount") AS min_amt,
    MAX("amount") AS max_amt,
    CASE WHEN MIN("amount") > 0
      THEN (MAX("amount") - MIN("amount")) / MIN("amount") * 100
      ELSE 0 END AS spread_pct
  FROM active_prices
  WHERE "sourceDocumentId" IS NOT NULL
  GROUP BY "variantId"
  HAVING COUNT(DISTINCT "sourceDocumentId") >= 3
),
cross_source_conflict AS (
  SELECT "variantId" FROM variant_source_stats WHERE spread_pct > 20
),

-- FLAG 3: Stale current (isCurrent=true, fetched >6 months ago)
stale_current AS (
  SELECT DISTINCT price_id
  FROM active_prices
  WHERE "isCurrent" = true AND fetched_at < NOW() - INTERVAL '6 months'
),

-- FLAG 4: No VehicleUniverse match
no_vu_match AS (
  SELECT DISTINCT ap.price_id
  FROM active_prices ap
  LEFT JOIN "VehicleUniverse" vu ON vu."variantId" = ap."variantId"
  WHERE vu."id" IS NULL
),

-- FLAG 5: Model-range misused (same amount across ALL variants of a model for same priceType)
model_range_check AS (
  SELECT model_id, model_name, amount, "priceType", COUNT(DISTINCT "variantId") AS price_variants
  FROM active_prices
  GROUP BY model_id, model_name, amount, "priceType"
  HAVING COUNT(DISTINCT "variantId") >= 2
),
model_total_variants AS (
  SELECT cm."id" AS model_id, COUNT(DISTINCT v."id") AS total_variants
  FROM "CarModel" cm
  JOIN "Variant" v ON v."modelId" = cm."id"
  JOIN "Price" p ON p."variantId" = v."id"
  WHERE (p."quarantineStatus" = 'ACTIVE' OR p."quarantineStatus" IS NULL)
  GROUP BY cm."id"
),
model_range_misused AS (
  SELECT DISTINCT ap.price_id
  FROM active_prices ap
  JOIN model_range_check mrc ON ap.model_id = mrc.model_id
    AND ap.amount = mrc.amount AND ap."priceType" = mrc."priceType"
  JOIN model_total_variants mtv ON ap.model_id = mtv.model_id
  WHERE mrc.price_variants = mtv.total_variants AND mtv.total_variants >= 2
),

-- FLAG 6: Exact duplicates
exact_duplicates AS (
  SELECT "variantId", "sourceDocumentId", "priceType", amount, "validFrom"
  FROM active_prices
  WHERE "sourceDocumentId" IS NOT NULL
  GROUP BY "variantId", "sourceDocumentId", "priceType", amount, "validFrom"
  HAVING COUNT(*) > 1
),
duplicate_prices AS (
  SELECT ap.price_id
  FROM active_prices ap
  JOIN exact_duplicates ed
    ON ap."variantId" = ed."variantId"
    AND ap."sourceDocumentId" = ed."sourceDocumentId"
    AND ap."priceType" = ed."priceType"
    AND ap.amount = ed.amount
    AND ap."validFrom" = ed."validFrom"
),

-- ── CLASSIFY ──
classified AS (
  SELECT ap.*,
    CASE
      WHEN ap.price_id IN (SELECT price_id FROM url_mismatch) THEN 'WRONG_MODEL'
      WHEN ap."variantId" IN (SELECT "variantId" FROM cross_source_conflict) THEN 'CROSS_SOURCE_CONFLICT'
      WHEN ap.price_id IN (SELECT price_id FROM stale_current) THEN 'STALE_CURRENT'
      WHEN ap.price_id IN (SELECT price_id FROM no_vu_match) THEN 'WRONG_VARIANT'
      WHEN ap.price_id IN (SELECT price_id FROM model_range_misused) THEN 'MODEL_RANGE_MISUSED'
      WHEN ap.price_id IN (SELECT price_id FROM duplicate_prices) THEN 'DUPLICATE'
      ELSE 'VALID'
    END AS disposition
  FROM active_prices ap
),

-- ── AGGREGATE ──
disposition_counts AS (
  SELECT disposition, COUNT(*) AS cnt
  FROM classified
  GROUP BY disposition
),
brand_disposition AS (
  SELECT brand, disposition, COUNT(*) AS cnt
  FROM classified
  GROUP BY brand, disposition
),
brand_summary AS (
  SELECT brand, jsonb_object_agg(disposition, cnt) AS counts
  FROM brand_disposition
  GROUP BY brand
)

SELECT jsonb_build_object(
  'file_path', '/home/ubuntu/Projects/thai-car-intelligence/scripts/price-semantic-audit-v2.json',
  'total_classified', (SELECT COUNT(*) FROM classified),
  'valid_count', (SELECT COUNT(*) FROM classified WHERE disposition = 'VALID'),
  'quarantine_candidates', (SELECT COUNT(*) FROM classified WHERE disposition != 'VALID'),
  'disposition_counts', (SELECT jsonb_object_agg(disposition, cnt) FROM disposition_counts),
  'by_brand', (SELECT jsonb_object_agg(brand, counts) FROM brand_summary)
);
"""

print("Running classification query...")
result = query(SQL)
data = json.loads(result)

# Write the artifact
output_path = "/home/ubuntu/Projects/thai-car-intelligence/scripts/price-semantic-audit-v2.json"
with open(output_path, "w") as f:
    json.dump(data, f, indent=2)

print(f"\n=== CLASSIFICATION RESULT ===")
print(f"Total classified: {data['total_classified']}")
print(f"Valid: {data['valid_count']}")
print(f"Quarantine candidates: {data['quarantine_candidates']}")
print(f"\nDisposition counts:")
for k, v in sorted(data['disposition_counts'].items()):
    print(f"  {k}: {v}")
print(f"\nBy brand:")
for brand in sorted(data['by_brand']):
    print(f"  {brand}: {data['by_brand'][brand]}")

print(f"\nJSON artifact written to: {output_path}")
