#!/usr/bin/env python3
"""Deep dive into Mazda Thailand homepage HTML to find API endpoints."""
import re, json
from urllib.request import urlopen, Request

def fetch(url):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120'})
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return ""

html = fetch("https://www.mazda.co.th/")
print(f"HTML length: {len(html)}")

# Find all script src URLs
scripts = re.findall(r'src="(https?://[^"]+\.js)"', html)
print("\n=== Script sources (first 30) ===")
for s in scripts[:30]:
    print(s)

# Find any API or data URLs
print("\n=== URLs in HTML ===")
all_urls = set(re.findall(r'https?://[^"\' >]+', html))
for u in sorted(all_urls):
    if any(x in u.lower() for x in ['api', 'json', 'graphql', 'data', 'price', 'model', 'car', 'catalog']):
        print(f"  {u}")

# Look for webpack chunks or lazy-loaded scripts
chunks = re.findall(r'["\']([^"\']*chunk[^"\']*)["\']', html, re.I)
print(f"\n=== Webpack chunks: {len(chunks)} ===")
for c in chunks[:10]:
    print(f"  {c}")

# Check for any Next.js/React patterns
for pattern in ['__NEXT_DATA__', '__NUXT__', '__STATE__', 'window.__', 'initialState', 'props:']:
    if pattern in html:
        print(f"\n=== Found: {pattern} ===")
        idx = html.index(pattern)
        print(html[idx:idx+500])

# Find car model page references
model_refs = re.findall(r'["\']((?:/cars/|/model/|/vehicle/)[^"\']*)["\']', html)
print(f"\n=== Model page refs ===")
for m in sorted(set(model_refs)):
    print(f"  {m}")

# Check if there's a sitemap
sitemap_url = "https://www.mazda.co.th/sitemap.xml"
sitemap = fetch(sitemap_url)
if sitemap:
    print(f"\n=== Sitemap found, length={len(sitemap)} ===")
    urls_in_sitemap = re.findall(r'<loc>([^<]+)</loc>', sitemap)
    car_urls = [u for u in urls_in_sitemap if 'car' in u.lower() or 'model' in u.lower() or 'cx' in u.lower() or 'mazda' in u.lower()]
    for u in car_urls[:30]:
        print(f"  {u}")
else:
    print("\n=== No sitemap ===")

# Also check robots.txt
robots = fetch("https://www.mazda.co.th/robots.txt")
if robots:
    print(f"\n=== robots.txt ===")
    print(robots[:1000])
