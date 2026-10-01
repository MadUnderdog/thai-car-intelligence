# P119-R1 — Targeted assembly safety repair (§96/§95)

Date: 2026-09-29 · Same thread · PR #3 (OPEN, UNMERGED) · branch `fix/p1-provenance-gate`
Base: `b3c9178ccacb07f9a0367ad153450869120a92d4` (reviewed P119 head)
Scope: exactly the two blocking defects assigned. No Phase 6. No refactor.

## Defect 1 — trust tier upgrade guard
- **Before**: `models.py::trust_for_obs()` returned an obs-declared `trust_tier` verbatim → an
  `IDENTITY_ENUMERATOR`/`MARKET_REFERENCE`/unknown-role observation could declare
  `official_verified` and assemble above its role ceiling (violates §95 non-increasing trust,
  hard contract 3).
- **Red-before** (`20260929-p119r1-redbefore.log`, on untouched b3c9178): T1/T3/T4 fail —
  enumerator declaring official_verified assembled as official_verified; unknown role
  inherited the declared tier.
- **Fix**: role/class sets a CEILING (unknown/malformed → `inferred`, fail closed); declared
  tier honoured only ≤ ceiling (higher clamped); missing/malformed declared tier → role ceiling.
- **Real-data impact**: 0 of 2,142 observations change (all real roles are `MARKET_TRUTH`,
  0 pre-existing violations) — latent defect, guard proven by mutation tests T1–T5 + real-set
  invariant T6 (every one of 1,323 assembled fields ≤ its obs role ceiling).

## Defect 2 — sibling-brand join isolation
- **Before**: `resolve_join_key()` used the alias-catalog model-display lookup for fallback AND
  enrichment without proving the entry belongs to the packet manufacturer.
- **Real evidence on HEAD b3c9178**: PKT-0250/0251 (`lexus|es`) matched MG's catalog entry
  (`nameEn: ES`, `brandSlug: mg`) and the pushed `assembled_records.jsonl` carried
  `"manufacturer_slug": "lexus", "model_slug": "mg-es"` — cross-brand join in the artifact.
- **Red-before**: T7/T8/T9 (synthetic same-display two-OEM catalog) + T10 (real Lexus→mg-es) fail.
- **Fix**: `_brand_agrees()` (brandSlug + brandEn/brandTh + catalog brands names/aliases);
  cross-brand catalog fallback → explicit `cross_brand_collision` rejection; universe enrichment
  applied only on brand agreement, otherwise recorded as
  `alias_evidence.catalog_enrichment = rejected_cross_brand:<brand>`.
- **Real-data impact**: exactly 2 records corrected (mg-es → es); `conflicts.jsonl`,
  `join_errors.jsonl`, `validation_failures.jsonl` byte-identical; other 415 records unchanged.
  T11 proves the invariant on all 417 records (manufacturer_slug == packet brand); T12 proves
  legitimate same-brand enrichment still works.

## Tests (12 new: `tests/test_p119_r1_safety.py`)
Red-before **7 failed | 5 passed** → after fix, focused **30 passed**
(12 new + 18 existing P119 tests — conflict semantics untouched, all green).

## Gates
- focused **30** · determinism **byte-identical** · combined **126 passed** (full-pytest order)
- full vitest **563 passed | 2 skipped (47)** · tsc **0** · prisma **OK** · credscan **0**
- full pytest **1019 passed** (bounded rerun `20260929-p119r1-full-pytest-rerun.log`);
  the chain's own full run showed 2 transient Playwright `set_content` 30s timeouts in
  `test_extraction_fixtures` (unrelated to assembly; standalone 2 passed; same code passed 1019
  in chain run 1). Known P49 ImportError excluded and reported separately.

## Disclosures
1. **Chain step-9 defect (fixed)**: run-1's clean-tree step restored ALL modified tracked files,
   reverting the repair source AFTER its gates passed. Source re-applied identically (focused 30
   re-verified), step-9 now restores only other waves' leaked audit artifacts + fails on any
   unexpected modification; FULL chain rerun → the numbers above (run 1 superseded).
2. 2-record output diff vs committed P119 = the repair itself (disclosed above).
3. No schema/provider/model/config/verifier/AcceptanceRunner change; no DB write; no promotion;
   `assemble.py` (conflict semantics) untouched; deterministic/idempotent output preserved.

## STOP
Repair green and pushed — awaiting review/direction for the next Blueprint phase.
