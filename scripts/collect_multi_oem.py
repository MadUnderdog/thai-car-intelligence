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
import time
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
            # Wait for the parsed DOM, not for remote subresources: these saved
            # AEM pages keep absolute image/style URLs, so waiting for "load"
            # lets network latency alone fail an attempt (the intermittent
            # Suzuki "no results" the retries above were added for).
            await page.set_content(HTML_CONTENT, timeout=60000,
                                   wait_until="domcontentloaded")
            result = await page.evaluate(EXTRACT_JS)
            print(json.dumps(result))
        except Exception as e:
            print(json.dumps({{"error": str(e)}}))
        finally:
            await browser.close()

asyncio.run(main())
'''
    # Unique script path per attempt (no shared /tmp file to race on), generous
    # timeout, and retries: a transient chromium launch/set_content failure must
    # not silently hide rows (observed intermittent Suzuki "no results").
    last_err = None
    for attempt in range(3):
        script_path = os.path.join(
            tempfile.gettempdir(), f"extract_js_{name}_{os.getpid()}_{attempt}.py")
        with open(script_path, 'w') as f:
            f.write(script_content)
        try:
            result = subprocess.run(['python3', script_path],
                                    capture_output=True, text=True, timeout=90)
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                if isinstance(data, list):
                    return data, artifact_path
                last_err = data  # {"error": ...} from the browser script
            else:
                last_err = f"rc={result.returncode} stderr={result.stderr[-200:]}"
        except Exception as e:
            last_err = repr(e)
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass
        time.sleep(1 + attempt)

    print(f"  extract_from_html({name}) FAILED after 3 attempts: {last_err}")
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

    # switched to the sidecar-verified recapture of the SAME manifest URL
    # (content verified identical to the legacy capture: same 99 rows)
    fixture_path = f"{FIXTURE_DIR}/toyota_pricelist_page.html"
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
def collect_mazda():
    """Collect from Mazda — root capture: h2 'MODEL | TAGLINE' + div.infoPrice ('เริ่มต้นที่')."""
    print("=== Mazda Thailand Official (DOM, root capture) ===")
    artifact_file = f"{FIXTURE_DIR}/mazda_home_page.html"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    with open(artifact_file) as f:
        html = f.read()

    results, artifact = extract_from_html(html, "mazda_home_page", MAZDA_ROOT_JS, fixture_path=artifact_file)
    if not results:
        print("  Extraction returned no results")
        return []

    with open(artifact, 'rb') as f:
        artifact_hash = hashlib.sha256(f.read()).hexdigest()
    prov = get_fixture_provenance(artifact)

    seen = set()
    observations = []
    for item in results:
        model = item['model']
        key = f"{model}:{item['price']}"
        if key in seen:
            continue
        seen.add(key)

        observations.append({
            "observation_id": hashlib.sha256(f"mazda:{model}:{item['price']}:{item.get('selector', '')}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": prov.get("source_url", "https://www.mazda.co.th/"),
                "name": "Mazda Thailand Official",
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
            "raw_labels": {"price_text": item.get('priceText', '')},
            "evidence_excerpt": item['evidence'],
            "evidence_locator": {
                "artifact_path": artifact,
                "selector": item.get('selector'),
                "method": "dom_query",
            },
        })

    print(f"  Extracted: {len(observations)} unique model/price pairs from mazda_home_page")
    return observations


# ─── Nissan Adapter (DOM — .vehicle-in-category-wrapper) ───
NISSAN_JS = """
(() => {
    // Full document-absolute CSS path using nth-of-type per level: every card gets
    // its own path, so a locator can never resolve to a neighbouring vehicle.
    const cssPath = (el) => {
        const parts = [];
        let node = el;
        while (node && node.nodeType === 1 && node !== document.documentElement) {
            let sel = node.tagName.toLowerCase();
            const parent = node.parentElement;
            if (parent) {
                const sameTag = Array.prototype.filter.call(
                    parent.children, (c) => c.tagName === node.tagName);
                if (sameTag.length > 1) {
                    sel += ':nth-of-type(' + (sameTag.indexOf(node) + 1) + ')';
                }
            }
            parts.unshift(sel);
            node = parent;
        }
        return parts.join(' > ');
    };

    const items = [];
    const priceEls = document.querySelectorAll('.price-figure');
    const seen = new Set();

    for (let idx = 0; idx < priceEls.length; idx++) {
        const priceEl = priceEls[idx];
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
            dom_path: cssPath(parent),
            price_index: idx,
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
                "artifact_sha256": hashlib.sha256(open(artifact, 'rb').read()).hexdigest() if os.path.exists(artifact) else None,
                # convenience selector matches every card; dom_path is the canonical,
                # document-absolute locator that resolves to exactly this vehicle
                "selector": item['selector'],
                "dom_path": item.get('dom_path'),
                "price_index": item.get('price_index'),
                "method": "dom_query",
            },
        })

    print(f"  Extracted: {len(observations)} models from fixture")
    return observations






ISUZU_TIS_JS = r"""
(() => {
    const items = [];
    const figures = document.querySelectorAll('figure[data-test^="lineup-item-"]');
    const seen = new Set();
    for (const fig of figures) {
        const dt = fig.getAttribute('data-test') || '';
        if (dt.includes('-button')) continue;
        const priceEl = fig.querySelector('[data-test="pricing"]');
        const img = fig.querySelector('img[alt]');
        if (!priceEl || !img) continue;
        const priceText = priceEl.textContent.replace(/\s+/g, ' ').trim();
        if (!priceText.includes('เริ่มต้น')) continue;
        const pm = priceText.match(/([\d,]+)\s*THB/);
        if (!pm) continue;
        const price = parseInt(pm[1].replace(/,/g, ''));
        if (!price || price < 100000 || price > 10000000) continue;

        // model from img alt, splitting ONLY the published ' - ' tagline separator;
        // fallback = the figure's own label (never a body-style like '4 DOORS')
        const alt = (img.getAttribute('alt') || '').replace(/\s+/g, ' ').trim();
        let model = '';
        if (alt.includes(' - ')) {
            model = alt.split(' - ')[0].trim();
        } else {
            const figText = fig.textContent.replace(/\s+/g, ' ').trim();
            const before = figText.split(priceText)[0].trim();
            if (before && !/^\d+\s*DOORS$/i.test(before)) model = before;
        }
        if (!model) continue;
        const key = model + ':' + price;
        if (seen.has(key)) continue;
        seen.add(key);

        const path = [];
        let el = fig;
        while (el && el !== document.body) {
            const idx = Array.from(el.parentElement.children).indexOf(el);
            path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (idx + 1) + ')');
            el = el.parentElement;
        }
        items.push({ model: model, price: price, priceText: priceText,
                     selector: path.join(' > '),
                     alt: alt,
                     evidence: (alt + ' | ' + fig.textContent.replace(/\s+/g, ' ').trim()).substring(0, 240) });
    }
    return items;
})()
"""


def collect_isuzu():
    """Collect from Isuzu — isuzu-tis.com lineup figures (sidecar-verified recapture)."""
    print("=== Isuzu Thailand Official (DOM, isuzu-tis recapture) ===")
    artifact_file = f"{FIXTURE_DIR}/isuzu_tis_page.html"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    with open(artifact_file) as f:
        html = f.read()

    results, artifact = extract_from_html(html, "isuzu_tis_page", ISUZU_TIS_JS, fixture_path=artifact_file)
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
            "observation_id": hashlib.sha256(f"isuzu:{model}:{item['price']}:{item.get('selector', '')}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": prov.get("source_url", "https://www.isuzu-tis.com/"),
                "name": "Isuzu Thailand Official",
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
            "raw_labels": {"img_alt": item.get('alt', '')},
            "evidence_excerpt": item['evidence'],
            "evidence_locator": {
                "artifact_path": artifact,
                "selector": item.get('selector'),
                "method": "dom_query",
            },
        })

    print(f"  Extracted: {len(observations)} unique model/price pairs from isuzu_tis_page")
    return observations


# ─── Honda Adapter (DOM — Grade Levels section) ───
HONDA_CITY_JS = """
(() => {
    const items = [];
    
    // Currency marker: the same official price renders as 'THB' (en locale)
    // or บาท (th locale) on the same /en/city page - both accepted.
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
        const priceMatch = text.match(/([\\d,]+)\\s*(?:THB|บาท)/);
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
    """Collect from Honda City — DOM extraction from grade cards.

    Reads the sidecar-verified recapture of the same official URL. The recapture
    was proven row-equivalent to the legacy capture (same 4 variants/prices);
    legacy `honda_city_page.html` stays committed for cross-capture comparison.
    """
    print("=== Honda Thailand Official (DOM) ===")
    fixture_path = f"{FIXTURE_DIR}/honda_city_recapture.html"
    if not os.path.exists(fixture_path):
        print(f"  Recapture fixture not found: {fixture_path}")
        return []
    with open(fixture_path) as f:
        html = f.read()

    results, artifact = extract_from_html(html, "honda_city", HONDA_CITY_JS, fixture_path=fixture_path)
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
        
        # Build a CSS-accurate DOM path.
        # bs4's .children includes NavigableString nodes, so the index must be
        # taken over ELEMENT siblings only — otherwise :nth-child(N) points at
        # a different node in the browser and the locator resolves nowhere.
        path = []
        el = li
        while el and el.name and el.name != 'body':
            parent = el.parent
            if parent:
                elements = [c for c in parent.children if getattr(c, 'name', None)]
                child_idx = elements.index(el) + 1 if el in elements else 1
                path.insert(0, f"{el.name}:nth-child({child_idx})")
            el = parent
        li_index = (lambda: [x for x in model_list.find_all('li', recursive=False)].index(li) + 1)()
        
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
            "observation_id": hashlib.sha256(
                f"lexus:{model}:{price}:{' > '.join(path)}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "identity": {
                "brand_raw": "Lexus",
                "level": "MODEL",
                "identity_level": "MODEL",
                "model_raw": model,
                "variant_raw": None,
                "year": None,
                "fuel_powertrain_raw": None,
                "brand_normalized": "lexus",
                "model_normalized": model.lower().replace(" ", "-"),
                "variant_normalized": None,
            },
            "price": {
                "value_thb": price,
                # MODEL-level row: EXACT_VARIANT would contradict the identity level.
                # 'เริ่มต้น' present -> starting price; bare 'ราคา' -> the displayed
                # model price (no starting marker, so do not claim one).
                "price_type": "MSRP_STARTING" if is_starting else "MSRP",
                "type": "MSRP_STARTING" if is_starting else "MSRP",
                "currency": "THB",
                "currentness": "UNKNOWN",
            },
            "specs": {},
            "raw_labels": {},
            "evidence_excerpt": text[:500],
            "evidence_locator": {
                "artifact_path": artifact,
                "artifact_sha256": hashlib.sha256(open(artifact, 'rb').read()).hexdigest(),
                "canonical_locator": ' > '.join(path),
                "selector": f"ul.tab__item_models > li.model_sort_item:nth-of-type({li_index})",
                "method": "dom_query",
            },
            # nested shape kept for backwards compatibility with existing tests
            "evidence": {
                "excerpt": text[:500],
                "evidence_locator": {
                    "canonical_locator": ' > '.join(path),
                    "convenience_selector": f"ul.tab__item_models > li.model_sort_item:nth-of-type({li_index})",
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
                            "observation_id": hashlib.sha256(
                                f"honda_models:{model}:{price}:{' > '.join(path)}".encode()
                            ).hexdigest()[:16],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "identity": {
                                "brand_raw": "Honda",
                                "level": "MODEL",
                                "identity_level": "MODEL",
                                "model_raw": model,
                                "variant_raw": None,
                                "year": None,
                                "fuel_powertrain_raw": None,
                                "brand_normalized": "honda",
                                "model_normalized": model.lower().replace(" ", "-"),
                                "variant_normalized": None,
                            },
                            "price": {
                                "value_thb": price,
                                "price_type": "MSRP_STARTING",
                                "type": "MSRP_STARTING",
                                "currency": "THB",
                                "currentness": "UNKNOWN",
                            },
                            "specs": {},
                            "raw_labels": {},
                            "evidence_excerpt": card_text[:500],
                            "evidence_locator": {
                                "artifact_path": artifact,
                                "artifact_sha256": hashlib.sha256(
                                    open(artifact, 'rb').read()).hexdigest(),
                                "canonical_locator": ' > '.join(path),
                                "selector": f"div # {model}",
                                "method": "dom_query",
                            },
                            # nested shape kept for backwards compatibility with existing tests
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


# ─── Mazda root-capture extractor (h2 'MODEL | TAGLINE' + infoPrice) ───
MAZDA_ROOT_JS = r"""
(() => {
    const items = [];
    const cards = document.querySelectorAll('div.cardeExploRerangerInfo_content');
    const seen = new Set();
    for (const card of cards) {
        const h2 = card.querySelector('h2');
        const priceEl = card.querySelector('div.infoPrice');
        if (!h2 || !priceEl) continue;
        const priceText = priceEl.textContent.replace(/\s+/g, ' ').trim();
        if (!priceText.includes('เริ่มต้นที่')) continue;
        const pm = priceText.match(/([\d,]+)\s*บาท/);
        if (!pm) continue;
        const price = parseInt(pm[1].replace(/,/g, ''));
        if (!price || price < 100000 || price > 10000000) continue;
        const full = h2.textContent.replace(/​/g, ' ').replace(/\s+/g, ' ').trim();
        const model = full.split('|')[0].trim();
        if (!model) continue;
        const key = model + ':' + price;
        if (seen.has(key)) continue;
        seen.add(key);
        const path = [];
        let el = card;
        while (el && el !== document.body) {
            const idx = Array.from(el.parentElement.children).indexOf(el);
            path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (idx + 1) + ')');
            el = el.parentElement;
        }
        items.push({ model: model, price: price, priceText: priceText,
                     selector: path.join(' > '),
                     evidence: (full + ' | ' + priceText).substring(0, 220) });
    }
    return items;
})()
"""


def collect_kia_promos():
    """Collect from Kia — kv promo cards: span.title + .kv_desc campaign price (ล้านบาท)."""
    print("=== Kia Thailand Official (DOM promo cards) ===")
    artifact_file = f"{FIXTURE_DIR}/kia_cars_page.html"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    with open(artifact_file) as f:
        html = f.read()

    results, artifact = extract_from_html(html, "kia_cars_page", KIA_JS, fixture_path=artifact_file)
    if not results:
        print("  Extraction returned no results")
        return []

    with open(artifact, 'rb') as f:
        artifact_hash = hashlib.sha256(f.read()).hexdigest()
    prov = get_fixture_provenance(artifact)

    observations = []
    seen = set()
    for item in results:
        model = item['title']
        key = f"{model}:{item['price']}"
        if key in seen:
            continue
        seen.add(key)
        price_type = 'MSRP_STARTING' if item['starting'] else 'MSRP'

        observations.append({
            "observation_id": hashlib.sha256(f"kia:{model}:{item['price']}:{item.get('selector', '')}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": prov.get("source_url", "https://www.kia.com/th/th/cars"),
                "name": "Kia Thailand Official",
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
                "brand_raw": "Kia",
                "model_raw": model,
                "variant_raw": None,
                "year": None,
                "fuel_powertrain_raw": None,
                "brand_normalized": "kia",
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
            "raw_labels": {"promo_text": item.get('desc', '')},
            "evidence_excerpt": item['evidence'],
            "evidence_locator": {
                "artifact_path": artifact,
                "selector": item.get('selector'),
                "method": "dom_query",
            },
        })

    print(f"  Extracted: {len(observations)} campaign-priced models from kia_cars_page")
    return observations


KIA_JS = r"""
(() => {
    const items = [];
    const seen = new Set();
    document.querySelectorAll('.kv_desc').forEach(d => {
        const card = d.parentElement;
        const t = card ? card.querySelector('span.title') : null;
        if (!t) return;
        const title = t.textContent.trim();
        const desc = d.textContent.replace(/\s+/g, ' ').trim();
        let m = desc.match(/ราคาพิเศษเริ่มต้น\s*([\d.]+)\s*ล้านบาท/);
        let starting = true;
        if (!m) {
            m = desc.match(/ในราคาพิเศษ\s*([\d.]+)\s*ล้านบาท/);
            starting = false;
        }
        if (!m) return;
        const price = Math.round(parseFloat(m[1]) * 1000000);
        if (!price || price < 100000 || price > 10000000) return;
        const key = title + ':' + price;
        if (seen.has(key)) return;
        seen.add(key);
        const path = [];
        let el = d;
        while (el && el !== document.body) {
            const idx = Array.from(el.parentElement.children).indexOf(el);
            path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (idx + 1) + ')');
            el = el.parentElement;
        }
        items.push({ title: title, price: price, starting: starting,
                     selector: path.join(' > '), desc: desc,
                     evidence: (title + ' — ' + desc).substring(0, 240) });
    });
    return items;
})()
"""


# ─── Changan own-brand prices (3 artifacts) ───
Q05_JS = r"""
(() => {
    const items = [];
    const seen = new Set();
    document.querySelectorAll('.bCarModelItemDetails').forEach(el => {
        const h2 = el.querySelector('h2');
        const p = el.querySelector('.bHead p');
        if (!h2 || !p) return;
        const t = p.textContent.replace(/\s+/g, ' ').trim();
        if (!t.includes('ราคาเริ่มต้น')) return;
        const m = t.match(/([\d,]+)\s*THB/);
        if (!m) return;
        const price = parseInt(m[1].replace(/,/g, ''));
        if (!price) return;
        const model = h2.textContent.trim();
        const key = model + ':' + price;
        if (seen.has(key)) return;
        seen.add(key);
        const path = [];
        let node = el;
        while (node && node !== document.body) {
            const idx = Array.from(node.parentElement.children).indexOf(node);
            path.unshift(node.tagName.toLowerCase() + ':nth-child(' + (idx + 1) + ')');
            node = node.parentElement;
        }
        items.push({ model: model, price: price, selector: path.join(' > '),
                     evidence: (model + ' | ' + t).substring(0, 220) });
    });
    return items;
})()
"""


def _changan_row(artifact, artifact_hash, prov, *, model, variant, price, price_type,
                 identity_level, evidence, selector, method, tag, raw_labels,
                 text_offset=None):
    return {
        "observation_id": hashlib.sha256(f"{tag}:{model}:{variant or ''}:{price}:{selector or ''}".encode()).hexdigest()[:16],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": {
            "class": "OEM_OFFICIAL",
            "url": prov.get("source_url", "https://www.changan.co.th/"),
            "name": "Changan Thailand Official",
            "precedence": 100,
            "native_id": None,
            "immutable_revision": None,
            "extraction_method": method,
            "artifact_path": artifact,
            "artifact_sha256": artifact_hash,
            "captured_at": prov["captured_at"],
            "provenance_state": prov["provenance_state"],
        },
        "identity": {
            "brand_raw": "Changan",
            "model_raw": model,
            "variant_raw": variant,
            "year": None,
            "fuel_powertrain_raw": None,
            "brand_normalized": "changan",
            "model_normalized": model.lower().replace(" ", "-"),
            "variant_normalized": variant.lower().replace(" ", "-") if variant else None,
            "identity_level": identity_level,
        },
        "price": {
            "value_thb": price,
            "type": price_type,
            "currency": "THB",
            "currentness": "UNKNOWN",
        },
        "specs": {},
        "raw_labels": raw_labels,
        "evidence_excerpt": evidence,
        "evidence_locator": {
            "artifact_path": artifact,
            "selector": selector,
            "method": method,
            # character offset of this occurrence in the decoded artifact text: the page
            # repeats the offer string inside several JSON blobs, so an
            # occurrence index is what makes the locator single-valued
            "text_offset": text_offset,
        },
    }


def collect_changan_prices():
    """Collect own-brand Changan prices: NEVO Q05 page (visible DOM), Lumin calc reference,
    promotion-page Q05 trim offers (ราคาพิเศษ + จากราคา list)."""
    print("=== Changan Thailand Official (own-brand) ===")
    observations = []

    # 1. NEVO Q05 product page — visible DOM card
    q05_file = f"{FIXTURE_DIR}/changan_nevo_q05_page.html"
    if os.path.exists(q05_file):
        with open(q05_file) as f:
            html = f.read()
        results, artifact = extract_from_html(html, "changan_nevo_q05_page", Q05_JS, fixture_path=q05_file)
        if results:
            artifact_hash = hashlib.sha256(open(artifact, 'rb').read()).hexdigest()
            prov = get_fixture_provenance(artifact)
            seen = set()
            for item in results:
                key = f"{item['model']}:{item['price']}"
                if key in seen:
                    continue
                seen.add(key)
                observations.append(_changan_row(
                    artifact, artifact_hash, prov,
                    model=item['model'], variant=None, price=item['price'],
                    price_type='MSRP_STARTING', identity_level='MODEL',
                    evidence=item['evidence'], selector=item.get('selector'),
                    method='playwright_dom', tag='changan_q05', raw_labels={}))
    else:
        print(f"  Fixture not found: {q05_file}")

    # 2. Lumin product page — calc-footnote model reference 'รุ่น <model> ราคา <n> บาท'
    lumin_file = f"{FIXTURE_DIR}/changan_lumin_page.html"
    if os.path.exists(lumin_file):
        with open(lumin_file) as f:
            html = f.read()
        artifact_hash = hashlib.sha256(open(lumin_file, 'rb').read()).hexdigest()
        prov = get_fixture_provenance(lumin_file)
        seen = set()
        for m in re.finditer(r'รุ่น\s+((?:Lumin\s+){1,2}[A-Z]{1,3}\s+DC)\s+ราคา\s*([\d,]+)\s*บาท', html):
            model, price = m.group(1), int(m.group(2).replace(',', ''))
            if not price or price < 100000 or price > 10000000:
                continue
            key = f"{model}:{price}"
            if key in seen:
                continue
            seen.add(key)
            ctx = re.sub(r'\s+', ' ', html[max(0, m.start() - 60):m.end() + 60])
            observations.append(_changan_row(
                lumin_file, artifact_hash, prov,
                model=model, variant=None, price=price,
                price_type='MSRP', identity_level='MODEL',
                evidence=ctx[:220], selector=m.group(0),
                method='regex_text', tag='changan_lumin', raw_labels={},
                text_offset=m.start()))
        print(f"  Lumin matches: {len(seen)}")
    else:
        print(f"  Fixture not found: {lumin_file}")

    # 3. Promotion page — Q05 trim offers (dedupe; page embeds offers multiple times)
    promo_file = f"{FIXTURE_DIR}/changan_promotion_page.html"
    if os.path.exists(promo_file):
        with open(promo_file) as f:
            html = f.read()
        artifact_hash = hashlib.sha256(open(promo_file, 'rb').read()).hexdigest()
        prov = get_fixture_provenance(promo_file)
        seen = set()
        for m in re.finditer(
                r'รุ่น\s+(NEVO Q05 (?:MAX|ULTRA))\s+ราคาพิเศษ\s*([\d,]+)\s*บาท\s*\(จากราคา\s*([\d,]+)\s*บาท\)',
                html):
            trim, promo, listp = m.group(1), int(m.group(2).replace(',', '')), int(m.group(3).replace(',', ''))
            key = f"{trim}:{listp}"
            if key in seen:
                continue
            seen.add(key)
            model = ' '.join(trim.split()[:2])
            observations.append(_changan_row(
                promo_file, artifact_hash, prov,
                model=model, variant=trim, price=listp,
                price_type='MSRP', identity_level='VARIANT',
                evidence=m.group(0)[:220], selector=m.group(0),
                method='regex_text', tag='changan_promo',
                raw_labels={'ราคาพิเศษ_thb': promo}, text_offset=m.start()))
        print(f"  Q05 trim offers (deduped): {len(seen)}")
    else:
        print(f"  Fixture not found: {promo_file}")

    print(f"  Changan own-brand rows: {len(observations)}")
    return observations


# ─── Official JLR price-sheet PDFs (base64 artifacts → pdftotext lines) ───
def _pdf_text(b64_path):
    """Decode a base64 PDF artifact and return pdftotext -layout output."""
    import base64 as _b64
    with open(b64_path) as f:
        data = _b64.b64decode(f.read())
    assert data[:4] == b'%PDF', f"not a PDF after decode: {b64_path}"
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tf:
        tf.write(data)
        tmp_pdf = tf.name
    out = tmp_pdf + '.txt'
    try:
        subprocess.run(['pdftotext', '-layout', tmp_pdf, out],
                       check=True, capture_output=True, timeout=60)
        with open(out, encoding='utf-8', errors='ignore') as f:
            return f.read()
    finally:
        for p in (tmp_pdf, out):
            try:
                os.unlink(p)
            except OSError:
                pass


def _parse_price_sheet(text):
    """Parse a JLR price-sheet: ALL-CAPS section + variant lines with MY token + THB price."""
    rows = []
    section = None
    for i, raw in enumerate(text.splitlines()):
        s = raw.strip()
        if not s:
            continue
        if (re.fullmatch(r'[A-Z][A-Z0-9 \-]{2,}', s) and 'THB' not in s
                and 'MY' not in s and not s.startswith(('TERMS', 'Effective'))):
            section = s
            continue
        m = re.search(r'(MY\d+(?:\.\d+)?)', s)
        p = re.search(r'THB\s+([\d,]{7,})', s)
        if m and p and section:
            price = int(p.group(1).replace(',', ''))
            variant = s[:m.start()].strip()
            rows.append({
                'section': section, 'variant': variant, 'year': m.group(1),
                'price': price, 'starting': '**' in variant, 'line': i,
                'line_text': s,
            })
    return rows


def _collect_price_sheet(artifact_name, brand, source_name):
    artifact_file = f"{FIXTURE_DIR}/{artifact_name}"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    text = _pdf_text(artifact_file)
    rows = _parse_price_sheet(text)
    if not rows:
        print(f"  No price rows parsed from {artifact_name}")
        return []

    artifact_hash = hashlib.sha256(open(artifact_file, 'rb').read()).hexdigest()
    prov = get_fixture_provenance(artifact_file)

    observations = []
    seen = set()
    for r in rows:
        variant_clean = r['variant'].rstrip('*').strip()
        key = f"{r['section']}:{variant_clean}:{r['price']}"
        if key in seen:
            continue
        seen.add(key)
        observations.append({
            "observation_id": hashlib.sha256(f"{source_name}:{r['section']}:{variant_clean}:{r['price']}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": prov.get("source_url"),
                "name": source_name,
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "pdftotext_line",
                "artifact_path": artifact_file,
                "artifact_sha256": artifact_hash,
                "captured_at": prov["captured_at"],
                "provenance_state": prov["provenance_state"],
            },
            "identity": {
                "brand_raw": brand,
                "model_raw": r['section'],
                "variant_raw": variant_clean,
                "year": None,
                "fuel_powertrain_raw": None,
                "brand_normalized": brand.lower().replace(" ", "-"),
                "model_normalized": r['section'].lower().replace(" ", "-"),
                "variant_normalized": variant_clean.lower().replace(" ", "-"),
                "identity_level": "VARIANT",
            },
            "price": {
                "value_thb": r['price'],
                "type": "MSRP_STARTING" if r['starting'] else "EXACT_VARIANT",
                "currency": "THB",
                "currentness": "UNKNOWN",
            },
            "specs": {},
            "raw_labels": {"model_year": r['year'],
                           "price_sheet": artifact_name,
                           "starting_marker": r['starting']},
            "evidence_excerpt": f"{r['section']}: {r['line_text']}"[:220],
            "evidence_locator": {
                "artifact_path": artifact_file,
                "selector": r['line_text'],
                "method": "pdf_text_line",
            },
        })

    print(f"  {brand} price sheet: {len(observations)} variant rows from {artifact_name}")
    return observations


def collect_jaguar_pricesheet():
    print("=== Jaguar Thailand Official (PDF price sheet) ===")
    return _collect_price_sheet("TH_Jaguar_PriceSheet.pdf.b64", "Jaguar", "Jaguar Thailand Official")


def collect_landrover_pricesheet():
    print("=== Land Rover Thailand Official (PDF price sheet) ===")
    return _collect_price_sheet("TH_LandRover_PriceSheet.pdf.b64", "Land Rover", "Land Rover Thailand Official")


def collect_porsche():
    """Collect from Porsche Thailand — RSC flight data on the official model page.

    Each model object carries modelName + modelRange (family) + modelYear +
    price.value from ONE flight node = same-record by construction.
    """
    print("=== Porsche Thailand Official (RSC flight data) ===")
    artifact_file = f"{FIXTURE_DIR}/porsche_macan_model_page.html"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    with open(artifact_file, encoding='utf-8', errors='ignore') as f:
        raw = f.read()

    # flight payload HTML-escapes quotes
    text = raw.replace('&quot;', '"')

    # split on model-object starts; each chunk = one model node until the next
    chunks = text.split('"modelType":[0,')[1:]
    artifact_hash = hashlib.sha256(open(artifact_file, 'rb').read()).hexdigest()
    prov = get_fixture_provenance(artifact_file)

    parsed = []
    for ch in chunks:
        name_m = re.search(r'"modelName":\[0,"([^"]+)"\]', ch)
        range_m = re.search(r'"modelRange":\[0,"([^"]+)"\]', ch)
        year_m = re.search(r'"modelYear":\[0,"([^"]+)"\]', ch)
        price_m = re.search(r'"price":\[0,\{"value":\[0,(\d+)\],"currencyCode":\[0,"THB"\]', ch)
        if not (name_m and range_m and price_m):
            continue
        name = name_m.group(1)
        fam = range_m.group(1)
        price = int(price_m.group(1))
        year = int(year_m.group(1)) if year_m else None
        if not price or price < 100000 or price > 100000000:
            continue
        # fuel + drive + power from the SAME node (best-effort, informational)
        fuel_m = re.search(r'"fuelTypeText":\[0,"([^"]+)"\]', ch)
        drive_m = re.search(r'"wheelDrive":\[0,"([^"]+)"\]', ch)
        hp_m = re.search(r'"powerHp":\[0,\{"label":\[[^\]]*\],"formattedValue":\[[^\]]*\],"value":\[0,(\d+)\]', ch)
        parsed.append({
            'name': name, 'family': fam, 'year': year, 'price': price,
            'fuel': fuel_m.group(1) if fuel_m else None,
            'drive': drive_m.group(1) if drive_m else None,
            'hp': int(hp_m.group(1)) if hp_m else None,
        })

    observations = []
    seen = set()
    skipped_ambiguous = set()
    for r in parsed:
        key = (r['family'], r['name'], r['year'], r['price'])
        if key in seen:
            continue
        seen.add(key)

        # name collision with DIFFERENT price/year = ambiguous generation → fail closed
        siblings = [p for p in parsed if p['name'] == r['name']]
        prices = {(p['price'], p['year']) for p in siblings}
        if len({p['price'] for p in siblings}) > 1:
            if len({p['year'] for p in siblings}) == len({p['price'] for p in siblings}) and r['year'] is not None:
                pass  # distinct years disambiguate
            else:
                skipped_ambiguous.add(r['name'])
                continue

        is_variant = r['name'] != r['family']
        model_raw = r['family'] if is_variant else r['name']
        variant_raw = r['name'] if is_variant else None
        price_type = 'EXACT_VARIANT' if is_variant else 'MSRP'
        locator_key = f"{r['name']}|{r['year']}|{r['price']}"

        observations.append({
            "observation_id": hashlib.sha256(f"porsche:{model_raw}:{variant_raw}:{r['year']}:{r['price']}".encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": prov.get("source_url"),
                "name": "Porsche Thailand Official",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "rsc_flight_parse",
                "artifact_path": artifact_file,
                "artifact_sha256": artifact_hash,
                "captured_at": prov["captured_at"],
                "provenance_state": prov["provenance_state"],
            },
            "identity": {
                "brand_raw": "Porsche",
                "model_raw": model_raw,
                "variant_raw": variant_raw,
                "year": r['year'],
                "fuel_powertrain_raw": r['fuel'],
                "brand_normalized": "porsche",
                "model_normalized": model_raw.lower().replace(" ", "-"),
                "variant_normalized": variant_raw.lower().replace(" ", "-") if variant_raw else None,
                "identity_level": "VARIANT" if is_variant else "MODEL",
            },
            "price": {
                "value_thb": r['price'],
                "type": price_type,
                "currency": "THB",
                "currentness": "UNKNOWN",
            },
            "specs": {
                "fuel": r['fuel'],
                "drive": r['drive'],
                "power_ps": r['hp'],
            },
            "raw_labels": {"model_year": r['year'], "model_name_published": r['name']},
            "evidence_excerpt": f"{r['family']} / {r['name']} / {r['year']} / THB {r['price']:,}"[:220],
            "evidence_locator": {
                "artifact_path": artifact_file,
                "selector": locator_key,
                "method": "rsc_node",
            },
        })

    if skipped_ambiguous:
        print(f"  SKIPPED ambiguous names (conflicting prices, no year disambiguation): {sorted(skipped_ambiguous)}")
    print(f"  Extracted: {len(observations)} model/price nodes from porsche_macan_model_page")
    return observations


# ─── GWM Thailand — official /th/models/<slug> price pages ──────────────────
# The GWM homepage, /en/models and mall.gwm.co.th are price-free (recorded, no
# adapter). The 13 server-rendered model detail pages discovered through
# gwm.co.th/sitemap.xml do publish figures, in two independent places:
#
#   A. the hero `.kv-content .desc` block — labelled ราคาเริ่มต้น / "MSRP :" /
#      or a bare number;
#   B. the configurator colour cards — data-title="฿N" on .btn-item together
#      with data-car-img, whose path names the trim.
#
# Rule that decides what may be staged: a hero figure is staged ONLY when the
# exact same figure is published as a configurator card price on the SAME
# artifact. Anything else is campaign-derived (list minus the month's ส่วนลด),
# so its price type cannot be established from this artifact alone and it is
# written to the rejection log instead of being typed as MSRP/MSRP_STARTING.
GWM_MIN_PRICE = 100_000
GWM_MAX_PRICE = 10_000_000
GWM_CANDIDATES_LOG = "audit/coverage/gwm_price_candidates_20260925.json"


def _gwm_variant_from_img(img):
    """Configurator image path -> trim slug, or None when the path names no trim.

    …/model/<page>/360/<trim>/file.png        -> <trim>
    …/model/<page>/a/b/<trim>/file.webp        -> <trim>   (last segment)
    …/model/<page>/360/file.png                -> None     (colour-only path)
    …/model/<page>/file.webp                   -> None     (no trim segment)
    """
    import posixpath
    dirp = posixpath.dirname(img or "")
    if not dirp:
        return None
    if "/360/" in dirp + "/":
        trimmed = (dirp + "/").split("/360/", 1)[1].strip("/")
        return trimmed or None
    m = re.search(r"/model/[^/]+/(.+)$", dirp)
    if m and m.group(1):
        segs = [s for s in m.group(1).split("/") if s]
        if segs:
            return segs[-1]
    return None


def _gwm_card_needle(raw, price, img):
    """Exact source slice binding ONE configurator card: its own data-title
    figure plus the data-car-img path that names the trim.

    The slice must stay inside a single tag (no '<' between the two attributes),
    otherwise it would run backwards across neighbouring colour buttons and drag
    their figures into this record's evidence. Returns (needle, offset).
    """
    marker = f'data-car-img="{img}"'
    figure = f"{price:,}"
    for mm in re.finditer(re.escape(marker), raw):
        start = raw.rfind('data-title="', 0, mm.start())
        if start < 0:
            continue
        head = raw[start:mm.end()]
        if "<" in head:          # crossed into another element
            continue
        if not head.startswith('data-title="'):
            continue
        if figure not in head:
            continue
        return head, start
    return None, None


def parse_gwm_page(raw, artifact, artifact_hash, prov):
    """Parse one GWM model page. Returns (observations, rejected_candidates).

    Both lists are exhaustive over what the page publishes: every hero figure
    the page shows is either staged or returned as a rejected candidate with a
    reason, so nothing is dropped silently.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw, "html.parser")
    kv = soup.select_one(".kv-content")
    title_el = kv.select_one(".title") if kv else None
    desc = kv.select_one(".desc") if kv else None
    if kv is None or title_el is None or desc is None:
        return [], []

    title = " ".join(title_el.get_text(" ", strip=True).split())
    container = kv.find_parent(id=True)
    cid = str(container.get("id")) if container and container.get("id") else None
    if not cid or len(soup.select("#" + cid)) != 1:
        return [], []  # no page-unique, single-valued anchor available

    source_url = prov.get("source_url", "https://www.gwm.co.th/")
    captured_at = prov["captured_at"]

    def _source(method):
        return {
            "class": "OEM_OFFICIAL",
            "url": source_url,
            "name": "GWM Thailand Official",
            "precedence": 100,
            "native_id": None,
            "immutable_revision": None,
            "extraction_method": method,
            "artifact_path": artifact,
            "artifact_sha256": artifact_hash,
            "captured_at": captured_at,
            "provenance_state": prov["provenance_state"],
        }

    def _identity(variant, level, powertrain=None):
        return {
            "brand_raw": "GWM",
            "model_raw": title,
            "variant_raw": variant,
            "year": None,
            "fuel_powertrain_raw": powertrain,
            "brand_normalized": "gwm",
            "model_normalized": title.lower().replace(" ", "-"),
            "variant_normalized": variant.lower().replace(" ", "-") if variant else None,
            "identity_level": level,
        }

    def _row(variant, level, price, price_type, evidence, locator, raw_labels,
             method, powertrain=None):
        tag = f"gwm:{artifact}:{title}:{variant or ''}:{price}:{locator.get('dom_path') or locator.get('text_offset')}"
        return {
            "observation_id": hashlib.sha256(tag.encode()).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": _source(method),
            "identity": _identity(variant, level, powertrain),
            "price": {"value_thb": price, "type": price_type, "currency": "THB",
                      "currentness": "UNKNOWN"},
            "specs": {},
            "raw_labels": raw_labels,
            "evidence_excerpt": evidence[:400],
            "evidence_locator": locator,
        }

    def _candidate(span_index, value, label, reason, text):
        return {
            "artifact": artifact, "source_url": source_url, "model": title,
            "span_index": span_index, "price_label": label,
            "value_thb": value, "reason": reason, "raw_text": text[:200],
        }

    observations, rejected = [], []

    # ── A. configurator cards: the figures this site publishes as buyable ──
    cards = []  # (price, data-car-img)
    for btn in soup.select(".btn-item[data-title]"):
        m = re.search(r"฿\s*([\d,]+)", str(btn.get("data-title") or ""))
        if not m:
            continue
        price = int(m.group(1).replace(",", ""))
        if not (GWM_MIN_PRICE <= price <= GWM_MAX_PRICE):
            continue
        cards.append((price, str(btn.get("data-car-img") or "")))
    card_prices = {p for p, _ in cards}

    # ── B. hero price block ──
    spans = desc.find_all("span", recursive=False)
    for idx, span in enumerate(spans):
        text = " ".join(span.get_text(" ", strip=True).split())
        m = re.search(r"([\d][\d,]{4,})", text)
        if not m:
            continue
        value = int(m.group(1).replace(",", ""))
        prev = " ".join(spans[idx - 1].get_text(" ", strip=True).split()) if idx else ""
        prev_carries_figure = bool(re.search(r"[\d][\d,]{4,}", prev))

        if "เริ่มต้น" in text:
            label, price_type = "ราคาเริ่มต้น", "MSRP_STARTING"
            marker = ""
        elif "เริ่มต้น" in prev and not prev_carries_figure:
            # label and figure live in sibling spans (ราคาเริ่มต้น: / 1,669,000.-)
            label, price_type, marker = "ราคาเริ่มต้น", "MSRP_STARTING", prev
        elif "msrp" in text.lower():
            label, price_type, marker = "MSRP", "MSRP", ""
        else:
            label, price_type, marker = None, "MSRP", ""

        powertrain = None
        if label == "ราคาเริ่มต้น" and "ราคาเริ่มต้น" in text:
            head = text.split("ราคาเริ่มต้น")[0].strip()
            if 0 < len(head) <= 8:
                powertrain = head

        if not (GWM_MIN_PRICE <= value <= GWM_MAX_PRICE):
            rejected.append(_candidate(idx, value, label, "outside_model_price_floor", text))
            continue
        if value not in card_prices:
            rejected.append(
                _candidate(idx, value, label,
                           "not_published_as_a_configurator_price_on_this_artifact", text))
            continue

        selector = f"#{cid} .desc > span:nth-of-type({idx + 1})"
        if len(soup.select(selector)) != 1:
            rejected.append(_candidate(idx, value, label, "locator_not_single_valued", text))
            continue

        evidence = " | ".join(x for x in (title, marker, text) if x)
        observations.append(_row(
            variant=None, level="MODEL", price=value, price_type=price_type,
            evidence=evidence,
            locator={"artifact_path": artifact, "artifact_sha256": artifact_hash,
                     "dom_path": selector, "selector": selector, "method": "dom_query"},
            raw_labels={"price_label": label or "unlabeled", "raw_source_text": (marker + " " + text).strip(),
                        "configurator_corroborated": True},
            method="html_dom", powertrain=powertrain))

    # ── C. configurator cards -> EXACT_VARIANT, only when the trim is named ──
    by_variant = {}
    for price, img in cards:
        variant = _gwm_variant_from_img(img)
        if not variant:
            continue
        by_variant.setdefault(variant, {}).setdefault(price, img)

    for variant, priced in sorted(by_variant.items()):
        if len(priced) != 1:
            continue  # a trim that resolves to two figures proves nothing
        price, img = next(iter(priced.items()))
        needle, offset = _gwm_card_needle(raw, price, img)
        if needle is None:
            rejected.append(_candidate(None, price, variant, "card_needle_not_found", img))
            continue
        observations.append(_row(
            variant=variant, level="VARIANT", price=price, price_type="EXACT_VARIANT",
            evidence=needle,
            locator={"artifact_path": artifact, "artifact_sha256": artifact_hash,
                     "selector": needle, "text_offset": offset, "method": "regex_text"},
            raw_labels={"data_title": f"฿{price:,}", "image_path": img},
            method="regex_text"))

    return observations, rejected


def collect_gwm_prices():
    """Collect from GWM Thailand — the 13 official model price pages."""
    print("=== GWM Thailand Official (model price pages) ===")
    observations, rejected = [], []
    for fn in sorted(os.listdir(FIXTURE_DIR)):
        if not (fn.startswith("gwm_th_model_") and fn.endswith(".html")):
            continue
        artifact = f"{FIXTURE_DIR}/{fn}"
        with open(artifact, encoding="utf-8") as f:
            raw = f.read()
        artifact_hash = hashlib.sha256(open(artifact, "rb").read()).hexdigest()
        prov = get_fixture_provenance(artifact)
        rows, cand = parse_gwm_page(raw, artifact, artifact_hash, prov)
        observations.extend(rows)
        rejected.extend(cand)
        print(f"  {fn:38} rows={len(rows):2} rejected={len(cand)}")

    os.makedirs(os.path.dirname(GWM_CANDIDATES_LOG), exist_ok=True)
    with open(GWM_CANDIDATES_LOG, "w", encoding="utf-8") as f:
        json.dump({
            "brand": "GWM",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rule": ("a hero price is staged only when the identical figure is "
                     "published as a configurator card price on the same artifact; "
                     "campaign-derived figures are rejected rather than typed"),
            "staged_rows": len(observations),
            "rejected_candidates": rejected,
        }, f, ensure_ascii=False, indent=2)
    print(f"  GWM rows: {len(observations)} staged, {len(rejected)} rejected -> {GWM_CANDIDATES_LOG}")
    return observations


# ─── Subaru Thailand (DOM — section.lineup lineup cards) ───
# The registry's primary host www.subaru.co.th is NXDOMAIN (BLOCKED_DNS); this
# adapter reads the official TC Subaru (Thailand) lineup page published on the
# Subaru Asia property instead. One card holds the model name AND its
# ราคาเริ่มต้น figure, so name+price always come from the same record.
SUBARU_JS = r"""
(() => {
    const cssPath = (el) => {
        const parts = [];
        let node = el;
        while (node && node.nodeType === 1 && node !== document.documentElement) {
            let sel = node.tagName.toLowerCase();
            const parent = node.parentElement;
            if (parent) {
                const sameTag = Array.prototype.filter.call(
                    parent.children, (c) => c.tagName === node.tagName);
                if (sameTag.length > 1) {
                    sel += ':nth-of-type(' + (sameTag.indexOf(node) + 1) + ')';
                }
            }
            parts.unshift(sel);
            node = parent;
        }
        return parts.join(' > ');
    };

    const items = [];
    const cards = document.querySelectorAll('section.lineup .lineup-list__item');
    for (const card of cards) {
        const nameEl = card.querySelector('.lineup-list__ttl');
        const priceEl = card.querySelector('.lineup-list__price');
        if (!nameEl || !priceEl) continue;

        const priceText = priceEl.textContent.replace(/\s+/g, ' ').trim();
        // ราคาเริ่มต้น (starting price) is the published marker; without it the
        // figure is not typed as MSRP_STARTING, and this adapter stages nothing.
        if (priceText.indexOf('ราคาเริ่มต้น') === -1) continue;

        const m = priceText.match(/\d{1,3}(?:,\d{3})+|\d{4,}/);
        if (!m) continue;
        const price = parseInt(m[0].replace(/,/g, ''), 10);
        if (!price || price < 100000 || price > 10000000) continue;

        const model = nameEl.textContent.replace(/\s+/g, ' ').trim();
        if (!model) continue;

        items.push({
            model: model,
            price: price,
            priceText: priceText,
            marker: 'ราคาเริ่มต้น',
            selector: 'section.lineup .lineup-list__item',
            dom_path: cssPath(card),
            evidence: card.textContent.replace(/\s+/g, ' ').trim().substring(0, 200)
        });
    }
    return items;
})()
"""


def collect_subaru():
    """Collect Subaru Thailand lineup prices: model cards with ราคาเริ่มต้น."""
    print("=== Subaru Thailand Official (DOM, lineup starting prices) ===")
    artifact_file = f"{FIXTURE_DIR}/subaru_th_home_page.html"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    with open(artifact_file) as f:
        html = f.read()

    results, artifact = extract_from_html(html, "subaru_th_home_page", SUBARU_JS,
                                          fixture_path=artifact_file)
    if not results:
        print("  Extraction returned no results")
        return []

    artifact_hash = hashlib.sha256(open(artifact, 'rb').read()).hexdigest()
    prov = get_fixture_provenance(artifact)

    seen = set()
    observations = []
    for item in results:
        key = f"{item['model']}:{item['price']}"
        if key in seen:
            continue
        seen.add(key)

        observations.append({
            "observation_id": hashlib.sha256(
                f"subaru:{item['model']}:{item['price']}:{item.get('dom_path', '')}".encode()
            ).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": prov.get("source_url", "https://www.subaru.asia/th/th/"),
                "name": "Subaru Thailand Official",
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
                "brand_raw": "Subaru",
                "model_raw": item['model'],
                "variant_raw": None,
                "year": None,
                "fuel_powertrain_raw": None,
                "brand_normalized": "subaru",
                "model_normalized": item['model'].lower().replace(" ", "-"),
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
            "raw_labels": {"price_text": item.get('priceText', ''),
                           "price_marker": item.get('marker', '')},
            "evidence_excerpt": item['evidence'],
            "evidence_locator": {
                "artifact_path": artifact,
                "dom_path": item.get('dom_path'),
                "selector": item.get('dom_path'),
                "method": "dom_query",
            },
        })

    print(f"  Extracted: {len(observations)} unique model/price pairs from subaru_th_home_page")
    return observations


# ─── P100 catalog-first: deeper catalog layers (grade / trim identity) ──────
# These adapters read the DEEPER first-party layers reached by §59 Pass C
# internal-link traversal (grade tables, all-model price indexes, price-list
# JSON, model-page grade payloads). They exist to complete the MODEL/VARIANT
# identity catalog; price is taken only from the same record as the identity.

def _catalog_row(*, source_name, source_url, extraction_method, artifact,
                 artifact_hash, prov, tag, brand, model, variant, price,
                 price_type, identity_level, evidence, selector,
                 text_offset=None, raw_labels=None):
    """One staged observation whose locator is bound to this exact record."""
    return {
        "observation_id": hashlib.sha256(
            f"{tag}:{model}:{variant or ''}:{price}:{text_offset if text_offset is not None else selector}"
            .encode()).hexdigest()[:16],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": {
            "class": "OEM_OFFICIAL",
            "url": source_url,
            "name": source_name,
            "precedence": 100,
            "native_id": None,
            "immutable_revision": None,
            "extraction_method": extraction_method,
            "artifact_path": artifact,
            "artifact_sha256": artifact_hash,
            "captured_at": prov["captured_at"],
            "provenance_state": prov["provenance_state"],
        },
        "identity": {
            "brand_raw": brand,
            "model_raw": model,
            "variant_raw": variant,
            "year": None,
            "fuel_powertrain_raw": None,
            "brand_normalized": brand.lower().replace(" ", "-"),
            "model_normalized": model.lower().replace(" ", "-"),
            "variant_normalized": variant.lower().replace(" ", "-") if variant else None,
            "identity_level": identity_level,
        },
        "price": {
            "value_thb": price,
            "type": price_type,
            "currency": "THB",
            "currentness": "UNKNOWN",
        },
        "specs": {},
        "raw_labels": raw_labels or {},
        "evidence_excerpt": evidence[:240],
        "evidence_locator": {
            "artifact_path": artifact,
            "selector": selector,
            "method": "regex_text",
            # exact character offset of THIS record in the artifact bytes: the
            # payload repeats strings, so the offset is what makes the locator
            # single-valued (same contract as the Changan regex_text rows)
            "text_offset": text_offset,
        },
    }


def _split_json_array_elements(raw, bracket_idx):
    """Split a raw JSON array (starting at '[' == bracket_idx) into element
    substrings, returned as (abs_start, abs_end_exclusive, text). Handles the
    RSC-style backslash-escaped quotes found inside flight payloads."""
    assert raw[bracket_idx] == "["
    i = bracket_idx + 1
    depth = 1
    in_str, esc, start = False, False, None
    out = []
    while i < len(raw):
        c = raw[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c in "[{":
                if depth == 1 and start is None and c == "{":
                    start = i
                depth += 1
            elif c in "]}":
                depth -= 1
                if depth == 1 and start is not None:
                    out.append((start, i + 1, raw[start:i + 1]))
                    start = None
                if depth == 0:
                    break
        i += 1
    return out


def _load_js_json(raw, varname):
    """Extract a plain (unescaped) JSON value assigned to a JS variable."""
    m = re.search(re.escape(varname) + r"\s*=\s*", raw)
    if not m:
        return None
    i = m.end()
    while i < len(raw) and raw[i] in " \t\r\n":
        i += 1
    if i >= len(raw) or raw[i] not in "[{":
        return None
    close = "]" if raw[i] == "[" else "}"
    depth, in_str, esc, j = 0, False, False, i
    while j < len(raw):
        c = raw[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
                if depth == 0:
                    break
        j += 1
    try:
        return json.loads(raw[i:j + 1])
    except Exception:
        return None


def _catalog_artifact(name):
    """Load a sidecar-verified artifact: (raw, absolute-ish path, sha, prov)."""
    path = f"{FIXTURE_DIR}/{name}"
    if not os.path.exists(path):
        print(f"  Fixture not found: {path}")
        return None
    with open(path, encoding="utf-8", errors="ignore") as f:
        raw = f.read()
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    prov = get_fixture_provenance(path)
    if prov.get("provenance_state") != "ACQUISITION_VERIFIED":
        print(f"  REFUSING {name}: provenance_state={prov.get('provenance_state')}")
        return None
    return raw, path, sha, prov


def collect_honda_grade_list():
    """Honda /models RSC payload — every published grade of every published model.

    The page publishes, per model object, {"title": <model>, "slug": <slug>,
    "grades": [{"title": <grade>, "grade_price": <int>, "grade_price_hide": bool}]}.
    Model attribution = the nearest preceding model object of the same payload;
    identity (model + grade) and price come from ONE grade record.
    """
    print("=== Honda Thailand Grade List (RSC grade payload) ===")
    art = _catalog_artifact("honda_models_page.html")
    if not art:
        return []
    raw, path, sha, prov = art

    slug_pat = re.compile(r'\\"slug\\":\\"([A-Za-z0-9\-]+)\\"')
    # field order on every published grade record: title -> price -> hide flag
    grade_pat = re.compile(
        r'\\"title\\":\\"([^"\\]+)\\",\\"grade_price\\":([0-9]+),'
        r'\\"grade_price_hide\\":(true|false)')

    models = []                      # (offset, slug, model_title)
    for m in slug_pat.finditer(raw):
        win = raw[max(0, m.start() - 900):m.start()]
        titles = list(re.finditer(r'\\"title\\":\\"([^"\\]+)\\"', win))
        if not titles:
            continue
        models.append((m.start(), m.group(1), titles[-1].group(1)))

    obs, seen = [], set()
    for gm in grade_pat.finditer(raw):
        owner = None
        for pos, slug, title in models:
            if pos < gm.start():
                owner = (slug, title)
            else:
                break
        if not owner:
            continue
        slug, model = owner
        gtitle, price, hidden = gm.group(1), int(gm.group(2)), gm.group(3) == "true"
        if hidden or price <= 0:
            continue                  # published without a figure: identity only
        key = (slug, gtitle, price)
        if key in seen:
            continue
        seen.add(key)
        level = "MODEL" if gtitle.strip() == model.strip() else "VARIANT"
        obs.append(_catalog_row(
            source_name="Honda Thailand Grade List",
            source_url=prov.get("source_url"),
            extraction_method="rsc_grade_payload",
            artifact=path, artifact_hash=sha, prov=prov,
            tag="honda_grades", brand="Honda",
            model=model,
            variant=None if level == "MODEL" else gtitle,
            price=price,
            # §95/§98: a MODEL-level row may not carry a grade-specific figure —
            # where the published grade IS the model name the figure is model MSRP
            price_type="EXACT_VARIANT" if level == "VARIANT" else "MSRP",
            identity_level=level,
            evidence=f"{model} (slug {slug}) > {gtitle} = {price} THB (grade_price)",
            selector=gm.group(0), text_offset=gm.start(),
            raw_labels={"grade_slug": slug, "grade_price_hide": hidden}))
    print(f"  grade rows: {len(obs)}")
    return obs


def collect_lexus_price_list():
    """Lexus official price-list tool — window.data_global_models JSON.

    Each car object carries modelname (published grade name), price and its own
    model URL; the enclosing group carries the published model-family title.
    """
    print("=== Lexus Thailand Price List (published JSON) ===")
    art = _catalog_artifact("lexus_price_list.html")
    if not art:
        return []
    raw, path, sha, prov = art
    data = _load_js_json(raw, "window.data_global_models")
    if not data:
        print("  window.data_global_models not found")
        return []

    obs, seen_offsets, seen_keys = [], set(), set()
    for group in data:
        family = (group.get("title") or "").strip()
        for car in group.get("cars", []):
            mp = car.get("mpdata") or {}
            name = mp.get("modelname")
            price = mp.get("price")
            if not name or not isinstance(price, (int, float)) or not price:
                continue
            price = int(price)
            # family heading is published with inconsistent casing ("LBX", "ux"):
            # take the family from the GRADE's own leading characters when they
            # match the heading case-insensitively, otherwise keep the heading
            if name[:len(family)].lower() == family.lower() and family:
                family_name = name[:len(family)]
            else:
                family_name = family
            key = (family_name, name, price)
            if key in seen_keys:
                continue
            # locate THIS record in the artifact bytes: name token -> price token
            name_tok = f'"modelname":"{name}"'
            off = raw.find(name_tok)
            while off != -1 and off in seen_offsets:
                off = raw.find(name_tok, off + 1)
            if off == -1:
                continue
            price_tok = ""
            poff = -1
            # the payload switches to scientific notation above 1e7 (1.5E7),
            # so the token is matched structurally and its value verified
            for pm in re.finditer(r'"price":([0-9]+(?:\.[0-9]+)?(?:[Ee][+-]?[0-9]+)?)',
                                  raw[off:off + 4000]):
                if abs(float(pm.group(1)) - price) < 0.5:
                    price_tok, poff = pm.group(0), off + pm.start()
                    break
            if poff == -1:
                continue
            seen_offsets.add(off)
            seen_keys.add(key)
            level = "MODEL" if name.strip() == family_name.strip() else "VARIANT"
            obs.append(_catalog_row(
                source_name="Lexus Thailand Price List",
                source_url=prov.get("source_url"),
                extraction_method="published_json_payload",
                artifact=path, artifact_hash=sha, prov=prov,
                tag="lexus_pricelist", brand="Lexus",
                model=family_name, variant=None if level == "MODEL" else name,
                price=price,
                price_type="MSRP_STARTING" if "เริ่มต้น" in (mp.get("fromtext") or "") or
                          "เริ่มต้น" in (mp.get("desc") or "") else "MSRP",
                identity_level=level,
                evidence=f"{family_name} > {name} = {price} THB "
                         f"({(mp.get('desc') or mp.get('startingprice') or '').strip()})",
                selector=raw[off:poff + len(price_tok)], text_offset=off,
                raw_labels={"startingprice": mp.get("startingprice"),
                            "group_title": group.get("title"),
                            "model_url": mp.get("url")}))
    print(f"  grade rows: {len(obs)}")
    return obs


def collect_mitsubishi_price_tables():
    """Mitsubishi 'ราคารถทุกรุ่น' — per-model HTML tables of รุ่น / ราคา rows."""
    print("=== Mitsubishi Thailand Price Tables (published grade tables) ===")
    art = _catalog_artifact("mitsubishi_all_models_price.html")
    if not art:
        return []
    raw, path, sha, prov = art

    heads = [(m.start(), re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip())
             for m in re.finditer(r"<h[1-6][^>]*>(.*?)</h[1-6]>", raw, re.S)]
    heads = [(p, h) for p, h in heads if h and h not in ("รุ่น", "ราคา")]

    obs, seen = [], set()
    for tm in re.finditer(r"<table[^>]*>.*?</table>", raw, re.S):
        prev = [h for p, h in heads if p < tm.start()]
        if not prev:
            continue
        model = prev[-1]
        for rm in re.finditer(r"<tr[^>]*>.*?</tr>", tm.group(0), re.S):
            row_raw = rm.group(0)
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row_raw, re.S)
            if len(cells) < 2:
                continue
            label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", cells[0]))
            label = label.replace("&nbsp;", " ").replace("\xa0", " ").replace("&amp;", "&").strip()
            pm = re.search(r"([0-9]{1,3}(?:,[0-9]{3})+)\s*(?:&nbsp;|​|\s)*บาท",
                           re.sub(r"<[^>]+>", "", cells[1]))
            if not label or not pm:
                continue
            price = int(pm.group(1).replace(",", ""))
            if price < 100000 or price > 20000000:
                continue
            # model identity comes from the section heading above the table;
            # the row label may repeat it (optionally behind the brand word)
            row_label = label
            if row_label.startswith("มิตซูบิชิ "):
                row_label = row_label[len("มิตซูบิชิ "):].strip()
            if row_label == model:
                level, variant = "MODEL", None
            elif model in row_label:
                rest = row_label.replace(model, "", 1).strip()
                if rest:
                    level, variant = "VARIANT", rest
                else:
                    level, variant = "MODEL", None
            else:
                level, variant = "VARIANT", label
            key = (model, variant, price)
            if key in seen:
                continue
            seen.add(key)
            abs_off = tm.start() + rm.start()
            obs.append(_catalog_row(
                source_name="Mitsubishi Thailand Price Tables",
                source_url=prov.get("source_url"),
                extraction_method="html_table_parse",
                artifact=path, artifact_hash=sha, prov=prov,
                tag="mitsubishi_tables", brand="Mitsubishi",
                model=model,
                variant=variant,
                price=price, price_type="MSRP",
                identity_level=level,
                evidence=f"{model} | {label} | {price:,} บาท",
                selector=row_raw, text_offset=abs_off,
                raw_labels={"row_label": label}))
    print(f"  rows: {len(obs)}")
    return obs


def collect_nissan_grade_prices():
    """Nissan 'ตารางราคาทุกรุ่น' — group-car cards with version + block-price."""
    print("=== Nissan Thailand Grade Price Table (published grade cards) ===")
    art = _catalog_artifact("nissan_all_grade_price.html")
    if not art:
        return []
    raw, path, sha, prov = art

    obs, seen = [], set()
    groups = list(re.finditer(r'<div class="group-car">', raw))
    for gi, gm in enumerate(groups):
        g_end = groups[gi + 1].start() if gi + 1 < len(groups) else len(raw)
        blob = raw[gm.start():g_end]
        hm = re.search(r"<h3>([^<]+)</h3>", blob)
        if not hm:
            continue
        model = hm.group(1).strip()
        for bm in re.finditer(r'<div class="block-inner version">', blob):
            b_start = gm.start() + bm.start()
            rest = raw[b_start:g_end]
            nm = re.search(r'<span class="version-name">([^<]+)</span>', rest)
            if not nm:
                continue
            version = re.sub(r"\s+", " ", nm.group(1)).strip()
            pm = re.search(r'฿([0-9,]+)', rest[:6000])
            if not pm:
                continue
            price = int(pm.group(1).replace(",", ""))
            if price < 100000 or price > 20000000:
                continue
            needle_end = b_start + pm.end()
            key = (model, version, price)
            if key in seen:
                continue
            seen.add(key)
            obs.append(_catalog_row(
                source_name="Nissan Thailand Grade Price Table",
                source_url=prov.get("source_url"),
                extraction_method="html_card_parse",
                artifact=path, artifact_hash=sha, prov=prov,
                tag="nissan_grade_table", brand="Nissan",
                model=model, variant=version,
                price=price, price_type="EXACT_VARIANT",
                identity_level="VARIANT",
                evidence=f"{model} > {version} = ฿{price:,}",
                selector=raw[b_start:needle_end], text_offset=b_start,
                raw_labels={"version_name_raw": version}))
    print(f"  grade rows: {len(obs)}")
    return obs


def collect_bmw_price_list():
    """BMW official price list — per-series tables of variant + SRP rows."""
    print("=== BMW Thailand Price List (published price tables) ===")
    art = _catalog_artifact("bmw_price_list.html")
    if not art:
        return []
    raw, path, sha, prov = art

    heads = [(m.start(), re.sub(r"\s+", " ", m.group(1)).strip().rstrip(". ").strip())
             for m in re.finditer(r'<h2 class="cmp-title__text[^"]*">(.*?)</h2>', raw, re.S)]

    obs, seen = [], set()
    for tm in re.finditer(r'<table[^>]*class="cmp-contenttable__table[^"]*"[^>]*>.*?</table>', raw, re.S):
        prev = [h for p, h in heads if p < tm.start()]
        if not prev:
            continue
        model = re.sub(r"\s+", " ", prev[-1]).strip()
        for rm in re.finditer(r"<tr[^>]*>.*?</tr>", tm.group(0), re.S):
            row_raw = rm.group(0)
            cells = re.findall(r"<(?:td|th)[^>]*>(.*?)</(?:td|th)>", row_raw, re.S)
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).replace("&nbsp;", " ").strip()
                     for c in cells]
            if len(cells) < 2 or not cells[0]:
                continue
            pm = re.fullmatch(r"([0-9]{1,3}(?:,[0-9]{3})+)", cells[1])
            if not pm:
                continue      # header row (Suggested Retail Price…)
            price = int(pm.group(1).replace(",", ""))
            if price < 100000 or price > 30000000:
                continue
            variant = cells[0]
            key = (model, variant, price)
            if key in seen:
                continue
            seen.add(key)
            abs_off = tm.start() + rm.start()
            obs.append(_catalog_row(
                source_name="BMW Thailand Price List",
                source_url=prov.get("source_url"),
                extraction_method="html_table_parse",
                artifact=path, artifact_hash=sha, prov=prov,
                tag="bmw_pricelist", brand="BMW",
                model=model, variant=variant,
                price=price, price_type="MSRP",
                identity_level="VARIANT",
                evidence=f"{model} > {variant} = {price} THB (Suggested Retail Price)",
                selector=row_raw, text_offset=abs_off,
                raw_labels={"price_column": cells[1]}))
    print(f"  grade rows: {len(obs)}")
    return obs


# ─── P101 catalog completeness: first-party variant/grade layers ───────────
# Model vs VARIANT identity stays strict: every row below is staged under the
# model label the OFFICIAL artifact itself publishes (§98 — no inferred joins
# across differently-labelled model identities).

_MINI_SECTION_EXCLUDE = ("FINANCIAL", "SERVICES", "FREEDOM", "ALL IN")


def _parse_mini_price_sheet(text):
    """Parse the MINI Thailand official price sheet (pdftotext -layout).

    Structure: standalone model-section headers ("MINI COOPER.") followed by
    variant rows: <VARIANT NAME> <suggested retail price> <price with MSI>
    <term> <installment> <future value/balloon>. Returns the published section
    (model label), variant name and suggested retail price per row.
    """
    header = re.compile(r'^(MINI[A-Z0-9 &\-]*?[A-Z0-9])\.\s*$')
    money = r'\d{1,3}(?:,\d{3}){2,}'
    row = re.compile(r'^(?P<name>[A-Za-z0-9][A-Za-z0-9 \-–&/()]{3,}?)\s+'
                     r'(?P<p1>' + money + r')(?:\s+(?P<p2>' + money + r'))?')
    section, rows, seen = None, [], set()
    for i, raw in enumerate(text.splitlines()):
        s = raw.strip()
        if not s:
            continue
        m = header.match(s)
        if m:
            section = m.group(1).strip().rstrip('.')
            continue
        if not section or any(k in section for k in _MINI_SECTION_EXCLUDE):
            continue
        hit = row.match(s)
        if not hit or 'MINI' not in hit.group('name').upper():
            continue
        variant = hit.group('name').strip()
        if (section, variant) in seen:      # variant repeated in a later table
            continue
        seen.add((section, variant))
        rows.append({
            'section': section, 'variant': variant,
            'price': int(hit.group('p1').replace(',', '')),
            'price_with_msi': int(hit.group('p2').replace(',', ''))
            if hit.group('p2') else None,
            'line': i, 'line_text': s,
        })
    return rows


def collect_mini_pricesheet():
    """MINI Thailand: official price sheet PDF → VARIANT rows (P101)."""
    print("=== MINI Thailand Official (official price-sheet PDF, P101) ===")
    artifact_name = "MINI_PriceSheet_20260327.pdf.b64"
    artifact_file = f"{FIXTURE_DIR}/{artifact_name}"
    if not os.path.exists(artifact_file):
        print(f"  Fixture not found: {artifact_file}")
        return []
    text = _pdf_text(artifact_file)
    rows = _parse_mini_price_sheet(text)
    if not rows:
        print(f"  No price rows parsed from {artifact_name}")
        return []
    artifact_hash = hashlib.sha256(open(artifact_file, 'rb').read()).hexdigest()
    prov = get_fixture_provenance(artifact_file)
    observations = []
    for r in rows:
        model_raw = r['section']
        variant_clean = r['variant'].strip()
        observations.append({
            "observation_id": hashlib.sha256(
                f"MINI Thailand Price Sheet:{model_raw}:{variant_clean}:{r['price']}".encode()
            ).hexdigest()[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": {
                "class": "OEM_OFFICIAL",
                "url": prov.get("source_url"),
                "name": "MINI Thailand Price Sheet",
                "precedence": 100,
                "native_id": None,
                "immutable_revision": None,
                "extraction_method": "pdftotext_line",
                "artifact_path": artifact_file,
                "artifact_sha256": artifact_hash,
                "captured_at": prov["captured_at"],
                "provenance_state": prov["provenance_state"],
            },
            "identity": {
                "brand_raw": "MINI",
                "model_raw": model_raw,
                "variant_raw": variant_clean,
                "year": None,
                "fuel_powertrain_raw": None,
                "brand_normalized": "mini",
                "model_normalized": model_raw.lower().replace(" ", "-"),
                "variant_normalized": variant_clean.lower().replace(" ", "-"),
                "identity_level": "VARIANT",
            },
            "price": {
                "value_thb": r['price'],
                "type": "EXACT_VARIANT",
                "currency": "THB",
                "currentness": "UNKNOWN",
            },
            "specs": {},
            "raw_labels": {
                "published_model_section": model_raw,
                "price_with_msi_thb": r['price_with_msi'],
                "price_sheet": artifact_name,
                "line_no": r['line'],
            },
            "evidence_excerpt":
                f"{model_raw}: {variant_clean} = {r['price']} THB "
                f"(suggested retail price, official price sheet)",
            "evidence_locator": {
                "artifact_path": artifact_file,
                "selector": r['line_text'],
                "method": "pdf_text_line",
            },
        })
    print(f"  MINI price sheet: {len(observations)} variant rows from {artifact_name}")
    return observations


def _p101_html(name):
    """Load a P101-captured HTML artifact with its verified provenance."""
    path = f"{FIXTURE_DIR}/{name}"
    if not os.path.exists(path):
        print(f"  Fixture not found: {path}")
        return None
    text = open(path, encoding='utf-8', errors='replace').read()
    return {
        'path': path,
        'text': text,
        'sha': hashlib.sha256(open(path, 'rb').read()).hexdigest(),
        'prov': get_fixture_provenance(path),
    }


_SUZUKI_GRADE_CELL = re.compile(
    r'class="model-[a-z0-9]+">\s*(?P<grade>[^<>]{1,40}?)\s*<br>\s*'
    r'<h3[^>]*>\s*(?P<p1>\d{1,3}(?:,\d{3}){1,2})\*?\s*</h3>'
    r'(?:\s*<h3[^>]*>\s*(?P<p2>\d{1,3}(?:,\d{3}){1,2})\s*</h3>)?', re.S)
_SUZUKI_MODEL = re.compile(r'href="(/model/[^"]+)"[^>]*>\s*([^<]{3,60}?)\s*<', re.S)


def collect_suzuki_grades():
    """Suzuki Thailand: official SPEC&PRICE grade tables → VARIANT rows (P101)."""
    print("=== Suzuki Thailand Official (equipment/spec&price pages, P101) ===")
    out = []
    for name in ("suzuki_fronx_equipment.html", "suzuki_xl7_equipment.html",
                 "suzuki_jimny_equipment.html"):
        art = _p101_html(name)
        if not art:
            continue
        page_url = art['prov'].get('source_url') or ''
        slug = re.search(r'/model/([^/]+)/', page_url + '/')
        slug = slug.group(1).lower() if slug else ''
        labels = [t.strip() for u, t in _SUZUKI_MODEL.findall(art['text'])
                  if t.strip() and u.rstrip('/').split('/')[-1].lower() == slug]
        if not labels:
            print(f"  {name}: no published model label in breadcrumb — skipped")
            continue
        model_raw = labels[-1].rstrip('/')
        seen = set()
        for hit in _SUZUKI_GRADE_CELL.finditer(art['text']):
            grade = hit.group('grade').strip()
            if not grade or grade in seen:
                continue
            seen.add(grade)
            p1 = int(hit.group('p1').replace(',', ''))
            p2 = int(hit.group('p2').replace(',', '')) if hit.group('p2') else None
            out.append(_catalog_row(
                source_name="Suzuki Thailand Spec & Price Tables",
                source_url=art['prov'].get("source_url"),
                extraction_method="regex_text", artifact=f"{FIXTURE_DIR}/{name}",
                artifact_hash=art['sha'],
                prov=art['prov'], tag="suzuki_equipment_grade", brand="Suzuki",
                model=model_raw, variant=grade,
                price=p2 if p2 else p1, price_type="MSRP",
                identity_level="VARIANT",
                evidence=f"{model_raw} > {grade} = {p2 if p2 else p1} THB (GRADE & PRICE table)",
                selector=hit.group(0)[:160],
                text_offset=hit.start(),
                raw_labels={"promo_price_thb": p1 if p2 else None,
                            "full_price_thb": p2,
                            "page": art['prov'].get("source_url")}))
        print(f"  {name}: {len(seen)} grades for {model_raw!r}")
    print(f"  Suzuki grade rows: {len(out)}")
    return out


_KIA_EV5_TRIM = re.compile(
    r'The Kia (?P<variant>EV5 [A-Za-z0-9][A-Za-z0-9 \-]{1,32}?)\s*'
    r'(?:ราคาพิเศษ|ราคาจำหน่ายใหม่|ราคา)\s*(?P<p>\d{1,3}(?:,\d{3}){2,})')


def collect_kia_ev5_variants():
    """Kia Thailand: official September-2026 campaign pages → EV5 VARIANT rows."""
    print("=== Kia Thailand Official (campaign pages, P101) ===")
    out, seen = [], set()
    for name in ("kia_promo_carnival_diesel.html", "kia_promo_carnival_hev.html"):
        art = _p101_html(name)
        if not art:
            continue
        for hit in _KIA_EV5_TRIM.finditer(art['text']):
            variant = "The Kia " + hit.group('variant').strip().rstrip('.')
            if variant in seen:
                continue
            seen.add(variant)
            price = int(hit.group('p').replace(',', ''))
            out.append(_catalog_row(
                source_name="Kia Thailand Campaign Pages",
                source_url=art['prov'].get("source_url"),
                extraction_method="regex_text", artifact=f"{FIXTURE_DIR}/{name}",
                artifact_hash=art['sha'],
                prov=art['prov'], tag="kia_campaign_variant", brand="Kia",
                model="The Kia EV5", variant=variant,
                price=price, price_type="EXACT_VARIANT", identity_level="VARIANT",
                evidence=hit.group(0)[:240],
                selector=hit.group(0)[:160], text_offset=hit.start(),
                raw_labels={"page": art['prov'].get("source_url")}))
    print(f"  Kia EV5 variant rows: {len(out)}")
    return out


# Deepal publishes trim prices inside official campaign copy. Pattern A states
# the full price of a named trim ("ราคา Deepal S07 L มูลค่า 1,499,000 บาท") and
# is staged with a figure; pattern B sits inside discount prose whose figure may
# be post-discount, so those rows carry identity + evidence only (price=None).
_DEEPAL_PRICE_OF = re.compile(
    r'ราคา\s*Deepal\s+(?P<n>[A-Za-z0-9][A-Za-z0-9\- ]{1,28}?)\s+มูลค่า\s*'
    r'(?P<p>\d{1,3}(?:,\d{3}){2,})')



def collect_deepal_variants():
    """Deepal (Changan Thailand official): campaign copy → VARIANT rows (P101)."""
    print("=== Deepal via Changan Thailand Official (P101) ===")
    out, seen = [], set()
    for name in ("deepal_s05.html", "deepal_s05_reev.html", "deepal_s07.html",
                 "deepal_e07_plus.html", "deepal_e07_awd.html",
                 "deepal_hunter_k50.html"):
        art = _p101_html(name)
        if not art:
            continue
        added = 0
        for hit in _DEEPAL_PRICE_OF.finditer(art['text']):
            label = hit.group('n').strip()
            tokens = label.split()
            if len(tokens) == 1:            # publishes a MODEL price ("L07")
                model, variant, level = label, None, "MODEL"
            else:                            # publishes a TRIM price ("S07 L")
                model, variant, level = tokens[0], label, "VARIANT"
            price = int(hit.group('p').replace(',', ''))
            key = (model, variant, price)
            if key in seen:
                continue
            seen.add(key)
            out.append(_catalog_row(
                source_name="Changan Thailand Campaign Pages",
                source_url=art['prov'].get("source_url"),
                extraction_method="regex_text", artifact=f"{FIXTURE_DIR}/{name}",
                artifact_hash=art['sha'],
                prov=art['prov'], tag="deepal_price_of", brand="Deepal",
                model=model, variant=variant, price=price,
                price_type="MSRP" if level == "MODEL" else "EXACT_VARIANT",
                identity_level=level,
                evidence=hit.group(0)[:240],
                selector=hit.group(0)[:160], text_offset=hit.start(),
                raw_labels={"page": art['prov'].get("source_url")}))
            added += 1
        print(f"  {name}: {added} rows")
    print(f"  Deepal rows: {len(out)}")
    return out


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

    kia_promos = collect_kia_promos()
    all_observations.extend(kia_promos)

    changan_prices = collect_changan_prices()
    all_observations.extend(changan_prices)

    jaguar_sheet = collect_jaguar_pricesheet()
    all_observations.extend(jaguar_sheet)

    landrover_sheet = collect_landrover_pricesheet()
    all_observations.extend(landrover_sheet)

    porsche = collect_porsche()
    all_observations.extend(porsche)

    gwm = collect_gwm_prices()
    all_observations.extend(gwm)

    subaru = collect_subaru()
    all_observations.extend(subaru)

    # P100 catalog-first: deeper catalog layers (grade/trim identity)
    honda_grades = collect_honda_grade_list()
    all_observations.extend(honda_grades)
    lexus_prices = collect_lexus_price_list()
    all_observations.extend(lexus_prices)
    mitsubishi_tables = collect_mitsubishi_price_tables()
    all_observations.extend(mitsubishi_tables)
    nissan_grades = collect_nissan_grade_prices()
    all_observations.extend(nissan_grades)
    bmw_prices = collect_bmw_price_list()
    all_observations.extend(bmw_prices)

    # P101 catalog completeness: first-party variant/grade layers for OEMs
    # whose staged catalog had models but no published variant rows.
    mini_sheet = collect_mini_pricesheet()
    all_observations.extend(mini_sheet)
    suzuki_grades = collect_suzuki_grades()
    all_observations.extend(suzuki_grades)
    kia_variants = collect_kia_ev5_variants()
    all_observations.extend(kia_variants)
    deepal_rows = collect_deepal_variants()
    all_observations.extend(deepal_rows)

    # §98 — no duplicate identity+price records. The FIRST staged source keeps
    # its observation_id; a later source publishing the identical (brand, model,
    # variant, price) fact is not staged twice — cross-artifact agreement is
    # captured in audit/data-staging/multi_source_joins.json instead.
    seen_keys, deduped, dropped_dupes = set(), [], []
    for obs in all_observations:
        ident = obs.get("identity") or {}
        price_val = (obs.get("price") or {}).get("value_thb")
        b, m = ident.get("brand_normalized"), ident.get("model_normalized")
        if not b or not m or price_val is None:
            deduped.append(obs)              # never drop an incomplete row
            continue
        key = (b, m, ident.get("variant_normalized"), price_val)
        if key in seen_keys:
            dropped_dupes.append(obs)
            continue
        seen_keys.add(key)
        deduped.append(obs)
    if dropped_dupes:
        print(f"  dedupe: {len(dropped_dupes)} identity+price duplicate(s) not "
              f"re-staged:")
        for o in dropped_dupes:
            i = o["identity"]
            print(f"    - {o['source']['name']}: {i['model_raw']} / "
                  f"{i.get('variant_raw')} @ {o['price']['value_thb']:,}")
    all_observations = deduped

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
    print(f"Kia promo cards: {len(kia_promos)}")
    print(f"Changan own-brand: {len(changan_prices)}")
    print(f"Jaguar price sheet (PDF): {len(jaguar_sheet)}")
    print(f"Land Rover price sheet (PDF): {len(landrover_sheet)}")
    print(f"Porsche RSC nodes: {len(porsche)}")
    print(f"GWM model price pages: {len(gwm)}")
    print(f"Subaru lineup (starting prices): {len(subaru)}")
    print(f"Genuinely extracted from fixtures: {len(toyota) + len(mazda) + len(nissan) + len(honda) + len(isuzu) + len(bmw) + len(lexus) + len(honda_models) + len(mg) + len(mitsubishi) + len(suzuki) + len(mini) + len(deepal) + len(kia_promos) + len(changan_prices) + len(jaguar_sheet) + len(landrover_sheet) + len(porsche) + len(gwm) + len(subaru)}")
    print(f"Total: {len(all_observations) + len(existing)}")

    # Write staging
    os.makedirs("audit/data-staging", exist_ok=True)
    with open(STAGING_FILE, 'w') as f:
        for obs in all_observations + existing:
            f.write(json.dumps(obs) + '\n')

    # post-dedupe list (P100): only rows actually written to staging
    oem_obs = all_observations
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dedupe": {
            "rule": "first staged source keeps the identity+price record; a later "
                    "source publishing the identical fact is not re-staged (§98)",
            "dropped_rows": len(dropped_dupes),
            "dropped": [
                {"source": o["source"]["name"],
                 "model": o["identity"]["model_raw"],
                 "variant": o["identity"].get("variant_raw"),
                 "price_thb": o["price"]["value_thb"]}
                for o in dropped_dupes],
        },
        "provenance": {
            "fixture_based_extraction": len(oem_obs),
            "acquisition_verified": sum(1 for o in oem_obs if o['source'].get('provenance_state') == 'ACQUISITION_VERIFIED'),
            "legacy_unverified": sum(1 for o in oem_obs if o['source'].get('provenance_state') == 'LEGACY_UNVERIFIED'),
            "from_existing_structured_data": len(existing),
        },
        "by_source": {"toyota": len(toyota), "mazda": len(mazda), "nissan": len(nissan), "honda": len(honda),
                       "isuzu": len(isuzu), "bmw": len(bmw), "lexus": len(lexus),
                       "honda_models": len(honda_models), "mg": len(mg), "mitsubishi": len(mitsubishi), "suzuki": len(suzuki), "mini": len(mini), "deepal": len(deepal), "kia_promos": len(kia_promos), "changan": len(changan_prices), "jaguar_sheet": len(jaguar_sheet), "landrover_sheet": len(landrover_sheet), "porsche": len(porsche), "gwm": len(gwm), "subaru": len(subaru),
                       "honda_grades": len(honda_grades), "lexus_price_list": len(lexus_prices),
                       "mitsubishi_price_tables": len(mitsubishi_tables),
                       "nissan_grade_table": len(nissan_grades), "bmw_price_list": len(bmw_prices)},
        "total": len(all_observations) + len(existing),
        "staged_rows_after_dedupe": len(all_observations),
        "by_source_note": "counts are rows extracted per source before the "
                          "identity+price dedupe; staged = after dedupe",
    }
    with open("audit/data-staging/summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nWrote {len(all_observations) + len(existing)} observations to {STAGING_FILE}")


if __name__ == '__main__':
    main()
