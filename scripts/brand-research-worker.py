#!/usr/bin/env python3
"""
Brand Research Worker — extracts price/spec data for a single brand.
Writes artifacts to: storage/research/runs/<run_id>/<brand>/
"""
import json, sys, os, re, hashlib
from urllib.request import urlopen, Request
from datetime import datetime

def fetch_url(url, timeout=10):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120'})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None

def extract_prices_from_html(html, brand_slug):
    """Extract price patterns from HTML text."""
    prices = []
    # Thai price patterns: ฿XXX,XXX or XXX,XXX บาท
    for m in re.finditer(r'(?:฿|บาท\s*)(\d{1,3}(?:,\d{3})+)', html):
        val = int(m.group(1).replace(',', ''))
        if 300000 <= val <= 15000000:
            prices.append(val)
    # Also try: price followed by THB
    for m in re.finditer(r'(\d{1,3}(?:,\d{3})+)\s*(?:THB|฿|บาท)', html):
        val = int(m.group(1).replace(',', ''))
        if 300000 <= val <= 15000000:
            prices.append(val)
    return sorted(set(prices))

def extract_specs_from_text(text):
    """Extract spec fields from text."""
    specs = {}
    # Power/torque
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:kW|kilowatt)', text, re.I):
        specs['power_kw'] = float(m.group(1))
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:Nm|นิวตัน)', text, re.I):
        specs['torque_nm'] = float(m.group(1))
    # Displacement
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:cc|ซีซี)', text, re.I):
        specs['displacement_cc'] = float(m.group(1))
    # Battery
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*kWh', text, re.I):
        specs['battery_kwh'] = float(m.group(1))
    # Range
    for m in re.finditer(r'(\d+)\s*(?:km|กม\.|กิโลเมตร)\s*(?:WLTP|range|ระยะทาง)', text, re.I):
        specs['range_km'] = int(m.group(1))
    # Dimensions
    for m in re.finditer(r'(\d{4})\s*[xX×]\s*(\d{4})\s*[xX×]\s*(\d{4})\s*mm', text):
        specs['dimensions_mm'] = f"{m.group(1)}x{m.group(2)}x{m.group(3)}"
    return specs

def research_brand(brand_slug, brand_name, run_dir, official_url):
    """Research a single brand and write artifacts."""
    brand_dir = os.path.join(run_dir, brand_slug)
    os.makedirs(brand_dir, exist_ok=True)
    
    result = {
        'brand': brand_slug,
        'brand_name': brand_name,
        'started_at': datetime.now().isoformat(),
        'official_url': official_url,
        'models_found': [],
        'prices_found': [],
        'specs_found': [],
        'sources': [],
        'failures': [],
    }
    
    # 1. Try official website
    html = fetch_url(official_url)
    if html:
        result['sources'].append({'url': official_url, 'status': 'ok', 'length': len(html)})
        prices = extract_prices_from_html(html, brand_slug)
        if prices:
            result['prices_found'] = prices
        specs = extract_specs_from_text(html)
        if specs:
            result['specs_found'].append(specs)
    else:
        result['failures'].append({'url': official_url, 'error': 'fetch_failed'})
    
    # 2. Try Thai automotive media
    media_urls = [
        f'https://www.9carthai.com/?s={brand_name}+ราคา',
        f'https://www.headlightmag.com/?s={brand_name}',
    ]
    for url in media_urls:
        html = fetch_url(url)
        if html:
            result['sources'].append({'url': url, 'status': 'ok', 'length': len(html)})
            prices = extract_prices_from_html(html, brand_slug)
            if prices:
                result['prices_found'].extend(prices)
    
    result['prices_found'] = sorted(set(result['prices_found']))
    result['finished_at'] = datetime.now().isoformat()
    
    # Write artifacts
    with open(os.path.join(brand_dir, 'summary.json'), 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"[{brand_slug}] prices={len(result['prices_found'])} sources={len(result['sources'])} failures={len(result['failures'])}")
    return result

if __name__ == '__main__':
    if len(sys.argv) < 5:
        print("Usage: brand-research-worker.py <brand_slug> <brand_name> <run_dir> <official_url>")
        sys.exit(1)
    
    brand_slug = sys.argv[1]
    brand_name = sys.argv[2]
    run_dir = sys.argv[3]
    official_url = sys.argv[4]
    
    research_brand(brand_slug, brand_name, run_dir, official_url)
