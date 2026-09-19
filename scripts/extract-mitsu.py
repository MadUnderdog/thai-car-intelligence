#!/usr/bin/env python3
"""Extract Mitsubishi Thailand car models and prices from web pages."""
import re
import json
import subprocess
import sys

def fetch_url(url):
    """Fetch URL using curl and return HTML."""
    result = subprocess.run(
        ["curl", "-sL", "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64) Chrome/120",
         "--connect-timeout", "15", "--max-time", "30", url],
        capture_output=True, text=True, timeout=45
    )
    return result.stdout

def extract_data(html, source_url):
    """Extract model names, prices, and specs from HTML."""
    data = {"source": source_url, "models": [], "prices": [], "specs": []}
    
    # Find car model links
    car_links = set()
    for m in re.finditer(r'href=["\'](/(?:en/)?cars/[a-z0-9_-]+)', html):
        car_links.add(m.group(1))
    data["car_links"] = sorted(car_links)
    
    # Find all Thai prices
    prices = set()
    for m in re.finditer(r'(?:฿|บาท\s*)(\d{1,3}(?:,\d{3})+)', html):
        val = int(m.group(1).replace(',', ''))
        if 300000 <= val <= 15000000:
            prices.add(val)
    for m in re.finditer(r'(\d{1,3}(?:,\d{3})+)\s*(?:THB|฿|บาท)', html):
        val = int(m.group(1).replace(',', ''))
        if 300000 <= val <= 15000000:
            prices.add(val)
    data["prices"] = sorted(prices)
    
    # Find model-price associations with context
    model_names = ['Xpander', 'Xpander HEV', 'Xforce', 'Xforce HEV', 'Triton', 'Outlander', 
                   'Attrage', 'Mirage', 'Pajero', 'L200', 'XFC', 'XRT', 'GT-Power']
    
    # Try to find structured data (JSON-LD)
    json_ld_matches = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    for jld in json_ld_matches:
        try:
            ld = json.loads(jld)
            if isinstance(ld, dict) and "name" in ld and "offers" in ld:
                data["specs"].append({"jsonld": ld})
        except:
            pass
    
    # Find price sections with model context
    for pattern in [
        r'(Xpander[^<]{0,100}?)(?:฿|บาท)\s*(\d{1,3}(?:,\d{3})+)',
        r'(Xforce[^<]{0,100}?)(?:฿|บาท)\s*(\d{1,3}(?:,\d{3})+)',
        r'(Triton[^<]{0,100}?)(?:฿|บาท)\s*(\d{1,3}(?:,\d{3})+)',
        r'(Outlander[^<]{0,100}?)(?:฿|บาท)\s*(\d{1,3}(?:,\d{3})+)',
        r'(Attrage[^<]{0,100}?)(?:฿|บาท)\s*(\d{1,3}(?:,\d{3})+)',
        r'(Mirage[^<]{0,100}?)(?:฿|บาท)\s*(\d{1,3}(?:,\d{3})+)',
    ]:
        for m in re.finditer(pattern, html):
            model_name = m.group(1).strip()
            price = int(m.group(2).replace(',', ''))
            if 300000 <= price <= 15000000:
                data["models"].append({"model": model_name, "price": price})
    
    # Also search for variant-specific patterns (e.g. "PLUS" "GLS-LTD" "GT-Power")
    variant_pattern = r'((?:Xpander|Xforce|Triton|Outlander|Attrage|Mirage)[^<]{0,50}?)\s*(?:฿|บาท)\s*(\d{1,3}(?:,\d{3})+)'
    for m in re.finditer(variant_pattern, html):
        variant = m.group(1).strip()
        price = int(m.group(2).replace(',', ''))
        if 300000 <= price <= 15000000:
            data["models"].append({"variant": variant, "price": price})
    
    # Extract engine specs
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:kW|kilowatt)', html, re.I):
        data["specs"].append({"power_kw": float(m.group(1))})
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:Nm|นิวตัน)', html, re.I):
        data["specs"].append({"torque_nm": float(m.group(1))})
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:cc|ซีซี)', html, re.I):
        data["specs"].append({"displacement_cc": float(m.group(1))})
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*kWh', html, re.I):
        data["specs"].append({"battery_kwh": float(m.group(1))})
    
    # Look for variant names with model associations
    for m in re.finditer(r'<(?:h[1-6]|a|span|div|p|li)[^>]*>([^<]*(?:Xpander|Xforce|Triton|Outlander|Attrage|Mirage)[^<]*)</(?:h[1-6]|a|span|div|p|li)>', html, re.I):
        text = m.group(1).strip()
        if len(text) < 200:
            data["specs"].append({"heading": text})
    
    return data

# Main execution
urls = [
    "https://www.mitsubishi-motors.co.th",
    "https://www.mitsubishi-motors.co.th/en/cars/xpanderhev",
    "https://www.mitsubishi-motors.co.th/en/cars/xforce-hev",
    "https://www.mitsubishi-motors.co.th/en/cars/xpander",
    "https://www.mitsubishi-motors.co.th/en/cars/xforce",
    "https://www.mitsubishi-motors.co.th/en/cars/triton",
    "https://www.mitsubishi-motors.co.th/en/cars/outlander-phev",
    "https://www.mitsubishi-motors.co.th/en/cars/attrage",
    "https://www.mitsubishi-motors.co.th/en/cars/mirage",
]

all_data = []
all_prices = set()
all_models = []

for url in urls:
    print(f"Fetching: {url}")
    html = fetch_url(url)
    if html and len(html) > 1000:
        data = extract_data(html, url)
        all_data.append(data)
        all_prices.update(data["prices"])
        all_models.extend(data["models"])
        print(f"  -> {len(html)} bytes, {len(data['prices'])} prices, {len(data['models'])} model-price pairs")
        if data["car_links"]:
            print(f"  -> Links: {data['car_links'][:10]}")
    else:
        print(f"  -> FAILED or too small ({len(html) if html else 0} bytes)")

# Also try fetching with Thai URL patterns
thai_urls = [
    "https://www.mitsubishi-motors.co.th/cars/xpander-hev",
    "https://www.mitsubishi-motors.co.th/cars/xforce-hev",
    "https://www.mitsubishi-motors.co.th/cars/xpander",
    "https://www.mitsubishi-motors.co.th/cars/triton",
]

for url in thai_urls:
    print(f"Fetching Thai: {url}")
    html = fetch_url(url)
    if html and len(html) > 1000:
        data = extract_data(html, url)
        all_data.append(data)
        all_prices.update(data["prices"])
        all_models.extend(data["models"])
        print(f"  -> {len(html)} bytes, {len(data['prices'])} prices, {len(data['models'])} model-price pairs")
    else:
        print(f"  -> FAILED ({len(html) if html else 0} bytes)")

# Deduplicate models
seen = set()
unique_models = []
for m in all_models:
    key = (m.get("model", m.get("variant", "")), m["price"])
    if key not in seen:
        seen.add(key)
        unique_models.append(m)

print(f"\n=== SUMMARY ===")
print(f"Total unique prices found: {len(all_prices)}")
print(f"Prices: {sorted(all_prices)}")
print(f"Total unique model-price pairs: {len(unique_models)}")
for mp in unique_models:
    print(f"  {mp}")

# Save raw data
with open("/tmp/mitsu_raw.json", "w") as f:
    json.dump({"all_data": all_data, "all_prices": sorted(all_prices), "models": unique_models}, f, indent=2, ensure_ascii=False)

print("\nRaw data saved to /tmp/mitsu_raw.json")
