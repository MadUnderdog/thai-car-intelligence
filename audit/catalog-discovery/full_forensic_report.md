# Forensic Audit Report

**Generated**: 2026-09-22T14:34:06.876797+00:00
**Project**: Thai Car Intelligence — Catalog Discovery
**Source Commit SHA (verified)**: 1ce622068a041aa68597e7003da2df989db6d32d
**Remote SHA**: 1ce622068a041aa68597e7003da2df989db6d32d
**Local == Remote**: YES
**Working Tree**: clean (pre-commit)

## 1. Source Inventory with Endpoints

| Source | Role | Rows | Status | Endpoint/Method | Observed At |
|--------|------|------|--------|-----------------|-------------|
| Fipe Models | IDENTITY_ENUMERATOR | 1,483 | PARTIAL | parallelum.com.br/fipe/api/v1/carros/marcas/ | Rate-limited |
| Fipe Year | IDENTITY_ENUMERATOR | 133 | PARTIAL | parallelum.com.br/fipe/api/v1/carros/marcas/{id}/modelos/{id}/anos | Reconstructed |
| open-ev-data | IDENTITY_ENUMERATOR | 26 | PARTIAL | raw.githubusercontent.com/open-ev-data/... | 1ce622068a04 |
| Toyota Official | MARKET_TRUTH | 34 | CAPTURED | toyota.co.th/en/pricelist (Playwright) | Prior capture |
| Mazda Official | MARKET_TRUTH | 10 | CAPTURED | mazda.co.th/en/vehicles (Playwright) | Prior capture |
| Thai Reference | MARKET_REFERENCE | 22 | UNVERIFIED | Knowledge base (NOT DLT) | N/A |
| HeadLightMag | MEDIA_DISCOVERY | 64 | PARTIAL | headlightmag.com/wp-json/wp/v2/ | Prior capture |

## 2. Source Accounting (Independently Recomputed)

### OpenEV
- Raw: 26
- Filtered: NOT_APPLICABLE (no pipeline state preserved)
- Accepted: NOT_APPLICABLE
- Rejected: NOT_APPLICABLE
- Unresolved: NOT_APPLICABLE
- Status: PARTIAL — cannot independently reconstruct acquisition pipeline

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
- Filtered: NOT_APPLICABLE (no pipeline state preserved)
- Accepted: NOT_APPLICABLE
- Rejected: NOT_APPLICABLE
- Unresolved: NOT_APPLICABLE
- Status: PARTIAL — cannot independently reconstruct acquisition pipeline

### Fipe Year
- Raw: 133
- Filtered: NOT_APPLICABLE (reconstructed from cached API)
- Accepted: NOT_APPLICABLE
- Rejected: NOT_APPLICABLE
- Unresolved: NOT_APPLICABLE
- Status: PARTIAL — reconstructed from cached API responses

## 3. Verifier Results

Total checks: 36
- PASS: 27
- FAIL: 0
- PARTIAL: 4
- BLOCKED: 0
- NOT_APPLICABLE: 5

### Check Details
- **artifacts/exists_fipe_models**: PASS
- **artifacts/exists_fipe_year**: PASS
- **artifacts/exists_open_ev**: PASS
- **artifacts/exists_toyota**: PASS
- **artifacts/exists_mazda**: PASS
- **artifacts/exists_hlm**: PASS
- **artifacts/exists_thai_ref**: PASS
- **artifacts/exists_raw_universe**: PASS
- **artifacts/exists_source_matrix**: PASS
- **hash_integrity/payload_hash_fipe_models**: PASS
- **hash_integrity/payload_hash_open_ev**: PASS
- **hash_integrity/payload_hash_toyota**: PASS
- **hash_integrity/payload_hash_mazda**: PASS
- **hash_integrity/payload_hash_fipe_year**: NOT_APPLICABLE
- **hash_integrity/payload_hash_hlm**: NOT_APPLICABLE
- **hash_integrity/payload_hash_thai_ref**: NOT_APPLICABLE
- **hash_integrity/payload_hash_raw_universe**: NOT_APPLICABLE
- **hash_integrity/payload_hash_source_matrix**: NOT_APPLICABLE
- **roles/media_reference_drift**: PASS
- **roles/valid_role_enum**: PASS
- **contamination/media_in_taxonomy**: PASS
- **integrity/canonical_id_in_raw**: PASS
- **openev/field_integrity**: PASS
- **openev/no_duplicates**: PASS
- **openev/hash_format**: PASS
- **openev/content_anchor**: PASS
- **openev/row_anchoring**: PASS
- **openev/object_existence**: PARTIAL
- **openev/object_hash_verify**: PASS
- **hlm/evidence_accounting**: PARTIAL
- **hlm/duplicate_post_audit**: PASS
- **hlm/field_integrity**: PASS
- **hlm/semantic_mapping**: PARTIAL
- **thai_ref/all_unverified**: PASS
- **fipe/parent_resolution**: PASS
- **accounting/source_state_equations**: PARTIAL

## 4. Mutation Tests (12/12 PASS)

All 12 mutation tests assert FAIL/PARTIAL on corrupted fixtures:
1. test_corrupt_openev_empty_payload_hash → FAIL
2. test_corrupt_openev_invalid_hash_format → FAIL
3. test_corrupt_openev_content_hash_with_mock_fetch → FAIL
4. test_corrupt_headlightmag → PARTIAL
5. test_corrupt_fipe_parent → FAIL
6. test_inject_canonical_id → FAIL
7. test_media_contamination → FAIL
8. test_corrupt_openev_row_anchoring → FAIL
9. test_hlm_cross_model_contamination → FAIL
10. test_corrupt_openev_raw_url_mismatch → FAIL
11. test_corrupt_hlm_classification → FAIL
12. test_corrupt_hlm_counts → FAIL

## 5. Hash Model

- upstream_payload_sha256: SHA-256 of original upstream raw payload
- local_artifact_sha256: SHA-256 of local JSON artifact file
- These are DIFFERENT objects and must never be compared directly

## 6. Known Findings

- HLM evidence accounting: PARTIAL — 19 entries lack article evidence
- HLM semantic mapping: PARTIAL — some same-brand multi-model articles
- Source accounting: PARTIAL — OpenEV/Fipe lack pipeline state preservation
- OpenEV object existence: PARTIAL — GitHub API verification attempted
- 10 duplicate HLM post IDs (expected multi-mention)
- 26 OpenEV rows lack source_native_id (upstream)
- 133 Fipe year rows reconstructed (not fresh API)
- Thai market reference: 22 makes all UNVERIFIED
- pre-existing import error in tests/test_generation_config_boundary.py (not related to this work)

## 7. Unresolved Blockers

- Fipe API rate limited (429, ~22h retry)
- Thai DLT not accessible (timeout)
- Third-party taxonomy sites blocked (WAF/JS/SSL)
- pre-existing import error in test_generation_config_boundary.py (not related to this work)

## 8. Tests

- pytest tests/test_taxonomy_provenance.py: 44/44 passed
- No xfailed, no skipped
- Note: tests/test_generation_config_boundary.py has pre-existing test failures (not related to this work)

## 9. Reproduction

```bash
cd /home/ubuntu/Projects/thai-car-intelligence
python3 -m pytest tests/test_taxonomy_provenance.py -v
python3 -c "from lib.thai_factory.catalog.verifier import verify_artifacts; r=verify_artifacts('audit/catalog-discovery', verify_upstream=True); print(f'{r["passed"]} PASS, {r["failed"]} FAIL, {r["partial"]} PARTIAL')"
```

## 10. Changed Files

- lib/thai_factory/catalog/verifier.py (VERIFIER V9)
- tests/test_taxonomy_provenance.py (12 mutation tests)
- audit/catalog-discovery/verifier_output.json
- audit/catalog-discovery/full_forensic_report.md
- audit/catalog-discovery/full_forensic_report.json
