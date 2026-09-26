#!/usr/bin/env python3
"""
Mitsubishi Thailand homepage extractor.
Source: mitsubishi-motors.co.th/th — server-rendered, prices in HTML.
Model-specific URLs return 404 — extract from homepage only.
Source class: OFFICIAL_WEB, trustState: QUALIFIED.
"""
import json
import hashlib
import re
import sys
import os
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(__file__))
from evidence_schema import Observation

MITSUBISHI_URL = "https://www.mitsubishi-motors.co.th/th"

MODEL_PATTERNS = {
    "Mirage": r"(?:Mirage|มิราจ)",
    "Attrage": r"(?:Attrage|แอททราจ)",
    "Xpander": r"(?:Xpander|เอ็กซ์팬เดอร์)",
    "Xpander Cross": r"(?:Xpander\s+Cross)",
    "Triton": r"(?:Triton|ไทรทัน)",
    "Pajero Sport": r"(?:Pajero\s+Sport|ปาเจโร่\s*สปอร์ต)",
}

def fetch_mitsubishi():
    req = Request(MITSUBISHI_URL, headers={
        "User-Agent": "Mozilla/5.0 Chrome/131",
        "Accept-Language": "th,en;q=0.9",
    })
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")

def extract_mitsubishi(html):
    observations = []
    rejections = []
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.I)
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    for model, pattern in MODEL_PATTERNS.items():
        # Find price near model name
        for m in re.finditer(
            pattern + r'.*?(\d{1,3}(?:,\d{3})+)\s*(?:บาท|฿)?',
            text, re.IGNORECASE | re.DOTALL
        ):
            price_str = m.group(1)
            price = int(price_str.replace(',', ''))
            if price < 200000 or price > 20000000:
                continue
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            excerpt = text[start:end]
            ch = hashlib.sha256(excerpt.encode()).hexdigest()[:16]
            observations.append({
                "brand": "mitsubishi", "model": model,
                "variant": "__MODEL_RANGE__", "scope": "MODEL",
                "obs_field": "price", "raw_value": str(price),
                "normalized_value": str(price), "unit": "THB",
                "price_type": "LIST_PRICE",
                "source_url": MITSUBISHI_URL, "source_class": "OFFICIAL_WEB",
                "extraction_method": "mitsubishi_homepage_regex",
                "evidence_excerpt": excerpt, "content_hash": ch,
                "trust_state": "QUALIFIED",
                "source_name": "Mitsubishi Thailand Website",
            })
            break  # One price per model from homepage

    return observations, rejections

if __name__ == "__main__":
    print("Fetching Mitsubishi homepage...")
    html = fetch_mitsubishi()
    obs, rej = extract_mitsubishi(html)
    print(f"Mitsubishi observations: {len(obs)}")
    print(json.dumps(obs, indent=2, ensure_ascii=False))
