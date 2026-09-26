#!/usr/bin/env python3
"""Combine all extraction artifacts into a single pipeline-output.json for db_integration."""
import json, os, hashlib, sys

RUNS_BASE = "/home/ubuntu/Projects/thai-car-intelligence/storage/research/runs"
OUTPUT = os.path.join(RUNS_BASE, "2026-09-20", "combined-pipeline-output.json")

all_obs = []

# 1. Load Toyota OEM API observations
api_path = os.path.join(RUNS_BASE, "2026-09-20-oem-api", "pipeline-output.json")
if os.path.exists(api_path):
    with open(api_path) as f:
        data = json.load(f)
    obs = data.get("accepted_observations", [])
    print(f"OEM API: {len(obs)} observations")
    all_obs.extend(obs)

# 2. Load 9CARTHAI brand observations
carthai_dir = os.path.join(RUNS_BASE, "2026-09-20-9carthai")
if os.path.isdir(carthai_dir):
    for brand in sorted(os.listdir(carthai_dir)):
        fpath = os.path.join(carthai_dir, brand, "9carthai.json")
        if not os.path.exists(fpath):
            continue
        with open(fpath) as f:
            data = json.load(f)
        prices = data.get("prices", [])
        for p in prices:
            # Normalize 9CARTHAI format to db_integration format
            obs = {
                "brand": p.get("brand", brand),
                "model": p.get("model", ""),
                "variant": p.get("variant", "__MODEL_RANGE__"),
                "obs_field": "price",
                "raw_value": str(p.get("amount", 0)),
                "normalized_value": str(p.get("amount", 0)),
                "unit": "THB",
                "source_url": p.get("source_url", ""),
                "source_class": p.get("source_class", "AUTOMOTIVE_MEDIA"),
                "extraction_method": p.get("extraction_method", "9carthai"),
                "content_hash": p.get("content_hash", ""),
                "article_title": p.get("article_title", ""),
                "price_type": p.get("price_type", "MSRP"),
            }
            all_obs.append(obs)
        if prices:
            print(f"9CARTHAI/{brand}: {len(prices)} prices")

# 3. Load Headlightmag if available
hl_dir = os.path.join(RUNS_BASE, "2026-09-20-headlightmag")
if os.path.isdir(hl_dir):
    for brand in sorted(os.listdir(hl_dir)):
        fpath = os.path.join(hl_dir, brand, "headlightmag.json")
        if not os.path.exists(fpath):
            continue
        with open(fpath) as f:
            data = json.load(f)
        prices = data.get("prices", [])
        for p in prices:
            obs = {
                "brand": p.get("brand", brand),
                "model": p.get("model", ""),
                "variant": p.get("variant", "__MODEL_RANGE__"),
                "obs_field": "price",
                "raw_value": str(p.get("price_thb", p.get("amount", 0))),
                "normalized_value": str(p.get("price_thb", p.get("amount", 0))),
                "unit": "THB",
                "source_url": p.get("source_url", ""),
                "source_class": "AUTOMOTIVE_MEDIA",
                "extraction_method": p.get("extraction_method", "headlightmag"),
                "content_hash": p.get("content_hash", hashlib.sha256(str(p.get("price_thb",0)).encode()).hexdigest()[:16]),
                "article_title": p.get("article_title", ""),
                "price_type": p.get("price_type", "MSRP"),
            }
            all_obs.append(obs)
        if prices:
            print(f"Headlightmag/{brand}: {len(prices)} prices")

# Write combined output
output = {
    "accepted_observations": all_obs,
    "rejected_candidates": [],
    "quarantined_candidates": [],
}
with open(OUTPUT, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\nTotal: {len(all_obs)} observations written to {OUTPUT}")
