# AI Integration Smoke Test Report — P4.6

**Date:** 2026-09-18
**Branch:** fix/p1-provenance-gate

## Summary

| Test Category | Pass | Fail |
|---------------|------|------|
| Provider smoke tests | 4 | 0 |
| AI Ask endpoint tests | 5 | 0 |
| Embedding smoke tests | 2 | 0 |
| DB Vector retrieval tests | 5 | 0 |
| Evidence merge tests | 2 | 0 |
| Model diagnostics | 3 | 0 |
| **Total** | **21** | **0** |

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

## Production Vector Index Expansion

**Status:** ✅ EXPANDED from 10 to 99 records

| Metric | Before | After |
|--------|--------|-------|
| Total embeddings | 10 | **99** |
| Verified price facts | 6 | **13** |
| Verified spec facts | 3 | **44** |
| Verified warranty facts | 1 | **9** |
| Charging facts | 0 | **3** |

## Idempotency Result

- First run: 66 indexed, 0 skipped, 0 errors
- Second run: 0 indexed, 66 skipped, 0 errors
- **Status:** ✅ IDEMPOTENT

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

| Query | Status | Mode | Vector Hit | Evidence Grounding |
|-------|--------|------|------------|-------------------|
| Honda City price | ✅ PASS | ai-enhanced | ✅ | ✅ |
| Comparison | ✅ PASS | ai-enhanced | ✅ | ✅ |
| Unsupported fact | ✅ PASS | ai-enhanced | ✅ | ✅ Hallucination guard |
| Catalog search | ✅ PASS | ai-enhanced | ✅ | ✅ |
| Insufficient evidence | ✅ PASS | structured-catalog | ✅ | ✅ Fallback |

## Evidence Merge Flow

```
Thai query
→ structured catalog retrieval
→ embedding
→ PostgreSQL/pgvector evidence retrieval
→ merge/rank evidence (structured priority)
→ Evidence Gate
→ model router
→ grounded Thai answer
→ source/evidence metadata
```

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
| lib/catalog/verified-evidence-indexer.ts | NEW — Reusable verified evidence indexer |
| scripts/index-all-verified.ts | Updated to use reusable indexer |
| docs/research/ai-integration-smoke-test-report.md | UPDATED — P4.6 results |

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
| Embeddings in DB | 10 | 99 |

## Remaining Blockers

1. union-alpha model unsupported (HTTP 401)
2. Response time varies (1.3s - 14.7s)

## AI/Config Confirmation

- ✅ No secrets committed
- ✅ .env not modified
- ✅ .env.example remains placeholder-only
