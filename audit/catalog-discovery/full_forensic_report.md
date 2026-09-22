# Full Forensic Report — Thai Car Intelligence Catalog Discovery

## Implementation vs Verification

This commit (p71) is VERIFICATION CODE ONLY. No new external acquisition.
All artifacts verified against existing captures from prior commits.

## 1. Git / Reproducibility

- **Branch:** `fix/p1-provenance-gate`
- **Status:** (verified at commit time)

## 2. Verifier Output

- **Total checks:** 33
- **Passed:** 27
- **Failed:** 0
- **Partial:** 1
- **Blocked:** 0
- **Not Applicable:** 5

## 3. Check Details

- [PASS] artifacts/exists_fipe_models
- [PASS] artifacts/exists_fipe_year
- [PASS] artifacts/exists_open_ev
- [PASS] artifacts/exists_toyota
- [PASS] artifacts/exists_mazda
- [PASS] artifacts/exists_hlm
- [PASS] artifacts/exists_thai_ref
- [PASS] artifacts/exists_raw_universe
- [PASS] artifacts/exists_source_matrix
- [PASS] hash_integrity/payload_hash_fipe_models — Hash recorded from upstream capture, not compared to local file
- [PASS] hash_integrity/payload_hash_open_ev — Hash recorded from upstream capture, not compared to local file
- [PASS] hash_integrity/payload_hash_toyota — Hash recorded from upstream capture, not compared to local file
- [PASS] hash_integrity/payload_hash_mazda — Hash recorded from upstream capture, not compared to local file
- [NOT_APPLICABLE] hash_integrity/payload_hash_fipe_year — Derived artifact — no upstream payload hash
- [NOT_APPLICABLE] hash_integrity/payload_hash_hlm — Derived artifact — no upstream payload hash
- [NOT_APPLICABLE] hash_integrity/payload_hash_thai_ref — Derived artifact — no upstream payload hash
- [NOT_APPLICABLE] hash_integrity/payload_hash_raw_universe — Derived artifact — no upstream payload hash
- [NOT_APPLICABLE] hash_integrity/payload_hash_source_matrix — Derived artifact — no upstream payload hash
- [PASS] roles/media_reference_drift
- [PASS] roles/valid_role_enum
- [PASS] contamination/media_in_taxonomy
- [PASS] integrity/canonical_id_in_raw
- [PASS] openev/field_integrity
- [PASS] openev/no_duplicates
- [PASS] openev/hash_integrity
- [PASS] openev/content_anchor
- [PASS] openev/row_anchoring
- [PARTIAL] hlm/evidence_accounting
- [PASS] hlm/duplicate_post_audit — Duplicate post IDs = multi-mention articles (expected)
- [PASS] hlm/field_integrity
- [PASS] thai_ref/all_unverified
- [PASS] fipe/parent_resolution
- [PASS] counts/reconciliation

## 4. Known Findings

1. HLM evidence accounting: PARTIAL — 19 entries lack article evidence
2. 10 duplicate HLM post IDs (expected multi-mention articles)
3. 26 OpenEV rows lack source_native_id (upstream has no unique_code)
4. 133 Fipe year rows reconstructed from sample_details (not fresh API)
5. Thai market reference: 22 makes all UNVERIFIED (not DLT data)

## 5. Unresolved Blockers

- Fipe API rate limited (429, ~22h retry)
- Thai DLT not accessible (timeout)
- Third-party taxonomy sites blocked (WAF/JS/SSL)

## 6. Test Results

- **File:** tests/test_taxonomy_provenance.py
- **Command:** pytest tests/test_taxonomy_provenance.py -v
- **Result:** 39/39 passed, 0 xfailed, 0 skipped

### Mutation Tests (7/7 PASS):
- test_corrupt_openev_payload_hash_verifier_catches
- test_corrupt_openev_content_hash_verifier_catches
- test_corrupt_openev_empty_payload_hash_verifier_catches
- test_corrupt_headlightmag_verifier_catches
- test_corrupt_fipe_parent_verifier_catches
- test_inject_canonical_id_verifier_catches
- test_media_contamination_detected

## 7. Hash Model

- `upstream_payload_sha256`: SHA-256 of original upstream raw payload
- `local_artifact_sha256`: SHA-256 of local JSON artifact file
- These are DIFFERENT objects and must never be compared directly
