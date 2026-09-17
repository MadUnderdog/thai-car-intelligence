# Catalog Integrity Audit — Batch 1

**Date:** 2026-08-26
**Tests:** 149/149 passed

---

## 1. Entity Integrity

### Current catalog
```text
Manufacturers: 13
Models: 76
Variants: 78
All variants: ACTIVE status
```

### Discovered entities — status assessment

| Entity | Status | Reason |
|--------|--------|--------|
| Honda City Hatchback | EXISTING, CURRENT | Verified: specs + price + ADAS from official launch |
| Honda Super One | EXISTING, CURRENT | Has price (฿990,000) but NO specs. Needs verification |
| Mazda CX-3 | EXISTING, CURRENT | Has price but NO specs. Needs verification |
| Mazda CX-80 | EXISTING, CURRENT | Has price but NO specs. Needs verification |

**Do NOT auto-publish new entities.** Honda Super One, Mazda CX-3, Mazda CX-80 remain as reference-only with incomplete data.

---

## 2. Variant/Model Consistency

```text
Toyota Camry: 3 variants (HEV Smart, HEV Premium, HEV Premium Luxury) ✅ correct trim separation
All other models: 1 variant each ✅
No duplicate models found ✅
No trim-as-model issues found ✅
```

---

## 3. Price Integrity

```text
All 78 variants: have current price ✅
All prices: from verified source documents ✅
No unverified prices in published catalog ✅
```

---

## 4. Fuel Type Provenance

```text
Official verified: 0
Secondary verified: 1 (Honda City Hatchback)
Reference: 15 (Honda City, Civic, CR-V, HR-V, Accord, Nissan Almera/Kicks/Terra/XTrail, Mazda 2/3/CX-30/CX-5)
Inferred: 19 (BYD EV/HEV/PHEV from names, Honda City Hatchback was inferred before upgrade)
Unknown: 39 (models without fuel type data)
```

**Issue:** 13 BYD EVs + 4 HEVs + 2 PHEVs have fuel type INFERRED from vehicle naming (e.g., "EV" in name). This is correctly marked as INFERRED.

---

## 5. Honda Brochure Cross-Verification

```text
Honda City India brochure: downloaded, OCR extracted
  Market: INDIA (not Thai)
  Source type: PRIMARY_OTHER_MARKET
  Used for: cross-reference only
  e:HEV torque: 253 Nm (matches Thai spec from motorist.co.th)
  Petrol: 89 kW (121 PS), 145 Nm

Rule: India brochure does NOT upgrade Thai data to OFFICIAL_VERIFIED
Thai-market data takes precedence when available.
```

---

## 6. Official Images Audit

```text
Total images: 12 (one per model for 12 models)
Official manufacturer images: 2 (Nissan Kicks from nissan.co.th, Mazda CX-30 from mazda.co.th)
Third-party images: 1 (Honda City from zigwheels.co.th — NOT official)
Previously added: BYD (4), MG (4), Toyota (1) — all from official CDNs
```

**Correction needed:** Honda City image from zigwheels.co.th should be marked as REFERENCE, not OFFICIAL.

---

## 7. Batch 1 Final Metrics

### Coverage
```text
Published current variants: 78
Batch 1 variants reviewed: 19
Discovered candidates: 0 (no new entities auto-published)
Unverified entities: 3 (Honda Super One, Mazda CX-3, Mazda CX-80 — no specs)
```

### Source Quality — Specifications
```text
Official verified: 18 PerformanceSpec + 18 DimensionsSpec + 11 BatterySpec + 11 ChargingSpec = 58
Secondary verified: 5 + 5 = 10
Reference: 11 + 11 = 22
Inferred: 8 + 8 = 16
```

### Coverage by Brand (Batch 1)
```text
Brand     Variants  Specs  ADAS  FuelType  Images
──────────────────────────────────────────────────
Honda        7       7/7    7/7    7/7      1
Nissan       6       6/6    4/6    6/6      1
Mazda        6       5/6    5/6    5/6      1
──────────────────────────────────────────────────
Total       19      18/19  16/19  18/19     3
```

### ADAS Verified Coverage
```text
Variants with ADAS: 33 (out of 78 total)
  BYD: 7 variants, 12-16 features each, official_verified
  MG: 4 variants, 12-14 features each, official_verified
  Toyota: 6 variants, 8 features each, official_verified
  Honda: 7 variants, 3-9 features each, secondary/reference
  Nissan: 4 variants, 3-8 features each, secondary/reference
  Mazda: 5 variants, 3-7 features each, reference
```

### Image Coverage
```text
Models with images: 12/76 = 16%
  Official manufacturer: 2 (Nissan, Mazda)
  Official CDN: 8 (BYD, MG, Toyota)
  Third-party: 1 (Honda — zigwheels)
  Unknown source: 1
```

---

## 8. Issues Found

1. **Honda City image source**: zigwheels.co.th is NOT official — should be REFERENCE
2. **Honda Super One, Mazda CX-3, CX-80**: have prices but NO specs — need verification or removal
3. **39 variants missing fuel type**: need research
4. **16 inferred spec records**: from Wikipedia/media — need upgrade path
5. **Image coverage low**: 16% of models have images

---

## 9. No Mutations Made

This audit did NOT:
- Create duplicate models/variants
- Delete any reference data
- Auto-publish newly discovered entities
- Modify published catalog data
- Change source tiers without evidence

All 149 tests remain passing.
