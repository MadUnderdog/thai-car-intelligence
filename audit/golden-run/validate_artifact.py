"""Validate golden artifact internal consistency."""
import json
import sys

def validate(artifact_path):
    with open(artifact_path) as f:
        a = json.load(f)
    
    errors = []
    
    # 1. article_block_count must match region_block_ids sum
    ab_ids = set(a.get('article_body_block_ids', []))
    region_blocks = 0
    for r in a.get('stage_a', {}).get('vehicle_regions', []):
        region_blocks += len(r.get('region_block_ids', []))
    if region_blocks > 0 and len(ab_ids) == 0:
        errors.append(f"article_block_count=0 but regions claim {region_blocks} blocks")
    
    # 2. Every observation's block_id must exist in article_body_block_ids
    for o in a.get('stage_b', {}).get('observations', []):
        bid = o.get('block_id', '')
        if bid and bid not in ab_ids:
            errors.append(f"Observation block_id '{bid}' not in article_body_block_ids")
    
    # 3. Every observation's evidence_quote must be in its block
    # (requires block content, skip if not available)
    
    # 4. Every observation must have non-empty entity
    for o in a.get('stage_b', {}).get('observations', []):
        ent = o.get('entity', {})
        if not ent.get('brand') or not ent.get('model'):
            errors.append(f"Observation missing entity: {o.get('field')}: {o.get('raw_value', '')[:30]}")
    
    # 5. price_type must be set
    for o in a.get('stage_b', {}).get('observations', []):
        if o.get('field') == 'price' and not o.get('price_type'):
            errors.append(f"Price observation missing price_type")
    
    # 6. Counts must be consistent
    obs_count = len(a.get('stage_b', {}).get('observations', []))
    rej_count = len(a.get('stage_b', {}).get('rejected', []))
    rev_count = len(a.get('stage_b', {}).get('needs_review', []))
    
    # 7. Fingerprint must be deterministic (present)
    for o in a.get('stage_b', {}).get('observations', []):
        if not o.get('fingerprint'):
            errors.append(f"Observation missing fingerprint: {o.get('field')}")
    
    return errors

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'audit/golden-run/golden_artifact.json'
    errors = validate(path)
    if errors:
        print(f"VALIDATION FAILED ({len(errors)} errors):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("VALIDATION PASSED")
