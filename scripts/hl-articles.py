#!/usr/bin/env python3
"""Headlightmag category page article processor."""
import json, hashlib, os, re, sys
from datetime import datetime
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed

RUN_DIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/hl-articles"
THB = (200_000, 20_000_000)
H = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/131'}

def ch(s): return hashlib.sha256(s.encode()).hexdigest()[:16]
def now(): return datetime.now().isoformat()

def get(cat_url):
    try:
        r = urlopen(Request(cat_url, headers=H), timeout=12)
        return r.read().decode('utf-8', errors='replace')
    except: return None

def fetch_articles(cat_url):
    html = get(cat_url)
    if not html: return []
    links = re.findall(r'href="(https://www\.headlightmag\.com/[^"]+)"', html)
    skip = ['/category/', '/tag/', '/author/', '/page/', '/wp-json', '/xmlrpc']
    return list(set(l for l in links if not any(s in l for s in skip)))

BRAND_KW = {
    'toyota': ['yaris','corolla','camry','fortuner','hilux','innova','veloz','avanza','bz4x','land-cruiser','alphard','hiace','coaster','commuter','majesty','gr-'],
    'honda': ['city','civic','hr-v','cr-v','br-v','accord','wr-v'],
    'nissan': ['almera','kicks','x-trail','terra','navara','serena','leaf','sakura','urvan'],
    'mazda': ['mazda2','mazda3','cx-3','cx-30','cx-5','cx-80','6e'],
    'mg': ['mg3','mg4','mg5','zs-ev','hs-','im5','im6','s5-ev','urban-ev','cyberster','ep-plus'],
    'byd': ['atto','dolphin','seal','sealion','m6-'],
    'gwm': ['haval','ora-','tank-'],
    'ford': ['ranger','everest','territory','maverick'],
    'isuzu': ['d-max','mu-x'],
    'bmw': ['series-','x1-','x3-','x5-','ix-','i5-'],
    'mercedes-benz': ['class-','gla-','glc-','gle-','eqa-','eqb-'],
    'volvo': ['xc40','xc60','xc90','ex30'],
    'chevrolet': ['trailblazer','colorado'],
    'chery': ['omoda','tiggo','jaecoo'],
    'hyundai': ['ioniq','santa-fe','stargazer','staria'],
    'kia': ['sonet','sportage','ev6','ev9','carnival'],
    'subaru': ['crosstrek','outback'],
    'mitsubishi': ['mirage','attrage','xpander','triton','pajero'],
    'porsche': ['cayenne','macan'],
    'mini': ['cooper','countryman','aceman'],
    'tesla': ['model-3','model-y'],
    'zeekr': ['zeekr'],
    'changan': ['changan','cs55','uni-v','uni-k','deepal'],
    'geely': ['geely','starray'],
    'denza': ['denza'],
    'xpeng': ['xpeng'],
    'kg-mobility': ['kg-mobility','korando','torres'],
    'ldv': ['ldv','d90'],
    'baic': ['baic','x55','bj30'],
    'jetour': ['jetour','t2-','dashing'],
}

def identify(url):
    slug = url.rstrip('/').split('/')[-1].lower()
    for brand, kws in BRAND_KW.items():
        for kw in kws:
            if kw in slug:
                return brand, slug
    return None, slug

def extract_prices(text):
    results = []
    for m in re.finditer(r'(?:฿|ราคา|เริ่มต้น)\s*(\d{1,3}(?:,\d{3})+)', text):
        v = int(m.group(1).replace(',', ''))
        if THB[0] <= v <= THB[1]:
            ctx = text[max(0,m.start()-80):m.end()+80]
            results.append((v, ctx))
    return results

def extract_trims(text, brand, slug):
    """Try to find trim+price pairs."""
    trims = []
    # Pattern: brand/model + trim + price
    for m in re.finditer(r'(\w[\w\+\-\. ]{1,20})\s*[:\s]+(\d{1,3}(?:,\d{3})+)\s*(?:บาท|฿)?', text):
        name = m.group(1).strip()
        v = int(m.group(2).replace(',', ''))
        if THB[0] <= v <= THB[1] and len(name) < 25:
            ctx = text[max(0,m.start()-40):m.end()+40]
            trims.append({'variant': name, 'price_thb': v, 'excerpt': ctx[:200]})
    return trims

def process(url):
    html = get(url)
    if not html: return []
    brand, slug = identify(url)
    if not brand: return []

    title_m = re.search(r'<title>(.*?)</title>', html)
    title = title_m.group(1).split('|')[0].strip() if title_m else slug

    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)

    results = []
    seen = set()

    # Try trim-level extraction first
    trims = extract_trims(text, brand, slug)
    for t in trims:
        key = (brand, slug, t['variant'], t['price_thb'])
        if key not in seen:
            seen.add(key)
            results.append({
                'brand': brand, 'model': title, 'variant': t['variant'],
                'price_thb': t['price_thb'], 'price_type': 'VARIANT_MSRP',
                'source_url': url, 'source_class': 'AUTO_MEDIA',
                'trust_state': 'RESEARCH_UNVERIFIED',
                'extraction_method': 'media_article',
                'evidence_excerpt': t['excerpt'],
                'content_hash': ch(f'{brand}:{slug}:{t["variant"]}:{t["price_thb"]}'),
                'timestamp': now(), 'article_title': title,
            })

    # Fallback: generic prices
    if not results:
        for v, ctx in extract_prices(text):
            key = (brand, slug, v)
            if key not in seen:
                seen.add(key)
                results.append({
                    'brand': brand, 'model': title, 'variant': '__MODEL_RANGE__',
                    'price_thb': v, 'price_type': 'STARTING_PRICE',
                    'source_url': url, 'source_class': 'AUTO_MEDIA',
                    'trust_state': 'RESEARCH_UNVERIFIED',
                    'extraction_method': 'media_regex',
                    'evidence_excerpt': ctx[:200],
                    'content_hash': ch(f'{brand}:{slug}:{v}'),
                    'timestamp': now(), 'article_title': title,
                })
                break

    return results

def main():
    os.makedirs(RUN_DIR, exist_ok=True)
    cats = [
        'https://www.headlightmag.com/category/news/new-cars-in-thailand/',
        'https://www.headlightmag.com/category/news/',
        'https://www.headlightmag.com/category/news/worlds-news/',
    ]
    all_urls = []
    for c in cats:
        urls = fetch_articles(c)
        all_urls.extend(urls)
        print(f"Category: {c.split('/')[-2]} → {len(urls)} articles")
    all_urls = list(set(all_urls))
    print(f"Total unique URLs: {len(all_urls)}")

    all_prices = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        fs = {ex.submit(process, u): u for u in all_urls[:40]}
        for f in as_completed(fs):
            try:
                r = f.result(timeout=15)
                if r:
                    all_prices.extend(r)
                    print(f"  ✓ {r[0]['brand']}/{r[0]['model'][:30]}: {len(r)} prices")
            except: pass

    # Dedup and write
    seen = set()
    uniq = []
    for p in all_prices:
        if p['content_hash'] not in seen:
            seen.add(p['content_hash'])
            uniq.append(p)

    by_brand = {}
    for p in uniq:
        by_brand.setdefault(p['brand'], []).append(p)

    for b, ps in by_brand.items():
        d = os.path.join(RUN_DIR, b)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'hl.json'), 'w') as f:
            json.dump(ps, f, ensure_ascii=False, indent=2)

    print(f"\nTotal: {len(uniq)} unique prices across {len(by_brand)} brands")
    for b, ps in sorted(by_brand.items(), key=lambda x: -len(x[1])):
        print(f"  {b}: {len(ps)} prices")

if __name__ == '__main__':
    main()
