#!/usr/bin/env python3
"""Ingest v2 spec observations with improved model mapping."""
import json
import subprocess

with open("/home/ubuntu/Projects/thai-car-intelligence/scripts/harvested-specs-v2.json") as f:
    specs = json.load(f)

print(f"Ingesting {len(specs)} spec observations...")

# Get all variants with model info
result = subprocess.run(
    ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-t", "-A", "-c",
     "SELECT v.slug, m.\"nameEn\" FROM \"Variant\" v JOIN \"CarModel\" m ON m.id = v.\"modelId\";"],
    capture_output=True, text=True
)
variants = {}
for line in result.stdout.strip().split("\n"):
    if "|" in line:
        parts = line.split("|")
        if len(parts) == 2:
            variants[parts[0].strip()] = parts[1].strip()

# Manual mapping from article model names to database model names
manual_map = {
    "byd seal 6 2026": "Seal",
    "byd sealion 5 dm i super phev": "Sealion 5 DM-i",
    "mg4 my2026 2": "MG4",
    "mg im 5 long range rwd": "IM5",
    "honda en2": "e:N2",
    "tesla model y l long wheelbase": None,  # Not in DB
    "nio firefly": None,  # Not in DB
    "zeekr x my2026": None,  # Not in DB
    "geely ex5 my2026": None,  # Not in DB
    "hyundai ioniq 5 n line ckd thailand 2nd lot": None,  # Not in DB
    "byd sealion 7 2026 awd ultimate": "Sealion 7",
    "gwm tank 500 diesel 2026": None,  # Not in DB
    "honda super one": "Super-ONE",
    "geely starray em r reev": None,  # Not in DB
    "honda city big minorchange 2026": "City",
    "honda accord 2026": "Accord",
    "mg urban 2026": "URBAN",
    "nissan kicks e power minorchange 2026": None,  # Not in DB
    "ford everest platinum my2026": None,  # Not in DB
    "ford ranger wildtrak x my2026": None,  # Not in DB
    "hyundai santa fe my2026": None,  # Not in DB
    "subaru crosstrek": None,  # Not in DB
    "mazda 6e edit": None,  # Not in DB
    "toyota land cruiser fj": None,  # Not in DB
    "bmw ix3 na5": None,  # Not in DB
    "toyota corolla altis my2026": "Corolla Altis",
    "suzuki jimny with safety support my2026": None,  # Not in DB
    "changan nevo q05": None,  # Not in DB
    "lepas l6": None,  # Not in DB
    "avatr 11 my2026": None,  # Not in DB
    "tesla model y thailand": None,  # Not in DB
    "tesla model 3 official thailand": None,  # Not in DB
    "offcial price denza z9gt ev bev thailand 2026": None,  # Not in DB
    "official special price byd seal 5 dm i phev plug in hybrid sep 2026": None,  # Not in DB
    "official price discount byd sealion 5 dm i phev sep 2026": "Sealion 5 DM-i",
    "official price discount byd atto 2 ev bev sep 2026": "ATTO 2",
    "xpeng l03 standard long range thailand specs": None,  # Not in DB
    "specification gwm tank 500 diesel 3000 turbo my2026": None,  # Not in DB
    "2026 08 14 picture specs honda super one": "Super-ONE",
    "2026 08 13 picture specs all new lexus es 350h grand luxury es 350e premium": None,  # Not in DB
    "2026 09 08 picture specs geely starray em r max": None,  # Not in DB
    "2026 09 28 picture specs mazda 6e exclusive": None,  # Not in DB
    "2026 09 26 picture specs toyota land cruiser fj edit": None,  # Not in DB
}

# Build model name to variant slug mapping
model_to_variants = {}
for slug, model_name in variants.items():
    if model_name not in model_to_variants:
        model_to_variants[model_name] = []
    model_to_variants[model_name].append(slug)

ingested = 0
skipped = 0
no_match = 0

for spec in specs:
    model_lower = spec["model"].lower()
    
    # Try manual mapping first
    db_model_name = manual_map.get(model_lower)
    
    if db_model_name is None:
        no_match += 1
        continue
    
    if db_model_name not in model_to_variants:
        skipped += 1
        continue
    
    variant_slug = model_to_variants[db_model_name][0]
    
    # Get variant ID
    result = subprocess.run(
        ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-t", "-A", "-c",
         f"SELECT id FROM \"Variant\" WHERE slug = '{variant_slug}' LIMIT 1;"],
        capture_output=True, text=True
    )
    variant_id = result.stdout.strip()
    
    if not variant_id:
        skipped += 1
        continue
    
    # Get or create source document
    content_hash = spec["content_hash"]
    result = subprocess.run(
        ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-t", "-A", "-c",
         f"SELECT id FROM \"SourceDocument\" WHERE \"contentHash\" = '{content_hash}' LIMIT 1;"],
        capture_output=True, text=True
    )
    sd_id = result.stdout.strip()
    
    if not sd_id:
        source_url = spec["source_url"].replace("'", "''")
        article_title = (spec.get("article_title") or "Spec Article").replace("'", "''")[:200]
        source_name = spec["source_name"].replace("'", "''")
        
        result = subprocess.run(
            ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-t", "-A", "-c",
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
        sd_id = result.stdout.strip()
    
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
    ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-t", "-A", "-c",
     'SELECT count(*) FROM "VariantSpec";'],
    capture_output=True, text=True
)
print(f"\nVariantSpec total: {result.stdout.strip()}")
print(f"This run: {ingested} ingested, {skipped} skipped, {no_match} no model match")
