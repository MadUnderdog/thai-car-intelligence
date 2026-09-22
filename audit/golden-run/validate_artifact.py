"""Validate golden artifact: 18 invariants including scope isolation."""
import json
import re
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))
from thai_factory.extract.ai_extractor import _normalize_value, _normalize_price_type, _obs_fp

_PRICE_RE = re.compile(r'[\d,]+(?:\.\d+)?\s*(?:บาท|฿|THB|ล้าน|ล้านบาท)|xx,xxx|xxx,xxx|ราคา|price', re.I)
_CONTAMINATED_KEYWORDS = ['share', 'must read', 'related news', 'facebook.com/sharer',
                          'must-read', 'more from']


def validate(artifact_path):
    with open(artifact_path) as f:
        a = json.load(f)
    
    errors = []
    snapshots = a.get('block_snapshots', {})
    
    # 1. article_body_block_ids must be > 0
    ab_ids = set(a.get('article_body_block_ids', []))
    if len(ab_ids) == 0:
        errors.append("article_body_block_ids is empty")
    
    # 2. article_body_block_ids must NOT contain contaminated blocks
    for bid in ab_ids:
        snap = snapshots.get(bid, {})
        content = snap.get('content', '').lower()
        for kw in _CONTAMINATED_KEYWORDS:
            if kw in content:
                errors.append(f"Article body contains contaminated block '{bid[:8]}': '{kw}' in content")
    
    # 3. block_count must be reasonable
    if a.get('block_count', 0) < 3:
        errors.append(f"block_count too low: {a.get('block_count', 0)}")
    
    # 4. Exactly one valid vehicle region (for SINGLE_MODEL)
    regions = a.get('stage_a', {}).get('vehicle_regions', [])
    scope = a.get('stage_a', {}).get('document_scope', {}).get('decision', '')
    if scope == 'SINGLE_MODEL' and len(regions) != 1:
        errors.append(f"SINGLE_MODEL but {len(regions)} regions (expected 1)")
    
    # 5. Every region must have non-empty brand AND model
    for i, r in enumerate(regions):
        if not r.get('brand'):
            errors.append(f"Region {i}: empty brand")
        if not r.get('model'):
            errors.append(f"Region {i}: empty model")
    
    # 6. region_block_ids must be subset of article_body_block_ids
    for i, r in enumerate(regions):
        for bid in r.get('region_block_ids', []):
            if bid not in ab_ids:
                errors.append(f"Region {i} block '{bid}' not in article_body_block_ids")
    
    # 7. price_block_ids must be subset of region_block_ids (NOT global)
    for i, r in enumerate(regions):
        region_blocks = set(r.get('region_block_ids', []))
        for pid in r.get('price_block_ids', []):
            if pid not in region_blocks:
                errors.append(f"Region {i} price_block '{pid}' not in region_block_ids (global leak)")
    
    # 8. price_block_ids must be non-empty
    for i, r in enumerate(regions):
        if not r.get('price_block_ids'):
            errors.append(f"Region {i} price_block_ids is empty")
    
    # 9. price_block_ids must actually contain price content
    for i, r in enumerate(regions):
        for pid in r.get('price_block_ids', []):
            snap = snapshots.get(pid, {})
            content = snap.get('content', '')
            if content and not _PRICE_RE.search(content):
                errors.append(f"price_block '{pid[:8]}' does NOT contain price content")
    
    # 10. Every observation's block_id must be in article_body_block_ids
    for idx, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        bid = o.get('block_id', '')
        if bid and bid not in ab_ids:
            errors.append(f"Obs {idx} block_id '{bid}' not in article_body_block_ids")
    
    # 11. evidence_quote must be exact substring of its block
    for idx, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        bid = o.get('block_id', '')
        q = o.get('evidence_quote', '')
        if bid and q:
            snap = snapshots.get(bid, {})
            content = snap.get('content', '')
            if content and q not in content:
                errors.append(f"Obs {idx} evidence_quote NOT in block {bid[:8]}")
    
    # 12. price_type_evidence_quote must be in its block
    for idx, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        ptbid = o.get('price_type_evidence_block_id', '')
        ptq = o.get('price_type_evidence_quote', '')
        if ptbid and ptq:
            snap = snapshots.get(ptbid, {})
            content = snap.get('content', '')
            if content and ptq not in content:
                errors.append(f"Obs {idx} price_type_quote NOT in block {ptbid[:8]}")
    
    # 13. Every observation must have entity brand+model
    for idx, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        ent = o.get('entity', {})
        if not ent.get('brand'):
            errors.append(f"Obs {idx} missing entity brand")
        if not ent.get('model'):
            errors.append(f"Obs {idx} missing entity model")
    
    # 14. Price obs must reference price_block_ids
    for i, r in enumerate(regions):
        price_ids = set(r.get('price_block_ids', []))
        for idx, o in enumerate(a.get('stage_b', {}).get('observations', [])):
            if o.get('field') == 'price' and o.get('block_id') and price_ids:
                if o['block_id'] not in price_ids:
                    errors.append(f"Price obs block '{o['block_id'][:8]}' NOT in region price_block_ids")
    
    # 15. Fingerprint reproducible
    for idx, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        if o.get('fingerprint'):
            fp = _obs_fp(o)
            if fp != o['fingerprint']:
                errors.append(f"Obs {idx} fingerprint mismatch")
    
    # 16. normalized_value reproducible
    for idx, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        norm = _normalize_value(o.get('field', ''), o.get('raw_value', ''))
        if norm != o.get('normalized_value', ''):
            errors.append(f"Obs {idx} normalized_value mismatch")
    
    # 17. price_type reproducible
    for idx, o in enumerate(a.get('stage_b', {}).get('observations', [])):
        if o.get('field') == 'price':
            pt = _normalize_price_type(o.get('raw_value', ''), o.get('price_type', ''))
            if pt != o.get('price_type', ''):
                errors.append(f"Obs {idx} price_type mismatch")
    
    # 18. article_body_block_ids count consistent
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
        print("VALIDATION PASSED — all 18 invariants verified")
