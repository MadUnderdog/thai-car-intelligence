#!/usr/bin/env python3
"""Ingest deduped observations into database via Prisma/SQL."""
import json
import subprocess
import sys

# Load deduped observations
with open("/home/ubuntu/Projects/thai-car-intelligence/scripts/deduped-observations.json") as f:
    observations = json.load(f)

print(f"Ingesting {len(observations)} observations...")

# Group by source
sources = {}
for obs in observations:
    s = obs["source_name"]
    if s not in sources:
        sources[s] = {"tier": obs["source_tier"], "url": obs["source_url"], "observations": []}
    sources[s]["observations"].append(obs)

# Generate SQL for each source
sql_parts = []
sql_parts.append("-- Batch4 mass harvest ingestion")
sql_parts.append("BEGIN;")

for source_name, source_data in sources.items():
    domain = source_data["url"].split("/")[2] if "/" in source_data["url"] else "unknown"
    base_url = f"https://{domain}"
    
    # Insert source
    sql_parts.append(f"""
INSERT INTO "Source" ("id", "nameTh", "nameEn", "sourceType", "baseUrl", "domain", "rightsStatus", "status", "createdAt", "updatedAt")
VALUES (gen_random_uuid(), '{source_name}', '{source_name}', 'AUTOMOTIVE_MEDIA', '{base_url}', '{domain}', 'UNKNOWN', 'ACTIVE', NOW(), NOW())
ON CONFLICT ("nameEn") DO NOTHING;""")
    
    # Insert observations as SourceDocuments
    for obs in source_data["observations"][:50]:  # Cap per source
        title = obs.get("article_title", "").replace("'", "''")[:200] if obs.get("article_title") else "Unknown"
        url = obs["source_url"].replace("'", "''")
        excerpt = obs.get("source_excerpt", "").replace("'", "''")[:300]
        content_hash = obs["content_hash"]
        
        sql_parts.append(f"""
INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '{source_name}' LIMIT 1),
  '{url}',
  '{url}',
  '{title}',
  '{title}',
  'text/html',
  'th',
  '{content_hash}',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;""")

sql_parts.append("COMMIT;")

# Write SQL to file
sql_content = "\n".join(sql_parts)
with open("/home/ubuntu/Projects/thai-car-intelligence/scripts/batch4-ingest.sql", "w") as f:
    f.write(sql_content)

print(f"Generated SQL with {len(sql_parts)} statements")
print(f"Written to scripts/batch4-ingest.sql")

# Execute SQL
result = subprocess.run(
    ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence", "-f", "/dev/stdin"],
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
         'SELECT (SELECT count(*) FROM "Source") as sources, (SELECT count(*) FROM "SourceDocument") as documents, (SELECT count(*) FROM "Price" WHERE "isCurrent" = true AND "sourceDocumentId" IS NOT NULL) as verified_prices;'],
        capture_output=True,
        text=True
    )
    print(count_result.stdout)
else:
    print(f"SQL error: {result.stderr}", file=sys.stderr)
    sys.exit(1)
