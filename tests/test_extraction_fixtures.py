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
    """Mazda evidence locator must be DOM selector, not text pattern."""
    observations = collect_mazda()
    for obs in observations:
        locator = obs['evidence_locator']
        assert locator.get('method') == 'dom_query', \
            f"method is not dom_query for {obs['identity']['model_raw']}"
        assert 'selector' in locator, \
            f"selector missing for {obs['identity']['model_raw']}"
        assert 'cardCarModelMega' in locator['selector'], \
            f"selector doesn't reference cardCarModelMega: {locator['selector']}"


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
    from collect_multi_oem import collect_honda, collect_isuzu, collect_bmw
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
    from collect_multi_oem import HONDA_CITY_JS, load_fixture, FIXTURE_DIR
    
    html, _ = load_fixture("honda_city")
    
    # Swap prices: 569,000 <-> 619,000
    mutated = html.replace('569,000 THB', 'XXX_PLACEHOLDER_XXX')
    mutated = mutated.replace('619,000 THB', '569,000 THB')
    mutated = mutated.replace('XXX_PLACEHOLDER_XXX', '619,000 THB')
    
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
        with open('/tmp/mutation_test.py', 'w') as f:
            f.write(script)
        result = subprocess.run(['python3', '/tmp/mutation_test.py'], capture_output=True, text=True, timeout=30)
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
    from collect_multi_oem import HONDA_CITY_JS, load_fixture
    import subprocess
    import json
    
    html, _ = load_fixture("honda_city")
    
    # Delete one price
    mutated = html.replace('739,000 THB', '')
    
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
        with open('/tmp/mutation_test2.py', 'w') as f:
            f.write(script)
        result = subprocess.run(['python3', '/tmp/mutation_test2.py'], capture_output=True, text=True, timeout=30)
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
    
    assert 'V-CROSS' in lookup, f"V-CROSS not found"
    assert lookup['V-CROSS']['price']['value_thb'] == 937000
    
    assert 'MU-X' in lookup, f"MU-X not found"
    assert lookup['MU-X']['price']['value_thb'] == 1194000


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
    """Specific BMW models must extract with correct prices."""
    from collect_multi_oem import collect_bmw
    observations = collect_bmw()
    models = {obs['identity']['model_raw']: obs for obs in observations}
    
    # Check specific known models exist with correct prices
    assert 'SAV ใหม่ iX' in models, f"iX not found. Models: {list(models.keys())[:5]}"
    assert models['SAV ใหม่ iX']['price']['value_thb'] == 5799000
    
    assert 'Sedan ซีรีย์3' in models, f"3 Series not found"
    assert models['Sedan ซีรีย์3']['price']['value_thb'] == 2679000
    
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

def test_captured_at_uses_manifest_not_mtime():
    """captured_at must come from acquisition manifest, NOT filesystem mtime."""
    from collect_multi_oem import collect_bmw, collect_honda, load_manifest
    import os
    
    manifest = load_manifest()
    assert 'bmw_models_page.html' in manifest, "BMW not in manifest"
    assert manifest['bmw_models_page.html']['captured_at'] is not None, \
        "BMW captured_at should be set in manifest"
    
    # Get actual observations
    bmw_obs = collect_bmw()
    honda_obs = collect_honda()
    
    # BMW should use manifest timestamp, not mtime
    bmw_captured = bmw_obs[0]['source']['captured_at']
    assert bmw_captured == manifest['bmw_models_page.html']['captured_at'], \
        f"BMW captured_at should match manifest, got {bmw_captured}"
    
    # Honda should use manifest timestamp
    honda_captured = honda_obs[0]['source']['captured_at']
    assert honda_captured == manifest['honda_city_page.html']['captured_at'], \
        f"Honda captured_at should match manifest, got {honda_captured}"
    
    # Verify it's NOT the file mtime
    bmw_path = 'tests/fixtures/oem-artifacts/bmw_models_page.html'
    mtime_iso = datetime.fromtimestamp(os.path.getmtime(bmw_path), tz=timezone.utc).isoformat()
    # Manifest timestamp should be different from mtime (or explicitly UNKNOWN)
    assert bmw_captured != mtime_iso or bmw_captured == 'UNKNOWN', \
        f"captured_at should not be derived from mtime"


def test_unknown_capture_time_for_mazda_nissan():
    """Fixtures without provenance must have UNKNOWN captured_at."""
    from collect_multi_oem import collect_mazda, collect_nissan
    
    mazda_obs = collect_mazda()
    nissan_obs = collect_nissan()
    
    # These have no provenance record
    assert mazda_obs[0]['source']['captured_at'] == 'UNKNOWN', \
        f"Mazda captured_at should be UNKNOWN, got {mazda_obs[0]['source']['captured_at']}"
    assert nissan_obs[0]['source']['captured_at'] == 'UNKNOWN', \
        f"Nissan captured_at should be UNKNOWN, got {nissan_obs[0]['source']['captured_at']}"


# ─── BMW Canonical Locator Resolution Test ───

def test_bmw_canonical_locator_resolves_to_exact_card():
    """Each stored canonical_locator must resolve to exactly one card with model+price."""
    from collect_multi_oem import collect_bmw, load_fixture
    import asyncio
    from playwright.async_api import async_playwright
    
    observations = collect_bmw()
    html, _ = load_fixture("bmw_models")
    
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

