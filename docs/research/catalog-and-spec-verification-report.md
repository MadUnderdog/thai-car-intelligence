# Catalog & Spec Verification Report — P3

**Date:** 2026-09-18
**Branch:** fix/p1-provenance-gate

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Canonical models | 46 | 61 |
| Canonical variants | 51 | 67 |
| Research spec observations | 165 | 165 |
| Canonical verified spec facts | 0 | 27 |

## Canonical Models Added (15 new)

| Manufacturer | Model | Segment |
|--------------|-------|---------|
| Tesla | Model Y | SUV |
| Tesla | Model 3 | Sedan |
| Hyundai | Ioniq 5 | SUV |
| Hyundai | Santa Fe | SUV |
| NIO | Firefly | Hatchback |
| Geely | EX5 | SUV |
| GWM | Tank 500 | SUV |
| Mazda | 6e | Sedan |
| Subaru | Crosstrek | SUV |
| Zeekr | X | SUV |
| Avatr | 11 | SUV |
| Denza | Z9GT | Sedan |
| Xpeng | L03 | Sedan |
| Nissan | Kicks | SUV |
| BYD | Seal 6 | Sedan |

## Verified Spec Facts (27 total)

### PerformanceSpec (10)
- Honda City e:HEV: 80.2 kW, 253 Nm
- Honda Civic e:HEV: 103.7 kW, 287 Nm
- Honda HR-V e:HEV: 96.3 kW, 253 Nm
- Honda CR-V e:HEV: 135.3 kW, 335 Nm
- Honda Accord e:HEV: 152.2 kW, 335 Nm
- BYD Atto 3: 150 kW, 310 Nm
- BYD Seal: 230 kW, 360 Nm
- MG IM5: 170 kW, 350 Nm, 410 km
- MG4: 125 kW, 250 Nm, 350 km
- MG S5 EV PLUS: 130 kW, 280 Nm, 420 km

### BatterySpec (5)
- BYD Atto 3: 49.9 kWh, LFP
- BYD Seal: 82.5 kWh, Blade
- MG IM5: 77 kWh, NMC
- MG4: 51 kWh, LFP
- MG S5 EV PLUS: 61.1 kWh, LFP

### DimensionsSpec (7)
- Honda City e:HEV: 4589×1748×1467 mm, WB 2610, GC 135
- Honda Civic e:HEV: 4674×1802×1415 mm, WB 2735, GC 135
- Honda HR-V e:HEV: 4385×1790×1612 mm, WB 2660, GC 190
- BYD Atto 3: 4455×1875×1615 mm, GC 175
- MG IM5: 4928×1905×1485 mm, GC 145
- MG4: 4287×1836×1516 mm, GC 150
- MG S5 EV PLUS: 4325×1815×1530 mm, GC 155

### WarrantySpec (4)
- Honda City e:HEV: 5 years / 150,000 km
- BYD Atto 3: 8 years / 150,000 km vehicle + 8 years / 150,000 km battery
- MG IM5: 8 years / 150,000 km
- MG4: 8 years / 150,000 km

### ChargingSpec (1)
- MG IM5: 150 kW DC

## Evidence Sources

| Source | Tier | Facts |
|--------|------|-------|
| HeadLight Magazine | secondary_automotive_media | 15 |
| 9CARTHAI | secondary_automotive_reference | 12 |

## Evidence States

- All 27 canonical facts: sourceTier = "secondary_automotive_media" or "secondary_automotive_reference"
- All 27 canonical facts: verifiedAt = NOW()
- Research observations (165): status = "DISCOVERED", confidence = 0.7

## Conflicts/Rejected/Ambiguous

- Conflicts: 0
- Rejected: 0
- Ambiguous: 0

## Price vs Spec Provenance Separation

- Verified prices: 13 (unchanged)
- Verified specs: 27 (new)
- Price provenance: separate SourceDocument chain
- Spec provenance: separate SourceDocument chain
- No cross-contamination

## Remaining Coverage Gaps

1. Tesla/NIO/Zeekr/Geely/Xpeng — new catalog identities without verified specs
2. Toyota models — limited spec data
3. ADAS/safety features — minimal extraction
4. Charging details — limited (AC power, time)
5. Drivetrain details — minimal

## Publish Gate

- Public APIs expose verified canonical specs only
- Unsupported fields omitted (not filled with research guesses)
- Research observations not leaked into public API
