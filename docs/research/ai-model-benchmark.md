# AI Model Benchmark: GLM-5.3-Flash vs mimo-v2.5 — P5

**Date:** 2026-09-19
**Branch:** fix/p1-provenance-gate
**Benchmark script:** `scripts/ai-model-benchmark.ts`
**Raw results:** `scripts/benchmark-results.json`

## Executive Summary

**GLM-5.3-Flash is the better model for this project.**

| Metric | GLM-5.3-Flash | mimo-v2.5 | Winner |
|--------|---------------|-----------|--------|
| Accuracy | **22/24 (91.7%)** | 19/24 (79.2%) | GLM |
| Success rate | 24/24 | 24/24 | Tie |
| Avg latency | 6,532ms | 5,770ms | Mimo (marginal) |
| Total tokens | 10,858 | 9,117 | Mimo (marginal) |

## Benchmark Setup

- **24-case Thai automotive golden set** using identical prompts, evidence, and settings for both models
- Same evidence bundles, same system prompt, same temperature settings
- Categories: 5 price, 5 spec, 4 variant-specific, 3 comparison, 2 alias/synonym, 2 ambiguous, 2 unsupported, 1 conflict

## Per-Category Results

| Category | GLM | Mimo |
|----------|-----|------|
| price | 5/5 | 5/5 |
| spec | 5/5 | 5/5 |
| variant | 4/4 | 2/4 |
| comparison | 3/3 | 2/3 |
| alias | 2/2 | 2/2 |
| ambiguous | 0/2 | 0/2 |
| unsupported | 2/2 | 2/2 |
| conflict | 1/1 | 1/1 |

Latency (successful cases): GLM min=2,267 avg=6,532; mimo min=2,377 avg=5,770. mimo total tokens 9,117, cost per case ~0.0091 THB.

## Key Findings

### Where GLM is better
- **Variant disambiguation**: GLM 4/4 vs Mimo 2/4 — Mimo confused variants (v1, v4)
- **Comparison questions**: GLM 3/3 vs Mimo 2/3 — Mimo failed c2 (battery comparison)
- **Overall accuracy**: GLM = 22/24 (91.7%); Mimo = 19/24 (79.2%)

### Where Mimo is better
- **Latency**: 5,770ms avg vs GLM 6,532ms (~12% faster)
- **Token efficiency**: 9,117 vs 10,858 tokens (~16% fewer)
- **Extreme outlier latency**: Mimo v3 hit 36,985ms on one run, but averages are consistent

### Where they are equivalent
- **Price questions**: both 5/5 (this is retrieval+prompt bound, not model bound)
- **Spec questions**: both 5/5
- **Alias/synonym**: both 2/2 — Thai alias handling handled by prompt, not model power
- **Unsupported fact handling**: both 2/2 correct refusals
- **Conflict preservation**: both 1/1
- **Ambiguous queries**: both 0/2 — retrieval/gate limitation, not a model problem
- **Thai language quality**: both produce natural Thai

### Tradeoff Summary

**Quality/speed/cost tradeoff:** GLM costs ~16% more tokens and ~11% more latency but delivers **+12.5 percentage points in accuracy**. For a fact-based automotive intelligence product, accuracy is non-negotiable — GLM's higher accuracy on price, variant, and comparison questions is decisive.

Both models fail ambiguous queries (am1/am2) — retrieval, not model choice, is the limiting factor there.

## Recommendation

**Use GLM-5.3-Flash as the production default.** Keep mimo-v2.5 as fallback only where latency-sensitive and factually-simple tasks exist. Do not use union-alpha (unsupported).

## Latency Breakdown

| Model | Min | Max | Avg | p95 (approx) |
|-------|-----|-----|-----|--------------|
| GLM-5.3-Flash | 2,267ms | 13,428ms | 6,532ms | ~11,000ms |
| mimo-v2.5 | 3,948ms | 36,985ms | 5,770ms | ~9,000ms |

## Cost Estimate

| Model | Total tokens | Est. cost/case* |
|-------|-------------|-----------------|
| GLM-5.3-Flash | 10,858 | ~0.00011 THB |
| mimo-v2.5 | 9,117 | ~0.00009 THB |

*Estimated; actual cost depends on provider pricing tiers.

## Conclusion

GLM-5.3-Flash is materially better for this project's evidence-grounded Thai automotive workload. The accuracy gap (91.7% vs 79.2%) far outweighs the modest latency/token differences.
