#!/usr/bin/env python3
"""Bulk 9CARTHAI extraction — fetch all brand price pages and extract prices."""
import sys, os, json, hashlib, time, subprocess, re, importlib.util
from datetime import datetime

RUN_DIR = "/home/ubuntu/Projects/thai-car-intelligence/storage/research/runs/2026-09-20-9carthai"
PARSERS_DIR = os.path.join(os.path.dirname(__file__), "thai-media-extractors")

# Load 9carthai_parser (filename starts with digit, can't use normal import)
spec = importlib.util.spec_from_file_location(
    "ninecarthai_parser", os.path.join(PARSERS_DIR, "9carthai_parser.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
parse_brand_page = mod.parse_brand_page
BRAND_DISPLAY_NAMES = mod.BRAND_DISPLAY_NAMES

BRANDS = [
    "toyota", "honda", "nissan", "mazda", "mg", "byd", "gwm", "ford",
    "isuzu", "bmw", "mercedes-benz", "volvo", "chevrolet", "chery", "hyundai",
    "kia", "subaru", "mitsubishi", "suzuki", "lexus", "porsche", "mini",
    "tesla", "zeekr", "changan", "geely", "dongfeng", "ldv", "jetour",
    "baic", "kg-mobility", "denza"
]

def fetch_html(brand_slug):
    url = f"https://www.9carthai.com/{brand_slug}-price/"
    result = subprocess.run(
        ["curl", "-sL", "--max-time", "15", "-H",
         "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
         url],
        capture_output=True, text=True, timeout=20
    )
    return result.stdout

def extract_title(html):
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    return re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else ""

def write_brand_result(brand_slug, observations, rejections, source_url, title, status, failure_reason=""):
    brand_dir = os.path.join(RUN_DIR, brand_slug)
    os.makedirs(brand_dir, exist_ok=True)
    prices = []
    for obs in observations:
        prices.append({
            "brand": brand_slug, "model": obs.model, "variant": obs.variant,
            "amount": int(obs.normalized_value) if obs.normalized_value else None,
            "unit": "THB", "price_type": obs.price_type,
            "source_url": obs.source_url, "source_class": "AUTOMOTIVE_MEDIA",
            "trust_state": "RESEARCH_UNVERIFIED",
            "extraction_method": obs.extraction_method,
            "content_hash": obs.content_hash, "article_title": title,
            "observed_date": obs.observed_date,
        })
    result = {
        "brand": brand_slug,
        "brand_display": BRAND_DISPLAY_NAMES.get(brand_slug, brand_slug.upper()),
        "status": status, "source_url": source_url, "article_title": title,
        "prices": prices, "specs": [], "sources": [source_url],
        "failures": [{"reason": failure_reason}] if failure_reason else [],
        "rejection_count": len(rejections),
        "extraction_ts": datetime.now().isoformat(),
    }
    out_path = os.path.join(brand_dir, "9carthai.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return out_path

def main():
    os.makedirs(RUN_DIR, exist_ok=True)
    summary = {"started": datetime.now().isoformat(), "brands": {},
               "total_prices": 0, "total_rejections": 0, "brands_extracted": []}
    total = len(BRANDS)

    for i, brand in enumerate(BRANDS):
        print(f"\n[{i+1}/{total}] {brand}...")
        url = f"https://www.9carthai.com/{brand}-price/"
        try:
            html = fetch_html(brand)
            if len(html) < 500:
                print(f"  SKIP: {len(html)} bytes")
                write_brand_result(brand, [], [], url, "", "NOT_FOUND", f"Too short: {len(html)} bytes")
                summary["brands"][brand] = {"status": "NOT_FOUND", "prices": 0}
                continue

            title = extract_title(html)
            observations, rejections = parse_brand_page(html, brand, url)
            status = "OK" if observations else "NO_PRICES"
            write_brand_result(brand, observations, rejections, url, title, status,
                              "" if observations else "No model+price matches")

            models = list(set(o.model for o in observations))
            print(f"  Prices={len(observations)} Rejections={len(rejections)} Models={len(models)}")
            if models:
                print(f"  Models: {', '.join(models[:8])}")

            summary["brands"][brand] = {"status": status, "prices": len(observations),
                                         "rejections": len(rejections), "models": models}
            summary["total_prices"] += len(observations)
            summary["total_rejections"] += len(rejections)
            if observations:
                summary["brands_extracted"].append(brand)

        except Exception as e:
            print(f"  ERROR: {e}")
            write_brand_result(brand, [], [], url, "", "ERROR", str(e))
            summary["brands"][brand] = {"status": "ERROR", "prices": 0, "error": str(e)}

        if i < total - 1:
            time.sleep(1.5)

    # Write run summary
    n_ok = len(summary["brands_extracted"])
    summary["finished"] = datetime.now().isoformat()
    summary["brands_ok_count"] = n_ok
    summary["met_target_brands"] = n_ok >= 15
    summary["met_target_prices"] = summary["total_prices"] >= 100

    with open(os.path.join(RUN_DIR, "run_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"DONE: {n_ok}/{total} brands, {summary['total_prices']} prices")
    print(f"Target >=15 brands: {summary['met_target_brands']}")
    print(f"Target >=100 prices: {summary['met_target_prices']}")
    print(f"Output: {RUN_DIR}")

if __name__ == "__main__":
    main()
