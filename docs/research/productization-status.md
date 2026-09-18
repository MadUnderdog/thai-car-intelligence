# Productization Status Report — P5

**Date:** 2026-09-19
**Branch:** fix/p1-provenance-gate

## 1. Catalog Counts

| Item | Count |
|------|-------|
| Manufacturers | 16 |
| Canonical models | 61 |
| Canonical variants | 67 |
| Verified prices | 13 |
| Verified canonical specs | 53 |
| Research VariantSpec observations | 165 |
| Production evidence embeddings | 99 |

## 2. GLM-5.3-Flash vs mimo-v2.5 Benchmark

**Detailed report:** `docs/research/ai-model-benchmark.md`

| Metric | GLM-5.3-Flash | mimo-v2.5 |
|--------|---------------|-----------|
| Accuracy (24-case golden set) | **22/24 (91.7%)** | 19/24 (79.2%) |
| Success rate | 24/24 | 24/24 |
| Avg latency | 6,532ms | 5,770ms |
| Total tokens | 10,858 | 9,117 |
| Unsupported-claim handling | 2/2 correct refusal | 2/2 correct refusal |
| Conflict preservation | 1/1 | 1/1 |

**Per-category:** GLM wins on variant disambiguation (4/4 vs 2/4) and comparison (3/3 vs 2/3). Price and spec accuracy are tied (5/5 both). Mimo is marginally faster and lighter.

**Decision made from project workload evidence:** GLM-5.3-Flash is now the production default.

## 3. Active Default Model Configuration

| Setting | Value |
|---------|-------|
| Default model (AI_MODEL) | **glm-5.3-flash** |
| Simple model | mimo-v2.5 |
| Complex model | glm-5.3-flash |
| Fallback | glm-5.3-flash |
| Embedding | perplexity/pplx-embed-v1-0.6b (1024d) |
| Provider | openai-compatible (OpenCode) |

Readout command: `npx tsx scripts/model-readout.ts` (no secrets printed).

## 4. RAG Retrieval Quality (30-query Thai evaluation)

| Metric | Result |
|--------|--------|
| Top-1 correct | **25/30 (83.3%)** |
| Retrieval misses | 1 |
| False positives (need qualification) | 4 |
| No-evidence correctness | 0/4 (known gap: vector search always returns nearest neighbor) |
| Unverified data in production index | **0** |
| Embedding latency | avg 409ms (min 316ms, max 1913ms) |
| Vector search latency | avg 2ms (min 1ms, max 4ms) |

Threshold note: cosine distance < 0.35 ≈ correct entity; loose queries (e.g. "Tesla Model Y ราคา") return synthetic nearest neighbors — Evidence Gate must qualify these.

## 5. /api/ai/ask Status

- Wired to structured catalog + pgvector evidence merge (P4.5)
- Evidence grounding and hallucination guard confirmed
- Latency: avg ~5.5s, dominated by LLM generation (embedding ~0.4s, vector search ~2ms)
- No unsafe latency optimization applied that weakens grounding

## 6. Public Catalog Surface (Verified Data Only)

**Files changed:**
- `src/app/cars/[manufacturer]/[model]/page.tsx` — vehicle detail now exposes verified price (with provenance gate: requires VERIFIED SourceDocument + BrochureVerification), performance, battery, charging, dimensions, warranty
- `src/app/cars/[manufacturer]/[model]/VehicleDetailClient.tsx` — Thai spec sections with clean empty state

**Behavior:**
- Verified fields show actual values with evidence indicator "ℹ️ ราคาที่แสดงเป็นข้อมูลที่ผ่านการตรวจสอบจากแหล่งข้อมูลทางการเท่านั้น"
- Missing fields show Thai empty state: **"ยังไม่มีข้อมูลยืนยัน"**
- Research-only values are NOT shown as verified
- Comparison/search API contract unchanged

## 7. Community Foundation

**Schema added** (prisma migration applied via db SQL — CommunityComment, CommentVote, CommentReport):

| Model | Purpose |
|-------|---------|
| CommunityComment | comment with thread/reply (parentId), soft delete, moderation state (VISIBLE/HIDDEN/FLAGGED/DELETED), anti-spam fields (ipAddressHash, flaggedCount) |
| CommentVote | +1/-1 vote, unique per (comment, voterToken) |
| CommentReport | report with unique per (comment, reporterToken), resolved state |

**Boundary enforced:** Community writes NEVER mutate canonical facts. Test script `scripts/test-community.ts` proves 9/9 checks pass, including "canonical prices unmutated by community writes".

**Flow implemented:** Comment → isResearchLead flag → (future) ResearchCandidate → verification → canonical fact.

## 8. Files Changed (this milestone)

| File | Change |
|------|--------|
| scripts/ai-model-benchmark.ts | NEW — GLM vs Mimo benchmark (24-case) |
| scripts/benchmark-results.json | Raw benchmark data |
| docs/research/ai-model-benchmark.md | NEW — Benchmark report |
| scripts/model-readout.ts | NEW — Non-secret config readout |
| scripts/db-vector-search.ts | UPDATED — 30-query retrieval evaluation |
| scripts/test-community.ts | NEW — Community foundation tests |
| lib/catalog/verified-evidence-indexer.ts | (P4.6) reusable indexer, unchanged this milestone |
| src/app/cars/[manufacturer]/[model]/page.tsx | UPDATED — verified-only spec joins |
| src/app/cars/[manufacturer]/[model]/VehicleDetailClient.tsx | UPDATED — Thai spec sections + empty state |
| prisma/schema.prisma | Community foundation models |

## 9. DB Row Deltas

| Table | Before | After | Change |
|-------|--------|-------|--------|
| CommunityComment | 0 | 0 | table created (test data cleaned up) |
| CommentVote / CommentReport | 0 | 0 | tables created |
| Embedding | 99 | 99 | 0 |
| Price (verified) | 13 | 13 | 0 |
| Verified specs | 53 | 53 | 0 |
| VariantSpec | 165 | 165 | 0 |

## 10. Quality / Security Results

| Check | Result |
|-------|--------|
| prisma validate | ✅ valid |
| tsc --noEmit | ✅ clean |
| vitest run | ✅ 33/33 files, 228 tests |
| Community tests | ✅ 9/9 |
| AI live benchmark | ✅ 48/48 requests (24 cases × 2 models) |
| 30-query RAG evaluation | ✅ run (83.3% top-1) |
| .env committed? | ❌ never (verified git-tracked set) |
| .env.example secrets? | ❌ placeholders only |
| union-alpha use? | ❌ marked unsupported, not called |

## 11. Remaining Blockers

1. **union-alpha unsupported** (HTTP 401) — kept out of routing
2. **Latency variance** 1.3s–14.7s dominated by LLM generation time; no safe optimization without weakening grounding
3. **Ambiguous queries** — vector retrieval always returns nearest neighbor; Evidence Gate qualification for "no exact evidence" cases needs a confidence threshold, not yet implemented
4. **Community admin queue UI** — schema/API foundation ready; queue hook deferred to next milestone
5. **mimo-v2.5 reasoning-mode content** — works with system prompt; no change needed
