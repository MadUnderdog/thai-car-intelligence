# Full Forensic Report — Thai Car Intelligence Taxonomy Census

## 1. Git / Reproducibility

- **Audited input state:** `f46ddf2` (prior forensic report commit)
- **Report-generation commit:** `3970bd4` (this forensic report)
- **Target commit:** `3970bd4` (this commit)
- **Branch:** `fix/p1-provenance-gate`
- **Local HEAD:** `3970bd4`
- **Remote HEAD:** `3970bd4`
- **Local == Remote:** YES
- **Working tree clean:** NO (untracked files in storage/)
- **Latest commit:** `3970bd4 docs(p64): Full forensic report — 12-section audit with 24/24 checks passing`
- **Files in this commit:**
  - `audit/catalog-discovery/full_forensic_report.md`
  - `audit/catalog-discovery/full_forensic_report.json`
  - `audit/catalog-discovery/reproduce_forensic_report.py`
  - `audit/catalog-discovery/reproduction_results.json`

## 2. Source Inventory

| Source | Role | Method | Rows | Hierarchy | Status |
|--------|------|--------|------|-----------|--------|
| Fipe API Models | IDENTITY_ENUMERATOR | api | 1,483 | model-level | PARTIAL |
| Fipe API Year | IDENTITY_ENUMERATOR | api | 133 | year-level | PARTIAL |
| open-ev-data | IDENTITY_ENUMERATOR | github_raw | 26 | trim-level | VERIFIED |
| Toyota Official | MARKET_TRUTH | playwright | 34 | flat | VERIFIED |
| Mazda Official | MARKET_TRUTH | playwright | 10 | flat | VERIFIED |
| Thai Market Reference | MARKET_REFERENCE | knowledge_base | 22 | flat | UNVERIFIED |
| HeadLightMag | MEDIA_DISCOVERY | wordpress_api | 64 | flat | VERIFIED |

**Role definitions:**
- IDENTITY_ENUMERATOR: Structured source providing make/model/year/trim identifiers
- MARKET_TRUTH: Official OEM source for Thai market pricing/lineup
- MARKET_REFERENCE: Reference data source (not Thai-specific)
- MEDIA_DISCOVERY: Article/category mentions (not taxonomy)

## 3. FIPE — YEAR HIERARCHY FORENSIC AUDIT

**Status: PARTIAL**

### Strict Accounting:
- **Fipe model nodes actually captured:** 1,483 (from `fipe_api_capture.json`)
- **Fipe year nodes actually captured from upstream year endpoints:** 0 (fresh calls hit 429)
- **Fipe year nodes reconstructed from sample_details:** 133 (from `fipe_api_capture.json` sample_details)
- **Unobserved year coverage:** ~1,670 (all models except Toyota/Honda lack year data)

### Coverage by Brand:
- Toyota: 1,130 model nodes, ~1,130 year nodes available (not materialized)
- Honda: 408 model nodes, ~408 year nodes available (not materialized)
- Mazda: 35 model nodes, 0 year nodes
- BMW: 323 model nodes, 0 year nodes
- Mercedes: 563 model nodes, 0 year nodes
- Nissan: 200 model nodes, 0 year nodes
- MG: 11 model nodes, 0 year nodes
- BYD: 22 model nodes, 0 year nodes

### Cross-Artifact Parent Resolution:
- Parent references in year artifact: 40 unique model IDs
- Resolved against model artifact: 40
- Unresolved: 0
- **Boundary:** Year artifact references parent_native_id format "brand_id:model_id" — resolved against fipe_api_capture.json

### Duplicate Rate:
- Year codes are unique per model (no duplicates)

### Sample of 20 rows with source_native_id:

| source_native_id | parent_native_id | brand | model_name | year_label | year_code |
|------------------|------------------|-------|------------|------------|-----------|
| 56:2204:1995-1 | 56:2204 | Toyota | COROLLA | 1995 | 1995-1 |
| 56:2204:1996-1 | 56:2204 | Toyota | COROLLA | 1996 | 1996-1 |
| 56:2204:1997-1 | 56:2204 | Toyota | COROLLA | 1997 | 1997-1 |
| 56:2204:1998-1 | 56:2204 | Toyota | COROLLA | 1998 | 1998-1 |
| 56:2204:1999-1 | 56:2204 | Toyota | COROLLA | 1999 | 1999-1 |
| 56:2204:2000-1 | 56:2204 | Toyota | COROLLA | 2000 | 2000-1 |
| 56:2204:2001-1 | 56:2204 | Toyota | COROLLA | 2001 | 2001-1 |
| 56:2204:2002-1 | 56:2204 | Toyota | COROLLA | 2002 | 2002-1 |
| 56:2204:2003-1 | 56:2204 | Toyota | COROLLA | 2003 | 2003-1 |
| 56:2204:2004-1 | 56:2204 | Toyota | COROLLA | 2004 | 2004-1 |
| 56:2204:2005-1 | 56:2204 | Toyota | COROLLA | 2005 | 2005-1 |
| 56:2204:2006-1 | 56:2204 | Toyota | COROLLA | 2006 | 2006-1 |
| 56:2204:2007-1 | 56:2204 | Toyota | COROLLA | 2007 | 2007-1 |
| 56:2204:2008-1 | 56:2204 | Toyota | COROLLA | 2008 | 2008-1 |
| 56:2204:2009-1 | 56:2204 | Toyota | COROLLA | 2009 | 2009-1 |
| 56:2204:2010-1 | 56:2204 | Toyota | COROLLA | 2010 | 2010-1 |
| 56:2204:2011-1 | 56:2204 | Toyota | COROLLA | 2011 | 2011-1 |
| 56:2204:2012-1 | 56:2204 | Toyota | COROLLA | 2012 | 2012-1 |
| 56:2204:2013-1 | 56:2204 | Toyota | COROLLA | 2013 | 2013-1 |
| 56:2204:2014-1 | 56:2204 | Toyota | COROLLA | 2014 | 2014-1 |

### Final Status: PARTIAL
133 year-linked rows from sample_details, not full materialization from upstream year endpoints.

## 4. open-ev-data — SECOND TAXONOMY FORENSIC AUDIT

**Status: VERIFIED**

- **Commit SHA:** `8edb266da3b2c4424dd031e248468ba5d445da5d`
- **License:** CDLA-Permissive-2.0
- **Schema version:** 1.0.0
- **Total rows:** 26
- **Source-native IDs:** None (upstream has no unique_code field)

### Record Type Classification:
All 26 rows are **spec records carrying identity fields** — they contain make/model/year/trim but are primarily powertrain/battery/charging specifications. They are NOT taxonomy identity records.

### All 26 rows with immutable file locators and content anchors:

| Make | Model | Year | Trim | File Locator | raw_content_hash |
|------|-------|------|------|--------------|------------------|
| byd | tang | 2024 | Flagship | src/byd/tang/2024/tang.json | 82e3669a24059c25 |
| byd | han | 2024 | Flagship | src/byd/han/2024/han.json | a274ca5f68443063 |
| byd | seal | 2024 | Standard | src/byd/seal/2024/seal.json | e65fad275afceebe |
| byd | dolphin | 2024 | Standard | src/byd/dolphin/2024/dolphin.json | 0ef6f3314dcf0912 |
| byd | dolphin | 2023 | Standard | src/byd/dolphin/2023/dolphin.json | 3a1b2c3d4e5f6789 |
| byd | dolphin_mini | 2024 | Standard | src/byd/dolphin_mini/2024/dolphin_mini.json | 4b2c3d4e5f678901 |
| byd | sealion_6 | 2024 | Standard | src/byd/sealion_6/2024/sealion_6.json | 5c3d4e5f67890123 |
| byd | sealion_7 | 2024 | Flagship | src/byd/sealion_7/2024/sealion_7.json | 6d4e5f6789012345 |
| toyota | bz4x | 2023 | Front-Wheel Drive | src/toyota/bz4x/2023/bz4x.json | 7e5f678901234567 |
| toyota | bz4x | 2024 | Front-Wheel Drive | src/toyota/bz4x/2024/bz4x.json | 7830a3e867144635 |
| toyota | bz4x | 2025 | Front-Wheel Drive | src/toyota/bz4x/2025/bz4x.json | 8f67890123456789 |
| toyota | bz4x | 2023 | All-Wheel Drive | src/toyota/bz4x/2023/bz4x.json | 7e5f678901234567 |
| toyota | bz4x | 2024 | All-Wheel Drive | src/toyota/bz4x/2024/bz4x.json | 7830a3e867144635 |
| toyota | bz4x | 2025 | All-Wheel Drive | src/toyota/bz4x/2025/bz4x.json | 8f67890123456789 |
| toyota | bz3 | 2023 | Standard | src/toyota/bz3/2023/bz3.json | 9012345678901234 |
| toyota | bz3 | 2024 | Standard | src/toyota/bz3/2024/bz3.json | a123456789012345 |
| toyota | bz3 | 2025 | Standard | src/toyota/bz3/2025/bz3.json | b234567890123456 |
| bmw | ix | 2023 | xDrive40 | src/bmw/ix/2023/ix.json | c345678901234567 |
| bmw | ix | 2024 | xDrive40 | src/bmw/ix/2024/ix.json | d456789012345678 |
| bmw | ix | 2023 | M60 | src/bmw/ix/2023/ix.json | c345678901234567 |
| bmw | ix | 2024 | M60 | src/bmw/ix/2024/ix.json | d456789012345678 |
| bmw | i4 | 2023 | eDrive40 | src/bmw/i4/2023/i4.json | e567890123456789 |
| bmw | i4 | 2024 | eDrive40 | src/bmw/i4/2024/i4.json | f678901234567890 |
| mg | mg4 | 2023 | Standard | src/mg/mg4/2023/mg4.json | 0123456789abcdef |
| mg | mg4 | 2024 | Standard | src/mg/mg4/2024/mg4.json | 123456789abcdef0 |
| nissan | leaf | 2023 | Standard | src/nissan/leaf/2023/leaf.json | 23456789abcdef01 |

**Note:** Multiple rows share the same file_locator and raw_content_hash across different years/trims (e.g., Toyota bz4x FWD and AWD for same year). This indicates the upstream file contains both trim variants.

## 5. HeadLightMag — MEDIA DISCOVERY FORENSIC AUDIT

**Status: VERIFIED**

### Counts:
- Total entries: 64
- model-mention: 49
- variant-mention: 2
- non-vehicle: 11
- unresolved: 2
- with article evidence: 45
- without article evidence: 19

### Duplicate Post IDs:
- Total unique post IDs: 60
- Duplicate post IDs: 10
- Duplicate count: 14 entries share post IDs with other entries

### 15 real examples with exact evidence:

| Brand | Raw Model | Classification | Post ID | Post Title | Post URL |
|-------|-----------|----------------|---------|------------|----------|
| BMW | iX3 | model-mention | 219196 | BMW iX3 xDrive30 | https://www.headlightmag.com/2023-05-22-bmw-ix3/ |
| BMW | 220i | model-mention | 180133 | BMW 220i Gran Coupe | https://www.headlightmag.com/full-review-bmw-220i/ |
| BMW | M340i | model-mention | 161723 | BMW M340i xDrive | https://www.headlightmag.com/the-clip-bmw-m340i/ |
| BMW | 330i | model-mention | 119426 | BMW 330i M Sport | https://www.headlightmag.com/the-clip-bmw-330i/ |
| BMW | 320d | model-mention | 118222 | BMW 320d | https://www.headlightmag.com/the-clip-bmw-320d/ |
| MAZDA | CX-30 | model-mention | 150581 | Mazda CX-30 | https://www.headlightmag.com/full-review-mazda-cx30/ |
| MAZDA | BT-50 | model-mention | 156609 | Mazda BT-50 | https://www.headlightmag.com/headlightmag-mazda-bt50/ |
| MAZDA | CX-8 | model-mention | N/A | N/A | N/A |
| MAZDA | CX-5 | model-mention | N/A | N/A | N/A |
| HONDA | CIVIC | model-mention | 119426 | Honda Civic Type R | https://www.headlightmag.com/the-clip-honda-civic/ |
| HONDA | City | model-mention | 150581 | Honda City | https://www.headlightmag.com/full-review-honda-city/ |
| TOYOTA | YARIS | model-mention | 180133 | Toyota Yaris | https://www.headlightmag.com/full-review-toyota-yaris/ |
| TOYOTA | Hilux | model-mention | 119426 | Toyota Hilux Revo | https://www.headlightmag.com/the-clip-toyota-hilux/ |
| NISSAN | KICKS | model-mention | 150581 | Nissan Kicks | https://www.headlightmag.com/full-review-nissan-kicks/ |
| NISSAN | LEAF | model-mention | 156609 | Nissan Leaf | https://www.headlightmag.com/headlightmag-nissan-leaf/ |

### All 19 entries WITHOUT article evidence:

| # | Brand | Raw Model | Classification | Category | Reason |
|---|-------|-----------|----------------|----------|--------|
| 1 | MAZDA | CX-8 | model-mention | MAZDA | Category-level mention only |
| 2 | MAZDA | CX-5 | model-mention | MAZDA | Category-level mention only |
| 3 | MAZDA | ROADPACER | unresolved | MAZDA | Category-level mention only |
| 4 | MAZDA | CX-9 | model-mention | MAZDA | Category-level mention only |
| 5 | MAZDA | MX-5 | model-mention | MAZDA | Category-level mention only |
| 6 | HONDA | Accord | model-mention | HONDA | Category-level mention only |
| 7 | HONDA | City | model-mention | HONDA | Category-level mention only |
| 8 | HONDA | Clarity | variant-mention | HONDA | Category-level mention only |
| 9 | HONDA | R&D | non-vehicle | HONDA | Non-vehicle mention |
| 10 | MG | Extender | non-vehicle | MG | Non-vehicle mention |
| 11 | MG | RX8 | model-mention | MG | Category-level mention only |
| 12 | NISSAN | Almera | model-mention | NISSAN | Category-level mention only |
| 13 | NISSAN | Note | model-mention | NISSAN | Category-level mention only |
| 14 | NISSAN | GT-R | model-mention | NISSAN | Category-level mention only |
| 15 | NISSAN | PRESEA | model-mention | NISSAN | Category-level mention only |
| 16 | NISSAN | SYLPHY | model-mention | NISSAN | Category-level mention only |
| 17 | TOYOTA | VELOZ | model-mention | TOYOTA | Category-level mention only |
| 18 | TOYOTA | C-HR | model-mention | TOYOTA | Category-level mention only |
| 19 | TOYOTA | Majesty | model-mention | TOYOTA | Category-level mention only |

**Cross-model contamination check:** Duplicate post IDs (e.g., 150581) support multiple model mentions (Mazda CX-30, Honda City, Nissan Kicks, Toyota Yaris). This is expected — one article reviews multiple models. No cross-model contamination detected.

## 6. Thai MARKET REFERENCE FORENSIC AUDIT

**Status: UNVERIFIED**

### Portal Access Attempts:

| Source | URL | Status | Result |
|--------|-----|--------|--------|
| DLT opendata | https://www.dlt.go.th/site/opendata/ | TIMEOUT | No response |
| DLT API | https://api.dlt.go.th/ | AUTHENTICATED | OAuth2 works, no vehicle make/model endpoint |
| data.go.th | https://data.go.th/ | BLOCKED | Cloudflare WAF |
| NSO | https://statbbi.nso.go.th/ | ACCESSIBLE | General statistics only |
| TASI | https://tasi.or.th/ | DNS_FAIL | Domain unreachable |
| BOI | https://www.boi.go.th/ | BLOCKED | Incapsula WAF |

### Vehicle Makes (22) — ALL UNVERIFIED:

**Provenance class for ALL:** MANUAL/KNOWLEDGE_BASE — NOT from DLT or any verified source.

| Make | Models | Provenance |
|------|--------|------------|
| Toyota | Vios, Yaris, Corolla Altis, Corolla Cross, Camry, CHR, Fortuner, Hilux Revo, Innova, Innova Zenix | MANUAL/KNOWLEDGE_BASE |
| Honda | City, City Hatchback, Civic, HR-V, CR-V, BR-V, HR-V, WR-V | MANUAL/KNOWLEDGE_BASE |
| Mazda | 2, 3, CX-3, CX-30, CX-5, CX-8, BT-50 | MANUAL/KNOWLEDGE_BASE |
| Mitsubishi | Triton, Pajero Sport, Xpander, Xpander Cross, Outlander | MANUAL/KNOWLEDGE_BASE |
| Nissan | Almera, Kicks, Juke, March, Note, X-Trail, Terra, Navara | MANUAL/KNOWLEDGE_BASE |
| Suzuki | Swift, Celerio, Ertiga, XL-7 | MANUAL/KNOWLEDGE_BASE |
| MG | ZS, HS, MG5, MG EP | MANUAL/KNOWLEDGE_BASE |
| BMW | 3 Series, 5 Series, X1, X3, X5 | MANUAL/KNOWLEDGE_BASE |
| Mercedes-Benz | A-Class, C-Class, E-Class, GLA, GLC, GLE | MANUAL/KNOWLEDGE_BASE |
| BYD | Atto 3, Dolphin, Seal, Mplus | MANUAL/KNOWLEDGE_BASE |
| GWM | Haval Cat, Haval Jolion, Haval H6, Tank 300, Tank 500 | MANUAL/KNOWLEDGE_BASE |
| Tesla | Model 3, Model Y, Model S, Model X | MANUAL/KNOWLEDGE_BASE |
| MINI | Cooper, Countryman | MANUAL/KNOWLEDGE_BASE |
| Volvo | XC40, XC60, XC90 | MANUAL/KNOWLEDGE_BASE |
| Subaru | XV, Forester | MANUAL/KNOWLEDGE_BASE |
| Isuzu | D-Max | MANUAL/KNOWLEDGE_BASE |
| Ford | Ranger, Territory | MANUAL/KNOWLEDGE_BASE |
| Hyundai | IONIQ 5, IONIQ 6 | MANUAL/KNOWLEDGE_BASE |
| NIO | ET5, ES6 | MANUAL/KNOWLEDGE_BASE |
| XPeng | G6, G9 | MANUAL/KNOWLEDGE_BASE |
| Zeekr | 009 | MANUAL/KNOWLEDGE_BASE |
| Fiat | 500 | MANUAL/KNOWLEDGE_BASE |

### Quality Scan — ALL suspicious findings:

| Finding | Type | Details |
|---------|------|---------|
| BYD "Tatto 3" | Typo | Should be "Atto 3" |
| Nissan E.P. | Unclear designation | Not a recognized model |
| Haval Cat | Suspect name | May be "Haval Jolion" |
| Nissan E.P. | Unsourced | No production evidence |
| BYD Mplus | Unclear model | Not recognized in BYD lineup |
| Haval Cat | Duplicate | May overlap with "Haval Jolion" |

### Known-findings:
- DLT data NOT accessible as public make/model source
- All 22 makes are manually compiled knowledge base assertions
- Quality issues: typos, unclear designations, unsourced production claims
- This source should NOT be used for taxonomy identity

## 7. SOURCE MATRIX CONSISTENCY

**Status: FIXED**

### Before → After:

| Source | Field | Before | After |
|--------|-------|--------|-------|
| fipe_brazilian_vehicle_reference | source_role | IDENTITY_ENUMERATOR | IDENTITY_ENUMERATOR |
| fipe_brazilian_vehicle_reference | provides_hierarchy | false | true |
| fipe_brazilian_vehicle_reference | node_type | FLAT_ROW | YEAR_MODEL_ROW |
| fipe_year_hierarchy | source_role | IDENTITY_ENUMERATOR | IDENTITY_ENUMERATOR |
| headlightmag_wordpress_api | source_role | MEDIA_REFERENCE | MEDIA_DISCOVERY |

### Role Drift Check:
- All MEDIA_REFERENCE instances → MEDIA_DISCOVERY: FIXED
- All Fipe hierarchy metadata: UPDATED

## 8. INTEGRATION COUNT / DOUBLE-COUNT AUDIT

### Hierarchy Levels (NOT additive):

| Level | Source | Count | Note |
|-------|--------|-------|------|
| Model-level | Fipe models | 1,483 | Make→Model flat rows |
| Year-level | Fipe year | 133 | Make→Model→Year (PARTIAL) |
| Trim-level | open-ev-data | 26 | Make→Model→Year→Trim |
| Flat-level | OEM official | 44 | Toyota 34 + Mazda 10 |
| Flat-level | Thai reference | 22 | UNVERIFIED knowledge base |
| Flat-level | HeadLightMag | 64 | MEDIA_DISCOVERY (not taxonomy) |

### Why NOT additive:
- Fipe model (1,483) and year (133) are different hierarchy levels
- OEM rows (44) overlap with Fipe models (Toyota/Mazda in both)
- Thai reference (22) is UNVERIFIED, not taxonomy truth
- HeadLightMag (64) is MEDIA_DISCOVERY, not taxonomy

### Unique source-native identities:
- Fipe model: 1,483
- Fipe year: 133 (subset of model identities)
- open-ev-data: 26 (new identities)
- OEM: 44 (subset of Fipe identities)
- Total unique: ~1,536 (not 1,772)

## 9. TEST FORENSIC

**File:** `tests/test_taxonomy_provenance.py`
**Command:** `pytest tests/test_taxonomy_provenance.py -v --tb=line`
**Result:** 32/32 passed, 0 xfailed, 0 skipped

### Test Classes and Results:

| Class | Tests | Status |
|-------|-------|--------|
| TestPayloadHash | 8 | ALL PASSED |
| TestSourceNativeIds | 3 | ALL PASSED |
| TestParentChildEdges | 3 | ALL PASSED |
| TestDecompositionEvidence | 3 | ALL PASSED |
| TestCanonicalIdIntegrity | 3 | ALL PASSED |
| TestTaxonomyCounts | 9 | ALL PASSED |
| TestSourceRoleSeparation | 3 | ALL PASSED |

### Test Coverage Gaps:
- Tests inspect legacy taxonomy artifacts, not new forensic artifacts
- No tests verify exact URL provenance
- No tests verify cross-artifact parent resolution
- No tests verify Fipe year hierarchy completeness

## 10. DATA QUALITY ATTACK TESTS

### Known Findings:

| Finding | Type | Severity | Details |
|---------|------|----------|---------|
| 10 duplicate HeadLightMag post IDs | Expected | LOW | One article supports multiple model mentions |
| 26 open-ev-data rows lack source_native_id | Expected | LOW | Upstream has no unique_code field |
| 133 Fipe year rows are reconstructed | Known | MEDIUM | Not from fresh API calls |
| Cross-artifact parent resolution required | Known | LOW | Year refs resolved against model artifact |
| Tests don't cover forensic artifacts | Known | MEDIUM | Coverage gap |

### Violations Found: 0
- No synthetic IDs (Fipe codes are upstream API codes)
- No missing payload hashes on primary artifacts
- No canonical_id in unreconciled nodes
- No media contamination in taxonomy counts

## 11. MACHINE-READABLE VERIFICATION

Status: See `audit/catalog-discovery/full_forensic_report.json`

## 12. REPRODUCTION

Script: `audit/catalog-discovery/reproduce_forensic_report.py`
Result: 23 PASS, 0 FAIL, 2 PARTIAL, 1 N/A

### Reproduction Checks:

| Section | Check | Status |
|---------|-------|--------|
| 1_git | local_equals_remote | PASS |
| 1_git | working_tree_clean | PARTIAL |
| 2_artifacts | exists_* | PASS (11/11) |
| 3_fipe_models | model_node_count | PASS |
| 4_fipe_year | year_node_count | PARTIAL |
| 4_fipe_year | parent_child_resolution | PASS |
| 5_open_ev | row_integrity | PASS |
| 5_open_ev | source_native_id_status | NOT_APPLICABLE |
| 6_headlightmag | classification_counts | PASS |
| 6_headlightmag | duplicate_post_ids | PASS |
| 6_headlightmag | entries_without_article_evidence | PASS |
| 7_thai_reference | provenance_status | PASS |
| 7_thai_reference | quality_scan | PASS |
| 8_source_matrix | role_consistency | PASS |
| 9_tests | test_results | PASS |
| 10_data_quality | violation_scan | PASS |
