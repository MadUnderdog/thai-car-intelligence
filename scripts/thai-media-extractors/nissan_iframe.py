#!/usr/bin/env python3
"""
Nissan Thailand iframe JSON extractor.
Source: Hidden iframe with id="allVehiclesModelPriceJSON" on all Nissan pages.
Returns JSON dict keyed by model slug — each entry has default.modelPrice.
Source class: OFFICIAL_WEB, trustState: QUALIFIED.

CRITICAL: Never flatten all prices to one model. Each slug key = one model.
Reject: test-gt-r, kicks-e-power-sky-edition (test/special data).
"""
import json
import hashlib
import re
import sys
import os
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(__file__))
from evidence_schema import Observation

NISSAN_URLS = [
    "https://www.nissan.co.th/en",
    "https://www.nissan.co.th/th",
]

REJECTED_KEYS = {"test-gt-r", "kicks-e-power-sky-edition"}

def fetch_nissan_page(url):
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 Chrome/131",
        "Accept-Language": "th,en;q=0.9",
    })
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")

def extract_nissan_iframe(html):
    """Extract the JSON from the hidden iframe."""
    m = re.search(r'id="allVehiclesModelPriceJSON"[^>]*>\s*(.*?)\s*</iframe', html, re.DOTALL)
    if not m:
        # Try finding JSON in script tags
        m = re.search(r'allVehiclesModelPriceJSON.*?(\{.*?\})\s*;?\s*</script', html, re.DOTALL)
    if not m:
        return None
    raw = m.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try fixing common issues
        raw = re.sub(r'<[^>]+>', '', raw)
        try:
            return json.loads(raw)
        except:
            return None

# Known modelCode → canonical model mapping
CODE_MAP = {
    "N17": "March", "L13": "Almera", "P12": "Kicks e-POWER",
    "T33": "X-Trail", "Y62": "Terra", "D23": "Navara",
    "C27": "Serena", "ZE1": "LEAF", "AE0": "Sakura",
}

def extract_nissan():
    observations = []
    rejections = []

    for url in NISSAN_URLS:
        try:
            html = fetch_nissan_page(url)
        except Exception as e:
            print(f"  FAIL: {url} — {e}", file=sys.stderr)
            continue

        data = extract_nissan_iframe(html)
        if not data:
            continue

        for slug, info in data.items():
            if slug in REJECTED_KEYS:
                rejections.append({
                    "brand": "nissan", "model_hint": slug,
                    "reason": "rejected_test_data_key",
                    "source_url": url,
                    "evidence_excerpt": json.dumps(info, ensure_ascii=False)[:200],
                })
                continue

            # Get price from default or Retail
            default = info.get("default", {})
            retail = info.get("Retail", {})
            price_str = default.get("modelPrice") or retail.get("modelPrice", "")
            model_code = info.get("modelCode", "")

            if not price_str:
                rejections.append({
                    "brand": "nissan", "model_hint": slug,
                    "reason": "no_price_in_iframe",
                    "source_url": url,
                })
                continue

            # Parse price
            price_clean = re.sub(r"[^\d]", "", str(price_str))
            if not price_clean:
                continue
            price = int(price_clean)
            if price < 200000 or price > 20000000:
                rejections.append({
                    "brand": "nissan", "model_hint": slug,
                    "reason": f"price_out_of_range_{price}",
                    "source_url": url,
                })
                continue

            # Map modelCode to canonical name
            canonical = CODE_MAP.get(model_code, slug.replace("-", " ").title())

            excerpt = json.dumps({"slug": slug, "modelCode": model_code,
                                  "modelPrice": price_str}, ensure_ascii=False)
            ch = hashlib.sha256(excerpt.encode()).hexdigest()[:16]

            observations.append({
                "brand": "nissan", "model": canonical,
                "variant": "__MODEL_RANGE__", "scope": "MODEL",
                "obs_field": "price", "raw_value": str(price),
                "normalized_value": str(price), "unit": "THB",
                "price_type": "LIST_PRICE",
                "source_url": url, "source_class": "OFFICIAL_WEB",
                "extraction_method": "nissan_iframe_json",
                "evidence_excerpt": excerpt, "content_hash": ch,
                "trust_state": "QUALIFIED",
                "source_name": "Nissan Thailand Website",
                "raw_json_path": f"iframe_json[{slug}]",
            })

    return observations, rejections

if __name__ == "__main__":
    obs, rej = extract_nissan()
    print(f"Nissan observations: {len(obs)}")
    print(f"Nissan rejections: {len(rej)}")
    print(json.dumps(obs + rej, indent=2, ensure_ascii=False))
