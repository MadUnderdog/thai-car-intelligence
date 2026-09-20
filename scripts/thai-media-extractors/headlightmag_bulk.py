#!/usr/bin/env python3
"""Headlightmag Bulk Extraction with Pagination - fetch 30-50 articles."""
import re, sys, os, json, hashlib, time
from urllib.request import Request, urlopen
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict

sys.path.insert(0, os.path.dirname(__file__))

THB_MIN = 150_000
THB_MAX = 25_000_000
HL_BASE = "https://www.headlightmag.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "th,en;q=0.9",
}

BRAND_URL_PATTERNS = {
    "toyota": ["toyota", "yaris", "corolla", "camry", "fortuner", "hilux", "innova", "veloz", "avanza", "bz4x", "land-cruiser", "alphard", "raize", "prius"],
    "honda": ["honda", "city", "civic", "hr-v", "cr-v", "br-v", "accord", "wr-v"],
    "nissan": ["nissan", "almera", "kicks", "x-trail", "terra", "navara", "serena", "leaf", "sakura"],
    "mazda": ["mazda", "cx-3", "cx-30", "cx-5", "cx-80", "mazda2", "mazda3", "6e"],
    "mg": ["mg", "mg3", "mg4", "mg5", "zs-ev", "hs", "im5", "im6", "s5", "urban", "ep", "cyberster"],
    "byd": ["byd", "atto", "dolphin", "seal", "sealion", "m6"],
    "gwm": ["gwm", "haval", "ora", "tank"],
    "ford": ["ford", "ranger", "everest", "territory"],
    "isuzu": ["isuzu", "d-max", "mu-x"],
    "bmw": ["bmw", "series", "x1", "x3", "x5", "ix", "i5"],
    "mercedes-benz": ["mercedes", "benz", "glc", "gle", "gla", "eqa", "eqb"],
    "volvo": ["volvo", "xc40", "xc60", "xc90", "ex30"],
    "chevrolet": ["chevrolet", "trailblazer", "colorado"],
    "chery": ["chery", "omoda", "tiggo", "jaecoo"],
    "hyundai": ["hyundai", "stargazer", "ioniq", "santa-fe"],
    "kia": ["kia", "sonet", "sportage", "ev6", "ev9", "carnival"],
    "subaru": ["subaru", "crosstrek", "outback"],
    "mitsubishi": ["mitsubishi", "mirage", "attrage", "xpander", "triton", "pajero"],
    "suzuki": ["suzuki", "swift", "celerio", "xl7"],
    "porsche": ["porsche", "cayenne", "macan"],
    "mini": ["mini", "cooper", "countryman"],
    "zeekr": ["zeekr"],
    "lexus": ["lexus"],
}

# Common model name patterns for identification
MODEL_PATTERNS = {
    "toyota": ["Toyota", "Yaris", "Corolla", "Camry", "Fortuner", "Hilux", "Innova", "Veloz", "Avanza", "bZ4X", "Land Cruiser", "Alphard", "Raize", "Prius"],
    "honda": ["Honda", "City", "Civic", "HR-V", "CR-V", "BR-V", "Accord", "WR-V"],
    "nissan": ["Nissan", "Almera", "Kicks", "X-Trail", "Terra", "Navara", "Serena", "Leaf", "Sakura"],
    "mazda": ["Mazda", "CX-3", "CX-30", "CX-5", "CX-80", "Mazda2", "Mazda3", "6e"],
    "mg": ["MG", "MG3", "MG4", "MG5", "ZS EV", "HS", "IM5", "IM6", "S5", "Urban", "EP", "Cyberster"],
    "byd": ["BYD", "Atto", "Dolphin", "Seal", "Sealion", "M6"],
    "gwm": ["GWM", "Haval", "Ora", "Tank"],
    "ford": ["Ford", "Ranger", "Everest", "Territory"],
    "isuzu": ["Isuzu", "D-Max", "MU-X"],
    "bmw": ["BMW", "X1", "X3", "X5", "iX", "i5"],
    "mercedes-benz": ["Mercedes", "Benz", "GLC", "GLE", "GLA", "EQA", "EQB"],
    "volvo": ["Volvo", "XC40", "XC60", "XC90", "EX30"],
    "chevrolet": ["Chevrolet", "Trailblazer", "Colorado"],
    "chery": ["Chery", "Omoda", "Tiggo", "Jaecoo"],
    "hyundai": ["Hyundai", "Stargazer", "Ioniq", "Santa Fe"],
    "kia": ["Kia", "Sonet", "Sportage", "EV6", "EV9", "Carnival"],
    "subaru": ["Subaru", "Crosstrek", "Outback"],
    "mitsubishi": ["Mitsubishi", "Mirage", "Attrage", "Xpander", "Triton", "Pajero"],
    "suzuki": ["Suzuki", "Swift", "Celerio", "XL7"],
    "porsche": ["Porsche", "Cayenne", "Macan"],
    "mini": ["Mini", "Cooper", "Countryman"],
    "zeekr": ["Zeekr"],
    "lexus": ["Lexus"],
}

def fetch_page(url: str, retries: int = 2, delay: float = 1.0) -> Optional[str]:
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
                time.sleep(delay)
                return html
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
            else:
                print(f"  FAIL: {url} — {e}", file=sys.stderr)
                return None

def get_article_urls_from_category(html: str) -> List[str]:
    urls = set()
    for m in re.finditer(r'href="((?:https://www\.headlightmag\.com)?/[a-z0-9\-]+/)"', html, re.I):
        url = m.group(1)
        if url.startswith("/"):
            url = HL_BASE + url
        if any(skip in url.lower() for skip in ["/category/", "/tag/", "/author/", "/page/", "/wp-json", "/wp-content", "/wp-admin", ".xml", ".css", ".js"]):
            continue
        slug = url.rstrip("/").split("/")[-1].lower()
        if len(slug) > 5:
            urls.add(url)
    return list(urls)

def identify_brand_from_url(url: str) -> Optional[str]:
    slug = url.rstrip("/").split("/")[-1].lower()
    for brand, patterns in BRAND_URL_PATTERNS.items():
        for pattern in patterns:
            if pattern in slug:
                return brand
    return None

def identify_model_from_title(title: str) -> Optional[Tuple[str, str]]:
    """Returns (brand, model) with LONGEST match first.

    FIX: Original code returned the first match, which was often the brand
    name (e.g. "BYD") instead of the specific model (e.g. "Seal"). This
    caused all specs from the article to be attributed to the brand rather
    than the model, leading to cross-model contamination in the DB.
    """
    title_lower = title.lower()
    best_brand = None
    best_model = None
    best_len = 0
    for brand, models in MODEL_PATTERNS.items():
        for model in models:
            if model.lower() in title_lower and len(model) > best_len:
                best_brand = brand
                best_model = model
                best_len = len(model)
    if best_brand and best_model:
        return (best_brand, best_model)
    return None

def extract_prices_from_article(text: str, model_name: str, brand: str, source_url: str, article_title: str) -> List[Dict]:
    observations = []
    seen = set()
    clean = re.sub(r'\s+', ' ', text).strip()

    # Pattern 1: "Model Trim X,XXX,XXX"
    pattern1 = re.finditer(
        rf'(?:{re.escape(model_name)})\s+([A-Za-z0-9\+\-\. :]{1,25}?)\s*[:\s]\s*(\d{{1,3}}(?:,\d{{3}})+)',
        clean, re.IGNORECASE
    )
    for m in pattern1:
        trim_raw = (m.group(1) or "").strip()
        price_str = m.group(2) or ""
        if not price_str:
            continue
        price = int(price_str.replace(',', ''))
        if not (THB_MIN <= price <= THB_MAX) or len(trim_raw) < 2:
            continue
        excerpt = clean[max(0, m.start()-80):min(len(clean), m.end()+80)]
        content_hash = hashlib.sha256(f"{brand}:{model_name}:{trim_raw}:{price}".encode()).hexdigest()[:16]
        dedup_key = (brand, model_name, trim_raw, str(price), source_url)
        if dedup_key not in seen:
            seen.add(dedup_key)
            observations.append({
                "brand": brand, "model": model_name, "variant": trim_raw,
                "amount": price, "source_url": source_url,
                "source_class": "AUTOMOTIVE_MEDIA", "trust_state": "RESEARCH_UNVERIFIED",
                "extraction_method": "headlightmag_article_regex",
                "content_hash": content_hash, "article_title": article_title,
                "evidence_excerpt": excerpt
            })

    # Pattern 2: "รุ่น X ราคา X,XXX,XXX"
    pattern2 = re.finditer(r'รุ่น\s+([A-Za-z0-9\+\-\. ]{1,25}?)\s+ราคา\s*(\d[\d,]*)', clean)
    for m in pattern2:
        trim_raw = (m.group(1) or "").strip()
        price_str = m.group(2) or ""
        if not price_str:
            continue
        price = int(price_str.replace(',', ''))
        if not (THB_MIN <= price <= THB_MAX) or len(trim_raw) < 2:
            continue
        excerpt = clean[max(0, m.start()-80):min(len(clean), m.end()+80)]
        content_hash = hashlib.sha256(f"{brand}:{model_name}:{trim_raw}:{price}".encode()).hexdigest()[:16]
        dedup_key = (brand, model_name, trim_raw, str(price), source_url)
        if dedup_key not in seen:
            seen.add(dedup_key)
            observations.append({
                "brand": brand, "model": model_name, "variant": trim_raw,
                "amount": price, "source_url": source_url,
                "source_class": "AUTOMOTIVE_MEDIA", "trust_state": "RESEARCH_UNVERIFIED",
                "extraction_method": "headlightmag_article_thai_pattern",
                "content_hash": content_hash, "article_title": article_title,
                "evidence_excerpt": excerpt
            })

    # Pattern 3: "ราคาอย่างเป็นทางการ Model : X,XXX,XXX บาท"
    pattern3 = re.finditer(r'ราคา(?:อย่างเป็นทางการ|เปิดตัว|เริ่มต้น)\s+.*?' + re.escape(model_name) + r'.*?(\d{1,3}(?:,\d{3})+)\s*บาท', clean, re.IGNORECASE)
    for m in pattern3:
        price_str = m.group(1) or ""
        if not price_str:
            continue
        price = int(price_str.replace(',', ''))
        if not (THB_MIN <= price <= THB_MAX):
            continue
        excerpt = clean[max(0, m.start()-50):min(len(clean), m.end()+50)]
        content_hash = hashlib.sha256(f"{brand}:{model_name}:__MODEL_RANGE__:{price}".encode()).hexdigest()[:16]
        dedup_key = (brand, model_name, "__MODEL_RANGE__", str(price), source_url)
        if dedup_key not in seen:
            seen.add(dedup_key)
            observations.append({
                "brand": brand, "model": model_name, "variant": "__MODEL_RANGE__",
                "amount": price, "source_url": source_url,
                "source_class": "AUTOMOTIVE_MEDIA", "trust_state": "RESEARCH_UNVERIFIED",
                "extraction_method": "headlightmag_article_official_price",
                "content_hash": content_hash, "article_title": article_title,
                "evidence_excerpt": excerpt
            })

    # Pattern 4: Table-like "Trim | Price" rows
    pattern4 = re.finditer(r'([A-Z][A-Za-z0-9\+\-\.]{1,15})\s*\|\s*(\d{1,3}(?:,\d{3})+)', clean)
    for m in pattern4:
        trim_raw = m.group(1).strip()
        price_str = m.group(2)
        if not price_str:
            continue
        price = int(price_str.replace(',', ''))
        if not (THB_MIN <= price <= THB_MAX) or len(trim_raw) < 2:
            continue
        excerpt = clean[max(0, m.start()-80):min(len(clean), m.end()+80)]
        content_hash = hashlib.sha256(f"{brand}:{model_name}:{trim_raw}:{price}".encode()).hexdigest()[:16]
        dedup_key = (brand, model_name, trim_raw, str(price), source_url)
        if dedup_key not in seen:
            seen.add(dedup_key)
            observations.append({
                "brand": brand, "model": model_name, "variant": trim_raw,
                "amount": price, "source_url": source_url,
                "source_class": "AUTOMOTIVE_MEDIA", "trust_state": "RESEARCH_UNVERIFIED",
                "extraction_method": "headlightmag_article_table_row",
                "content_hash": content_hash, "article_title": article_title,
                "evidence_excerpt": excerpt
            })

    # Pattern 5: Generic price extraction around model name
    pattern5 = re.finditer(
        rf'{re.escape(model_name)}.*?(\d{{1,3}}(?:,\d{{3}})+)\s*(?:บาท|฿)',
        clean, re.IGNORECASE | re.DOTALL
    )
    for m in pattern5:
        price_str = m.group(1) or ""
        if not price_str:
            continue
        price = int(price_str.replace(',', ''))
        if not (THB_MIN <= price <= THB_MAX):
            continue
        excerpt = clean[max(0, m.start()-50):min(len(clean), m.end()+50)]
        content_hash = hashlib.sha256(f"{brand}:{model_name}:__GENERIC__:{price}".encode()).hexdigest()[:16]
        dedup_key = (brand, model_name, "__GENERIC__", str(price), source_url)
        if dedup_key not in seen:
            seen.add(dedup_key)
            observations.append({
                "brand": brand, "model": model_name, "variant": "__GENERIC__",
                "amount": price, "source_url": source_url,
                "source_class": "AUTOMOTIVE_MEDIA", "trust_state": "RESEARCH_UNVERIFIED",
                "extraction_method": "headlightmag_article_generic_price",
                "content_hash": content_hash, "article_title": article_title,
                "evidence_excerpt": excerpt
            })

    # Extract specs
    specs = []
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:แรงม้า|horsepower|hp|PS)\b', clean, re.I):
        val = float(m.group(1))
        if 30 <= val <= 1000:
            excerpt = clean[max(0, m.start()-50):min(len(clean), m.end()+50)]
            specs.append({"field": "power_hp", "value": str(val), "unit": "hp", "excerpt": excerpt})
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:Nm|นิวตันเมตร)\b', clean, re.I):
        val = float(m.group(1))
        if 50 <= val <= 1000:
            excerpt = clean[max(0, m.start()-50):min(len(clean), m.end()+50)]
            specs.append({"field": "torque_nm", "value": str(val), "unit": "Nm", "excerpt": excerpt})
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*kWh', clean, re.I):
        val = float(m.group(1))
        if 10 <= val <= 200:
            excerpt = clean[max(0, m.start()-50):min(len(clean), m.end()+50)]
            specs.append({"field": "battery_kwh", "value": str(val), "unit": "kWh", "excerpt": excerpt})

    # Add specs as observations
    for spec in specs:
        content_hash = hashlib.sha256(f"{brand}:{model_name}:{spec['field']}:{spec['value']}".encode()).hexdigest()[:16]
        observations.append({
            "brand": brand, "model": model_name, "variant": "__MODEL__",
            "field": spec["field"], "value": spec["value"], "unit": spec["unit"],
            "source_url": source_url, "source_class": "AUTOMOTIVE_MEDIA",
            "trust_state": "RESEARCH_UNVERIFIED",
            "extraction_method": "headlightmag_article_spec_regex",
            "content_hash": content_hash, "article_title": article_title,
            "evidence_excerpt": spec["excerpt"]
        })

    return observations

def extract_title_from_html(html: str) -> str:
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return ""

def run_extraction(max_articles: int = 50):
    """Full extraction with pagination."""
    all_observations = []
    stats = {"articles_fetched": 0, "articles_with_prices": 0, "total_prices": 0, "total_specs": 0}

    # Category URLs with pagination
    categories = [
        f"{HL_BASE}/category/news/new-cars-in-thailand/",
        f"{HL_BASE}/category/news/",
    ]

    article_urls: Set[str] = set()

    # Fetch multiple pages per category
    for cat_url in categories:
        for page in range(1, 6):  # Pages 1-5
            page_url = f"{cat_url}page/{page}/" if page > 1 else cat_url
            print(f"  Fetching category page: {page_url}", file=sys.stderr)
            html = fetch_page(page_url, delay=1.5)
            if html:
                urls = get_article_urls_from_category(html)
                new_urls = set(urls) - article_urls
                new_count = len(new_urls)
                article_urls.update(urls)
                print(f"    Found {len(urls)} URLs, {new_count} new", file=sys.stderr)
            else:
                print(f"    Failed to fetch page {page}", file=sys.stderr)
                break

    print(f"\n  Total unique article URLs: {len(article_urls)}", file=sys.stderr)

    # Process articles
    processed = 0
    for url in sorted(article_urls):
        if processed >= max_articles:
            break

        brand = identify_brand_from_url(url)
        if not brand:
            continue

        print(f"  Processing [{processed+1}/{max_articles}]: {url[:60]}...", file=sys.stderr)
        html = fetch_page(url, delay=1.0)
        if not html:
            continue

        title = extract_title_from_html(html)
        model_info = identify_model_from_title(title)
        if not model_info:
            # Try from URL slug
            slug = url.rstrip("/").split("/")[-1].lower()
            for b, models in MODEL_PATTERNS.items():
                for model in models:
                    if model.lower() in slug:
                        model_info = (b, model)
                        break
                if model_info:
                    break

        if not model_info:
            print(f"    No model identified: {title[:50]}", file=sys.stderr)
            continue

        brand, model_name = model_info

        # Extract text
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        obs = extract_prices_from_article(text, model_name, brand, url, title)
        all_observations.extend(obs)

        prices = [o for o in obs if "amount" in o]
        specs = [o for o in obs if "field" in o]
        stats["articles_fetched"] += 1
        if prices:
            stats["articles_with_prices"] += 1
            stats["total_prices"] += len(prices)
        stats["total_specs"] += len(specs)

        processed += 1
        time.sleep(0.5)

    return all_observations, stats

if __name__ == "__main__":
    max_articles = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    run_dir = "/home/ubuntu/Projects/thai-car-intelligence/storage/research/runs/2026-09-20-headlightmag"
    os.makedirs(run_dir, exist_ok=True)

    print(f"Starting Headlightmag bulk extraction (max {max_articles} articles)...", file=sys.stderr)
    observations, stats = run_extraction(max_articles)

    # Write raw extraction
    result = {
        "run_id": f"hl-bulk-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "stats": stats,
        "observations": observations,
    }
    raw_path = os.path.join(run_dir, "headlightmag-extraction.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Write per-brand artifacts
    brand_obs = {}
    for obs in observations:
        brand = obs.get("brand", "unknown")
        if brand not in brand_obs:
            brand_obs[brand] = {"prices": [], "specs": [], "sources": set(), "failures": []}
        if "amount" in obs:
            brand_obs[brand]["prices"].append(obs)
        elif "field" in obs:
            brand_obs[brand]["specs"].append(obs)
        brand_obs[brand]["sources"].add(obs.get("source_url", ""))

    for brand, data in brand_obs.items():
        brand_dir = os.path.join(run_dir, brand)
        os.makedirs(brand_dir, exist_ok=True)
        brand_data = {
            "brand": brand,
            "prices": data["prices"],
            "specs": data["specs"],
            "sources": list(data["sources"]),
            "failures": data["failures"],
        }
        with open(os.path.join(brand_dir, "headlightmag.json"), "w", encoding="utf-8") as f:
            json.dump(brand_data, f, indent=2, ensure_ascii=False)

    print(f"\nResults written to: {run_dir}", file=sys.stderr)
    print(f"  Total observations: {len(observations)}", file=sys.stderr)
    print(f"  Stats: {json.dumps(stats, indent=2)}", file=sys.stderr)

    # Summary to stdout
    print(json.dumps({
        "run_id": result["run_id"],
        "stats": stats,
        "brands_found": list(brand_obs.keys()),
        "total_price_observations": stats["total_prices"],
    }, indent=2))
