# Productization Status Report — P12.6

**Date:** 2026-09-19
**Branch:** fix/p1-provenance-gate
**PR:** #3 (OPEN, UNMERGED)
**HEAD:** pending commit

## 1. Catalog Counts (verified from DB)

| Item | Count |
|------|-------|
| Manufacturers | 16 |
| Active models (CarModel) | 61 |
| Active variants | 67 |
| Verified prices | 13 |
| Canonical specs (Dims+Perf+Batt+Charg) | 44 (11+19+11+3) |
| Research VariantSpec observations | 165 |
| Production evidence embeddings | 99 |
| SourceDocument | 605 |
| BrochureVerification | 13 |

## 2. Evidence Gate Policy (P12.6 hardened)

Five defense layers (all deterministic, no LLM):

1. **Source-type guard**: RESEARCH/UNVERIFIED/COMMUNITY/USER_SUBMISSION evidence rejected at gate level. Unknown types → fail-closed (rejected). Trusted: OFFICIAL_MANUFACTURER, OFFICIAL_BROCHURE, OFFICIAL_PRICE_LIST, AUTHORIZED_DEALER, VERIFIED_AUTOMOTIVE_REFERENCE.
2. **Canonical model identity**: Exact brand+model pairing via 40+ canonical model entries with word-boundary matching. Longest-match-first prevents "MG EP" from matching "MG EP Plus" evidence. Cross-exclusion guards (e.g., Model Y excludes Model 3, IM5 excludes IM6).
3. **Brand consistency**: Evidence must reference the query's manufacturer brand. Prevents "Toyota City" for "Honda City" queries.
4. **Entity specificity**: Query-specific non-brand terms must match evidence content.
5. **Distance thresholds**: STRICT (0.30) for high-confidence, MAX (0.45) for entity-corroborated, absolute bound 0.60.

States:
- **ACCEPTED**: distance ≤ 0.30 AND entity-corroborated → full confidence
- **QUALIFIED**: distance > 0.30 BUT entity-corroborated (0.30–0.60) → accepted but flagged
- **REJECTED**: distance > 0.45 without corroboration, or > 0.60 even with corroboration, or source-type untrusted, or canonical identity mismatch

## 3. Adversarial Test Suite (P12.6)

**52 tests, all passing.** Zero tests document known-unsafe behavior.

Coverage:
- Wrong brand/same model (Honda City vs Toyota City)
- Same brand/wrong model (MG IM5 vs IM6, Tesla Model Y vs Model 3)
- Short token collision (MG EP vs EP Plus, canonical identity)
- Exact variant and trim (City Hatchback vs City sedan)
- Thai aliases (ฮอนด้า ซิตี้, เอ็มจี โฟร์, mixed Thai+English)
- Punctuation/spacing variants (MG IM-5)
- Body-type mismatch (SUV vs sedan)
- Source type defense (RESEARCH rejected, VERIFIED official accepted, VERIFIED secondary accepted, unknown fail-closed)
- High-similarity wrong entity
- Brand-only queries
- Broad compare intent
- BYD Atto 2 vs Atto 3
- Toyota Yaris vs Yaris Cross
- Honda HR-V vs CR-V
- Missing evidence, empty results
- Distance boundary tests
- Mixed evidence (accepted + rejected in same result)

## 4. AI Ask Response Contract

Every non-validation response includes:
- `status` (ok/insufficient_evidence/unavailable)
- `mode` (structured-catalog/ai-enhanced/error)
- `trust` (ProvenanceMeta with confidence, retrievalMode, verifiedEvidenceCount, qualifiedEvidenceCount, hasResearchObservations)
- `vectorAvailable` (boolean)
- `timing` (parseMs, catalogMs, vectorMs, mergeGateMs, llmMs, totalMs) — only on successful AI path

Trust states: VERIFIED / QUALIFIED / INSUFFICIENT / CLARIFICATION_NEEDED / RESEARCH_UNVERIFIED

## 5. Search Normalizer

`lib/search/thai-normalize.ts` — resolves Thai model/brand aliases to English terms:
- 20+ Thai model mappings
- 14 Thai brand mappings
- Parser entity extraction for English queries
- Original query always searched (augmented, not replaced)

## 6. Public Vehicle Detail

- Hero: verified price badge (✔️ยืนยันแล้ว / ⛔ยังไม่ยืนยัน), last-verified date
- Per-section evidence dots: ประสิทธิภาพ / แบตเตอรี่ / ขนาด / การรับประกัน
- Thai empty state: "ยังไม่มีข้อมูลยืนยัน"
- Research-only block: "ข้อมูลจากงานวิจัย (ยังไม่ยืนยัน)" with warning
- Compare CTA: "⚖️ เปรียบเทียบรุ่นนี้"

## 7. Comparison

`/api/compare` gates prices on VERIFIED SourceDocument + BrochureVerification.

## 8. Community

| Route | Method | Rate Limit | Description |
|-------|--------|------------|-------------|
| /api/community/comments | GET | — | List visible comments with replies |
| /api/community/comments | POST | 5/min | Create comment or reply |
| /api/community/comments/[id]/vote | POST | 20/min | Vote (up/down, idempotent) |
| /api/community/comments/[id]/report | POST | 10/min | Report with reason, auto-hide at 3 |

Anonymous identity via SHA-256 salted IP hash + httpOnly cookie.

## 9. Moderation

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| /api/admin/community/moderation | GET | bearer | List flagged/hidden with report brief |
| /api/admin/community/moderation | PATCH | bearer | HIDE/DELETE/RESTORE |
| /api/admin/community/research-lead | POST | bearer | Handoff → ResearchCandidate |

## 10. Showcase

Demo page with visible "ข้อมูลจำลอง / Demo Data" warning banner. UI primitives only, no real catalog facts presented as verified.

## 11. Test Results (P12.6)

| Check | Result |
|-------|--------|
| prisma validate | ✅ valid |
| tsc --noEmit | ✅ 0 errors |
| vitest run | ✅ 36 files, 301 passed, 2 skipped |
| adversarial suite | ✅ 52/52 PASS |
| brand consistency | ✅ 9/9 PASS |
| lint | 101 errors, 39 warnings (pre-existing legacy) |
| npm run build | ✅ clean |

## 12. DB Invariants

| Item | Expected | Actual | Status |
|------|----------|--------|--------|
| Verified prices | 13 | 13 | ✅ |
| Canonical specs | 44 | 44 | ✅ (11 Dims + 19 Perf + 11 Batt + 3 Charg) |
| VariantSpec | 165 | 165 | ✅ |
| Embeddings | 99 | 99 | ✅ |
| .env secrets | none exposed | clean | ✅ |
| Destructive migration | none | clean | ✅ |
| Broad reindex/harvest | none | clean | ✅ |
| Image generation | none | clean | ✅ |
| union-alpha | unused | clean | ✅ |

## 13. Lint Breakdown

- Pre-existing legacy errors: ~101 (unused vars, explicit-any in test files)
- New errors from P12.6: 0
- Warnings: 39 (unused imports in test files)
- Pre-existing test warnings: `gateVectorEvidence`, `VECTOR_STRICT_DISTANCE`, `VECTOR_MAX_DISTANCE` unused imports in adversarial test (cosmetic, not functional)

## 14. Files Changed (P12.6)

Modified:
- `lib/ai/retrieval/evidence-gate-policy.ts` — canonical model identity table (40+ models), source-type defense-in-depth, word-boundary matching, longest-match-first specificity
- `tests/unit/evidence-gate-adversarial.test.ts` — 52 adversarial tests (expanded from ~20, zero GAP/unsafe assertions)
- `docs/research/productization-status.md` — this report (rewritten to current truth)

## 15. Remaining Blockers

1. **union-alpha unsupported** (HTTP 401) — external provider limitation, not fixable
2. **LLM latency 1.3–14.7s** — LLM generation dominates, no safe reduction
3. **MG IM6 no verified corpus** — data gap (no official evidence exists), correct behavior to return insufficient
4. **Community admin UI** — API-only moderation, UI deferred
5. **Canonical spec count 44 vs old claim 53** — old docs overcounted; actual canonical table count is 44 (11+19+11+3). Not a defect, a documentation correction.
