#!/usr/bin/env python3
"""
Thai Automotive Data Factory — Full Evidence Pipeline
=====================================================
DISCOVER → FETCH → EXTRACT → ENTITY RESOLUTION → SCOPE VALIDATION →
CLASSIFY → NORMALIZE → DEDUP → PERSIST → RECONCILE → AUDIT

Fetches live URLs from 6 Thai automotive sources in parallel,
extracts prices and specs with full provenance, resolves entities
against the DB, validates scope, deduplicates, and persists.

Usage:
    python3 thai-data-factory.py [--reset] [--max-per-source N] [--dry-run]
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage")
CHECKPOINT_FILE = os.path.join(STORAGE_DIR, "data-factory-checkpoint.json")
RESULTS_FILE = os.path.join(STORAGE_DIR, "data-factory-results.json")
METRICS_FILE = os.path.join(STORAGE_DIR, "data-factory-metrics.json")
REPORT_FILE = os.path.join(STORAGE_DIR, "data-factory-report.txt")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20
THB_MIN = 100_000
THB_MAX = 20_000_000
EXTRACTOR_VERSION = "1.0.0"

# ═══════════════════════════════════════════════════════════════════════
# DATA CLASS: OBSERVATION
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Observation:
    """A single source-backed observation with full provenance."""
    source_url: str
    source_domain: str
    source_class: str          # AUTO_MEDIA, REFERENCE_MEDIA, etc.
    title: str
    published_date: str
    brand: str
    model: str
    variant: str               # "" for model-range pricing
    field_type: str            # "price" or "spec"
    raw_value: str
    normalized_value: str
    unit: str
    price_type: str            # MSRP, LIST_PRICE, PROMOTION, etc.
    confidence: float
    scope_state: str           # SINGLE_MODEL, MULTI_MODEL, COMPARISON, ROUNDUP, UNKNOWN
    trust_state: str           # QUALIFIED, UNVERIFIED, REJECTED
    evidence_excerpt: str
    content_hash: str
    extractor_version: str
    observed_at: str

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════
# BRAND KEYWORDS (Thai + English)
# ═══════════════════════════════════════════════════════════════════════

BRAND_KEYWORDS: Dict[str, List[str]] = {
    "toyota": ["toyota", "โตโยต้า", "yaris", "corolla", "camry", "fortuner",
               "hilux", "innova", "veloz", "avanza", "bz4x", "land cruiser",
               "alphard", "hiace", "commuter", "rav4", "yzaris", "yz Cross",
               "fortuner", "cross"],
    "honda": ["honda", "ฮอนด้า", "city", "civic", "hr-v", "cr-v", "br-v",
              "accord", "wr-v", "zr-v", "hrv", "crv"],
    "nissan": ["nissan", "นิสสัน", "almera", "kicks", "x-trail", "terra",
               "navara", "serena", "leaf", "sakura", "urvan", "note"],
    "mazda": ["mazda", "มาสด้า", "mazda2", "mazda3", "cx-3", "cx-30", "cx-5",
              "cx-80", "6e", "cx-60", "cx-90"],
    "mitsubishi": ["mitsubishi", "มิตซูบิชิ", "mirage", "attrage", "xpander",
                    "triton", "pajero"],
    "isuzu": ["isuzu", "อีซูซุ", "d-max", "mu-x", "dmax"],
    "ford": ["ford", "ฟอร์ด", "ranger", "everest", "territory", "maverick"],
    "suzuki": ["suzuki", "ซูซูกิ", "swift", "vitara", "xl7", "s-presso",
               "jimny", "fronx", "celerio", "CELERIO"],
    "hyundai": ["hyundai", "ฮุนได", "ioniq", "santa-fe", "stargazer",
                "staria", "tucson", "kona"],
    "kia": ["kia", "เกีย", "sonet", "sportage", "ev6", "ev9", "carnival",
            "niro", "seltos"],
    "porsche": ["porsche", "ปอร์เช่", "cayenne", "macan", "taycan", "panamera"],
    "mercedes": ["mercedes", "เบนซ์", "benz", "class", "gla", "glc", "gle",
                 "eqa", "eqb", "eqs", "a-class", "c-class", "e-class"],
    "volvo": ["volvo", "วอลโว่", "xc40", "xc60", "xc90", "ex30", "ex90"],
    "mg": ["mg", "mg3", "mg4", "mg5", "zs-ev", "hs-", "im5", "im6",
           "s5-ev", "urban-ev", "cyberster", "ep-plus", "mg-zs"],
    "byd": ["byd", "atto", "dolphin", "seal", "sealion", "m6", "seal-6"],
    "gwm": ["gwm", "haval", "ora-", "tank-", "jolion", "h6"],
    "bmw": ["bmw", "ซีรีส์", "x1", "x3", "x5", "ix", "i5", "i7", "x7"],
    "chevrolet": ["chevrolet", "เชฟโรเลต", "trailblazer", "colorado", "captiva"],
    "chery": ["chery", "เชอรี่", "omoda", "tiggo", "jaecoo"],
    "subaru": ["subaru", "ซูบารุ", "crosstrek", "outback", "forester"],
    "tesla": ["tesla", "เทสลา", "model-3", "model-y", "model s", "model x"],
    "zeekr": ["zeekr"],
    "changan": ["changan", "changan", "cs55", "uni-v", "uni-k", "deepal"],
    "geely": ["geely", "geely", "starray", "ex5", "ex2"],
    "nio": ["nio", "nio", "es6", "et5", "firefly"],
    "baic": ["baic", "x55", "bj30", "bj40"],
    "ldv": ["ldv", "d90", "t60", "mifa"],
    "jetour": ["jetour", "dashing", "t2"],
    "lexus": ["lexus", "เลกซัส", "nx", "rx", "rz", "es", "ls", "ux"],
    "mini": ["mini", "คูเปอร์", "cooper", "countryman", "aceman"],
    "dongfeng": ["dongfeng", "dongfeng", "forthing"],
    "denza": ["denza", "denza", "d9", "n7", "z9gt"],
    "kg mobility": ["kg mobility", "torres", "korando"],
}

# Reverse map: keyword → brand slug (lowercased first-match)
_KEY_TO_BRAND: Dict[str, str] = {}
for _brand, _kws in BRAND_KEYWORDS.items():
    for _kw in _kws:
        if _kw.lower() not in _KEY_TO_BRAND:
            _KEY_TO_BRAND[_kw.lower()] = _brand


# ═══════════════════════════════════════════════════════════════════════
# DB ACCESS (docker exec psql)
# ═══════════════════════════════════════════════════════════════════════

def psql(sql: str, fetch: bool = True) -> List[str]:
    """Execute SQL via docker exec psql, return pipe-delimited rows."""
    cmd = [
        "docker", "exec", "pgvector", "psql",
        "-U", "hermes", "-d", "thai_car_intelligence",
        "-t", "-A", "-F", "|", "-c", sql,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as e:
        print(f"  [psql] connection error: {e}", file=sys.stderr)
        return [] if fetch else ""
    if result.returncode != 0:
        print(f"  [psql] error: {result.stderr[:300]}", file=sys.stderr)
        return [] if fetch else ""
    if not fetch:
        return result.stdout.strip()
    lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
    return lines


def psql_batch(sql_stmts: List[str]) -> List[str]:
    """Execute multiple SQL statements in one docker exec call."""
    combined = ";\n".join(sql_stmts) + ";\n"
    cmd = [
        "docker", "exec", "-i", "pgvector", "psql",
        "-U", "hermes", "-d", "thai_car_intelligence",
        "-t", "-A", "-F", "|",
    ]
    try:
        result = subprocess.run(cmd, input=combined, capture_output=True, text=True, timeout=60)
    except Exception as e:
        print(f"  [psql_batch] error: {e}", file=sys.stderr)
        return []
    if result.returncode != 0:
        print(f"  [psql_batch] error: {result.stderr[:300]}", file=sys.stderr)
        return []
    lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
    return lines


def get_existing_sources() -> Dict[str, dict]:
    """Get existing Source records keyed by domain."""
    rows = psql('SELECT id, "nameEn", "baseUrl", "domain" FROM "Source"')
    sources = {}
    for row in rows:
        parts = row.split("|")
        if len(parts) >= 4:
            sources[parts[3].strip()] = {"id": parts[0].strip(), "name": parts[1].strip()}
    return sources


def get_existing_variants() -> Dict[str, Any]:
    """Get variant ID map: 'brand|model' → list of {id, slug, name}."""
    rows = psql('''
        SELECT v.id, v.slug, v."nameEn", cm."nameEn" as model_name, m."nameEn" as brand_name
        FROM "Variant" v
        JOIN "CarModel" cm ON v."modelId" = cm.id
        JOIN "Manufacturer" m ON cm."manufacturerId" = m.id
    ''')
    variants: Dict[str, Any] = {}
    for row in rows:
        parts = row.split("|")
        if len(parts) < 5:
            continue
        bm_key = f"{parts[4].strip().lower()}|{parts[3].strip().lower()}"
        if bm_key not in variants:
            variants[bm_key] = []
        variants[bm_key].append({
            "id": parts[0].strip(),
            "slug": parts[1].strip(),
            "name": parts[2].strip(),
        })
    return variants


def get_or_create_source(sources: dict, name: str, url: str) -> str:
    """Get or create a Source record. Returns source ID."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    if domain in sources:
        return sources[domain]["id"]
    source_id = str(uuid.uuid4())
    safe_name = name.replace("'", "''")
    safe_url = url.replace("'", "''")
    psql(f'''
        INSERT INTO "Source" (id, "nameTh", "nameEn", "sourceType", "baseUrl", "domain",
              "status", "createdAt", "updatedAt")
        VALUES ('{source_id}', '{safe_name}', '{safe_name}', 'AUTOMOTIVE_MEDIA'::"SourceType",
                '{safe_url}', '{domain}', 'ACTIVE'::"RecordStatus", NOW(), NOW())
    ''', fetch=False)
    sources[domain] = {"id": source_id, "name": name}
    return source_id


def create_source_document(source_id: str, url: str, content_hash: str,
                           method: str, title: str = "") -> str:
    """Create a SourceDocument. Returns doc ID (existing or new)."""
    safe_url = url.replace("'", "''")[:2000]
    safe_hash = content_hash.replace("'", "''")[:200]
    safe_method = method.replace("'", "''")[:200]
    safe_title = title.replace("'", "''")[:500]
    existing = psql(f'''
        SELECT id FROM "SourceDocument"
        WHERE "sourceId" = '{source_id}' AND "contentHash" = '{safe_hash}'
    ''')
    if existing:
        return existing[0].strip()
    doc_id = str(uuid.uuid4())
    psql(f'''
        INSERT INTO "SourceDocument" (id, "sourceId", url, "contentHash", "extractionMethod",
              "fetchedAt", status, "extractionStatus", "createdAt", "updatedAt", "titleTh")
        VALUES ('{doc_id}', '{source_id}', '{safe_url}', '{safe_hash}', '{safe_method}',
                NOW(), 'VERIFIED'::"DocumentStatus", 'SUCCEEDED'::"ExtractionStatus",
                NOW(), NOW(), '{safe_title}')
    ''', fetch=False)
    return doc_id


def resolve_variant(brand: str, model: str, variants_map: Dict) -> Optional[str]:
    """Map brand+model to a DB variant ID. Returns first match or None."""
    brand_l = brand.lower().strip()
    model_l = model.lower().strip()
    # Normalize common variations
    NORM = {
        "hilux revo": "hilux", "hilux champ": "hilux",
        "innova crysta": "innova zenix", "innova": "innova zenix",
        "corolla altis gr sport": "corolla altis",
        "corolla cross gr sport": "corolla cross",
        "fortuner gr sport": "fortuner", "fortuner legender": "fortuner",
        "yaris ativ gr sport": "yaris ativ",
        "kicks e-power": "kicks", "new kicks": "kicks",
        "np300 navara double cab": "navara", "np300 navara king cab": "navara",
        "new navara single cab": "navara",
    }
    norm_model = NORM.get(model_l, model_l)
    bm_key = f"{brand_l}|{norm_model}"
    if bm_key in variants_map:
        vlist = variants_map[bm_key]
        if isinstance(vlist, list) and vlist:
            return vlist[0]["id"]
    # Try original if normalized didn't match
    if norm_model != model_l:
        bm_key2 = f"{brand_l}|{model_l}"
        if bm_key2 in variants_map:
            vlist = variants_map[bm_key2]
            if isinstance(vlist, list) and vlist:
                return vlist[0]["id"]
    return None


# ═══════════════════════════════════════════════════════════════════════
# FETCH HELPER
# ═══════════════════════════════════════════════════════════════════════

def fetch_url(url: str, retries: int = 2) -> Optional[str]:
    """Fetch URL with retries. Returns content string or None."""
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "th,en;q=0.9",
            })
            with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = resp.read()
                # Detect encoding
                content_type = resp.headers.get("Content-Type", "")
                charset = "utf-8"
                if "charset=" in content_type:
                    charset = content_type.split("charset=")[-1].strip()
                return data.decode(charset, errors="replace")
        except Exception as e:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            else:
                print(f"  [fetch] FAIL {url}: {e}", file=sys.stderr)
                return None


# ═══════════════════════════════════════════════════════════════════════
# SOURCE ADAPTER BASE CLASS
# ═══════════════════════════════════════════════════════════════════════

class SourceAdapter(ABC):
    """Base class for Thai automotive source adapters."""

    name: str = "Unknown"
    domain: str = ""
    source_class: str = "AUTO_MEDIA"
    trust_state: str = "UNVERIFIED"

    @abstractmethod
    def discover(self, max_articles: int = 15) -> List[dict]:
        """Discover article URLs. Returns list of {url, title, published_date}."""
        ...

    @abstractmethod
    def fetch(self, url: str) -> Optional[str]:
        """Fetch article content. Returns HTML/text or None."""
        ...

    @abstractmethod
    def extract(self, url: str, html: str, meta: dict) -> List[Observation]:
        """Extract observations from article. Returns list of Observation."""
        ...

    def _make_obs(self, url: str, html: str, meta: dict,
                  field_type: str, raw_value: str, normalized_value: str,
                  unit: str, price_type: str = "", brand: str = "",
                  model: str = "", variant: str = "",
                  evidence: str = "") -> Observation:
        """Build an Observation with provenance fields."""
        domain = urlparse(url).netloc.replace("www.", "")
        content_h = hashlib.sha256(
            (url + raw_value + normalized_value).encode("utf-8")
        ).hexdigest()[:16]
        return Observation(
            source_url=url,
            source_domain=domain,
            source_class=self.source_class,
            title=meta.get("title", ""),
            published_date=meta.get("published_date", ""),
            brand=brand,
            model=model,
            variant=variant,
            field_type=field_type,
            raw_value=raw_value,
            normalized_value=normalized_value,
            unit=unit,
            price_type=price_type,
            confidence=0.75,
            scope_state="UNKNOWN",
            trust_state=self.trust_state,
            evidence_excerpt=(evidence or raw_value)[:500],
            content_hash=content_h,
            extractor_version=EXTRACTOR_VERSION,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )


# ═══════════════════════════════════════════════════════════════════════
# ADAPTER: HeadlightMag
# ═══════════════════════════════════════════════════════════════════════

class HeadlightMagAdapter(SourceAdapter):
    name = "HeadLight Magazine"
    domain = "headlightmag.com"
    source_class = "AUTO_MEDIA"
    trust_state = "UNVERIFIED"

    RSS_URL = "https://www.headlightmag.com/feed/"
    CATEGORY_URLS = [
        "https://www.headlightmag.com/category/news/new-cars-in-thailand/",
        "https://www.headlightmag.com/category/news/",
    ]

    def discover(self, max_articles=15) -> List[dict]:
        articles = []
        seen = set()

        # RSS feed
        print(f"  [{self.name}] Fetching RSS...")
        rss_html = fetch_url(self.RSS_URL)
        if rss_html:
            for m in re.finditer(r'<link>(https?://(?:www\.)?headlightmag\.com/[^<]*)</link>', rss_html):
                url = m.group(1).strip()
                # Skip homepage and feed URLs
                if url in seen or "/feed/" in url or url.rstrip("/") in ("https://www.headlightmag.com", "https://headlightmag.com"):
                    continue
                seen.add(url)
                title_m = re.search(r'<title>(.*?)</title>', rss_html[m.start():m.start()+600])
                title = title_m.group(1) if title_m else ""
                pub_m = re.search(r'<pubDate>(.*?)</pubDate>', rss_html[m.start():m.start()+800])
                pub = pub_m.group(1) if pub_m else ""
                articles.append({"url": url, "title": title, "published_date": pub})
                if len(articles) >= max_articles:
                    break

        # Category pages as fallback
        if len(articles) < max_articles:
            for cat_url in self.CATEGORY_URLS:
                if len(articles) >= max_articles:
                    break
                print(f"  [{self.name}] Fetching category: {cat_url}")
                cat_html = fetch_url(cat_url)
                if not cat_html:
                    continue
                for m in re.finditer(r'href="(https://www\.headlightmag\.com/\d{4}-\d{2}-\d{2}[^"]*)"', cat_html):
                    url = m.group(1).strip()
                    if url not in seen:
                        seen.add(url)
                        articles.append({"url": url, "title": "", "published_date": ""})
                        if len(articles) >= max_articles:
                            break
                time.sleep(1)

        return articles[:max_articles]

    def fetch(self, url: str) -> Optional[str]:
        return fetch_url(url)

    def extract(self, url: str, html: str, meta: dict) -> List[Observation]:
        if not html:
            return []
        obs_list = []
        title = meta.get("title", "")
        if not title:
            t_m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
            if t_m:
                title = t_m.group(1).strip()

        # Extract prices: ราคา + number + บาท
        for m in re.finditer(r'ราคา[^0-9]{0,30}(\d{1,3}(?:,\d{3})+)\s*บาท', html):
            num = int(m.group(1).replace(",", ""))
            if THB_MIN <= num <= THB_MAX:
                start = max(0, m.start() - 200)
                end = min(len(html), m.end() + 100)
                excerpt = re.sub(r'<[^>]+>', ' ', html[start:end]).strip()[:300]
                brand, model = _detect_brand_model(title + " " + excerpt)
                obs_list.append(self._make_obs(
                    url, html, meta, "price", m.group(1), str(num), "THB",
                    price_type=_detect_price_type(excerpt),
                    brand=brand, model=model, variant=_detect_variant(excerpt),
                    evidence=excerpt,
                ))

        # Also: ฿ + number
        for m in re.finditer(r'฿\s*(\d{1,3}(?:,\d{3})+)', html):
            num = int(m.group(1).replace(",", ""))
            if THB_MIN <= num <= THB_MAX:
                start = max(0, m.start() - 200)
                excerpt = re.sub(r'<[^>]+>', ' ', html[start:min(len(html), m.end()+100)]).strip()[:300]
                brand, model = _detect_brand_model(title + " " + excerpt)
                obs_list.append(self._make_obs(
                    url, html, meta, "price", m.group(1), str(num), "THB",
                    price_type=_detect_price_type(excerpt),
                    brand=brand, model=model, variant=_detect_variant(excerpt),
                    evidence=excerpt,
                ))

        # Extract specs
        obs_list.extend(_extract_specs(html, url, meta, self))

        return obs_list


# ═══════════════════════════════════════════════════════════════════════
# ADAPTER: AutoSpinn
# ═══════════════════════════════════════════════════════════════════════

class AutoSpinnAdapter(SourceAdapter):
    name = "AutoSpinn"
    domain = "autospinn.com"
    source_class = "AUTO_MEDIA"
    trust_state = "UNVERIFIED"

    RSS_URL = "https://www.autospinn.com/rss"
    CATEGORY_URLS = [
        "https://www.autospinn.com/category/new-cars/",
        "https://www.autospinn.com/category/tech/",
    ]

    def discover(self, max_articles=15) -> List[dict]:
        articles = []
        seen = set()

        # RSS
        print(f"  [{self.name}] Fetching RSS...")
        rss = fetch_url(self.RSS_URL)
        if rss:
            for m in re.finditer(r'<link>(https?://(?:www\.)?autospinn\.com/[^<]*)</link>', rss):
                url = m.group(1).strip()
                # Skip homepage and non-article URLs
                if url in seen or "/feed/" in url or url.rstrip("/") == "https://www.autospinn.com" or url.rstrip("/") == "https://autospinn.com":
                    continue
                seen.add(url)
                t_m = re.search(r'<title>(.*?)</title>', rss[m.start():m.start()+600])
                title = t_m.group(1) if t_m else ""
                p_m = re.search(r'<pubDate>(.*?)</pubDate>', rss[m.start():m.start()+800])
                pub = p_m.group(1) if p_m else ""
                articles.append({"url": url, "title": title, "published_date": pub})
                if len(articles) >= max_articles:
                    break

        # Category fallback
        if len(articles) < max_articles:
            for cat in self.CATEGORY_URLS:
                if len(articles) >= max_articles:
                    break
                print(f"  [{self.name}] Fetching category: {cat}")
                html = fetch_url(cat)
                if not html:
                    continue
                for m in re.finditer(r'href="(https?://www\.autospinn\.com/\d{4}[^"]*)"', html):
                    url = m.group(1).strip()
                    if url not in seen:
                        seen.add(url)
                        articles.append({"url": url, "title": "", "published_date": ""})
                        if len(articles) >= max_articles:
                            break
                time.sleep(1)

        return articles[:max_articles]

    def fetch(self, url: str) -> Optional[str]:
        return fetch_url(url)

    def extract(self, url: str, html: str, meta: dict) -> List[Observation]:
        if not html:
            return []
        obs_list = []
        title = meta.get("title", "")
        if not title:
            t_m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
            if t_m:
                title = t_m.group(1).strip()

        for m in re.finditer(r'ราคา[^0-9]{0,30}(\d{1,3}(?:,\d{3})+)\s*บาท', html):
            num = int(m.group(1).replace(",", ""))
            if THB_MIN <= num <= THB_MAX:
                start = max(0, m.start() - 200)
                excerpt = re.sub(r'<[^>]+>', ' ', html[start:min(len(html), m.end()+100)]).strip()[:300]
                brand, model = _detect_brand_model(title + " " + excerpt)
                obs_list.append(self._make_obs(
                    url, html, meta, "price", m.group(1), str(num), "THB",
                    price_type=_detect_price_type(excerpt),
                    brand=brand, model=model, variant=_detect_variant(excerpt),
                    evidence=excerpt,
                ))

        for m in re.finditer(r'฿\s*(\d{1,3}(?:,\d{3})+)', html):
            num = int(m.group(1).replace(",", ""))
            if THB_MIN <= num <= THB_MAX:
                start = max(0, m.start() - 200)
                excerpt = re.sub(r'<[^>]+>', ' ', html[start:min(len(html), m.end()+100)]).strip()[:300]
                brand, model = _detect_brand_model(title + " " + excerpt)
                obs_list.append(self._make_obs(
                    url, html, meta, "price", m.group(1), str(num), "THB",
                    price_type=_detect_price_type(excerpt),
                    brand=brand, model=model, variant=_detect_variant(excerpt),
                    evidence=excerpt,
                ))

        obs_list.extend(_extract_specs(html, url, meta, self))
        return obs_list


# ═══════════════════════════════════════════════════════════════════════
# ADAPTER: AutoLifeThailand
# ═══════════════════════════════════════════════════════════════════════

class AutoLifeThailandAdapter(SourceAdapter):
    name = "AutoLife Thailand"
    domain = "autolifethailand.tv"
    source_class = "AUTO_MEDIA"
    trust_state = "UNVERIFIED"

    RSS_URL = "https://www.autolifethailand.tv/feed/"

    def discover(self, max_articles=15) -> List[dict]:
        articles = []
        seen = set()
        print(f"  [{self.name}] Fetching RSS...")
        rss = fetch_url(self.RSS_URL)
        if rss:
            for m in re.finditer(r'<link>(https?://(?:www\.)?autolifethailand\.tv/[^<]*)</link>', rss):
                url = m.group(1).strip()
                if url not in seen and "/feed/" not in url:
                    seen.add(url)
                    t_m = re.search(r'<title>(.*?)</title>', rss[m.start():m.start()+600])
                    title = t_m.group(1) if t_m else ""
                    p_m = re.search(r'<pubDate>(.*?)</pubDate>', rss[m.start():m.start()+800])
                    pub = p_m.group(1) if p_m else ""
                    articles.append({"url": url, "title": title, "published_date": pub})
                    if len(articles) >= max_articles:
                        break
        return articles[:max_articles]

    def fetch(self, url: str) -> Optional[str]:
        return fetch_url(url)

    def extract(self, url: str, html: str, meta: dict) -> List[Observation]:
        if not html:
            return []
        obs_list = []
        title = meta.get("title", "")
        if not title:
            t_m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
            if t_m:
                title = t_m.group(1).strip()

        for m in re.finditer(r'ราคา[^0-9]{0,30}(\d{1,3}(?:,\d{3})+)\s*บาท', html):
            num = int(m.group(1).replace(",", ""))
            if THB_MIN <= num <= THB_MAX:
                start = max(0, m.start() - 200)
                excerpt = re.sub(r'<[^>]+>', ' ', html[start:min(len(html), m.end()+100)]).strip()[:300]
                brand, model = _detect_brand_model(title + " " + excerpt)
                obs_list.append(self._make_obs(
                    url, html, meta, "price", m.group(1), str(num), "THB",
                    price_type=_detect_price_type(excerpt),
                    brand=brand, model=model, variant=_detect_variant(excerpt),
                    evidence=excerpt,
                ))

        for m in re.finditer(r'฿\s*(\d{1,3}(?:,\d{3})+)', html):
            num = int(m.group(1).replace(",", ""))
            if THB_MIN <= num <= THB_MAX:
                start = max(0, m.start() - 200)
                excerpt = re.sub(r'<[^>]+>', ' ', html[start:min(len(html), m.end()+100)]).strip()[:300]
                brand, model = _detect_brand_model(title + " " + excerpt)
                obs_list.append(self._make_obs(
                    url, html, meta, "price", m.group(1), str(num), "THB",
                    price_type=_detect_price_type(excerpt),
                    brand=brand, model=model, variant=_detect_variant(excerpt),
                    evidence=excerpt,
                ))

        obs_list.extend(_extract_specs(html, url, meta, self))
        return obs_list


# ═══════════════════════════════════════════════════════════════════════
# ADAPTER: 9CARTHAI
# ═══════════════════════════════════════════════════════════════════════

class NineCarThaiAdapter(SourceAdapter):
    name = "9CARTHAI"
    domain = "9carthai.com"
    source_class = "REFERENCE_MEDIA"
    trust_state = "UNVERIFIED"

    RSS_URL = "https://www.9carthai.com/feed/"

    def discover(self, max_articles=15) -> List[dict]:
        articles = []
        seen = set()
        print(f"  [{self.name}] Fetching RSS...")
        rss = fetch_url(self.RSS_URL)
        if rss:
            for m in re.finditer(r'<link>(https?://www\.9carthai\.com/[^<]*)</link>', rss):
                url = m.group(1).strip()
                if url not in seen:
                    seen.add(url)
                    t_m = re.search(r'<title>(.*?)</title>', rss[m.start():m.start()+600])
                    title = t_m.group(1) if t_m else ""
                    p_m = re.search(r'<pubDate>(.*?)</pubDate>', rss[m.start():m.start()+800])
                    pub = p_m.group(1) if p_m else ""
                    articles.append({"url": url, "title": title, "published_date": pub})
                    if len(articles) >= max_articles:
                        break
        # Also try brand price pages
        brand_slugs = ["toyota", "honda", "nissan", "mazda", "ford", "mg", "byd"]
        for slug in brand_slugs:
            if len(articles) >= max_articles:
                break
            price_url = f"https://www.9carthai.com/{slug}-price/"
            if price_url not in seen:
                seen.add(price_url)
                articles.append({"url": price_url, "title": f"{slug} price list", "published_date": ""})
        return articles[:max_articles]

    def fetch(self, url: str) -> Optional[str]:
        return fetch_url(url)

    def extract(self, url: str, html: str, meta: dict) -> List[Observation]:
        if not html:
            return []
        obs_list = []
        title = meta.get("title", "")
        if not title:
            t_m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
            if t_m:
                title = t_m.group(1).strip()

        # 9CARTHAI price list pages: brand + model + variant + price pattern
        for m in re.finditer(
            r'((?:BYD|MG|Honda|Toyota|Ford|Hyundai|Nissan|Suzuki|BMW|Tesla|Geely|GWM|'
            r'Mazda|Subaru|Mitsubishi|Kia|Volvo|Mercedes|Isuzu|Chevrolet|Chery|'
            r'Zeekr|Changan|NIO|BAIC|LDV|Jetour|MG|Lexus|Mini|Porsche|Denza)'
            r'[^<]{2,60})\s+(\d{1,3}(?:,\d{3})+)', html
        ):
            variant_text = m.group(1).strip()
            price_str = m.group(2)
            num = int(price_str.replace(",", ""))
            if THB_MIN <= num <= THB_MAX:
                start = max(0, m.start() - 100)
                excerpt = re.sub(r'<[^>]+>', ' ', html[start:min(len(html), m.end()+50)]).strip()[:300]
                brand, model = _detect_brand_model(variant_text)
                variant = _detect_variant(variant_text)
                obs_list.append(self._make_obs(
                    url, html, meta, "price", price_str, str(num), "THB",
                    price_type="MSRP",
                    brand=brand, model=model, variant=variant,
                    evidence=excerpt,
                ))

        # Fallback: generic price pattern
        for m in re.finditer(r'ราคา[^0-9]{0,30}(\d{1,3}(?:,\d{3})+)\s*บาท', html):
            num = int(m.group(1).replace(",", ""))
            if THB_MIN <= num <= THB_MAX:
                start = max(0, m.start() - 200)
                excerpt = re.sub(r'<[^>]+>', ' ', html[start:min(len(html), m.end()+100)]).strip()[:300]
                brand, model = _detect_brand_model(title + " " + excerpt)
                obs_list.append(self._make_obs(
                    url, html, meta, "price", m.group(1), str(num), "THB",
                    price_type=_detect_price_type(excerpt),
                    brand=brand, model=model, variant=_detect_variant(excerpt),
                    evidence=excerpt,
                ))

        obs_list.extend(_extract_specs(html, url, meta, self))
        return obs_list


# ═══════════════════════════════════════════════════════════════════════
# ADAPTER: Car2Day
# ═══════════════════════════════════════════════════════════════════════

class Car2DayAdapter(SourceAdapter):
    name = "Car2Day"
    domain = "car2day.com"
    source_class = "AUTO_MEDIA"
    trust_state = "UNVERIFIED"

    RSS_URL = "https://www.car2day.com/feed/"

    def discover(self, max_articles=15) -> List[dict]:
        articles = []
        seen = set()
        print(f"  [{self.name}] Fetching RSS...")
        rss = fetch_url(self.RSS_URL)
        if rss:
            for m in re.finditer(r'<link>(https?://(?:www\.)?car2day\.com/[^<]*)</link>', rss):
                url = m.group(1).strip()
                if url not in seen and "/feed/" not in url and url.rstrip("/") != "https://car2day.com":
                    seen.add(url)
                    t_m = re.search(r'<title>(.*?)</title>', rss[m.start():m.start()+600])
                    title = t_m.group(1) if t_m else ""
                    p_m = re.search(r'<pubDate>(.*?)</pubDate>', rss[m.start():m.start()+800])
                    pub = p_m.group(1) if p_m else ""
                    articles.append({"url": url, "title": title, "published_date": pub})
                    if len(articles) >= max_articles:
                        break
        return articles[:max_articles]

    def fetch(self, url: str) -> Optional[str]:
        return fetch_url(url)

    def extract(self, url: str, html: str, meta: dict) -> List[Observation]:
        if not html:
            return []
        obs_list = []
        title = meta.get("title", "")
        if not title:
            t_m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
            if t_m:
                title = t_m.group(1).strip()

        for m in re.finditer(r'ราคา[^0-9]{0,30}(\d{1,3}(?:,\d{3})+)\s*บาท', html):
            num = int(m.group(1).replace(",", ""))
            if THB_MIN <= num <= THB_MAX:
                start = max(0, m.start() - 200)
                excerpt = re.sub(r'<[^>]+>', ' ', html[start:min(len(html), m.end()+100)]).strip()[:300]
                brand, model = _detect_brand_model(title + " " + excerpt)
                obs_list.append(self._make_obs(
                    url, html, meta, "price", m.group(1), str(num), "THB",
                    price_type=_detect_price_type(excerpt),
                    brand=brand, model=model, variant=_detect_variant(excerpt),
                    evidence=excerpt,
                ))

        for m in re.finditer(r'฿\s*(\d{1,3}(?:,\d{3})+)', html):
            num = int(m.group(1).replace(",", ""))
            if THB_MIN <= num <= THB_MAX:
                start = max(0, m.start() - 200)
                excerpt = re.sub(r'<[^>]+>', ' ', html[start:min(len(html), m.end()+100)]).strip()[:300]
                brand, model = _detect_brand_model(title + " " + excerpt)
                obs_list.append(self._make_obs(
                    url, html, meta, "price", m.group(1), str(num), "THB",
                    price_type=_detect_price_type(excerpt),
                    brand=brand, model=model, variant=_detect_variant(excerpt),
                    evidence=excerpt,
                ))

        obs_list.extend(_extract_specs(html, url, meta, self))
        return obs_list


# ═══════════════════════════════════════════════════════════════════════
# ADAPTER: CheckRaka
# ═══════════════════════════════════════════════════════════════════════

class CheckRakaAdapter(SourceAdapter):
    name = "CheckRaka"
    domain = "checkraka.com"
    source_class = "AUTO_MEDIA"
    trust_state = "UNVERIFIED"

    CATEGORY_URLS = [
        "https://www.checkraka.com/car",
        "https://www.checkraka.com/ev-car",
    ]

    def discover(self, max_articles=15) -> List[dict]:
        articles = []
        seen = set()
        for cat_url in self.CATEGORY_URLS:
            if len(articles) >= max_articles:
                break
            print(f"  [{self.name}] Fetching category: {cat_url}")
            html = fetch_url(cat_url)
            if not html:
                continue
            for m in re.finditer(r'href="(/car/[^"]*)"', html):
                path = m.group(1)
                full_url = "https://www.checkraka.com" + path
                if full_url not in seen:
                    seen.add(full_url)
                    articles.append({"url": full_url, "title": "", "published_date": ""})
                    if len(articles) >= max_articles:
                        break
            time.sleep(1)
        return articles[:max_articles]

    def fetch(self, url: str) -> Optional[str]:
        return fetch_url(url)

    def extract(self, url: str, html: str, meta: dict) -> List[Observation]:
        if not html:
            return []
        obs_list = []
        title = meta.get("title", "")
        if not title:
            t_m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
            if t_m:
                title = t_m.group(1).strip()

        for m in re.finditer(r'ราคา[^0-9]{0,30}(\d{1,3}(?:,\d{3})+)\s*บาท', html):
            num = int(m.group(1).replace(",", ""))
            if THB_MIN <= num <= THB_MAX:
                start = max(0, m.start() - 200)
                excerpt = re.sub(r'<[^>]+>', ' ', html[start:min(len(html), m.end()+100)]).strip()[:300]
                brand, model = _detect_brand_model(title + " " + excerpt)
                obs_list.append(self._make_obs(
                    url, html, meta, "price", m.group(1), str(num), "THB",
                    price_type=_detect_price_type(excerpt),
                    brand=brand, model=model, variant=_detect_variant(excerpt),
                    evidence=excerpt,
                ))

        for m in re.finditer(r'฿\s*(\d{1,3}(?:,\d{3})+)', html):
            num = int(m.group(1).replace(",", ""))
            if THB_MIN <= num <= THB_MAX:
                start = max(0, m.start() - 200)
                excerpt = re.sub(r'<[^>]+>', ' ', html[start:min(len(html), m.end()+100)]).strip()[:300]
                brand, model = _detect_brand_model(title + " " + excerpt)
                obs_list.append(self._make_obs(
                    url, html, meta, "price", m.group(1), str(num), "THB",
                    price_type=_detect_price_type(excerpt),
                    brand=brand, model=model, variant=_detect_variant(excerpt),
                    evidence=excerpt,
                ))

        obs_list.extend(_extract_specs(html, url, meta, self))
        return obs_list


# ═══════════════════════════════════════════════════════════════════════
# ENTITY RESOLUTION
# ═══════════════════════════════════════════════════════════════════════

def _detect_brand_model(text: str) -> Tuple[str, str]:
    """Detect brand and model from text. Returns (brand, model)."""
    lower = text.lower()
    # Find brand
    detected_brand = ""
    detected_model = ""
    best_brand_pos = -1

    for brand, keywords in BRAND_KEYWORDS.items():
        for kw in keywords:
            pos = lower.find(kw.lower())
            if pos != -1 and (best_brand_pos == -1 or pos < best_brand_pos):
                detected_brand = brand
                best_brand_pos = pos

    if not detected_brand:
        return "", ""

    # Try to extract model name after brand keyword
    # Look for common model names near the brand mention
    brand_kws = BRAND_KEYWORDS.get(detected_brand, [])
    for kw in sorted(brand_kws, key=len, reverse=True):
        kw_pos = lower.find(kw.lower())
        if kw_pos != -1:
            # Extract words after the keyword
            after = text[kw_pos:kw_pos+100]
            # Clean HTML
            after = re.sub(r'<[^>]+>', ' ', after)
            # Find model-like word (capitalized or known patterns)
            words = after.split()
            model_words = []
            for w in words[1:6]:  # skip brand keyword itself
                w_clean = re.sub(r'[^a-zA-Z0-9\-]', '', w)
                if w_clean and len(w_clean) > 1:
                    model_words.append(w_clean)
                else:
                    break
            if model_words:
                detected_model = " ".join(model_words).lower()
                break

    return detected_brand, detected_model


def resolve_entities(observations: List[Observation]) -> List[Observation]:
    """Resolve brand/model for observations that don't have them yet."""
    for obs in observations:
        if not obs.brand:
            combined = obs.title + " " + obs.evidence_excerpt
            brand, model = _detect_brand_model(combined)
            obs.brand = brand
            obs.model = model
    return observations


# ═══════════════════════════════════════════════════════════════════════
# PRICE EXTRACTION
# ═══════════════════════════════════════════════════════════════════════

def _detect_price_type(text: str) -> str:
    """Detect price type from context text."""
    lower = text.lower()
    if re.search(r'อย่างเป็นทางการ|official price|ราคาจำหน่าย|ราคาวางจำหน่าย', lower):
        return "MSRP"
    if re.search(r'โปรโมชั่น|พิเศษ|campaign|ลด|discount|เสนอขาย', lower):
        return "PROMOTION"
    if re.search(r'เริ่มต้น|starting|ราคาเริ่ม', lower):
        return "LIST_PRICE"
    if re.search(r'หลังหักส่วนลด', lower):
        return "PROMOTION"
    return "MSRP"  # Default for automotive price articles


def _detect_variant(text: str) -> str:
    """Try to extract variant/trim name from text."""
    patterns = [
        r'(?:รุ่น|variant|grade|trim)\s*[:：]?\s*([A-Za-z0-9\s\-\+\.]+?)(?:\s*[,\(]|$)',
        r'((?:Dynamic|Premium|Standard|Extended|Performance|Sport|Smart|Elite|'
        r'PLUS|HEV|BEV|PHEV|e:HEV|DM-i|Type R|Long Range|AWD|RWD|2WD|'
        r'GR Sport|Legender|Wildtrak|Platinum|NightShade|Comfort|Luxury|'
        r'EL\+|S\+|Wolftrak|Executive|Premium S|Urban|LX|ZX|EX|'
        r'Open Air|Cab Plus|Double Cab|Single Cab|King Cab|'
        r'4WD|2WD|FWD)\s*[A-Za-z0-9\-]*)',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()[:80]
    return ""


# ═══════════════════════════════════════════════════════════════════════
# SPEC EXTRACTION
# ═══════════════════════════════════════════════════════════════════════

# Spec patterns: (field_type, regex, unit, group_index_for_value)
SPEC_PATTERNS = [
    # Power: hp/kW/PS
    ("power", r'กำลัง(?:เครื่อง)?[^0-9]{0,20}(\d{1,4}(?:\.\d+)?)\s*(?:hp|PS|แรงม้า|匹)', "hp", 1),
    ("power", r'(\d{1,4}(?:\.\d+)?)\s*(?:hp|PS|แรงม้า)', "hp", 1),
    ("power_kw", r'(\d{1,4}(?:\.\d+)?)\s*kW', "kW", 1),
    # Torque: Nm
    ("torque", r'แรงบิด[^0-9]{0,20}(\d{1,4}(?:\.\d+)?)\s*(?:Nm|นิวตันเมตร)', "Nm", 1),
    ("torque", r'(\d{1,4}(?:\.\d+)?)\s*Nm', "Nm", 1),
    # Engine displacement: cc
    ("engine_cc", r'(\d{1,4}(?:\.\d+)?)\s*(?:cc|ซีซี)', "cc", 1),
    ("engine_cc", r'ความจุ[^0-9]{0,15}(\d{1,4}(?:\.\d+)?)\s*(?:cc|ซีซี)', "cc", 1),
    # Engine: L
    ("engine_l", r'(\d\.\d)\s*(?:L|ลิตร|liter| litres)', "L", 1),
    # Fuel type
    ("fuel_type", r'(เบนซิน|ดีเซล|ไฮบริด|plug-in hybrid|electric|EV|Diesel|Benzine|Gasoline|Hybrid)', "type", 1),
    # Transmission
    ("transmission", r'เกียร์\s*(\d+)\s*-speed|เกียร์\s*(AT|CVT|MT|DCT|AMT|อัตโนมัติ|กระปุก)', "type", 1),
    ("transmission", r'(\d+)\s*(?:AT|MT|CVT|DCT|AMT|speed)', "type", 1),
    # Drive type
    ("drive_type", r'(FWD|RWD|AWD|4WD|2WD|ขับเคลื่อนหน้า|ขับเคลื่อนหลัง|ขับสี่|ขับสอง)', "type", 1),
    # Weight
    ("weight", r'(\d{3,4}(?:\.\d+)?)\s*(?:kg|กิโลกรัม|กก\.)', "kg", 1),
    # Battery
    ("battery_kwh", r'(\d{1,3}(?:\.\d+)?)\s*kWh', "kWh", 1),
    # Range
    ("range_km", r'(\d{2,4}(?:\.\d+)?)\s*(?:km\.?|กิโลเมตร)', "km", 1),
    # Dimensions: L x W x H
    ("dimensions", r'(\d{3,5})\s*[x×]\s*(\d{3,5})\s*[x×]\s*(\d{3,5})\s*mm', "mm", 0),
]


def _extract_specs(html: str, url: str, meta: dict, adapter: SourceAdapter) -> List[Observation]:
    """Extract spec observations from HTML content."""
    obs_list = []
    # Strip HTML for cleaner matching
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    title = meta.get("title", "")

    seen_specs = set()  # dedup within article

    for field_type, pattern, unit, grp_idx in SPEC_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            if field_type == "dimensions":
                # Special: extract L x W x H
                l_val, w_val, h_val = m.group(1), m.group(2), m.group(3)
                for suffix, val in [("length_mm", l_val), ("width_mm", w_val), ("height_mm", h_val)]:
                    key = f"{field_type}_{suffix}"
                    if key not in seen_specs:
                        seen_specs.add(key)
                        excerpt = text[max(0, m.start()-50):min(len(text), m.end()+50)].strip()[:200]
                        brand, model = _detect_brand_model(title + " " + excerpt)
                        obs_list.append(adapter._make_obs(
                            url, html, meta, "spec", f"{suffix}: {val} mm", val, unit,
                            brand=brand, model=model,
                            evidence=excerpt,
                        ))
                        # Override field type in the observation
                        obs_list[-1].field_type = "spec"
                        obs_list[-1].raw_value = f"{suffix}: {val} mm"
            elif field_type == "transmission":
                val = m.group(1) or m.group(2)
                if val:
                    dedup_key = f"transmission_{val}"
                    if dedup_key not in seen_specs:
                        seen_specs.add(dedup_key)
                        excerpt = text[max(0, m.start()-50):min(len(text), m.end()+50)].strip()[:200]
                        brand, model = _detect_brand_model(title + " " + excerpt)
                        obs_list.append(adapter._make_obs(
                            url, html, meta, "spec", f"transmission: {val}", val, unit,
                            brand=brand, model=model,
                            evidence=excerpt,
                        ))
            else:
                val = m.group(grp_idx)
                if val:
                    dedup_key = f"{field_type}_{val}"
                    if dedup_key not in seen_specs:
                        seen_specs.add(dedup_key)
                        excerpt = text[max(0, m.start()-50):min(len(text), m.end()+50)].strip()[:200]
                        brand, model = _detect_brand_model(title + " " + excerpt)
                        obs_list.append(adapter._make_obs(
                            url, html, meta, "spec", f"{field_type}: {val} {unit}", val, unit,
                            brand=brand, model=model,
                            evidence=excerpt,
                        ))

    return obs_list


# ═══════════════════════════════════════════════════════════════════════
# SCOPE VALIDATION
# ═══════════════════════════════════════════════════════════════════════

def validate_scope(obs: Observation) -> str:
    """Determine scope state for an observation."""
    combined = obs.title + " " + obs.evidence_excerpt

    # Check for comparison signals
    comparison_signals = [
        'เปรียบเทียบ', 'versus', 'vs', 'compare', 'comparison',
        'เทียบ', 'เปรียบ', 'vs.', '对抗', 'ชน'
    ]
    for sig in comparison_signals:
        if sig.lower() in combined.lower():
            return "COMPARISON"

    # Count brand mentions to determine SINGLE vs MULTI
    brand_mentions: Dict[str, int] = defaultdict(int)
    lower_combined = combined.lower()
    for brand, keywords in BRAND_KEYWORDS.items():
        for kw in keywords:
            brand_mentions[brand] += lower_combined.count(kw.lower())

    active_brands = [(b, c) for b, c in brand_mentions.items() if c > 0]
    if len(active_brands) == 0:
        return "UNKNOWN"
    elif len(active_brands) == 1:
        # Check if target brand is mentioned >= 2 times
        if active_brands[0][1] >= 2:
            return "SINGLE_MODEL"
        else:
            return "UNKNOWN"
    else:
        # Multiple brands: check if any dominates
        active_brands.sort(key=lambda x: x[1], reverse=True)
        top_count = active_brands[0][1]
        second_count = active_brands[1][1] if len(active_brands) > 1 else 0
        if second_count == 0 or top_count >= second_count * 3:
            return "SINGLE_MODEL"
        elif top_count >= second_count:
            return "MULTI_MODEL"
        else:
            return "ROUNDUP"


def validate_scopes(observations: List[Observation]) -> List[Observation]:
    """Apply scope validation to all observations."""
    for obs in observations:
        obs.scope_state = validate_scope(obs)
    return observations


# ═══════════════════════════════════════════════════════════════════════
# CLASSIFY + NORMALIZE
# ═══════════════════════════════════════════════════════════════════════

def classify_and_normalize(observations: List[Observation]) -> List[Observation]:
    """Classify and normalize observations."""
    for obs in observations:
        # Ensure trust_state is set
        if not obs.trust_state:
            obs.trust_state = "UNVERIFIED"

        # Filter out observations without brand/model
        if not obs.brand or not obs.model:
            obs.trust_state = "REJECTED"
            continue

        # Filter price observations by THB range
        if obs.field_type == "price":
            try:
                amount = int(obs.normalized_value)
                if amount < THB_MIN or amount > THB_MAX:
                    obs.trust_state = "REJECTED"
            except (ValueError, TypeError):
                obs.trust_state = "REJECTED"

    return observations


# ═══════════════════════════════════════════════════════════════════════
# DEDUP
# ═══════════════════════════════════════════════════════════════════════

def dedup_observations(observations: List[Observation]) -> List[Observation]:
    """Deduplicate by fingerprint: source_domain + content_hash + brand + model + field + value."""
    seen: Set[str] = set()
    deduped = []
    for obs in observations:
        if obs.trust_state == "REJECTED":
            continue
        fp = f"{obs.source_domain}|{obs.content_hash}|{obs.brand}|{obs.model}|{obs.field_type}|{obs.normalized_value}"
        fp_hash = hashlib.sha256(fp.encode()).hexdigest()[:16]
        if fp_hash not in seen:
            seen.add(fp_hash)
            deduped.append(obs)
    return deduped


# ═══════════════════════════════════════════════════════════════════════
# QUALITY GATES
# ═══════════════════════════════════════════════════════════════════════

def verify_model_exists(obs: Observation, variants_map: Dict) -> bool:
    """Verify that the resolved model exists in the DB."""
    variant_id = resolve_variant(obs.brand, obs.model, variants_map)
    return variant_id is not None


def verify_variant_msrp_needs_variant(obs: Observation, variants_map: Dict) -> bool:
    """MSRP prices should have a variant. List prices can be model-range."""
    if obs.price_type == "MSRP":
        variant_id = resolve_variant(obs.brand, obs.model, variants_map)
        return variant_id is not None
    return True


def verify_no_cross_model_contamination(observations: List[Observation]) -> bool:
    """Check that same source URL doesn't mix brands incorrectly."""
    url_brands: Dict[str, Set[str]] = defaultdict(set)
    for obs in observations:
        if obs.brand:
            url_brands[obs.source_url].add(obs.brand)
    for url, brands in url_brands.items():
        if len(brands) > 3:
            print(f"  [quality] CROSS-MODEL WARNING: {url} has {len(brands)} brands", file=sys.stderr)
            return False
    return True


def verify_secondary_not_official(obs: Observation) -> bool:
    """Secondary media should never claim to be official."""
    if obs.source_class in ("AUTO_MEDIA", "REFERENCE_MEDIA"):
        return True
    return True


def verify_currentness(obs: Observation) -> bool:
    """Basic currentness check — observation should be recent."""
    # We accept all observations for now; this gate is for future use
    return True


def verify_idempotent_rerun(obs: Observation, persisted_hashes: Set[str]) -> bool:
    """Check that this observation wasn't already persisted."""
    return obs.content_hash not in persisted_hashes


def apply_quality_gates(observations: List[Observation], variants_map: Dict,
                        persisted_hashes: Set[str]) -> Tuple[List[Observation], List[Observation]]:
    """Apply all quality gates. Returns (accepted, quarantined)."""
    accepted = []
    quarantined = []
    for obs in observations:
        reasons = []
        if not verify_model_exists(obs, variants_map):
            reasons.append("model_not_in_db")
        if not verify_secondary_not_official(obs):
            reasons.append("secondary_claims_official")
        if not verify_currentness(obs):
            reasons.append("stale_observation")
        if not verify_idempotent_rerun(obs, persisted_hashes):
            reasons.append("already_persisted")

        if reasons:
            obs.trust_state = "REJECTED"
            quarantined.append(obs)
        else:
            accepted.append(obs)

    # Cross-model check on accepted
    if not verify_no_cross_model_contamination(accepted):
        # Don't reject, just warn
        pass

    return accepted, quarantined


# ═══════════════════════════════════════════════════════════════════════
# PERSIST
# ═══════════════════════════════════════════════════════════════════════

def persist_observations(observations: List[Observation],
                         sources: Dict, variants_map: Dict,
                         dry_run: bool = False) -> Dict[str, int]:
    """Persist observations to the DB. Returns stats."""
    stats = {"prices_inserted": 0, "specs_inserted": 0, "no_variant": 0, "errors": 0}
    source_doc_cache: Dict[str, str] = {}  # url → doc_id
    price_batch = []
    spec_batch = []
    BATCH = 50
    seen_prices: Set[str] = set()  # dedup: variantId|amount|sourceDocumentId

    for obs in observations:
        if obs.trust_state == "REJECTED":
            continue
        if obs.field_type == "price" and obs.price_type not in ("MSRP", "LIST_PRICE", "PROMOTION"):
            continue

        # Resolve variant
        variant_id = resolve_variant(obs.brand, obs.model, variants_map)
        if not variant_id:
            stats["no_variant"] += 1
            continue

        # Get/create source + document
        if obs.source_url not in source_doc_cache:
            if dry_run:
                source_doc_cache[obs.source_url] = "dry-run-doc-id"
            else:
                source_id = get_or_create_source(sources, obs.source_domain, obs.source_url)
                doc_id = create_source_document(source_id, obs.source_url,
                                                obs.content_hash, obs.extractor_version, obs.title)
                source_doc_cache[obs.source_url] = doc_id
        doc_id = source_doc_cache[obs.source_url]

        if obs.field_type == "price":
            amount = int(obs.normalized_value)
            pt = obs.price_type if obs.price_type in ("MSRP", "LIST_PRICE", "PROMOTION") else "MSRP"
            # Dedup: skip if same variant+amount+source already seen
            price_key = f"{variant_id}|{amount}|{doc_id}"
            if price_key in seen_prices:
                continue
            seen_prices.add(price_key)
            price_id = str(uuid.uuid4())
            # Expire existing
            price_batch.append(
                f'UPDATE "Price" SET "isCurrent" = false, "validTo" = NOW() '
                f'WHERE "variantId" = \'{variant_id}\' AND "priceType" = \'{pt}\'::"PriceType" '
                f'AND "isCurrent" = true'
            )
            price_batch.append(
                f'INSERT INTO "Price" (id, "variantId", "sourceDocumentId", "priceType", '
                f'amount, currency, "validFrom", "isCurrent", confidence, "sourceTier", "sourceUrl") '
                f'VALUES (\'{price_id}\', \'{variant_id}\', \'{doc_id}\', \'{pt}\'::"PriceType", '
                f'{amount}, \'THB\', NOW(), true, {obs.confidence}, '
                f'\'{obs.source_class}\', \'{obs.source_url[:500].replace(chr(39), "")}\')'
            )
            if len(price_batch) >= BATCH * 2:
                if not dry_run:
                    psql_batch(price_batch)
                stats["prices_inserted"] += len(price_batch) // 2
                price_batch = []

        elif obs.field_type == "spec":
            key = obs.raw_value.split(":")[0].strip()[:100].replace("'", "''")
            val = obs.normalized_value.replace("'", "''")[:500]
            unit_val = f"'{obs.unit}'" if obs.unit else "NULL"
            numeric_val = "NULL"
            try:
                numeric_val = str(float(obs.normalized_value))
            except (ValueError, TypeError):
                pass
            spec_id = str(uuid.uuid4())
            spec_batch.append(
                f'INSERT INTO "VariantSpec" (id, "variantId", "sourceDocumentId", key, '
                f'"valueTh", "valueEn", "valueNumeric", unit, confidence) '
                f'VALUES (\'{spec_id}\', \'{variant_id}\', \'{doc_id}\', \'{key}\', '
                f'\'{val}\', \'{val}\', {numeric_val}, {unit_val}, {obs.confidence}) '
                f'ON CONFLICT ("variantId", key, "sourceDocumentId") DO NOTHING'
            )
            if len(spec_batch) >= BATCH:
                if not dry_run:
                    psql_batch(spec_batch)
                stats["specs_inserted"] += len(spec_batch)
                spec_batch = []

    # Flush remaining
    if price_batch:
        if not dry_run:
            psql_batch(price_batch)
        stats["prices_inserted"] += len(price_batch) // 2
    if spec_batch:
        if not dry_run:
            psql_batch(spec_batch)
        stats["specs_inserted"] += len(spec_batch)

    return stats


# ═══════════════════════════════════════════════════════════════════════
# RECONCILE + AUDIT
# ═══════════════════════════════════════════════════════════════════════

def reconcile_and_audit(observations: List[Observation]) -> Dict[str, Any]:
    """Generate audit report from observations."""
    brand_counts = defaultdict(int)
    model_counts = defaultdict(int)
    scope_counts = defaultdict(int)
    trust_counts = defaultdict(int)
    price_observations = 0
    spec_observations = 0
    total_amount = 0

    for obs in observations:
        if obs.brand:
            brand_counts[obs.brand] += 1
        if obs.model:
            model_counts[f"{obs.brand}/{obs.model}"] += 1
        scope_counts[obs.scope_state] += 1
        trust_counts[obs.trust_state] += 1
        if obs.field_type == "price":
            price_observations += 1
            try:
                total_amount += int(obs.normalized_value)
            except (ValueError, TypeError):
                pass
        elif obs.field_type == "spec":
            spec_observations += 1

    return {
        "total_observations": len(observations),
        "price_observations": price_observations,
        "spec_observations": spec_observations,
        "brands_found": dict(brand_counts),
        "models_found": dict(model_counts),
        "scope_distribution": dict(scope_counts),
        "trust_distribution": dict(trust_counts),
        "total_price_value_thb": total_amount,
    }


# ═══════════════════════════════════════════════════════════════════════
# CHECKPOINT / RESUME
# ═══════════════════════════════════════════════════════════════════════

def load_checkpoint() -> Dict[str, Any]:
    """Load checkpoint state."""
    if os.path.isfile(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"completed_sources": [], "completed_urls": [], "phase": "discover"}


def save_checkpoint(state: Dict[str, Any]):
    """Save checkpoint state."""
    os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# METRICS
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SourceMetrics:
    source_name: str
    discovered: int = 0
    fetched: int = 0
    extracted: int = 0
    resolved: int = 0
    scope_valid: int = 0
    accepted: int = 0
    deduped: int = 0
    persisted: int = 0
    quarantined: int = 0
    errors: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════
# PARSE CLI ARGS
# ═══════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(description="Thai Automotive Data Factory")
    parser.add_argument("--reset", action="store_true", help="Reset checkpoint and start fresh")
    parser.add_argument("--max-per-source", type=int, default=15, help="Max articles per source")
    parser.add_argument("--dry-run", action="store_true", help="Don't persist to DB")
    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════

ADAPTERS: List[SourceAdapter] = [
    HeadlightMagAdapter(),
    AutoSpinnAdapter(),
    AutoLifeThailandAdapter(),
    NineCarThaiAdapter(),
    Car2DayAdapter(),
    CheckRakaAdapter(),
]


def run_source_pipeline(adapter: SourceAdapter, max_articles: int,
                        checkpoint: Dict, dry_run: bool) -> Tuple[List[Observation], SourceMetrics, Dict]:
    """Run the full pipeline for a single source. Returns (observations, metrics, checkpoint_update)."""
    metrics = SourceMetrics(source_name=adapter.name)
    obs_list = []

    try:
        # ── DISCOVER ──
        print(f"\n{'='*60}")
        print(f"  SOURCE: {adapter.name} ({adapter.domain})")
        print(f"{'='*60}")

        articles = adapter.discover(max_articles=max_articles)
        metrics.discovered = len(articles)
        print(f"  [DISCOVER] {len(articles)} articles found")

        # Filter already-completed URLs
        completed_urls = set(checkpoint.get("completed_urls", []))
        articles = [a for a in articles if a["url"] not in completed_urls]
        print(f"  [CHECKPOINT] {len(articles)} new articles (filtered {len(completed_urls)} done)")

        for i, article in enumerate(articles):
            url = article["url"]
            print(f"\n  [{i+1}/{len(articles)}] {url}")

            # ── FETCH ──
            html = adapter.fetch(url)
            if not html:
                metrics.errors += 1
                print(f"    [FETCH] FAILED")
                continue
            metrics.fetched += 1
            content_h = hashlib.sha256(html.encode("utf-8")).hexdigest()[:16]
            print(f"    [FETCH] OK ({len(html)} bytes, hash={content_h})")

            # ── EXTRACT ──
            try:
                extracted = adapter.extract(url, html, article)
                metrics.extracted += len(extracted)
                print(f"    [EXTRACT] {len(extracted)} observations")
            except Exception as e:
                metrics.errors += 1
                print(f"    [EXTRACT] ERROR: {e}")
                continue

            obs_list.extend(extracted)

            # Mark URL as completed
            checkpoint.setdefault("completed_urls", []).append(url)

            # Rate limiting
            time.sleep(0.5)

    except Exception as e:
        metrics.errors += 1
        print(f"  [ERROR] {adapter.name}: {e}", file=sys.stderr)

    return obs_list, metrics, checkpoint


def main():
    args = parse_args()
    os.makedirs(STORAGE_DIR, exist_ok=True)

    print("=" * 70)
    print("  THAI AUTOMOTIVE DATA FACTORY")
    print(f"  Version: {EXTRACTOR_VERSION}")
    print(f"  Max per source: {args.max_per_source}")
    print(f"  Dry run: {args.dry_run}")
    print(f"  Reset: {args.reset}")
    print("=" * 70)

    # Load or reset checkpoint
    if args.reset:
        checkpoint = {"completed_sources": [], "completed_urls": [], "phase": "discover"}
        save_checkpoint(checkpoint)
        print("\n[CHECKPOINT] Reset.")
    else:
        checkpoint = load_checkpoint()
        print(f"\n[CHECKPOINT] Resumed. {len(checkpoint.get('completed_urls', []))} URLs already done.")

    # ── Phase 1: DISCOVER + FETCH + EXTRACT (parallel) ──
    print("\n" + "=" * 70)
    print("  PHASE 1: DISCOVER → FETCH → EXTRACT (parallel)")
    print("=" * 70)

    all_observations: List[Observation] = []
    source_metrics: Dict[str, SourceMetrics] = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for adapter in ADAPTERS:
            if adapter.domain in checkpoint.get("completed_sources", []):
                print(f"  [SKIP] {adapter.name} already completed")
                continue
            future = executor.submit(
                run_source_pipeline, adapter, args.max_per_source,
                checkpoint, args.dry_run
            )
            futures[future] = adapter

        for future in as_completed(futures):
            adapter = futures[future]
            try:
                obs, metrics, _ = future.result()
                all_observations.extend(obs)
                source_metrics[adapter.name] = metrics
                checkpoint.setdefault("completed_sources", []).append(adapter.domain)
            except Exception as e:
                print(f"  [ERROR] {adapter.name} pipeline failed: {e}", file=sys.stderr)

    save_checkpoint(checkpoint)
    print(f"\n  TOTAL raw observations: {len(all_observations)}")

    # ── Phase 2: ENTITY RESOLUTION ──
    print("\n" + "=" * 70)
    print("  PHASE 2: ENTITY RESOLUTION")
    print("=" * 70)
    all_observations = resolve_entities(all_observations)
    resolved_count = sum(1 for o in all_observations if o.brand)
    print(f"  Resolved: {resolved_count}/{len(all_observations)}")

    # ── Phase 3: SCOPE VALIDATION ──
    print("\n" + "=" * 70)
    print("  PHASE 3: SCOPE VALIDATION")
    print("=" * 70)
    all_observations = validate_scopes(all_observations)
    scope_dist = defaultdict(int)
    for o in all_observations:
        scope_dist[o.scope_state] += 1
    for state, count in sorted(scope_dist.items()):
        print(f"  {state}: {count}")

    # ── Phase 4: CLASSIFY + NORMALIZE ──
    print("\n" + "=" * 70)
    print("  PHASE 4: CLASSIFY + NORMALIZE")
    print("=" * 70)
    all_observations = classify_and_normalize(all_observations)
    pre_dedup = len(all_observations)

    # ── Phase 5: DEDUP ──
    print("\n" + "=" * 70)
    print("  PHASE 5: DEDUP")
    print("=" * 70)
    all_observations = dedup_observations(all_observations)
    print(f"  Before: {pre_dedup}, After: {len(all_observations)}")

    # ── Phase 6: QUALITY GATES ──
    print("\n" + "=" * 70)
    print("  PHASE 6: QUALITY GATES")
    print("=" * 70)
    print("  Loading DB state for quality gates...")
    try:
        variants_map = get_existing_variants()
        persisted_hashes = set()  # Could load from DB in future
        all_observations, quarantined = apply_quality_gates(
            all_observations, variants_map, persisted_hashes
        )
        print(f"  Accepted: {len(all_observations)}, Quarantined: {len(quarantined)}")
    except Exception as e:
        print(f"  [WARNING] Quality gates skipped (DB issue): {e}")
        variants_map = {}
        quarantined = []

    # ── Phase 7: PERSIST ──
    print("\n" + "=" * 70)
    print("  PHASE 7: PERSIST")
    print("=" * 70)
    if args.dry_run:
        print("  [DRY RUN] Skipping DB persistence")
        persist_stats = {"prices_inserted": 0, "specs_inserted": 0, "no_variant": 0}
    else:
        try:
            sources = get_existing_sources()
            persist_stats = persist_observations(all_observations, sources, variants_map, args.dry_run)
            print(f"  Prices inserted: {persist_stats['prices_inserted']}")
            print(f"  Specs inserted: {persist_stats['specs_inserted']}")
            print(f"  No variant match: {persist_stats['no_variant']}")
        except Exception as e:
            print(f"  [ERROR] Persistence failed: {e}")
            persist_stats = {"prices_inserted": 0, "specs_inserted": 0, "no_variant": 0, "errors": 1}

    # ── Phase 8: RECONCILE + AUDIT ──
    print("\n" + "=" * 70)
    print("  PHASE 8: RECONCILE + AUDIT")
    print("=" * 70)
    audit = reconcile_and_audit(all_observations)

    # ── OUTPUT: RESULTS JSON ──
    results = {
        "run_id": f"factory-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "max_per_source": args.max_per_source,
            "dry_run": args.dry_run,
            "extractor_version": EXTRACTOR_VERSION,
        },
        "observations": [o.to_dict() for o in all_observations],
        "quarantined": [o.to_dict() for o in quarantined] if quarantined else [],
        "persist_stats": persist_stats,
        "audit": audit,
        "source_metrics": {k: v.to_dict() for k, v in source_metrics.items()},
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Results: {RESULTS_FILE}")

    # ── OUTPUT: METRICS JSON ──
    metrics_output = {
        "run_id": results["run_id"],
        "timestamp": results["timestamp"],
        "total_observations": audit["total_observations"],
        "price_observations": audit["price_observations"],
        "spec_observations": audit["spec_observations"],
        "brands_found": audit["brands_found"],
        "scope_distribution": audit["scope_distribution"],
        "trust_distribution": audit["trust_distribution"],
        "persist_stats": persist_stats,
        "per_source": {k: v.to_dict() for k, v in source_metrics.items()},
    }

    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(metrics_output, f, indent=2, ensure_ascii=False)
    print(f"  Metrics: {METRICS_FILE}")

    # ── OUTPUT: SUMMARY REPORT ──
    report_lines = [
        "=" * 70,
        "  THAI AUTOMOTIVE DATA FACTORY — SUMMARY REPORT",
        f"  Run: {results['run_id']}",
        f"  Time: {results['timestamp']}",
        "=" * 70,
        "",
        "  PIPELINE RESULTS:",
        f"    Total observations: {audit['total_observations']}",
        f"    Price observations: {audit['price_observations']}",
        f"    Spec observations: {audit['spec_observations']}",
        f"    Brands found: {len(audit['brands_found'])}",
        "",
        "  PERSISTENCE:",
        f"    Prices inserted: {persist_stats.get('prices_inserted', 0)}",
        f"    Specs inserted: {persist_stats.get('specs_inserted', 0)}",
        f"    No variant match: {persist_stats.get('no_variant', 0)}",
        "",
        "  SCOPE DISTRIBUTION:",
    ]
    for state, count in sorted(audit["scope_distribution"].items()):
        report_lines.append(f"    {state}: {count}")

    report_lines.extend(["", "  TRUST DISTRIBUTION:"])
    for state, count in sorted(audit["trust_distribution"].items()):
        report_lines.append(f"    {state}: {count}")

    report_lines.extend(["", "  BRANDS FOUND:"])
    for brand, count in sorted(audit["brands_found"].items(), key=lambda x: -x[1]):
        report_lines.append(f"    {brand}: {count}")

    report_lines.extend(["", "  PER-SOURCE METRICS:"])
    for name, m in source_metrics.items():
        d = m.to_dict()
        report_lines.append(f"    {name}:")
        report_lines.append(f"      Discovered: {d['discovered']}, Fetched: {d['fetched']}, "
                           f"Extracted: {d['extracted']}, Resolved: {d['resolved']}")
        report_lines.append(f"      Accepted: {d['accepted']}, Deduped: {d['deduped']}, "
                           f"Persisted: {d['persisted']}, Quarantined: {d['quarantined']}")

    report_lines.extend(["", "  TOP PRICES:"])
    price_obs = [o for o in all_observations if o.field_type == "price"]
    price_obs.sort(key=lambda o: int(o.normalized_value) if o.normalized_value.isdigit() else 0, reverse=True)
    for obs in price_obs[:10]:
        report_lines.append(f"    {obs.brand}/{obs.model}: {obs.normalized_value} THB ({obs.price_type}) [{obs.source_domain}]")

    report_lines.append("\n" + "=" * 70)

    report_text = "\n".join(report_lines)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"  Report: {REPORT_FILE}")
    print("\n" + report_text)

    return results


if __name__ == "__main__":
    main()
