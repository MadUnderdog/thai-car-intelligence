# Thai Car Intelligence — Database Forensic Audit

## Table Row Counts
| Table | Rows |
|---|---|
| Manufacturer | 34 |
| CarModel | 207 |
| Variant | 343 |
| Price | 31 |
| Source | 11 |
| SourceDocument | 650 |
| BrochureVerification | 52 |
| DimensionsSpec | 26 |
| PerformanceSpec | 36 |
| BatterySpec | 19 |
| ChargingSpec | 3 |
| WarrantySpec | 9 |
| SafetySpec | 0 |
| VariantSpec | 165 |

## Price Audit (31 rows)
All 31 prices have full provenance chain:
- SourceDocument → Source → BrochureVerification
- All are isCurrent=true
- All have sourceDocumentId (no orphaned prices)

## Price Breakdown by Source Class
| Source Class | Count |
|---|---|
| OFFICIAL_MANUFACTURER (Toyota API) | 11 |
| OFFICIAL_MANUFACTURER (Honda website) | 8 |
| OFFICIAL_MANUFACTURER (Nissan HTML) | 10 |
| OFFICIAL_MANUFACTURER (MG website) | 2 |

## Price Breakdown by Type
| PriceType | Count |
|---|---|
| MSRP | 20 |
| LIST_PRICE | 11 |

## Spec Observations
| Table | Source: primary_official | Source: secondary | Total |
|---|---|---|---|
| DimensionsSpec | 15 | 11 | 26 |
| PerformanceSpec | 17 | 19 | 36 |
| BatterySpec | 8 | 11 | 19 |

## Key Findings
1. All 31 prices have full provenance chain
2. Toyota prices are LIST_PRICE (model-range), not MSRP
3. Honda/Nissan/MG prices are MSRP (variant-specific)
4. 26 dimension specs, 36 performance specs, 19 battery specs
5. Toyota specs from official API (primary_official)
6. Other specs from secondary automotive media (9carthai, headlightmag)
