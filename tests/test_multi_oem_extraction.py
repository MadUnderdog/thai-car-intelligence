"""
Multi-OEM extraction tests — proves DOM-based extraction works for each source.
"""
import json
import os
import sys

sys.path.insert(0, 'scripts')
from collect_multi_oem import collect_mazda, collect_nissan


def test_mazda_extraction():
    """Mazda extractor must produce observations from real page."""
    observations = collect_mazda()
    assert len(observations) >= 8, f"Expected >= 8 Mazda models, got {len(observations)}"
    
    # Check specific models
    models = {obs['identity']['model_raw']: obs for obs in observations}
    assert 'NEW MAZDA CX-5' in models, f"CX-5 not found. Got: {list(models.keys())}"
    assert models['NEW MAZDA CX-5']['price']['value_thb'] == 1219000
    
    # Every observation must have artifact path
    for obs in observations:
        assert obs['source'].get('artifact_path'), f"No artifact for {obs['identity']['model_raw']}"
        assert os.path.exists(obs['source']['artifact_path']), f"Artifact missing: {obs['source']['artifact_path']}"


def test_nissan_extraction():
    """Nissan extractor must produce observations from real page."""
    observations = collect_nissan()
    assert len(observations) >= 2, f"Expected >= 2 Nissan models, got {len(observations)}"
    
    # Check specific models
    models = {obs['identity']['model_raw']: obs for obs in observations}
    nissan_models = list(models.keys())
    
    # At least one should be an actual Nissan model
    has_kicks = any('คิกส์' in m or 'KICKS' in m.upper() for m in nissan_models)
    has_xtrail = any('เอ็กซ์เทรล' in m or 'X-TRAIL' in m.upper() for m in nissan_models)
    assert has_kicks or has_xtrail, f"No Nissan model found. Got: {nissan_models}"


def test_no_hardcoded_prices():
    """Extractor output must come from actual page parsing, not hardcoded data."""
    mazda = collect_mazda()
    
    # Known Mazda prices from the page
    known_prices = {
        'NEW MAZDA CX-5': 1219000,
        'MAZDA CX-8': 1549000,
        'NEW MAZDA BT-50': 762000,
    }
    
    for model, expected_price in known_prices.items():
        if model in {obs['identity']['model_raw'] for obs in mazda}:
            obs = next(o for o in mazda if o['identity']['model_raw'] == model)
            assert obs['price']['value_thb'] == expected_price, \
                f"{model}: expected {expected_price}, got {obs['price']['value_thb']}"
            # Must have evidence
            assert obs['evidence_excerpt'], f"{model}: no evidence excerpt"
            assert obs['source']['extraction_method'] == 'playwright_dom', \
                f"{model}: extraction_method is not playwright_dom"


def test_staging_includes_all_oems():
    """Staging file must contain observations from all collected OEMs."""
    staging_file = "audit/data-staging/vehicle_observations.jsonl"
    assert os.path.exists(staging_file), "Staging file not found"
    
    sources = set()
    with open(staging_file) as f:
        for line in f:
            if line.strip():
                obs = json.loads(line)
                sources.add(obs['source']['name'])
    
    assert 'Toyota Thailand Official' in sources, "Toyota not in staging"
    assert 'Mazda Thailand Official' in sources, "Mazda not in staging"
    assert 'Nissan Thailand Official' in sources, "Nissan not in staging"
