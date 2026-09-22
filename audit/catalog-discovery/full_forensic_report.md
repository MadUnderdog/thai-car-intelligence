# Forensic Audit Report

**Generated**: 2026-09-22T13:38:39.859762+00:00
**Project**: Thai Car Intelligence — Catalog Discovery
**Source Commit SHA (verified)**: e5b91e7de8a7444729971b501de2e4e5bb4c2781
**Remote SHA**: e5b91e7de8a7444729971b501de2e4e5bb4c2781
**Local == Remote**: YES
**Working Tree**: clean (pre-commit)

## 1. Source Inventory

| Source | Role | Rows | Status |
|--------|------|------|--------|
| Fipe Models | IDENTITY_ENUMERATOR | 1,483 | PARTIAL (rate-limited) |
| Fipe Year | IDENTITY_ENUMERATOR | 133 | PARTIAL (reconstructed) |
| open-ev-data | IDENTITY_ENUMERATOR | 26 | VERIFIED (upstream hash) |
| Toyota Official | MARKET_TRUTH | 34 | VERIFIED |
| Mazda Official | MARKET_TRUTH | 10 | VERIFIED |
| Thai Reference | MARKET_REFERENCE | 22 | ALL UNVERIFIED |
| HeadLightMag | MEDIA_DISCOVERY | 64 | PARTIAL (19 without article) |

## 2. Source Accounting (Independently Recomputed)

### OpenEV
- Raw: 26
- Filtered: 26
- Accepted: 26
- Rejected: 0
- Unresolved: 0
- Equation: 26 = 26 + 0 ✓

### HeadLightMag
- Raw: 64
- Model mentions: 49
- Variant mentions: 2
- Non-vehicle: 11
- Unresolved: 2
- Sum: 64
- Equation: 64 = 49 + 2 + 11 + 2 ✓

### Fipe Models
- Raw: 1,483
- Filtered: 1,483
- Accepted: 1,483
- Rejected: 0
- Unresolved: 0
- Equation: 1,483 = 1,483 + 0 ✓

### Fipe Year
- Raw: 133
- Filtered: 133
- Accepted: 133
- Rejected: 0
- Unresolved: 0
- Equation: 133 = 133 + 0 ✓

## 3. Verifier Results

Total checks: 34
- PASS: 28
- FAIL: 0
- PARTIAL: 1
- BLOCKED: 0
- NOT_APPLICABLE: 5

### PARTIAL Checks

- **hlm/evidence_accounting**: PARTIAL
  - total: 64
  - model_mentions: 49
  - variant_mentions: 2
  - non_vehicle: 11
  - unresolved: 2
  - with_article: 45
  - without_article: 19
  - model_with_article: 34
  - model_without_article: 15
  - evidence_status: INSUFFICIENT_EVIDENCE
  - classifications: {'model-mention': 49, 'non-vehicle': 11, 'unresolved': 2, 'variant-mention': 2}

## 4. Mutation Tests

All 9 mutation tests assert FAIL/PARTIAL on corrupted fixtures:
1. test_corrupt_openev_empty_payload_hash → FAIL
2. test_corrupt_openev_invalid_hash_format → FAIL
3. test_corrupt_openev_content_hash_with_mock_fetch → FAIL
4. test_corrupt_headlightmag_verifier_catches → PARTIAL
5. test_corrupt_fipe_parent_verifier_catches → FAIL
6. test_inject_canonical_id_verifier_catches → FAIL
7. test_media_contamination_detected → FAIL
8. test_corrupt_openev_row_anchoring_verifier_catches → FAIL
9. test_hlm_cross_model_contamination_detected → FAIL

## 5. Known Findings

- HLM evidence accounting: PARTIAL — 19 entries lack article evidence
- 10 duplicate HLM post IDs (expected multi-mention)
- 26 OpenEV rows lack source_native_id (upstream)
- 133 Fipe year rows reconstructed (not fresh API)
- Thai market reference: 22 makes all UNVERIFIED

## 6. Unresolved Blockers

- Fipe API rate limited (429, ~22h retry)
- Thai DLT not accessible (timeout)
- Third-party taxonomy sites blocked (WAF/JS/SSL)

## 7. Tests

- pytest tests/test_taxonomy_provenance.py: 41/41 passed
- No xfailed, no skipped

## 8. Reproduction

```bash
cd /home/ubuntu/Projects/thai-car-intelligence
python3 -m pytest tests/test_taxonomy_provenance.py -v
python3 -c "from lib.thai_factory.catalog.verifier import verify_artifacts; r=verify_artifacts('audit/catalog-discovery', verify_upstream=True); print(f'{r["passed"]} PASS, {r["failed"]} FAIL, {r["partial"]} PARTIAL')"
```
