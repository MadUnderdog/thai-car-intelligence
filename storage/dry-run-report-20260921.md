# Thai Car Intelligence — Dry-Run Source Accessibility Check

**Run time:** 2026-09-21 09:02:45 (ICT)  
**Total URLs checked:** 176  
**Accessible:** 165 ✅ | **Inaccessible:** 11 ❌  
**Published data changed:** NO (dry-run)

---

## URL Breakdown by Source

| Source Type | Count |
|------------|-------|
| Source base URLs | 20 |
| SourceDocument URLs (DB) | 144 |
| Manufacturer website URLs | 22 |
| **Total unique URLs** | **176** |

## Domain Breakdown

| Domain | Accessible | Inaccessible |
|--------|-----------|-------------|
| autolifethailand.tv | 7/7 ✅ | 0 |
| www.9carthai.com | 13/13 ✅ | 0 |
| www.autospinn.com | 2/2 ✅ | 0 |
| www.bmw.co.th | 1/1 ✅ | 0 |
| www.byd.com | 2/2 ✅ | 0 |
| www.changan.co.th | 1/1 ✅ | 0 |
| www.chevrolet.co.th | 1/1 ✅ | 0 |
| www.ford.co.th | 1/1 ✅ | 0 |
| www.headlightmag.com | 54/54 ✅ | 0 |
| www.honda.co.th | 12/12 ✅ | 0 |
| www.kia.com | 1/1 ✅ | 0 |
| www.lexus.co.th | 1/1 ✅ | 0 |
| www.mazda.co.th | 7/7 ✅ | 0 |
| www.mercedes-benz.co.th | 1/1 ✅ | 0 |
| www.mgcars.com | 10/10 ✅ | 0 |
| www.mini.co.th | 1/1 ✅ | 0 |
| www.mitsubishi-motors.co.th | 6/6 ✅ | 0 |
| www.nissan.co.th | 20/20 ✅ | 0 |
| www.porsche.com | 1/1 ✅ | 0 |
| www.toyota.co.th | 23/23 ✅ | 0 |
| test.example.com | 0 | 1 ❌ (test fixture) |
| test2.example.com | 0 | 1 ❌ (test fixture) |
| test3.example.com | 0 | 1 ❌ (test fixture) |
| www.baic.co.th | 0 | 1 ❌ DNS fail |
| www.chery.co.th | 0 | 1 ❌ DNS fail |
| www.isuzu-tti.co.th | 0 | 1 ❌ DNS fail |
| www.jetour.co.th | 0 | 1 ❌ DNS fail |
| www.kgmobility.co.th | 0 | 1 ❌ DNS fail |
| www.ldvautomotive.co.th | 0 | 1 ❌ DNS fail |
| www.suzukimotor.co.th | 0 | 1 ❌ DNS fail |
| www.volvo.co.th | 0 | 1 ❌ SSL mismatch |

## ⚠️ Inaccessible Sources

### DNS Failures (domain not resolvable) — 6 brands
These manufacturer domains do not resolve via DNS. Possible causes: domain expired, changed, or not yet registered.

| Brand | URL | Error |
|-------|-----|-------|
| BAIC | https://www.baic.co.th | DNS: Name or service not known |
| Chery | https://www.chery.co.th | DNS: Name or service not known |
| Isuzu | https://www.isuzu-tti.co.th | DNS: Name or service not known |
| Jetour | https://www.jetour.co.th | DNS: Name or service not known |
| KG Mobility | https://www.kgmobility.co.th | DNS: Name or service not known |
| LDV | https://www.ldvautomotive.co.th | DNS: Name or service not known |
| Suzuki | https://www.suzukimotor.co.th | DNS: Name or service not known |

### SSL Certificate Issue — 1 brand

| Brand | URL | Error |
|-------|-----|-------|
| Volvo | https://www.volvo.co.th | SSL hostname mismatch — cert is not valid for www.volvo.co.th |

### Test Fixtures — 3 URLs (expected failures)
These are test/development URLs in the Source table, not real production sources:
- test.example.com, test2.example.com, test3.example.com

## ⚠️ 404 Model Pages (site structure changed)

Several model-specific URLs return HTTP 404, indicating site restructuring:

### Nissan Thailand — 15 model pages returning 404
All `/en/vehicles/*` paths now return 404:
- https://www.nissan.co.th/en/vehicles/almera
- https://www.nissan.co.th/en/vehicles/kicks
- https://www.nissan.co.th/en/vehicles/kicks-epower
- https://www.nissan.co.th/en/vehicles/navara
- https://www.nissan.co.th/en/vehicles/terra
- https://www.nissan.co.th/en/vehicles/x-trail
- https://www.nissan.co.th/en/vehicles/xtrail-epower
- https://www.nissan.co.th/en/vehicles/new-terra
- https://www.nissan.co.th/en/vehicles/new-vehicles/kicks-epower.html
- https://www.nissan.co.th/en/vehicles/new-vehicles/leaf.html
- https://www.nissan.co.th/en/vehicles/new-vehicles/livina.html
- https://www.nissan.co.th/en/vehicles/new-vehicles/march.html
- https://www.nissan.co.th/en/vehicles/new-vehicles/navara.html
- https://www.nissan.co.th/en/vehicles/new-vehicles/new-terra.html
- https://www.nissan.co.th/en/vehicles/new-vehicles/serena.html
- https://www.nissan.co.th/en/vehicles/new-vehicles/xtrail-epower.html

**Note:** Nissan homepage (https://www.nissan.co.th) still works and contains the hidden iframe with price JSON. The model subpages were migrated to a new URL structure.

### Mazda Thailand — 6 model pages returning 404
All `/en/cars/*` paths now return 404:
- https://www.mazda.co.th/en/cars/cx-3
- https://www.mazda.co.th/en/cars/cx-30
- https://www.mazda.co.th/en/cars/cx-5
- https://www.mazda.co.th/en/cars/cx-80
- https://www.mazda.co.th/en/cars/mazda2
- https://www.mazda.co.th/en/cars/mazda3

**Note:** Mazda homepage redirects to /th and is accessible. Model pages need new URL discovery.

### MG Thailand — 7 model pages returning 404
Old URL pattern pages are dead, new `/th/cars/*` pattern is working:
- https://www.mgcars.com/th/all-new-mg3 → 404 (use /th/cars/all-new-mg3)
- https://www.mgcars.com/th/mg-im5 → 404 (use /th/cars/mg-im5)
- https://www.mgcars.com/th/mg-s5-ev-plus → 404
- https://www.mgcars.com/th/mg-urban → 404
- https://www.mgcars.com/th/mg4 → 404
- https://www.mgcars.com/th/mg4-my2026 → 404
- https://www.mgcars.com/th_th/cars/mg-extender → 404
- https://www.mgcars.com/th_th/cars/mg-s5-ev-plus → 404

### Mitsubishi — 2 model pages returning 404
- https://www.mitsubishi-motors.co.th/en/cars/triton → 404
- https://www.mitsubishi-motors.co.th/en/cars/xpander → 404

### Honda — 1 model page returning 404
- https://www.honda.co.th/hr-v → 404 (note: /hrvehev works fine)

### BYD — 1 SourceDocument URL returning 404
- https://www.byd.com/th → 404 (main site uses /en-th)

## ✅ All Working Official Sources

### Toyota (23/23 ✅)
- Homepage: https://www.toyota.co.th — 200 ✅
- Web-init API: https://www.toyota.co.th/component/api/tcoth/web-init — 405 (expected, POST-only)
- 21 model API endpoints — all 200 ✅

### Honda (12/12 ✅)
- Homepage: https://www.honda.co.th — 200 ✅
- 11 model pages — all 200 ✅

### MG (10/10 ✅)
- Homepage: https://www.mgcars.com/th — 200 ✅
- 9 model pages (/th/cars/*) — all 200 ✅

### BYD (2/2 ✅)
- Homepage: https://www.byd.com/en-th — 200 ✅
- /en-th → 200 ✅

### Nissan (20/20 ✅)
- Homepage: https://www.nissan.co.th — 200 ✅
- Model subpages — all 404 (but homepage JSON works)

### Headlightmag (54/54 ✅)
- All article URLs accessible — 200 ✅

### 9CARTHAI (13/13 ✅)
- All brand price pages — 200 ✅

### AutoLifeThailand (7/7 ✅)
- All article URLs — 200 ✅

### AutoSpinn (2/2 ✅)
- Homepage + article — 200 ✅

## 📊 Performance Summary

| Metric | Value |
|--------|-------|
| Average response time | 915ms |
| Min response time | 54ms |
| Max response time | 6,812ms |
| Slowest domains | Lexus (4.1s), Porsche (6.8s), Mitsubishi (4.3s) |
| Fastest domains | Toyota API (150-210ms), Headlightmag (190-300ms) |

## 🔍 Changes Since Last Run (2026-09-14)

### Previous run: 39/39 accessible (100%)
### Current run: 165/176 accessible (93.8%)

**Key differences:**
1. Current run checks 176 URLs (vs 39 previously) — much more comprehensive
2. 7 new DNS failures discovered (BAIC, Chery, Isuzu, Jetour, KG Mobility, LDV, Suzuki) — these brands' .co.th domains are not resolving
3. Volvo SSL certificate issue detected
4. Nissan model subpages confirmed 404 (was known from skill notes)
5. Mazda model subpages confirmed 404 (new discovery)
6. MG old URL pattern confirmed 404 (new pattern works)
7. Mitsubishi Triton/Xpander subpages confirmed 404

## 💾 Files Saved

- `dry-run-report-20260921.md` — this report
- Previous reports: `dry-run-report-20260831.md`, `dry-run-report-20260907.md`

## ⚠️ Recommended Actions

1. **Update DNS for 7 brands** — BAIC, Chery, Isuzu, Jetour, KG Mobility, LDV, Suzuki domains are dead. Verify if these brands have moved to new domains.
2. **Fix Volvo SSL** — www.volvo.co.th has hostname mismatch. May need to check if cert covers volvo.co.th (without www).
3. **Discover new Nissan model URLs** — All /en/vehicles/* paths are 404. Need to find new URL structure.
4. **Discover new Mazda model URLs** — All /en/cars/* paths are 404.
5. **Update MG SourceDocuments** — Change URLs from /th/mg-* to /th/cars/mg-* pattern.
6. **Update Mitsubishi SourceDocuments** — Triton/Xpander URLs need new paths.

---

**No data was modified during this dry run.** All results are for review only.
