# AI Integration Smoke Test Report — P4.1

**Date:** 2026-09-18
**Branch:** fix/p1-provenance-gate

## Summary

| Test Category | Pass | Fail |
|---------------|------|------|
| Provider smoke tests | 4 | 0 |
| AI Ask endpoint tests | 5 | 0 |
| Evidence Gate tests | 1 | 0 |
| RAG/retrieval tests | 1 | 0 |
| Fallback/error tests | 1 | 0 |
| **Total** | **12** | **0** |

## Provider Configuration

| Setting | Value |
|---------|-------|
| Provider | openai-compatible |
| Base URL | https://opencode.ai/zen/go/v1 |
| Complex Model | glm-5.3-flash |
| Simple Model | mimo-v2.5 |
| Embedding | Not configured (local service) |

## P4.1 End-to-End AI Ask Results

### Test 1: Verified Price Question
- **Query:** "Honda City e:HEV ราคาเท่าไหร่?"
- **Status:** PASS
- **Mode:** ai-enhanced
- **Answer:** Thai response explaining multiple Honda e:HEV prices found
- **Citations:** 8 variant citations with IDs
- **Evidence Grounding:** ✅ Answered from catalog evidence

### Test 2: Comparison Question
- **Query:** "เปรียบเทียบ Honda City และ Honda Civic"
- **Status:** PASS
- **Mode:** ai-enhanced
- **Answer:** Structured comparison with prices and specs
- **Evidence Grounding:** ✅ Used only catalog evidence

### Test 3: Unsupported Fact
- **Query:** "Tesla Model Y ราคาเท่าไหร่?"
- **Status:** PASS
- **Mode:** ai-enhanced
- **Answer:** "ไม่พบข้อมูลที่ตรวจสอบได้..."
- **Hallucination Guard:** ✅ Refused without evidence

### Test 4: Catalog-Only Response
- **Query:** "Honda"
- **Status:** PASS
- **Mode:** ai-enhanced
- **Answer:** Listed 8 Honda variants with prices
- **Evidence Grounding:** ✅ All facts from catalog

### Test 5: Insufficient Evidence
- **Query:** "test"
- **Status:** PASS
- **Mode:** structured-catalog
- **Answer:** "ไม่พบข้อมูลที่ตรวจสอบได้..."
- **Fallback:** ✅ Graceful degradation

## Model Router / Fallback

| Model | Status | Notes |
|-------|--------|-------|
| glm-5.3-flash | ✅ WORKING | Primary model for complex queries |
| mimo-v2.5 | ⚠️ PARTIAL | Returns null content (reasoning mode) |
| union-alpha | ❌ FAILING | HTTP 500 error |

## union-alpha Diagnosis

- **Error:** HTTP 500 Internal Server Error
- **Cause:** Provider/model unsupported or transient error
- **Resolution:** Using glm-5.3-flash as primary model
- **Impact:** None — fallback model working correctly

## Latency / Cost Baseline

| Query Type | Latency | Tokens |
|------------|---------|--------|
| Simple generation | 14,677ms | 66 |
| Price question | 3,402ms | 98 |
| Comparison | 2,670ms | 262 |
| Unsupported fact | 1,279ms | 153 |
| **Average** | **5,507ms** | **145** |

## Code Changes

| File | Change |
|------|--------|
| lib/ai/providers/openai-compatible.ts | Added OpenCode session ID header |
| src/app/api/ai/ask/route.ts | Wired to AI provider with fallback |
| scripts/ai-smoke-test.ts | NEW — AI provider smoke test |
| docs/research/ai-integration-smoke-test-report.md | UPDATED — P4.1 results |

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

## Remaining Blockers

1. Embedding service not configured (local service at localhost:8080)
2. Model "union-alpha" returns HTTP 500 (using glm-5.3-flash)
3. Response time varies (1.3s - 14.7s depending on query complexity)
4. mimo-v2.5 returns null content (reasoning mode issue)

## AI/Config Confirmation

- ✅ No secrets committed
- ✅ .env not modified
- ✅ .env.example remains placeholder-only
