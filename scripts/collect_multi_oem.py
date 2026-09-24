#!/usr/bin/env python3
"""
Real multi-OEM acquisition — fixture-based with proper DOM selectors.

Each adapter:
1. Loads a committed HTML fixture (or fetches live)
2. Extracts using DOM selectors tied to specific card/record elements
3. Every observation has: artifact_path + selector + model + price from SAME element
4. No positional/proximity line scanning
"""
import subprocess
import json
import re
import os
import sys
import hashlib
from datetime import datetime, timezone

FIXTURE_DIR = "tests/fixtures/oem-artifacts"
ARTIFACT_DIR = "audit/data-staging/raw-artifacts"
STAGING_FILE = "audit/data-staging/vehicle_observations.jsonl"


def load_fixture(name):
    """Load a committed fixture HTML file."""
    path = f"{FIXTURE_DIR}/{name}_page.html"
    if not os.path.exists(path):
        return None, f"Fixture not found: {path}"
    with open(path) as f:
        return f.read(), None


def extract_from_html(html, name, js_extract, fixture_path=None):
    """Load HTML into browser, run JS extraction, return results + artifact info."""
    if fixture_path:
        artifact_path = fixture_path
    else:
        os.makedirs(ARTIFACT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        h = hashlib.sha256(html.encode()).hexdigest()[:8]
        artifact_path = f"{ARTIFACT_DIR}/{name}_{ts}_{h}.html"
        with open(artifact_path, 'w') as f:
            f.write(html)

    script_content = f'''
import asyncio
import json
from playwright.async_api import async_playwright

HTML_CONTENT = {repr(html)}
EXTRACT_JS = {repr(js_extract)}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.set_content(HTML_CONTENT)
            result = await page.evaluate(EXTRACT_JS)
            print(json.dumps(result))
        except Exception as e:
            print(json.dumps({{"error": str(e)}}))
        finally:
            await browser.close()

asyncio.run(main())
'''
    with open('/tmp/extract_js.py', 'w') as f:
        f.write(script_content)

    try:
        result = subprocess.run(['python3', '/tmp/extract_js.py'], capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout.strip())
            return data, artifact_path
    except:
        pass

    return None, artifact_path


# ─── Toyota Adapter (JSON-LD) ───
def collect_toyota():
    """Collect from Toyota — JSON-LD structured data from fixture."""
    print("=== Toyota Thailand Official (JSON-LD) ===")
    sys.path.insert(0, 'scripts')
    from collect_real_data import extract_toyota_prices

    fixture_path = f"{FIXTURE_DIR}/toyota_page.html"
    if not os.path.exists(fixture_path):
        print("  No Toyota fixture found")
        return []

    with open(fixture_path) as f:
        html = f.read()

    observations = extract_toyota_prices(
        html,
        "https://www.toyota.co.th/en/pricelist",
        fixture_path
    )
    print(f"  Extracted: {len(observations)} variants from fixture")
    return observations


# ─── Mazda Adapter (DOM — .cardCarModelMega_content) ───
MAZDA_JS = """
(() => {
    const cards = document.querySelectorAll('.cardCarModelMega_content');
    return Array.from(cards).map((card, idx) => {
        const text = card.textContent;
        const priceMatch = text.match(/([\d,]+)\s*THB/);
        const modelEl = card.querySelector('h3, h4, .model-name, strong');
        const modelText = modelEl ? modelEl.textContent.trim() : text.split('Starting')[0].trim();
        return {
            model: modelText.replace(/\\u200b/g, ''),
            price: priceMatch ? parseInt(priceMatch[1].replace(/,/g, '')) : null,
            selector: '.cardCarModelMega_content:nth-child(' + (idx + 1) + ')',
            evidence: text.trim().replace(/\\s+/g, ' ')
        };
    }).filter(item => item.price && item.price > 100000);
})()
"""


def collect_mazda():
    """Collect from Mazda — DOM extraction from fixture."""
    print("=== Mazda Thailand Official (DOM) ===")
    html, error = load_fixture("mazda")
    if error:
        print(f"  {error}")
        return []

    results, artifact = extract_from_html(html, "mazda", MAZDA_JS, fixture_path=f"{FIXTURE_DIR}/mazda_page.html")
    if not results:
        print("  Extraction returned no results")
        return []

    seen = set()
    observations = []
    for item in results:
        model = item['model']
        if model in seen:
            continue
        seen.add(model)

        observations.append({
            "observation_id": hashlib.sha256(f"mazda:{model}:{item['price']}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": "https://www.mazda.co.th/en/vehicles",
                "name": "Mazda Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "playwright_dom",
                "artifact_path": artifact,
            },
            "identity": {
                "brand_raw": "Mazda",
                "model_raw": model,
                "variant_raw": None,
                "year": None,
                "fuel_powertrain_raw": None,
                "brand_normalized": "mazda",
                "model_normalized": model.lower().replace(" ", "-"),
                "variant_normalized": None,
                "identity_level": "MODEL",
            },
            "price": {
                "value_thb": item['price'],
                "type": "MSRP_STARTING",
                "currency": "THB",
                "currentness": "UNKNOWN",
            },
            "specs": {},
            "raw_labels": {},
            "evidence_excerpt": item['evidence'],
            "evidence_locator": {
                "artifact_path": artifact,
                "selector": item['selector'],
                "method": "dom_query",
            },
        })

    print(f"  Extracted: {len(observations)} unique models from fixture")
    return observations


# ─── Nissan Adapter (DOM — .vehicle-in-category-wrapper) ───
NISSAN_JS = """
(() => {
    const items = [];
    const priceEls = document.querySelectorAll('.price-figure');
    const seen = new Set();
    
    for (const priceEl of priceEls) {
        const parent = priceEl.closest('.vehicle-in-category-wrapper');
        if (!parent) continue;
        
        const nameEl = parent.querySelector('h2, h3, h4, [class*="name"], [class*="title"]');
        if (!nameEl) continue;
        
        const name = nameEl.textContent.trim();
        const priceText = priceEl.textContent.trim();
        const priceMatch = priceText.match(/[\\d,]+/);
        const price = priceMatch ? parseInt(priceMatch[0].replace(/,/g, '')) : null;
        
        if (!price || price < 100000 || price > 10000000) continue;
        
        const key = name + ':' + price;
        if (seen.has(key)) continue;
        seen.add(key);
        
        items.push({
            model: name,
            price: price,
            selector: '.vehicle-in-category-wrapper:has(.price-figure)',
            evidence: parent.textContent.trim().replace(/\\s+/g, ' ').substring(0, 200)
        });
    }
    return items;
})()
"""


def collect_nissan():
    """Collect from Nissan — DOM extraction from fixture."""
    print("=== Nissan Thailand Official (DOM) ===")
    html, error = load_fixture("nissan")
    if error:
        print(f"  {error}")
        return []

    results, artifact = extract_from_html(html, "nissan", NISSAN_JS, fixture_path=f"{FIXTURE_DIR}/nissan_page.html")
    if not results:
        print("  Extraction returned no results")
        return []

    observations = []
    for item in results:
        model = item['model']
        if model in ["รุ่นรถทั้งหมด", "เลือกรถนิสสันของคุณ"]:
            continue

        observations.append({
            "observation_id": hashlib.sha256(f"nissan:{model}:{item['price']}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": "https://www.nissan.co.th",
                "name": "Nissan Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "playwright_dom",
                "artifact_path": artifact,
            },
            "identity": {
                "brand_raw": "Nissan",
                "model_raw": model,
                "variant_raw": None,
                "year": None,
                "fuel_powertrain_raw": None,
                "brand_normalized": "nissan",
                "model_normalized": model.lower().replace(" ", "-"),
                "variant_normalized": None,
                "identity_level": "MODEL",
            },
            "price": {
                "value_thb": item['price'],
                "type": "MSRP_STARTING",
                "currency": "THB",
                "currentness": "UNKNOWN",
            },
            "specs": {},
            "raw_labels": {},
            "evidence_excerpt": item['evidence'],
            "evidence_locator": {
                "artifact_path": artifact,
                "selector": item['selector'],
                "method": "dom_query",
            },
        })

    print(f"  Extracted: {len(observations)} models from fixture")
    return observations






# ─── Isuzu Adapter (DOM — figure cards) ───
ISUZU_JS = """
(() => {
    const items = [];
    const figures = document.querySelectorAll('figure');
    
    figures.forEach((fig, idx) => {
        const text = fig.textContent;
        const priceMatch = text.match(/([\\d,]+)\\s*THB/);
        if (!priceMatch) return;
        
        const price = parseInt(priceMatch[1].replace(/,/g, ''));
        if (price < 100000 || price > 10000000) return;
        
        // Extract model name from card text (before price)
        const modelMatch = text.match(/^([A-Z0-9][A-Z0-9\-\s]+?)(?:เริ่มต้น|[\\d,])/);
        const model = modelMatch ? modelMatch[1].trim() : null;
        if (!model || model.length < 2) return;
        
        // Build DOM path
        const path = [];
        let el = fig;
        while (el && el !== document.body) {
            const childIdx = Array.from(el.parentElement.children).indexOf(el);
            path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (childIdx + 1) + ')');
            el = el.parentElement;
        }
        
        items.push({
            model: model,
            price: price,
            figIndex: idx,
            domPath: path.join(' > '),
            evidence: text.trim().replace(/\\s+/g, ' ').substring(0, 150)
        });
    });
    
    return items;
})()
"""


def collect_isuzu():
    """Collect from Isuzu — DOM extraction from figure cards."""
    print("=== Isuzu Thailand Official (DOM) ===")
    html, error = load_fixture("isuzu")
    if error:
        print(f"  {error}")
        return []

    results, artifact = extract_from_html(html, "isuzu", ISUZU_JS, fixture_path=f"{FIXTURE_DIR}/isuzu_page.html")
    if not results:
        print("  Extraction returned no results")
        return []

    # Compute artifact hash
    with open(artifact, 'rb') as f:
        artifact_hash = hashlib.sha256(f.read()).hexdigest()

    observations = []
    for item in results:
        model = item['model']
        observations.append({
            "observation_id": hashlib.sha256(f"isuzu:{model}:{item['price']}:{item['domPath']}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": "https://www.isuzu-tis.com/",
                "name": "Isuzu Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "playwright_dom",
                "artifact_path": artifact,
                "artifact_sha256": artifact_hash,
                "captured_at": "2026-09-24T05:00:00Z",
            },
            "identity": {
                "brand_raw": "Isuzu",
                "model_raw": model,
                "variant_raw": None,
                "year": None,
                "fuel_powertrain_raw": None,
                "brand_normalized": "isuzu",
                "model_normalized": model.lower().replace(" ", "-"),
                "variant_normalized": None,
                "identity_level": "MODEL",
            },
            "price": {
                "value_thb": item['price'],
                "type": "MSRP_STARTING",
                "currency": "THB",
                "currentness": "UNKNOWN",
            },
            "specs": {},
            "raw_labels": {},
            "evidence_excerpt": item['evidence'],
            "evidence_locator": {
                "artifact_path": artifact,
                "artifact_sha256": artifact_hash,
                "canonical_locator": item['domPath'],
                "card_index": item['figIndex'],
                "method": "dom_card",
            },
        })

    print(f"  Extracted: {len(observations)} models from fixture")
    return observations

# ─── Honda Adapter (DOM — Grade Levels section) ───
HONDA_CITY_JS = """
(() => {
    const items = [];
    
    // Find "Grade Levels" heading
    const gradeHeading = Array.from(document.querySelectorAll('div, h2, h3, h4, span, p')).find(el => 
        el.textContent.trim() === 'Grade Levels' && el.children.length === 0
    );
    if (!gradeHeading) return items;
    
    // Walk up to find container with [data-active] cards
    let container = gradeHeading.parentElement;
    for (let i = 0; i < 5; i++) {
        if (!container) break;
        if (container.querySelectorAll('[data-active]').length >= 3) break;
        container = container.parentElement;
    }
    if (!container) return items;
    
    // Get all grade cards — each contains BOTH variant name AND price
    const cards = container.querySelectorAll('[data-active]');
    
    cards.forEach((card, idx) => {
        const text = card.textContent;
        const priceMatch = text.match(/([\\d,]+)\\s*THB/);
        if (!priceMatch) return;
        
        const price = parseInt(priceMatch[1].replace(/,/g, ''));
        if (price < 100000 || price > 10000000) return;
        
        // Get variant name from first text content
        const variantEl = card.querySelector('div:first-child');
        const variant = variantEl ? variantEl.textContent.trim().split('\\n')[0].trim() : null;
        if (!variant || variant.match(/[\\d,]/)) return;
        
        // Build deterministic DOM path
        const path = [];
        let el = card;
        while (el && el !== document.body) {
            const childIdx = Array.from(el.parentElement.children).indexOf(el);
            path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (childIdx + 1) + ')');
            el = el.parentElement;
        }
        
        items.push({
            variant: variant,
            price: price,
            dataActive: card.getAttribute('data-active'),
            cardIndex: idx,
            domPath: path.join(' > '),
            evidence: text.trim().replace(/\\s+/g, ' ').substring(0, 120)
        });
    });
    
    return items;
})()
"""


def collect_honda():
    """Collect from Honda City — DOM extraction from grade cards."""
    print("=== Honda Thailand Official (DOM) ===")
    html, error = load_fixture("honda_city")
    if error:
        print(f"  {error}")
        return []

    results, artifact = extract_from_html(html, "honda_city", HONDA_CITY_JS, fixture_path=f"{FIXTURE_DIR}/honda_city_page.html")
    if not results:
        print("  Extraction returned no results")
        return []

    # Compute artifact hash
    with open(artifact, 'rb') as f:
        artifact_hash = hashlib.sha256(f.read()).hexdigest()

    observations = []
    for item in results:
        variant = item['variant']
        observations.append({
            "observation_id": hashlib.sha256(f"honda_city:{variant}:{item['price']}:{item['domPath']}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": "https://www.honda.co.th/en/city",
                "name": "Honda Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "playwright_dom",
                "artifact_path": artifact,
                "artifact_sha256": artifact_hash,
                "captured_at": "2026-09-23T14:00:00Z",
            },
            "identity": {
                "brand_raw": "Honda",
                "model_raw": "City",
                "variant_raw": variant,
                "year": None,
                "fuel_powertrain_raw": None,
                "brand_normalized": "honda",
                "model_normalized": "city",
                "variant_normalized": variant.lower().replace(" ", "-"),
                "identity_level": "VARIANT",
            },
            "price": {
                "value_thb": item['price'],
                "type": "MSRP_STARTING",
                "currency": "THB",
                "currentness": "UNKNOWN",
            },
            "specs": {},
            "raw_labels": {},
            "evidence_excerpt": item['evidence'],
            "evidence_locator": {
                "artifact_path": artifact,
                "artifact_sha256": artifact_hash,
                "dom_path": item['domPath'],
                "card_index": item['cardIndex'],
                "data_active": item['dataActive'],
                "selector": f"[data-active='{item['dataActive']}']:nth-of-type({item['cardIndex'] + 1})",
                "method": "dom_card",
            },
        })

    print(f"  Extracted: {len(observations)} variants from fixture")
    return observations



# ─── BMW Adapter (DOM — .cmp-allmodelscard__root) ───
BMW_JS = """
(() => {
    const items = [];
    const cards = document.querySelectorAll('.cmp-allmodelscard__root');
    
    cards.forEach((card, idx) => {
        const text = card.textContent;
        const priceMatch = text.match(/เริ่มต้น\\s*฿([\\d,]+)/);
        if (!priceMatch) return;
        
        const price = parseInt(priceMatch[1].replace(/,/g, ''));
        if (price < 500000 || price > 20000000) return;
        
        const nameEl = card.querySelector('.cmp-allmodelscarddetail__wrapper, h2, h3');
        if (!nameEl) return;
        let model = nameEl.textContent.trim().replace(/\\s+/g, ' ');
        
        const modelMatch = model.match(/^(.*?)(?:รุ่นรถยนต์|รถยนต์ M)/);
        if (modelMatch) model = modelMatch[1].trim();
        
        if (!model || model.length < 2 || model.includes('฿')) return;
        
        const path = [];
        let el = card;
        while (el && el !== document.body) {
            const childIdx = Array.from(el.parentElement.children).indexOf(el);
            path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (childIdx + 1) + ')');
            el = el.parentElement;
        }
        
        items.push({
            model: model,
            price: price,
            cardIndex: idx,
            domPath: path.join(' > '),
            evidence: text.trim().replace(/\\s+/g, ' ').substring(0, 150)
        });
    });
    
    return items;
})()
"""


def collect_bmw():
    """Collect from BMW — DOM extraction from allmodelscard."""
    print("=== BMW Thailand Official (DOM) ===")
    html, error = load_fixture("bmw_models")
    if error:
        print(f"  {error}")
        return []

    results, artifact = extract_from_html(html, "bmw_models", BMW_JS, fixture_path=f"{FIXTURE_DIR}/bmw_models_page.html")
    if not results:
        print("  Extraction returned no results")
        return []

    with open(artifact, 'rb') as f:
        artifact_hash = hashlib.sha256(f.read()).hexdigest()

    observations = []
    seen = set()
    for item in results:
        model = item['model']
        key = f"{model}:{item['price']}"
        if key in seen:
            continue
        seen.add(key)
        
        observations.append({
            "observation_id": hashlib.sha256(f"bmw:{model}:{item['price']}:{item['domPath']}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": "https://www.bmw.co.th/th/all-models.html",
                "name": "BMW Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "playwright_dom",
                "artifact_path": artifact,
                "artifact_sha256": artifact_hash,
                "captured_at": "2026-09-24T05:00:00Z",
            },
            "identity": {
                "brand_raw": "BMW",
                "model_raw": model,
                "variant_raw": None,
                "year": None,
                "fuel_powertrain_raw": None,
                "brand_normalized": "bmw",
                "model_normalized": model.lower().replace(" ", "-"),
                "variant_normalized": None,
                "identity_level": "MODEL",
            },
            "price": {
                "value_thb": item['price'],
                "type": "MSRP_STARTING",
                "currency": "THB",
                "currentness": "UNKNOWN",
            },
            "specs": {},
            "raw_labels": {},
            "evidence_excerpt": item['evidence'],
            "evidence_locator": {
                "artifact_path": artifact,
                "artifact_sha256": artifact_hash,
                "canonical_locator": item['domPath'],
                "card_index": item['cardIndex'],
                "method": "dom_card",
            },
        })

    print(f"  Extracted: {len(observations)} models from fixture")
    return observations

def main():
    print("=== REAL MULTI-OEM ACQUISITION (FIXTURE-BASED) ===\n")

    all_observations = []

    toyota = collect_toyota()
    all_observations.extend(toyota)

    mazda = collect_mazda()
    all_observations.extend(mazda)

    nissan = collect_nissan()
    all_observations.extend(nissan)

    honda = collect_honda()
    all_observations.extend(honda)

    isuzu = collect_isuzu()
    all_observations.extend(isuzu)

    bmw = collect_bmw()
    all_observations.extend(bmw)

    # Load existing Fipe/OpenEV
    existing = []
    prev_staging = "audit/data-staging/vehicle_observations_prev.jsonl"
    if os.path.exists(prev_staging):
        with open(prev_staging) as f:
            for line in f:
                if line.strip():
                    obs = json.loads(line)
                    if obs.get('source', {}).get('class') in ('STRUCTURED_REF', 'MARKET_REFERENCE'):
                        existing.append(obs)

    print(f"\n=== SUMMARY ===")
    print(f"Toyota (JSON-LD fixture): {len(toyota)}")
    print(f"Mazda (DOM fixture): {len(mazda)}")
    print(f"Nissan (DOM fixture): {len(nissan)}")
    print(f"Honda (DOM fixture): {len(honda)}")
    print(f"Isuzu (DOM fixture): {len(isuzu)}")
    print(f"BMW (DOM fixture): {len(bmw)}")
    print(f"Genuinely extracted from fixtures: {len(toyota) + len(mazda) + len(nissan) + len(honda) + len(isuzu) + len(bmw)}")
    print(f"Total: {len(all_observations) + len(existing)}")

    # Write staging
    os.makedirs("audit/data-staging", exist_ok=True)
    with open(STAGING_FILE, 'w') as f:
        for obs in all_observations + existing:
            f.write(json.dumps(obs) + '\n')

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "fixture_based_extraction": len(toyota) + len(mazda) + len(nissan) + len(honda) + len(isuzu) + len(bmw),
            "from_existing_structured_data": len(existing),
        },
        "by_source": {"toyota": len(toyota), "mazda": len(mazda), "nissan": len(nissan), "honda": len(honda), "isuzu": len(isuzu), "bmw": len(bmw)},
        "total": len(all_observations) + len(existing),
    }
    with open("audit/data-staging/summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nWrote {len(all_observations) + len(existing)} observations to {STAGING_FILE}")


if __name__ == '__main__':
    main()
