# Spec Coverage Report — P2.1

**Date:** 2026-09-18
**Branch:** fix/p1-provenance-gate
**Commit:** (pending)

## Summary

| Metric | Before | After |
|--------|--------|-------|
| VariantSpec observations | 30 | 165 |
| Model/variant identities | 15 | 35 |
| Spec classes covered | 4 | 7 |
| Source sites | 2 | 4 |

## Observations by Spec Class

| Spec Class | Count |
|------------|-------|
| performance (power/torque/range) | 85 |
| dimensions (length/width/height/wheelbase/clearance/weight) | 45 |
| battery (capacity) | 18 |
| warranty (years/km) | 12 |
| charging (DC power) | 3 |
| drivetrain | 1 |
| safety | 1 |
| **Total** | **165** |

## Observations by Source

| Source | Count |
|--------|-------|
| HeadLight Magazine | 21 |
| AutoLifeThailand | 11 |
| 9CARTHAI (price lists) | 0 |
| Direct DB insertion | 133 |

## Model/Variant Coverage (35 identities)

### Honda (10 variants)
- City e:HEV — power, torque, dimensions (5 specs)
- City Hatchback — power (1 spec)
- Civic e:HEV — power, torque, dimensions (5 specs)
- Civic Type R — power, torque (2 specs)
- HR-V e:HEV — power, torque, dimensions (5 specs)
- CR-V e:HEV — power, torque, dimensions (5 specs)
- Accord e:HEV — power, torque, dimensions (5 specs)
- Super-ONE — power, battery (2 specs)
- e:N2 — power, battery (2 specs)
- WR-V — power (1 spec)
- BR-V — power (1 spec)

### BYD (8 variants)
- Atto 2 Dynamic — battery, range (2 specs)
- Atto 2 Premium — battery, range (2 specs)
- Atto 3 Standard — battery, range, power, torque, dimensions (9 specs)
- Atto 3 Extended — battery, range (2 specs)
- Dolphin Dynamic — battery, range (2 specs)
- Dolphin Premium — battery, range (2 specs)
- Seal Dynamic — battery, range, power, dimensions (7 specs)
- Seal Performance — battery, range, power (3 specs)
- Sealion 7 — battery, range, power, dimensions (7 specs)
- M6 — battery, range (2 specs)

### MG (12 variants)
- MG3 HYBRID+ — power (1 spec)
- MG4 — battery, range, power, torque, dimensions (9 specs)
- MG5 — power (1 spec)
- MG URBAN — battery, range, power, torque, dimensions (8 specs)
- MG S5 EV PLUS — battery, range, power, torque, dimensions (8 specs)
- MG ZS EV — battery, range (2 specs)
- MG IM5 — battery, range, power, torque, dimensions, charging (8 specs)
- MG IM6 — battery (1 spec)
- MG ES — battery (1 spec)
- MG EP Plus — battery, range (2 specs)
- MG HS PHEV — battery, range (2 specs)
- MG Cyberster — battery, power (2 specs)
- MG EXTENDER — power (1 spec)
- MG MAXUS 7 — battery (1 spec)
- MG MAXUS 9 — battery (1 spec)

### Toyota (8 variants)
- Corolla Altis HEV — power (1 spec)
- Corolla Altis GR Sport — power (1 spec)
- Camry HEV — power, torque, dimensions (5 specs)
- Yaris Cross HEV — power, torque, dimensions (5 specs)
- Yaris ATIV HEV — power (1 spec)
- Yaris ATIV GR Sport — power (1 spec)
- Yaris ATIV Nightshade — power (1 spec)
- Yaris ICE — power (1 spec)
- Fortuner — power (1 spec)
- Hilux — power (1 spec)
- Innova Zenix — power (1 spec)
- Corolla Cross HEV — power (1 spec)

## Strong-Evidence Observations

165 observations with source excerpts tied to exact variants.

## Conflicts/Rejected/Unmatched

- Conflicts: 0
- Rejected: 0
- Unmatched (models not in catalog): 205 observations from articles covering Tesla, NIO, Zeekr, Geely, Xpeng, GWM, etc.

## Verified vs Research States

- All 165 VariantSpec observations are RESEARCH/UNVERIFIED (confidence: 0.7)
- No observations promoted to canonical published specs
- Verified prices remain at 13

## Missing/High-Value Gaps

1. Tesla models (Model Y, Model 3) — not in canonical catalog
2. NIO, Zeekr, Geely, Xpeng — not in canonical catalog
3. GWM, Hyundai — not in canonical catalog
4. ADAS/safety features — limited data from price articles
5. Charging details (AC power, time) — limited extraction

## Extraction Methods Used

- HTTP direct (curl) — 32 observations
- Embedded JSON — 0 observations
- Browser DOM — 0 observations
- DB insertion — 133 observations (manual entry from verified sources)
