#!/usr/bin/env python3
"""Fetch Mitsubishi car pages and extract price/variant data from __PRELOADED_STATE__."""
import re
import json
import subprocess

def fetch(url):
    r = subprocess.run(
        ["curl", "-sL", "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64) Chrome/120", url],
        capture_output=True, text=True, timeout=30
    )
    return r.stdout

def find_prices(obj, path="", results=None):
    if results is None:
        results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = k.lower()
            if any(w in kl for w in ['price', 'variant', 'grade', 'model', 'name']):
                val = str(v)[:500]
                if val and val != 'None' and val != '':
                    results.append((path + "." + k, val))
            find_prices(v, path + "." + k, results)
    elif isinstance(obj, list):
        for idx, v in enumerate(obj[:10]):
            find_prices(v, path + f"[{idx}]", results)
    return results

def extract_preloaded(html):
    m = re.search(r'window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});\s*</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        # Try to fix common issues
        text = m.group(1)
        # Remove trailing commas
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)
        try:
            return json.loads(text)
        except:
            return None

urls = [
    ("Xpander HEV", "https://www.mitsubishi-motors.co.th/th/cars/xpanderhev"),
    ("Xforce HEV", "https://www.mitsubishi-motors.co.th/th/cars/xforce-hev"),
    ("Xpander Cross HEV", "https://www.mitsubishi-motors.co.th/th/cars/xpandercrosshev"),
    ("Triton", "https://www.mitsubishi-motors.co.th/th/cars/all-newtriton"),
    ("Pajero Sport", "https://www.mitsubishi-motors.co.th/th/cars/pajero-sport"),
    ("Mirage", "https://www.mitsubishi-motors.co.th/th/cars/mirage"),
]

all_results = {}

for name, url in urls:
    print(f"\n{'='*60}")
    print(f"  {name}: {url}")
    print(f"{'='*60}")
    html = fetch(url)
    if not html or len(html) < 1000:
        print(f"  FAILED to fetch ({len(html) if html else 0} bytes)")
        continue
    
    data = extract_preloaded(html)
    if not data:
        print("  No __PRELOADED_STATE__ found")
        continue
    
    print(f"  Page size: {len(html)} bytes")
    print(f"  Top-level keys: {list(data.keys())[:15]}")
    
    results = find_prices(data)
    if results:
        print(f"  Found {len(results)} price-related entries:")
        for path, val in results[:30]:
            print(f"    {path}: {val}")
    else:
        print("  No price entries found in state")
        # Show structure
        for k, v in list(data.items())[:10]:
            print(f"    {k}: {type(v).__name__} = {str(v)[:200]}")
    
    all_results[name] = {"url": url, "data": data, "price_entries": results}

# Save all results
with open("/tmp/mitsu_preloaded.json", "w") as f:
    # Don't save full data, just the price entries
    summary = {}
    for name, r in all_results.items():
        summary[name] = {
            "url": r["url"],
            "price_entries": r["price_entries"]
        }
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(f"\n{'='*60}")
print(f"  SUMMARY: {len(all_results)} pages processed")
print(f"{'='*60}")
