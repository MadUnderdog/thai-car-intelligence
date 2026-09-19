# Productization Status Report — P7

**Date:** 2026-09-19
**Branch:** fix/p1-provenance-gate

## 1. Catalog Counts

| Item | Count |
|------|-------|
| Manufacturers | 16 |
| Active models | 61 |
| Active variants | 67 |
| Verified prices | 13 |
| Verified canonical specs | 53 |
| Research VariantSpec observations | 165 |
| Production evidence embeddings | 99 |
| SourceDocument | 605 |

## 2. RAG Quality (30-query Thai evaluation)

| Metric | P5 (before) | P6 (after) |
|--------|-------------|------------|
| Hit-set top-1 | 21/25 | **25/25** |
| Hit-set misses | 4/25 | **0/25** |
| Ambiguous FP (hard-passed) | 4/4 | **0/4** |
| Ambiguous correctly rejected | 0/4 | **1/4** (Tesla — no corpus entity) |
| Ambiguous qualified (brand-coherent) | 0/4 | **3/4** (answer qualified, not untrusted) |
| Embedding latency avg | 436ms | 482ms |
| Vector search latency avg | 2ms | 2ms |

Root causes fixed:
1. **Thai alias gap**: added Thai→English token map (ฮอนด้า→honda, ซิตี้→city, etc.) → Thai queries now resolve to English entity tokens → content corroboration succeeds.
2. **Hard 0.45 absolute cutoff**: broad/comparison queries legitimately retrieve distant but entity-matched rows (d=0.47–0.55). Fixed: entity-corroborated rows get wider bound (0.60 max), uncorroborated rows still hard-rejected.
3. **Unqualified trust**: brand-matching rows previously passed as equal to exact matches. Fixed: rows beyond VECTOR_STRICT_DISTANCE (0.30) marked `qualified=true` → AI Ask injects Thai qualification prefix.

## 3. Evidence Gate Policy

Three states:
- **ACCEPTED**: distance ≤ 0.30 AND entity-corroborated → full confidence
- **QUALIFIED**: distance > 0.30 BUT entity-corroborated (0.30–0.60) → accepted but flagged
- **REJECTED**: distance > 0.45 without corroboration, or > 0.60 even with corroboration

## 4. AI Ask Quality

| Query | Mode | Status | Confidence |
|-------|------|--------|------------|
| Honda City ราคาเท่าไหร่ | ai-enhanced | ok | verified |
| ฮอนด้า ซิตี้ ราคาเท่าไหร่ | ai-enhanced | ok | verified |
| Tesla Model Y ราคาเท่าไหร่ | structured-catalog | insufficient_evidence | — |
| Honda City ล็อกหน้าจอเท่าไหร่ | ai-enhanced | ok | qualified |

Latency: avg 5.5s chat, 482ms embed, 2ms vector search (unchanged from P5).

## 5. Public Vehicle Detail

- Hero: verified price badge (✔️ยืนยันแล้ว / ⛔ยังไม่ยืนยัน), last-verified date
- Per-section evidence dots: ประสิทธิภาพ / แบตเตอรี่ / ขนาด / การรับประกัน
- Thai empty state: "ยังไม่มีข้อมูลยืนยัน"
- Research-only block: "ข้อมูลจากงานวิจัย (ยังไม่ยืนยัน)" with warning
- Compare CTA: "⚖️ เปรียบเทียบรุ่นนี้"

## 6. Comparison

`/api/compare` now gates prices on VERIFIED SourceDocument + BrochureVerification.

## 7. Community (Part E)

| Route | Method | Rate Limit | Description |
|-------|--------|------------|-------------|
| /api/community/comments | GET | — | List visible comments with replies |
| /api/community/comments | POST | 5/min | Create comment or reply |
| /api/community/comments/[id]/vote | POST | 20/min | Vote (up/down, idempotent) |
| /api/community/comments/[id]/report | POST | 10/min | Report with reason, auto-hide at 3 |

Anonymous identity via SHA-256 salted IP hash + httpOnly cookie. Threading via parentId. Duplicate prevention (same body 5 min). Vote switching supported.

## 8. Moderation + Research Hook (Part F)

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| /api/admin/community/moderation | GET | bearer | List flagged/hidden with report brief |
| /api/admin/community/moderation | PATCH | bearer | HIDE/DELETE/RESTORE |
| /api/admin/community/research-lead | POST | bearer | Handoff → ResearchCandidate |

Invariant: Community → optional research lead → ResearchCandidate → later verification → canonical fact. Never mutates Price/spec tables. Verified by test #9.

## 9. Test Results

| Check | Result |
|-------|--------|
| prisma validate | ✅ valid |
| tsc --noEmit | ✅ 0 errors |
| vitest run | ✅ 33/33 files, 228 tests |
| lint | 104 errors (pre-existing legacy; down from 139) |
| npm run build | ✅ clean |
| gate regression | ✅ 6/6 PASS |
| 30-query RAG eval | ✅ 25/25 hit-set |
| community test | ✅ 9/9 PASS |

## 10. DB Row Deltas

| Table | Before | After | Change |
|-------|--------|-------|--------|
| Verified prices | 13 | 13 | 0 |
| Verified specs | 53 | 53 | 0 |
| VariantSpec | 165 | 165 | 0 |
| Embedding | 99 | 99 | 0 |

## 11. Data/Security Invariants

- ✅ verified prices = 13 unchanged
- ✅ verified specs = 53 unchanged
- ✅ VariantSpec = 165 unchanged
- ✅ Embeddings = 99 (verified facts only)
- ✅ .env untouched
- ✅ .env.example placeholders only
- ✅ No secrets in git/report
- ✅ union-alpha unused
- ✅ No destructive migration
- ✅ No broad reindex
- ✅ No image generation

## 12. Files Changed (P6)

New: `lib/ai/retrieval/evidence-gate-policy.ts`, `scripts/rag-eval-v2.ts`, `scripts/evidence-gate-regression.ts`, 5 community API routes, `src/lib/community/identity.ts`, `src/lib/community/admin-auth.ts`, `src/components/community/CommunitySection.tsx`

Modified: `lib/ai/retrieval/evidence-merge.ts`, `src/app/api/ai/ask/route.ts`, `src/app/cars/[manufacturer]/[model]/page.tsx`, `VehicleDetailClient.tsx`, `src/app/api/compare/route.ts`

## 13. Remaining Blockers

1. union-alpha unsupported (HTTP 401)
2. Latency 1.3–14.7s = LLM generation (no safe reduction)
3. Brand-coherent but wrong vehicle-type queries → qualified path (correct behavior)
4. MG IM6: no embedding corpus entry → MISS (data gap)
5. Community admin UI deferred (API-only moderation)

## P7 Additions

### Vehicle-Type/Body-Type Intent (Part A)
- Added `lib/ai/retrieval/body-type-intent.ts`: BODY_TYPE_MAP (Thai+English), KNOWN_BODY_TYPES (slug→type), NAME_TO_BODY_TYPE (DB model name→type, 50 entries)
- Evidence gate now rejects body-type-violated vector evidence (longest-match-first to avoid "City" matching inside "City Hatchback")
- AI Ask route filters structured catalog results by body type
- Body-type regression: 8/8 PASS (exact, alias, brand-only, correct type, wrong type, ambiguous, unsupported, MG IM6)

### MG IM6 Diagnosis (Part B)
- 1 research observation (battery 90 kWh, DISCOVERED), 0 verified specs/price, 0 embeddings
- RAG miss is correct behavior — no verified evidence exists
- MG IM6 returns "qualified" when entity "mg" matches, insufficient otherwise

### RAG After P7
- Hit-set top-1: 25/25 (restored from 24/25 after body-type fix)
- Body-type regression: 8/8
- Gate regression: 6/6

### Compare UI (Part E)
- Missing data now shows "ยังไม่มีข้อมูลยืนยัน" instead of "—"
- Added provenance note at bottom

### Community Admin UI (Part F)
- New: `src/app/admin/moderation/page.tsx` — minimal Thai moderation queue
- Lists flagged/hidden comments with report brief
- Actions: HIDE/DELETE/RESTORE
- Bearer token auth

### Files Added (P7)
- `lib/ai/retrieval/body-type-intent.ts` — body-type intent extraction + mappings
- `scripts/body-type-regression.ts` — 8-case body-type regression
- `src/app/admin/moderation/page.tsx` — Thai admin moderation UI

### Files Modified (P7)
- `lib/ai/retrieval/evidence-gate-policy.ts` — body-type constraint in gate
- `src/app/api/ai/ask/route.ts` — body-type filtering of structured results
- `src/app/compare/CompareClient.tsx` — Thai missing-data state + provenance note
- `docs/research/productization-status.md` — this report

## P8 Additions

### Trust Contract (Part A)
- New: `lib/ai/trust-contract.ts` — unified FactualConfidence states (VERIFIED/QUALIFIED/INSUFFICIENT/CLARIFICATION_NEEDED/RESEARCH_UNVERIFIED)
- ProvenanceMeta type with verifiedEvidenceCount, qualifiedEvidenceCount, hasResearchObservations
- gateStateToConfidence() maps gate states to public contract
- confidenceLabel() returns Thai labels
- AI Ask route now returns `trust` field in all responses
- 14 new trust contract tests (242 total vitest)

### AI Ask UI (Part B)
- Trust state badges: ✔️ข้อมูลยืนยันแล้ว / ⚠️ข้อมูลบางส่วน / ⛔ยังไม่มีข้อมูลยืนยัน / ❓กรุณาระบุให้ชัดเจน
- Evidence count display (verified + qualified)
- Source citations with links
- All Thai text

### Catalog Discovery (Part C)
- Body type filter: SUV, Sedan, Hatchback, Pickup, MPV, Coupe
- Client-side filtering using NAME_TO_BODY_TYPE slug mapping
- Price display uses verified-only data (API-gated)
- Compare selection (up to 4) with compare bar

### Files Added (P8)
- `lib/ai/trust-contract.ts` — trust contract types + helpers
- `tests/trust-contract.test.ts` — 14 trust contract tests

### Files Modified (P8)
- `src/app/api/ai/ask/route.ts` — trust contract in all responses
- `src/app/ai-ask/AIAskClient.tsx` — trust badges, evidence count, citations
- `src/app/cars/page.tsx` — body type filter
- `docs/research/productization-status.md` — this report
