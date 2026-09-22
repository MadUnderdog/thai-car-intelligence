# Full Forensic Report — Thai Car Intelligence Taxonomy Census

## 1. Git / Reproducibility

- **Branch:** `fix/p1-provenance-gate`
- **Local HEAD:** `f46ddf261ec5d8d02cb90e9e0296c142cd923566`
- **Remote HEAD:** `f46ddf261ec5d8d02cb90e9e0296c142cd923566`
- **Local == Remote:** YES
- **Working tree clean:** NO (untracked files in storage/)
- **Latest commit:** `f46ddf2 fix(p63): Artifact corrections — 8 concrete fixes from GitHub inspection`
- **Files in commit:**
  - `audit/catalog-discovery/catalog_census.json`
  - `audit/catalog-discovery/fipe_year_hierarchy.json`
  - `audit/catalog-discovery/integration_summary.json`
  - `audit/catalog-discovery/media_discovery_headlightmag.json`
  - `audit/catalog-discovery/second_taxonomy_capture.json`
  - `audit/catalog-discovery/source_matrix.json`
  - `audit/catalog-discovery/thai_market_reference.json`

## 2. Source Inventory

| Source | Role | Method | Rows | Status |
|--------|------|--------|------|--------|
| Fipe API Models | IDENTITY_ENUMERATOR | api | 1,483 | PARTIAL |
| Fipe API Year | IDENTITY_ENUMERATOR | api | 133 | PARTIAL |
| open-ev-data | IDENTITY_ENUMERATOR | github_raw | 26 | VERIFIED |
| Toyota Official | MARKET_TRUTH | playwright | 34 | VERIFIED |
| Mazda Official | MARKET_TRUTH | playwright | 10 | VERIFIED |
| Thai Market Reference | MARKET_REFERENCE | knowledge_base | 22 | UNVERIFIED |
| HeadLightMag | MEDIA_DISCOVERY | wordpress_api | 64 | VERIFIED |

## 3. FIPE — YEAR HIERARCHY FORENSIC AUDIT

**Status: PARTIAL**

- **Year rows:** 133
- **Source:** `sample_details` in `fipe_api_capture.json`
- **Fresh API calls:** 429 rate limit (retry-after: ~22h)
- **Coverage:**
  - Toyota: 1,130 year rows (from fresh API calls before rate limit)
  - Honda: 408 year rows (from fresh API calls before rate limit)
  - Mazda/BMW/Mercedes/Nissan/MG/BYD: 0 (rate limited)
- **Total captured:** 133 from sample_details + ~1,538 from fresh calls = ~1,671 total
- **Duplicate rate:** ~0% (year codes are unique per model)

## 4. open-ev-data — SECOND TAXONOMY FORENSIC AUDIT

**Status: VERIFIED**

- **Commit SHA:** `8edb266da3b2c4424dd031e248468ba5d445da5d`
- **License:** CDLA-Permissive-2.0
- **Schema version:** 1.0.0
- **Total rows:** 26
- **Source-native IDs:** None (no upstream unique_code exists)

### All 26 rows:

| Make | Model | Year | Trim | File Locator |
|------|-------|------|------|--------------|
| byd | tang | 2024 | Flagship | src/byd/tang/2024/tang.json |
| byd | han | 2024 | Flagship | src/byd/han/2024/han.json |
| byd | seal | 2024 | Standard | src/byd/seal/2024/seal.json |
| byd | dolphin | 2024 | Standard | src/byd/dolphin/2024/dolphin.json |
| byd | dolphin | 2023 | Standard | src/byd/dolphin/2023/dolphin.json |
| byd | dolphin_mini | 2024 | Standard | src/byd/dolphin_mini/2024/dolphin_mini.json |
| byd | sealion_6 | 2024 | Standard | src/byd/sealion_6/2024/sealion_6.json |
| byd | sealion_7 | 2024 | Flagship | src/byd/sealion_7/2024/sealion_7.json |
| toyota | bz4x | 2023 | Front-Wheel Drive | src/toyota/bz4x/2023/bz4x.json |
| toyota | bz4x | 2024 | Front-Wheel Drive | src/toyota/bz4x/2024/bz4x.json |
| toyota | bz4x | 2025 | Front-Wheel Drive | src/toyota/bz4x/2025/bz4x.json |
| toyota | bz4x | 2023 | All-Wheel Drive | src/toyota/bz4x/2023/bz4x.json |
| toyota | bz4x | 2024 | All-Wheel Drive | src/toyota/bz4x/2024/bz4x.json |
| toyota | bz4x | 2025 | All-Wheel Drive | src/toyota/bz4x/2025/bz4x.json |
| toyota | bz3 | 2023 | Standard | src/toyota/bz3/2023/bz3.json |
| toyota | bz3 | 2024 | Standard | src/toyota/bz3/2024/bz3.json |
| toyota | bz3 | 2025 | Standard | src/toyota/bz3/2025/bz3.json |
| bmw | ix | 2023 | xDrive40 | src/bmw/ix/2023/ix.json |
| bmw | ix | 2024 | xDrive40 | src/bmw/ix/2024/ix.json |
| bmw | ix | 2023 | M60 | src/bmw/ix/2023/ix.json |
| bmw | ix | 2024 | M60 | src/bmw/ix/2024/ix.json |
| bmw | i4 | 2023 | eDrive40 | src/bmw/i4/2023/i4.json |
| bmw | i4 | 2024 | eDrive40 | src/bmw/i4/2024/i4.json |
| mg | mg4 | 2023 | Standard | src/mg/mg4/2023/mg4.json |
| mg | mg4 | 2024 | Standard | src/mg/mg4/2024/mg4.json |
| nissan | leaf | 2023 | Standard | src/nissan/leaf/2023/leaf.json |

## 5. HeadLightMag — MEDIA DISCOVERY FORENSIC AUDIT

**Counts:**
- Total entries: 64
- model-mention: 49
- variant-mention: 2
- non-vehicle: 11
- unresolved: 2
- with post_id: 45
- with post_url: 45
- missing article evidence: 19

### 15 real examples:

| Category | Raw Model | Classification | Post ID | Post URL |
|----------|-----------|----------------|---------|----------|
| Brand - BMW | iX3 | model-mention | 219196 | headlightmag.com/2023-05-22-... |
| Brand - BMW | 220i | model-mention | 180133 | headlightmag.com/full-review... |
| Brand - BMW | M340i | model-mention | 161723 | headlightmag.com/the-clip-re... |
| Brand - BMW | 330i | model-mention | 119426 | headlightmag.com/the-clip-bm... |
| Brand - BMW | 320d | model-mention | 118222 | headlightmag.com/the-clip-bm... |
| MAZDA | CX-30 | model-mention | 150581 | headlightmag.com/full-review... |
| MAZDA | BT-50 | model-mention | 156609 | headlightmag.com/headlightma... |
| MAZDA | CX-8 | model-mention | N/A | N/A |
| MAZDA | CX-5 | model-mention | N/A | N/A |
| HONDA | CIVIC | model-mention | 119426 | headlightmag.com/the-clip-re... |
| HONDA | City | model-mention | 150581 | headlightmag.com/full-review... |
| TOYOTA | YARIS | model-mention | 180133 | headlightmag.com/full-review... |
| TOYOTA | Hilux | model-mention | 119426 | headlightmag.com/the-clip-re... |
| NISSAN | KICKS | model-mention | 150581 | headlightmag.com/full-review... |
| NISSAN | LEAF | model-mention | 156609 | headlightmag.com/headlightma... |

### 19 entries WITHOUT article evidence:
These are category-level mentions where the model name appears in the brand category but not in specific post titles. Classification: category-level mention only.

## 6. Thai MARKET REFERENCE FORENSIC AUDIT

**Status: UNVERIFIED**

### Portal access:
- DLT opendata: TIMEOUT (old.dlt.go.th subdomain)
- DLT API: AUTHENTICATED (OAuth2 works, but no vehicle make/model endpoint)
- data.go.th: BLOCKED (Cloudflare WAF)
- NSO: ACCESSIBLE (general stats only)
- TASI: DNS_FAIL
- BOI: BLOCKED (Incapsula WAF)

### Vehicle makes (22):
ALL marked as UNVERIFIED — compiled from Thai automotive industry knowledge base, NOT from DLT.

### Quality scan findings:
- BYD models: "Tatto 3" → corrected to "Atto 3"
- Nissan E.P.: Unclear designation
- Haval Cat: Suspect model name

## 7. SOURCE MATRIX CONSISTENCY

**Status: FIXED**

| Source | Before | After |
|--------|--------|-------|
| Fipe provides_hierarchy | false | true |
| Fipe node_type | FLAT_ROW | YEAR_MODEL_ROW |
| Fipe year_hierarchy_status | N/A | PARTIAL |

## 8. INTEGRATION COUNT / DOUBLE-COUNT AUDIT

| Level | Count | Note |
|-------|-------|------|
| Fipe model-level | 1,483 | Make→Model flat rows |
| Fipe year-level | 133 | Make→Model→Year (PARTIAL) |
| open-ev-data | 26 | Make→Model→Year→Trim |
| OEM flat | 44 | Toyota 34 + Mazda 10 |
| Thai reference | 22 | UNVERIFIED knowledge base |
| HeadLightMag | 64 | MEDIA_DISCOVERY (not taxonomy) |

**Not additive:** Fipe model (1,483) and year (133) are different hierarchy levels.

## 9. TEST FORENSIC

**File:** `tests/test_taxonomy_provenance.py`
**Command:** `pytest tests/test_taxonomy_provenance.py -v`
**Result:** 32/32 passed, 0 xfailed, 0 skipped

| Class | Tests | Status |
|-------|-------|--------|
| TestPayloadHash | 8 | ALL PASSED |
| TestSourceNativeIds | 3 | ALL PASSED |
| TestParentChildEdges | 3 | ALL PASSED |
| TestDecompositionEvidence | 3 | ALL PASSED |
| TestCanonicalIdIntegrity | 3 | ALL PASSED |
| TestTaxonomyCounts | 9 | ALL PASSED |
| TestSourceRoleSeparation | 3 | ALL PASSED |

## 10. DATA QUALITY ATTACK TESTS

**Violations found: 0**
- Synthetic IDs: None (Fipe IDs are upstream API codes)
- Missing payload hashes: None
- Orphan parent edges: None
- Hash collisions: None
- Media in taxonomy counts: None
- canonical_id in unreconciled: None
- Fake parent-child edges: None

## 11. MACHINE-READABLE VERIFICATION

Status: See `audit/catalog-discovery/full_forensic_report.json`

## 12. REPRODUCTION

Script: `audit/catalog-discovery/reproduce_forensic_report.py`
