#!/usr/bin/env python3
"""Extract Mazda Thailand prices from their website."""
import json, re, sys
from urllib.request import urlopen, Request

def fetch(url):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120'})
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return ""

urls = [
    "https://www.mazda.co.th/",
    "https://www.mazda.co.th/cars/cx-5",
    "https://www.mazda.co.th/cars/mazda3",
    "https://www.mazda.co.th/cars/cx-30",
    "https://www.mazda.co.th/cars/mazda2",
    "https://www.mazda.co.th/cars/cx-3",
    "https://www.mazda.co.th/cars/mazda-mx-5",
    "https://www.mazda.co.th/cars/bt-50",
    "https://www.mazda.co.th/cars/cx-60",
]

all_prices = set()
all_contexts = []
car_links = set()
json_data_blocks = []

for url in urls:
    print(f"\n=== Fetching: {url} ===")
    html = fetch(url)
    if not html:
        continue
    print(f"  HTML length: {len(html)}")
    
    # Find all car-related links
    for m in re.finditer(r'href="(/cars/[^"]*)"', html):
        car_links.add(m.group(1))
    for m in re.finditer(r'href=\'(/cars/[^\']*)\'', html):
        car_links.add(m.group(1))
    
    # Extract prices - Thai baht patterns
    for m in re.finditer(r'(\d{1,3}(?:,\d{3})+)\s*(?:บาท|฿|THB|baht)', html, re.I):
        val = int(m.group(1).replace(',', ''))
        if 300000 <= val <= 15000000:
            all_prices.add(val)
            # Get surrounding context
            start = max(0, m.start() - 100)
            end = min(len(html), m.end() + 100)
            ctx = html[start:end]
            # Clean HTML tags
            ctx = re.sub(r'<[^>]+>', ' ', ctx).strip()
            ctx = re.sub(r'\s+', ' ', ctx)
            all_contexts.append({'price': val, 'context': ctx[:200], 'source': url})
    
    # Also check for price patterns like ฿XXX,XXX
    for m in re.finditer(r'฿\s*(\d{1,3}(?:,\d{3})+)', html):
        val = int(m.group(1).replace(',', ''))
        if 300000 <= val <= 15000000:
            all_prices.add(val)
    
    # Check for JSON-LD
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1))
            json_data_blocks.append({'type': 'ld+json', 'data': data, 'source': url})
            print(f"  LD+JSON found: {json.dumps(data, ensure_ascii=False)[:500]}")
        except:
            pass
    
    # Check for __NEXT_DATA__ or similar
    m = re.search(r'__NEXT_DATA__\s*=\s*(\{.*?\})\s*;', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            json_data_blocks.append({'type': 'next_data', 'source': url, 'data': data})
            print(f"  __NEXT_DATA__ found, length={len(m.group(1))}")
        except:
            pass
    
    # Check for embedded API calls or data
    for m in re.finditer(r'"price[^"]*":\s*"?(\d[\d,]+)', html):
        val = int(m.group(1).replace(',', ''))
        if 300000 <= val <= 15000000:
            all_prices.add(val)
            all_contexts.append({'price': val, 'context': f'JSON field match', 'source': url})
    
    # Look for model names
    model_matches = re.findall(r'(?:Mazda\s*(?:CX-?\d+|MX-?\d+|BT-?\d+|2|3|6)|CX-?\d+|MX-?\d+|BT-?\d+)', html, re.I)
    unique_models = set(m.upper() for m in model_matches)
    if unique_models:
        print(f"  Models found: {unique_models}")

print(f"\n=== SUMMARY ===")
print(f"All unique prices found: {sorted(all_prices)}")
print(f"Total price contexts: {len(all_contexts)}")
print(f"Car links found: {sorted(car_links)}")
print(f"\nPrice contexts:")
for ctx in sorted(all_contexts, key=lambda x: x['price']):
    print(f"  ฿{ctx['price']:,} - {ctx['context'][:150]} (from {ctx['source']})")

# Save results
result = {
    'prices': sorted(all_prices),
    'contexts': all_contexts,
    'car_links': sorted(car_links),
    'json_blocks_count': len(json_data_blocks),
    'json_blocks': json_data_blocks[:5]  # Save first 5
}
with open('/tmp/mazda_prices_raw.json', 'w') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"\nSaved raw data to /tmp/mazda_prices_raw.json")
