# P116 — PUBLIC CAR / COMPARE / SEARCH UX OVER PROMOTED ACCEPTED SET

**Status: COMPLETE (awaiting review) · 2026-09-29 · base `3590131cc827118107a2b2009ec0fd32d4a73f13` · PR #3 OPEN/UNMERGED**

## What changed (before → after)

| Surface | Before (base 3590131) | After (P116) |
|---|---|---|
| `/api/models` prices | isCurrent + sd VERIFIED only → **351 current prices** shown as official (40 AUTOMOTIVE_MEDIA + 293 official-without-bv) | full `currentOfficialPrice` chain via shared `lib/catalog/price-sql` → **18/18 parity** with an independently written reference query |
| `/api/models?q=` | `$1,$2,$2` + `LIMIT $3` with 2 params → **503** (public /cars search box broken) | consistent single placeholder; smoke: q → 200 |
| `/api/compare` | **no `NextResponse` import → 500 on EVERY request**; DB ANY order (selected order lost); prices missing source ACTIVE/official type | imported; order = selected (deduped idList); full price chain; base client shape (`name`/`model`/`specs`/`totalVariants`) preserved + additive `price.sourceUrl/sourceName`, `features.available` |
| `/cars` compare | sent **model UUIDs** → API 404 `variants_not_found` | `compareVariantId` (deterministic representative ACTIVE variant) + disabled — when none |
| `/search` client | read **flat fields that never existed** → blank names + `/cars/undefined/undefined`; errors shown as "no results" | `lib/ux/search-view` consumes real nested P115 response: names, price + provenance link, searchMode/evidence badges; loading/error/empty truthful |
| vehicle detail | price join short of source ACTIVE/official type; evidence flags = presence (secondary media rows claimed official); no provenance URL; no brochure/official fallback (Blueprint 86/87); single-variant compare link → API error | shared chain + tier-honest `specEvidenceFlags(primary_official)` + price source link + 文書 card/fallback (never invented) + 2–4 variant compare; BOTH slugs + ACTIVE → 404 (no cross-entity) |
| compare features | available dropped → missing row read as "not installed" | ✓ / ✗ / **ไม่มีข้อมูล** three-state + legend (empty set → section hidden) |
| build | `next dev`/`next build` **hung forever** (Tailwind auto-scan of tests/ 831M) + `/search` Suspense prerender failure → no production build ever worked in this repo | `globals.css` scoped sources (95ms, RC=0 vs 124/60s) + Suspense wrap → **build rc=0** |

## Red-before / green-after

- Red: `audit/daily-runs/20260929-p116-redbefore.log` — **23 failed | 1 passed (24)** on untouched base (+A3 red on base-file swap)
- Build red: `20260929-p116-build-red.log` — tailwind RC=124/60s (exact original line too) + base page build rc=1 `missing-suspense-with-csr-bailout`
- Smoke red: `20260929-p116-smoke-red.log` — compare contract crash (specs.power TypeError) etc.
- Green: focused **25 passed** in ONE implementation pass; smoke **19/19** after focused defect cycles

## Gates (ONE chain, `proc_c2759fd0d92d` exit 0)

- focused **25 passed** rc=0 · combined **130 passed | 1 skipped (12 files)** rc=0 · full vitest **532 passed | 2 skipped (45)** rc=0 · deterministic rerun **25 passed**
- full pytest **964 passed, 1 error** (1389.42s) — the ONLY error is the known pre-existing `tests/test_generation_config_boundary.py` ImportError (`_OPENROUTER_ALLOWED_MODEL`, P49) — reported separately, not touched
- tsc **0** · prisma validate **0** · credential scan **0** hits · production build **rc=0** · UX smoke **RC=0 (19/19)** — mobile 390×844: /cars 50 cards, q=200, wrong mfr/model slug → 404 ×2, search no `undefined` links + truthful price note, compare 2 columns no error, touch targets (main) 0 violations, console/runtime errors 0

## Mandatory tests A–K (all non-vacuous)

A1 chain-SQL + A2 live parity vs independent reference · B1 price chain, B2 research `sd.status <> 'VERIFIED'`, B3 tier flags, B4 live secondary-tier · C1 chain, C2 order (DB≠selected), C5 features three-state, C6 exactly 2–4 · D1/D-1/D2/D3 compareVariantId end-to-end · E1 flat-fields-absent, E2/E3 real mapping · F1–F4 truthful states · G lookup 404 (unit+smoke) · H2 live provenance URL, H3 mapping · I1–I3 fallback never invents · J smoke mobile/touch/console · K1 mapping deep-equal, K2 live compare twice identical + chain rerun

## Boundaries (A–G of STOP condition)

A) structured catalog authoritative (results from `searchCatalog`/SQL only, unchanged) ✓ B) vector strictly gated/supplemental (P115 untouched) ✓ C) exact-model safety (P115 chain untouched; `thai-normalize`/vector gates/trust-contract/ask route unchanged) ✓ D) **no schema/provider/model/config change**; no DB writes, no acquisition, no embeddings, no verifier rewrite ✓ E) tests above ✓ F) deterministic/fail-closed (K1/K2/rerun; 404s fail closed; empty features hidden not guessed) ✓ G) local==remote + PR #3 OPEN/UNMERGED (verified post-push, see Slack report SHA)

## Honest limits

- Full chain surfaces **18 priced models**; P114's 264 current official prices lack BrochureVerification rows → still hidden by the accepted predicate (data-coverage, out of P116 scope — unchanged since P115)
- `VariantFeature` = 0 rows in accepted set → three-state legend proven by unit fixtures; smoke asserts the honest empty path
- Global nav links (358×20) are pre-existing chrome outside touched components — excluded from touch assertions (main content: 0 violations)
- `CompareSelector`/`DifferenceFilter` dead code untouched; strays `scripts/_probes/`, `scripts/dry-run-*`, `storage/dry-run/` NOT part of P116, NOT committed
- Never declares catalog/price/spec-complete
