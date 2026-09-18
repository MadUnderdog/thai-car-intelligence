#!/usr/bin/env python3
"""Ingest harvested spec observations into database."""
import json
import subprocess
import sys

# Load harvested specs
with open("/home/ubuntu/Projects/thai-car-intelligence/scripts/harvested-specs.json") as f:
    specs = json.load(f)

print(f"Ingesting {len(specs)} spec observations...")

# Also add manually extracted specs from HeadLight articles
manual_specs = [
    # Xpeng L03
    {"source_name": "HeadLight Magazine", "source_tier": "secondary_automotive_media",
     "source_url": "https://www.headlightmag.com/xpeng-l03-standard-long-range-thailand-specs/",
     "article_title": "Xpeng L03 Standard/Long Range Thailand Specs",
     "manufacturer": "Xpeng", "model": "L03", "variant": "Standard",
     "spec_class": "battery", "spec_key": "capacityKwh", "raw_value": "58.3 kWh",
     "normalized_value": 58.3, "unit": "kWh",
     "source_excerpt": "แบตฯ LFP 58.3 kWh", "retrieval_timestamp": "2026-09-18T15:00:00Z",
     "content_hash": "xpeng-l03-battery-58", "model_year": "2026", "market": "Thailand"},
    {"source_name": "HeadLight Magazine", "source_tier": "secondary_automotive_media",
     "source_url": "https://www.headlightmag.com/xpeng-l03-standard-long-range-thailand-specs/",
     "article_title": "Xpeng L03 Standard/Long Range Thailand Specs",
     "manufacturer": "Xpeng", "model": "L03", "variant": "Long Range",
     "spec_class": "battery", "spec_key": "capacityKwh", "raw_value": "71.2 kWh",
     "normalized_value": 71.2, "unit": "kWh",
     "source_excerpt": "แบตฯ LFP 71.2 kWh", "retrieval_timestamp": "2026-09-18T15:00:00Z",
     "content_hash": "xpeng-l03-battery-71", "model_year": "2026", "market": "Thailand"},
    {"source_name": "HeadLight Magazine", "source_tier": "secondary_automotive_media",
     "source_url": "https://www.headlightmag.com/xpeng-l03-standard-long-range-thailand-specs/",
     "article_title": "Xpeng L03 Standard/Long Range Thailand Specs",
     "manufacturer": "Xpeng", "model": "L03", "variant": "Long Range",
     "spec_class": "performance", "spec_key": "rangeKm", "raw_value": "600 km",
     "normalized_value": 600, "unit": "km",
     "source_excerpt": "วิ่งไกลสุด 600 km (NEDC)", "retrieval_timestamp": "2026-09-18T15:00:00Z",
     "content_hash": "xpeng-l03-range-600", "model_year": "2026", "market": "Thailand"},
    # GWM Tank 500
    {"source_name": "HeadLight Magazine", "source_tier": "secondary_automotive_media",
     "source_url": "https://www.headlightmag.com/specification-gwm-tank-500-diesel-3000-turbo-my2026/",
     "article_title": "GWM Tank 500 Diesel 3.0T MY2026 Specs",
     "manufacturer": "GWM", "model": "Tank 500", "variant": "Diesel",
     "spec_class": "performance", "spec_key": "powerKw", "raw_value": "231 แรงม้า",
     "normalized_value": 231, "unit": "hp",
     "source_excerpt": "231 แรงม้า", "retrieval_timestamp": "2026-09-18T15:00:00Z",
     "content_hash": "gwm-tank500-power-231", "model_year": "2026", "market": "Thailand"},
    {"source_name": "HeadLight Magazine", "source_tier": "secondary_automotive_media",
     "source_url": "https://www.headlightmag.com/specification-gwm-tank-500-diesel-3000-turbo-my2026/",
     "article_title": "GWM Tank 500 Diesel 3.0T MY2026 Specs",
     "manufacturer": "GWM", "model": "Tank 500", "variant": "Diesel",
     "spec_class": "performance", "spec_key": "torqueNm", "raw_value": "620 นิวตันเมตร",
     "normalized_value": 620, "unit": "Nm",
     "source_excerpt": "620 นิวตันเมตร", "retrieval_timestamp": "2026-09-18T15:00:00Z",
     "content_hash": "gwm-tank500-torque-620", "model_year": "2026", "market": "Thailand"},
]

# Combine all specs
all_specs = specs + manual_specs

# Generate SQL
sql_parts = ["BEGIN;"]

for spec in all_specs:
    source_name = spec["source_name"].replace("'", "''")
    source_url = spec["source_url"].replace("'", "''")
    article_title = spec.get("article_title", "").replace("'", "''")[:200]
    manufacturer = spec["manufacturer"].replace("'", "''")
    model = spec["model"].replace("'", "''")
    variant = spec["variant"].replace("'", "''")
    spec_class = spec["spec_class"]
    spec_key = spec["spec_key"]
    raw_value = spec["raw_value"].replace("'", "''")
    normalized_value = spec.get("normalized_value")
    unit = spec.get("unit", "")
    excerpt = spec["source_excerpt"].replace("'", "''")[:300]
    content_hash = spec["content_hash"]
    model_year = spec.get("model_year", "2026")
    
    # Insert source if not exists
    sql_parts.append(f"""
INSERT INTO "Source" ("id", "nameTh", "nameEn", "sourceType", "baseUrl", "domain", "rightsStatus", "status", "createdAt", "updatedAt")
VALUES (gen_random_uuid(), '{source_name}', '{source_name}', 'AUTOMOTIVE_MEDIA', '{source_url.split("/")[0]}//{source_url.split("/")[2]}', '{source_url.split("/")[2]}', 'UNKNOWN', 'ACTIVE', NOW(), NOW())
ON CONFLICT ("nameEn") DO NOTHING;""")
    
    # Insert SourceDocument
    sql_parts.append(f"""
INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '{source_name}' LIMIT 1),
  '{source_url}', '{source_url}', '{article_title}', '{article_title}',
  'text/html', 'th', '{content_hash}', NOW(), 'spec_article', 'DISCOVERED', 'UNKNOWN', 'SUCCEEDED', NOW(), NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;""")
    
    # Insert VariantSpec observation
    norm_val = f"'{normalized_value}'" if normalized_value else "NULL"
    sql_parts.append(f"""
INSERT INTO "VariantSpec" ("id", "variantId", "sourceDocumentId", "key", "valueTh", "valueEn", "valueNumeric", "unit", "confidence", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Variant" WHERE slug = LOWER(REPLACE('{model}', ' ', '-')) LIMIT 1),
  (SELECT id FROM "SourceDocument" WHERE "contentHash" = '{content_hash}' LIMIT 1),
  '{spec_key}',
  '{raw_value}',
  '{raw_value}',
  {norm_val},
  '{unit}',
  0.7,
  NOW(), NOW()
)
ON CONFLICT ("variantId", "key", "sourceDocumentId") DO NOTHING;""")

sql_parts.append("COMMIT;")

sql_content = "\n".join(sql_parts)

# Execute SQL
result = subprocess.run(
    ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence"],
    input=sql_content,
    capture_output=True,
    text=True,
    timeout=60
)

if result.returncode == 0:
    print("SQL executed successfully")
    # Count results
    count_result = subprocess.run(
        ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-c",
         'SELECT count(*) FROM "VariantSpec";'],
        capture_output=True,
        text=True
    )
    print(f"VariantSpec count: {count_result.stdout.strip()}")
else:
    print(f"SQL error: {result.stderr}", file=sys.stderr)
