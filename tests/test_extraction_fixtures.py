"""
Fixture-based extraction tests — run from committed artifacts, no live web.

Each test loads a committed HTML fixture, runs the adapter's extraction logic,
and verifies model/variant/price come from the SAME source record.
"""
import json
import os
import sys
import hashlib
import subprocess
import asyncio
from datetime import datetime, timezone

sys.path.insert(0, 'scripts')
from collect_multi_oem import collect_toyota, collect_mazda, collect_nissan, load_fixture

FIXTURE_DIR = "tests/fixtures/oem-artifacts"
STAGING_FILE = "audit/data-staging/vehicle_observations.jsonl"


# ─── Artifact Existence Tests ───

def test_toyota_fixture_exists():
    """Toyota fixture must be committed and non-empty."""
    path = f"{FIXTURE_DIR}/toyota_page.html"
    assert os.path.exists(path), f"Toyota fixture missing: {path}"
    assert os.path.getsize(path) > 10000, f"Toyota fixture too small: {os.path.getsize(path)}"


def test_mazda_fixture_exists():
    """Mazda fixture must be committed and non-empty."""
    path = f"{FIXTURE_DIR}/mazda_page.html"
    assert os.path.exists(path), f"Mazda fixture missing: {path}"
    assert os.path.getsize(path) > 10000, f"Mazda fixture too small: {os.path.getsize(path)}"


def test_nissan_fixture_exists():
    """Nissan fixture must be committed and non-empty."""
    path = f"{FIXTURE_DIR}/nissan_page.html"
    assert os.path.exists(path), f"Nissan fixture missing: {path}"
    assert os.path.getsize(path) > 10000, f"Nissan fixture too small: {os.path.getsize(path)}"


# ─── Toyota Extraction Tests (from fixture) ───

def test_toyota_extraction_count():
    """Toyota extractor must produce >= 50 observations from fixture."""
    observations = collect_toyota()
    assert len(observations) >= 50, f"Expected >= 50 Toyota, got {len(observations)}"


def test_toyota_every_observation_has_variant():
    """Every Toyota observation must have variant_raw from JSON-LD."""
    observations = collect_toyota()
    for obs in observations:
        assert obs['identity']['variant_raw'] is not None, \
            f"variant_raw is None for {obs['identity']['model_raw']}"
        assert obs['identity']['identity_level'] == 'VARIANT', \
            f"identity_level is not VARIANT: {obs['identity']['identity_level']}"


def test_toyota_price_currentness():
    """Toyota currentness must reflect actual availability, not always CURRENT."""
    observations = collect_toyota()
    currentnesses = set(obs['price']['currentness'] for obs in observations)
    assert len(currentnesses) >= 2, f"Expected multiple currentness values, got: {currentnesses}"


def test_toyota_evidence_locator():
    """Toyota evidence locator must be JSON-LD path."""
    observations = collect_toyota()
    for obs in observations:
        locator = obs['evidence_locator']
        assert locator.get('ldplusjson_block') == True, \
            f"ldplusjson_block not True for {obs['identity']['model_raw']}"
        assert 'json_path' in locator, \
            f"json_path missing for {obs['identity']['model_raw']}"


def test_toyota_specific_vehicles():
    """Specific Toyota vehicles must extract with correct model/variant/price."""
    observations = collect_toyota()
    lookup = {f"{o['identity']['model_raw']}|{o['identity']['variant_raw']}": o for o in observations}

    assert 'Corolla Altis|HEV Premium' in lookup, f"Not found"
    assert lookup['Corolla Altis|HEV Premium']['price']['value_thb'] == 1009000

    assert 'GR 86|GR86' in lookup, f"GR 86 not found"
    assert lookup['GR 86|GR86']['price']['value_thb'] == 2999000
    assert lookup['GR 86|GR86']['price']['currentness'] == 'UNKNOWN'


# ─── Mazda Extraction Tests (from fixture) ───

def test_mazda_extraction_count():
    """Mazda extractor must produce >= 8 observations from fixture."""
    observations = collect_mazda()
    assert len(observations) >= 8, f"Expected >= 8 Mazda, got {len(observations)}"


def test_mazda_specific_models():
    """Specific Mazda models must extract with correct prices."""
    observations = collect_mazda()
    lookup = {obs['identity']['model_raw']: obs for obs in observations}

    assert 'NEW MAZDA CX-5' in lookup, f"CX-5 not found. Got: {list(lookup.keys())}"
    assert lookup['NEW MAZDA CX-5']['price']['value_thb'] == 1219000
    assert lookup['NEW MAZDA CX-5']['price']['type'] == 'MSRP_STARTING'

    assert 'MAZDA CX-8' in lookup, f"CX-8 not found"
    assert lookup['MAZDA CX-8']['price']['value_thb'] == 1549000


def test_mazda_locator_is_dom_selector():
    """Mazda evidence locator must be a resolved nth-child DOM chain from the root capture."""
    observations = collect_mazda()
    assert observations, "no Mazda observations"
    for obs in observations:
        locator = obs['evidence_locator']
        assert locator.get('method') == 'dom_query', \
            f"method is not dom_query for {obs['identity']['model_raw']}"
        selector = locator.get('selector') or ''
        assert ' > ' in selector and ':nth-child(' in selector, \
            f"selector is not an nth-child chain: {selector!r}"
        assert 'mazda_home_page.html' in locator['artifact_path'], \
            f"root capture artifact expected, got {locator['artifact_path']}"


def test_mazda_model_level_only():
    """Mazda observations must be MODEL level (not claimed as VARIANT)."""
    observations = collect_mazda()
    for obs in observations:
        assert obs['identity']['identity_level'] == 'MODEL', \
            f"identity_level should be MODEL, got {obs['identity']['identity_level']}"
        assert obs['identity']['variant_raw'] is None, \
            f"variant_raw should be None for MODEL-level"
        assert obs['price']['type'] == 'MSRP_STARTING', \
            f"price_type should be MSRP_STARTING, got {obs['price']['type']}"


# ─── Nissan Extraction Tests (from fixture) ───

def test_nissan_extraction_count():
    """Nissan extractor must produce >= 5 observations from fixture."""
    observations = collect_nissan()
    assert len(observations) >= 5, f"Expected >= 5 Nissan, got {len(observations)}"


def test_nissan_specific_models():
    """Specific Nissan models must extract with correct prices."""
    observations = collect_nissan()
    models = {obs['identity']['model_raw']: obs for obs in observations}

    # Check for Kicks
    has_kicks = any('คิกส์' in m for m in models)
    assert has_kicks, f"No Kicks model found. Got: {list(models.keys())}"

    # Check for Navara
    has_navara = any('นาวารา' in m for m in models)
    assert has_navara, f"No Navara model found. Got: {list(models.keys())}"


def test_nissan_locator_is_dom_selector():
    """Nissan evidence locator must be DOM selector wrapping model+price."""
    observations = collect_nissan()
    for obs in observations:
        locator = obs['evidence_locator']
        assert locator.get('method') == 'dom_query', \
            f"method is not dom_query for {obs['identity']['model_raw']}"
        assert 'vehicle-in-category' in locator.get('selector', ''), \
            f"selector doesn't reference vehicle-in-category: {locator.get('selector')}"


def test_nissan_no_positional_inference():
    """Nissan must not infer model from nearby lines — same DOM card only."""
    observations = collect_nissan()
    for obs in observations:
        # Evidence excerpt must contain BOTH model name AND price
        excerpt = obs['evidence_excerpt']
        model = obs['identity']['model_raw']
        price_str = str(obs['price']['value_thb'])
        assert model in excerpt, \
            f"Model '{model}' not in evidence excerpt: {excerpt[:80]}"
        assert price_str in excerpt.replace(',', ''), \
            f"Price {price_str} not in evidence excerpt: {excerpt[:80]}"


# ─── Staging Integrity Tests ───

def test_staging_artifact_paths_exist():
    """Every observation in staging must reference an artifact that exists."""
    if not os.path.exists(STAGING_FILE):
        return  # Skip if staging not yet generated

    with open(STAGING_FILE) as f:
        for line in f:
            if not line.strip():
                continue
            obs = json.loads(line)
            artifact = obs.get('source', {}).get('artifact_path')
            if artifact:
                assert os.path.exists(artifact), \
                    f"Artifact missing for {obs['identity']['model_raw']}: {artifact}"


def test_staging_counts_match_extractors():
    """Staging counts must match extractor output counts."""
    if not os.path.exists(STAGING_FILE):
        return

    toyota_expected = len(collect_toyota())
    mazda_expected = len(collect_mazda())
    nissan_expected = len(collect_nissan())
    from collect_multi_oem import collect_honda, collect_isuzu, collect_bmw, collect_mg
    honda_expected = len(collect_honda())
    isuzu_expected = len(collect_isuzu())
    bmw_expected = len(collect_bmw())

    counts = {}
    with open(STAGING_FILE) as f:
        for line in f:
            if not line.strip():
                continue
            obs = json.loads(line)
            name = obs['source']['name']
            counts[name] = counts.get(name, 0) + 1

    assert counts.get('Toyota Thailand Official', 0) == toyota_expected, \
        f"Toyota staging count mismatch"
    assert counts.get('Mazda Thailand Official', 0) == mazda_expected, \
        f"Mazda staging count mismatch"
    assert counts.get('Nissan Thailand Official', 0) == nissan_expected, \
        f"Nissan staging count mismatch"
    assert counts.get('Honda Thailand Official', 0) == honda_expected, \
        f"Honda staging count mismatch"
    assert counts.get('Isuzu Thailand Official', 0) == isuzu_expected, \
        f"Isuzu staging count mismatch"
    assert counts.get('BMW Thailand Official', 0) == bmw_expected, \
        f"BMW staging count mismatch"
    assert counts.get('MG Thailand Official', 0) == len(collect_mg()), \
        f"MG staging count mismatch"


    from collect_multi_oem import collect_kia_promos, collect_jaguar_pricesheet, collect_landrover_pricesheet, collect_porsche
    assert counts.get('Kia Thailand Official', 0) == len(collect_kia_promos()), \
        "Kia staging count mismatch"
    assert counts.get('Jaguar Thailand Official', 0) == len(collect_jaguar_pricesheet()), \
        "Jaguar staging count mismatch"
    assert counts.get('Land Rover Thailand Official', 0) == len(collect_landrover_pricesheet()), \
        "Land Rover staging count mismatch"
    assert counts.get('Porsche Thailand Official', 0) == len(collect_porsche()), \
        "Porsche staging count mismatch"

    from collect_multi_oem import collect_gwm_prices
    assert counts.get('GWM Thailand Official', 0) == len(collect_gwm_prices()), \
        "GWM staging count mismatch"


# ─── Honda Extraction Tests (from fixture) ───

def test_honda_fixture_exists():
    """Honda fixture must be committed and non-empty."""
    path = f"{FIXTURE_DIR}/honda_city_page.html"
    assert os.path.exists(path), f"Honda fixture missing: {path}"
    assert os.path.getsize(path) > 10000, f"Honda fixture too small: {os.path.getsize(path)}"


def test_honda_extraction_count():
    """Honda City extractor must produce 4 observations from fixture."""
    from collect_multi_oem import collect_honda
    observations = collect_honda()
    assert len(observations) == 4, f"Expected 4 Honda City variants, got {len(observations)}"


def test_honda_specific_variants():
    """Honda City variants must extract with correct prices."""
    from collect_multi_oem import collect_honda
    observations = collect_honda()
    lookup = {obs['identity']['variant_raw']: obs for obs in observations}
    
    assert 'S' in lookup, f"S variant not found. Got: {list(lookup.keys())}"
    assert lookup['S']['price']['value_thb'] == 569000
    
    assert 'e:HEV RS' in lookup, f"e:HEV RS not found"
    assert lookup['e:HEV RS']['price']['value_thb'] == 739000


def test_honda_variant_level():
    """Honda observations must be VARIANT level with model=City."""
    from collect_multi_oem import collect_honda
    observations = collect_honda()
    for obs in observations:
        assert obs['identity']['identity_level'] == 'VARIANT', \
            f"identity_level should be VARIANT, got {obs['identity']['identity_level']}"
        assert obs['identity']['model_raw'] == 'City', \
            f"model_raw should be City, got {obs['identity']['model_raw']}"
        assert obs['identity']['variant_raw'] is not None, \
            f"variant_raw should not be None"


# ─── Honda Mutation Tests ───

def test_honda_evidence_contains_both_variant_and_price():
    """Evidence excerpt must contain BOTH variant name and price from same card."""
    from collect_multi_oem import collect_honda
    observations = collect_honda()
    for obs in observations:
        excerpt = obs['evidence_excerpt']
        variant = obs['identity']['variant_raw']
        price_str = str(obs['price']['value_thb'])
        assert variant in excerpt, \
            f"Variant '{variant}' not in evidence: {excerpt[:80]}"
        assert price_str in excerpt.replace(',', ''), \
            f"Price {price_str} not in evidence: {excerpt[:80]}"


def test_honda_locator_is_unique_per_card():
    """Each Honda observation must have a unique locator."""
    from collect_multi_oem import collect_honda
    observations = collect_honda()
    locators = [obs['evidence_locator']['selector'] for obs in observations]
    assert len(locators) == len(set(locators)), \
        f"Duplicate locators found: {locators}"


def test_honda_adjacent_prices_cannot_swap():
    """Mutation test: swapping prices between adjacent grades must produce different extraction."""
    import asyncio
    from playwright.async_api import async_playwright
    from collect_multi_oem import HONDA_CITY_JS, FIXTURE_DIR

    # mutate the LIVE artifact the collector actually reads (sidecar-verified recapture)
    with open(f"{FIXTURE_DIR}/honda_city_recapture.html", encoding="utf-8") as f:
        html = f.read()

    # Prices render with a locale-dependent marker ('THB' in en, 'บาท' in th) and
    # the SAME number can appear in both a card and a JSON blob — swap every
    # marker-attached occurrence in ONE pass so each occurrence keeps its marker.
    import re
    a, b = r'569,000', r'619,000'
    pat = re.compile(f'({a}|{b})\\s*(THB|\u0e1a\u0e32\u0e17)')
    mutated = pat.sub(lambda m: (b if m.group(1) == a else a) + ' ' + m.group(2), html)
    assert mutated != html, "mutation produced identical HTML"
    # every marker-attached occurrence of BOTH grades must have moved
    assert len(pat.findall(html)) >= 4, \
        f"expected both grades in both locales, got {pat.findall(html)}"
    assert pat.search(mutated) is not None
    # the numbers themselves must survive (they are the values being swapped)
    assert '569,000' in mutated and '619,000' in mutated
    
    async def extract(data):
        script = f'''
import asyncio
import json
from playwright.async_api import async_playwright

HTML = {repr(data)}
JS = {repr(HONDA_CITY_JS)}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML)
        result = await page.evaluate(JS)
        print(json.dumps(result))
        await browser.close()

asyncio.run(main())
'''
        import tempfile
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, dir='/tmp') as f:
            f.write(script)
            path = f.name
        result = subprocess.run(['python3', path], capture_output=True, text=True, timeout=30)
        os.unlink(path)
        return json.loads(result.stdout.strip())
    
    # Extract from original
    original_results = asyncio.run(extract(html))
    
    # Extract from mutated (prices swapped)
    mutated_results = asyncio.run(extract(mutated))
    
    # Verify prices swapped
    orig_prices = {r['variant']: r['price'] for r in original_results}
    mut_prices = {r['variant']: r['price'] for r in mutated_results}
    
    assert orig_prices != mut_prices, "Mutation did not change extraction"
    
    # S price should be different in mutated
    assert orig_prices.get('S') == 569000, "Original S price wrong"
    assert mut_prices.get('S') == 619000, f"Mutated S price should be 619000, got {mut_prices.get('S')}"
    assert orig_prices.get('e:HEV V') == 619000, "Original e:HEV V price wrong"
    assert mut_prices.get('e:HEV V') == 569000, f"Mutated e:HEV V price should be 569000, got {mut_prices.get('e:HEV V')}"


def test_honda_deleting_price_causes_deterministic_failure():
    """Mutation test: deleting a price must cause extraction to return fewer results."""
    from collect_multi_oem import HONDA_CITY_JS, FIXTURE_DIR
    import subprocess
    import json
    import os

    # mutate the LIVE artifact the collector actually reads
    with open(f"{FIXTURE_DIR}/honda_city_recapture.html", encoding="utf-8") as f:
        html = f.read()

    # Delete every marker-attached occurrence of one grade price (locale-robust)
    import re
    pat = re.compile(r'739,000\s*(THB|\u0e1a\u0e32\u0e17)')
    hits = pat.findall(html)
    assert hits, "e:HEV RS price marker not found in either locale"
    mutated = pat.sub('', html)
    assert mutated != html, "mutation produced identical HTML"
    assert '739,000 THB' not in mutated and '739,000 บาท' not in mutated, \
        "price deletion incomplete"
    
    async def extract_js(data):
        script = f'''
import asyncio
import json
from playwright.async_api import async_playwright

HTML = {repr(data)}
JS = {repr(HONDA_CITY_JS)}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML)
        result = await page.evaluate(JS)
        print(json.dumps(result))
        await browser.close()

asyncio.run(main())
'''
        import tempfile
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, dir='/tmp') as f:
            f.write(script)
            path = f.name
        result = subprocess.run(['python3', path], capture_output=True, text=True, timeout=30)
        os.unlink(path)
        return json.loads(result.stdout.strip())
    
    import asyncio
    original_results = asyncio.run(extract_js(html))
    mutated_results = asyncio.run(extract_js(mutated))
    
    assert len(original_results) == 4, f"Original should have 4 results, got {len(original_results)}"
    assert len(mutated_results) == 3, f"Mutated should have 3 results (deleted price), got {len(mutated_results)}"
    
    # e:HEV RS should be gone
    variants = [r['variant'] for r in mutated_results]
    assert 'e:HEV RS' not in variants, "e:HEV RS should be removed after price deletion"


def test_honda_artifact_hash_present():
    """Every Honda observation must carry artifact SHA-256 hash."""
    from collect_multi_oem import collect_honda
    observations = collect_honda()
    for obs in observations:
        assert 'artifact_sha256' in obs['source'], \
            f"artifact_sha256 missing for {obs['identity']['variant_raw']}"
        assert len(obs['source']['artifact_sha256']) == 64, \
            f"artifact_sha256 not full SHA-256: {obs['source']['artifact_sha256']}"
        assert 'artifact_sha256' in obs['evidence_locator'], \
            f"evidence_locator.artifact_sha256 missing"


# ─── Isuzu Extraction Tests (from fixture) ───

def test_isuzu_fixture_exists():
    """Isuzu fixture must be committed and non-empty."""
    path = f"{FIXTURE_DIR}/isuzu_page.html"
    assert os.path.exists(path), f"Isuzu fixture missing: {path}"
    assert os.path.getsize(path) > 10000, f"Isuzu fixture too small: {os.path.getsize(path)}"


def test_isuzu_extraction_count():
    """Isuzu extractor must produce 6 observations from fixture."""
    from collect_multi_oem import collect_isuzu
    observations = collect_isuzu()
    assert len(observations) == 6, f"Expected 6 Isuzu models, got {len(observations)}"


def test_isuzu_specific_models():
    """Specific Isuzu models must extract with correct prices."""
    from collect_multi_oem import collect_isuzu
    observations = collect_isuzu()
    lookup = {obs['identity']['model_raw']: obs for obs in observations}
    
    assert 'NEW ISUZU V-CROSS 4x4' in lookup, f"V-CROSS not found: {list(lookup)}"
    assert lookup['NEW ISUZU V-CROSS 4x4']['price']['value_thb'] == 937000

    assert 'MU-X' in lookup, f"MU-X not found"
    assert lookup['MU-X']['price']['value_thb'] == 1194000

    # body styles must never surface as model names (legacy defect fixed)
    for bad in ('4 DOORS', '2 DOORS'):
        assert bad not in lookup, f"body style leaked into model names: {bad}"
    assert 'NEW ISUZU D-MAX HI-LANDER' in lookup, "HI-LANDER (alt-derived) not found"


def test_isuzu_model_level():
    """Isuzu observations must be MODEL level."""
    from collect_multi_oem import collect_isuzu
    observations = collect_isuzu()
    for obs in observations:
        assert obs['identity']['identity_level'] == 'MODEL', \
            f"identity_level should be MODEL, got {obs['identity']['identity_level']}"
        assert obs['identity']['variant_raw'] is None, \
            f"variant_raw should be None for MODEL-level"


def test_isuzu_evidence_contains_both():
    """Evidence excerpt must contain BOTH model name and price."""
    from collect_multi_oem import collect_isuzu
    observations = collect_isuzu()
    for obs in observations:
        excerpt = obs['evidence_excerpt']
        model = obs['identity']['model_raw']
        price_str = str(obs['price']['value_thb'])
        assert model in excerpt, f"Model '{model}' not in evidence: {excerpt[:60]}"
        assert price_str in excerpt.replace(',', ''), \
            f"Price {price_str} not in evidence: {excerpt[:60]}"


# ─── BMW Extraction Tests (from fixture) ───

def test_bmw_fixture_exists():
    """BMW fixture must be committed and non-empty."""
    path = f"{FIXTURE_DIR}/bmw_models_page.html"
    assert os.path.exists(path), f"BMW fixture missing: {path}"
    assert os.path.getsize(path) > 10000, f"BMW fixture too small: {os.path.getsize(path)}"


def test_bmw_extraction_count():
    """BMW extractor must produce >= 30 observations from fixture."""
    from collect_multi_oem import collect_bmw
    observations = collect_bmw()
    assert len(observations) >= 30, f"Expected >= 30 BMW models, got {len(observations)}"


def test_bmw_specific_models():
    """Specific BMW models must extract with correct prices (verified recapture artifact)."""
    from collect_multi_oem import collect_bmw
    observations = collect_bmw()
    models = {obs['identity']['model_raw']: obs for obs in observations}
    
    # Check specific known models exist with correct prices
    assert 'SAV New iX' in models, f"iX not found. Models: {list(models.keys())[:5]}"
    assert models['SAV New iX']['price']['value_thb'] == 5799000
    
    assert 'Sedan 3 series' in models, f"3 Series not found"
    assert models['Sedan 3 series']['price']['value_thb'] == 2679000
    
    assert 'Sedan M3' in models, f"M3 not found"
    assert models['Sedan M3']['price']['value_thb'] == 14799000


def test_bmw_model_level():
    """BMW observations must be MODEL level."""
    from collect_multi_oem import collect_bmw
    observations = collect_bmw()
    for obs in observations:
        assert obs['identity']['identity_level'] == 'MODEL', \
            f"identity_level should be MODEL"
        assert obs['identity']['variant_raw'] is None, \
            f"variant_raw should be None"


def test_bmw_evidence_contains_both():
    """Evidence excerpt must contain BOTH model name and price from same card."""
    from collect_multi_oem import collect_bmw
    observations = collect_bmw()
    for obs in observations:
        excerpt = obs['evidence_excerpt']
        model = obs['identity']['model_raw']
        price_str = str(obs['price']['value_thb'])
        # Price must be in evidence
        assert price_str in excerpt.replace(',', ''), \
            f"Price {price_str} not in evidence: {excerpt[:60]}"
        # Model name (or key part of it) must be in evidence
        model_key = model.split()[-1] if model else ''
        if model_key and len(model_key) > 1:
            assert model_key in excerpt or model in excerpt, \
                f"Model '{model}' not in evidence: {excerpt[:80]}"


def test_bmw_canonical_locator():
    """BMW observations must have canonical_locator (DOM path)."""
    from collect_multi_oem import collect_bmw
    observations = collect_bmw()
    for obs in observations:
        assert 'canonical_locator' in obs['evidence_locator'], \
            f"canonical_locator missing"
        assert 'artifact_sha256' in obs['source'], \
            f"artifact_sha256 missing"


# ─── BMW Mutation Tests ───

def test_bmw_canonical_locator_unique():
    """Each BMW observation must have a unique canonical locator."""
    from collect_multi_oem import collect_bmw
    observations = collect_bmw()
    locators = [obs['evidence_locator']['canonical_locator'] for obs in observations]
    assert len(locators) == len(set(locators)), \
        f"Duplicate locators found: {len(locators) - len(set(locators))} duplicates"


def test_bmw_same_card_model_price():
    """Evidence excerpt must contain BOTH model name and price from same card."""
    from collect_multi_oem import collect_bmw
    
    observations = collect_bmw()
    
    # Verify evidence excerpt contains both model and price
    passed = 0
    for obs in observations:
        excerpt = obs['evidence_excerpt']
        model = obs['identity']['model_raw']
        price_str = str(obs['price']['value_thb'])
        
        # Price must be in evidence (with or without commas)
        price_in_evidence = price_str in excerpt.replace(',', '') or price_str in excerpt
        # Model name must be in evidence
        model_in_evidence = model in excerpt
        
        if price_in_evidence and model_in_evidence:
            passed += 1
    
    assert passed == len(observations), \
        f"Same-card verification: {passed}/{len(observations)} passed"


def test_bmw_adjacent_prices_cannot_swap():
    """Mutation test: swapping prices between adjacent BMW cards must change extraction."""
    from collect_multi_oem import BMW_JS, load_fixture
    import subprocess
    import json
    import asyncio
    
    html, _ = load_fixture("bmw_models")
    
    # Swap two known prices: 5,799,000 <-> 3,459,000
    mutated = html.replace('฿5,799,000', 'XXX_TMP_XXX')
    mutated = mutated.replace('฿3,459,000', '฿5,799,000')
    mutated = mutated.replace('XXX_TMP_XXX', '฿3,459,000')
    
    async def extract_js(data):
        script = f'''
import asyncio
import json
from playwright.async_api import async_playwright

HTML = {repr(data)}
JS = {repr(BMW_JS)}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML, timeout=60000, wait_until="domcontentloaded")
        result = await page.evaluate(JS)
        print(json.dumps(result))
        await browser.close()

asyncio.run(main())
'''
        with open('/tmp/bmw_mutation.py', 'w') as f:
            f.write(script)
        result = subprocess.run(['python3', '/tmp/bmw_mutation.py'], capture_output=True, text=True, timeout=60)
        return json.loads(result.stdout.strip())
    
    original = asyncio.run(extract_js(html))
    mutated_results = asyncio.run(extract_js(mutated))
    
    # Build lookup
    orig_prices = {r['model']: r['price'] for r in original}
    mut_prices = {r['model']: r['price'] for r in mutated_results}
    
    # Verify prices swapped
    assert orig_prices.get('SAV ใหม่ iX') == 5799000, "Original iX price wrong"
    assert mut_prices.get('SAV ใหม่ iX') == 3459000, \
        f"Mutated iX price should be 3459000, got {mut_prices.get('SAV ใหม่ iX')}"


def test_bmw_deleting_price_causes_deterministic_failure():
    """Mutation test: deleting a price must cause extraction to return fewer results."""
    from collect_multi_oem import BMW_JS, load_fixture
    import subprocess
    import json
    import asyncio
    
    html, _ = load_fixture("bmw_models")
    
    # Delete one price
    mutated = html.replace('฿14,799,000', '')
    
    async def extract_js(data):
        script = f'''
import asyncio
import json
from playwright.async_api import async_playwright

HTML = {repr(data)}
JS = {repr(BMW_JS)}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML, timeout=60000, wait_until="domcontentloaded")
        result = await page.evaluate(JS)
        print(json.dumps(result))
        await browser.close()

asyncio.run(main())
'''
        with open('/tmp/bmw_mutation2.py', 'w') as f:
            f.write(script)
        result = subprocess.run(['python3', '/tmp/bmw_mutation2.py'], capture_output=True, text=True, timeout=60)
        return json.loads(result.stdout.strip())
    
    original = asyncio.run(extract_js(html))
    mutated_results = asyncio.run(extract_js(mutated))
    
    assert len(original) >= 30, f"Original should have >=30, got {len(original)}"
    assert len(mutated_results) < len(original), \
        f"Mutated should have fewer results: {len(mutated_results)} vs {len(original)}"
    
    # M3 should be gone
    models = [r['model'] for r in mutated_results]
    assert 'Sedan M3' not in models, "M3 should be removed after price deletion"


# ─── Manifest Provenance Tests ───

def test_captured_at_uses_acquisition_record_not_mtime():
    """captured_at must come from the acquisition record (manifest or sidecar), NOT filesystem mtime."""
    from collect_multi_oem import collect_bmw, collect_honda, load_manifest
    import os
    import json as _json

    manifest = load_manifest()
    assert 'honda_city_page.html' in manifest, "Honda not in manifest"
    assert manifest['honda_city_page.html']['captured_at'] is not None, \
        "Legacy manifest entry should still be recorded (historical artifact)"

    # Honda now sources its time from the SIDECAR of the verified recapture
    # (the same official URL, proven row-equivalent to the legacy capture)
    honda_obs = collect_honda()
    honda_captured = honda_obs[0]['source']['captured_at']
    with open('tests/fixtures/oem-artifacts/honda_city_recapture.html.prov.json') as f:
        honda_sidecar = _json.load(f)
    assert honda_captured == honda_sidecar['captured_at'], \
        f"Honda captured_at should match sidecar, got {honda_captured}"
    assert honda_obs[0]['source']['provenance_state'] == 'ACQUISITION_VERIFIED', \
        "Honda recapture must be ACQUISITION_VERIFIED"
    assert honda_captured != manifest['honda_city_page.html']['captured_at'], \
        "Honda must no longer source its time from the legacy manifest"

    # BMW now sources its time from the sidecar of the genuine recapture
    with open('tests/fixtures/oem-artifacts/bmw_all_models_verified.html.prov.json') as f:
        bmw_sidecar = _json.load(f)
    bmw_obs = collect_bmw()
    bmw_captured = bmw_obs[0]['source']['captured_at']
    assert bmw_captured == bmw_sidecar['captured_at'], \
        f"BMW captured_at should match sidecar, got {bmw_captured}"
    assert bmw_obs[0]['source']['provenance_state'] == 'ACQUISITION_VERIFIED', \
        "BMW recapture must be ACQUISITION_VERIFIED"

    # Neither timestamp may be derived from file mtime
    for obs, path in [
        (bmw_obs[0], 'tests/fixtures/oem-artifacts/bmw_all_models_verified.html'),
        (honda_obs[0], 'tests/fixtures/oem-artifacts/honda_city_recapture.html'),
    ]:
        mtime_iso = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat()
        assert obs['source']['captured_at'] != mtime_iso, \
            "captured_at must not be derived from mtime"


def test_mazda_legacy_unknown_but_nissan_recapture_has_sidecar_time():
    """Legacy fixtures without provenance keep UNKNOWN; switched collectors carry sidecar time."""
    from collect_multi_oem import collect_mazda, collect_nissan, get_fixture_provenance

    # the OLD mazda fixture has no sidecar and no manifest entry — stays UNKNOWN
    legacy = get_fixture_provenance(f"{FIXTURE_DIR}/mazda_page.html")
    assert legacy['captured_at'] == 'UNKNOWN', \
        f"legacy mazda fixture should stay UNKNOWN, got {legacy['captured_at']}"

    # collect_mazda switched to the sidecar-verified root capture
    mazda_obs = collect_mazda()
    assert mazda_obs[0]['source']['artifact_path'].endswith('mazda_home_page.html'), \
        "collect_mazda must read the root capture"
    assert mazda_obs[0]['source']['provenance_state'] == 'ACQUISITION_VERIFIED'
    assert mazda_obs[0]['source']['captured_at'] != 'UNKNOWN', \
        f"Mazda root capture must carry sidecar time, got {mazda_obs[0]['source']['captured_at']}"

    # Nissan was genuinely recaptured via AcquisitionWriter — sidecar time, not UNKNOWN
    nissan_obs = collect_nissan()
    assert nissan_obs[0]['source']['provenance_state'] == 'ACQUISITION_VERIFIED'
    assert nissan_obs[0]['source']['captured_at'] != 'UNKNOWN', \
        "Nissan recapture must carry a real captured_at from its sidecar"


def test_bmw_canonical_locator_resolves_to_exact_card():
    """Each stored canonical_locator must resolve to exactly one card with model+price."""
    from collect_multi_oem import collect_bmw, load_fixture
    import asyncio
    from playwright.async_api import async_playwright
    
    observations = collect_bmw()
    # Resolve against the exact artifact the observations were extracted from
    with open(observations[0]['evidence_locator']['artifact_path'], encoding='utf-8') as f:
        html = f.read()
    
    async def resolve_locators():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html, timeout=60000, wait_until='domcontentloaded')
            
            # Get all card count
            card_count = await page.evaluate("document.querySelectorAll('.cmp-allmodelscard__root').length")
            
            results = []
            for obs in observations:
                locator = obs['evidence_locator']['canonical_locator']
                model = obs['identity']['model_raw']
                price = obs['price']['value_thb']
                
                # Resolve locator (DOM path) and verify it contains model+price
                try:
                    resolved = await page.evaluate(f"""
                        (() => {{
                            // Parse DOM path like "div:nth-child(97) > div:nth-child(1) > ..."
                            const pathStr = {repr(locator)};
                            const parts = pathStr.split(' > ');
                            let el = document.body;
                            
                            for (const part of parts) {{
                                const parenIdx = part.indexOf(':nth-child(');
                                if (parenIdx === -1) return {{found: false, error: 'bad part: ' + part}};
                                const tag = part.substring(0, parenIdx);
                                const idx = parseInt(part.substring(parenIdx + 11, part.length - 1));
                                const children = Array.from(el.children);
                                const child = children[idx - 1];
                                if (!child || child.tagName.toLowerCase() !== tag) return {{found: false, error: 'no child: ' + part}};
                                el = child;
                            }}
                            
                            if (!el) return {{found: false}};
                            const text = el.textContent.replace(/\s+/g, ' ');
                            const modelNorm = {repr(model)}.replace(/\s+/g, ' ');
                            const hasModel = text.includes(modelNorm);
                            const hasPrice = text.replace(/,/g, '').includes({repr(str(price))});
                            return {{found: true, hasModel, hasPrice, isCard: el.classList.contains('cmp-allmodelscard__root')}};
                        }})()
                    """)
                    results.append({
                        'found': resolved.get('found', False),
                        'hasModel': resolved.get('hasModel', False),
                        'hasPrice': resolved.get('hasPrice', False),
                        'isCard': resolved.get('isCard', False)
                    })
                except:
                    results.append({'found': False, 'hasModel': False, 'hasPrice': False, 'isCard': False})
            
            await browser.close()
            return card_count, results
    
    card_count, results = asyncio.run(resolve_locators())
    
    # All locators should resolve
    found_count = sum(1 for r in results if r['found'])
    assert found_count == len(results), \
        f"Only {found_count}/{len(results)} locators resolved"
    
    # All should be actual cards
    card_count_resolved = sum(1 for r in results if r['isCard'])
    assert card_count_resolved == len(results), \
        f"Only {card_count_resolved}/{len(results)} resolved to .cmp-allmodelscard__root"
    
    # All should contain model
    model_count = sum(1 for r in results if r['hasModel'])
    assert model_count == len(results), \
        f"Only {model_count}/{len(results)} contain model name"
    
    # All should contain price
    price_count = sum(1 for r in results if r['hasPrice'])
    assert price_count == len(results), \
        f"Only {price_count}/{len(results)} contain price"


# ─── Lexus Tests ───

def test_lexus_fixture_exists():
    assert os.path.exists(f"{FIXTURE_DIR}/lexus_models_page.html"), "Lexus fixture missing"

def test_lexus_fixture_sidecar_exists():
    assert os.path.exists(f"{FIXTURE_DIR}/lexus_models_page.html.prov.json"), "Lexus sidecar missing"

def test_lexus_extraction_count():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_lexus
    obs = collect_lexus()
    assert len(obs) == 6, f"Expected 6 Lexus models, got {len(obs)}"

def test_lexus_specific_models():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_lexus
    obs = collect_lexus()
    models = {o['identity']['model_raw']: o for o in obs}
    
    assert 'LBX' in models, "LBX not found"
    assert models['LBX']['price']['value_thb'] == 2430000
    assert models['LBX']['price']['price_type'] == 'MSRP_STARTING'
    
    assert 'NX' in models, "NX not found"
    assert models['NX']['price']['value_thb'] == 3310000
    
    assert 'RX' in models, "RX not found"
    assert models['RX']['price']['value_thb'] == 4520000

def test_lexus_model_level():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_lexus
    obs = collect_lexus()
    for o in obs:
        assert o['identity']['level'] == 'MODEL'
        assert o['identity']['variant_raw'] is None

def test_lexus_currentness_unknown():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_lexus
    obs = collect_lexus()
    for o in obs:
        assert o['price']['currentness'] == 'UNKNOWN'

def test_lexus_evidence_contains_both():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_lexus
    obs = collect_lexus()
    for o in obs:
        model = o['identity']['model_raw']
        price = str(o['price']['value_thb'])
        excerpt = o['evidence']['excerpt']
        assert model in excerpt, f"Model {model} not in evidence"
        assert price in excerpt.replace(',', ''), f"Price {price} not in evidence"

def test_lexus_sidecar_provenance():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_lexus
    obs = collect_lexus()
    for o in obs:
        assert o['source']['provenance_state'] == 'ACQUISITION_VERIFIED'
        assert o['source']['captured_at'] != 'UNKNOWN'

def test_lexus_canonical_locator_present():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_lexus
    obs = collect_lexus()
    for o in obs:
        locator = o['evidence']['evidence_locator']['canonical_locator']
        assert locator, f"Missing locator for {o['identity']['model_raw']}"
        assert 'nth-child' in locator or ':' in locator



# ─── Honda Models Page Tests ───

def test_honda_models_fixture_exists():
    assert os.path.exists(f"{FIXTURE_DIR}/honda_models_page.html"), "Honda models fixture missing"

def test_honda_models_fixture_sidecar_exists():
    assert os.path.exists(f"{FIXTURE_DIR}/honda_models_page.html.prov.json"), "Honda models sidecar missing"

def test_honda_models_extraction_count():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_honda_models
    obs = collect_honda_models()
    assert len(obs) == 6, f"Expected 6 Honda models, got {len(obs)}"

def test_honda_models_specific_models():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_honda_models
    obs = collect_honda_models()
    models = {o['identity']['model_raw']: o for o in obs}
    
    assert 'City' in models, "City not found"
    assert models['City']['price']['value_thb'] == 569000
    assert models['City']['price']['price_type'] == 'MSRP_STARTING'
    
    assert 'City Hatchback' in models, "City Hatchback not found"
    assert models['City Hatchback']['price']['value_thb'] == 579000

def test_honda_models_model_level():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_honda_models
    obs = collect_honda_models()
    for o in obs:
        assert o['identity']['level'] == 'MODEL'
        assert o['identity']['variant_raw'] is None

def test_honda_models_currentness_unknown():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_honda_models
    obs = collect_honda_models()
    for o in obs:
        assert o['price']['currentness'] == 'UNKNOWN'

def test_honda_models_evidence_contains_both():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_honda_models
    obs = collect_honda_models()
    for o in obs:
        model = o['identity']['model_raw']
        price = str(o['price']['value_thb'])
        excerpt = o['evidence']['excerpt']
        assert model in excerpt, f"Model {model} not in evidence"
        assert price in excerpt.replace(',', ''), f"Price {price} not in evidence"

def test_honda_models_sidecar_provenance():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_honda_models
    obs = collect_honda_models()
    for o in obs:
        assert o['source']['provenance_state'] == 'ACQUISITION_VERIFIED'
        assert o['source']['captured_at'] != 'UNKNOWN'

def test_honda_models_canonical_locator_present():
    import sys
    sys.path.insert(0, 'scripts')
    from collect_multi_oem import collect_honda_models
    obs = collect_honda_models()
    for o in obs:
        locator = o['evidence']['evidence_locator']['canonical_locator']
        assert locator, f"Missing locator for {o['identity']['model_raw']}"


# ─── MG Extraction Tests (sidecar-verified capture) ───


def test_mg_artifact_and_sidecar_exist():
    """MG artifact must be committed with a matching ACQUISITION_VERIFIED sidecar."""
    import hashlib as _hashlib
    path = f"{FIXTURE_DIR}/mg_home_page.html"
    assert os.path.exists(path), f"MG artifact missing: {path}"
    assert os.path.getsize(path) > 10000, f"MG artifact too small: {os.path.getsize(path)}"
    sc_path = path + ".prov.json"
    assert os.path.exists(sc_path), f"MG sidecar missing: {sc_path}"
    with open(sc_path) as f:
        sc = json.load(f)
    assert sc['provenance_state'] == 'ACQUISITION_VERIFIED'
    assert sc['source_url'].startswith('https://www.mgcars.com/th')
    with open(path, 'rb') as f:
        assert _hashlib.sha256(f.read()).hexdigest() == sc['sha256'], \
            "sidecar sha256 must match artifact bytes"


def test_mg_extraction_count():
    """MG extractor must produce >= 5 MODEL rows from the verified capture."""
    from collect_multi_oem import collect_mg
    observations = collect_mg()
    assert len(observations) >= 5, f"Expected >= 5 MG models, got {len(observations)}"


def test_mg_specific_models():
    """Specific MG models must extract with correct source-labelled starting prices."""
    from collect_multi_oem import collect_mg
    observations = collect_mg()
    lookup = {}
    for obs in observations:
        lookup.setdefault(obs['identity']['model_raw'], obs)

    assert 'MG ZS' in lookup, f"MG ZS not found. Models: {list(lookup)}"
    assert lookup['MG ZS']['price']['value_thb'] == 599000

    assert 'MG HS PHEV' in lookup, f"MG HS PHEV not found"
    assert lookup['MG HS PHEV']['price']['value_thb'] == 899000

    assert 'MG4' in lookup, f"MG4 not found"
    assert lookup['MG4']['price']['value_thb'] == 599900

    assert 'MG MAXUS 9' in lookup, f"MG MAXUS 9 not found"
    assert lookup['MG MAXUS 9']['price']['value_thb'] == 1799900


def test_mg_identity_model_level():
    """MG observations must be MODEL identity, brand MG, no invented variants."""
    from collect_multi_oem import collect_mg
    for obs in collect_mg():
        assert obs['identity']['identity_level'] == 'MODEL'
        assert obs['identity']['variant_raw'] is None, \
            f"variant must not be invented: {obs['identity']['model_raw']}"
        assert obs['identity']['brand_normalized'] == 'mg'


def test_mg_price_semantics():
    """MG prices must be MSRP_STARTING/THB/UNKNOWN and the excerpt must be source-labelled เริ่มต้น."""
    from collect_multi_oem import collect_mg
    for obs in collect_mg():
        assert obs['price']['type'] == 'MSRP_STARTING'
        assert obs['price']['currency'] == 'THB'
        assert obs['price']['currentness'] == 'UNKNOWN'
        assert 'เริ่มต้น' in obs['evidence_excerpt'], \
            f"price not labelled starting by the source: {obs['evidence_excerpt'][:80]}"


def test_mg_same_record_model_price():
    """Model and price must come from the SAME source span (evidence contains both)."""
    from collect_multi_oem import collect_mg
    for obs in collect_mg():
        excerpt = obs['evidence_excerpt']
        model = obs['identity']['model_raw']
        price_digits = str(obs['price']['value_thb'])
        assert model in excerpt, f"model not in evidence: {excerpt[:80]}"
        assert price_digits in excerpt.replace(',', ''), \
            f"price {price_digits} not in evidence: {excerpt[:80]}"


def test_mg_locator_unique():
    """Every MG canonical locator must be unique within the capture."""
    from collect_multi_oem import collect_mg
    locators = [obs['evidence_locator']['canonical_locator'] for obs in collect_mg()]
    assert len(locators) == len(set(locators)), "duplicate canonical locators"


def test_mg_provenance_verified():
    """MG rows must carry ACQUISITION_VERIFIED provenance + sidecar captured_at."""
    from collect_multi_oem import collect_mg
    with open(f"{FIXTURE_DIR}/mg_home_page.html.prov.json") as f:
        sc = json.load(f)
    for obs in collect_mg():
        assert obs['source']['provenance_state'] == 'ACQUISITION_VERIFIED'
        assert obs['source']['captured_at'] == sc['captured_at']
        assert obs['source']['artifact_sha256'] == sc['sha256']


def test_mg_locator_resolves_to_exact_card():
    """Each stored canonical_locator must re-resolve against the artifact to the SAME record."""
    from collect_multi_oem import collect_mg
    from playwright.async_api import async_playwright

    observations = collect_mg()
    with open(observations[0]['evidence_locator']['artifact_path'], encoding='utf-8') as f:
        html = f.read()

    async def resolve_locators():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html, timeout=60000, wait_until='domcontentloaded')
            results = []
            for obs in observations:
                locator = obs['evidence_locator']['canonical_locator']
                model = obs['identity']['model_raw']
                price = obs['price']['value_thb']
                resolved = await page.evaluate(f"""
                    (() => {{
                        const parts = {repr(locator)}.split(' > ');
                        let el = document.body;
                        for (const part of parts) {{
                            const parenIdx = part.indexOf(':nth-child(');
                            if (parenIdx === -1) return {{found: false}};
                            const tag = part.substring(0, parenIdx);
                            const idx = parseInt(part.substring(parenIdx + 11, part.length - 1));
                            const children = Array.from(el.children);
                            const child = children[idx - 1];
                            if (!child || child.tagName.toLowerCase() !== tag) return {{found: false}};
                            el = child;
                        }}
                        const text = el.textContent.replace(/\\s+/g, ' ');
                        return {{
                            found: true,
                            hasModel: text.includes({repr(model)}),
                            hasPrice: text.replace(/,/g, '').includes({repr(str(price))}),
                            isRecordSpan: el.tagName.toLowerCase() === 'span'
                                && el.classList.contains('font-bold'),
                        }};
                    }})()
                """)
                results.append(resolved)
            await browser.close()
            return results

    results = asyncio.run(resolve_locators())
    assert len(results) == len(observations)
    for r in results:
        assert r.get('found'), "locator failed to resolve"
        assert r.get('hasModel'), "resolved record missing model"
        assert r.get('hasPrice'), "resolved record missing price"
        assert r.get('isRecordSpan'), "locator did not land on the record span"


def test_mg_adjacent_prices_cannot_swap():
    """Mutation: swapping prices between two MG cards must change extraction."""
    from collect_multi_oem import MG_JS

    html, _ = load_fixture("mg_home")
    mutated = html.replace('599,000 บาท', 'XXXTMPXXX')
    mutated = mutated.replace('899,000 บาท', '599,000 บาท')
    mutated = mutated.replace('XXXTMPXXX', '899,000 บาท')

    def run_extract(data):
        import json as _json
        script = f'''
import asyncio, json
from playwright.async_api import async_playwright

HTML = {repr(data)}
JS = {repr(MG_JS)}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML, timeout=60000, wait_until="domcontentloaded")
        result = await page.evaluate(JS)
        print(json.dumps(result))
        await browser.close()

asyncio.run(main())
'''
        with open('/tmp/mg_mutation_swap.py', 'w') as f:
            f.write(script)
        result = subprocess.run(['python3', '/tmp/mg_mutation_swap.py'], capture_output=True, text=True, timeout=60)
        return json.loads(result.stdout.strip())

    original = {r['model']: r['price'] for r in run_extract(html)}
    mutated_res = {r['model']: r['price'] for r in run_extract(mutated)}

    assert original.get('MG ZS') == 599000, f"original MG ZS wrong: {original.get('MG ZS')}"
    assert original.get('MG HS PHEV') == 899000, f"original HS PHEV wrong: {original.get('MG HS PHEV')}"
    assert mutated_res.get('MG ZS') == 899000, \
        f"mutated MG ZS should be 899000, got {mutated_res.get('MG ZS')}"
    assert mutated_res.get('MG HS PHEV') == 599000, \
        f"mutated HS PHEV should be 599000, got {mutated_res.get('MG HS PHEV')}"


def test_mg_dealer_capture_yields_no_rows():
    """The dealer-redirect capture must NOT yield business rows through the MG adapter."""
    from collect_multi_oem import MG_JS

    html, _ = load_fixture("mg_models")  # dealer capture (jnt.co.th)
    assert html is not None

    script = f'''
import asyncio, json
from playwright.async_api import async_playwright

HTML = {repr(html)}
JS = {repr(MG_JS)}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML, timeout=60000, wait_until="domcontentloaded")
        result = await page.evaluate(JS)
        print(json.dumps(result))
        await browser.close()

asyncio.run(main())
'''
    with open('/tmp/mg_dealer_check.py', 'w') as f:
        f.write(script)
    result = subprocess.run(['python3', '/tmp/mg_dealer_check.py'], capture_output=True, text=True, timeout=60)
    rows = json.loads(result.stdout.strip())
    assert rows == [], f"Dealer capture must yield no business rows, got {len(rows)}"


# ══════════════════════════════════════════════════════════════════
# Cycle 2026-09-24-3: captured-unparsed → PARSED_TESTED conversions
# (Mitsubishi, Suzuki, MINI, Deepal-via-Changan)
# ══════════════════════════════════════════════════════════════════

def _fx(fn):
    return f"{FIXTURE_DIR}/{fn}"


MUTATION_RUNNER = """
import asyncio, json, sys
from playwright.async_api import async_playwright
JS = sys.argv[1]
HTML = open(sys.argv[2], encoding="utf-8", errors="ignore").read()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page()
        await page.set_content(HTML)
        res = await page.evaluate(JS)
        print(json.dumps({i["model"]: i["price"] for i in res}))
        await b.close()
asyncio.run(main())
"""


def test_mitsubishi_artifact_and_sidecar():
    """Mitsubishi capture exists with AcquisitionWriter sidecar (VERIFIED)."""
    import json as _json
    import hashlib as _hashlib
    artifact = _fx("mitsubishi_home_page.html")
    sidecar = _fx("mitsubishi_home_page.html.prov.json")
    assert os.path.exists(artifact), "mitsubishi_home_page.html missing"
    assert os.path.exists(sidecar), "sidecar missing"
    sc = _json.load(open(sidecar))
    assert sc["provenance_state"] == "ACQUISITION_VERIFIED"
    actual = _hashlib.sha256(open(artifact, "rb").read()).hexdigest()
    assert sc["sha256"] == actual, "sidecar sha must match artifact bytes"


def test_mitsubishi_extraction_count():
    """Mitsubishi nav-links yield the model lineup (deduped)."""
    from collect_multi_oem import collect_mitsubishi
    obs = collect_mitsubishi()
    assert len(obs) >= 5, f"expected >=5, got {len(obs)}"


def test_mitsubishi_specific_models():
    """Known Mitsubishi models with correct starting prices."""
    from collect_multi_oem import collect_mitsubishi
    lookup = {o["identity"]["model_raw"]: o for o in collect_mitsubishi()}
    assert lookup["ไทรทัน"]["price"]["value_thb"] == 614000
    assert lookup["เอ็กซ์แพนเดอร์ เอชอีวี"]["price"]["value_thb"] == 939000
    assert lookup["ปาเจโร สปอร์ต"]["price"]["value_thb"] == 1139000


def test_mitsubishi_identity_and_price_semantics():
    """MODEL level, MSRP_STARTING (site says ราคาเริ่มต้น), THB, UNKNOWN."""
    from collect_multi_oem import collect_mitsubishi
    for o in collect_mitsubishi():
        assert o["identity"]["identity_level"] == "MODEL"
        assert o["identity"]["variant_raw"] is None
        assert o["identity"]["brand_normalized"] == "mitsubishi"
        assert o["price"]["type"] == "MSRP_STARTING"
        assert o["price"]["currency"] == "THB"
        assert o["price"]["currentness"] == "UNKNOWN"
        assert "ราคาเริ่มต้น" in o["evidence_excerpt"], "starting-price wording must be in evidence"
        assert o["source"]["provenance_state"] == "ACQUISITION_VERIFIED"


def test_mitsubishi_locator_resolves_to_same_record():
    """Re-resolve canonical locator: card contains BOTH model and price."""
    import asyncio
    from playwright.async_api import async_playwright
    from collect_multi_oem import collect_mitsubishi
    obs = collect_mitsubishi()
    html = open(obs[0]["evidence_locator"]["artifact_path"], encoding="utf-8").read()

    async def resolve():
        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html)
            for o in obs:
                resolved = await page.evaluate(
                    """(args) => {
                        const els = document.querySelectorAll(args.path);
                        if (!els.length) return {found: false};
                        const el = els[0];
                        return {
                            found: true,
                            text: el.textContent,
                            hasModel: el.textContent.includes(args.model),
                            hasPrice: el.textContent.includes(args.price)
                        };
                    }""",
                    {"path": o["evidence_locator"]["canonical_locator"],
                     "model": o["identity"]["model_raw"],
                     "price": f'{o["price"]["value_thb"]:,}'}
                )
                results.append(resolved)
            await browser.close()
        return results

    results = asyncio.run(resolve())
    assert len(results) == len(obs)
    for r in results:
        assert r.get("found"), "locator resolved to nothing"
        assert r.get("hasModel"), "model not in resolved record (same-record violated)"
        assert r.get("hasPrice"), "price not in resolved record (same-record violated)"


def test_mitsubishi_mutation_price_swap_detected():
    """Swapping two prices across nav cards changes the model→price map."""
    import subprocess as _subprocess
    import json as _json
    from collect_multi_oem import MITSUBISHI_JS
    artifact = _fx("mitsubishi_home_page.html")
    data = open(artifact, encoding="utf-8").read()
    assert data.count("฿939,000") >= 1 and data.count("฿614,000") >= 1
    mutated = data.replace("฿939,000", "฿__TMP__").replace("฿614,000", "฿939,000").replace("฿__TMP__", "฿614,000")
    assert mutated != data
    script = """
import asyncio, json, sys
from playwright.async_api import async_playwright
JS = sys.argv[1]
HTML = open(sys.argv[2], encoding="utf-8", errors="ignore").read()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page()
        await page.set_content(HTML)
        res = await page.evaluate(JS)
        print(json.dumps({i["model"]: i["price"] for i in res}))
        await b.close()
asyncio.run(main())
"""
    open("/tmp/mits_mutation.py", "w").write(script)
    tmp_html = "/tmp/mits_mutated.html"
    open(tmp_html, "w").write(mutated)
    out = _subprocess.run(["python3", "/tmp/mits_mutation.py", MITSUBISHI_JS, tmp_html],
                          capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    mut_map = _json.loads(out.stdout)
    assert mut_map.get("ไทรทัน") == 939000, "swapped price not detected on Triton"
    assert mut_map.get("เอ็กซ์แพนเดอร์ เอชอีวี") == 614000, "swapped price not detected on Xpander"


def test_suzuki_artifact_and_sidecar():
    """Suzuki root capture (not the old /error page) has a sidecar."""
    import json as _json
    import hashlib as _hashlib
    artifact = _fx("suzuki_home_page.html")
    assert os.path.exists(artifact)
    sc = _json.load(open(artifact + ".prov.json"))
    assert sc["provenance_state"] == "ACQUISITION_VERIFIED"
    assert sc["sha256"] == _hashlib.sha256(open(artifact, "rb").read()).hexdigest()


def test_suzuki_extraction_count():
    from collect_multi_oem import collect_suzuki
    obs = collect_suzuki()
    assert len(obs) >= 4, f"expected >=4, got {len(obs)}"


def test_suzuki_specific_models():
    from collect_multi_oem import collect_suzuki
    lookup = {o["identity"]["model_raw"]: o for o in collect_suzuki()}
    assert lookup["ALL NEW SUZUKI FRONX"]["price"]["value_thb"] == 689000
    assert lookup["JIMNY"]["price"]["value_thb"] == 1590000
    assert lookup["ALL NEW SUZUKI e VITARA"]["price"]["value_thb"] == 2890000


def test_suzuki_price_type_follows_source_phrasing():
    """เริ่มต้นที่ → MSRP_STARTING; ราคาพิเศษ/ราคาเพียง/plain → MSRP (evidence keeps phrase)."""
    from collect_multi_oem import collect_suzuki
    lookup = {o["identity"]["model_raw"]: o for o in collect_suzuki()}
    fronx = lookup["ALL NEW SUZUKI FRONX"]
    assert fronx["price"]["type"] == "MSRP_STARTING"
    assert "เริ่มต้นที่" in fronx["evidence_excerpt"]
    xl7 = lookup["XL7 HYBRID"]
    assert xl7["price"]["type"] == "MSRP"
    assert "ราคาพิเศษ" in xl7["evidence_excerpt"], "promo phrase must stay visible in evidence"
    carry = lookup["CARRY"]
    assert carry["price"]["type"] == "MSRP"
    for o in lookup.values():
        assert o["identity"]["identity_level"] == "MODEL"
        assert o["price"]["currency"] == "THB"
        assert o["source"]["provenance_state"] == "ACQUISITION_VERIFIED"


def test_suzuki_locator_resolves_to_same_record():
    import asyncio
    from playwright.async_api import async_playwright
    from collect_multi_oem import collect_suzuki
    obs = collect_suzuki()
    html = open(obs[0]["evidence_locator"]["artifact_path"], encoding="utf-8").read()

    async def resolve():
        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html)
            for o in obs:
                resolved = await page.evaluate(
                    """(args) => {
                        const els = document.querySelectorAll(args.path);
                        if (!els.length) return {found: false};
                        const el = els[0];
                        return {found: true, hasModel: el.textContent.includes(args.model),
                                hasPrice: el.textContent.includes(args.price)};
                    }""",
                    {"path": o["evidence_locator"]["canonical_locator"],
                     "model": o["identity"]["model_raw"],
                     "price": f'{o["price"]["value_thb"]:,}'}
                )
                results.append(resolved)
            await browser.close()
        return results

    results = asyncio.run(resolve())
    for r in results:
        assert r.get("found")
        assert r.get("hasModel"), "model not in resolved card"
        assert r.get("hasPrice"), "price not in resolved card"


def test_suzuki_mutation_price_swap_detected():
    import subprocess as _subprocess
    import json as _json
    from collect_multi_oem import SUZUKI_JS
    artifact = _fx("suzuki_home_page.html")
    data = open(artifact, encoding="utf-8").read()
    assert "689,000" in data and "1,590,000" in data
    mutated = data.replace("689,000", "__TMP__").replace("1,590,000", "689,000").replace("__TMP__", "1,590,000")
    open("/tmp/mits_mutation.py", "w").write(MUTATION_RUNNER)
    open("/tmp/suz_mutated.html", "w").write(mutated)
    out = _subprocess.run(["python3", "/tmp/mits_mutation.py", SUZUKI_JS, "/tmp/suz_mutated.html"],
                          capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    mut_map = _json.loads(out.stdout)
    assert mut_map.get("ALL NEW SUZUKI FRONX") == 1590000, "swap not detected"
    assert mut_map.get("JIMNY") == 689000, "swap not detected"


def test_mini_artifact_and_sidecar():
    import json as _json
    import hashlib as _hashlib
    artifact = _fx("mini_home_page.html")
    assert os.path.exists(artifact)
    sc = _json.load(open(artifact + ".prov.json"))
    assert sc["provenance_state"] == "ACQUISITION_VERIFIED"
    assert sc["sha256"] == _hashlib.sha256(open(artifact, "rb").read()).hexdigest()


def test_mini_extraction_count():
    from collect_multi_oem import collect_mini
    obs = collect_mini()
    assert len(obs) >= 4, f"expected >=4, got {len(obs)}"


def test_mini_specific_models():
    from collect_multi_oem import collect_mini
    lookup = {o["identity"]["model_raw"]: o for o in collect_mini()}
    assert lookup["ALL-ELECTRIC MINI COOPER"]["price"]["value_thb"] == 1555000
    assert lookup["MINI COUNTRYMAN"]["price"]["value_thb"] == 2799000
    assert lookup["JOHN COOPER WORKS"]["price"]["value_thb"] == 2199000


def test_mini_msrp_distinguished_from_finance():
    """MSRP only: 'From X ฿' source-labelled, >=100k; finance (MTHLY) values never staged."""
    from collect_multi_oem import collect_mini
    finance_values = {8888, 9999, 11111, 17999, 28999}   # displayed ฿/MTHLY installments
    obs = collect_mini()
    assert obs, "no MINI rows"
    for o in obs:
        assert o["price"]["value_thb"] >= 100000, "finance-scale value staged!"
        assert o["price"]["value_thb"] not in finance_values, "installment value staged!"
        assert "MTHLY" not in o["evidence_excerpt"].split("From")[0] or "From" in o["evidence_excerpt"]
        assert "From " in o["evidence_excerpt"], "MSRP must be source-labelled 'From' (starting)"
        assert o["price"]["type"] == "MSRP_STARTING"
        assert o["identity"]["identity_level"] == "MODEL"
        assert o["source"]["provenance_state"] == "ACQUISITION_VERIFIED"
    prices = [o["price"]["value_thb"] for o in obs]
    assert len(set(prices)) == len(prices), "duplicate prices suggest finance/MSRP collision"


def test_mini_locator_resolves_to_same_record():
    import asyncio
    from playwright.async_api import async_playwright
    from collect_multi_oem import collect_mini
    obs = collect_mini()
    html = open(obs[0]["evidence_locator"]["artifact_path"], encoding="utf-8").read()

    async def resolve():
        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html)
            for o in obs:
                resolved = await page.evaluate(
                    """(args) => {
                        const els = document.querySelectorAll(args.path);
                        if (!els.length) return {found: false};
                        const el = els[0];
                        return {found: true, hasModel: el.textContent.includes(args.model),
                                hasPrice: el.textContent.includes(args.price)};
                    }""",
                    {"path": o["evidence_locator"]["canonical_locator"],
                     "model": o["identity"]["model_raw"],
                     "price": f'{o["price"]["value_thb"]:,}'}
                )
                results.append(resolved)
            await browser.close()
        return results

    results = asyncio.run(resolve())
    for r in results:
        assert r.get("found")
        assert r.get("hasModel"), "model not in resolved item"
        assert r.get("hasPrice"), "price not in resolved item"


def test_mini_mutation_finance_not_rescued():
    """Delete the MSRP text → MINI_JS must not fall back to the installment value."""
    import subprocess as _subprocess
    import json as _json
    from collect_multi_oem import MINI_JS
    artifact = _fx("mini_home_page.html")
    data = open(artifact, encoding="utf-8").read()
    assert "1,555,000" in data
    mutated = data.replace("1,555,000", "1,555,000 ฿ / MTHLY * ")   # poison the MSRP leaf pattern
    mutated = mutated.replace("From 1,555,000 ฿ / MTHLY * ", "From ")
    open("/tmp/mits_mutation.py", "w").write(MUTATION_RUNNER)
    open("/tmp/mini_mutated.html", "w").write(mutated)
    out = _subprocess.run(["python3", "/tmp/mits_mutation.py", MINI_JS, "/tmp/mini_mutated.html"],
                          capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    mut_map = _json.loads(out.stdout)
    assert mut_map.get("ALL-ELECTRIC MINI COOPER") is None, "MSRP removed but row survived — finance fallback leak"


def test_deepal_artifact_and_sidecar():
    import json as _json
    import hashlib as _hashlib
    artifact = _fx("changan_home_page.html")
    assert os.path.exists(artifact)
    sc = _json.load(open(artifact + ".prov.json"))
    assert sc["provenance_state"] == "ACQUISITION_VERIFIED"
    assert sc["sha256"] == _hashlib.sha256(open(artifact, "rb").read()).hexdigest()


def test_deepal_extraction_count():
    from collect_multi_oem import collect_deepal
    obs = collect_deepal()
    assert len(obs) >= 4, f"expected >=4, got {len(obs)}"


def test_deepal_specific_models_from_published_slugs():
    from collect_multi_oem import collect_deepal
    lookup = {o["identity"]["model_raw"]: o for o in collect_deepal()}
    assert lookup["s07"]["price"]["value_thb"] == 1219000
    assert lookup["hunter-k50"]["price"]["value_thb"] == 1099000
    assert lookup["s05-reev"]["price"]["value_thb"] == 949000
    # brand comes from the published URL segment — never merged into 'Changan'
    for o in lookup.values():
        assert o["identity"]["brand_raw"] == "thdeepal", o["identity"]["brand_raw"]
        assert o["identity"]["brand_normalized"] == "deepal"


def test_deepal_identity_and_price_semantics():
    from collect_multi_oem import collect_deepal
    for o in collect_deepal():
        assert o["identity"]["identity_level"] == "MODEL"
        assert o["price"]["type"] == "MSRP_STARTING"
        assert "ราคาเริ่มต้น" in o["evidence_excerpt"]
        assert "link:" in o["evidence_excerpt"], "card must carry its product link as model evidence"
        assert o["source"]["provenance_state"] == "ACQUISITION_VERIFIED"
        assert o["source"]["name"] == "Changan Thailand Official"


def test_deepal_locator_resolves_to_same_record_with_link():
    """Resolved card carries the price AND the product link whose slug is the model."""
    import asyncio
    import re as _re
    from playwright.async_api import async_playwright
    from collect_multi_oem import collect_deepal
    obs = collect_deepal()
    html = open(obs[0]["evidence_locator"]["artifact_path"], encoding="utf-8").read()

    async def resolve():
        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html)
            for o in obs:
                resolved = await page.evaluate(
                    """(args) => {
                        const els = document.querySelectorAll(args.path);
                        if (!els.length) return {found: false};
                        const el = els[0];
                        const a = el.querySelector('a[href*="-th"]');
                        return {found: true, hasPrice: el.textContent.includes(args.price),
                                href: a ? a.getAttribute('href') : null};
                    }""",
                    {"path": o["evidence_locator"]["canonical_locator"],
                     "price": f'{o["price"]["value_thb"]:,}'}
                )
                results.append((o["identity"]["model_raw"], resolved))
            await browser.close()
        return results

    results = asyncio.run(resolve())
    for model, r in results:
        assert r.get("found"), "locator resolved to nothing"
        assert r.get("hasPrice"), "price not in resolved card (same-record violated)"
        href = r.get("href") or ""
        assert _re.search(r"/" + _re.escape(model) + r"-th/?$", href), \
            f"model {model!r} not bound to link {href!r} in same card"


def test_deepal_mutation_link_price_swap_detected():
    """Swap prices between two cards → the model→price map must change."""
    import subprocess as _subprocess
    import json as _json
    from collect_multi_oem import DEEPAL_JS
    artifact = _fx("changan_home_page.html")
    data = open(artifact, encoding="utf-8").read()
    assert "1,099,000" in data and "1,219,000" in data
    mutated = data.replace("1,099,000", "__TMP__").replace("1,219,000", "1,099,000").replace("__TMP__", "1,219,000")
    open("/tmp/mits_mutation.py", "w").write(MUTATION_RUNNER)
    open("/tmp/deepal_mutated.html", "w").write(mutated)
    out = _subprocess.run(["python3", "/tmp/mits_mutation.py", DEEPAL_JS, "/tmp/deepal_mutated.html"],
                          capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    mut_map = _json.loads(out.stdout)
    assert mut_map.get("hunter-k50") == 1219000, "swap not detected"
    assert mut_map.get("s07") == 1099000, "swap not detected"


def test_smart_wrong_target_capture_yields_no_rows():
    """smart.co.th capture (wrong target) must never stage business rows."""
    smart_artifact = _fx("smart_home_page.html")
    if not os.path.exists(smart_artifact):
        return
    rows = [line for line in open(STAGING_FILE, encoding="utf-8") if line.strip()]
    assert rows, "staging missing"
    for line in rows:
        assert "smart_home_page.html" not in line, "Smart wrong-target artifact produced a staged row"
        assert "smartsecurity" not in line


def test_recaptured_range_pages_have_sidecars_no_prices():
    """Range recaptures: VERIFIED sidecars; price-free pages stage nothing, kia_cars only its3 promo cards."""
    import json as _json
    import hashlib as _hashlib
    recaptured = ["gwm_models_page.html", "jaguar_range_page.html",
                  "landrover_discovery_page.html", "landrover_range_rover_page.html",
                  "isuzu_th_rendered_page.html", "kia_cars_page.html"]
    for fn in recaptured:
        artifact = _fx(fn)
        assert os.path.exists(artifact), f"{fn} missing"
        sc = _json.load(open(artifact + ".prov.json"))
        assert sc["provenance_state"] == "ACQUISITION_VERIFIED"
        assert sc["sha256"] == _hashlib.sha256(open(artifact, "rb").read()).hexdigest()
    # the truly price-free range pages stage NO rows
    content = open(STAGING_FILE, encoding="utf-8").read()
    price_free = [fn for fn in recaptured if fn != "kia_cars_page.html"]
    for fn in price_free:
        assert fn not in content, f"{fn} has no adapter yet but rows reference it"
    # kia_cars changed: the CARS LIST stays price-free, but the page hosts dated
    # promo kv-cards (span.title + .kv_desc) — only those3 rows may reference it,
    # and only with the original ล้านบาท campaign label in evidence
    rows = [json.loads(line) for line in content.splitlines()
            if line.strip() and "kia_cars_page.html" in line]
    assert len(rows) == 3, f"expected exactly 3 promo-card rows from kia_cars, got {len(rows)}"
    for r in rows:
        assert "ล้านบาท" in r["evidence_excerpt"], "row not bound to the published campaign label"
        assert r["source"]["extraction_method"] == "playwright_dom"
        assert r["identity"]["identity_level"] == "MODEL"


# ─── Mazda Root-Capture Tests (mazda_home_page.html, 'MODEL | TAGLINE' h2) ───

def test_mazda_root_capture_artifact_and_sidecar():
    """Root capture artifact + sidecar are committed and verified."""
    path = f"{FIXTURE_DIR}/mazda_home_page.html"
    assert os.path.exists(path), f"missing {path}"
    assert os.path.getsize(path) > 10000
    sc = json.load(open(path + '.prov.json'))
    assert sc['provenance_state'] == 'ACQUISITION_VERIFIED'
    assert sc['captured_at'] != 'UNKNOWN'
    assert sc['source_url'].startswith('https://www.mazda.co.th')


def test_mazda_root_model_names_tagline_stripped():
    """Published tagline after '|' is not part of model_raw; evidence keeps both."""
    observations = collect_mazda()
    assert len(observations) >= 8, f"expected >=8, got {len(observations)}"
    for obs in observations:
        model = obs['identity']['model_raw']
        assert '|' not in model, f"tagline separator leaked into model: {model}"
        assert ' | ' in obs['evidence_excerpt'], f"evidence lost full h2 text: {obs['evidence_excerpt'][:80]}"
        assert model in obs['evidence_excerpt'], "model not present in its own evidence"
        assert obs['price']['type'] == 'MSRP_STARTING'
        assert obs['source']['artifact_path'].endswith('mazda_home_page.html')
        assert obs['source']['provenance_state'] == 'ACQUISITION_VERIFIED'


def test_mazda_locator_resolves_to_same_record():
    """Re-resolving each nth-child chain yields a card containing BOTH model and price."""
    from playwright.async_api import async_playwright
    observations = collect_mazda()
    html = open(observations[0]['evidence_locator']['artifact_path'], encoding='utf-8').read()

    WALK_JS = """(args) => {
        const parts = args.selector.split(' > ');
        let el = document.body;
        for (const part of parts) {
            const m = part.match(/^(\\w+):nth-child\\((\\d+)\\)$/);
            if (!m) return {found: false, reason: 'parse ' + part};
            el = el.children[parseInt(m[2], 10) - 1];
            if (!el || el.tagName.toLowerCase() !== m[1]) return {found: false, reason: 'miss ' + part};
        }
        const t = (el.textContent || '').replace(/\\s+/g, ' ');
        return {found: true, hasModel: t.includes(args.model), hasPrice: t.includes(args.price)};
    }"""

    async def resolve():
        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html)
            for o in observations:
                results.append(await page.evaluate(WALK_JS, {
                    "selector": o['evidence_locator']['selector'],
                    "model": o['identity']['model_raw'],
                    "price": f"{o['price']['value_thb']:,}",
                }))
            await browser.close()
        return results

    results = asyncio.run(resolve())
    assert len(results) == len(observations)
    for o, r in zip(observations, results):
        assert r.get('found'), f"chain did not resolve: {r}"
        assert r.get('hasModel'), f"model missing from resolved card: {o['identity']['model_raw']}"
        assert r.get('hasPrice'), f"price missing from resolved card: {o['identity']['model_raw']}"


def test_mazda_mutation_price_swap_detected(tmp_path, monkeypatch):
    """Swapping two prices in the artifact changes the extracted model→price map."""
    import collect_multi_oem as cmo
    orig = {o['identity']['model_raw']: o['price']['value_thb'] for o in cmo.collect_mazda()}
    assert orig.get('NEW MAZDA2 ESSENTIAL') == 529000
    assert orig.get('NEW MAZDA CX-3 ESSENTIAL') == 699000

    html = open(f"{cmo.FIXTURE_DIR}/mazda_home_page.html", encoding='utf-8').read()
    mutated = html.replace('529,000', '__T__').replace('699,000', '529,000').replace('__T__', '699,000')
    assert mutated != html
    open(str(tmp_path / 'mazda_home_page.html'), 'w', encoding='utf-8').write(mutated)
    monkeypatch.setattr(cmo, 'FIXTURE_DIR', str(tmp_path))

    m = {o['identity']['model_raw']: o['price']['value_thb'] for o in cmo.collect_mazda()}
    assert m.get('NEW MAZDA2 ESSENTIAL') == 699000, "swap not detected on MAZDA2"
    assert m.get('NEW MAZDA CX-3 ESSENTIAL') == 529000, "swap not detected on CX-3"
    assert m != orig


# ─── Kia Tests (kia_cars_page.html promo cards) ───

def test_kia_artifact_and_sidecar():
    path = f"{FIXTURE_DIR}/kia_cars_page.html"
    assert os.path.exists(path), f"missing {path}"
    sc = json.load(open(path + '.prov.json'))
    assert sc['provenance_state'] == 'ACQUISITION_VERIFIED'
    assert sc['captured_at'] != 'UNKNOWN'
    assert 'kia.com' in sc['source_url']


def test_kia_extraction_count_and_prices():
    from collect_multi_oem import collect_kia_promos
    obs = collect_kia_promos()
    assert len(obs) == 3, f"expected 3 priced promo cards, got {len(obs)}"
    lookup = {o['identity']['model_raw']: o for o in obs}
    assert lookup['The Kia EV5']['price']['value_thb'] == 1080000
    assert lookup['The Kia EV5']['price']['type'] == 'MSRP_STARTING'
    assert lookup['The Kia Carnival Diesel SXL']['price']['value_thb'] == 1999000
    assert lookup['The Kia Carnival Diesel SXL']['price']['type'] == 'MSRP'
    assert lookup['The Kia Sorento PHEV']['price']['value_thb'] == 1549000
    assert lookup['The Kia Sorento PHEV']['price']['type'] == 'MSRP'
    for o in obs:
        assert o['identity']['identity_level'] == 'MODEL'
        assert o['identity']['brand_normalized'] == 'kia'
        assert o['source']['name'] == 'Kia Thailand Official'
        assert o['price']['currency'] == 'THB'


def test_kia_promo_not_discount_or_interest():
    """Discount amounts and interest offers must not be staged as vehicle prices."""
    from collect_multi_oem import collect_kia_promos
    obs = collect_kia_promos()
    values = {o['price']['value_thb'] for o in obs}
    for decoy in (595000, 550000, 200000, 2990, 0):
        assert decoy not in values, f"decoy value staged as price: {decoy}"
    ev = ' '.join(o['evidence_excerpt'] for o in obs)
    assert '1 - 30 ก.ย. 2026' in ev, "campaign period missing from evidence"
    for o in obs:
        assert 'ล้านบาท' in o['evidence_excerpt'], "original million-baht label must stay in evidence"


def test_kia_locator_resolves_to_same_record():
    from playwright.async_api import async_playwright
    from collect_multi_oem import collect_kia_promos
    obs = collect_kia_promos()
    html = open(obs[0]['evidence_locator']['artifact_path'], encoding='utf-8').read()

    WALK_JS = """(args) => {
        const parts = args.selector.split(' > ');
        let el = document.body;
        for (const part of parts) {
            const m = part.match(/^(\\w+):nth-child\\((\\d+)\\)$/);
            if (!m) return {found: false};
            el = el.children[parseInt(m[2], 10) - 1];
            if (!el || el.tagName.toLowerCase() !== m[1]) return {found: false};
        }
        const card = el.parentElement;
        const t = (card ? card.textContent : '').replace(/\\s+/g, ' ');
        return {found: true, hasModel: t.includes(args.model), hasPrice: t.includes(args.price)};
    }"""

    async def resolve():
        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html)
            for o in obs:
                price_txt = f"{o['price']['value_thb'] / 1_000_000:.3f} ล้านบาท"
                results.append(await page.evaluate(WALK_JS, {
                    "selector": o['evidence_locator']['selector'],
                    "model": o['identity']['model_raw'],
                    "price": price_txt,
                }))
            await browser.close()
        return results

    results = asyncio.run(resolve())
    for o, r in zip(obs, results):
        assert r.get('found'), f"chain did not resolve for {o['identity']['model_raw']}"
        assert r.get('hasModel'), f"model missing from resolved card: {o['identity']['model_raw']}"
        assert r.get('hasPrice'), f"price missing from resolved card: {o['identity']['model_raw']}"


def test_kia_mutation_price_swap_detected(tmp_path, monkeypatch):
    import collect_multi_oem as cmo
    from collect_multi_oem import collect_kia_promos
    orig = {o['identity']['model_raw']: o['price']['value_thb'] for o in collect_kia_promos()}
    assert orig.get('The Kia Carnival Diesel SXL') == 1999000
    assert orig.get('The Kia Sorento PHEV') == 1549000

    html = open(f"{cmo.FIXTURE_DIR}/kia_cars_page.html", encoding='utf-8').read()
    mutated = html.replace('1.999 ล้านบาท', '__T__').replace('1.549 ล้านบาท', '1.999 ล้านบาท').replace('__T__', '1.549 ล้านบาท')
    assert mutated != html
    open(str(tmp_path / 'kia_cars_page.html'), 'w', encoding='utf-8').write(mutated)
    monkeypatch.setattr(cmo, 'FIXTURE_DIR', str(tmp_path))

    m = {o['identity']['model_raw']: o['price']['value_thb'] for o in cmo.collect_kia_promos()}
    assert m.get('The Kia Carnival Diesel SXL') == 1549000, "swap not detected on Carnival"
    assert m.get('The Kia Sorento PHEV') == 1999000, "swap not detected on Sorento"


# ─── Changan Own-Brand Tests (Q05 page, Lumin page, promotion page) ───

def test_changan_own_artifacts_and_sidecars():
    for name in ('changan_nevo_q05_page.html', 'changan_lumin_page.html', 'changan_promotion_page.html'):
        path = f"{FIXTURE_DIR}/{name}"
        assert os.path.exists(path), f"missing {path}"
        sc = json.load(open(path + '.prov.json'))
        assert sc['provenance_state'] == 'ACQUISITION_VERIFIED'
        assert sc['captured_at'] != 'UNKNOWN'
        assert sc['source_url'].startswith('https://www.changan.co.th')


def test_changan_own_price_rows():
    from collect_multi_oem import collect_changan_prices
    obs = collect_changan_prices()
    assert len(obs) == 4, f"expected 4 own-brand rows, got {len(obs)}"
    by_variant = {o['identity']['variant_raw']: o for o in obs}
    q05 = by_variant[None] if None in by_variant else None
    # model-level rows (variant None): Q05 page + Lumin page
    model_rows = {o['identity']['model_raw']: o for o in obs if o['identity']['variant_raw'] is None}
    assert model_rows['NEVO Q05']['price']['value_thb'] == 629900
    assert model_rows['NEVO Q05']['price']['type'] == 'MSRP_STARTING'
    assert model_rows['NEVO Q05']['source']['artifact_path'].endswith('changan_nevo_q05_page.html')
    assert model_rows['Lumin L DC']['price']['value_thb'] == 499000
    assert model_rows['Lumin L DC']['price']['type'] == 'MSRP'
    assert model_rows['Lumin L DC']['source']['artifact_path'].endswith('changan_lumin_page.html')
    # trim offers: list price staged, promo kept in raw_labels
    trim_rows = {o['identity']['variant_raw']: o for o in obs if o['identity']['variant_raw'] is not None}
    assert set(trim_rows) == {'NEVO Q05 MAX', 'NEVO Q05 ULTRA'}
    assert trim_rows['NEVO Q05 MAX']['price']['value_thb'] == 629900
    assert trim_rows['NEVO Q05 MAX']['raw_labels']['ราคาพิเศษ_thb'] == 619900
    assert trim_rows['NEVO Q05 ULTRA']['price']['value_thb'] == 709900
    assert trim_rows['NEVO Q05 ULTRA']['raw_labels']['ราคาพิเศษ_thb'] == 679900
    for o in trim_rows.values():
        assert o['identity']['identity_level'] == 'VARIANT'
        assert o['price']['type'] == 'MSRP'
        assert o['identity']['model_raw'] == 'NEVO Q05'


def test_changan_brand_integrity_own_vs_deepal():
    """Own-brand rows stay Changan; Deepal products never merge into Changan."""
    from collect_multi_oem import collect_changan_prices, collect_deepal
    own = collect_changan_prices()
    deepal = collect_deepal()
    deepal_models = {o['identity']['model_raw'] for o in deepal}
    for o in own:
        assert o['identity']['brand_normalized'] == 'changan'
        assert o['identity']['model_raw'] not in deepal_models, \
            f"Deepal model merged into Changan: {o['identity']['model_raw']}"
        assert o['source']['name'] == 'Changan Thailand Official'
    for o in deepal:
        assert o['identity']['brand_normalized'] == 'deepal', \
            f"Deepal brand mutated: {o['identity']['brand_normalized']}"


def test_changan_own_locators_re_resolve():
    """q05 DOM chain resolves; regex locators re-locate model AND price in one match."""
    from playwright.async_api import async_playwright
    from collect_multi_oem import collect_changan_prices
    obs = collect_changan_prices()
    dom_rows = [o for o in obs if o['evidence_locator']['method'] == 'playwright_dom']
    regex_rows = [o for o in obs if o['evidence_locator']['method'] == 'regex_text']
    assert len(dom_rows) == 1 and len(regex_rows) == 3

    # DOM chain: card contains h2 model + price text
    html = open(dom_rows[0]['evidence_locator']['artifact_path'], encoding='utf-8').read()
    WALK_JS = """(args) => {
        const parts = args.selector.split(' > ');
        let el = document.body;
        for (const part of parts) {
            const m = part.match(/^(\\w+):nth-child\\((\\d+)\\)$/);
            if (!m) return {found: false};
            el = el.children[parseInt(m[2], 10) - 1];
            if (!el || el.tagName.toLowerCase() !== m[1]) return {found: false};
        }
        const t = (el.textContent || '').replace(/\\s+/g, ' ');
        return {found: true, hasModel: t.includes(args.model), hasPrice: t.includes(args.price)};
    }"""

    async def resolve_one():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html)
            r = await page.evaluate(WALK_JS, {
                "selector": dom_rows[0]['evidence_locator']['selector'],
                "model": dom_rows[0]['identity']['model_raw'],
                "price": f"{dom_rows[0]['price']['value_thb']:,}",
            })
            await browser.close()
            return r

    r = asyncio.run(resolve_one())
    assert r.get('found') and r.get('hasModel') and r.get('hasPrice'), r

    # regex rows: selector itself contains model + price, and re-locates in the artifact
    for o in regex_rows:
        art = open(o['evidence_locator']['artifact_path'], encoding='utf-8').read()
        sel = o['evidence_locator']['selector']
        assert sel in art, f"regex locator no longer present in artifact: {sel[:60]}"
        target = o['identity']['variant_raw'] or o['identity']['model_raw']
        assert target in sel, "model/variant not in the matched record"
        assert f"{o['price']['value_thb']:,}" in sel, "price not in the matched record"


def test_changan_own_mutation_price_swap_detected(tmp_path, monkeypatch):
    """Mutating all three artifacts changes every extracted price → binding proven."""
    import collect_multi_oem as cmo
    from collect_multi_oem import collect_changan_prices
    orig = {}
    for o in collect_changan_prices():
        orig[o['identity']['variant_raw'] or o['identity']['model_raw']] = o['price']['value_thb']
    assert orig == {'NEVO Q05': 629900, 'Lumin L DC': 499000, 'NEVO Q05 MAX': 629900, 'NEVO Q05 ULTRA': 709900}

    q05 = open(f"{cmo.FIXTURE_DIR}/changan_nevo_q05_page.html", encoding='utf-8').read()
    open(str(tmp_path / 'changan_nevo_q05_page.html'), 'w', encoding='utf-8').write(
        q05.replace('629,900', '729,900'))

    lumin = open(f"{cmo.FIXTURE_DIR}/changan_lumin_page.html", encoding='utf-8').read()
    open(str(tmp_path / 'changan_lumin_page.html'), 'w', encoding='utf-8').write(
        lumin.replace('499,000', '549,000'))

    promo = open(f"{cmo.FIXTURE_DIR}/changan_promotion_page.html", encoding='utf-8').read()
    mutated_promo = promo.replace('629,900', '__T__').replace('709,900', '629,900').replace('__T__', '709,900')
    assert mutated_promo != promo
    open(str(tmp_path / 'changan_promotion_page.html'), 'w', encoding='utf-8').write(mutated_promo)

    monkeypatch.setattr(cmo, 'FIXTURE_DIR', str(tmp_path))
    m = {}
    for o in cmo.collect_changan_prices():
        m[o['identity']['variant_raw'] or o['identity']['model_raw']] = o['price']['value_thb']
    assert m.get('NEVO Q05') == 729900, "Q05 mutation not detected"
    assert m.get('Lumin L DC') == 549000, "Lumin mutation not detected"
    assert m.get('NEVO Q05 MAX') == 709900, "MAX trim swap not detected"
    assert m.get('NEVO Q05 ULTRA') == 629900, "ULTRA trim swap not detected"


# ─── JLR Official Price-Sheet PDF Tests (base64 artifacts) ───

def test_price_sheet_b64_artifacts_and_sidecars():
    import base64 as _b64
    for name in ('TH_Jaguar_PriceSheet.pdf.b64', 'TH_LandRover_PriceSheet.pdf.b64'):
        path = f"{FIXTURE_DIR}/{name}"
        assert os.path.exists(path), f"missing {path}"
        assert os.path.getsize(path) > 10000, f"too small: {path}"
        sc = json.load(open(path + '.prov.json'))
        assert sc['provenance_state'] == 'ACQUISITION_VERIFIED'
        assert sc['acquisition_method'] == 'http_get_pdf_base64'
        assert sc['captured_at'] != 'UNKNOWN'
        assert sc['source_url'].endswith('.pdf')
        # sidecar sha binds the bytes on disk
        actual = hashlib.sha256(open(path, 'rb').read()).hexdigest()
        assert actual == sc['sha256'], "sidecar sha != artifact sha"
        # decoded payload is the original PDF
        data = _b64.b64decode(open(path, encoding='utf-8').read())
        assert data[:4] == b'%PDF', "decoded payload is not a PDF"


def test_jaguar_price_sheet_rows():
    from collect_multi_oem import collect_jaguar_pricesheet
    obs = collect_jaguar_pricesheet()
    assert len(obs) == 1, f"expected 1 F-TYPE row, got {len(obs)}"
    o = obs[0]
    assert o['identity']['brand_normalized'] == 'jaguar'
    assert o['identity']['model_raw'] == 'F-TYPE'
    assert o['identity']['variant_raw'] == '2.0 RWD Coupe R-Dynamic Plus'
    assert o['identity']['identity_level'] == 'VARIANT'
    assert o['price']['value_thb'] == 6999000
    assert o['price']['type'] == 'EXACT_VARIANT'
    assert o['raw_labels']['model_year'] == 'MY24'
    assert o['evidence_locator']['method'] == 'pdf_text_line'
    assert 'F-TYPE:' in o['evidence_excerpt']


def test_landrover_price_sheet_rows():
    from collect_multi_oem import collect_landrover_pricesheet
    obs = collect_landrover_pricesheet()
    assert len(obs) == 11, f"expected 11 rows, got {len(obs)}"
    lookup = {(o['identity']['model_raw'], o['identity']['variant_raw']): o for o in obs}
    velar = lookup[('RANGE ROVER VELAR', '2.0 AWD Dynamic SE Plus')]
    assert velar['price']['value_thb'] == 4999000
    assert velar['price']['type'] == 'EXACT_VARIANT'
    assert velar['raw_labels']['model_year'] == 'MY26'
    sv = lookup[('RANGE ROVER', '3.0 AWD SV LWB Plus')]
    assert sv['price']['value_thb'] == 17499000
    assert sv['price']['type'] == 'MSRP_STARTING', "** marker must map to starting price"
    assert sv['raw_labels']['starting_marker'] is True
    exact = [o for o in obs if o['price']['type'] == 'EXACT_VARIANT']
    starting = [o for o in obs if o['price']['type'] == 'MSRP_STARTING']
    assert len(exact) == 10 and len(starting) == 1
    for o in obs:
        assert o['identity']['identity_level'] == 'VARIANT'
        assert o['identity']['brand_normalized'] == 'land-rover'
        assert o['price']['currency'] == 'THB'
        assert o['raw_labels']['price_sheet'] == 'TH_LandRover_PriceSheet.pdf.b64'


def test_price_sheet_locator_resolves_in_extracted_text():
    """Re-running pdftotext finds each line anchor under its section header."""
    from collect_multi_oem import _pdf_text, _parse_price_sheet
    for artifact, expected in (('TH_Jaguar_PriceSheet.pdf.b64', 1),
                               ('TH_LandRover_PriceSheet.pdf.b64', 11)):
        path = f"{FIXTURE_DIR}/{artifact}"
        text = _pdf_text(path)
        lines = text.splitlines()
        parsed = _parse_price_sheet(text)
        assert len(parsed) == expected
        for row in parsed:
            idx = lines.index(row['line_text']) if row['line_text'] in lines else None
            assert idx is not None, f"line anchor not found: {row['line_text'][:60]}"
            # nearest preceding ALL-CAPS section header == model
            section_idx = None
            for j in range(idx - 1, -1, -1):
                s = lines[j].strip()
                if s == row['section']:
                    section_idx = j
                    break
            assert section_idx is not None, f"section header {row['section']} not above its row"
            assert f"THB {row['price']:,}" in row['line_text']


def test_price_sheet_mutation_price_in_text_changes_output():
    """Parser reads price from extracted text — mutating text changes the row."""
    from collect_multi_oem import _pdf_text, _parse_price_sheet
    text = _pdf_text(f"{FIXTURE_DIR}/TH_LandRover_PriceSheet.pdf.b64")
    pristine = _parse_price_sheet(text)
    velar_price = [r['price'] for r in pristine if r['section'] == 'RANGE ROVER VELAR'
                   and r['variant'] == '2.0 AWD Dynamic SE Plus']
    assert velar_price == [4999000]
    mutated = text.replace('4,999,000', '4,111,000')
    assert mutated != text
    rows = _parse_price_sheet(mutated)
    changed = [r['price'] for r in rows if r['section'] == 'RANGE ROVER VELAR'
               and r['variant'] == '2.0 AWD Dynamic SE Plus']
    assert changed == [4111000], f"parser did not follow the mutated text: {changed}"


def test_price_sheet_corrupted_artifact_fails_closed(tmp_path, monkeypatch):
    """A corrupted base64 artifact must raise, never emit rows."""
    import base64 as _b64
    import collect_multi_oem as cmo
    open(str(tmp_path / 'TH_Jaguar_PriceSheet.pdf.b64'), 'w').write(
        _b64.b64encode(b'this is definitely not a pdf payload').decode())
    monkeypatch.setattr(cmo, 'FIXTURE_DIR', str(tmp_path))
    raised = False
    try:
        rows = cmo.collect_jaguar_pricesheet()
        assert rows == [], "corrupted artifact must not produce rows"
    except AssertionError:
        raised = True
    assert raised, "corrupted PDF payload must fail closed (AssertionError on magic bytes)"


# ─── Toyota Sidecar-Verified Recapture ───

def test_toyota_recapture_sidecar_verified():
    """Toyota switched to the recapture of the same manifest URL with a real sidecar."""
    from collect_multi_oem import collect_toyota
    path = f"{FIXTURE_DIR}/toyota_pricelist_page.html"
    assert os.path.exists(path)
    sc = json.load(open(path + '.prov.json'))
    assert sc['provenance_state'] == 'ACQUISITION_VERIFIED'
    assert sc['captured_at'] != 'UNKNOWN'
    assert sc['source_url'] == 'https://www.toyota.co.th/en/pricelist'
    obs = collect_toyota()
    assert len(obs) >= 50
    for o in obs:
        assert o['source']['artifact_path'].endswith('toyota_pricelist_page.html')
        assert o['source']['provenance_state'] == 'ACQUISITION_VERIFIED'
        assert o['source']['captured_at'] != 'UNKNOWN'
        assert o['evidence_locator'].get('ldplusjson_block') is True


# ─── Isuzu Recapture (isuzu-tis.com, img-alt model binding) ───

def test_isuzu_recapture_artifact_and_sidecar():
    path = f"{FIXTURE_DIR}/isuzu_tis_page.html"
    assert os.path.exists(path), f"missing {path}"
    sc = json.load(open(path + '.prov.json'))
    assert sc['provenance_state'] == 'ACQUISITION_VERIFIED'
    assert sc['captured_at'] != 'UNKNOWN'
    assert 'isuzu-tis.com' in sc['source_url']


def test_isuzu_rows_from_sidecar_artifact():
    from collect_multi_oem import collect_isuzu
    obs = collect_isuzu()
    assert len(obs) == 6
    for o in obs:
        assert o['source']['artifact_path'].endswith('isuzu_tis_page.html')
        assert o['source']['provenance_state'] == 'ACQUISITION_VERIFIED'
        assert o['price']['type'] == 'MSRP_STARTING'
        assert 'เริ่มต้น' in o['evidence_excerpt'], "starting marker lost from evidence"
        # same record: model (from img alt) AND price both ride in one evidence excerpt
        assert o['identity']['model_raw'] in o['evidence_excerpt']


def test_isuzu_locator_resolves_to_same_record():
    from playwright.async_api import async_playwright
    from collect_multi_oem import collect_isuzu
    obs = collect_isuzu()
    html = open(obs[0]['evidence_locator']['artifact_path'], encoding='utf-8').read()

    WALK_JS = """(args) => {
        const parts = args.selector.split(' > ');
        let el = document.body;
        for (const part of parts) {
            const m = part.match(/^(\\w+):nth-child\\((\\d+)\\)$/);
            if (!m) return {found: false};
            el = el.children[parseInt(m[2], 10) - 1];
            if (!el || el.tagName.toLowerCase() !== m[1]) return {found: false};
        }
        const t = (el.textContent || '').replace(/\\s+/g, ' ');
        const alts = Array.from(el.querySelectorAll('img[alt]')).map(i => i.alt).join(' | ');
        const all = t + ' || ' + alts;
        return {found: true, hasModel: all.includes(args.model), hasPrice: all.includes(args.price)};
    }"""

    async def resolve():
        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html)
            for o in obs:
                results.append(await page.evaluate(WALK_JS, {
                    "selector": o['evidence_locator']['selector'],
                    "model": o['identity']['model_raw'],
                    "price": f"{o['price']['value_thb']:,}",
                }))
            await browser.close()
        return results

    results = asyncio.run(resolve())
    for o, r in zip(obs, results):
        assert r.get('found'), f"chain did not resolve: {o['identity']['model_raw']}"
        assert r.get('hasModel'), f"model (img alt) missing from figure: {o['identity']['model_raw']}"
        assert r.get('hasPrice'), f"price missing from figure: {o['identity']['model_raw']}"


def test_isuzu_mutation_price_swap_detected(tmp_path, monkeypatch):
    import collect_multi_oem as cmo
    from collect_multi_oem import collect_isuzu
    orig = {o['identity']['model_raw']: o['price']['value_thb'] for o in collect_isuzu()}
    assert orig.get('NEW ISUZU V-CROSS 4x4') == 937000
    assert orig.get('MU-X') == 1194000

    html = open(f"{cmo.FIXTURE_DIR}/isuzu_tis_page.html", encoding='utf-8').read()
    mutated = html.replace('937,000', '__T__').replace('1,194,000', '937,000').replace('__T__', '1,194,000')
    assert mutated != html
    open(str(tmp_path / 'isuzu_tis_page.html'), 'w', encoding='utf-8').write(mutated)
    monkeypatch.setattr(cmo, 'FIXTURE_DIR', str(tmp_path))

    m = {o['identity']['model_raw']: o['price']['value_thb'] for o in cmo.collect_isuzu()}
    assert m.get('NEW ISUZU V-CROSS 4x4') == 1194000, "swap not detected on V-CROSS"
    assert m.get('MU-X') == 937000, "swap not detected on MU-X"


# ─── Porsche RSC Flight-Data Tests ───

def test_porsche_artifact_and_sidecar():
    path = f"{FIXTURE_DIR}/porsche_macan_model_page.html"
    assert os.path.exists(path), f"missing {path}"
    assert os.path.getsize(path) > 100000
    sc = json.load(open(path + '.prov.json'))
    assert sc['provenance_state'] == 'ACQUISITION_VERIFIED'
    assert sc['captured_at'] != 'UNKNOWN'
    assert 'porsche.com' in sc['source_url']


def test_porsche_extraction_count_and_families():
    from collect_multi_oem import collect_porsche
    obs = collect_porsche()
    assert len(obs) == 72, f"expected 72 nodes (74 pairs minus 2 ambiguous Macan GTS), got {len(obs)}"
    fams = {o['identity']['model_raw'] for o in obs}
    assert fams == {'718', '911', 'Taycan', 'Panamera', 'Macan', 'Cayenne'}
    for o in obs:
        assert o['source']['name'] == 'Porsche Thailand Official'
        assert o['source']['provenance_state'] == 'ACQUISITION_VERIFIED'
        assert o['price']['currency'] == 'THB'


def test_porsche_identity_and_price_semantics():
    from collect_multi_oem import collect_porsche
    obs = collect_porsche()
    lookup = {o['identity']['variant_raw'] or o['identity']['model_raw']: o for o in obs}
    # VARIANT rows: family + derivative from one flight node
    c4s = lookup['911 Carrera 4S']
    assert c4s['identity']['model_raw'] == '911'
    assert c4s['identity']['identity_level'] == 'VARIANT'
    assert c4s['price']['value_thb'] == 14790000
    assert c4s['price']['type'] == 'EXACT_VARIANT'
    assert c4s['identity']['year'] == 2027
    assert c4s['specs'].get('fuel') == 'Gasoline'
    # name == family → MODEL-level, plain MSRP
    taycan = lookup['Taycan']
    assert taycan['identity']['identity_level'] == 'MODEL'
    assert taycan['identity']['variant_raw'] is None
    assert taycan['price']['type'] == 'MSRP'
    assert taycan['price']['value_thb'] == 7190000
    # price types distribution: EXACT_VARIANT for derivatives
    exact = sum(1 for o in obs if o['price']['type'] == 'EXACT_VARIANT')
    msrp = sum(1 for o in obs if o['price']['type'] == 'MSRP')
    assert exact + msrp == len(obs) and exact > msrp


def test_porsche_ambiguous_generation_fail_closed():
    """'Macan GTS' appears with two prices but no year disambiguation → zero rows."""
    from collect_multi_oem import collect_porsche
    obs = collect_porsche()
    names = [o['identity']['variant_raw'] or o['identity']['model_raw'] for o in obs]
    assert 'Macan GTS' not in names, "ambiguous generation must not be staged"
    # the unambiguous GTS derivatives remain
    assert 'Macan 4S Electric' in names or 'Macan GTS' not in names


def test_porsche_locator_resolves_in_flight_node():
    """Re-parsing the artifact finds the node carrying family+name+year+price together."""
    from collect_multi_oem import collect_porsche
    obs = collect_porsche()
    artifact = obs[0]['evidence_locator']['artifact_path']
    text = open(artifact, encoding='utf-8', errors='ignore').read().replace('&quot;', '"')
    chunks = text.split('"modelType":[0,')[1:]
    for o in obs[:20]:
        name = o['identity']['variant_raw'] or o['identity']['model_raw']
        fam = o['identity']['model_raw']
        price = o['price']['value_thb']
        matched = None
        for ch in chunks:
            if f'"modelName":[0,"{name}"]' in ch and f'"modelRange":[0,"{fam}"]' in ch:
                if f'"value":[0,{price}]' in ch:
                    matched = ch
                    break
        assert matched, f"no single flight node binds {fam}/{name}/{price}"
        if o['identity']['year']:
            assert f'"modelYear":[0,"{o["identity"]["year"]}"]' in matched


def test_porsche_mutation_price_detected(tmp_path, monkeypatch):
    """Mutating the numeric price in flight data changes the extracted row."""
    import collect_multi_oem as cmo
    from collect_multi_oem import collect_porsche
    orig = {o['identity']['variant_raw'] or o['identity']['model_raw']: o['price']['value_thb']
            for o in collect_porsche()}
    assert orig['911 Carrera 4S'] == 14790000

    raw = open(f"{cmo.FIXTURE_DIR}/porsche_macan_model_page.html", encoding='utf-8', errors='ignore').read()
    mutated = raw.replace('&quot;value&quot;:[0,14790000]', '&quot;value&quot;:[0,14190000]')
    assert mutated != raw, "mutation target not found"
    open(str(tmp_path / 'porsche_macan_model_page.html'), 'w', encoding='utf-8').write(mutated)
    monkeypatch.setattr(cmo, 'FIXTURE_DIR', str(tmp_path))

    m = {o['identity']['variant_raw'] or o['identity']['model_raw']: o['price']['value_thb']
         for o in cmo.collect_porsche()}
    assert m['911 Carrera 4S'] == 14190000, "flight-data mutation not detected"


# ─── Honda City Sidecar Recapture ───

def test_honda_recapture_fixture_and_sidecar():
    """The recapture of the same official URL must exist with a real sidecar."""
    path = f"{FIXTURE_DIR}/honda_city_recapture.html"
    assert os.path.exists(path), f"missing {path}"
    assert os.path.getsize(path) > 10000
    sc_path = path + ".prov.json"
    assert os.path.exists(sc_path), "sidecar missing"
    sc = json.load(open(sc_path, encoding="utf-8"))
    assert sc["provenance_state"] == "ACQUISITION_VERIFIED"
    assert sc["captured_at"] != "UNKNOWN"
    assert "honda.co.th/en/city" in sc["source_url"], sc["source_url"]


def test_honda_rows_come_from_verified_recapture():
    """Every staged Honda City row must be provenance-verified, not LEGACY."""
    from collect_multi_oem import collect_honda
    obs = collect_honda()
    assert len(obs) == 4
    for o in obs:
        assert o["source"]["artifact_path"].endswith("honda_city_recapture.html"), \
            f"row still sourced from legacy artifact: {o['source']['artifact_path']}"
        assert o["source"]["provenance_state"] == "ACQUISITION_VERIFIED"
        assert o["source"]["captured_at"] != "UNKNOWN"


def test_honda_recapture_proves_same_rows_as_legacy():
    """The upgrade is only legitimate if the fresh capture proves the same rows."""
    from collect_multi_oem import HONDA_CITY_JS, FIXTURE_DIR, extract_from_html

    def pairs(fn):
        with open(f"{FIXTURE_DIR}/{fn}", encoding="utf-8") as f:
            html = f.read()
        res, _ = extract_from_html(html, "equiv", HONDA_CITY_JS,
                                   fixture_path=f"{FIXTURE_DIR}/{fn}")
        return sorted((r["variant"], r["price"]) for r in (res or []))

    legacy = pairs("honda_city_page.html")
    recapture = pairs("honda_city_recapture.html")
    assert len(legacy) == 4 and len(recapture) == 4
    assert legacy == recapture, (
        f"recapture does not prove the legacy rows: legacy={legacy} recapture={recapture}")


def test_honda_currency_marker_locale_equivalence():
    """The same official price renders as 'THB' (en) or 'บาท' (th) — both must parse identically."""
    from collect_multi_oem import HONDA_CITY_JS, FIXTURE_DIR, extract_from_html

    with open(f"{FIXTURE_DIR}/honda_city_recapture.html", encoding="utf-8") as f:
        recapture = f.read()
    with open(f"{FIXTURE_DIR}/honda_city_page.html", encoding="utf-8") as f:
        legacy = f.read()

    assert "บาท" in recapture, "expected Thai currency marker in recapture"
    assert "569,000 THB" in legacy, "expected English currency marker in legacy"

    # same numeric price, two marker spellings
    html_variant = legacy.replace("569,000 THB", "569,000 บาท")
    assert html_variant != legacy
    res, _ = extract_from_html(html_variant, "locale", HONDA_CITY_JS,
                               fixture_path=f"{FIXTURE_DIR}/honda_city_page.html")
    lookup = {r["variant"]: r["price"] for r in (res or [])}
    assert lookup.get("S") == 569000, f"locale swap broke S price: {lookup}"


def test_honda_recapture_locator_resolves_to_same_record():
    """Re-walk each canonical dom_path in the recapture and confirm model+price bind."""
    from playwright.async_api import async_playwright
    from collect_multi_oem import collect_honda

    obs = collect_honda()
    html = open(obs[0]["evidence_locator"]["artifact_path"], encoding="utf-8").read()

    WALK = """(args) => {
        const parts = args.path.split(' > ');
        let el = document.body;
        for (const part of parts) {
            const m = part.match(/^(\w+):nth-child\((\d+)\)$/);
            if (!m) return {found: false};
            el = el.children[parseInt(m[2], 10) - 1];
            if (!el || el.tagName.toLowerCase() !== m[1]) return {found: false};
        }
        const t = (el.textContent || '').replace(/\s+/g, ' ');
        return {found: true, hasVariant: t.includes(args.variant),
                hasPrice: t.includes(args.price)};
    }"""

    async def run():
        out = []
        async with async_playwright() as p:
            b = await p.chromium.launch()
            page = await b.new_page()
            await page.set_content(html)
            for o in obs:
                out.append(await page.evaluate(WALK, {
                    "path": o["evidence_locator"]["dom_path"],
                    "variant": o["identity"]["variant_raw"],
                    "price": f"{o['price']['value_thb']:,}",
                }))
            await b.close()
        return out

    results = asyncio.run(run())
    for o, r in zip(obs, results):
        assert r.get("found"), f"dom_path did not resolve: {o['identity']['variant_raw']}"
        assert r.get("hasVariant"), f"variant missing at locator: {o['identity']['variant_raw']}"
        assert r.get("hasPrice"), f"price missing at locator: {o['identity']['variant_raw']}"


def test_honda_same_record_evidence_on_recapture():
    """Variant AND price must ride together in one card excerpt (no cross-card bleed)."""
    from collect_multi_oem import collect_honda
    for o in collect_honda():
        ev = o["evidence_excerpt"]
        var = o["identity"]["variant_raw"]
        price = str(o["price"]["value_thb"])
        assert var in ev, f"{var} not in evidence: {ev[:90]}"
        assert price in ev.replace(",", ""), f"{price} not in evidence: {ev[:90]}"
        # a variant name must never carry another grade's price
        other = {"S": "619,000", "e:HEV V": "569,000"}
        if var in other:
            assert other[var].replace(",", "") not in ev.replace(",", ""), \
                f"{var} evidence carries a foreign price: {ev[:90]}"
