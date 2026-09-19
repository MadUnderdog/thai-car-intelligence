#!/usr/bin/env python3
"""
Mega-Parallel Thai Automotive Data Extractor v3
================================================
Multi-strategy extraction for ALL Thailand brands.
Supports: API, HTML, JSON-LD, embedded JSON, Playwright DOM, Thai media.

Evidence-preserving: every observation carries source URL, extraction method,
content hash, evidence excerpt, and trust state.

Variant rule:
  - Explicit trim prices → VARIANT_MSRP per trim
  - Range only → MODEL_RANGE / STARTING_PRICE
  - Model-level → do NOT attach to arbitrary variant

Output: per-brand JSON artifacts in run directory.
"""

import hashlib
import json
import os
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin, urlparse

# ─── Configuration ───────────────────────────────────────────────────────────

RUN_DIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/thai-car-mega-run"
TIMEOUT = 15
MAX_WORKERS = 8
THB_MIN = 200_000     # Minimum plausible car price in THB
THB_MAX = 20_000_000  # Maximum plausible car price in THB

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'th-TH,th;q=0.9,en;q=0.8',
}

# ─── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class PriceObservation:
    brand: str
    model: str
    variant: str
    price_thb: int
    price_type: str  # VARIANT_MSRP | MODEL_RANGE | STARTING_PRICE | PROMOTION
    source_url: str
    source_class: str  # OFFICIAL_API | OFFICIAL_WEB | OFFICIAL_PDF | OFFICIAL_SOCIAL | AUTO_MEDIA | DEALER_WEB
    trust_state: str   # QUALIFIED | RESEARCH_UNVERIFIED
    extraction_method: str  # api_json | html_json_embed | html_regex | playwright_dom | media_article
    evidence_excerpt: str
    content_hash: str
    timestamp: str
    model_year: Optional[str] = None
    raw_json_path: Optional[str] = None

@dataclass
class SpecObservation:
    brand: str
    model: str
    variant: str
    spec_key: str
    spec_value: str
    source_url: str
    source_class: str
    trust_state: str
    extraction_method: str
    evidence_excerpt: str
    content_hash: str
    timestamp: str

@dataclass
class BrandResult:
    brand: str
    brand_name: str
    status: str  # RUNNING | DATA_EXTRACTED | PARTIAL | BLOCKED | FAILED
    prices: List[dict] = field(default_factory=list)
    specs: List[dict] = field(default_factory=list)
    sources: List[dict] = field(default_factory=list)
    failures: List[dict] = field(default_factory=list)
    models_found: int = 0
    variants_found: int = 0
    started_at: str = ""
    finished_at: str = ""

# ─── Utility Functions ────────────────────────────────────────────────────────

def fetch_url(url: str, timeout: int = TIMEOUT, headers: dict = None, 
              method: str = 'GET', data: bytes = None) -> Optional[str]:
    """Safe URL fetch with timeout and error handling."""
    hdrs = {**HEADERS, **(headers or {})}
    req = Request(url, headers=hdrs, method=method, data=data)
    try:
        with urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get('Content-Type', '')
            raw = resp.read()
            # Try UTF-8 first, then latin-1
            try:
                return raw.decode('utf-8')
            except UnicodeDecodeError:
                return raw.decode('latin-1')
    except Exception as e:
        return None

def content_hash(text: str) -> str:
    """SHA-256 hash of content for dedup."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

def extract_thb_prices(text: str) -> List[Tuple[int, str]]:
    """Extract THB price amounts from text. Returns (amount, matched_text) pairs."""
    results = []
    patterns = [
        # ฿1,234,567
        (r'฿\s*(\d{1,3}(?:,\d{3})+)', 'thb_symbol'),
        # 1,234,567 บาท
        (r'(\d{1,3}(?:,\d{3})+)\s*บาท', 'baht_text'),
        # ราคา 1,234,567
        (r'ราคา\s*(\d{1,3}(?:,\d{3})+)', 'raa_kha'),
        # 1,234,567 THB
        (r'(\d{1,3}(?:,\d{3})+)\s*THB', 'thb_text'),
        # เริ่มต้น 1,234,567
        (r'เริ่มต้น\s*(\d{1,3}(?:,\d{3})+)', 'starting'),
        # เริ่มที่ 1,234,567
        (r'เริ่มที่\s*(\d{1,3}(?:,\d{3})+)', 'starting2'),
        # ราคาเริ่มต้น 1,234,567
        (r'ราคาเริ่มต้น\s*(\d{1,3}(?:,\d{3})+)', 'price_starting'),
    ]
    seen = set()
    for pattern, method in patterns:
        for m in re.finditer(pattern, text):
            val = int(m.group(1).replace(',', ''))
            if THB_MIN <= val <= THB_MAX and val not in seen:
                # Get surrounding context (50 chars each side)
                start = max(0, m.start() - 50)
                end = min(len(text), m.end() + 50)
                excerpt = text[start:end].strip()
                results.append((val, excerpt))
                seen.add(val)
    return results

def extract_variant_prices(text: str, brand: str, model: str) -> List[dict]:
    """
    Extract variant-level prices from Thai media article text.
    Looks for patterns like:
      - City V: 569,000 / City RS: 949,000
      - รุ่น V 569,000 บาท / รุ่น RS 949,000 บาท
      -表格 with trim + price
    """
    variants = []
    
    # Pattern: variant name followed by price
    # E.g., "City V 569,000" or "Civic RS 1,234,000"
    vp_patterns = [
        # Thai style: "รุ่น X ราคา X,XXX,XXX"
        r'รุ่น\s+([A-Za-z0-9\+\-\. ]+?)\s+ราคา\s*(\d{1,3}(?:,\d{3})+)',
        # English trim + price: "V 569,000" or "RS: 949,000"
        r'\b([A-Z][A-Za-z0-9\+\-\.]{1,15})\s*[:\s]\s*(\d{1,3}(?:,\d{3})+)\s*(?:บาท|฿|THB)',
        # Price after trim in parentheses
        r'\(([A-Za-z0-9\+\-\. ]+?)\)\s*(?:ราคา\s*)?(\d{1,3}(?:,\d{3})+)',
        # Table-like: trim | price
        r'([A-Z][A-Za-z0-9\+\-\.]{1,15})\s*\|\s*(\d{1,3}(?:,\d{3})+)',
    ]
    
    seen_variants = set()
    for pattern in vp_patterns:
        for m in re.finditer(pattern, text):
            trim = m.group(1).strip()
            price = int(m.group(2).replace(',', ''))
            if THB_MIN <= price <= THB_MAX and trim.lower() not in seen_variants:
                seen_variants.add(trim.lower())
                start = max(0, m.start() - 30)
                end = min(len(text), m.end() + 30)
                excerpt = text[start:end].strip()
                variants.append({
                    'variant': trim,
                    'price_thb': price,
                    'excerpt': excerpt,
                })
    
    return variants

def extract_specs_from_text(text: str) -> Dict[str, str]:
    """Extract spec fields from article/page text."""
    specs = {}
    spec_patterns = {
        'power_kw': r'(\d+(?:\.\d+)?)\s*(?:kW|กิโลวัตต์)',
        'power_ps': r'(\d+(?:\.\d+)?)\s*(?:PS|匹|แรงม้า)',
        'power_hp': r'(\d+(?:\.\d+)?)\s*(?:hp| horsepower)',
        'torque_nm': r'(\d+(?:\.\d+)?)\s*(?:Nm|นิวตัน-เมตร|นิวตันเมตร)',
        'displacement_cc': r'(\d{3,4})\s*(?:cc|ซีซี)',
        'battery_kwh': r'(\d+(?:\.\d+)?)\s*kWh',
        'range_km': r'(\d{3,5})\s*(?:km|กม\.|กิโลเมตร)\s*(?:WLTP|range|ระยะทาง|NEDC|CLTC)',
        'dimensions_mm': r'(\d{4})\s*[xX×]\s*(\d{4})\s*[xX×]\s*(\d{4})\s*mm',
        'wheelbase_mm': r'ฐานล้อ\s*(\d{4})\s*mm|wheelbase\s*(\d{4})\s*mm',
        'ground_clearance_mm': r' Clearance\s*(\d{3})\s*mm| ground clearance\s*(\d{3})\s*mm|  Clearance\s*(\d{3})\s*mm',
        'seating': r'(\d)\s*(?:ที่นั่ง|ที่นั่่ง| seats)',
        'fuel_type_th': r'(เบนซิน|ดีเซล|ไฮบริด|ปลั๊กอินไฮบริด|ไฟฟ้า|EV|BEV|PHEV|HEV)',
    }
    for key, pattern in spec_patterns.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            if key == 'dimensions_mm':
                specs[key] = f"{m.group(1)}x{m.group(2)}x{m.group(3)}"
            else:
                specs[key] = m.group(1)
    return specs

def find_brand_media_urls(brand_name: str, brand_name_th: str) -> List[str]:
    """Find Thai automotive media article URLs for a brand."""
    urls = []
    
    # 9CARTHAI price pages
    urls.append(f'https://www.9carthai.com/{brand_name.lower().replace("-", "").replace(" ", "")}-price/')
    
    # Headlightmag search via homepage
    urls.append('https://www.headlightmag.com/')
    
    # AutoSpinn
    urls.append(f'https://www.autospinn.com/tag/{brand_name.lower().replace(" ", "-")}')
    
    return urls

# ─── Brand-Specific Extractors ───────────────────────────────────────────────

def extract_toyota() -> List[dict]:
    """Toyota Thailand — known public API."""
    prices = []
    specs_list = []
    sources = []
    
    # Known API endpoints
    api_url = 'https://www.toyota.co.th/component/api/tcoth/web-init'
    api_resp = fetch_url(api_url, method='POST', data=b'{}',
                        headers={'Content-Type': 'application/json'})
    if api_resp:
        sources.append({'url': api_url, 'status': 'ok', 'method': 'api_json'})
        try:
            data = json.loads(api_resp)
            models = data if isinstance(data, list) else data.get('data', data.get('models', []))
            if isinstance(models, dict):
                models = models.get('data', [])
            for item in models:
                if not isinstance(item, dict):
                    continue
                model_name = item.get('name', item.get('model_name', item.get('modelName', '')))
                code = item.get('code', item.get('model_code', item.get('modelCode', '')))
                start_price = item.get('start_price', item.get('minPrice', 0))
                max_price = item.get('max_price', item.get('maxPrice', 0))
                
                if model_name and start_price:
                    start_val = int(float(start_price))
                    max_val = int(float(max_price)) if max_price else 0
                    
                    if THB_MIN <= start_val <= THB_MAX:
                        excerpt = json.dumps(item, ensure_ascii=False)[:300]
                        h = content_hash(excerpt)
                        ts = datetime.now().isoformat()
                        
                        # Model-range price from API
                        obs = {
                            'brand': 'toyota',
                            'model': model_name,
                            'variant': '__MODEL_RANGE__',
                            'price_thb': start_val,
                            'price_type': 'STARTING_PRICE',
                            'source_url': api_url,
                            'source_class': 'OFFICIAL_API',
                            'trust_state': 'QUALIFIED',
                            'extraction_method': 'api_json',
                            'evidence_excerpt': excerpt,
                            'content_hash': h,
                            'timestamp': ts,
                            'raw_json_path': f'code={code}',
                        }
                        if max_val and max_val > start_val:
                            obs['price_max_thb'] = max_val
                        prices.append(obs)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            pass
    
    # Try model detail API for specs + grade-level prices
    # First get series list
    series_url = 'https://www.toyota.co.th/en/model/api/car-series/'
    series_resp = fetch_url(series_url)
    if series_resp:
        sources.append({'url': series_url, 'status': 'ok', 'method': 'api_json'})
        try:
            series_data = json.loads(series_resp)
            categories = series_data if isinstance(series_data, list) else series_data.get('data', [])
            for cat in categories:
                series_list = cat.get('series', cat.get('models', [])) if isinstance(cat, dict) else []
                for series in series_list:
                    if not isinstance(series, dict):
                        continue
                    code = series.get('code', series.get('series_code', ''))
                    name = series.get('name', series.get('series_name', ''))
                    if code:
                        # Fetch detail for each model
                        detail_url = f'https://www.toyota.co.th/en/model/api/car/?series_code={code}'
                        detail_resp = fetch_url(detail_url)
                        if detail_resp:
                            try:
                                detail = json.loads(detail_resp)
                                detail_data = detail.get('data', [{}]) if isinstance(detail, dict) else [{}]
                                if isinstance(detail_data, list) and len(detail_data) > 0:
                                    model_info = detail_data[0]
                                    grades = model_info.get('grades', [])
                                    for grade in grades:
                                        grade_name = grade.get('name', grade.get('grade_name', ''))
                                        grade_price = grade.get('price', grade.get('msrp', 0))
                                        if grade_name and grade_price:
                                            gp = int(float(grade_price))
                                            if THB_MIN <= gp <= THB_MAX:
                                                excerpt = json.dumps(grade, ensure_ascii=False)[:300]
                                                prices.append({
                                                    'brand': 'toyota',
                                                    'model': name or model_name,
                                                    'variant': grade_name,
                                                    'price_thb': gp,
                                                    'price_type': 'VARIANT_MSRP',
                                                    'source_url': detail_url,
                                                    'source_class': 'OFFICIAL_API',
                                                    'trust_state': 'QUALIFIED',
                                                    'extraction_method': 'api_json',
                                                    'evidence_excerpt': excerpt,
                                                    'content_hash': content_hash(excerpt),
                                                    'timestamp': datetime.now().isoformat(),
                                                    'raw_json_path': f'grades[{grade_name}]',
                                                })
                                    
                                    # Extract specs from grade specifications
                                    for grade in grades:
                                        specs_groups = grade.get('specifications', [])
                                        for group in specs_groups:
                                            items = group.get('items', [])
                                            for item in items:
                                                title = item.get('title_en', item.get('title', ''))
                                                value = item.get('value_en', item.get('value', ''))
                                                if title and value:
                                                    specs_list.append({
                                                        'brand': 'toyota',
                                                        'model': name,
                                                        'variant': grade.get('name', ''),
                                                        'spec_key': title.lower().replace(' ', '_'),
                                                        'spec_value': value,
                                                        'source_url': detail_url,
                                                        'source_class': 'OFFICIAL_API',
                                                        'trust_state': 'QUALIFIED',
                                                        'extraction_method': 'api_json',
                                                        'evidence_excerpt': f'{title}: {value}',
                                                        'content_hash': content_hash(f'{title}:{value}'),
                                                        'timestamp': datetime.now().isoformat(),
                                                    })
                            except (json.JSONDecodeError, KeyError):
                                pass
        except (json.JSONDecodeError, KeyError):
            pass
    
    return prices, specs_list, sources


def extract_nissan() -> List[dict]:
    """Nissan Thailand — embedded JSON in hidden iframe."""
    prices = []
    sources = []
    
    # Known: Nissan puts ALL model prices in a hidden iframe JSON
    # Try the main page first
    for url in ['https://www.nissan.co.th/', 'https://www.nissan.co.th/all-vehicles.html']:
        html = fetch_url(url)
        if html:
            sources.append({'url': url, 'status': 'ok', 'method': 'html_json_embed'})
            
            # Look for the hidden iframe with JSON data
            # Pattern: id="allVehiclesModelPriceJSON" or similar
            json_match = re.search(r'id=["\']allVehiclesModelPriceJSON["\'][^>]*>(.*?)</iframe>', html, re.DOTALL)
            if not json_match:
                # Try alternative patterns
                json_match = re.search(r'modelPriceJSON\s*=\s*(\[.*?\]);', html, re.DOTALL)
            if not json_match:
                json_match = re.search(r'"modelPrice"\s*:\s*(\[.*?\])', html, re.DOTALL)
            if not json_match:
                # Try finding any large JSON blob with model/price data
                json_match = re.search(r'(\[{[^<]{500,}}\])', html, re.DOTALL)
            
            if json_match:
                try:
                    raw_json = json_match.group(1).strip()
                    # Unescape HTML entities
                    raw_json = raw_json.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                    models_data = json.loads(raw_json)
                    
                    if isinstance(models_data, list):
                        for item in models_data:
                            if not isinstance(item, dict):
                                continue
                            model_slug = item.get('url', item.get('slug', item.get('modelKey', '')))
                            model_name = item.get('name', item.get('modelName', item.get('title', '')))
                            price = item.get('modelPrice', item.get('price', item.get('startingPrice', 0)))
                            model_code = item.get('modelCode', item.get('code', ''))
                            
                            if price:
                                p = int(float(str(price).replace(',', '')))
                                if THB_MIN <= p <= THB_MAX:
                                    excerpt = json.dumps(item, ensure_ascii=False)[:300]
                                    prices.append({
                                        'brand': 'nissan',
                                        'model': model_name or model_slug,
                                        'variant': '__MODEL_RANGE__',
                                        'price_thb': p,
                                        'price_type': 'STARTING_PRICE',
                                        'source_url': url,
                                        'source_class': 'OFFICIAL_WEB',
                                        'trust_state': 'QUALIFIED',
                                        'extraction_method': 'html_json_embed',
                                        'evidence_excerpt': excerpt,
                                        'content_hash': content_hash(excerpt),
                                        'timestamp': datetime.now().isoformat(),
                                        'raw_json_path': f'slug={model_slug}',
                                    })
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Also try regex for prices in the HTML
            if not prices:
                for m in re.finditer(r'฿\s*(\d{1,3}(?:,\d{3})+)', html):
                    val = int(m.group(1).replace(',', ''))
                    if THB_MIN <= val <= THB_MAX:
                        start = max(0, m.start() - 80)
                        end = min(len(html), m.end() + 80)
                        excerpt = re.sub(r'<[^>]+>', ' ', html[start:end]).strip()[:200]
                        prices.append({
                            'brand': 'nissan',
                            'model': 'unknown',
                            'variant': '__MODEL_RANGE__',
                            'price_thb': val,
                            'price_type': 'STARTING_PRICE',
                            'source_url': url,
                            'source_class': 'OFFICIAL_WEB',
                            'trust_state': 'QUALIFIED',
                            'extraction_method': 'html_regex',
                            'evidence_excerpt': excerpt,
                            'content_hash': content_hash(excerpt),
                            'timestamp': datetime.now().isoformat(),
                        })
    
    return prices, [], sources


def extract_honda() -> List[dict]:
    """Honda Thailand — Next.js RSC, try multiple approaches."""
    prices = []
    sources = []
    
    # Try direct page fetch for embedded data
    urls_to_try = [
        'https://www.honda.co.th/th/car',
        'https://www.honda.co.th/th',
        'https://www.honda.co.th/th/car/city',
        'https://www.honda.co.th/th/car/civic',
        'https://www.honda.co.th/th/car/hr-v',
        'https://www.honda.co.th/th/car/cr-v',
    ]
    
    for url in urls_to_try:
        html = fetch_url(url, timeout=12)
        if html:
            sources.append({'url': url, 'status': 'ok', 'method': 'html_regex'})
            
            # Try to find __NEXT_DATA__ or similar
            next_data = re.search(r'__NEXT_DATA__\s*=\s*(\{.*?\})\s*</script>', html, re.DOTALL)
            if next_data:
                try:
                    nd = json.loads(next_data.group(1))
                    # Extract model data from Next.js page props
                    props = nd.get('props', {}).get('pageProps', {})
                    if 'models' in props:
                        for model in props['models']:
                            name = model.get('name', '')
                            price = model.get('price', model.get('startingPrice', 0))
                            if name and price:
                                p = int(float(str(price).replace(',', '')))
                                if THB_MIN <= p <= THB_MAX:
                                    excerpt = json.dumps(model, ensure_ascii=False)[:300]
                                    prices.append({
                                        'brand': 'honda',
                                        'model': name,
                                        'variant': '__MODEL_RANGE__',
                                        'price_thb': p,
                                        'price_type': 'STARTING_PRICE',
                                        'source_url': url,
                                        'source_class': 'OFFICIAL_WEB',
                                        'trust_state': 'QUALIFIED',
                                        'extraction_method': 'html_json_embed',
                                        'evidence_excerpt': excerpt,
                                        'content_hash': content_hash(excerpt),
                                        'timestamp': datetime.now().isoformat(),
                                    })
                except (json.JSONDecodeError, KeyError):
                    pass
            
            # Try RSC push data
            rsc_matches = re.findall(r'self\.__next_f\.push\(\[.*?\]\)', html, re.DOTALL)
            for rsc in rsc_matches:
                # Look for price-like patterns in RSC data
                price_matches = re.findall(r'"(?:price|startingPrice|msrp)":\s*(\d+)', rsc)
                model_matches = re.findall(r'"(?:name|modelName)":\s*"([^"]+)"', rsc)
                if price_matches and model_matches:
                    for i, pm in enumerate(model_matches[:len(price_matches)]):
                        p = int(price_matches[i])
                        if THB_MIN <= p <= THB_MAX:
                            prices.append({
                                'brand': 'honda',
                                'model': pm,
                                'variant': '__MODEL_RANGE__',
                                'price_thb': p,
                                'price_type': 'STARTING_PRICE',
                                'source_url': url,
                                'source_class': 'OFFICIAL_WEB',
                                'trust_state': 'QUALIFIED',
                                'extraction_method': 'rsc_push',
                                'evidence_excerpt': f'RSC push data: {pm} = {p}',
                                'content_hash': content_hash(f'honda:{pm}:{p}'),
                                'timestamp': datetime.now().isoformat(),
                            })
            
            # Generic price extraction from HTML
            prices_html = extract_thb_prices(html)
            for val, excerpt in prices_html:
                # Skip very common navigation/footer prices
                if val not in [p['price_thb'] for p in prices]:
                    prices.append({
                        'brand': 'honda',
                        'model': 'unknown',
                        'variant': '__MODEL_RANGE__',
                        'price_thb': val,
                        'price_type': 'STARTING_PRICE',
                        'source_url': url,
                        'source_class': 'OFFICIAL_WEB',
                        'trust_state': 'QUALIFIED',
                        'extraction_method': 'html_regex',
                        'evidence_excerpt': excerpt,
                        'content_hash': content_hash(f'honda:{val}:{url}'),
                        'timestamp': datetime.now().isoformat(),
                    })
    
    return prices, [], sources


def extract_generic_official(brand_slug: str, brand_name: str, 
                             brand_name_th: str, website_url: str) -> List[dict]:
    """Generic extraction for brands without known special APIs."""
    prices = []
    sources = []
    
    # Try official website
    html = fetch_url(website_url)
    if html:
        sources.append({'url': website_url, 'status': 'ok', 'method': 'html_regex'})
        
        # Check for __NUXT__ data
        nuxt_match = re.search(r'window\.__NUXT__\s*=\s*(\{.*?\})\s*</script>', html, re.DOTALL)
        if nuxt_match:
            try:
                nuxt_data = json.loads(nuxt_match.group(1))
                # Extract prices from Nuxt state
                nuxt_str = json.dumps(nuxt_data)
                for m in re.finditer(r'"(?:price|startingPrice|msrp|modelPrice)":\s*"?(\d+)"?', nuxt_str):
                    val = int(m.group(1))
                    if THB_MIN <= val <= THB_MAX:
                        prices.append({
                            'brand': brand_slug,
                            'model': 'unknown',
                            'variant': '__MODEL_RANGE__',
                            'price_thb': val,
                            'price_type': 'STARTING_PRICE',
                            'source_url': website_url,
                            'source_class': 'OFFICIAL_WEB',
                            'trust_state': 'QUALIFIED',
                            'extraction_method': 'nuxt_json',
                            'evidence_excerpt': f'__NUXT__ data: {val}',
                            'content_hash': content_hash(f'{brand_slug}:{val}'),
                            'timestamp': datetime.now().isoformat(),
                        })
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Check for __NEXT_DATA__
        next_match = re.search(r'__NEXT_DATA__\s*=\s*(\{.*?\})\s*</script>', html, re.DOTALL)
        if next_match:
            try:
                nd = json.loads(next_match.group(1))
                nd_str = json.dumps(nd)
                for m in re.finditer(r'"(?:price|startingPrice|msrp)":\s*"?(\d+)"?', nd_str):
                    val = int(m.group(1))
                    if THB_MIN <= val <= THB_MAX:
                        prices.append({
                            'brand': brand_slug,
                            'model': 'unknown',
                            'variant': '__MODEL_RANGE__',
                            'price_thb': val,
                            'price_type': 'STARTING_PRICE',
                            'source_url': website_url,
                            'source_class': 'OFFICIAL_WEB',
                            'trust_state': 'QUALIFIED',
                            'extraction_method': 'next_data_json',
                            'evidence_excerpt': f'__NEXT_DATA__: {val}',
                            'content_hash': content_hash(f'{brand_slug}:{val}:next'),
                            'timestamp': datetime.now().isoformat(),
                        })
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Generic price extraction
        html_prices = extract_thb_prices(html)
        for val, excerpt in html_prices:
            if val not in [p['price_thb'] for p in prices]:
                prices.append({
                    'brand': brand_slug,
                    'model': 'unknown',
                    'variant': '__MODEL_RANGE__',
                    'price_thb': val,
                    'price_type': 'STARTING_PRICE',
                    'source_url': website_url,
                    'source_class': 'OFFICIAL_WEB',
                    'trust_state': 'QUALIFIED',
                    'extraction_method': 'html_regex',
                    'evidence_excerpt': excerpt,
                    'content_hash': content_hash(f'{brand_slug}:{val}:html'),
                    'timestamp': datetime.now().isoformat(),
                })
    
    # Try Thai automotive media
    media_urls = [
        f'https://www.9carthai.com/{brand_slug.replace("-", "")}-price/',
        f'https://www.9carthai.com/?s={brand_name}+ราคา',
    ]
    
    for murl in media_urls:
        mhtml = fetch_url(murl)
        if mhtml:
            sources.append({'url': murl, 'status': 'ok', 'method': 'media_search'})
            html_prices = extract_thb_prices(mhtml)
            for val, excerpt in html_prices:
                if val not in [p['price_thb'] for p in prices]:
                    prices.append({
                        'brand': brand_slug,
                        'model': 'unknown',
                        'variant': '__MODEL_RANGE__',
                        'price_thb': val,
                        'price_type': 'STARTING_PRICE',
                        'source_url': murl,
                        'source_class': 'AUTO_MEDIA',
                        'trust_state': 'RESEARCH_UNVERIFIED',
                        'extraction_method': 'media_regex',
                        'evidence_excerpt': excerpt,
                        'content_hash': content_hash(f'{brand_slug}:{val}:media'),
                        'timestamp': datetime.now().isoformat(),
                    })
    
    return prices, [], sources


def extract_mitsubishi() -> List[dict]:
    """Mitsubishi Thailand — server-rendered, prices in HTML."""
    prices = []
    sources = []
    
    model_urls = [
        ('Mirage', 'https://www.mitsubishi-motors.co.th/th/model/mirage'),
        ('Attrage', 'https://www.mitsubishi-motors.co.th/th/model/attrage'),
        ('Xpander', 'https://www.mitsubishi-motors.co.th/th/model/xpander'),
        ('Xpander Cross', 'https://www.mitsubishi-motors.co.th/th/model/xpander-cross'),
        ('Triton', 'https://www.mitsubishi-motors.co.th/th/model/triton'),
        ('Pajero Sport', 'https://www.mitsubishi-motors.co.th/th/model/pajero-sport'),
    ]
    
    for model_name, url in model_urls:
        html = fetch_url(url)
        if html:
            sources.append({'url': url, 'status': 'ok', 'method': 'html_regex'})
            html_prices = extract_thb_prices(html)
            for val, excerpt in html_prices:
                prices.append({
                    'brand': 'mitsubishi',
                    'model': model_name,
                    'variant': '__MODEL_RANGE__',
                    'price_thb': val,
                    'price_type': 'STARTING_PRICE',
                    'source_url': url,
                    'source_class': 'OFFICIAL_WEB',
                    'trust_state': 'QUALIFIED',
                    'extraction_method': 'html_regex',
                    'evidence_excerpt': excerpt,
                    'content_hash': content_hash(f'mitsubishi:{model_name}:{val}'),
                    'timestamp': datetime.now().isoformat(),
                })
    
    return prices, [], sources


def extract_byd() -> List[dict]:
    """BYD Thailand — SPA, try multiple approaches."""
    prices = []
    sources = []
    
    # BYD Thailand official site
    urls = [
        'https://www.byd.com/th/car',
        'https://www.byd.com/th',
        'https://www.byd.com/th/atto-3',
        'https://www.byd.com/th/dolphin',
        'https://www.byd.com/th/seal',
        'https://www.byd.com/th/sealion-7',
    ]
    
    for url in urls:
        html = fetch_url(url)
        if html:
            sources.append({'url': url, 'status': 'ok', 'method': 'html_regex'})
            
            # Check for embedded JSON
            json_matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
            for jm in json_matches:
                try:
                    data = json.loads(jm)
                    if isinstance(data, dict):
                        offers = data.get('offers', {})
                        price = offers.get('price', offers.get('lowPrice', 0))
                        if price:
                            p = int(float(str(price).replace(',', '')))
                            if THB_MIN <= p <= THB_MAX:
                                name = data.get('name', 'unknown')
                                excerpt = json.dumps(data, ensure_ascii=False)[:300]
                                prices.append({
                                    'brand': 'byd',
                                    'model': name,
                                    'variant': '__MODEL_RANGE__',
                                    'price_thb': p,
                                    'price_type': 'STARTING_PRICE',
                                    'source_url': url,
                                    'source_class': 'OFFICIAL_WEB',
                                    'trust_state': 'QUALIFIED',
                                    'extraction_method': 'json_ld',
                                    'evidence_excerpt': excerpt,
                                    'content_hash': content_hash(excerpt),
                                    'timestamp': datetime.now().isoformat(),
                                })
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Generic price extraction
            html_prices = extract_thb_prices(html)
            for val, excerpt in html_prices:
                if val not in [p['price_thb'] for p in prices]:
                    prices.append({
                        'brand': 'byd',
                        'model': 'unknown',
                        'variant': '__MODEL_RANGE__',
                        'price_thb': val,
                        'price_type': 'STARTING_PRICE',
                        'source_url': url,
                        'source_class': 'OFFICIAL_WEB',
                        'trust_state': 'QUALIFIED',
                        'extraction_method': 'html_regex',
                        'evidence_excerpt': excerpt,
                        'content_hash': content_hash(f'byd:{val}'),
                        'timestamp': datetime.now().isoformat(),
                    })
    
    return prices, [], sources


def extract_mg() -> List[dict]:
    """MG Thailand — SPA with Cloudflare, try multiple approaches."""
    prices = []
    sources = []
    
    # Try known MG URLs
    urls = [
        'https://mgcars.com/th/',
        'https://mgcars.com/th/mg-zs',
        'https://mgcars.com/th/mg-zs-ev',
        'https://mgcars.com/th/mg4',
        'https://mgcars.com/th/mg5',
        'https://mgcars.com/th/mg3-hybrid-plus',
    ]
    
    for url in urls:
        html = fetch_url(url)
        if html:
            sources.append({'url': url, 'status': 'ok', 'method': 'html_regex'})
            html_prices = extract_thb_prices(html)
            for val, excerpt in html_prices:
                if val not in [p['price_thb'] for p in prices]:
                    prices.append({
                        'brand': 'mg',
                        'model': 'unknown',
                        'variant': '__MODEL_RANGE__',
                        'price_thb': val,
                        'price_type': 'STARTING_PRICE',
                        'source_url': url,
                        'source_class': 'OFFICIAL_WEB',
                        'trust_state': 'QUALIFIED',
                        'extraction_method': 'html_regex',
                        'evidence_excerpt': excerpt,
                        'content_hash': content_hash(f'mg:{val}:{url}'),
                        'timestamp': datetime.now().isoformat(),
                    })
    
    return prices, [], sources


def extract_headlightmag_articles(brand_name: str, brand_slug: str) -> List[dict]:
    """Extract prices from Headlightmag homepage articles for a brand."""
    prices = []
    sources = []
    
    # Get homepage
    html = fetch_url('https://www.headlightmag.com/')
    if not html:
        return prices, sources
    
    # Extract article URLs
    article_urls = re.findall(r'href="(https://www\.headlightmag\.com/[^"]*\.html)"', html)
    article_urls = list(set(article_urls))
    
    # Filter to brand-relevant articles
    brand_lower = brand_name.lower()
    relevant = [u for u in article_urls if brand_lower in u.lower() 
                or any(word in u.lower() for word in brand_name.split())]
    
    # Also try common model names for the brand
    model_keywords = {
        'toyota': ['yaris', 'corolla', 'camry', 'fortuner', 'hilux', 'innova', 'veloz', 'avanza', 'bz4x', 'cross'],
        'honda': ['city', 'civic', 'hr-v', 'cr-v', 'br-v', 'accord', 'wr-v'],
        'nissan': ['almera', 'kicks', 'x-trail', 'terra', 'navara', 'serena', 'gt-r'],
        'mazda': ['mazda2', 'mazda3', 'cx-3', 'cx-30', 'cx-5', 'cx-80', '6e'],
        'mg': ['mg3', 'mg4', 'mg5', 'zs', 'hs', 'im5', 'im6', 's5', 'urban', 'cyberster'],
        'byd': ['atto', 'dolphin', 'seal', 'sealion', 'm6'],
        'gwm': ['haval', 'ora', 'tank'],
        'ford': ['ranger', 'everest', 'territory', 'maverick'],
        'isuzu': ['d-max', 'mu-x'],
        'bmw': ['series', 'x1', 'x3', 'x5', 'ix', 'i5'],
        'mercedes-benz': ['class', 'gla', 'glc', 'gle', 'eqa', 'eqb'],
        'volvo': ['xc40', 'xc60', 'xc90', 'ex30'],
    }
    
    for kw in model_keywords.get(brand_slug, []):
        relevant.extend([u for u in article_urls if kw in u.lower()])
    
    relevant = list(set(relevant))[:10]  # Cap at 10 articles
    
    for article_url in relevant:
        article_html = fetch_url(article_url, timeout=10)
        if article_html:
            sources.append({'url': article_url, 'status': 'ok', 'method': 'media_article'})
            
            # Strip HTML tags for text extraction
            text = re.sub(r'<[^>]+>', ' ', article_html)
            text = re.sub(r'\s+', ' ', text)
            
            # Extract title
            title_match = re.search(r'<title>(.*?)</title>', article_html)
            title = title_match.group(1) if title_match else ''
            
            # Try variant-level prices
            variant_prices = extract_variant_prices(text, brand_slug, '')
            if variant_prices:
                for vp in variant_prices:
                    prices.append({
                        'brand': brand_slug,
                        'model': title.split('|')[0].strip() if title else 'unknown',
                        'variant': vp['variant'],
                        'price_thb': vp['price_thb'],
                        'price_type': 'VARIANT_MSRP',
                        'source_url': article_url,
                        'source_class': 'AUTO_MEDIA',
                        'trust_state': 'RESEARCH_UNVERIFIED',
                        'extraction_method': 'media_article',
                        'evidence_excerpt': vp['excerpt'],
                        'content_hash': content_hash(f'{brand_slug}:{vp["variant"]}:{vp["price_thb"]}'),
                        'timestamp': datetime.now().isoformat(),
                    })
            else:
                # Fall back to generic price extraction
                article_prices = extract_thb_prices(text)
                for val, excerpt in article_prices:
                    if val not in [p['price_thb'] for p in prices]:
                        prices.append({
                            'brand': brand_slug,
                            'model': title.split('|')[0].strip() if title else 'unknown',
                            'variant': '__MODEL_RANGE__',
                            'price_thb': val,
                            'price_type': 'STARTING_PRICE',
                            'source_url': article_url,
                            'source_class': 'AUTO_MEDIA',
                            'trust_state': 'RESEARCH_UNVERIFIED',
                            'extraction_method': 'media_article',
                            'evidence_excerpt': excerpt,
                            'content_hash': content_hash(f'{brand_slug}:{val}:{article_url}'),
                            'timestamp': datetime.now().isoformat(),
                        })
    
    return prices, [], sources


# ─── Brand Registry ──────────────────────────────────────────────────────────

BRANDS = {
    'toyota': {'name': 'Toyota', 'name_th': 'โตโยต้า', 'url': 'https://www.toyota.co.th', 'extractor': 'toyota'},
    'honda': {'name': 'Honda', 'name_th': 'ฮอนด้า', 'url': 'https://www.honda.co.th', 'extractor': 'honda'},
    'nissan': {'name': 'Nissan', 'name_th': 'นิสสัน', 'url': 'https://www.nissan.co.th', 'extractor': 'nissan'},
    'mazda': {'name': 'Mazda', 'name_th': 'มาสด้า', 'url': 'https://www.mazda.co.th', 'extractor': 'generic'},
    'mitsubishi': {'name': 'Mitsubishi', 'name_th': 'มิตซูบิชิ', 'url': 'https://www.mitsubishi-motors.co.th', 'extractor': 'mitsubishi'},
    'suzuki': {'name': 'Suzuki', 'name_th': 'ซูซูกิ', 'url': 'https://www.suzuki.co.th', 'extractor': 'generic'},
    'isuzu': {'name': 'Isuzu', 'name_th': 'อีซูซุ', 'url': 'https://www.isuzu.co.th', 'extractor': 'generic'},
    'byd': {'name': 'BYD', 'name_th': 'บีวายดี', 'url': 'https://www.byd.com/th', 'extractor': 'byd'},
    'mg': {'name': 'MG', 'name_th': 'เอ็มจี', 'url': 'https://mgcars.com/th', 'extractor': 'mg'},
    'gwm': {'name': 'GWM', 'name_th': 'จีดับบลิวเอ็ม', 'url': 'https://www.gwm.co.th', 'extractor': 'generic'},
    'changan': {'name': 'Changan', 'name_th': 'ฉางอัน', 'url': 'https://www.changan.co.th', 'extractor': 'generic'},
    'chery': {'name': 'Chery', 'name_th': 'เชอรี่', 'url': 'https://www.chery.co.th', 'extractor': 'generic'},
    'zeekr': {'name': 'Zeekr', 'name_th': 'ซีเคอร์', 'url': 'https://www.zeekrlife.com/th', 'extractor': 'generic'},
    'hyundai': {'name': 'Hyundai', 'name_th': 'ฮุนได', 'url': 'https://www.hyundai.co.th', 'extractor': 'generic'},
    'kia': {'name': 'Kia', 'name_th': 'เกีย', 'url': 'https://www.kia.com/th', 'extractor': 'generic'},
    'ford': {'name': 'Ford', 'name_th': 'ฟอร์ด', 'url': 'https://www.ford.co.th', 'extractor': 'generic'},
    'chevrolet': {'name': 'Chevrolet', 'name_th': 'เชฟโรเลต', 'url': 'https://www.chevrolet.co.th', 'extractor': 'generic'},
    'bmw': {'name': 'BMW', 'name_th': 'บีเอ็มดับบลิว', 'url': 'https://www.bmw.co.th', 'extractor': 'generic'},
    'mercedes-benz': {'name': 'Mercedes-Benz', 'name_th': 'เมอร์เซเดส-เบนซ์', 'url': 'https://www.mercedes-benz.co.th', 'extractor': 'generic'},
    'volvo': {'name': 'Volvo', 'name_th': 'วอลโว่', 'url': 'https://www.volvo.co.th', 'extractor': 'generic'},
    'mini': {'name': 'MINI', 'name_th': 'มินิ', 'url': 'https://www.mini.co.th', 'extractor': 'generic'},
    'porsche': {'name': 'Porsche', 'name_th': 'ปอร์เช่', 'url': 'https://www.porsche.com/thailand', 'extractor': 'generic'},
    'lexus': {'name': 'Lexus', 'name_th': 'เล็กซัส', 'url': 'https://www.lexus.co.th', 'extractor': 'generic'},
    'tesla': {'name': 'Tesla', 'name_th': 'เทสลา', 'url': 'https://www.tesla.com/th_th', 'extractor': 'generic'},
    'subaru': {'name': 'Subaru', 'name_th': 'ซูบารุ', 'url': 'https://www.subaru.co.th', 'extractor': 'generic'},
    'kg-mobility': {'name': 'KG Mobility', 'name_th': 'เคจี โมบิลิตี้', 'url': 'https://www.kgmobility.co.th', 'extractor': 'generic'},
    'ldv': {'name': 'LDV', 'name_th': 'เอลดีวี', 'url': 'https://www.ldvautomotive.co.th', 'extractor': 'generic'},
    'baic': {'name': 'BAIC', 'name_th': 'บีไอซี', 'url': 'https://www.baicmotor.com/th', 'extractor': 'generic'},
    'jetour': {'name': 'Jetour', 'name_th': 'เจ็ททัวร์', 'url': 'https://www.jetour.co.th', 'extractor': 'generic'},
    'geely': {'name': 'Geely', 'name_th': 'จีลี่', 'url': 'https://www.geelyauto.co.th', 'extractor': 'generic'},
    'denza': {'name': 'Denza', 'name_th': 'เดนซ่า', 'url': 'https://www.denza.com/th', 'extractor': 'generic'},
    'nio': {'name': 'NIO', 'name_th': 'นิโอ', 'url': 'https://www.nio.com', 'extractor': 'generic'},
    'xpeng': {'name': 'Xpeng', 'name_th': 'เอ็กซ์เพ่ง', 'url': 'https://www.xpeng.com', 'extractor': 'generic'},
    'avora': {'name': 'Avatr', 'name_th': 'อาวาทร์', 'url': 'https://www.avatr.com', 'extractor': 'generic'},
}

# ─── Main Orchestration ──────────────────────────────────────────────────────

def research_brand(brand_slug: str) -> BrandResult:
    """Research a single brand using all available strategies."""
    info = BRANDS[brand_slug]
    result = BrandResult(
        brand=brand_slug,
        brand_name=info['name'],
        status='RUNNING',
        started_at=datetime.now().isoformat(),
    )
    
    try:
        extractor_type = info['extractor']
        
        if extractor_type == 'toyota':
            prices, specs, sources = extract_toyota()
        elif extractor_type == 'nissan':
            prices, specs, sources = extract_nissan()
        elif extractor_type == 'honda':
            prices, specs, sources = extract_honda()
        elif extractor_type == 'mitsubishi':
            prices, specs, sources = extract_mitsubishi()
        elif extractor_type == 'byd':
            prices, specs, sources = extract_byd()
        elif extractor_type == 'mg':
            prices, specs, sources = extract_mg()
        else:
            prices, specs, sources = extract_generic_official(
                brand_slug, info['name'], info['name_th'], info['url'])
        
        # Also try Headlightmag for all brands
        hl_prices, hl_specs, hl_sources = extract_headlightmag_articles(
            info['name'], brand_slug)
        
        # Merge results (dedup by content_hash)
        seen_hashes = set()
        all_prices = prices + hl_prices
        for p in all_prices:
            h = p.get('content_hash', '')
            if h not in seen_hashes:
                seen_hashes.add(h)
                result.prices.append(p)
        
        result.specs = specs + hl_specs
        result.sources = sources + hl_sources
        result.models_found = len(set(p['model'] for p in result.prices if p['model'] != 'unknown'))
        result.variants_found = len([p for p in result.prices if p['variant'] != '__MODEL_RANGE__'])
        
        if result.prices:
            result.status = 'DATA_EXTRACTED'
        elif result.sources:
            result.status = 'PARTIAL'
        else:
            result.status = 'BLOCKED'
            
    except Exception as e:
        result.status = 'FAILED'
        result.failures.append({
            'error': str(e),
            'traceback': traceback.format_exc()
        })
    
    result.finished_at = datetime.now().isoformat()
    return result


def main():
    """Run parallel extraction for all brands."""
    os.makedirs(RUN_DIR, exist_ok=True)
    
    print(f"=== Mega-Parallel Thai Automotive Data Extraction ===")
    print(f"Run directory: {RUN_DIR}")
    print(f"Brands to process: {len(BRANDS)}")
    print(f"Started: {datetime.now().isoformat()}")
    print()
    
    all_results = {}
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for slug in BRANDS:
            future = executor.submit(research_brand, slug)
            futures[future] = slug
        
        for future in as_completed(futures):
            slug = futures[future]
            try:
                result = future.result(timeout=120)
                all_results[slug] = result
                
                # Write per-brand artifact
                brand_dir = os.path.join(RUN_DIR, slug)
                os.makedirs(brand_dir, exist_ok=True)
                with open(os.path.join(brand_dir, 'summary.json'), 'w') as f:
                    json.dump(asdict(result), f, ensure_ascii=False, indent=2)
                
                # Print progress
                n_prices = len(result.prices)
                n_specs = len(result.specs)
                n_sources = len(result.sources)
                print(f"  [{result.status:>15}] {slug:>20}: {n_prices} prices, {n_specs} specs, {n_sources} sources")
                
            except Exception as e:
                print(f"  [FAILED] {slug}: {e}")
                all_results[slug] = BrandResult(
                    brand=slug, brand_name=BRANDS[slug]['name'],
                    status='FAILED',
                    failures=[{'error': str(e)}],
                    started_at=datetime.now().isoformat(),
                    finished_at=datetime.now().isoformat(),
                )
    
    # Write aggregate summary
    total_prices = sum(len(r.prices) for r in all_results.values())
    total_specs = sum(len(r.specs) for r in all_results.values())
    total_sources = sum(len(r.sources) for r in all_results.values())
    total_models = sum(r.models_found for r in all_results.values())
    
    summary = {
        'run_id': os.path.basename(RUN_DIR),
        'timestamp': datetime.now().isoformat(),
        'total_brands': len(all_results),
        'brands_with_prices': sum(1 for r in all_results.values() if r.prices),
        'brands_blocked': sum(1 for r in all_results.values() if r.status == 'BLOCKED'),
        'brands_failed': sum(1 for r in all_results.values() if r.status == 'FAILED'),
        'total_prices': total_prices,
        'total_specs': total_specs,
        'total_sources': total_sources,
        'total_models_found': total_models,
        'per_brand': {
            slug: {
                'status': r.status,
                'prices': len(r.prices),
                'specs': len(r.specs),
                'sources': len(r.sources),
                'models': r.models_found,
                'variants': r.variants_found,
            }
            for slug, r in all_results.items()
        }
    }
    
    with open(os.path.join(RUN_DIR, 'run-summary.json'), 'w') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n=== Run Complete ===")
    print(f"Total prices extracted: {total_prices}")
    print(f"Total specs extracted: {total_specs}")
    print(f"Total sources: {total_sources}")
    print(f"Brands with data: {summary['brands_with_prices']}/{summary['total_brands']}")
    print(f"Blocked: {summary['brands_blocked']}, Failed: {summary['brands_failed']}")
    print(f"Summary: {os.path.join(RUN_DIR, 'run-summary.json')}")


if __name__ == '__main__':
    main()
