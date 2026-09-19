#!/usr/bin/env python3
"""Extract Mitsubishi trim/price data from preloaded state."""
import re
import json
import subprocess

def fetch(url):
    r = subprocess.run(
        ["curl", "-sL", "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64) Chrome/120", 
         "--max-time", "30", url],
        capture_output=True, text=True, timeout=45
    )
    return r.stdout

def extract_state(html):
    m = re.search(r'window\.__PRELOADED_STATE__\s*=\s*(\{.+)', html, re.DOTALL)
    if not m:
        return None
    text = m.group(1)
    if '</script>' in text:
        text = text.split('</script>')[0].rstrip(';').rstrip()
    
    # Try full parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract just the relevant parts by finding key patterns
    # Look for trim data
    results = {}
    
    # Find all "trims" arrays
    for m2 in re.finditer(r'"trims"\s*:\s*\[', text):
        start = m2.start()
        # Find matching bracket
        bracket_count = 0
        i = text.index('[', start)
        j = i
        while j < len(text) and j < start + 20000:
            if text[j] == '[':
                bracket_count += 1
            elif text[j] == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    break
            j += 1
        if bracket_count == 0:
            trim_text = text[i:j+1]
            try:
                trims = json.loads(trim_text)
                results.setdefault('trims', []).extend(trims)
                print(f"  Found trims array with {len(trims)} items")
                for t in trims:
                    if isinstance(t, dict):
                        print(f"    {t.get('name', 'unnamed')}: {t.get('code', 'no code')}")
            except json.JSONDecodeError:
                print(f"  Failed to parse trims array at pos {start}")
    
    # Find price data near trims
    for m2 in re.finditer(r'"price"\s*:\s*\{[^}]*"value"\s*:\s*(\d+\.?\d*)', text):
        print(f"  Price value found: {m2.group(1)}")
    
    return results

# Main
urls = [
    ("Xpander HEV", "https://www.mitsubishi-motors.co.th/th/cars/xpanderhev"),
    ("Xforce HEV", "https://www.mitsubishi-motors.co.th/th/cars/xforce-hev"),
    ("Xpander Cross HEV", "https://www.mitsubishi-motors.co.th/th/cars/xpandercrosshev"),
    ("Triton", "https://www.mitsubishi-motors.co.th/th/cars/all-newtriton"),
    ("Pajero Sport", "https://www.mitsubishi-motors.co.th/th/cars/pajero-sport"),
    ("Mirage", "https://www.mitsubishi-motors.co.th/th/cars/mirage"),
]

all_data = {}
for name, url in urls:
    print(f"\n=== {name} ===")
    html = fetch(url)
    if not html or len(html) < 1000:
        print(f"  FAILED ({len(html) if html else 0} bytes)")
        continue
    
    state = extract_state(html)
    if state and isinstance(state, dict) and 'trims' in state:
        all_data[name] = state['trims']
    else:
        print(f"  No trim data found in state (size={len(html)})")
        # Try direct HTML extraction
        prices = set()
        for m in re.finditer(r'(?:฿|บาท\s*)(\d{1,3}(?:,\d{3})+)', html):
            val = int(m.group(1).replace(',', ''))
            if 300000 <= val <= 15000000:
                prices.add(val)
        for m in re.finditer(r'(\d{1,3}(?:,\d{3})+)\s*(?:THB|฿|บาท)', html):
            val = int(m.group(1).replace(',', ''))
            if 300000 <= val <= 15000000:
                prices.add(val)
        if prices:
            print(f"  HTML prices: {sorted(prices)}")
            all_data[name] = [{"price_from_html": sorted(prices)}]

print(f"\n=== FINAL DATA ===")
print(json.dumps(all_data, indent=2, ensure_ascii=False))
