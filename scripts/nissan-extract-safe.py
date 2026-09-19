#!/usr/bin/env python3
"""
Safe Nissan price extraction from official HTML JSON.
Only extracts prices with explicit model-key linkage.
Never flattens all prices from shared JSON.
"""

import json, re, sys
from urllib.request import urlopen, Request
from datetime import datetime

# Nissan model slug → canonical model name mapping
NISSAN_MODELS = {
    'march': {'name': 'Nissan March', 'code': 'B02A'},
    'almera': {'name': 'Nissan Almera', 'code': 'L02B'},
    'almera-with-stylish-package': {'name': 'Nissan Almera', 'code': '29851'},
    'kicks-epower': {'name': 'Nissan Kicks e-POWER', 'code': '70053'},
    'kicks-e-power-with-stylish-package': {'name': 'Nissan Kicks e-POWER', 'code': '29843'},
    'xtrail-epower': {'name': 'Nissan X-Trail e-POWER', 'code': '70006'},
    'x-trail': {'name': 'Nissan X-Trail', 'code': 'P32R'},
    'terra': {'name': 'Nissan Terra', 'code': 'P60A'},
    'new-terra': {'name': 'Nissan Terra', 'code': '29838'},
    'navara': {'name': 'Nissan Navara', 'code': '70005'},
    'navara-single-cab': {'name': 'Nissan Navara Single Cab', 'code': '70002'},
    'navara-king-cab': {'name': 'Nissan Navara King Cab', 'code': '70003'},
    'navara-calibre': {'name': 'Nissan Navara Calibre', 'code': '70004'},
    'new-navara-calibre': {'name': 'Nissan Navara Calibre', 'code': '29621'},
    'new-navara-single-cab': {'name': 'Nissan Navara Single Cab', 'code': '29637'},
    'new-navara-king-cab': {'name': 'Nissan Navara King Cab', 'code': '29624'},
    'new-navara-pro-4x-and-pro-2x': {'name': 'Nissan Navara Pro', 'code': '29643'},
    'serena': {'name': 'Nissan Serena', 'code': '30177'},
    'serena-epower': {'name': 'Nissan Serena e-POWER', 'code': '30176'},
    'leaf': {'name': 'Nissan Leaf', 'code': 'B12P'},
    'new-leaf': {'name': 'Nissan Leaf', 'code': '29785'},
    'livina': {'name': 'Nissan Livina', 'code': 'N11Q'},
    'juke': {'name': 'Nissan Juke', 'code': 'P12C'},
    'note': {'name': 'Nissan Note', 'code': 'J02C'},
    'teana': {'name': 'Nissan Teana', 'code': 'L42L'},
    'nv350-urvan': {'name': 'Nissan Urvan', 'code': 'X81C'},
}

# Test/invalid entries to reject
REJECT_KEYS = {'test-gt-r', 'sky-edition', 'kicks-e-power-sky-edition'}

def extract_nissan_prices(url):
    """Extract Nissan prices with explicit model-key linkage."""
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='replace')
    
    # Extract JSON from iframe
    m = re.search(r'(\{\"urvan\".*?\})\s*</iframe>', html, re.DOTALL)
    if not m:
        return {'error': 'No Nissan price JSON found'}
    
    data = json.loads(m.group(1))
    
    candidates = []
    for model_key, model_data in data.items():
        # Skip rejected keys
        if model_key in REJECT_KEYS:
            continue
        
        # Get the first pricing tier
        for tier, tier_data in model_data.items():
            if isinstance(tier_data, dict) and 'modelPrice' in tier_data:
                price_str = tier_data.get('modelPrice', '')
                if not price_str:
                    continue
                
                price = int(price_str)
                if price < 100000 or price > 20000000:
                    continue  # Skip invalid prices
                
                version_key = tier_data.get('bestPriceVersionKey', '')
                grade_key = tier_data.get('bestPriceGradeKey', '')
                model_code = model_data.get('modelCode', '')
                updated = model_data.get('Updated_On', '')
                
                # Validate: model_code must match known model
                model_info = NISSAN_MODELS.get(model_key)
                if not model_info:
                    continue  # Unknown model, skip
                
                candidates.append({
                    'model_key': model_key,
                    'model_name': model_info['name'],
                    'expected_code': model_info['code'],
                    'actual_code': model_code,
                    'price': price,
                    'version_key': version_key,
                    'grade_key': grade_key,
                    'tier': tier,
                    'updated': updated,
                    'source_url': url,
                    'confidence': 0.90,
                    'valid': model_code == model_info['code'],
                })
                break  # Only first tier
    
    return {
        'candidates': candidates,
        'total': len(candidates),
        'valid': sum(1 for c in candidates if c['valid']),
        'invalid': sum(1 for c in candidates if not c['valid']),
    }


if __name__ == '__main__':
    url = 'https://www.nissan.co.th/en/vehicles/new-vehicles/march.html'
    result = extract_nissan_prices(url)
    
    print(f"Nissan Price Extraction: {result['total']} candidates, {result['valid']} valid, {result['invalid']} invalid")
    print()
    
    for c in result.get('candidates', []):
        status = '✓' if c['valid'] else '✗ CODE MISMATCH'
        print(f"  {c['model_name']:<30} {c['price']:>10,} THB | {status}")
        print(f"    key={c['model_key']} code={c['actual_code']} expected={c['expected_code']}")
    
    # Save candidates
    with open('/home/ubuntu/Projects/thai-car-intelligence/storage/research/nissan-safe-candidates.json', 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved to storage/research/nissan-safe-candidates.json")
