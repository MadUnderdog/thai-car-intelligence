# AI Integration Smoke Test Report — P4

**Date:** 2026-09-18
**Branch:** fix/p1-provenance-gate

## Summary

| Test Category | Pass | Fail |
|---------------|------|------|
| Provider smoke tests | 4 | 0 |
| AI Ask scenarios | 4 | 0 |
| Evidence Gate tests | 1 | 0 |
| RAG/retrieval tests | 1 | 0 |
| Fallback/error tests | 1 | 0 |
| **Total** | **11** | **0** |

## Provider Configuration

| Setting | Value |
|---------|-------|
| Provider | openai-compatible |
| Base URL | https://opencode.ai/zen/go/v1 |
| Model | glm-5.3-flash |
| Embedding | Not configured (local service) |

## Smoke Test Results

### Test 1: Simple Generation
- **Status:** PASS
- **Latency:** 14,677ms
- **Tokens:** 66
- **Result:** "สวัสดี (sawasdee) — This is the standard Thai greeting..."

### Test 2: Thai Car Price Question with Evidence
- **Status:** PASS
- **Latency:** 3,402ms
- **Tokens:** 98
- **Result:** "Honda City e:HEV มีราคา 569,000 บาท ครับ"
- **Evidence Grounding:** ✅ Answered from provided evidence only

### Test 3: Comparison Question
- **Status:** PASS
- **Latency:** 2,670ms
- **Tokens:** 262
- **Result:** Structured comparison table with Honda City vs Civic
- **Evidence Grounding:** ✅ Used only provided evidence

### Test 4: Unsupported Fact Handling
- **Status:** PASS
- **Latency:** 1,279ms
- **Tokens:** 153
- **Result:** "ขออภัย ไม่มีข้อมูลเพียงพอในการตอบคำถามนี้..."
- **Hallucination Guard:** ✅ Refused to answer without evidence

## AI Ask Scenarios

| Scenario | Status | Notes |
|----------|--------|-------|
| Price question (verified vehicle) | PASS | Answered from evidence |
| Spec question (verified spec) | PASS | Answered from evidence |
| Comparison question (2 vehicles) | PASS | Structured comparison |
| Unsupported fact | PASS | Refused to answer |

## Evidence Gate Behavior

- ✅ Verified facts are answerable
- ✅ Unverified research facts cannot be presented as verified
- ✅ Missing specs stay missing
- ✅ Source metadata preserved in context

## Fallback/Error Behavior

- ✅ Provider returns structured error on failure
- ✅ Timeout handling implemented
- ✅ Graceful degradation when evidence insufficient

## Code Changes

| File | Change |
|------|--------|
| lib/ai/providers/openai-compatible.ts | Added OpenCode session ID header |

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
2. OpenCode session ID is auto-generated per request (may need persistent session for production)
3. Model "union-alpha" returns HTTP 500 (using "glm-5.3-flash" as fallback)
4. Response time varies (1.3s - 14.7s depending on query complexity)

## AI/Config Confirmation

- ✅ No secrets committed
- ✅ .env not modified
- ✅ .env.example remains placeholder-only
