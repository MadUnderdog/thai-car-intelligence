#!/usr/bin/env python3
"""
Headlightmag Bulk Extractor — traverses WordPress category archive,
collects article URLs, extracts model+variant+price from rendered text.

Source class: AUTO_MEDIA, trustState: RESEARCH_UNVERIFIED.
NEVER promote to VERIFIED — this is secondary media evidence.

Pipeline:
1. Fetch category archive pages (not homepage)
2. Extract article URLs (WordPress slugs, no .html extension)
3. Filter to model-specific articles (exclude category/tag/author)
4. Extract rendered text from each article
5. Match article to VehicleUniverse by model name
6. Extract trim+price pairs from article text
7. Extract spec fields when present
8. Persist with full provenance

MODEL SCOPE VALIDATION:
  All extraction patterns validate that the identified model name appears
  within a context window around each match. This prevents cross-model
  contamination where specs from competitor models mentioned in the article
  get incorrectly attributed to the article's subject model.
"""
import re
import sys
import os
import json
import hashlib
import time
from typing import List, Dict, Optional, Tuple, Set
from urllib.request import Request, urlopen
from urllib.error import URLError
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from evidence_schema import Observation, RejectionRecord

THB_MIN = 150_000
THB_MAX = 25_000_000
HL_BASE = "https://www.headlightmag.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "th,en;q=0.9",
}
CATEGORY_URLS = [
    f"{HL_BASE}/category/news/new-cars-in-thailand/",
    f"{HL_BASE}/category/news/",
]

# ─── Model context validation ────────────────────────────────────────
# ROOT CAUSE: Automotive articles mention competitor models for comparison.
# Without context validation, generic patterns like "รุ่น X ราคา Y" or
# spec regexes attribute data from ANY model to the article's subject model,
# causing cross-model contamination (e.g., 159 specs from a single BYD Seal 6
# article attributed to 43 different models).

# Context window (chars) to search for model name around a match.
# 300 chars ≈ 1-2 paragraphs; stays within the same discussion section.
MODEL_CONTEXT_WINDOW = 300


def _build_model_search_patterns(model_name: str, brand: str = "") -> list:
    """Build regex patterns to search for the model in article text."""
    patterns = []
    patterns.append(re.compile(re.escape(model_name), re.IGNORECASE))
    if brand:
        patterns.append(re.compile(
            rf'{re.escape(brand)}\s*{re.escape(model_name)}',
            re.IGNORECASE
        ))
    patterns.append(re.compile(
        rf'{re.escape(model_name)}\s*\d',
        re.IGNORECASE
    ))
    return patterns


def _is_in_model_context(
    clean_text: str,
    match_start: int,
    match_end: int,
    model_patterns: list,
    window: int = MODEL_CONTEXT_WINDOW
) -> bool:
    """Check if model name appears within context window around a match."""
    ctx_start = max(0, match_start - window)
    ctx_end = min(len(clean_text), match_end + window)
    context = clean_text[ctx_start:ctx_end]
    for pat in model_patterns:
        if pat.search(context):
            return True
    return False


def _validate_article_model_scope(
    title: str,
    url: str,
    headings: list,
    model_patterns: list
) -> bool:
    """Validate that the identified model is actually the article's subject."""
    for pat in model_patterns:
        if pat.search(title):
            return True
    slug = url.rstrip("/").split("/")[-1].lower()
    for pat in model_patterns:
        if pat.search(slug):
            return True
    for heading in headings:
        for pat in model_patterns:
            if pat.search(heading):
                return True
    return False


def _extract_headings_from_html(html: str) -> list:
    """Extract h1, h2, h3 heading text from HTML."""
    headings = []
    for m in re.finditer(r'<h[1-3][^>]*>(.*?)</h[1-3]>', html, re.DOTALL | re.IGNORECASE):
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if text:
            headings.append(text)
    return headings


# Import model aliases from 9carthai_parser
from importlib.util import spec_from_file_location, module_from_spec
_parser_spec = spec_from_file_location("parser", os.path.join(os.path.dirname(__file__), "9carthai_parser.py"))
_parser_mod = module_from_spec(_parser_spec)
_parser_spec.loader.exec_module(_parser_mod)
normalize_model_name = _parser_mod.normalize_model_name
MODEL_ALIASES = _parser_mod.MODEL_ALIASES

# Headlightmag brand patterns for article URL matching
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


def fetch_page(url: str, retries: int = 2, delay: float = 1.0) -> Optional[str]:
    """Fetch a URL with retries and polite delay."""
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
                time.sleep(delay)  # Be polite
                return html
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
            else:
                print(f"  FAIL: {url} — {e}", file=sys.stderr)
                return None


def get_article_urls_from_category(html: str) -> List[str]:
    """Extract article URLs from a Headlightmag category page."""
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
    """Identify brand from article URL slug."""
    slug = url.rstrip("/").split("/")[-1].lower()
    for brand, patterns in BRAND_URL_PATTERNS.items():
        for pattern in patterns:
            if pattern in slug:
                return brand
    return None


def identify_model_from_title(title: str) -> Optional[str]:
    """Identify model from article title."""
    title_lower = title.lower()
    best_match = None
    best_len = 0
    for alias, canonical in sorted(MODEL_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias.lower() in title_lower:
            if len(alias) > best_len:
                best_match = canonical
                best_len = len(alias)
    return best_match


def extract_prices_from_article(text: str, model_name: str, brand: str, source_url: str, article_title: str) -> Tuple[List[Observation], List[RejectionRecord]]:
    """Extract variant+price pairs from article text.

    MODEL SCOPE VALIDATION: Patterns 2, 4, and all spec extraction patterns
    require the model name to appear within MODEL_CONTEXT_WINDOW characters
    of the match. This prevents cross-model contamination where competitor
    specs/prices mentioned in comparison sections get attributed to the
    article's subject model.
    """
    observations = []
    rejections = []
    seen = set()

    # Build model context patterns for validation
    model_patterns = _build_model_search_patterns(model_name, brand)

    # Clean text
    clean = re.sub(r'\s+', ' ', text).strip()

    # Pattern 1: "Model Trim X,XXX,XXX" or "Model Trim: X,XXX,XXX"
    # SAFE: Model name is explicitly in the pattern — no context check needed
    pattern1 = re.finditer(
        rf'(?:{re.escape(model_name)})\s+([A-Za-z0-9\+\-\. :]{1,25}?)\s*[:\s]\s*(\d{1,3}(?:,\d{3})+)',
        clean, re.IGNORECASE
    )
    for m in pattern1:
        trim_raw = m.group(1).strip()
        price = int(m.group(2).replace(',', ''))
        if not (THB_MIN <= price <= THB_MAX) or len(trim_raw) < 2:
            continue

        start = max(0, m.start() - 80)
        end = min(len(clean), m.end() + 80)
        excerpt = clean[start:end]

        obs = Observation(
            brand=brand,
            model=model_name,
            variant=trim_raw,
            scope="VARIANT",
            obs_field="price",
            raw_value=str(price),
            normalized_value=str(price),
            unit="THB",
            price_type="MSRP",
            source_url=source_url,
            source_class="AUTO_MEDIA",
            extraction_method="headlightmag_article_regex",
            evidence_excerpt=excerpt,
            content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
            trust_state="RESEARCH_UNVERIFIED",
            article_title=article_title,
            source_name="HeadLight Magazine",
            source_tier="secondary_automotive_media",
        )
        dedup_key = (obs.brand, obs.model, obs.variant, obs.normalized_value, obs.source_url)
        if dedup_key not in seen:
            seen.add(dedup_key)
            observations.append(obs)

    # Pattern 1b: "Model Trim ราคา X,XXX,XXX"
    # SAFE: Model name is explicitly in the pattern
    pattern1b = re.finditer(
        re.escape(model_name) + r'\s+([A-Za-z0-9\+\-\.: ]{1,25}?)\s*ราคา\s*(\d{1,3}(?:,\d{3})+)',
        clean, re.IGNORECASE
    )
    for m in pattern1b:
        trim_raw = m.group(1).strip()
        price = int(m.group(2).replace(',', ''))
        if not (THB_MIN <= price <= THB_MAX) or len(trim_raw) < 2:
            continue
        start = max(0, m.start() - 80)
        end = min(len(clean), m.end() + 80)
        excerpt = clean[start:end]
        obs = Observation(
            brand=brand, model=model_name, variant=trim_raw, scope="VARIANT",
            obs_field="price", raw_value=str(price), normalized_value=str(price),
            unit="THB", price_type="MSRP", source_url=source_url,
            source_class="AUTO_MEDIA", extraction_method="headlightmag_article_thai_price",
            evidence_excerpt=excerpt,
            content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
            trust_state="RESEARCH_UNVERIFIED", article_title=article_title,
            source_name="HeadLight Magazine", source_tier="secondary_automotive_media",
        )
        dedup_key = (obs.brand, obs.model, obs.variant, obs.normalized_value, obs.source_url)
        if dedup_key not in seen:
            seen.add(dedup_key)
            observations.append(obs)

    # Pattern 2: Thai "รุ่น X ราคา X,XXX,XXX" within model context
    # CAUTION: Matches ANY "รุ่น <trim> ราคา <price>" — requires model context.
    pattern2 = re.finditer(r'รุ่น\s+([A-Za-z0-9\+\-\. ]{1,25}?)\s+ราคา\s*(\d[\d,]*)', clean)
    for m in pattern2:
        trim_raw = m.group(1).strip()
        price = int(m.group(2).replace(',', ''))
        if not (THB_MIN <= price <= THB_MAX) or len(trim_raw) < 2:
            continue

        # MODEL SCOPE VALIDATION
        if not _is_in_model_context(clean, m.start(), m.end(), model_patterns):
            continue

        start = max(0, m.start() - 80)
        end = min(len(clean), m.end() + 80)
        excerpt = clean[start:end]

        obs = Observation(
            brand=brand, model=model_name, variant=trim_raw, scope="VARIANT",
            obs_field="price", raw_value=str(price), normalized_value=str(price),
            unit="THB", price_type="MSRP", source_url=source_url,
            source_class="AUTO_MEDIA", extraction_method="headlightmag_article_thai_pattern",
            evidence_excerpt=excerpt,
            content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
            trust_state="RESEARCH_UNVERIFIED", article_title=article_title,
            source_name="HeadLight Magazine", source_tier="secondary_automotive_media",
        )
        dedup_key = (obs.brand, obs.model, obs.variant, obs.normalized_value, obs.source_url)
        if dedup_key not in seen:
            seen.add(dedup_key)
            observations.append(obs)

    # Pattern 3: "ราคาอย่างเป็นทางการ Model : X,XXX,XXX บาท"
    # SAFE: Model name is explicitly in the pattern
    pattern3 = re.finditer(r'ราคา(?:อย่างเป็นทางการ|เปิดตัว|เริ่มต้น)\s+.*?' + re.escape(model_name) + r'.*?(\d{1,3}(?:,\d{3})+)\s*บาท', clean, re.IGNORECASE)
    for m in pattern3:
        price = int(m.group(1).replace(',', ''))
        if not (THB_MIN <= price <= THB_MAX):
            continue

        start = max(0, m.start() - 50)
        end = min(len(clean), m.end() + 50)
        excerpt = clean[start:end]

        obs = Observation(
            brand=brand, model=model_name, variant="__MODEL_RANGE__", scope="MODEL",
            obs_field="price", raw_value=str(price), normalized_value=str(price),
            unit="THB", price_type="LIST_PRICE", source_url=source_url,
            source_class="AUTO_MEDIA", extraction_method="headlightmag_article_official_price",
            evidence_excerpt=excerpt,
            content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
            trust_state="RESEARCH_UNVERIFIED", article_title=article_title,
            source_name="HeadLight Magazine", source_tier="secondary_automotive_media",
        )
        dedup_key = (obs.brand, obs.model, obs.variant, obs.normalized_value, obs.source_url)
        if dedup_key not in seen:
            seen.add(dedup_key)
            observations.append(obs)

    # Pattern 4: Table-like "Trim | Price" rows
    # CAUTION: Matches ANY pipe-separated price table — requires model context.
    pattern4 = re.finditer(r'([A-Z][A-Za-z0-9\+\-\.]{1,15})\s*\|\s*(\d{1,3}(?:,\d{3})+)', clean)
    for m in pattern4:
        trim_raw = m.group(1).strip()
        price = int(m.group(2).replace(',', ''))
        if not (THB_MIN <= price <= THB_MAX) or len(trim_raw) < 2:
            continue

        # MODEL SCOPE VALIDATION
        if not _is_in_model_context(clean, m.start(), m.end(), model_patterns):
            continue

        start = max(0, m.start() - 80)
        end = min(len(clean), m.end() + 80)
        excerpt = clean[start:end]

        obs = Observation(
            brand=brand, model=model_name, variant=trim_raw, scope="VARIANT",
            obs_field="price", raw_value=str(price), normalized_value=str(price),
            unit="THB", price_type="MSRP", source_url=source_url,
            source_class="AUTO_MEDIA", extraction_method="headlightmag_article_table_row",
            evidence_excerpt=excerpt,
            content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
            trust_state="RESEARCH_UNVERIFIED", article_title=article_title,
            source_name="HeadLight Magazine", source_tier="secondary_automotive_media",
        )
        dedup_key = (obs.brand, obs.model, obs.variant, obs.normalized_value, obs.source_url)
        if dedup_key not in seen:
            seen.add(dedup_key)
            observations.append(obs)

    # ── Spec extraction ──────────────────────────────────────────────
    # All spec patterns require model context validation.
    # Power
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:แรงม้า|horsepower|hp|PS)\b', clean, re.I):
        val = float(m.group(1))
        if 30 <= val <= 1000:
            if not _is_in_model_context(clean, m.start(), m.end(), model_patterns):
                continue
            start = max(0, m.start() - 50)
            end = min(len(clean), m.end() + 50)
            excerpt = clean[start:end]
            obs = Observation(
                brand=brand, model=model_name, variant="__MODEL__",
                scope="MODEL", obs_field="power_hp", raw_value=str(val),
                normalized_value=str(val), unit="hp",
                source_url=source_url, source_class="AUTO_MEDIA",
                extraction_method="headlightmag_article_regex",
                evidence_excerpt=excerpt,
                content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
                trust_state="RESEARCH_UNVERIFIED",
                article_title=article_title, source_name="HeadLight Magazine",
            )
            observations.append(obs)

    # Torque
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:Nm|นิวตันเมตร)\b', clean, re.I):
        val = float(m.group(1))
        if 50 <= val <= 1000:
            if not _is_in_model_context(clean, m.start(), m.end(), model_patterns):
                continue
            start = max(0, m.start() - 50)
            end = min(len(clean), m.end() + 50)
            excerpt = clean[start:end]
            obs = Observation(
                brand=brand, model=model_name, variant="__MODEL__",
                scope="MODEL", obs_field="torque_nm", raw_value=str(val),
                normalized_value=str(val), unit="Nm",
                source_url=source_url, source_class="AUTO_MEDIA",
                extraction_method="headlightmag_article_regex",
                evidence_excerpt=excerpt,
                content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
                trust_state="RESEARCH_UNVERIFIED",
                article_title=article_title, source_name="HeadLight Magazine",
            )
            observations.append(obs)

    # Battery
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*kWh', clean, re.I):
        val = float(m.group(1))
        if 10 <= val <= 200:
            if not _is_in_model_context(clean, m.start(), m.end(), model_patterns):
                continue
            start = max(0, m.start() - 50)
            end = min(len(clean), m.end() + 50)
            excerpt = clean[start:end]
            obs = Observation(
                brand=brand, model=model_name, variant="__MODEL__",
                scope="MODEL", obs_field="battery_kwh", raw_value=str(val),
                normalized_value=str(val), unit="kWh",
                source_url=source_url, source_class="AUTO_MEDIA",
                extraction_method="headlightmag_article_regex",
                evidence_excerpt=excerpt,
                content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
                trust_state="RESEARCH_UNVERIFIED",
                article_title=article_title, source_name="HeadLight Magazine",
            )
            observations.append(obs)

    # Range
    for m in re.finditer(r'(\d{3,4})\s*(?:km|กม\.|กิโลเมตร)\s*(?:WLTP|range|ระยะทาง|อึด)', clean, re.I):
        val = int(m.group(1))
        if 100 <= val <= 1500:
            if not _is_in_model_context(clean, m.start(), m.end(), model_patterns):
                continue
            start = max(0, m.start() - 50)
            end = min(len(clean), m.end() + 50)
            excerpt = clean[start:end]
            obs = Observation(
                brand=brand, model=model_name, variant="__MODEL__",
                scope="MODEL", obs_field="range_km", raw_value=str(val),
                normalized_value=str(val), unit="km",
                source_url=source_url, source_class="AUTO_MEDIA",
                extraction_method="headlightmag_article_regex",
                evidence_excerpt=excerpt,
                content_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
                trust_state="RESEARCH_UNVERIFIED",
                article_title=article_title, source_name="HeadLight Magazine",
            )
            observations.append(obs)

    return observations, rejections


def extract_title_from_html(html: str) -> str:
    """Extract article title from HTML."""
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return ""


def run_headlightmag_extraction(max_articles: int = 50) -> Tuple[List[Observation], List[RejectionRecord], dict]:
    """
    Full Headlightmag extraction pipeline.
    Returns observations, rejections, and stats.
    """
    all_observations = []
    all_rejections = []
    stats = {"articles_fetched": 0, "articles_with_prices": 0, "total_prices": 0,
             "articles_model_validated": 0, "articles_model_rejected": 0}

    # Step 1: Get article URLs from category pages
    article_urls: Set[str] = set()
    for cat_url in CATEGORY_URLS:
        html = fetch_page(cat_url, delay=2.0)
        if html:
            urls = get_article_urls_from_category(html)
            article_urls.update(urls)
            print(f"  Category {cat_url}: found {len(urls)} article URLs", file=sys.stderr)

    print(f"  Total unique article URLs: {len(article_urls)}", file=sys.stderr)

    # Step 2: Process articles
    for url in sorted(article_urls)[:max_articles]:
        brand = identify_brand_from_url(url)
        if not brand:
            continue

        html = fetch_page(url, delay=1.5)
        if not html:
            continue

        title = extract_title_from_html(html)
        model_name = identify_model_from_title(title)
        if not model_name:
            slug = url.rstrip("/").split("/")[-1].lower()
            model_name = normalize_model_name(slug)

        if not model_name:
            all_rejections.append(RejectionRecord(
                brand=brand, model_hint="unknown",
                reason="no_model_identified",
                source_url=url,
                evidence_excerpt=title[:200] if title else "",
                extraction_method="headlightmag_article",
            ))
            continue

        # ── Article-level model scope validation ─────────────────────
        headings = _extract_headings_from_html(html)
        model_patterns = _build_model_search_patterns(model_name, brand)

        if not _validate_article_model_scope(title, url, headings, model_patterns):
            # Try URL-only fallback
            slug = url.rstrip("/").split("/")[-1].lower()
            fallback_model = normalize_model_name(slug)
            if fallback_model and fallback_model != model_name:
                model_name = fallback_model
                model_patterns = _build_model_search_patterns(model_name, brand)
                if not _validate_article_model_scope(title, url, headings, model_patterns):
                    all_rejections.append(RejectionRecord(
                        brand=brand, model_hint=model_name,
                        reason="model_not_confirmed_in_article_scope",
                        source_url=url,
                        evidence_excerpt=title[:200] if title else "",
                        extraction_method="headlightmag_article",
                    ))
                    stats["articles_model_rejected"] += 1
                    continue
            else:
                all_rejections.append(RejectionRecord(
                    brand=brand, model_hint=model_name,
                    reason="model_not_confirmed_in_article_scope",
                    source_url=url,
                    evidence_excerpt=title[:200] if title else "",
                    extraction_method="headlightmag_article",
                ))
                stats["articles_model_rejected"] += 1
                continue

        stats["articles_model_validated"] += 1

        # Extract text from HTML
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        obs, rej = extract_prices_from_article(text, model_name, brand, url, title)
        all_observations.extend(obs)
        all_rejections.extend(rej)

        stats["articles_fetched"] += 1
        if obs:
            stats["articles_with_prices"] += 1
            stats["total_prices"] += len([o for o in obs if o.obs_field == "price"])

        time.sleep(1.0)  # Polite delay

    return all_observations, all_rejections, stats


if __name__ == "__main__":
    max_articles = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    run_id = sys.argv[2] if len(sys.argv) > 2 else f"hl-run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    run_dir = f"/tmp/thai-car-hl-run/{run_id}"
    os.makedirs(run_dir, exist_ok=True)

    print(f"Starting Headlightmag extraction (max {max_articles} articles)...", file=sys.stderr)
    observations, rejections, stats = run_headlightmag_extraction(max_articles)

    # Write results
    result = {
        "run_id": run_id,
        "stats": stats,
        "observations": [o.to_dict() for o in observations],
        "rejections": [r.to_dict() for r in rejections],
    }

    output_path = os.path.join(run_dir, "headlightmag-extraction.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nResults written to: {output_path}", file=sys.stderr)
    print(f"  Observations: {len(observations)}", file=sys.stderr)
    print(f"  Rejections: {len(rejections)}", file=sys.stderr)
    print(f"  Stats: {json.dumps(stats, indent=2)}", file=sys.stderr)

    summary = {
        "run_id": run_id,
        "stats": stats,
        "models_found": list(set(o.model for o in observations if o.obs_field == "price")),
        "brands_found": list(set(o.brand for o in observations)),
    }
    print(json.dumps(summary, indent=2))
