#!/usr/bin/env python3
"""Ingest v2 spec observations into VariantSpec table."""
import json
import subprocess

with open("/home/ubuntu/Projects/thai-car-intelligence/scripts/harvested-specs-v2.json") as f:
    specs = json.load(f)

print(f"Ingesting {len(specs)} spec observations...")

# Get existing variant slugs
result = subprocess.run(
    ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-c",
     "SELECT slug FROM \"Variant\";"],
    capture_output=True, text=True
)
existing_slugs = set()
for line in result.stdout.split("\n"):
    line = line.strip()
    if line and line != "slug" and line != "---" and not line.startswith("("):
        existing_slugs.add(line.lower())

print(f"Existing variant slugs: {len(existing_slugs)}")

# Map model names to variant slugs
model_to_slug = {
    "byd seal 6 2026": "seal-dynamic",
    "byd sealion 5 dm i super phev": "sealion-5-dynamic",
    "mg4 my2026 2": "mg4-standard",
    "mg im 5 long range rwd": "mg-im5-ev",
    "honda en2": "honda-en2-ev",
    "tesla model y l long wheelbase": "tesla-model-y",
    "nio firefly": "nio-firefly",
    "zeekr x my2026": "zeekr-x",
    "geely ex5 my2026": "geely-ex5",
    "hyundai ioniq 5 n line ckd thailand 2nd lot": "hyundai-ioniq-5",
    "byd sealion 7 2026 awd ultimate": "sealion-7-advanced",
    "gwm tank 500 diesel 2026": "gwm-tank-500",
    "honda super one": "honda-super-one",
    "geely starray em r reev": "geely-starray",
    "honda city big minorchange 2026": "honda-city",
    "honda accord 2026": "honda-accord",
    "mg urban 2026": "mg-urban-ev",
    "nissan kicks e power minorchange 2026": "nissan-kicks",
    "ford everest platinum my2026": "ford-everest",
    "ford ranger wildtrak x my2026": "ford-ranger",
    "hyundai santa fe my2026": "hyundai-santa-fe",
    "subaru crosstrek": "subaru-crosstrek",
    "mazda 6e edit": "mazda-6e",
    "toyota land cruiser fj": "toyota-land-cruiser-fj",
    "bmw ix3 na5": "bmw-ix3",
    "toyota corolla altis my2026": "toyota-corolla-altis",
    "suzuki jimny with safety support my2026": "suzuki-jimny",
    "changan nevo q05": "changan-nevo-q05",
    "lepas l6": "lepas-l6",
    "avatr 11 my2026": "avatr-11",
    "tesla model y thailand": "tesla-model-y",
    "tesla model 3 official thailand": "tesla-model-3",
    "offcial price denza z9gt ev bev thailand 2026": "denza-z9gt",
    "official special price byd seal 5 dm i phev plug in hybrid sep 2026": "byd-seal-5",
    "official price discount byd sealion 5 dm i phev sep 2026": "sealion-5-dynamic",
    "official price discount byd atto 2 ev bev sep 2026": "atto-2-dynamic",
    "xpeng l03 standard long range thailand specs": "xpeng-l03",
    "specification gwm tank 500 diesel 3000 turbo my2026": "gwm-tank-500",
    "2026 08 14 picture specs honda super one": "honda-super-one",
    "2026 08 13 picture specs all new lexus es 350h grand luxury es 350e premium": "lexus-es",
    "2026 09 08 picture specs geely starray em r max": "geely-starray",
    "2026 09 28 picture specs mazda 6e exclusive": "mazda-6e",
    "2026 09 26 picture specs toyota land cruiser fj edit": "toyota-land-cruiser-fj",
}

ingested = 0
skipped = 0

for spec in specs:
    # Try to find matching variant
    model_lower = spec["model"].lower()
    variant_slug = model_to_slug.get(model_lower)
    
    if not variant_slug:
        # Try fuzzy match
        for key, slug in model_to_slug.items():
            if any(word in model_lower for word in key.split() if len(word) > 3):
                variant_slug = slug
                break
    
    if not variant_slug or variant_slug not in existing_slugs:
        skipped += 1
        continue
    
    # Get variant ID
    result = subprocess.run(
        ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-c",
         f"SELECT id FROM \"Variant\" WHERE slug = '{variant_slug}' LIMIT 1;"],
        capture_output=True, text=True
    )
    variant_id = None
    for line in result.stdout.split("\n"):
        line = line.strip()
        if line and line != "id" and line != "---" and not line.startswith("(") and len(line) == 36:
            variant_id = line
            break
    
    if not variant_id:
        skipped += 1
        continue
    
    # Get or create source document
    content_hash = spec["content_hash"]
    result = subprocess.run(
        ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-c",
         f"SELECT id FROM \"SourceDocument\" WHERE \"contentHash\" = '{content_hash}' LIMIT 1;"],
        capture_output=True, text=True
    )
    sd_id = None
    for line in result.stdout.split("\n"):
        line = line.strip()
        if line and line != "id" and line != "---" and not line.startswith("(") and len(line) == 36:
            sd_id = line
            break
    
    if not sd_id:
        # Create source document
        source_url = spec["source_url"].replace("'", "''")
        article_title = (spec.get("article_title") or "Spec Article").replace("'", "''")[:200]
        source_name = spec["source_name"].replace("'", "''")
        
        result = subprocess.run(
            ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-c",
             f"""INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus")
SELECT gen_random_uuid(), 
  (SELECT id FROM "Source" WHERE "nameEn" = '{source_name}' LIMIT 1),
  '{source_url}', '{source_url}', '{article_title}', '{article_title}',
  'text/html', 'th', '{content_hash}', NOW(), 'spec_article', 'DISCOVERED', 'UNKNOWN', 'SUCCEEDED'
WHERE EXISTS (SELECT 1 FROM "Source" WHERE "nameEn" = '{source_name}')
ON CONFLICT ("sourceId", "contentHash") DO NOTHING
RETURNING id;"""],
            capture_output=True, text=True
        )
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line and line != "id" and line != "---" and not line.startswith("(") and len(line) == 36:
                sd_id = line
                break
    
    if not sd_id:
        skipped += 1
        continue
    
    # Insert VariantSpec
    spec_key = spec["spec_key"]
    raw_value = spec["raw_value"].replace("'", "''")
    normalized = spec.get("normalized_value")
    unit = spec.get("unit") or ""
    
    norm_val = f"'{normalized}'" if normalized else "NULL"
    
    result = subprocess.run(
        ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-c",
         f"""INSERT INTO "VariantSpec" ("id", "variantId", "sourceDocumentId", "key", "valueTh", "valueEn", "valueNumeric", "unit", "confidence")
VALUES (gen_random_uuid(), '{variant_id}', '{sd_id}', '{spec_key}', '{raw_value}', '{raw_value}', {norm_val}, '{unit}', 0.7)
ON CONFLICT ("variantId", "key", "sourceDocumentId") DO NOTHING;"""],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        ingested += 1
    else:
        skipped += 1

# Count
result = subprocess.run(
    ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-c",
     'SELECT count(*) FROM "VariantSpec";'],
    capture_output=True, text=True
)
print(f"\nVariantSpec count: {result.stdout.strip()}")
print(f"This run: {ingested} ingested, {skipped} skipped")
