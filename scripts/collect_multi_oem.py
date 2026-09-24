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
import tempfile
from datetime import datetime, timezone

# Add lib to path for provenance module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from thai_factory.acquisition.provenance import get_provenance_for_fixture

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




def load_manifest():
    """Load acquisition manifest with real capture timestamps."""
    path = f"{FIXTURE_DIR}/acquisition_manifest.json"
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def get_fixture_provenance(artifact_path):
    """Get provenance from sidecar (preferred) or legacy manifest."""
    legacy_manifest = f"{FIXTURE_DIR}/acquisition_manifest.json"
    return get_provenance_for_fixture(artifact_path, legacy_manifest_path=legacy_manifest)

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
    
    # Add provenance from sidecar/legacy manifest
    prov = get_fixture_provenance(fixture_path)
    for obs in observations:
        obs['source']['captured_at'] = prov['captured_at']
        obs['source']['provenance_state'] = prov['provenance_state']
        obs['source']['artifact_sha256'] = prov.get('sha256') or hashlib.sha256(open(fixture_path, 'rb').read()).hexdigest()
    
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
                "artifact_sha256": hashlib.sha256(open(artifact, 'rb').read()).hexdigest() if os.path.exists(artifact) else None,
                "captured_at": get_fixture_provenance(artifact)["captured_at"],
                "provenance_state": get_fixture_provenance(artifact)["provenance_state"],
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
    """Collect from Nissan — DOM extraction from sidecar-verified recapture (new official domain)."""
    print("=== Nissan Thailand Official (sidecar-verified recapture) ===")
    html, error = load_fixture("nissan_new_home")
    if error:
        print(f"  {error}")
        return []

    results, artifact = extract_from_html(html, "nissan_new_home", NISSAN_JS, fixture_path=f"{FIXTURE_DIR}/nissan_new_home_page.html")
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
                "url": "https://www.nissan.co.th/",
                "name": "Nissan Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "playwright_dom",
                "artifact_path": artifact,
                "artifact_sha256": hashlib.sha256(open(artifact, 'rb').read()).hexdigest() if os.path.exists(artifact) else None,
                "captured_at": get_fixture_provenance(artifact)["captured_at"],
                "provenance_state": get_fixture_provenance(artifact)["provenance_state"],
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
                "captured_at": get_fixture_provenance(artifact)["captured_at"],
                "provenance_state": get_fixture_provenance(artifact)["provenance_state"],
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
                "captured_at": get_fixture_provenance(artifact)["captured_at"],
                "provenance_state": get_fixture_provenance(artifact)["provenance_state"],
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
        let price = null;
        const m1 = text.match(/เริ่มต้น\\s*฿([\\d,]+)/);
        const m2 = text.match(/From THB([\\d,]+)/);
        if (m1) price = parseInt(m1[1].replace(/,/g, ''));
        else if (m2) price = parseInt(m2[1].replace(/,/g, ''));
        if (!price || price < 500000 || price > 20000000) return;

        let model = null;
        const bodyType = card.querySelector('.cmp-allmodelscarddetail__body-type');
        const series = card.querySelector('.cmp-allmodelscarddetail__series');
        if (bodyType && series) {
            const addLabel = card.querySelector('.cmp-allmodelscarddetail__additional-label');
            model = [bodyType, addLabel, series]
                .map(x => x ? x.textContent.trim() : '')
                .filter(Boolean).join(' ').replace(/\\s+/g, ' ').trim();
        } else {
            const nameEl = card.querySelector('.cmp-allmodelscarddetail__wrapper, h2, h3');
            if (!nameEl) return;
            model = nameEl.textContent.trim().replace(/\\s+/g, ' ');
            const modelMatch = model.match(/^(.*?)(?:รุ่นรถยนต์|รถยนต์ M)/);
            if (modelMatch) model = modelMatch[1].trim();
        }

        if (!model || model.length < 2 || model.includes('฿') || model.includes('THB')) return;

        const path = [];
        let el = card;
        while (el && el !== document.body) {
            const childIdx = Array.from(el.parentElement.children).indexOf(el);
            path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (childIdx + 1) + ')');
            el = el.parentElement;
        }
        items.push({ model: model, price: price, cardIndex: idx, domPath: path.join(' > '),
                     evidence: text.trim().replace(/\\s+/g, ' ').substring(0, 150) });
    });
    return items;
})()
"""


def collect_bmw():
    """Collect from BMW — DOM extraction from sidecar-verified recapture artifact."""
    print("=== BMW Thailand Official (sidecar-verified recapture) ===")
    artifact_file = f"{FIXTURE_DIR}/bmw_all_models_verified.html"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    with open(artifact_file) as f:
        html = f.read()

    results, artifact = extract_from_html(html, "bmw_models_verified", BMW_JS, fixture_path=artifact_file)
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
                "url": "https://www.bmw.co.th/en/all-models.html",
                "name": "BMW Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "playwright_dom",
                "artifact_path": artifact,
                "artifact_sha256": artifact_hash,
                "captured_at": get_fixture_provenance(artifact)["captured_at"],
                "provenance_state": get_fixture_provenance(artifact)["provenance_state"],
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



# ─── Lexus Adapter (DOM — ul.tab__item_models > li) ───
def collect_lexus():
    """Collect from Lexus — ul.tab__item_models cards from fixture."""
    print("=== Lexus Thailand Official (DOM) ===")
    html, err = load_fixture("lexus_models")
    if err:
        print(f"  {err}")
        return []
    
    from bs4 import BeautifulSoup
    import re
    
    soup = BeautifulSoup(html, 'html.parser')
    model_list = soup.select_one('ul.tab__item_models')
    
    if not model_list:
        print("  No model list found")
        return []
    
    observations = []
    artifact = f"{FIXTURE_DIR}/lexus_models_page.html"
    prov = get_fixture_provenance(artifact)
    
    for li in model_list.find_all('li', recursive=False):
        text = li.get_text().strip()
        
        # Extract model name (first uppercase-starting token)
        model_match = re.match(r'^([A-Z][A-Za-z0-9]*)', text)
        if not model_match:
            continue
        model = model_match.group(1)
        
        # Extract price
        price_match = re.search(r'(?:เริ่มต้น|ราคา)\s*([\d,]+)', text)
        if not price_match:
            continue
        price = int(price_match.group(1).replace(',', ''))
        
        # Determine price type
        is_starting = 'เริ่มต้น' in text
        
        # Build DOM path
        path = []
        el = li
        while el and el.name and el.name != 'body':
            parent = el.parent
            if parent:
                child_idx = list(parent.children).index(el) + 1
                path.insert(0, f"{el.name}:nth-child({child_idx})")
            el = parent
        
        observations.append({
            "source": {
                "name": "Lexus Thailand Official",
                "url": "https://www.lexus.co.th/th.html",
                "acquisition_method": "playwright_fixture",
                "artifact_path": artifact,
                "artifact_sha256": prov.get('sha256') or hashlib.sha256(open(artifact, 'rb').read()).hexdigest(),
                "captured_at": prov["captured_at"],
                "provenance_state": prov["provenance_state"],
                "class": "OEM_OFFICIAL",
            },
            "identity": {
                "level": "MODEL",
                "identity_level": "MODEL",
                "model_raw": model,
                "variant_raw": None,
            },
            "price": {
                "value_thb": price,
                "price_type": "MSRP_STARTING" if is_starting else "EXACT_VARIANT",
                "type": "MSRP_STARTING" if is_starting else "EXACT_VARIANT",
                "currency": "THB",
                "currentness": "UNKNOWN",
            },
            "evidence": {
                "excerpt": text[:500],
                "evidence_locator": {
                    "canonical_locator": ' > '.join(path),
                    "convenience_selector": f"ul.tab__item_models > li # {model}",
                },
            },
        })
    
    print(f"  Extracted: {len(observations)} models from fixture")
    return observations




# ─── Honda Models Page Adapter (DOM — model cards with เริ่มต้น) ───
def collect_honda_models():
    """Collect from Honda models page — model cards with starting price."""
    print("=== Honda Models Page (DOM) ===")
    html, err = load_fixture("honda_models")
    if err:
        print(f"  {err}")
        return []
    
    from bs4 import BeautifulSoup
    import re
    
    soup = BeautifulSoup(html, 'html.parser')
    
    observations = []
    artifact = f"{FIXTURE_DIR}/honda_models_page.html"
    prov = get_fixture_provenance(artifact)
    
    # Find all elements with starting price
    price_elements = soup.find_all(string=re.compile(r'เริ่มต้น\s*[\d,]+'))
    
    seen = set()
    for elem in price_elements:
        # Walk up to find compact card
        card = elem.parent
        for depth in range(3):
            if not card or not card.parent:
                break
            
            card_text = card.get_text()
            
            # Check for compact card with model + price
            if len(card_text) < 200:
                model_match = re.search(r'(?:ใหม่|New)?\s*([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)*)\s*เริ่มต้น\s*([\d,]+)', card_text)
                if model_match:
                    model = model_match.group(1).strip()
                    price = int(model_match.group(2).replace(',', ''))
                    
                    if model not in seen:
                        seen.add(model)
                        
                        # Build DOM path
                        path = []
                        el = card
                        while el and el.name and el.name != 'body':
                            parent = el.parent
                            if parent:
                                children = [c for c in parent.children if c.name]
                                try:
                                    child_idx = children.index(el) + 1
                                    path.insert(0, f"{el.name}:nth-child({child_idx})")
                                except:
                                    pass
                            el = parent
                        
                        observations.append({
                            "source": {
                                "name": "Honda Models Page",
                                "url": "https://www.honda.co.th/models",
                                "acquisition_method": prov.get('acquisition_method', 'playwright_fixture'),
                                "artifact_path": artifact,
                                "artifact_sha256": prov.get('sha256') or hashlib.sha256(open(artifact, 'rb').read()).hexdigest(),
                                "captured_at": prov["captured_at"],
                                "provenance_state": prov["provenance_state"],
                                "class": "OEM_OFFICIAL",
                            },
                            "identity": {
                                "level": "MODEL",
                                "identity_level": "MODEL",
                                "model_raw": model,
                                "variant_raw": None,
                            },
                            "price": {
                                "value_thb": price,
                                "price_type": "MSRP_STARTING",
                                "type": "MSRP_STARTING",
                                "currency": "THB",
                                "currentness": "UNKNOWN",
                            },
                            "evidence": {
                                "excerpt": card_text[:500],
                                "evidence_locator": {
                                    "canonical_locator": ' > '.join(path),
                                    "convenience_selector": f"div # {model}",
                                },
                            },
                        })
                    break
            
            card = card.parent
    
    print(f"  Extracted: {len(observations)} models from fixture")
    return observations


# ─── MITSUBISHI adapter (DOM) ───

MITSUBISHI_JS = """
(() => {
    const items = [];
    const seen = new Set();
    const prices = document.querySelectorAll('[class*="navLinkPrice"]');
    prices.forEach((p, idx) => {
        const a = p.closest('a');
        if (!a) return;
        const at = a.textContent.replace(/\\s+/g, ' ').trim();
        if (!at.includes('ราคาเริ่มต้น')) return;
        const pm = at.match(/฿\\s*([\\d,]{6,})/);
        if (!pm) return;
        const price = parseInt(pm[1].replace(/,/g, ''));
        if (price < 100000 || price > 10000000) return;
        const model = at.split('ราคาเริ่มต้น')[0].trim();
        if (!model) return;
        const key = model + ':' + price;
        if (seen.has(key)) return;
        seen.add(key);
        const path = [];
        let el = a;
        while (el && el !== document.body) {
            const i = Array.from(el.parentElement.children).indexOf(el);
            path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (i + 1) + ')');
            el = el.parentElement;
        }
        items.push({ model: model, price: price, cardIndex: idx, domPath: path.join(' > '),
                     evidence: at.substring(0, 200) });
    });
    return items;
})()
"""

# ─── SUZUKI adapter (DOM) ───

SUZUKI_JS = """
(() => {
    const items = [];
    const seen = new Set();
    const cards = document.querySelectorAll('div.product-main-content');
    cards.forEach((card, idx) => {
        const t = card.textContent.replace(/\\s+/g, ' ').trim();
        const mm = t.match(/^([A-Za-z][A-Za-z0-9 \\-]*?)\\s*(?=[\\u0E00-\\u0E7F]|\\d{1,3},\\d{3})/);
        if (!mm) return;
        const model = mm[1].trim();
        const h4 = card.querySelector('h4');
        if (!h4) return;
        const ht = h4.textContent.replace(/\\s+/g, ' ').trim();
        const pm = ht.match(/(\\d[\\d,]{4,})/);
        if (!pm) return;
        const price = parseInt(pm[1].replace(/,/g, ''));
        if (price < 100000 || price > 10000000) return;
        const key = model + ':' + price;
        if (seen.has(key)) return;
        seen.add(key);
        const path = [];
        let el = card;
        while (el && el !== document.body) {
            const i = Array.from(el.parentElement.children).indexOf(el);
            path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (i + 1) + ')');
            el = el.parentElement;
        }
        items.push({ model: model, price: price, starting: ht.includes('เริ่มต้น'),
                     cardIndex: idx, domPath: path.join(' > '), evidence: t.substring(0, 200) });
    });
    return items;
})()
"""

# ─── MINI adapter (DOM) ───

MINI_JS = """
(() => {
    const items = [];
    const seen = new Set();
    const nodes = document.querySelectorAll('div.md-ppni-item-inner');
    nodes.forEach((item, idx) => {
        const clone = item.cloneNode(true);
        clone.querySelectorAll('style, script, noscript').forEach(n => n.remove());
        const t = clone.textContent.replace(/\\s+/g, ' ').trim();
        const mm = t.match(/^([^0-9]*?)(?=\\d{1,3},\\d{3})/);
        if (!mm) return;
        const model = mm[1].trim();
        if (!model) return;
        let msrp = null;
        const cands = item.querySelectorAll('span, strong');
        for (const el of cands) {
            const txt = el.textContent.replace(/\\s+/g, ' ').trim();
            if (el.children.length === 0 && /^[\\d,]{6,9}\\s*฿$/.test(txt)) {
                msrp = parseInt(txt.replace(/[^\\d]/g, ''));
                break;
            }
        }
        if (msrp === null) return;
        if (msrp < 100000 || msrp > 10000000) return;
        if (!/From\\s+[\\d,]+\\s*฿/.test(t)) return;
        const key = model + ':' + msrp;
        if (seen.has(key)) return;
        seen.add(key);
        const path = [];
        let el = item;
        while (el && el !== document.body) {
            const i = Array.from(el.parentElement.children).indexOf(el);
            path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (i + 1) + ')');
            el = el.parentElement;
        }
        items.push({ model: model, price: msrp, cardIndex: idx, domPath: path.join(' > '),
                     evidence: t.substring(0, 200) });
    });
    return items;
})()
"""

# ─── DEEPAL adapter (DOM) ───

DEEPAL_JS = """
(() => {
    const items = [];
    const seen = new Set();
    const cards = document.querySelectorAll('div.swiper-slide.bg-changan-primary');
    cards.forEach((card, idx) => {
        const link = card.querySelector('a[href*="-th"]');
        if (!link) return;
        const href = link.getAttribute('href') || '';
        const hm = href.match(/\\/([a-z0-9]+)\\/([a-z0-9\\-]+?)-th\\/?$/);
        if (!hm) return;
        const brandSeg = hm[1];
        const model = hm[2];
        const t = card.textContent.replace(/\\s+/g, ' ').trim();
        if (!t.includes('ราคาเริ่มต้น')) return;
        const pm = t.match(/([\\d][\\d,]{5,})\\s*บาท/);
        if (!pm) return;
        const price = parseInt(pm[1].replace(/,/g, ''));
        if (price < 100000 || price > 10000000) return;
        const key = model + ':' + price;
        if (seen.has(key)) return;
        seen.add(key);
        const path = [];
        let el = card;
        while (el && el !== document.body) {
            const i = Array.from(el.parentElement.children).indexOf(el);
            path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (i + 1) + ')');
            el = el.parentElement;
        }
        items.push({ model: model, brandSeg: brandSeg, price: price, cardIndex: idx,
                     domPath: path.join(' > '),
                     evidence: (t + ' | link: ' + href).substring(0, 240) });
    });
    return items;
})()
"""

def collect_mitsubishi():
    """Collect from Mitsubishi Thailand Official — DOM extraction from sidecar-verified capture."""
    print("=== Mitsubishi Thailand Official (DOM) ===")
    artifact_file = f"{FIXTURE_DIR}/mitsubishi_home_page.html"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    with open(artifact_file) as f:
        html = f.read()

    results, artifact = extract_from_html(html, "mitsubishi_home_page", MITSUBISHI_JS, fixture_path=artifact_file)
    if not results:
        print("  Extraction returned no results")
        return []

    with open(artifact, 'rb') as f:
        artifact_hash = hashlib.sha256(f.read()).hexdigest()
    prov = get_fixture_provenance(artifact)

    observations = []
    seen = set()
    for item in results:
        model = item['model']
        key = f"{model}:{item['price']}"
        if key in seen:
            continue
        seen.add(key)
        price_type = 'MSRP_STARTING'

        observations.append({
            "observation_id": hashlib.sha256(f"mitsubishi:{model}:{item['price']}:{item['domPath']}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": "https://www.mitsubishi-motors.co.th/",
                "name": "Mitsubishi Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "playwright_dom",
                "artifact_path": artifact,
                "artifact_sha256": artifact_hash,
                "captured_at": prov["captured_at"],
                "provenance_state": prov["provenance_state"],
            },
            "identity": {
                "brand_raw": "Mitsubishi",
                "brand_normalized": "mitsubishi",
                "model_raw": model,
                "variant_raw": None,
                "year": None,
                "fuel_powertrain_raw": None,
                "model_normalized": model.lower().replace(" ", "-"),
                "variant_normalized": None,
                "identity_level": "MODEL",
            },
            "price": {
                "value_thb": item['price'],
                "type": price_type,
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

def collect_suzuki():
    """Collect from Suzuki Thailand Official — DOM extraction from sidecar-verified capture."""
    print("=== Suzuki Thailand Official (DOM) ===")
    artifact_file = f"{FIXTURE_DIR}/suzuki_home_page.html"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    with open(artifact_file) as f:
        html = f.read()

    results, artifact = extract_from_html(html, "suzuki_home_page", SUZUKI_JS, fixture_path=artifact_file)
    if not results:
        print("  Extraction returned no results")
        return []

    with open(artifact, 'rb') as f:
        artifact_hash = hashlib.sha256(f.read()).hexdigest()
    prov = get_fixture_provenance(artifact)

    observations = []
    seen = set()
    for item in results:
        model = item['model']
        key = f"{model}:{item['price']}"
        if key in seen:
            continue
        seen.add(key)
        price_type = 'MSRP_STARTING' if item.get('starting') else 'MSRP'

        observations.append({
            "observation_id": hashlib.sha256(f"suzuki:{model}:{item['price']}:{item['domPath']}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": "https://www.suzuki.co.th/",
                "name": "Suzuki Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "playwright_dom",
                "artifact_path": artifact,
                "artifact_sha256": artifact_hash,
                "captured_at": prov["captured_at"],
                "provenance_state": prov["provenance_state"],
            },
            "identity": {
                "brand_raw": "Suzuki",
                "brand_normalized": "suzuki",
                "model_raw": model,
                "variant_raw": None,
                "year": None,
                "fuel_powertrain_raw": None,
                "model_normalized": model.lower().replace(" ", "-"),
                "variant_normalized": None,
                "identity_level": "MODEL",
            },
            "price": {
                "value_thb": item['price'],
                "type": price_type,
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

def collect_mini():
    """Collect from MINI Thailand Official — DOM extraction from sidecar-verified capture."""
    print("=== MINI Thailand Official (DOM) ===")
    artifact_file = f"{FIXTURE_DIR}/mini_home_page.html"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    with open(artifact_file) as f:
        html = f.read()

    results, artifact = extract_from_html(html, "mini_home_page", MINI_JS, fixture_path=artifact_file)
    if not results:
        print("  Extraction returned no results")
        return []

    with open(artifact, 'rb') as f:
        artifact_hash = hashlib.sha256(f.read()).hexdigest()
    prov = get_fixture_provenance(artifact)

    observations = []
    seen = set()
    for item in results:
        model = item['model']
        key = f"{model}:{item['price']}"
        if key in seen:
            continue
        seen.add(key)
        price_type = 'MSRP_STARTING'

        observations.append({
            "observation_id": hashlib.sha256(f"mini:{model}:{item['price']}:{item['domPath']}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": "https://www.mini.co.th/",
                "name": "MINI Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "playwright_dom",
                "artifact_path": artifact,
                "artifact_sha256": artifact_hash,
                "captured_at": prov["captured_at"],
                "provenance_state": prov["provenance_state"],
            },
            "identity": {
                "brand_raw": "MINI",
                "brand_normalized": "mini",
                "model_raw": model,
                "variant_raw": None,
                "year": None,
                "fuel_powertrain_raw": None,
                "model_normalized": model.lower().replace(" ", "-"),
                "variant_normalized": None,
                "identity_level": "MODEL",
            },
            "price": {
                "value_thb": item['price'],
                "type": price_type,
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

def collect_deepal():
    """Collect from Changan Thailand Official — DOM extraction from sidecar-verified capture."""
    print("=== Changan Thailand Official (DOM) ===")
    artifact_file = f"{FIXTURE_DIR}/changan_home_page.html"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    with open(artifact_file) as f:
        html = f.read()

    results, artifact = extract_from_html(html, "changan_home_page", DEEPAL_JS, fixture_path=artifact_file)
    if not results:
        print("  Extraction returned no results")
        return []

    with open(artifact, 'rb') as f:
        artifact_hash = hashlib.sha256(f.read()).hexdigest()
    prov = get_fixture_provenance(artifact)

    observations = []
    seen = set()
    for item in results:
        model = item['model']
        key = f"{model}:{item['price']}"
        if key in seen:
            continue
        seen.add(key)
        price_type = 'MSRP_STARTING'

        observations.append({
            "observation_id": hashlib.sha256(f"deepal:{model}:{item['price']}:{item['domPath']}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": "https://www.changan.co.th/",
                "name": "Changan Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "playwright_dom",
                "artifact_path": artifact,
                "artifact_sha256": artifact_hash,
                "captured_at": prov["captured_at"],
                "provenance_state": prov["provenance_state"],
            },
            "identity": {
                "brand_raw": item.get("brandSeg", "thdeepal"),
                "brand_normalized": "deepal",
                "model_raw": model,
                "variant_raw": None,
                "year": None,
                "fuel_powertrain_raw": None,
                "model_normalized": model.lower().replace(" ", "-"),
                "variant_normalized": None,
                "identity_level": "MODEL",
            },
            "price": {
                "value_thb": item['price'],
                "type": price_type,
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

# ─── MG Adapter (DOM — promo cards with source-labelled starting price) ───

MG_JS = """
(() => {
    const items = [];
    const seen = new Set();
    const cards = document.querySelectorAll('div.p-5');
    cards.forEach((card, idx) => {
        const spans = card.querySelectorAll('span.font-bold');
        spans.forEach(span => {
            const t = span.textContent.replace(/\\s+/g, ' ').trim();
            if (!t.includes('ราคา') || !t.includes('เริ่มต้น')) return;
            const pm = t.match(/([\\d][\\d,]{4,})\\s*บาท/);
            if (!pm) return;
            const price = parseInt(pm[1].replace(/,/g, ''));
            if (price < 100000 || price > 10000000) return;
            const mm = t.match(/MG\\s?[A-Za-z0-9]+(?:\\s+[A-Za-z0-9]+)*/);
            if (!mm) return;
            const model = mm[0].trim();
            const key = model + ':' + price;
            if (seen.has(key)) return;
            seen.add(key);
            const path = [];
            let el = span;
            while (el && el !== document.body) {
                const childIdx = Array.from(el.parentElement.children).indexOf(el);
                path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (childIdx + 1) + ')');
                el = el.parentElement;
            }
            items.push({ model: model, price: price, cardIndex: idx, domPath: path.join(' > '),
                         evidence: t.substring(0, 200) });
        });
    });
    return items;
})()
"""


def collect_mg():
    """Collect from MG — DOM extraction from sidecar-verified capture."""
    print("=== MG Thailand Official (DOM) ===")
    artifact_file = f"{FIXTURE_DIR}/mg_home_page.html"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    with open(artifact_file) as f:
        html = f.read()

    results, artifact = extract_from_html(html, "mg_home", MG_JS, fixture_path=artifact_file)
    if not results:
        print("  Extraction returned no results")
        return []

    with open(artifact, 'rb') as f:
        artifact_hash = hashlib.sha256(f.read()).hexdigest()
    prov = get_fixture_provenance(artifact)

    observations = []
    seen = set()
    for item in results:
        model = item['model']
        key = f"{model}:{item['price']}"
        if key in seen:
            continue
        seen.add(key)

        observations.append({
            "observation_id": hashlib.sha256(f"mg:{model}:{item['price']}:{item['domPath']}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": "https://www.mgcars.com/th/",
                "name": "MG Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "playwright_dom",
                "artifact_path": artifact,
                "artifact_sha256": artifact_hash,
                "captured_at": prov["captured_at"],
                "provenance_state": prov["provenance_state"],
            },
            "identity": {
                "brand_raw": "MG",
                "model_raw": model,
                "variant_raw": None,
                "year": None,
                "fuel_powertrain_raw": None,
                "brand_normalized": "mg",
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
    lexus = collect_lexus()
    all_observations.extend(lexus)
    honda_models = collect_honda_models()
    all_observations.extend(honda_models)
    mg = collect_mg()
    all_observations.extend(mg)

    mitsubishi = collect_mitsubishi()
    all_observations.extend(mitsubishi)

    suzuki = collect_suzuki()
    all_observations.extend(suzuki)

    mini = collect_mini()
    all_observations.extend(mini)

    deepal = collect_deepal()
    all_observations.extend(deepal)

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
    print(f"Lexus (DOM fixture): {len(lexus)}")
    print(f"Honda Models (DOM fixture): {len(honda_models)}")
    print(f"MG (DOM fixture): {len(mg)}")
    print(f"Mitsubishi (DOM fixture): {len(mitsubishi)}")
    print(f"Suzuki (DOM fixture): {len(suzuki)}")
    print(f"MINI (DOM fixture): {len(mini)}")
    print(f"Deepal via Changan (DOM fixture): {len(deepal)}")
    print(f"Genuinely extracted from fixtures: {len(toyota) + len(mazda) + len(nissan) + len(honda) + len(isuzu) + len(bmw) + len(lexus) + len(honda_models) + len(mg) + len(mitsubishi) + len(suzuki) + len(mini) + len(deepal)}")
    print(f"Total: {len(all_observations) + len(existing)}")

    # Write staging
    os.makedirs("audit/data-staging", exist_ok=True)
    with open(STAGING_FILE, 'w') as f:
        for obs in all_observations + existing:
            f.write(json.dumps(obs) + '\n')

    oem_obs = toyota + mazda + nissan + honda + isuzu + bmw + lexus + honda_models + mg + mitsubishi + suzuki + mini + deepal
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "fixture_based_extraction": len(oem_obs),
            "acquisition_verified": sum(1 for o in oem_obs if o['source'].get('provenance_state') == 'ACQUISITION_VERIFIED'),
            "legacy_unverified": sum(1 for o in oem_obs if o['source'].get('provenance_state') == 'LEGACY_UNVERIFIED'),
            "from_existing_structured_data": len(existing),
        },
        "by_source": {"toyota": len(toyota), "mazda": len(mazda), "nissan": len(nissan), "honda": len(honda),
                       "isuzu": len(isuzu), "bmw": len(bmw), "lexus": len(lexus),
                       "honda_models": len(honda_models), "mg": len(mg), "mitsubishi": len(mitsubishi), "suzuki": len(suzuki), "mini": len(mini), "deepal": len(deepal)},
        "total": len(all_observations) + len(existing),
    }
    with open("audit/data-staging/summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nWrote {len(all_observations) + len(existing)} observations to {STAGING_FILE}")


if __name__ == '__main__':
    main()
