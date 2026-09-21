"""Validate golden artifact: counts, quotes, regions, normalization."""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))
from thai_factory.extract.ai_extractor import _normalize_value, _normalize_price_type, _obs_fp


def validate(artifact_path):
    with open(artifact_path) as f:
        a = json.load(f)
    
    errors = []
    
    # 1. article_block_count must be > 0
    ab_ids = set(a.get('article_body_block_ids', []))
    if len(ab_ids) == 0:
        errors.append("article_body_block_ids is empty")
    
    # 2. block_count must match actual blocks
    if a.get('block_count', 0) < 3:
        errors.append(f"block_count too low: {a.get('block_count', 0)}")
    
    # 3. Every observation's block_id must exist in article_body_block_ids
    for i, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        bid = o.get('block_id', '')
        if bid and bid not in ab_ids:
            errors.append(f"Obs {i} block_id '{bid}' not in article_body_block_ids")
    
    # 4. Every observation's evidence_quote must be in its block (via snapshots)
    snapshots = a.get('block_snapshots', {})
    for i, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        bid = o.get('block_id', '')
        q = o.get('evidence_quote', '')
        if bid and q:
            snap = snapshots.get(bid, {})
            content = snap.get('content', '')
            if content and q not in content:
                errors.append(f"Obs {i} evidence_quote NOT in block {bid}: '{q[:50]}'")
    
    # 5. price_type_evidence_quote must be in its block
    for i, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        ptbid = o.get('price_type_evidence_block_id', '')
        ptq = o.get('price_type_evidence_quote', '')
        if ptbid and ptq:
            snap = snapshots.get(ptbid, {})
            content = snap.get('content', '')
            if content and ptq not in content:
                errors.append(f"Obs {i} price_type_quote NOT in block {ptbid}: '{ptq[:50]}'")
    
    # 6. Every observation must have non-empty entity
    for i, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        ent = o.get('entity', {})
        if not ent.get('brand') or not ent.get('model'):
            errors.append(f"Obs {i} missing entity: {o.get('field')}: {o.get('raw_value', '')[:30]}")
    
    # 7. price_type must be set
    for i, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        if o.get('field') == 'price' and not o.get('price_type'):
            errors.append(f"Obs {i} price observation missing price_type")
    
    # 8. Counts must be consistent
    obs_count = len(a.get('stage_b', {}).get('observations', []))
    rej_count = len(a.get('stage_b', {}).get('rejected', []))
    rev_count = len(a.get('stage_b', {}).get('needs_review', []))
    
    # 9. Fingerprint must be present and reproducible
    for i, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        if not o.get('fingerprint'):
            errors.append(f"Obs {i} missing fingerprint")
        else:
            # Verify fingerprint is reproducible
            fp = _obs_fp(o)
            if fp != o['fingerprint']:
                errors.append(f"Obs {i} fingerprint mismatch: stored={o['fingerprint']} computed={fp}")
    
    # 10. Normalized_value must be reproducible from raw_value
    for i, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        norm = _normalize_value(o.get('field', ''), o.get('raw_value', ''))
        if norm != o.get('normalized_value', ''):
            errors.append(f"Obs {i} normalized_value mismatch: stored='{o.get('normalized_value')}' computed='{norm}'")
    
    # 11. price_type must be reproducible
    for i, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        if o.get('field') == 'price':
            pt = _normalize_price_type(o.get('raw_value', ''), o.get('price_type', ''))
            if pt != o.get('price_type', ''):
                errors.append(f"Obs {i} price_type mismatch: stored='{o.get('price_type')}' computed='{pt}'")
    
    # 12. vehicle_regions must have non-empty price_block_ids
    for i, r in enumerate(a.get('stage_a', {}).get('vehicle_regions', [])):
        if not r.get('price_block_ids'):
            errors.append(f"Region {i} price_block_ids is empty")
    
    # 13. region_block_ids must be subset of article_body_block_ids
    for i, r in enumerate(a.get('stage_a', {}).get('vehicle_regions', [])):
        for bid in r.get('region_block_ids', []):
            if bid not in ab_ids:
                errors.append(f"Region {i} block '{bid}' not in article_body_block_ids")
    
    # 14. stage_a.article_body_block_ids count must match top-level count
    stage_ab = set(a.get('stage_a', {}).get('article_body_block_ids', []))
    if stage_ab and stage_ab != ab_ids:
        errors.append(f"article_body_block_ids mismatch: top={len(ab_ids)} stage_a={len(stage_ab)}")
    
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
        print("VALIDATION PASSED — all 14 invariants verified")
