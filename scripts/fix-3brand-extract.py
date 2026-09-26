#!/usr/bin/env python3
"""Fix Toyota extraction — API returns car_series with start_price/max_price."""
import json, hashlib, os, re, sys
from datetime import datetime
from urllib.request import Request, urlopen

RUN_DIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/thai-car-fix"
THB_MIN, THB_MAX = 200_000, 20_000_000
HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/131', 'Content-Type': 'application/json'}

def chash(s): return hashlib.sha256(s.encode()).hexdigest()[:16]
def ts(): return datetime.now().isoformat()

def extract_toyota():
    """Toyota API: POST /component/api/tcoth/web-init → car_series list."""
    prices, specs, sources = [], [], []
    url = 'https://www.toyota.co.th/component/api/tcoth/web-init'
    req = Request(url, headers=HEADERS, method='POST', data=b'{}')
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        sources.append({'url': url, 'status': 'ok', 'method': 'api_json'})
    except Exception as e:
        return prices, specs, [{'url': url, 'status': 'failed', 'error': str(e)}]

    series = data.get('car_series', [])
    for s in series:
        code = s.get('code', '')
        name = s.get('title_en') or s.get('title', code)
        sp = int(s.get('start_price', 0))
        mp = int(s.get('max_price', 0))
        if not (THB_MIN <= sp <= THB_MAX):
            continue
        exc = json.dumps(s, ensure_ascii=False)[:300]
        h = chash(exc)
        t = ts()

        # Model-range observation
        obs = {
            'brand': 'toyota', 'model': name, 'variant': '__MODEL_RANGE__',
            'price_thb': sp, 'price_type': 'STARTING_PRICE',
            'source_url': url, 'source_class': 'OFFICIAL_API',
            'trust_state': 'QUALIFIED', 'extraction_method': 'api_json',
            'evidence_excerpt': exc, 'content_hash': h, 'timestamp': t,
            'raw_json_path': f'car_series[{code}]',
        }
        if mp > sp:
            obs['price_max_thb'] = mp
        prices.append(obs)

        # Now fetch grade-level detail for this model
        detail_url = f'https://www.toyota.co.th/en/model/api/car/?series_code={code}'
        try:
            req2 = Request(detail_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req2, timeout=10) as resp2:
                detail = json.loads(resp2.read().decode('utf-8'))
            dlist = detail.get('data', [])
            if isinstance(dlist, list) and dlist:
                model_data = dlist[0]
                grades = model_data.get('grades', [])
                for g in grades:
                    gname = g.get('name', g.get('grade_name', ''))
                    gprice = g.get('price', g.get('msrp', 0))
                    if gname and gprice:
                        gp = int(float(gprice))
                        if THB_MIN <= gp <= THB_MAX:
                            gexc = json.dumps(g, ensure_ascii=False)[:300]
                            prices.append({
                                'brand': 'toyota', 'model': name, 'variant': gname,
                                'price_thb': gp, 'price_type': 'VARIANT_MSRP',
                                'source_url': detail_url, 'source_class': 'OFFICIAL_API',
                                'trust_state': 'QUALIFIED', 'extraction_method': 'api_json',
                                'evidence_excerpt': gexc, 'content_hash': chash(gexc),
                                'timestamp': t, 'raw_json_path': f'grades[{gname}]',
                            })
                    # Extract specs from grade
                    for group in g.get('specifications', []):
                        for item in group.get('items', []):
                            title = item.get('title_en') or item.get('title', '')
                            value = item.get('value_en') or item.get('value', '')
                            if title and value:
                                specs.append({
                                    'brand': 'toyota', 'model': name,
                                    'variant': gname, 'spec_key': title,
                                    'spec_value': value, 'source_url': detail_url,
                                    'source_class': 'OFFICIAL_API',
                                    'trust_state': 'QUALIFIED',
                                    'extraction_method': 'api_json',
                                    'evidence_excerpt': f'{title}: {value}',
                                    'content_hash': chash(f'{name}:{title}:{value}'),
                                    'timestamp': t,
                                })
        except Exception:
            pass

    return prices, specs, sources


def extract_nissan():
    """Nissan: hidden iframe with JSON dict keyed by model slug."""
    prices, sources = [], []
    url = 'https://www.nissan.co.th/'
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/131'})
    try:
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return prices, [{'url': url, 'status': 'failed', 'error': str(e)}]

    sources.append({'url': url, 'status': 'ok', 'method': 'html_json_embed'})

    # Find hidden iframe content
    m = re.search(r'id=["\']allVehiclesModelPriceJSON["\'][^>]*>(.*?)</iframe>', html, re.DOTALL)
    if not m:
        return prices, sources

    try:
        data = json.loads(m.group(1).strip())
    except json.JSONDecodeError:
        return prices, sources

    if not isinstance(data, dict):
        return prices, sources

    # Rejected keys (test data, accessories, etc.)
    REJECTED = {'test-gt-r', 'gt-r-test'}

    for slug, entry in data.items():
        if slug in REJECTED or not isinstance(entry, dict):
            continue
        # Price is in 'default' or 'Retail' sub-key
        price_data = entry.get('default') or entry.get('Retail') or {}
        raw_price = price_data.get('modelPrice', '0')
        try:
            price_val = int(str(raw_price).replace(',', '').replace('.', ''))
        except (ValueError, TypeError):
            continue

        if not (THB_MIN <= price_val <= THB_MAX):
            continue

        model_code = entry.get('modelCode', '')
        exc = json.dumps(entry, ensure_ascii=False)[:300]
        h = chash(exc)
        t = ts()

        # Map slug to readable model name
        model_name = slug.replace('-', ' ').title()
        # Known slug → name mappings
        SLUG_MAP = {
            'urvan': 'Urvan', 'note': 'Note', 'terra': 'Terra',
            'navara-sc': 'Navara Single Cab', 'new-terra': 'Terra (New)',
            'navara-calibre-my21': 'Navara Calibre', 'kicks-epower': 'Kicks e-POWER',
            'xtrail-epower': 'X-Trail e-POWER', 'new-navara-single-cab': 'Navara Single Cab',
            'navara': 'Navara', 'almera': 'Almera', 'kicks': 'Kicks',
            'x-trail': 'X-Trail', 'serena': 'Serena', 'leaf': 'LEAF',
            'sakura': 'Sakura', 'qashqai': 'Qashqai', 'juke': 'Juke',
            ' Patrol': 'Patrol', 'navara-double-cab': 'Navara Double Cab',
        }
        model_name = SLUG_MAP.get(slug, model_name)

        prices.append({
            'brand': 'nissan', 'model': model_name, 'variant': '__MODEL_RANGE__',
            'price_thb': price_val, 'price_type': 'STARTING_PRICE',
            'source_url': url, 'source_class': 'OFFICIAL_WEB',
            'trust_state': 'QUALIFIED', 'extraction_method': 'html_json_embed',
            'evidence_excerpt': exc, 'content_hash': h, 'timestamp': t,
            'raw_json_path': f'allVehiclesModelPriceJSON.{slug}',
        })

    return prices, sources


def extract_mitsubishi():
    """Mitsubishi: server-rendered homepage has prices."""
    prices, sources = [], []
    url = 'https://www.mitsubishi-motors.co.th/th'
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/131'})
    try:
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return prices, [{'url': url, 'status': 'failed', 'error': str(e)}]

    sources.append({'url': url, 'status': 'ok', 'method': 'html_regex'})

    # Find model cards with prices — look for price near model names
    # Pattern: model name followed by price
    model_price_pattern = re.compile(
        r'(Mirage|Attrage|Xpander(?:\s+Cross)?|Triton|Pajero\s+Sport)'
        r'.*?(?:฿|ราคา|เริ่มต้น)\s*(\d{1,3}(?:,\d{3})+)',
        re.DOTALL | re.IGNORECASE
    )
    for m in model_price_pattern.finditer(html):
        model = m.group(1).strip()
        price = int(m.group(2).replace(',', ''))
        if THB_MIN <= price <= THB_MAX:
            exc = html[max(0,m.start()-50):m.end()+50].strip()[:200]
            prices.append({
                'brand': 'mitsubishi', 'model': model,
                'variant': '__MODEL_RANGE__',
                'price_thb': price, 'price_type': 'STARTING_PRICE',
                'source_url': url, 'source_class': 'OFFICIAL_WEB',
                'trust_state': 'QUALIFIED', 'extraction_method': 'html_regex',
                'evidence_excerpt': exc, 'content_hash': chash(f'mitsu:{model}:{price}'),
                'timestamp': ts(),
            })

    # Also try generic price extraction with context
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    for m in re.finditer(r'(?:฿|ราคา|เริ่มต้น)\s*(\d{1,3}(?:,\d{3})+)', text):
        val = int(m.group(1).replace(',', ''))
        if THB_MIN <= val <= THB_MAX:
            ctx = text[max(0,m.start()-80):m.end()+80]
            # Find nearest model name
            for mname in ['Mirage', 'Attrage', 'Xpander Cross', 'Xpander',
                          'Triton', 'Pajero Sport']:
                if mname.lower() in ctx.lower():
                    if val not in [p['price_thb'] for p in prices if p['model']==mname]:
                        prices.append({
                            'brand': 'mitsubishi', 'model': mname,
                            'variant': '__MODEL_RANGE__',
                            'price_thb': val, 'price_type': 'STARTING_PRICE',
                            'source_url': url, 'source_class': 'OFFICIAL_WEB',
                            'trust_state': 'QUALIFIED', 'extraction_method': 'html_regex',
                            'evidence_excerpt': ctx[:200],
                            'content_hash': chash(f'mitsu:{mname}:{val}'),
                            'timestamp': ts(),
                        })
                    break

    return prices, sources


if __name__ == '__main__':
    os.makedirs(RUN_DIR, exist_ok=True)
    for brand, fn in [('toyota', extract_toyota), ('nissan', extract_nissan),
                      ('mitsubishi', extract_mitsubishi)]:
        result = fn()
        if len(result) == 3:
            prices, specs, sources = result
        else:
            prices, sources = result
            specs = []
        out = {
            'brand': brand, 'status': 'DATA_EXTRACTED' if prices else 'BLOCKED',
            'prices': prices, 'specs': specs, 'sources': sources,
            'failures': [], 'timestamp': ts(),
        }
        brand_dir = os.path.join(RUN_DIR, brand)
        os.makedirs(brand_dir, exist_ok=True)
        with open(os.path.join(brand_dir, 'summary.json'), 'w') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"[{brand}] {len(prices)} prices, {len(specs)} specs, {len(sources)} sources")
