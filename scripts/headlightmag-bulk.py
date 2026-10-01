#!/usr/bin/env python3
"""
Headlightmag Bulk Extractor — fetch articles, extract model+variant+price.
Associates prices with specific models using article titles and context.
"""
import json, hashlib, os, re, sys, time
from datetime import datetime
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed

RUN_DIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/thai-car-hl-run"
THB_MIN, THB_MAX = 200_000, 20_000_000
HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/131'}
HL_BASE = 'https://www.headlightmag.com'

# Brand → model name patterns for matching
BRAND_MODELS = {
    'toyota': ['Yaris', 'Corolla', 'Camry', 'Fortuner', 'Hilux', 'Innova', 'Veloz', 'Avanza', 'bZ4X', 'Land Cruiser', 'Alphard', 'GR'],
    'honda': ['City', 'Civic', 'HR-V', 'CR-V', 'BR-V', 'Accord', 'WR-V', 'e:N2'],
    'nissan': ['Almera', 'Kicks', 'X-Trail', 'Terra', 'Navara', 'Serena', 'LEAF', 'Sakura'],
    'mazda': ['Mazda2', 'Mazda3', 'CX-3', 'CX-30', 'CX-5', 'CX-80', '6e'],
    'mg': ['MG3', 'MG4', 'MG5', 'ZS', 'HS', 'IM5', 'IM6', 'S5', 'Urban', 'Cyberster', 'EP'],
    'byd': ['Atto', 'Dolphin', 'Seal', 'Sealion', 'M6'],
    'gwm': ['Haval', 'Ora', 'Tank'],
    'ford': ['Ranger', 'Everest', 'Territory', 'Maverick'],
    'isuzu': ['D-Max', 'MU-X'],
    'bmw': ['Series', 'X1', 'X3', 'X5', 'iX', 'i5', '1 Series', '3 Series', '5 Series'],
    'mercedes-benz': ['A-Class', 'C-Class', 'E-Class', 'GLA', 'GLC', 'GLE', 'EQA', 'EQB'],
    'volvo': ['XC40', 'XC60', 'XC90', 'EX30'],
    'chevrolet': ['Trailblazer', 'Colorado'],
    'chery': ['Omoda', 'Tiggo', 'Jaecoo'],
    'hyundai': ['Ioniq', 'Santa Fe', 'Stargazer'],
    'kia': ['Sonet', 'Sportage', 'EV6', 'EV9', 'Carnival'],
    'subaru': ['Crosstrek', 'Outback'],
    'lexus': ['NX', 'RX', 'RZ'],
    'mitsubishi': ['Mirage', 'Attrage', 'Xpander', 'Triton', 'Pajero'],
    'porsche': ['Cayenne', 'Macan'],
    'mini': ['Cooper', 'Countryman'],
    'tesla': ['Model 3', 'Model Y'],
}

def chash(s): return hashlib.sha256(s.encode()).hexdigest()[:16]
def ts(): return datetime.now().isoformat()

def fetch(url, timeout=12):
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except:
        return None

def get_article_urls():
    """Get article URLs from Headlightmag homepage."""
    html = fetch(HL_BASE)
    if not html:
        return []
    urls = re.findall(r'href="((?:https://www\.headlightmag\.com/)?/[^"]*\.html)"', html)
    # Normalize to full URLs
    full = []
    for u in urls:
        if u.startswith('/'):
            full.append(HL_BASE + u)
        elif 'headlightmag.com' in u:
            full.append(u)
    return list(set(full))

def identify_brand_model(title):
    """Identify brand and model from article title."""
    title_lower = title.lower()
    for brand, models in BRAND_MODELS.items():
        for model in models:
            if model.lower() in title_lower:
                return brand, model
    return None, None

def extract_variant_prices_from_text(text, brand, model):
    """Extract variant-level prices from article text."""
    prices = []
    
    # Pattern 1: "Model Trim X,XXX,XXX" or "Model Trim: X,XXX,XXX"
    # E.g., "City V 569,000 / City RS 949,000"
    p1 = re.findall(
        rf'{re.escape(model)}\s+([A-Za-z0-9\+\-\.\s]{{1,20}}?)\s*[:\s]\s*(\d{{1,3}}(?:,\d{{3}})+)',
        text, re.IGNORECASE
    )
    for trim, price_str in p1:
        val = int(price_str.replace(',', ''))
        if THB_MIN <= val <= THB_MAX:
            prices.append({'variant': trim.strip(), 'price_thb': val})
    
    # Pattern 2: Thai "รุ่น X ราคา X,XXX,XXX"
    p2 = re.findall(r'รุ่น\s+([A-Za-z0-9\+\-\.\s]{1,20}?)\s+ราคา\s*(\d{1,3}(?:,\d{3})+)', text)
    for trim, price_str in p2:
        val = int(price_str.replace(',', ''))
        if THB_MIN <= val <= THB_MAX and trim.strip() not in [p['variant'] for p in prices]:
            prices.append({'variant': trim.strip(), 'price_thb': val})
    
    # Pattern 3: Table rows with trim | price
    p3 = re.findall(r'([A-Z][A-Za-z0-9\+\-\.]{1,15})\s*\|\s*(\d{1,3}(?:,\d{3})+)', text)
    for trim, price_str in p3:
        val = int(price_str.replace(',', ''))
        if THB_MIN <= val <= THB_MAX and trim not in [p['variant'] for p in prices]:
            prices.append({'variant': trim, 'price_thb': val})
    
    # Pattern 4: Price comparison tables (multiple prices in sequence)
    # Find lines with both model name and price
    for line in text.split('\n'):
        if model.lower() in line.lower():
            for m in re.finditer(r'(\d{1,3}(?:,\d{3})+)', line):
                val = int(m.group(1).replace(',', ''))
                if THB_MIN <= val <= THB_MAX:
                    # Extract trim from same line
                    after_price = line[m.end():m.end()+50]
                    before_price = line[max(0,m.start()-30):m.start()]
                    trim_match = re.search(r'([A-Z][A-Za-z0-9\+\-\.]{1,15})', after_price)
                    if not trim_match:
                        trim_match = re.search(r'([A-Z][A-Za-z0-9\+\-\.]{1,15})\s*$', before_price)
                    trim = trim_match.group(1) if trim_match else '__MODEL_RANGE__'
                    if val not in [p['price_thb'] for p in prices]:
                        prices.append({'variant': trim, 'price_thb': val})
    
    return prices

def process_article(url):
    """Process a single Headlightmag article."""
    html = fetch(url)
    if not html:
        return []
    
    # Extract title
    title_m = re.search(r'<title>(.*?)</title>', html)
    title = title_m.group(1) if title_m else ''
    
    brand, model = identify_brand_model(title)
    if not brand or not model:
        return []
    
    # Strip HTML for text extraction
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    
    # Extract variant prices
    variant_prices = extract_variant_prices_from_text(text, brand, model)
    
    results = []
    seen = set()
    for vp in variant_prices:
        key = (brand, model, vp['variant'], vp['price_thb'])
        if key in seen:
            continue
        seen.add(key)
        
        # Get excerpt
        price_str = f"{vp['price_thb']:,}"
        idx = text.find(price_str)
        if idx >= 0:
            exc = text[max(0,idx-80):idx+len(price_str)+80].strip()
        else:
            exc = ''
        
        results.append({
            'brand': brand, 'model': model,
            'variant': vp['variant'],
            'price_thb': vp['price_thb'],
            'price_type': 'VARIANT_MSRP' if vp['variant'] != '__MODEL_RANGE__' else 'STARTING_PRICE',
            'source_url': url,
            'source_class': 'AUTO_MEDIA',
            'trust_state': 'RESEARCH_UNVERIFIED',
            'extraction_method': 'media_article',
            'evidence_excerpt': exc[:200],
            'content_hash': chash(f'{brand}:{model}:{vp["variant"]}:{vp["price_thb"]}'),
            'timestamp': ts(),
            'article_title': title,
        })
    
    # If no variant prices, try generic price extraction
    if not results:
        for m in re.finditer(r'(?:฿|ราคา)\s*(\d{1,3}(?:,\d{3})+)', text):
            val = int(m.group(1).replace(',', ''))
            if THB_MIN <= val <= THB_MAX:
                exc = text[max(0,m.start()-50):m.end()+50].strip()[:200]
                results.append({
                    'brand': brand, 'model': model,
                    'variant': '__MODEL_RANGE__',
                    'price_thb': val, 'price_type': 'STARTING_PRICE',
                    'source_url': url, 'source_class': 'AUTO_MEDIA',
                    'trust_state': 'RESEARCH_UNVERIFIED',
                    'extraction_method': 'media_regex',
                    'evidence_excerpt': exc,
                    'content_hash': chash(f'{brand}:{model}:{val}'),
                    'timestamp': ts(),
                    'article_title': title,
                })
                break  # Take first price only for generic
    
    return results

def main():
    os.makedirs(RUN_DIR, exist_ok=True)
    
    print(f"=== Headlightmag Bulk Extraction ===")
    article_urls = get_article_urls()
    print(f"Found {len(article_urls)} article URLs on homepage")
    
    all_prices = []
    processed = 0
    
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(process_article, u): u for u in article_urls[:50]}
        for f in as_completed(futures):
            url = futures[f]
            try:
                results = f.result(timeout=20)
                if results:
                    all_prices.extend(results)
                    processed += 1
                    brand = results[0]['brand']
                    model = results[0]['model']
                    print(f"  ✓ {brand}/{model}: {len(results)} prices from {url}")
            except Exception as e:
                pass
    
    # Dedup by content_hash
    seen = set()
    unique = []
    for p in all_prices:
        h = p['content_hash']
        if h not in seen:
            seen.add(h)
            unique.append(p)
    
    # Group by brand
    by_brand = {}
    for p in unique:
        b = p['brand']
        if b not in by_brand:
            by_brand[b] = []
        by_brand[b].append(p)
    
    # Write per-brand artifacts
    for brand, prices in by_brand.items():
        brand_dir = os.path.join(RUN_DIR, brand)
        os.makedirs(brand_dir, exist_ok=True)
        out = {
            'brand': brand, 'status': 'DATA_EXTRACTED',
            'prices': prices, 'specs': [],
            'sources': list(set(p['source_url'] for p in prices)),
            'failures': [], 'timestamp': ts(),
        }
        with open(os.path.join(brand_dir, 'headlightmag.json'), 'w') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"Articles processed: {processed}")
    print(f"Total prices: {len(unique)}")
    for brand, prices in sorted(by_brand.items(), key=lambda x: -len(x[1])):
        models = set(p['model'] for p in prices)
        variants = len([p for p in prices if p['variant'] != '__MODEL_RANGE__'])
        print(f"  {brand:>20}: {len(prices):>3} prices, {len(models)} models, {variants} variant-level")

if __name__ == '__main__':
    main()
