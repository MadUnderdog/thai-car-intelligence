#!/usr/bin/env python3
"""Ingest v2 spec observations with proper variant mapping."""
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

print(f"Variants: {len(variants)}")

# Build mapping from model names to variant slugs
model_variant_map = {}
for slug, model_name in variants.items():
    model_lower = model_name.lower()
    if model_lower not in model_variant_map:
        model_variant_map[model_lower] = []
    model_variant_map[model_lower].append(slug)

ingested = 0
skipped = 0
no_match = 0

for spec in specs:
    model_lower = spec["model"].lower()
    
    # Try exact match first
    variant_slug = None
    if model_lower in model_variant_map:
        variant_slug = model_variant_map[model_lower][0]
    else:
        # Try fuzzy match
        for model_name, slugs in model_variant_map.items():
            model_words = set(model_lower.split())
            db_words = set(model_name.lower().split())
            common = model_words & db_words
            if len(common) >= 2 or (len(common) >= 1 and any(w in model_lower for w in ["honda", "byd", "mg", "toyota"])):
                variant_slug = slugs[0]
                break
    
    if not variant_slug:
        no_match += 1
        continue
    
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
