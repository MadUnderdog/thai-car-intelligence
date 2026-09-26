#!/usr/bin/env python3
"""Deduplicate and ingest harvested observations into database."""
import json
import hashlib
from urllib.request import Request, urlopen

# Load harvested observations
with open("/home/ubuntu/Projects/thai-car-intelligence/scripts/harvested-observations.json") as f:
    raw = json.load(f)

print(f"Raw observations: {len(raw)}")

# Deduplicate by content_hash
seen = set()
deduped = []
for obs in raw:
    key = obs["content_hash"]
    if key not in seen:
        seen.add(key)
        deduped.append(obs)

print(f"After dedup: {len(deduped)}")

# Filter to reasonable prices (300k-10M THB)
filtered = [o for o in deduped if 300000 <= o["reported_price"] <= 10000000]
print(f"After price filter: {len(filtered)}")

# Count by source
sources = {}
for o in filtered:
    s = o["source_name"]
    sources[s] = sources.get(s, 0) + 1
print("\nBy source:")
for s, c in sorted(sources.items(), key=lambda x: -x[1]):
    print(f"  {s}: {c}")

# Write deduped observations
with open("/home/ubuntu/Projects/thai-car-intelligence/scripts/deduped-observations.json", "w") as f:
    json.dump(filtered, f, ensure_ascii=False, indent=2)

print(f"\nWritten {len(filtered)} deduped observations")
