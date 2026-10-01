# P121 — UI Capture Pack Review (real browser, desktop + mobile)

- **Run IDs:** `p121-20260930-baseline` (red-before, before any UI fix) · `p121-20260930-final` (after fixes)
- **Captured on:** 2026-09-30/10-01 (+07) against `http://127.0.0.1:3099` (production `next build` + `next start`)
- **Base:** `8fda850671ab5d6ad2d6e8b830e7c033b7c87e17` (P120-R1) — all P121 work committed on top
- **Browser:** Playwright Chromium (system Chrome, `--no-sandbox`), viewports **desktop 1440×900** and **mobile 390×844**
- **Machine-readable truth:** `manifest.json` in each run dir (route, viewport, screenshot paths, HTTP status,
  console/page errors, failed requests, per-check booleans, interaction results, `summary`)
- **Reproduce:** `P121_RUN_ID=p121-20260930-final node scripts/p121_ui_capture.mjs` (spawns/reuses port 3099, read-only)

## Headline

| | pages | failed checks | console errors | screenshots | defects |
|---|---|---|---|---|---|
| baseline (red-before) | 12 | 11 | 0 | 17 | **24** |
| final | 20 | **0** | **0** | **31** | **0** |

Baseline `manifest.json` keeps the exact red-state defects; final `manifest.json` proves every check green
AND every interaction ok (search typing, compare selection, difference-filter toggle, AI-ask availability).

## Page × viewport matrix (final)

| # | route | desktop | mobile | notes |
|---|---|---|---|---|
| 1 | `/` | ✅ | ✅ | stats 747/36/19/37 (real ACTIVE-row counts), cards show real ฿ prices, label "รถยนต์ที่มีราคาตรวจสอบแล้ว" |
| 2 | `/cars` | ✅ | ✅ | mobile: +compare toggles → "เลือกแล้ว 2/4" bar → `/compare?ids=…` handoff verified |
| 3 | `/cars/toyota/gr-86` | ✅ | ✅ | honest mostly-unavailable state (bv price gate, thin specs) — truthful, not fabricated |
| 4 | `/cars/mg/mg-s5` | ✅ | ✅ | "สเปคหลัก — EV PLUS": 130 kW / 280 Nm / 4325×1815×1530 / 61.1 kWh LFP / 88 kW DC + ฿749,900 + source link |
| 5 | `/cars/honda/city-hatchback` | ✅ | ✅ | ฿579,000 + clickable provenance `แหล่งข้อมูล: Honda Thailand Official Website ↗` |
| 6 | `/search` (+typing "City") | ✅ | ✅ | results with real price (interaction asserted price matches > 0) |
| 7 | `/search?q=GR 86` | ✅ | ✅ | truthful empty state (model outside verified-price catalog) |
| 8 | `/compare` price pair (City V + Serena V) | ✅ | ✅ | ฿579,000 vs ฿1,469,000 with source links; only meaningful sections rendered |
| 9 | `/compare` specs pair (MG4 + MG S5) | ✅ | ✅ | 125/130 kW, 250/280 Nm, 350/420 km, 51/61.1 kWh; filter narrows to differing rows |
| 10 | `/ai-ask` | ✅ | ✅ | reachable without credentials (input ready); no AI request sent during capture |

Screenshots: full-page JPEG per route×viewport + interaction/viewport PNGs
(`search-interaction-*`, `cars-compare-selection-mobile`, `compare-*-viewport`, `compare-*-toggled`).

## Defects found in baseline → fixed (evidence → regression)

1. **Home stats rendered `18 / 0 / 0 / 0`** — page read `totalManufacturers/evCount/hevCount` fields the API
   never returned (`|| 0` fallbacks). → `/api/cars` now returns real ACTIVE-row counts
   (**747 / 36 / 19 / 37**), page only renders stats the API actually sent. Test: `p121_api_cars_stats` (4, red 3→green 4).
2. **Home "รถยอดนิยม"/"รถยนต์ทั้งหมด" grid showed 12 alphabetically-first, mostly price-less models.**
   → fetched `sortBy=price_asc` (verified-price set), relabelled "รถยนต์ที่มีราคาตรวจสอบแล้ว";
   footer "รถยนต์ทั้งหมด" → "รถยนต์". Test: `p121_ui_contracts` F4/F5.
3. **Touch targets < 32px on mobile:** header nav (h20), footer nav, breadcrumbs, "ดูทั้งหมด" links (h20),
   detail sidebar actions (h24), search filter/clear buttons (h20). → `min-h-[32px]` everywhere incl. Button base.
   Verified by the capture's live rect measurement (touch_targets_ok now true on every mobile page).
4. **Dead button "🔖 บันทึก"** on detail sidebar (no handler, no backend). → removed. Test F2.
5. **Breadcrumb `aria-label="面包屑导航"`** (Chinese copy-paste artifact). → `aria-label="เส้นทางนำทาง"`. Test F3.
6. **Detail "สเปคหลัก" bound to `variants[0]`** (price-first) — mg-s5 showed 19× "ยังไม่มีข้อมูลยืนยัน" while
   sibling variant `s5-ev` had full typed specs. → `pickSpecVariant()` selects the variant with most typed
   spec data (ties keep price-first order). Spec section now shows real values. Tests: `p121_detail_spec_pick` (4).
7. **Verified price source unreachable on detail** (URL existed in payload, never rendered as a link).
   → provenance `<a>` with `target=_blank rel=noopener` (mirrors /compare). Test F6. Capture: `provenance_link_present`.
8. **`DifferenceFilter` was a dead component** (never imported; tables had no `#comparison-rows`/`data-different`).
   → wired: import + row-level `data-different` flags + label `min-h-[32px]`.
   Capture interaction proves behavior: rows 11→7 (specs pair), identical rows visible after toggle = 0. Test F7.
9. **Compare rendered all-empty spec groups** (e.g. battery/charging blocks for gasoline-only pairs →
   "demo-looking" walls of placeholders). → groups with zero values are not rendered. Test F8. Visual: price pair now shows only the populated ราคา section.
10. **Capture-harness defects fixed at their boundary** (not app defects): wrong city slug (404), Next.js
    `_rsc` prefetch aborts counted as page failures, sr-only inputs counted as tap targets, manifest
    screenshot filename collisions between compare pages.

## Honest limitations (unchanged by design — NOT defects)

- **`bmw`/model cards use the neutral 🚗 placeholder** — the DB has no vehicle photos; no fake images were added.
- **bv (BrochureVerification) price gate = 18 verified-price variants** — other models (incl. GR 86) truthfully
  show "ยังไม่มีข้อมูลราคา/ยืนยัน". No bv backfill performed (P120 contract, unchanged).
- **Typed spec tables are small** (PerformanceSpec 36 / DimensionsSpec 26 rows DB-wide); `VariantSpec`
  thousands of rows are research-tier and shown only in the clearly-marked "ข้อมูลจากงานวิจัย (ยังไม่ยืนยัน)"
  block with raw extraction keys (`battery.capacityKwh` …) — English keys are a known polish gap.
- **Search only spans the verified-price catalog** (public-surface contract from P115/P116) — `q=GR 86`
  therefore shows the truthful empty state; `q=City` succeeds.
- **Model display names come from seed data with inconsistent casing** (`Bmw Ix` vs `BMW X5`) — data layer,
  untouched this wave.
- **Price ranges on single-price models render `฿X - ฿X`** (min = max) — truthful, mildly redundant.
- `/ai-ask` was captured in ready state; no AI request was issued (no credentials, no cost).

## Data & safety statement

- **UI/product hardening only.** No schema change, no provider/model/config change, no verifier rewrite,
  no production promotion, **no production DB writes** (capture is read-only; only live SELECTs and public APIs).
- **P120 / P120-R1 did NOT create a new production row**; this wave did not either.
- **No fictional "Phase 7"** — Blueprint §101 ends at Phase 6; this wave is post-roadmap UI/product hardening.
