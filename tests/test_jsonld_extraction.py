"""
Extraction test — proves Toyota JSON-LD extraction produces correct results.

Reviewer can verify: open the raw artifact, follow the locator, see the same data.
"""
import json
import os
import sys

sys.path.insert(0, 'scripts')
from collect_real_data import extract_toyota_prices

ARTIFACT_DIR = "audit/data-staging/raw-artifacts"
STAGING_FILE = "audit/data-staging/vehicle_observations.jsonl"


def get_toyota_artifact():
    """Find Toyota artifact file."""
    for f in os.listdir(ARTIFACT_DIR):
        if f.startswith('toyota_') and f.endswith('.html'):
            return os.path.join(ARTIFACT_DIR, f)
    return None


def test_jsonld_extraction_count():
    """Extractor must produce observations from actual artifact."""
    artifact = get_toyota_artifact()
    assert artifact, "Toyota artifact not found"
    
    with open(artifact) as f:
        html = f.read()
    
    observations = extract_toyota_prices(
        html,
        "https://www.toyota.co.th/en/pricelist",
        artifact
    )
    
    # Must extract > 0 observations
    assert len(observations) > 0, "Extractor produced 0 observations"
    
    # Toyota page has ~99 variants — should get at least 50
    assert len(observations) >= 50, f"Expected >= 50 observations, got {len(observations)}"


def test_every_observation_has_variant():
    """Every Toyota observation must have exact variant/trim from JSON-LD."""
    artifact = get_toyota_artifact()
    with open(artifact) as f:
        html = f.read()
    
    observations = extract_toyota_prices(
        html,
        "https://www.toyota.co.th/en/pricelist",
        artifact
    )
    
    for obs in observations:
        assert obs['identity']['variant_raw'] is not None, \
            f"variant_raw is None for {obs['identity']['model_raw']}"
        assert obs['identity']['identity_level'] == 'VARIANT', \
            f"identity_level is not VARIANT: {obs['identity']['identity_level']}"


def test_price_currentness_not_always_current():
    """Currentness must reflect actual availability, not always CURRENT."""
    artifact = get_toyota_artifact()
    with open(artifact) as f:
        html = f.read()
    
    observations = extract_toyota_prices(
        html,
        "https://www.toyota.co.th/en/pricelist",
        artifact
    )
    
    currentnesses = set(obs['price']['currentness'] for obs in observations)
    # Should have at least two different currentness values
    # (InStock → CURRENT, OutOfStock → UNKNOWN)
    assert len(currentnesses) >= 2, \
        f"Expected multiple currentness values, got: {currentnesses}"


def test_evidence_locator_is_jsonld_path():
    """Evidence locator must be JSON-LD path, not generic html_pattern."""
    artifact = get_toyota_artifact()
    with open(artifact) as f:
        html = f.read()
    
    observations = extract_toyota_prices(
        html,
        "https://www.toyota.co.th/en/pricelist",
        artifact
    )
    
    for obs in observations:
        locator = obs['evidence_locator']
        assert 'ldplusjson_block' in locator and locator['ldplusjson_block'] == True, \
            f"ldplusjson_block not True for {obs['identity']['model_raw']}"
        assert 'json_path' in locator, \
            f"json_path missing for {obs['identity']['model_raw']}"
        assert 'hasVariant' in locator['json_path'], \
            f"json_path doesn't reference hasVariant: {locator['json_path']}"


def test_specific_vehicle_extraction():
    """Specific vehicles must extract with correct model/variant/price."""
    artifact = get_toyota_artifact()
    with open(artifact) as f:
        html = f.read()
    
    observations = extract_toyota_prices(
        html,
        "https://www.toyota.co.th/en/pricelist",
        artifact
    )
    
    # Build lookup by model+variant
    lookup = {}
    for obs in observations:
        key = f"{obs['identity']['model_raw']}|{obs['identity']['variant_raw']}"
        lookup[key] = obs
    
    # Verify specific known vehicles from the page
    assert 'Corolla Altis|HEV Premium' in lookup, \
        f"Corolla Altis/HEV Premium not found. Available: {list(lookup.keys())[:10]}"
    assert lookup['Corolla Altis|HEV Premium']['price']['value_thb'] == 1009000, \
        f"Corolla Altis/HEV Premium price wrong: {lookup['Corolla Altis|HEV Premium']['price']['value_thb']}"
    
    assert 'CAMRY|HEV Smart' in lookup, \
        f"CAMRY/HEV Smart not found"
    assert lookup['CAMRY|HEV Smart']['price']['value_thb'] == 1475000, \
        f"CAMRY/HEV Smart price wrong: {lookup['CAMRY|HEV Smart']['price']['value_thb']}"
    
    assert 'GR 86|GR86' in lookup, \
        f"GR 86/GR86 not found"
    assert lookup['GR 86|GR86']['price']['value_thb'] == 2999000, \
        f"GR 86/GR86 price wrong: {lookup['GR 86|GR86']['price']['value_thb']}"
    
    # GR 86 is OutOfStock → currentness should be UNKNOWN, not CURRENT
    assert lookup['GR 86|GR86']['price']['currentness'] == 'UNKNOWN', \
        f"GR 86/GR86 currentness should be UNKNOWN (OutOfStock), got {lookup['GR 86|GR86']['price']['currentness']}"


def test_staging_rows_match_extractor_output():
    """Staging file must contain rows produced by the extractor, not fabricated data."""
    artifact = get_toyota_artifact()
    with open(artifact) as f:
        html = f.read()
    
    extractor_obs = extract_toyota_prices(
        html,
        "https://www.toyota.co.th/en/pricelist",
        artifact
    )
    
    # Load staging
    staging_toyota = []
    with open(STAGING_FILE) as f:
        for line in f:
            if line.strip():
                obs = json.loads(line)
                if obs['source']['name'] == 'Toyota Thailand Official':
                    staging_toyota.append(obs)
    
    # Staging must have same count as extractor
    assert len(staging_toyota) == len(extractor_obs), \
        f"Staging Toyota count ({len(staging_toyota)}) != extractor count ({len(extractor_obs)})"
    
    # Spot check first observation
    assert staging_toyota[0]['identity']['model_raw'] == extractor_obs[0]['identity']['model_raw'], \
        f"First observation model mismatch"
    assert staging_toyota[0]['price']['value_thb'] == extractor_obs[0]['price']['value_thb'], \
        f"First observation price mismatch"
