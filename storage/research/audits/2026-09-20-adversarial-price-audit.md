# Adversarial Price Audit — 2026-09-20

## Summary
- Total prices: 226
- Current prices before audit: 65
- Current prices after quarantine: 60
- Quarantined: 5 bad current prices

## Quarantine Actions

### 1. GR Corolla → Corolla Altis HEV (WRONG MAPPING)
- **Amount:** ฿4,199,000
- **Was mapped to:** Toyota Corolla Altis / HEV
- **Actual source:** Toyota web-init API → `grcorolla` code
- **Correct model:** GR Corolla (separate model, not Corolla Altis HEV)
- **Action:** Expired (isCurrent=false)
- **Root cause:** Extraction script mapped GR Corolla to Corolla Altis because both contain "corolla"

### 2. GR Yaris → Yaris ICE (WRONG MAPPING)
- **Amount:** ฿3,499,000
- **Was mapped to:** Toyota Yaris / ICE
- **Actual source:** Toyota web-init API → `gryaris` code
- **Correct model:** GR Yaris (separate model, not Yaris ICE)
- **Action:** Expired (isCurrent=false)
- **Root cause:** Extraction script mapped GR Yaris to Yaris because both contain "yaris"

### 3. Fortuner GR Sport → Fortuner ICE (WRONG VARIANT)
- **Amount:** ฿1,969,000
- **Was mapped to:** Toyota Fortuner / ICE
- **Actual source:** Toyota web-init API → `fortuner_grsport` code
- **Correct variant:** GR Sport (not "ICE")
- **Action:** Expired (isCurrent=false)
- **Root cause:** No "GR Sport" variant existed for Fortuner; defaulted to "ICE"

### 4. Navara King Cab Calibre E — 9CARTHAI price likely wrong trim
- **Amount:** ฿1,045,000
- **Source:** 9carthai_brand_page_regex
- **Conflict:** Nissan iframe shows King Cab Calibre E starting at ฿765,000
- **Likely:** ฿1,045,000 is for a different Navara trim (e.g., 4WD variant)
- **Action:** Expired (isCurrent=false)
- **Note:** Needs re-verification from 9CARTHAI source

### 5. Corolla Cross HEV duplicate
- **Amount:** ฿1,254,000 (two rows: LIST_PRICE from Toyota API, MSRP from 9CARTHAI)
- **Action:** Expired the Toyota API LIST_PRICE row (same amount, keep 9CARTHAI MSRP)
- **Note:** Both sources agree on amount — data is correct, just deduplicated

## Remaining Anomaly: Fortuner variant mapping
- DB only has variants: "ICE", "2.4 G", "2.4 LEGENDER"
- Toyota API returns: Leader (1,239,000-1,600,000), Legender (1,643,000-1,904,000), GR Sport (1,969,000)
- Need to create proper variants or fix existing mapping

## Current Price Distribution (post-quarantine)
| Brand | Current Prices |
|-------|---------------|
| Toyota | 20 |
| Honda | 18 |
| Nissan | 12 |
| BYD | 3 |
| MG | 3 |
| Isuzu | 2 |
| Hyundai | 1 |
| Kia | 1 |
| **Total** | **60** |
