#!/usr/bin/env python3
"""
9CARTHAI Parser — extracts model+trim+price from 9carthai.com brand price pages.

URL pattern: 9carthai.com/{brand}-price/ — one page per brand, ALL models listed.
Thai text pattern: "รุ่น {trim} ราคา {price}" — extract model name from surrounding context.
Prices are in Thai text nodes, NOT tables — use regex with context window.
Each brand page lists ALL variants — extract EVERY price line.

Key rules:
- Model identity comes from page headings + section context, NOT from regex alone
- Prices without explicit model/trim context are REJECTED
- Range-only values (599k-799k) → MODEL_RANGE, never first-variant MSRP
- Generic homepage/navigation prices → REJECTED unless exact scope proven
"""
import re
import sys
import os
import json
import hashlib
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(__file__))
from evidence_schema import Observation, RejectionRecord

THB_MIN = 150_000
THB_MAX = 25_000_000

# Brand slug → display names for URL matching
BRAND_DISPLAY_NAMES = {
    "toyota": "Toyota", "honda": "Honda", "nissan": "Nissan", "mazda": "Mazda",
    "mg": "MG", "byd": "BYD", "gwm": "GWM", "ford": "Ford", "isuzu": "Isuzu",
    "bmw": "BMW", "mercedes-benz": "Mercedes-Benz", "volvo": "Volvo",
    "chevrolet": "Chevrolet", "chery": "Chery", "hyundai": "Hyundai",
    "kia": "Kia", "subaru": "Subaru", "mitsubishi": "Mitsubishi",
    "suzuki": "Suzuki", "lexus": "Lexus", "porsche": "Porsche", "mini": "Mini",
    "tesla": "Tesla", "zeekr": "Zeekr", "nio": "NIO", "geely": "Geely",
    "dongfeng": "Dongfeng", "ldv": "LDV", "jetour": "Jetour",
    "baic": "BAIC", "changan": "Changan", "denza": "Denza",
    "kg-mobility": "KG Mobility", "avora": "Avora", "acura": "Acura",
}

# Known model aliases → canonical model names (for DB matching)
MODEL_ALIASES = {
    # Toyota
    "yaris ativa": "Yaris ATIV", "yaris ativ": "Yaris ATIV",
    "yaris cross": "Yaris Cross", "corolla altis": "Corolla Altis",
    "corolla cross": "Corolla Cross", "fortuner": "Fortuner",
    "hilux": "Hilux Revo", "hilux revo": "Hilux Revo", "innova": "Innova Crysta",
    "veloz": "Veloz", "avanza": "Avanza", "bz4x": "bZ4X",
    "land cruiser": "Land Cruiser", "alphard": "Alphard", "camry": "Camry",
    "prius": "Prius", "corolla": "Corolla Cross", "raize": "Raize",
    "yzaris": "Yaris", "yaris": "Yaris",
    # Honda
    "city": "City", "city hatchback": "City Hatchback", "civic": "Civic",
    "hr-v": "HR-V", "hrv": "HR-V", "cr-v": "CR-V", "crv": "CR-V",
    "br-v": "BR-V", "brv": "BR-V", "accord": "Accord", "wr-v": "WR-V",
    "wr-v:": "WR-V",
    # Nissan
    "almera": "Almera", "kicks": "Kicks e-POWER", "kicks e-power": "Kicks e-POWER",
    "x-trail": "X-Trail", "terra": "Terra", "navara": "Navara",
    "serena": "Serena", "leaf": "LEAF", "sakura": "Sakura",
    # MG
    "mg3": "MG3", "mg4": "MG4", "mg5": "MG5",
    "zs": "ZS", "hs": "HS", "im5": "IM5", "im6": "IM6",
    "s5": "S5 EV PLUS", "urban": "URBAN", "ep": "EP", "cyberster": "Cyberster",
    # BYD
    "atto 2": "Atto 2", "atto 3": "Atto 3", "dolphin": "Dolphin",
    "seal": "Seal", "sealion 7": "Sealion 7", "sealion7": "Sealion 7",
    "m6": "M6",
    # Mazda
    "mazda2": "Mazda2", "mazda3": "Mazda3", "cx-3": "CX-3",
    "cx-30": "CX-30", "cx-5": "CX-5", "cx-80": "CX-80", "6e": "Mazda 6e",
    # Mitsubishi
    "mirage": "Mirage", "attrage": "Attrage", "xpander": "Xpander",
    "triton": "Triton", "pajero sport": "Pajero Sport",
    # Isuzu
    "d-max": "D-Max", "dmax": "D-Max", "mu-x": "MU-X", "mux": "MU-X",
    # Ford
    "ranger": "Ranger", "everest": "Everest", "territory": "Territory",
    # Suzuki
    "swift": "Swift", "CELERIO": "Celerio", "CELERIO": "Celerio",
    "xl7": "XL7", "carry": "Carry",
    # BMW
    "1 series": "1 Series", "3 series": "3 Series", "5 series": "5 Series",
    "x1": "X1", "x3": "X3", "x5": "X5", "ix": "iX", "i5": "i5",
    # GWM
    "haval": "Haval", "haval jolion": "Haval Jolion", "haval h6": "Haval H6",
    "ora": "ORA", "ora good cat": "ORA Good Cat", "tank": "Tank",
    # Hyundai
    "stargazer": "Stargazer", "ioniq": "Ioniq", "ioniq 5": "Ioniq 5",
    "santa fe": "Santa Fe",
    # Kia
    "sonet": "Sonet", "sportage": "Sportage", "ev6": "EV6", "ev9": "EV9",
    "carnival": "Carnival",
    # Others
    "chery": "Chery", "omoda": "Omoda", "tiggo": "Tiggo", "jaecoo": "JAECOO",
    "zeekr": "Zeekr", "volvo": "Volvo", "xc40": "XC40", "xc60": "XC60",
    "porsche": "Porsche", "cayenne": "Cayenne", "macan": "Macan",
}


def normalize_model_name(raw: str) -> Optional[str]:
    """Map raw model text to canonical model name. Returns None if unrecognized."""
    key = raw.strip().lower()
    # Try exact match first
    if key in MODEL_ALIASES:
        return MODEL_ALIASES[key]
    # Try removing common prefixes
    for prefix in ["new ", "all new ", "all-new ", "the "]:
        if key.startswith(prefix):
            key = key[len(prefix):].strip()
            if key in MODEL_ALIASES:
                return MODEL_ALIASES[key]
    return None


def extract_price_number(text: str) -> Optional[int]:
    """Extract a numeric price from Thai text. Returns None if not found or out of range."""
    # Pattern: 1,299,000 or 1299000
    m = re.search(r'(\d{1,3}(?:,\d{3})+)', text)
    if m:
        val = int(m.group(1).replace(',', ''))
        if THB_MIN <= val <= THB_MAX:
            return val
    # Pattern: 1.299 ล้าน (1.299 million)
    m = re.search(r'([\d.]+)\s*ล้าน', text)
    if m:
        val = int(float(m.group(1)) * 1_000_000)
        if THB_MIN <= val <= THB_MAX:
            return val
    return None


def extract_range(text: str) -> Optional[Tuple[int, int]]:
    """Extract a price range (e.g. 599,000-799,000). Returns (min, max) or None."""
    m = re.search(r'(\d{1,3}(?:,\d{3})+)\s*[-–~]\s*(\d{1,3}(?:,\d{3})+)', text)
    if m:
        lo = int(m.group(1).replace(',', ''))
        hi = int(m.group(2).replace(',', ''))
        if THB_MIN <= lo <= hi <= THB_MAX:
            return (lo, hi)
    return None


def parse_brand_page(html: str, brand_slug: str, source_url: str) -> Tuple[List[Observation], List[RejectionRecord]]:
    """
    Parse a 9CARTHAI brand price page into observations + rejections.

    Strategy:
    1. Find model sections (h2/h3 headings with model names)
    2. Within each section, find trim+price pairs
    3. Reject prices without explicit model context
    4. Reject range-only values as MODEL_RANGE (not MSRP)
    """
    observations = []
    rejections = []
    brand_name = BRAND_DISPLAY_NAMES.get(brand_slug, brand_slug.upper())
    seen = set()  # Dedupe by (model, variant, price, source)

    # Remove HTML tags but preserve structure markers
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Extract headings and their following content
    # Split by headings to get model sections
    sections = re.split(r'<h[23][^>]*>(.*?)</h[23]>', text, flags=re.DOTALL | re.IGNORECASE)

    current_model = None
    for i, section in enumerate(sections):
        if i % 2 == 1:
            # This is a heading — try to extract model name
            heading_text = re.sub(r'<[^>]+>', '', section).strip()
            # Remove common prefixes
            heading_clean = re.sub(r'^\d+\.\s*', '', heading_text)
            heading_clean = re.sub(r'ราคา.*', '', heading_clean).strip()
            heading_clean = re.sub(r'\s*\d{4}.*', '', heading_clean).strip()

            # Try to find a model name in the heading
            for alias, canonical in MODEL_ALIASES.items():
                if alias.lower() in heading_clean.lower():
                    current_model = canonical
                    break
            continue

        if i % 2 == 0 and current_model:
            # This is content after a heading — extract prices
            content_text = re.sub(r'<[^>]+>', ' ', section)
            content_text = re.sub(r'\s+', ' ', content_text).strip()

            # Pattern 1: "รุ่น {trim} ราคา {price}"
            for m in re.finditer(r'รุ่น\s+([A-Za-z0-9\+\-\. :]{1,30}?)\s+ราคา\s*(\d[\d,]*)', content_text):
                trim_raw = m.group(1).strip()
                price = int(m.group(2).replace(',', ''))
                if not (THB_MIN <= price <= THB_MAX):
                    continue

                # Get excerpt
                start = max(0, m.start() - 50)
                end = min(len(content_text), m.end() + 50)
                excerpt = content_text[start:end]

                obs = Observation(
                    brand=brand_slug,
                    model=current_model,
                    variant=trim_raw,
                    scope="VARIANT",
                    obs_field="price",
                    raw_value=str(price),
                    normalized_value=str(price),
                    unit="THB",
                    price_type="MSRP",
                    source_url=source_url,
                    source_class="REFERENCE_MEDIA",
                    extraction_method="9carthai_brand_page_regex",
                    evidence_excerpt=excerpt,
                    content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
                    trust_state="RESEARCH_UNVERIFIED",
                    source_name="9CARTHAI",
                    source_tier="secondary_automotive_reference",
                )
                dedup_key = (obs.brand, obs.model, obs.variant, obs.normalized_value, obs.source_url)
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    observations.append(obs)

            # Pattern 2: "Model Trim : X,XXX,XXX" or "Model Trim X,XXX,XXX บาท"
            for m in re.finditer(
                rf'{re.escape(current_model)}\s+([A-Za-z0-9\+\-\. ]{{1,20}}?)\s*[:\s]\s*(\d[\d,]*)\s*(?:บาท|฿)?',
                content_text, re.IGNORECASE
            ):
                trim_raw = m.group(1).strip()
                price = int(m.group(2).replace(',', ''))
                if not (THB_MIN <= price <= THB_MAX):
                    continue
                if len(trim_raw) < 2:
                    continue  # Skip if trim name is too short

                start = max(0, m.start() - 50)
                end = min(len(content_text), m.end() + 50)
                excerpt = content_text[start:end]

                obs = Observation(
                    brand=brand_slug,
                    model=current_model,
                    variant=trim_raw,
                    scope="VARIANT",
                    obs_field="price",
                    raw_value=str(price),
                    normalized_value=str(price),
                    unit="THB",
                    price_type="MSRP",
                    source_url=source_url,
                    source_class="REFERENCE_MEDIA",
                    extraction_method="9carthai_brand_page_regex",
                    evidence_excerpt=excerpt,
                    content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
                    trust_state="RESEARCH_UNVERIFIED",
                    source_name="9CARTHAI",
                    source_tier="secondary_automotive_reference",
                )
                dedup_key = (obs.brand, obs.model, obs.variant, obs.normalized_value, obs.source_url)
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    observations.append(obs)

            # Pattern 2b: "Model Trim ราคา X,XXX,XXX" (ราคา between trim and price)
            for m in re.finditer(
                re.escape(current_model) + r'\s+([A-Za-z0-9\+\-\.: ]{1,20}?)\s*ราคา\s*(\d[\d,]*)',
                content_text, re.IGNORECASE
            ):
                trim_raw = m.group(1).strip()
                price = int(m.group(2).replace(',', ''))
                if not (THB_MIN <= price <= THB_MAX) or len(trim_raw) < 1:
                    continue
                start = max(0, m.start() - 50)
                end = min(len(content_text), m.end() + 50)
                excerpt = content_text[start:end]
                obs = Observation(
                    brand=brand_slug, model=current_model, variant=trim_raw,
                    scope="VARIANT", obs_field="price", raw_value=str(price),
                    normalized_value=str(price), unit="THB", price_type="MSRP",
                    source_url=source_url, source_class="REFERENCE_MEDIA",
                    extraction_method="9carthai_model_trim_price",
                    evidence_excerpt=excerpt,
                    content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
                    trust_state="RESEARCH_UNVERIFIED",
                    source_name="9CARTHAI",
                    source_tier="secondary_automotive_reference",
                )
                dedup_key = (obs.brand, obs.model, obs.variant, obs.normalized_value, obs.source_url)
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    observations.append(obs)

            # Pattern 3: Official price "ราคาอย่างเป็นทางการ Model X,XXX,XXX บาท"
            for m in re.finditer(
                r'ราคา(?:อย่างเป็นทางการ|เปิดตัว|เริ่มต้น)\s+.*?' + re.escape(current_model) + r'.*?(\d{1,3}(?:,\d{3})+)\s*บาท',
                content_text, re.IGNORECASE
            ):
                price = int(m.group(1).replace(',', ''))
                if not (THB_MIN <= price <= THB_MAX):
                    continue
                start = max(0, m.start() - 50)
                end = min(len(content_text), m.end() + 50)
                excerpt = content_text[start:end]
                obs = Observation(
                    brand=brand_slug, model=current_model,
                    variant="__MODEL_RANGE__", scope="MODEL",
                    obs_field="price", raw_value=str(price),
                    normalized_value=str(price), unit="THB",
                    price_type="LIST_PRICE",
                    source_url=source_url, source_class="REFERENCE_MEDIA",
                    extraction_method="9carthai_official_price",
                    evidence_excerpt=excerpt,
                    content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
                    trust_state="RESEARCH_UNVERIFIED",
                    source_name="9CARTHAI",
                    source_tier="secondary_automotive_reference",
                )
                dedup_key = (obs.brand, obs.model, obs.variant, obs.normalized_value, obs.source_url)
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    observations.append(obs)

            # Pattern 4: Range only → MODEL_RANGE
            rng = extract_range(content_text)
            if rng and not any(o.model == current_model and o.scope == "MODEL" for o in observations):
                obs = Observation(
                    brand=brand_slug,
                    model=current_model,
                    variant="__MODEL_RANGE__",
                    scope="MODEL",
                    obs_field="price",
                    raw_value=f"{rng[0]:,}-{rng[1]:,}",
                    normalized_value=str(rng[0]),
                    unit="THB",
                    price_type="LIST_PRICE",
                    source_url=source_url,
                    source_class="REFERENCE_MEDIA",
                    extraction_method="9carthai_brand_page_range",
                    evidence_excerpt=content_text[:200],
                    content_hash=hashlib.sha256(content_text[:200].encode()).hexdigest()[:16],
                    trust_state="RESEARCH_UNVERIFIED",
                    source_name="9CARTHAI",
                    source_tier="secondary_automotive_reference",
                )
                dedup_key = (obs.brand, obs.model, obs.variant, obs.normalized_value, obs.source_url)
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    observations.append(obs)

    # Catch-all: prices without model context → REJECT
    # Find all prices in the full text
    full_text = re.sub(r'<[^>]+>', ' ', html)
    full_text = re.sub(r'\s+', ' ', full_text).strip()

    prices_without_model = []
    for m in re.finditer(r'(\d{1,3}(?:,\d{3})+)\s*(?:บาท|฿)', full_text):
        val = int(m.group(1).replace(',', ''))
        if THB_MIN <= val <= THB_MAX:
            start = max(0, m.start() - 100)
            end = min(len(full_text), m.end() + 50)
            excerpt = full_text[start:end]
            prices_without_model.append((val, excerpt))

    # Check which prices are already covered
    covered_prices = set()
    for obs in observations:
        if obs.normalized_value:
            covered_prices.add(int(obs.normalized_value))

    for val, excerpt in prices_without_model:
        if val not in covered_prices:
            rejections.append(RejectionRecord(
                brand=brand_slug,
                model_hint="unknown",
                reason="price_without_model_context",
                source_url=source_url,
                evidence_excerpt=excerpt[:200],
                extraction_method="9carthai_brand_page_catchall",
            ))

    return observations, rejections


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: 9carthai-parser.py <brand_slug> <html_file>")
        sys.exit(1)

    brand_slug = sys.argv[1]
    html_file = sys.argv[2]

    with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    source_url = f"https://www.9carthai.com/{brand_slug}-price/"
    observations, rejections = parse_brand_page(html, brand_slug, source_url)

    result = {
        "brand": brand_slug,
        "observations": [o.to_dict() for o in observations],
        "rejections": [r.to_dict() for r in rejections],
        "summary": {
            "total_observations": len(observations),
            "total_rejections": len(rejections),
            "models_found": list(set(o.model for o in observations)),
        },
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
