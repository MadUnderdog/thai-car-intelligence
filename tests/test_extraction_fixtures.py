"""
Fixture-based extraction tests — run from committed artifacts, no live web.

Each test loads a committed HTML fixture, runs the adapter's extraction logic,
and verifies model/variant/price come from the SAME source record.
"""
import json
import os
import sys
import hashlib

sys.path.insert(0, 'scripts')
from collect_multi_oem import collect_toyota, collect_mazda, collect_nissan

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
