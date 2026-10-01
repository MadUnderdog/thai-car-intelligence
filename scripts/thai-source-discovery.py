#!/usr/bin/env python3
"""
Thai Automotive Source Discovery & Acquisition Script

Discovers articles from 10+ Thai automotive sources, extracts prices, specs,
and model data with full provenance. Runs idempotently with checkpoint/resume.

Targets:
  - 100+ articles processed across all sources
  - 50+ prices extracted
  - 100+ specs extracted

Usage:
    python3 thai-source-discovery.py [--reset] [--max-per-source N] [--dry-run]
"""
import json
import os
import re
import sys
import time
import hashlib
import signal
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Set
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree as ET
import traceback

# ─── Configuration ──────────────────────────────────────────────────

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage")
CHECKPOINT_FILE = os.path.join(STORAGE_DIR, "source-discovery-checkpoint.json")
RESULTS_FILE = os.path.join(STORAGE_DIR, "source-discovery-results.json")
REPORT_FILE = os.path.join(STORAGE_DIR, "source-discovery-report.json")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 15
MAX_WORKERS = 6
THB_MIN = 100_000
THB_MAX = 20_000_000

# ─── Thai-first search queries ──────────────────────────────────────

SEARCH_QUERIES = [
    "ราคา {brand} {model}",
    "{brand} {model} รุ่นย่อย",
    "{brand} {model} เปิดตัว",
    "{brand} {model} สเปก",
    "{brand} {model} โปรโมชั่น",
    "{brand} {model} ราคาอย่างเป็นทางการ",
]

# ─── Known brand keywords for slug/URL identification ──────────────

BRAND_KEYWORDS = {
    "toyota": ["yaris", "corolla", "camry", "fortuner", "hilux", "innova",
               "veloz", "avanza", "bz4x", "land-cruiser", "alphard", "hiace",
               "commuter", "majesty", "gr-sport", "fortuner", "rav4", "bz3x"],
    "honda": ["city", "civic", "hr-v", "cr-v", "br-v", "accord", "wr-v", "zr-v"],
    "nissan": ["almera", "kicks", "x-trail", "terra", "navara", "serena",
               "leaf", "sakura", "urvan", "note"],
    "mazda": ["mazda2", "mazda3", "cx-3", "cx-30", "cx-5", "cx-80", "6e",
              "cx-60", "cx-90"],
    "mg": ["mg3", "mg4", "mg5", "zs-ev", "hs-", "im5", "im6", "s5-ev",
           "urban-ev", "cyberster", "ep-plus", "mg-zs"],
    "byd": ["atto", "dolphin", "seal", "sealion", "m6-", "m6 ", "seal-6"],
    "gwm": ["haval", "ora-", "tank-", "jolion", "h6"],
    "ford": ["ranger", "everest", "territory", "maverick"],
    "isuzu": ["d-max", "mu-x", "dmax"],
    "bmw": ["series", "x1", "x3", "x5", "ix", "i5", "i7", "x7"],
    "mercedes-benz": ["class", "gla", "glc", "gle", "eqa", "eqb", "eqs"],
    "volvo": ["xc40", "xc60", "xc90", "ex30", "ex90"],
    "chevrolet": ["trailblazer", "colorado", "captiva"],
    "chery": ["omoda", "tiggo", "jaecoo"],
    "hyundai": ["ioniq", "santa-fe", "stargazer", "staria", "tucson", "kona"],
    "kia": ["sonet", "sportage", "ev6", "ev9", "carnival", "niro", "seltos"],
    "subaru": ["crosstrek", "outback", "forester", "evoltis"],
    "mitsubishi": ["mirage", "attrage", "xpander", "triton", "pajero"],
    "suzuki": ["swift", "vitara", "xl7", "s-presso", "jimny", "fronx", "CELERIO"],
    "porsche": ["cayenne", "macan", "taycan", "panamera"],
    "mini": ["cooper", "countryman", "aceman"],
    "tesla": ["model-3", "model-y", "model-s", "model-x"],
    "zeekr": ["zeekr"],
    "changan": ["cs55", "uni-v", "uni-k", "deepal", "cs75"],
    "geely": ["geely", "starray", "ex5", "ex2"],
    "denza": ["denza", "d9", "n7", "z9gt"],
    "xpeng": ["xpeng", "g6", "g9"],
    "kg-mobility": ["torres", "korando"],
    "ldv": ["d90", "t60", "mifa"],
    "baic": ["x55", "bj30", "bj40"],
    "jetour": ["dashing", "t2"],
    "nio": ["es6", "et5", "firefly"],
    "lexus": ["nx", "rx", "rz", "es", "ls", "ux", "lm"],
    "dongfeng": ["dongfeng", "forthing"],
    "avatr": ["avatr"],
}

# ─── Source Registry ────────────────────────────────────────────────

@dataclass
class SourceConfig:
    """Configuration for a Thai automotive source."""
    domain: str
    display_name: str
    rss_feeds: List[str] = field(default_factory=list)
    category_pages: List[str] = field(default_factory=list)
    search_query_templates: List[str] = field(default_factory=list)
    article_url_pattern: Optional[str] = None
    source_class: str = "AUTOMOTIVE_MEDIA"
    trust_state: str = "RESEARCH_UNVERIFIED"
    max_articles: int = 30
    enabled: bool = True
    notes: str = ""


SOURCES: List[SourceConfig] = [
    SourceConfig(
        domain="headlightmag.com",
        display_name="HeadLight Magazine",
        rss_feeds=["https://www.headlightmag.com/feed/"],
        category_pages=[
            "https://www.headlightmag.com/category/news/new-cars-in-thailand/",
            "https://www.headlightmag.com/category/news/",
        ],
        article_url_pattern=r"headlightmag\.com/\d{4}-\d{2}-\d{2}",
        notes="WordPress site. Best RSS feed. Rich price+spec content.",
    ),
    SourceConfig(
        domain="9carthai.com",
        display_name="9CARTHAI",
        rss_feeds=["https://www.9carthai.com/feed/"],
        category_pages=[
            "https://www.9carthai.com/news/",
        ],
        article_url_pattern=r"9carthai\.com/\d{4}/\d{2}",
        notes="WordPress. Price pages and news articles.",
    ),
    SourceConfig(
        domain="autodeft.com",
        display_name="AutoDeft",
        rss_feeds=["https://www.autodeft.com/feed/"],
        category_pages=[],
        article_url_pattern=r"autodeft\.com/\d{4}/\d{2}",
        notes="Auto news and reviews with good spec coverage.",
    ),
    SourceConfig(
        domain="autolifethailand.tv",
        display_name="AutoLife Thailand",
        rss_feeds=["https://www.autolifethailand.tv/feed/"],
        category_pages=[],
        article_url_pattern=r"autolifethailand\.tv/\d{4}",
        notes="Lifestyle automotive content with price coverage.",
    ),
    SourceConfig(
        domain="car2day.com",
        display_name="Car2Day",
        rss_feeds=["https://www.car2day.com/feed/"],
        category_pages=[],
        article_url_pattern=r"car2day\.com/\d{4}",
        notes="Thai auto news and reviews.",
    ),
    SourceConfig(
        domain="sanook.com",
        display_name="Sanook Auto",
        rss_feeds=["https://news.sanook.com/rss/auto.xml"],
        category_pages=[],
        article_url_pattern=r"sanook\.com/auto",
        notes="Major Thai portal. Auto section with news articles.",
    ),
    SourceConfig(
        domain="bangkokbiznews.com",
        display_name="Bangkok Biz News Auto",
        rss_feeds=["https://www.bangkokbiznews.com/rss/auto.rss"],
        category_pages=[],
        article_url_pattern=r"bangkokbiznews\.com",
        notes="Business-focused auto news.",
    ),
    SourceConfig(
        domain="autospinn.com",
        display_name="AutoSpinn",
        rss_feeds=["https://www.autospinn.com/rss"],
        category_pages=[
            "https://www.autospinn.com/category/new-cars/",
            "https://www.autospinn.com/category/tech/",
        ],
        article_url_pattern=r"autospinn\.com/\d{4}",
        notes="Thai auto news site with category pages.",
    ),
    SourceConfig(
        domain="dailynews.co.th",
        display_name="Daily News Auto",
        rss_feeds=["https://www.dailynews.co.th/rss"],
        category_pages=[],
        article_url_pattern=r"dailynews\.co\.th",
        notes="Major Thai newspaper. General RSS with auto content.",
    ),
    SourceConfig(
        domain="checkraka.com",
        display_name="CheckRaka",
        rss_feeds=[],
        category_pages=[
            "https://www.checkraka.com/car",
            "https://www.checkraka.com/ev-car",
        ],
        article_url_pattern=r"checkraka\.com/car",
        notes="Thai auto comparison site. Category pages for discovery.",
    ),
    SourceConfig(
        domain="thairath.co.th",
        display_name="Thairath Auto",
        rss_feeds=[],
        category_pages=[],
        article_url_pattern=r"thairath\.co\.th/auto",
        notes="Major Thai newspaper. No RSS; use web search for discovery.",
    ),
    SourceConfig(
        domain="kapook.com",
        display_name="Kapook Auto",
        rss_feeds=[],
        category_pages=[],
        article_url_pattern=r"kapook\.com",
        notes="Thai portal. No direct auto RSS; web search only.",
    ),
    SourceConfig(
        domain="mgronline.com",
        display_name="Manager Auto",
        rss_feeds=[],
        category_pages=[],
        article_url_pattern=r"mgronline\.com",
        notes="Manager media group. 403 on RSS; web search only.",
    ),
]


# ─── Data Classes ───────────────────────────────────────────────────

@dataclass
class ArticleRecord:
    """Discovered article with metadata."""
    url: str
    title: str = ""
    published_date: str = ""
    source_domain: str = ""
    source_display: str = ""
    discovery_method: str = ""  # rss, category, web_search
    brand: str = ""
    model: str = ""
    brand_confidence: float = 0.0
    model_confidence: float = 0.0
    content_text: str = ""  # Extracted article text
    prices: List[dict] = field(default_factory=list)
    specs: List[dict] = field(default_factory=list)
    scope_valid: bool = False
    scope_reason: str = ""
    content_hash: str = ""
    discovered_at: str = ""
    processed: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("content_text", None)  # Don't store full text in results
        return d


@dataclass
class DiscoveryMetrics:
    """Per-source metrics."""
    articles_discovered: int = 0
    articles_processed: int = 0
    articles_failed: int = 0
    prices_extracted: int = 0
    specs_extracted: int = 0
    brands_seen: Dict[str, int] = field(default_factory=dict)
    models_seen: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""


# ─── Helpers ────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def fetch_url(url: str, timeout: int = REQUEST_TIMEOUT) -> Optional[str]:
    """Fetch URL with standard headers. Returns HTML/text or None."""
    try:
        req = Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "th,en;q=0.9",
        })
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None


def extract_text_from_html(html: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_title_from_html(html: str) -> str:
    """Extract page title from HTML."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if m:
        title = m.group(1).strip()
        title = re.sub(r"<[^>]+>", "", title)
        # Split on common separators, take first meaningful part
        for sep in [" | ", " - ", " — ", " :: ", " | ", "\n"]:
            if sep in title:
                title = title.split(sep)[0].strip()
                break
        return title
    return ""


def identify_brand_from_url(url: str) -> Optional[str]:
    """Try to identify brand from URL slug."""
    path = urlparse(url).path.lower()
    slug = path.rstrip("/").split("/")[-1]
    for brand, keywords in BRAND_KEYWORDS.items():
        for kw in keywords:
            if kw in slug:
                return brand
    return None


def identify_brand_from_text(text: str) -> Optional[str]:
    """Try to identify brand from article text (scans title + first 1500 chars)."""
    # Prioritize title (first 200 chars) then body
    snippet = text[:1500].lower()
    brand_patterns = {
        "toyota": r"\btoyota\b|โตโยต้า",
        "honda": r"\bhonda\b|ฮอนด้า",
        "nissan": r"\bnissan\b|นิสสัน",
        "mazda": r"\bmazda\b|มาสด้า",
        "mg": r"\bmg\b",
        "byd": r"\bbyd\b",
        "gwm": r"\bgwm\b|gwm haval|gwm ora|gwm tank",
        "ford": r"\bford\b|ฟอร์ด",
        "isuzu": r"\bisuzu\b|อีซูซุ",
        "bmw": r"\bbmw\b",
        "mercedes-benz": r"\bmercedes\b|เบนซ์|เมอร์เซเดส",
        "volvo": r"\bvolvo\b|วอลโว่",
        "chevrolet": r"\bchevrolet\b|เชฟโรเลต",
        "chery": r"\bchery\b|เชอรี่",
        "hyundai": r"\bhyundai\b|ฮุนได",
        "kia": r"\bkia\b|เกีย",
        "subaru": r"\bsubaru\b|สубารุ",
        "mitsubishi": r"\bmitsubishi\b|มิตซูบิชิ",
        "suzuki": r"\bsuzuki\b|ซูซูกิ",
        "porsche": r"\bporsche\b|ปอร์เช่",
        "mini": r"\bmini\b",
        "tesla": r"\btesla\b|เทสลา",
        "zeekr": r"\bzeekr\b",
        "changan": r"\bchangan\b|ช้าง",
        "geely": r"\bgeely\b|geely",
        "denza": r"\bdenza\b",
        "ldv": r"\bldv\b",
        "baic": r"\bbaic\b",
        "jetour": r"\bjetour\b",
        "nio": r"\bnio\b",
        "lexus": r"\blexus\b|เล็กซัส",
    }
    for brand, pattern in brand_patterns.items():
        if re.search(pattern, snippet, re.IGNORECASE):
            return brand
    return None


def identify_model_from_text(text: str, brand: Optional[str] = None) -> Tuple[str, float]:
    """Identify car model from text. Returns (model_name, confidence)."""
    if brand:
        keywords = BRAND_KEYWORDS.get(brand.lower(), [])
        text_lower = text.lower()
        for kw in sorted(keywords, key=len, reverse=True):
            if kw.replace("-", " ") in text_lower or kw in text_lower:
                return kw.replace("-", " ").title(), 0.85
    # Fallback: generic model patterns
    model_patterns = [
        (r"\b(cross|altis|camry|civic|city|corolla|hilux|fortuner|innova|yaris)\b", 0.7),
        (r"\b(cx-5|cx-30|cr-v|hr-v|x-trail|d-max|mu-x|ranger|everest)\b", 0.7),
        (r"\b(almera|kicks|navara|serena|terra|pajero|xpander|triton)\b", 0.7),
        (r"\b(mg[345]|atto|dolphin|seal|haval|h6|jolion)\b", 0.7),
    ]
    for pattern, conf in model_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).title(), conf
    return "", 0.0


# ─── Price Extraction ──────────────────────────────────────────────

PRICE_PATTERNS = [
    # Thai Baht with commas: 1,234,567 บาท
    (r"(?:ราคา|฿|price)[:\s]*(?:เริ่มต้น|เริ่ม)?\s*(\d{1,3}(?:,\d{3}){1,3})\s*(?:บาท|฿)?", "thb_comma"),
    # Price with trim prefix
    (r"([\w\s\-\.]{2,25})\s*[:\s]+(\d{1,3}(?:,\d{3}){1,3})\s*(?:บาท|฿)", "trim_price"),
    # Standalone large numbers near price context
    (r"(?:ราคา|฿|price|-msrp|msrp)[^\d]{0,30}(\d{1,3}(?:,\d{3}){1,3})", "price_context"),
    # Range prices: 1,234,567 - 1,567,890
    (r"(\d{1,3}(?:,\d{3}){1,3})\s*[-–—]\s*(\d{1,3}(?:,\d{3}){1,3})\s*(?:บาท|฿)?", "price_range"),
    # Just ฿ symbol with number
    (r"฿\s*(\d{1,3}(?:,\d{3}){1,3})", "baht_symbol"),
]


def extract_prices(text: str) -> List[dict]:
    """Extract price observations from article text."""
    prices = []
    seen_values = set()

    for pattern, method in PRICE_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            groups = m.groups()
            excerpt_start = max(0, m.start() - 60)
            excerpt_end = min(len(text), m.end() + 60)
            excerpt = text[excerpt_start:excerpt_end].strip()

            if method == "price_range" and len(groups) >= 2:
                # Price range — extract both endpoints
                for val_str in groups[:2]:
                    val = int(val_str.replace(",", ""))
                    if THB_MIN <= val <= THB_MAX and val not in seen_values:
                        seen_values.add(val)
                        prices.append({
                            "raw_value": val_str,
                            "normalized_value": val,
                            "price_type": "RANGE_ENDPOINT",
                            "extraction_method": method,
                            "evidence_excerpt": excerpt[:200],
                            "content_hash": content_hash(f"price:{val}:{excerpt[:50]}"),
                        })
            elif method == "trim_price" and len(groups) >= 2:
                variant = groups[0].strip()
                val_str = groups[1]
                val = int(val_str.replace(",", ""))
                if THB_MIN <= val <= THB_MAX and val not in seen_values:
                    seen_values.add(val)
                    prices.append({
                        "raw_value": f"{variant}: {val_str}",
                        "normalized_value": val,
                        "variant": variant,
                        "price_type": "VARIANT_MSRP",
                        "extraction_method": method,
                        "evidence_excerpt": excerpt[:200],
                        "content_hash": content_hash(f"price:{variant}:{val}:{excerpt[:50]}"),
                    })
            elif groups:
                val_str = groups[0]
                val = int(val_str.replace(",", ""))
                if THB_MIN <= val <= THB_MAX and val not in seen_values:
                    seen_values.add(val)
                    prices.append({
                        "raw_value": val_str,
                        "normalized_value": val,
                        "price_type": "LIST_PRICE" if "ราคา" in excerpt.lower() else "MSRP",
                        "extraction_method": method,
                        "evidence_excerpt": excerpt[:200],
                        "content_hash": content_hash(f"price:{val}:{excerpt[:50]}"),
                    })

    return prices


# ─── Spec Extraction ────────────────────────────────────────────────

SPEC_PATTERNS = {
    "power_kw": [
        (r"(\d{2,3})\s*(?:กิโลวัตต์|kilowatt|kw)\b", "kW"),
        (r"(\d{2,3})\s*(?:แรงม้า|horsepower|hp|ps)\b", "hp"),
    ],
    "torque_nm": [
        (r"(\d{2,4})\s*(?:นิวตันเมตร|newton[\s-]?meter|nm)\b", "Nm"),
    ],
    "engine_displacement": [
        (r"(\d{1,2}\.\d)\s*(?:ลิตร|liter|cc|ลิ)\b", "L"),
        (r"(\d{3,4})\s*cc\b", "cc"),
    ],
    "fuel_type": [
        (r"\b(diesel|เบนซิน|gasoline|petrol|electric|ev|phev|hybrid|lpg|cng)\b", None),
    ],
    "transmission": [
        (r"\b(\d)\s*(?:speed|สปีด|เกียร์)\b", "speed"),
        (r"\b(automatic|manual|cvt|amt| dct)\b", None),
    ],
    "drive_type": [
        (r"\b(fwd|2wd|2-wheel|front[\s-]?wheel)\b", "FWD"),
        (r"\b(rwd|rear[\s-]?wheel)\b", "RWD"),
        (r"\b(awd|4wd|4-wheel|all[\s-]?wheel)\b", "AWD"),
    ],
    "dimensions_length": [
        (r"(?:ยาว|length)[:\s]*(\d{4})\s*มม\.?", "mm"),
    ],
    "dimensions_width": [
        (r"(?:กว้าง|width)[:\s]*(\d{3,4})\s*มม\.?", "mm"),
    ],
    "dimensions_height": [
        (r"(?:สูง|height)[:\s]*(\d{3,4})\s*มม\.?", "mm"),
    ],
    "wheelbase": [
        (r"(?:ฐานล้อ|wheelbase)[:\s]*(\d{3,4})\s*มม\.?", "mm"),
    ],
    "weight": [
        (r"(?:น้ำหนัก|weight| curb)[:\s]*(\d{3,4})\s*(?:กก\.?|kg)\b", "kg"),
    ],
    "fuel_consumption": [
        (r"(\d{1,2}\.?\d?)\s*(?:กม\.?\/ลิตร|km/l|km/liter)\b", "km/L"),
        (r"(\d{1,2}\.?\d?)\s*(?:ลิตร\/100|L/100)\b", "L/100km"),
    ],
    "seating_capacity": [
        (r"(?:นั่ง|ที่นั่ง|seats?)[:\s]*(\d{1,2})\s*(?:ที่นั่ง| seats?)?", "seats"),
    ],
    "battery_capacity": [
        (r"(\d{2,3}\.?\d?)\s*(?:kwh|กิโลวัตต์[\s-]?ชั่วโมง)\b", "kWh"),
    ],
    "range_km": [
        (r"(\d{3,4})\s*(?:กม\.?|km|kilometer)\b(?=.*(?:range|ระยะทาง|วิ่ง))", "km"),
    ],
    "charging_time": [
        (r"(\d{1,2}\.?\d?)\s*(?:ชั่วโมง|hours?|ชม\.?)\b(?=.*(?:charge|ชาร์จ))", "hours"),
    ],
}


def extract_specs(text: str) -> List[dict]:
    """Extract specification observations from article text."""
    specs = []
    seen_specs = set()

    for spec_type, patterns in SPEC_PATTERNS.items():
        for pattern, unit in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                value = m.group(1).strip()
                excerpt_start = max(0, m.start() - 40)
                excerpt_end = min(len(text), m.end() + 40)
                excerpt = text[excerpt_start:excerpt_end].strip()

                spec_key = f"{spec_type}:{value}"
                if spec_key not in seen_specs:
                    seen_specs.add(spec_key)
                    specs.append({
                        "spec_type": spec_type,
                        "raw_value": value,
                        "unit": unit or "",
                        "extraction_method": "regex",
                        "evidence_excerpt": excerpt[:150],
                        "content_hash": content_hash(f"spec:{spec_type}:{value}:{excerpt[:50]}"),
                    })

    return specs


# ─── Scope Validation ───────────────────────────────────────────────

def validate_scope(title: str, text: str, brand: str, model: str) -> Tuple[bool, str]:
    """
    Validate that article is primarily about one model.
    Returns (is_valid, reason).
    """
    if not brand or not model:
        return False, "no_brand_or_model"

    text_lower = text.lower()
    title_lower = title.lower()
    model_lower = model.lower()
    brand_lower = brand.lower()

    # Count mentions of the target model/brand
    model_mentions = len(re.findall(re.escape(model_lower), text_lower))
    brand_mentions = len(re.findall(re.escape(brand_lower), text_lower))

    # If target brand is mentioned at least once, it's probably in scope
    if brand_mentions >= 1 and model_mentions >= 1:
        return True, "ok"

    # If brand is mentioned but not model, still ok for model-range articles
    if brand_mentions >= 2:
        return True, "brand_dominant"

    # Check for explicit multi-brand comparison signals
    comparison_signals = [
        r"เปรียบเทียบ|compare|versus|vs\.?\b",
        r"(\d+)\s*(?:แบรนด์|ยี่ห้อ|brand)",
        r"ทุกยี่ห้อ|every brand|all brands",
    ]
    for sig in comparison_signals:
        if re.search(sig, text_lower):
            return False, "comparison_article"

    # If the target brand isn't mentioned at all, likely wrong attribution
    if brand_mentions == 0 and model_mentions == 0:
        return False, "brand_not_mentioned"

    return True, "ok"


# ─── RSS Feed Parser ────────────────────────────────────────────────

def parse_rss_feed(xml_text: str, source_domain: str) -> List[ArticleRecord]:
    """Parse RSS XML and extract articles."""
    articles = []
    try:
        # Handle potential encoding issues
        xml_text = xml_text.strip()
        if not xml_text.startswith("<?xml"):
            xml_text = '<?xml version="1.0" encoding="UTF-8"?>' + xml_text

        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return []

        for item in channel.findall("item"):
            link_el = item.find("link")
            title_el = item.find("title")
            pub_date_el = item.find("pubDate")

            url = link_el.text.strip() if link_el is not None and link_el.text else ""
            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            pub_date = pub_date_el.text.strip() if pub_date_el is not None and pub_date_el.text else ""

            if not url or not title:
                continue

            # Skip non-article links
            skip_patterns = ["/category/", "/tag/", "/author/", "/page/",
                             "/wp-json", "/xmlrpc", "/feed/", "#"]
            if any(sp in url.lower() for sp in skip_patterns):
                continue

            brand = identify_brand_from_url(url) or identify_brand_from_text(title)

            articles.append(ArticleRecord(
                url=url,
                title=title,
                published_date=pub_date,
                source_domain=source_domain,
                discovery_method="rss",
                brand=brand or "",
                discovered_at=now_iso(),
            ))

    except ET.ParseError:
        pass
    except Exception:
        pass

    return articles


# ─── Category Page Parser ───────────────────────────────────────────

def parse_category_page(html: str, source_domain: str, base_url: str) -> List[ArticleRecord]:
    """Extract article links from a category/listing page."""
    articles = []
    seen_urls = set()

    # Extract all links
    links = re.findall(r'href="(https?://[^"]+)"', html)
    # Also extract relative links
    relative_links = re.findall(r'href="(/[^"]+)"', html)
    for rl in relative_links:
        links.append(f"https://{source_domain}{rl}")

    for url in links:
        if url in seen_urls:
            continue
        seen_urls.add(url)

        parsed = urlparse(url)
        if parsed.hostname and source_domain not in parsed.hostname:
            continue

        # Skip non-article URLs
        skip_patterns = ["/category/", "/tag/", "/author/", "/page/",
                         "/wp-json", "/xmlrpc", "/feed/", "/static/",
                         ".css", ".js", ".png", ".jpg", ".gif", ".svg",
                         ".pdf", ".zip", "#", "javascript:"]
        if any(sp in url.lower() for sp in skip_patterns):
            continue

        # Must have some path depth (likely an article)
        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) < 1:
            continue

        brand = identify_brand_from_url(url)

        articles.append(ArticleRecord(
            url=url,
            source_domain=source_domain,
            discovery_method="category",
            brand=brand or "",
            discovered_at=now_iso(),
        ))

    return articles


# ─── Model Identity Resolver (lightweight, no DB) ──────────────────

class LightweightModelResolver:
    """
    Lightweight model resolver that works without database.
    Uses BRAND_KEYWORDS and text matching for model attribution.
    """

    def resolve(self, brand_hint: Optional[str], text: str) -> Tuple[str, str, float, bool]:
        """Resolve brand + model from text. Returns (brand, model, confidence, ambiguous)."""
        brand = brand_hint or identify_brand_from_text(text)
        if not brand:
            return "", "", 0.0, False

        model, conf = identify_model_from_text(text, brand)
        return brand, model, conf, False


_resolver = LightweightModelResolver()


# ─── Checkpoint Manager ─────────────────────────────────────────────

@dataclass
class CheckpointState:
    """Tracks processing state for idempotent resume."""
    processed_urls: Dict[str, str] = field(default_factory=dict)  # url -> status
    source_metrics: Dict[str, dict] = field(default_factory=dict)
    run_id: str = ""
    started_at: str = ""
    last_updated: str = ""
    total_articles: int = 0
    total_prices: int = 0
    total_specs: int = 0

    def save(self):
        os.makedirs(STORAGE_DIR, exist_ok=True)
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        self.last_updated = now_iso()

    @classmethod
    def load(cls) -> "CheckpointState":
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                state = cls(**{k: v for k, v in data.items()
                               if k in cls.__dataclass_fields__})
                return state
            except Exception:
                pass
        return cls()

    def mark_processed(self, url: str, status: str = "succeeded"):
        self.processed_urls[url] = status
        self.last_updated = now_iso()

    def is_processed(self, url: str) -> bool:
        return url in self.processed_urls


# ─── Main Discovery Engine ──────────────────────────────────────────

class ThaiSourceDiscovery:
    """Main discovery and acquisition engine."""

    def __init__(self, reset: bool = False, max_per_source: int = 30, dry_run: bool = False):
        self.max_per_source = max_per_source
        self.dry_run = dry_run
        self.state = CheckpointState.load()
        self.articles: List[ArticleRecord] = []
        self.all_prices: List[dict] = []
        self.all_specs: List[dict] = []
        self.metrics: Dict[str, DiscoveryMetrics] = {}
        self._running = True

        if reset:
            self.state = CheckpointState()

        # Graceful shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        print(f"\n[!] Signal {signum} received. Saving checkpoint and exiting...")
        self._running = False
        self._save_checkpoint()

    def _save_checkpoint(self):
        self.state.total_articles = len(self.articles)
        self.state.total_prices = sum(len(a.prices) for a in self.articles)
        self.state.total_specs = sum(len(a.specs) for a in self.articles)
        for source_domain, metrics in self.metrics.items():
            self.state.source_metrics[source_domain] = asdict(metrics)
        self.state.save()

    def run(self):
        """Main execution loop."""
        self.state.run_id = f"discovery-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.state.started_at = now_iso()
        os.makedirs(STORAGE_DIR, exist_ok=True)

        print(f"=" * 70)
        print(f"Thai Automotive Source Discovery & Acquisition")
        print(f"Run ID: {self.state.run_id}")
        print(f"Max per source: {self.max_per_source}")
        print(f"Checkpoint: {CHECKPOINT_FILE}")
        print(f"=" * 70)

        # Phase 1: Discover articles from all sources
        print("\n--- Phase 1: Article Discovery ---")
        discovered = self._discover_all_sources()
        print(f"Total discovered: {len(discovered)} articles")

        # Phase 2: Process articles (extract prices, specs, model identity)
        print("\n--- Phase 2: Article Processing ---")
        self._process_articles(discovered)

        # Phase 3: Scope validation
        print("\n--- Phase 3: Scope Validation ---")
        self._validate_scopes()

        # Phase 4: Save results
        print("\n--- Phase 4: Save Results ---")
        self._save_results()

        # Final summary
        self._print_summary()

    def _discover_all_sources(self) -> List[ArticleRecord]:
        """Discover articles from all enabled sources."""
        all_articles = []

        for source in SOURCES:
            if not source.enabled:
                continue

            if not self._running:
                break

            print(f"\n  [{source.display_name}] ({source.domain})")
            metrics = DiscoveryMetrics(started_at=now_iso())
            self.metrics[source.domain] = metrics

            source_articles = []

            # Method 1: RSS feeds
            for rss_url in source.rss_feeds:
                if not self._running:
                    break
                print(f"    RSS: {rss_url}")
                if self.dry_run:
                    print(f"      [DRY RUN] Would fetch RSS")
                    continue

                xml = fetch_url(rss_url)
                if xml:
                    articles = parse_rss_feed(xml, source.domain)
                    for a in articles:
                        a.source_display = source.display_name
                    source_articles.extend(articles)
                    print(f"      Found {len(articles)} articles from RSS")
                else:
                    print(f"      Failed to fetch RSS")
                    metrics.errors.append(f"rss_fetch_failed: {rss_url}")
                time.sleep(0.5)

            # Method 2: Category pages
            for cat_url in source.category_pages:
                if not self._running:
                    break
                print(f"    Category: {cat_url}")
                if self.dry_run:
                    print(f"      [DRY RUN] Would fetch category")
                    continue

                html = fetch_url(cat_url)
                if html:
                    articles = parse_category_page(html, source.domain, cat_url)
                    for a in articles:
                        a.source_display = source.display_name
                    source_articles.extend(articles)
                    print(f"      Found {len(articles)} articles from category page")
                else:
                    print(f"      Failed to fetch category page")
                    metrics.errors.append(f"category_fetch_failed: {cat_url}")
                time.sleep(0.5)

            # Deduplicate within source
            seen_urls = set()
            unique_articles = []
            for a in source_articles:
                if a.url not in seen_urls:
                    seen_urls.add(a.url)
                    unique_articles.append(a)

            # Apply max_per_source limit
            unique_articles = unique_articles[:self.max_per_source]

            # Skip already-processed articles (idempotent resume)
            new_articles = [a for a in unique_articles if not self.state.is_processed(a.url)]
            skipped = len(unique_articles) - len(new_articles)

            metrics.articles_discovered = len(unique_articles)
            print(f"    Total: {len(unique_articles)} unique, {skipped} already processed, {len(new_articles)} new")

            all_articles.extend(new_articles)

        return all_articles

    def _process_articles(self, articles: List[ArticleRecord]):
        """Process each article: fetch content, extract prices/specs, resolve model."""
        total = len(articles)
        processed = 0
        failed = 0

        for i, article in enumerate(articles):
            if not self._running:
                break

            if self.dry_run:
                print(f"    [{i+1}/{total}] [DRY RUN] Would process: {article.title[:60] or article.url[:60]}")
                self.articles.append(article)
                continue

            source_domain = article.source_domain
            if source_domain not in self.metrics:
                self.metrics[source_domain] = DiscoveryMetrics()
            metrics = self.metrics[source_domain]

            try:
                # Fetch article content
                html = fetch_url(article.url)
                if not html:
                    raise Exception("fetch_failed")

                # Extract title if not from RSS
                if not article.title:
                    article.title = extract_title_from_html(html)

                # Extract text content
                text = extract_text_from_html(html)
                article.content_text = text
                article.content_hash = content_hash(text[:1000])

                # Resolve brand/model
                brand, model, confidence, ambiguous = _resolver.resolve(
                    article.brand or None, f"{article.title} {text[:500]}"
                )
                article.brand = brand
                article.model = model
                article.brand_confidence = confidence

                # Extract prices
                article.prices = extract_prices(text)

                # Extract specs
                article.specs = extract_specs(text)

                article.processed = True
                processed += 1
                metrics.articles_processed += 1
                metrics.prices_extracted += len(article.prices)
                metrics.specs_extracted += len(article.specs)

                if brand:
                    metrics.brands_seen[brand] = metrics.brands_seen.get(brand, 0) + 1
                if model:
                    metrics.models_seen[f"{brand}/{model}"] = metrics.models_seen.get(f"{brand}/{model}", 0) + 1

                self.state.mark_processed(article.url, "succeeded")
                self.articles.append(article)

                # Progress indicator
                status_parts = []
                if article.prices:
                    status_parts.append(f"{len(article.prices)} prices")
                if article.specs:
                    status_parts.append(f"{len(article.specs)} specs")
                status = ", ".join(status_parts) if status_parts else "no data"
                print(f"    [{i+1}/{total}] {article.brand or '?'}/{article.model or '?'}: {status} | {article.title[:50]}")

            except Exception as e:
                failed += 1
                metrics.articles_failed += 1
                metrics.errors.append(f"{article.url}: {str(e)[:100]}")
                self.state.mark_processed(article.url, "failed")

            # Checkpoint every 10 articles
            if (i + 1) % 10 == 0:
                self._save_checkpoint()
                print(f"      [Checkpoint saved: {i+1}/{total} processed]")

        self._save_checkpoint()

    def _validate_scopes(self):
        """Validate that each article is primarily about one model."""
        valid_count = 0
        invalid_count = 0

        for article in self.articles:
            if not article.processed:
                continue

            if article.brand and article.model:
                is_valid, reason = validate_scope(
                    article.title, article.content_text,
                    article.brand, article.model
                )
                article.scope_valid = is_valid
                article.scope_reason = reason
                if is_valid:
                    valid_count += 1
                else:
                    invalid_count += 1
            else:
                article.scope_valid = False
                article.scope_reason = "no_model_identity"
                invalid_count += 1

        print(f"    Scope valid: {valid_count}, Invalid: {invalid_count}")

    def _save_results(self):
        """Save all results as JSON artifacts."""
        # Build the results structure
        results = {
            "run_id": self.state.run_id,
            "timestamp": now_iso(),
            "checkpoint_file": CHECKPOINT_FILE,
            "summary": {
                "total_discovered": sum(
                    m.articles_discovered for m in self.metrics.values()
                ),
                "total_processed": sum(
                    m.articles_processed for m in self.metrics.values()
                ),
                "total_failed": sum(
                    m.articles_failed for m in self.metrics.values()
                ),
                "total_prices": sum(
                    m.prices_extracted for m in self.metrics.values()
                ),
                "total_specs": sum(
                    m.specs_extracted for m in self.metrics.values()
                ),
                "sources_used": len([m for m in self.metrics.values()
                                     if m.articles_discovered > 0]),
                "brands_covered": list(set(
                    b for m in self.metrics.values() for b in m.brands_seen
                )),
                "models_found": list(set(
                    k for m in self.metrics.values() for k in m.models_seen
                )),
            },
            "per_source": {},
            "articles_with_prices": [],
            "articles_with_specs": [],
            "all_prices": [],
            "all_specs": [],
        }

        # Per-source metrics
        for source_domain, metrics in self.metrics.items():
            results["per_source"][source_domain] = {
                "display_name": next(
                    (s.display_name for s in SOURCES if s.domain == source_domain),
                    source_domain
                ),
                "discovered": metrics.articles_discovered,
                "processed": metrics.articles_processed,
                "failed": metrics.articles_failed,
                "prices": metrics.prices_extracted,
                "specs": metrics.specs_extracted,
                "brands": dict(metrics.brands_seen),
                "models": dict(metrics.models_seen),
                "errors": metrics.errors[:10],
                "duration": metrics.finished_at or now_iso(),
            }

        # Articles with data
        for article in self.articles:
            if article.prices:
                results["articles_with_prices"].append(article.to_dict())
                for price in article.prices:
                    price["source_url"] = article.url
                    price["brand"] = article.brand
                    price["model"] = article.model
                    price["source_domain"] = article.source_domain
                    results["all_prices"].append(price)

            if article.specs:
                results["articles_with_specs"].append(article.to_dict())
                for spec in article.specs:
                    spec["source_url"] = article.url
                    spec["brand"] = article.brand
                    spec["model"] = article.model
                    spec["source_domain"] = article.source_domain
                    results["all_specs"].append(spec)

        # Save results
        os.makedirs(STORAGE_DIR, exist_ok=True)
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"    Results saved to: {RESULTS_FILE}")

        # Save report
        report = self._generate_report(results)
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"    Report saved to: {REPORT_FILE}")

    def _generate_report(self, results: dict) -> dict:
        """Generate a human-readable report."""
        s = results["summary"]
        return {
            "title": "Thai Automotive Source Discovery Report",
            "run_id": self.state.run_id,
            "generated_at": now_iso(),
            "overview": {
                "articles_discovered": s["total_discovered"],
                "articles_processed": s["total_processed"],
                "articles_failed": s["total_failed"],
                "prices_extracted": s["total_prices"],
                "specs_extracted": s["total_specs"],
                "sources_active": s["sources_used"],
                "brands_covered": len(s["brands_covered"]),
                "models_found": len(s["models_found"]),
            },
            "targets_met": {
                "100_plus_articles": s["total_processed"] >= 100,
                "50_plus_prices": s["total_prices"] >= 50,
                "100_plus_specs": s["total_specs"] >= 100,
            },
            "per_source": results["per_source"],
            "top_brands_by_articles": self._top_brands(results),
            "top_models_by_data": self._top_models(results),
        }

    def _top_brands(self, results: dict) -> List[dict]:
        brand_counts: Dict[str, int] = {}
        for source_data in results["per_source"].values():
            for brand, count in source_data.get("brands", {}).items():
                brand_counts[brand] = brand_counts.get(brand, 0) + count
        return [{"brand": b, "count": c} for b, c in sorted(brand_counts.items(), key=lambda x: -x[1])[:15]]

    def _top_models(self, results: dict) -> List[dict]:
        model_counts: Dict[str, int] = {}
        for source_data in results["per_source"].values():
            for model, count in source_data.get("models", {}).items():
                model_counts[model] = model_counts.get(model, 0) + count
        return [{"model": m, "count": c} for m, c in sorted(model_counts.items(), key=lambda x: -x[1])[:20]]

    def _print_summary(self):
        """Print final summary."""
        print(f"\n{'=' * 70}")
        print(f"DISCOVERY COMPLETE")
        print(f"{'=' * 70}")

        total_discovered = sum(m.articles_discovered for m in self.metrics.values())
        total_processed = sum(m.articles_processed for m in self.metrics.values())
        total_prices = sum(m.prices_extracted for m in self.metrics.values())
        total_specs = sum(m.specs_extracted for m in self.metrics.values())
        sources_active = len([m for m in self.metrics.values() if m.articles_discovered > 0])

        print(f"  Articles discovered: {total_discovered}")
        print(f"  Articles processed:  {total_processed}")
        print(f"  Prices extracted:    {total_prices}")
        print(f"  Specs extracted:     {total_specs}")
        print(f"  Sources active:      {sources_active}/{len(SOURCES)}")

        # Target check
        print(f"\n  Targets:")
        print(f"    100+ articles: {'✓ MET' if total_processed >= 100 else f'✗ {total_processed}/100'}")
        print(f"    50+ prices:    {'✓ MET' if total_prices >= 50 else f'✗ {total_prices}/50'}")
        print(f"    100+ specs:    {'✓ MET' if total_specs >= 100 else f'✗ {total_specs}/100'}")

        # Per-source breakdown
        print(f"\n  Per-source breakdown:")
        for source in SOURCES:
            if source.domain in self.metrics:
                m = self.metrics[source.domain]
                if m.articles_discovered > 0:
                    print(f"    {source.display_name:30s} disc={m.articles_discovered:3d} "
                          f"proc={m.articles_processed:3d} "
                          f"prices={m.prices_extracted:3d} "
                          f"specs={m.specs_extracted:3d}")

        # Top brands
        all_brands = {}
        for m in self.metrics.values():
            for b, c in m.brands_seen.items():
                all_brands[b] = all_brands.get(b, 0) + c
        if all_brands:
            print(f"\n  Top brands by article count:")
            for b, c in sorted(all_brands.items(), key=lambda x: -x[1])[:10]:
                print(f"    {b:20s} {c:3d} articles")

        print(f"\n  Output files:")
        print(f"    Results:  {RESULTS_FILE}")
        print(f"    Report:   {REPORT_FILE}")
        print(f"    Checkpoint: {CHECKPOINT_FILE}")
        print(f"{'=' * 70}")


# ─── CLI Entry Point ────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Thai Automotive Source Discovery & Acquisition"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Reset checkpoint and start fresh")
    parser.add_argument("--max-per-source", type=int, default=30,
                        help="Max articles to process per source (default: 30)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without fetching")
    args = parser.parse_args()

    engine = ThaiSourceDiscovery(
        reset=args.reset,
        max_per_source=args.max_per_source,
        dry_run=args.dry_run,
    )
    engine.run()


if __name__ == "__main__":
    main()
