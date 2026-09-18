# AI Integration Smoke Test Report — P4.4

**Date:** 2026-09-18
**Branch:** fix/p1-provenance-gate

## Summary

| Test Category | Pass | Fail |
|---------------|------|------|
| Provider smoke tests | 4 | 0 |
| AI Ask endpoint tests | 5 | 0 |
| Embedding smoke tests | 2 | 0 |
| DB Vector retrieval tests | 5 | 0 |
| Model diagnostics | 3 | 0 |
| **Total** | **19** | **0** |

## Provider Configuration

| Setting | Value |
|---------|-------|
| Provider | openai-compatible |
| Base URL | https://opencode.ai/zen/go/v1 |
| Complex Model | glm-5.3-flash |
| Simple Model | mimo-v2.5 |
| Embedding Provider | openai-compatible |
| Embedding Base URL | https://openrouter.ai/api/v1 |
| Embedding Model | perplexity/pplx-embed-v1-0.6b |
| Embedding Dimensions | 1024 |

## Embedding Dimension Contract

**Source of Truth:** Prisma schema (`embeddings.vector Unsupported("vector(1024)")`)

| Dimension Source | Status |
|------------------|--------|
| Prisma schema | 1024 ✅ |
| .env.example | 1024 ✅ |
| Actual model output | 1024 ✅ |
| Config validation | Enabled ✅ |

## Production Vector Index

**Status:** ✅ INDEXED in PostgreSQL/pgvector

| Metric | Count |
|--------|-------|
| Indexed corpus records | 10 |
| Source documents | 10 |
| Verified price facts | 6 |
| Verified spec facts | 3 |
| Verified warranty facts | 1 |

## DB Vector Retrieval Tests

| Query | Expected | Distance | Status |
|-------|----------|----------|--------|
| "Honda City ราคาเท่าไหร่" | honda-city-ehev | 0.2956 | ✅ PASS |
| "MG4 แบตเตอรี่กี่ kWh" | mg4-standard | 0.3073 | ✅ PASS |
| "Honda Civic กำลังกี่แรงม้า" | honda-civic-ehev | 0.3197 | ✅ PASS |
| "BYD Atto 3 ระยะทางวิ่งได้เท่าไหร่" | byd-atto3 | 0.2342 | ✅ PASS |
| "MG IM5 ชาร์จเร็วกี่ kW" | mg-im5-ev | 0.2677 | ✅ PASS |

**Results:** 5/5 queries returned correct evidence from pgvector

## AI Ask End-to-End Results

| Query | Status | Mode | Evidence Grounding |
|-------|--------|------|-------------------|
| Honda City price | ✅ PASS | ai-enhanced | ✅ |
| Comparison | ✅ PASS | ai-enhanced | ✅ |
| Unsupported fact | ✅ PASS | ai-enhanced | ✅ Hallucination guard |
| Catalog search | ✅ PASS | ai-enhanced | ✅ |
| Insufficient evidence | ✅ PASS | structured-catalog | ✅ Fallback |

## Latency / Cost Baseline

| Query Type | Latency | Tokens |
|------------|---------|--------|
| Simple generation | 14,677ms | 66 |
| Price question | 3,402ms | 98 |
| Comparison | 2,670ms | 262 |
| Unsupported fact | 1,279ms | 153 |
| Embedding (Thai) | 1,239ms | N/A |
| Embedding (spec) | 351ms | N/A |
| DB vector search | ~50ms | N/A |
| **Average (chat)** | **5,507ms** | **145** |
| **Average (embed)** | **795ms** | **N/A** |

## Code Changes

| File | Change |
|------|--------|
| scripts/index-evidence.ts | NEW — Production vector indexing |
| scripts/db-vector-search.ts | NEW — DB vector search test |
| docs/research/ai-integration-smoke-test-report.md | UPDATED — P4.4 results |

## Quality Checks

| Check | Result |
|-------|--------|
| `prisma validate` | ✅ valid |
| `vitest run` | ✅ 33/33 files, 228 tests pass |
| `next build` | ✅ clean |

## Verified Data Preservation

| Metric | Before | After |
|--------|--------|-------|
| Verified prices | 13 | 13 |
| Verified specs | 53 | 53 |
| Research observations | 165 | 165 |
| Embeddings in DB | 0 | 10 |

## Remaining Blockers

1. union-alpha model unsupported (HTTP 401)
2. Response time varies (1.3s - 14.7s)
3. AI Ask not yet wired to use DB vector retrieval (uses structured catalog only)

## AI/Config Confirmation

- ✅ No secrets committed
- ✅ .env not modified
- ✅ .env.example remains placeholder-only
