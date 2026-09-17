# Quality Gate Report — 2026-08-25

## 1. Current Strengths

- **Verified official prices**: 76 variants with source URLs from official manufacturer pages
- **Source provenance model**: every price has source document + verification status
- **SSRF-safe fetch**: all external HTTP goes through validated pipeline
- **Hybrid search**: structured catalog + vector retrieval
- **AI honesty**: no-key mode returns "unavailable" instead of fabrication
- **CarCompare**: works with real data, source-backed comparison
- **OCR fallback**: Tesseract eng+tha for scanned brochures
- **Research audit trail**: research runs + candidates persisted

## 2. Current Data Weaknesses

### Critical
- **Fabrication risk**: AI answered "328,000 THB" for cheapest car when actual is 399,000. No retrieval guard prevented this.
- **Zero specs**: 76 variants have 0 specification records
- **Zero images**: 0 media records
- **Zero features**: 0 feature records

### Schema Issues
- **Model/trim mixing**: BYD ATTO 3 Premium and Extended are separate models but should be trims under one model
- **Single source per brand**: most brands share 1 source doc across all models
- **No generation field**: can't distinguish model year/generation properly

### RAG Quality
- **Entity extraction fails for compound queries**: "EV ราคาไม่เกิน 800,000" doesn't find EVs
- **No-data response in English**: should always respond in Thai
- **2/8 golden tests passed**

## 3. Verified vs Pending Records

```text
Manufacturers:        13 verified
Models:               74 verified
Variants:             76 verified
Current prices:       76 verified (all from official pages)
Source documents:     18 (many shared across models)
Specs:                0 pending
Images:               0 pending
Features:             0 pending
Embeddings:           5 chunks (MG only)
Brochures:            0 verified
```

## 4. RAG Benchmark Results

```text
Tests run:    8
Passed:       2 (cross-brand, feature-search)
Failed:       6
  - price-exact: entity match too strict (answer was correct)
  - price-range: returned Accord e:HEV instead of EVs
  - comparison: AI timeout
  - cheapest: fabrication (328k vs 399k)
  - brand-filter: AI timeout
  - unknown: answered in English, regex didn't match
```

**Root causes:**
1. Entity resolution too strict for Thai compound queries
2. AI fabrication when retrieval returns irrelevant results
3. Timeout on complex multi-entity queries
4. No Thai-first response enforcement in prompt

## 5. Recommended Next Expansion Brands (after fixing quality)

Priority order (based on Thai market share + data availability):

1. **BMW** — bmw.co.th has structured price/spec pages
2. **Mercedes-Benz** — mercedes-benz.co.th
3. **Volvo** — volvocars.com/th
4. **GWM** — gwm.co.th (new brand, growing fast)
5. **Subaru** — subaru-motor.co.th

But **first fix**:
1. Fabrication guard in AI retrieval
2. Thai-first response enforcement
3. Entity extraction improvement for compound queries
4. Model/trim relationship fix for BYD ATTO 3

---

## Summary

```text
Overall data quality: 40% (prices only, no specs/images/features)
Schema correctness: needs model/trim restructure
RAG quality: needs entity resolution + fabrication guard fixes
Search quality: structured works, vector underutilized
AI quality: correct when evidence is strong, fabrication when weak
```

**Decision**: Fix quality foundations before adding more brands.
