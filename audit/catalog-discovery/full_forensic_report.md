# Full Forensic Report — Thai Car Intelligence Catalog Discovery

## Implementation vs Verification

This commit (p72) includes VERIFICATION CODE with upstream hash verification capability.
No new external acquisition in this commit — all artifacts verified against existing captures.

## 1. Git / Reproducibility

- **Branch:** `fix/p1-provenance-gate`
- **Local HEAD:** `29094a12efdd2768799910a27b5a7f61d7e5bc7a`
- **Remote HEAD:** `29094a12efdd2768799910a27b5a7f61d7e5bc7a`
- **Local == Remote:** YES
- **Working tree clean:** NO (untracked files)

## 2. Verifier Output

- **Total checks:** 34
- **Passed:** 28
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
- [PASS] openev/hash_format
- [PASS] openev/content_anchor
- [PASS] openev/row_anchoring
- [PASS] openev/upstream_hash_verify
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
- test_corrupt_openev_empty_payload_hash_verifier_catches → FAIL
- test_corrupt_openev_invalid_hash_format_verifier_catches → FAIL
- test_corrupt_headlightmag_verifier_catches → PARTIAL
- test_corrupt_fipe_parent_verifier_catches → FAIL
- test_inject_canonical_id_verifier_catches → FAIL
- test_media_contamination_detected → FAIL
- test_corrupt_openev_row_anchoring_verifier_catches → FAIL

## 7. Hash Model

- `upstream_payload_sha256`: SHA-256 of original upstream raw payload (verified by fetch)
- `local_artifact_sha256`: SHA-256 of local JSON artifact file
- These are DIFFERENT objects and must never be compared directly
- OpenEV upstream verification: fetch from pinned commit, compute SHA-256, compare

## 8. Source Inventory

| Source | Role | Rows | Status |
|--------|------|------|--------|
| Fipe Models | IDENTITY_ENUMERATOR | 1483 | PARTIAL (rate-limited) |
| Fipe Year | IDENTITY_ENUMERATOR | 133 | PARTIAL (reconstructed) |
| open-ev-data | IDENTITY_ENUMERATOR | 26 | VERIFIED (upstream hash) |
| Toyota Official | MARKET_TRUTH | 34 | VERIFIED |
| Mazda Official | MARKET_TRUTH | 10 | VERIFIED |
| Thai Reference | MARKET_REFERENCE | 22 | UNVERIFIED |
| HeadLightMag | MEDIA_DISCOVERY | 64 | PARTIAL (19 no evidence) |
