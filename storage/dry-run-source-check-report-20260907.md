# Thai Car Intelligence — Dry-Run Source Check Report
**Date:** 2026-09-07 09:03 ICT  
**Mode:** DRY-RUN (no published data modified)

---

## Summary

| Metric | Count |
|--------|-------|
| Total URLs checked | 39 |
| HTTP 200 (fully accessible) | 35 |
| HTTP 404 (broken) | 4 |
| Inaccessible (timeout/DNS/5xx) | 0 |
| Source/SourceDocument tables | empty (0 entries) |

## ⚠️ Broken Source URLs (HTTP 404)

| Model | Variant | Price (THB) | Broken URL | Status |
|-------|---------|------------|------------|--------|
| BYD ATTO 2 | Dynamic | 629,900 | `https://www.byd.com/en-th/car/atto2` | 404 |
| BYD ATTO 2 | Premium | 659,900 | `https://www.byd.com/en-th/car/atto2` | 404 |
| BYD M6 | Electric | 859,900 | `https://www.byd.com/en-th/car/m6` | 404 |
| BYD Seal | Dynamic RWD | 1,099,900 | `https://www.byd.com/en-th/car/seal` | 404 |
| BYD Seal | Performance AWD | 1,299,900 | `https://www.byd.com/en-th/car/seal` | 404 |
| BYD Sealion 7 | Advanced | 1,718,020 | `https://www.byd.com/en-th/car/sealion7` | 404 |

**Root cause:** BYD Thailand appears to have restructured their website. Only `atto3` and `dolphin` remain as active `/car/` pages. The other models' URLs have been removed or relocated — no redirects in place.

## Missing Data (no source URL at all)

| Model | Notes |
|-------|-------|
| BYD Sealion 5 DM-i | Model exists in DB, no variants/prices/sources |
| BYD Sealion 6 DM-i | Model exists in DB, no variants/prices/sources |

## ✅ Fully Accessible Sources (HTTP 200)

### BYD (2/7 product pages OK)
- `byd.com/en-th` — manufacturer homepage ✅
- `byd.com/en-th/car/atto3` — ATTO 3 ✅
- `byd.com/en-th/car/dolphin` — Dolphin ✅

### Honda (11/11 product pages OK)
- All Honda model pages accessible: city, cityhatchback, civic, civictyper, crv, en2, hrvehev, super-one, wrv, brv, accordehev

### MG (17/17 product pages OK)
- All MG model pages accessible: urban, mg4-my2026, mg-s5-ev-plus, mg-zs-ev, mg-es, mg-ep-plus, mg-im5, mg-im6, mg-maxus7, mg-maxus9-my26, mg-cyberster, all-new-mg3, mg-vs-hev, mg-hs, mg5, mg-zs, mg-extender-dc

### Toyota (1/1 product pages OK)
- `toyota.co.th/en/model-list` — single URL covers all Toyota models ✅

## Response Time Stats

| Metric | Value |
|--------|-------|
| Average | 750ms |
| Min | 134ms (Toyota) |
| Max | 1,660ms (BYD M6 404) |

## Domain Breakdown

| Domain | Accessible | Total | Notes |
|--------|-----------|-------|-------|
| www.byd.com | 3/7 | 7 | 4 broken (404) |
| www.honda.co.th | 11/11 | 12 | All OK |
| www.mgcars.com | 17/17 | 18 | All OK |
| www.toyota.co.th | 2/2 | 2 | All OK |

## Recommended Actions

1. **HIGH:** Verify and update 4 broken BYD source URLs — need to find current product page URLs on byd.com/en-th
2. **MEDIUM:** Add source URLs for Sealion 5 DM-i and Sealion 6 DM-i when available
3. **LOW:** Consider adding Source and SourceDocument entries for better provenance tracking

---

*Results saved to:*
- `storage/dry-run-source-check-20260907-090259.json`
- `storage/dry-run-source-check-latest.json`
