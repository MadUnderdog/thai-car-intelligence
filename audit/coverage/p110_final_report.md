# P110 — Dedicated price pass over the frozen P108/P109 accepted ledger

**wave:** P110 · **date:** 2026-09-28 · **baseline (frozen):** `p108_final_result.json` → accepted ledger = **488 first-party confirmed variants**

> Catalog identity work stops here (P109 closed all 32/32 OEMs). This wave asks only one
> question per accepted variant: *does a first-party Thai-market price exist on the SAME
> published record as that exact grade, and what price_type is it?*  Nothing is invented,
> nothing is spread across grades, and no identity count changes.

## 1. Contract (Blueprint §95 / §98)

- mandatory on every price row: identity (manufacturer + model + exact variant) + 
  `price.type` + value + currentness + scope (Thailand) + source class / trust tier +
  evidence locator with a same-record excerpt + provenance (sha256 / captured_at / state / session)
- `price_type` is mandatory and never converted: `EXACT_VARIANT` (grade list price),
  `MSRP_STARTING` (เริ่มต้น / starting from), `PROMOTIONAL`, `FINANCE_INSTALLMENT`, `RANGE`
- a model-level or range price is never promoted to a grade price (rule 5) → `UNVERIFIED_PRICE`
- third-party / enumerator prices are discovery only → never official MSRP (rule 8)
- blocked OEMs are not bypassed (rule 8); captured artifacts are reused, no new fetch (rule 7)

## 2. Input & plan

- `p110_price_target_plan.json` written before harvest: **488** accepted variants, 19 OEMs with accepted variants, 13 blocked OEMs listed as excluded
- blocked OEMs (no accepted variants, no bypass): Audi, Avance, BYD, Chery, Chevrolet, Ford, Haval, Mercedes-Benz, NETA, Peugeot, Smart, Tesla, Volvo
- new captures: **0** — the pass ran over already-captured first-party artifacts
  (`p110_price_capture_log.json`, `new_captures: 0`); no URL was re-fetched

## 3. How a same-record price was accepted (parser rules, each with red-before tests)

1. **record blocks** — label and money value must sit in the same published block
   (table row / paragraph / card); minified pages are re-split into row-level blocks and
   navigation blobs (>8 links, login/menu wording, multi-price promo banners) never bind
2. **structured data** — `application/ld+json` Vehicle/Offer nodes that name model + variant
   and carry a THB price are same-record evidence (Toyota pricelist = 99 nodes)
3. **PDF text layer** — captured `.pdf.b64` price sheets (Land Rover / Jaguar / MINI) are
   base64-decoded locally and read with `pdftotext -layout` (no network; image-only PDFs
   stay unresolved)
4. **proximity classification** — finance/promo wording only counts when it qualifies the
   value itself or the record's own label; page-level "ราคาเริ่มต้น / starting from" scope
   wording qualifies the page's prices; footnote marker `**` + "Starting price" note →
   `MSRP_STARTING`
5. **longest label owns the price** — when grades of one model match the same published
   record (Premium vs Premium Luxury, Supra vs Supra Track Edition) only the longest match
   takes the price; the shorter grade stays `UNVERIFIED_PRICE`
6. **next-record value** — a label block followed by a money-only block binds (existing
   `price_row_boundary` semantics), still never converting the type

## 4. Price pass result (counts computed from JSON)

| bucket | count | of 488 |
|---|---:|---:|
| accepted variants targeted | 488 | 100.0% |
| **exact MSRP verified** (EXACT_VARIANT + official_verified + CURRENT) | **246** | 50.4% |
| exact non-MSRP price only (MSRP_STARTING / reference tier) | 28 | 5.7% |
| price bound to the record (any type) | 274 | 56.1% |
| UNVERIFIED_PRICE (source gap) | 214 | 43.9% |
| blocked OEM accepted variants | 0 | 0.0% |
| blocked/source-gap bucket | 214 | 43.9% |

- price_type distribution: {"EXACT_VARIANT": 247, "MSRP_STARTING": 27}
- evidence origin: {"row": 188, "jsonld": 86} (HTML/PDF record blocks vs structured JSON-LD nodes)
- trust tier: {"official_verified": 273, "reference": 1} · currentness: {"CURRENT": 273, "NOT_A_CURRENTNESS_SOURCE": 1}
- **no price invention: 0** · **third-party promoted to MSRP: 0** · identity ledger unchanged: **488** (`changed_by_p110: false`)

## 5. Per-OEM coverage

| OEM | targets | bound | exact MSRP | non-MSRP | unverified | coverage | price types |
|---|---:|---:|---:|---:|---:|---:|---|
| Jaguar | 1 | 1 | 1 | 0 | 0 | 100.0% | {"EXACT_VARIANT": 1} |
| Land Rover | 11 | 11 | 10 | 1 | 0 | 100.0% | {"EXACT_VARIANT": 10, "MSRP_STARTING": 1} |
| Toyota | 110 | 108 | 104 | 4 | 2 | 98.2% | {"EXACT_VARIANT": 104, "MSRP_STARTING": 4} |
| BMW | 73 | 67 | 67 | 0 | 6 | 91.8% | {"EXACT_VARIANT": 67} |
| Suzuki | 11 | 10 | 10 | 0 | 1 | 90.9% | {"EXACT_VARIANT": 10} |
| Mitsubishi | 24 | 20 | 20 | 0 | 4 | 83.3% | {"EXACT_VARIANT": 20} |
| Lexus | 38 | 27 | 6 | 21 | 11 | 71.1% | {"EXACT_VARIANT": 6, "MSRP_STARTING": 21} |
| Mazda | 22 | 14 | 14 | 0 | 8 | 63.6% | {"EXACT_VARIANT": 14} |
| Kia | 6 | 3 | 3 | 0 | 3 | 50.0% | {"EXACT_VARIANT": 3} |
| Subaru | 2 | 1 | 1 | 0 | 1 | 50.0% | {"EXACT_VARIANT": 1} |
| Honda | 35 | 8 | 7 | 1 | 27 | 22.9% | {"EXACT_VARIANT": 7, "MSRP_STARTING": 1} |
| Changan | 5 | 1 | 1 | 0 | 4 | 20.0% | {"EXACT_VARIANT": 1} |
| MG | 8 | 1 | 0 | 1 | 7 | 12.5% | {"EXACT_VARIANT": 1} |
| Nissan | 25 | 2 | 2 | 0 | 23 | 8.0% | {"EXACT_VARIANT": 2} |
| Deepal | 4 | 0 | 0 | 0 | 4 | 0.0% | {} |
| GWM | 22 | 0 | 0 | 0 | 22 | 0.0% | {} |
| Isuzu | 7 | 0 | 0 | 0 | 7 | 0.0% | {} |
| MINI | 15 | 0 | 0 | 0 | 15 | 0.0% | {} |
| Porsche | 69 | 0 | 0 | 0 | 69 | 0.0% | {} |

## 6. Source ceiling for the 214 UNVERIFIED_PRICE rows (evidence-backed)

- **130** — no captured first-party record publishes this exact grade label next to a price (label wording differs, or the grade is not priced on any captured page)
- **80** — the exact grade is published on a captured first-party page but that record does not carry a price (model-level or range price only, never promoted to a grade price)
- **2** — captured file has no readable text layer (image-only pdf or unreadable encoding)
- **2** — the cited artifact is not in the fixture set (dropped during an earlier acquisition wave)

Heaviest gaps: Porsche 69, Honda 27, Nissan 23, GWM 22, MINI 15, Lexus 11, Mazda 8, Isuzu 7.
Reasons are structural, not procedural: Porsche configurator pages publish only a model-level
JSON-LD price (grade prices are JS-rendered); GWM model pages carry no price text; Honda/Mazda/Nissan
grade rows exist without a price on the same record; MINI publishes only a finance/promotion price
sheet (base64 PDF) whose grade wording differs by dash style; Isuzu publishes Thai grade names while
the frozen identity labels are English. Per the no-loop rule these are reported as a ceiling, not
closed by guessing.

## 7. Audit surface

```text
scripts/p110_price_pass.py                      driver (local only: no network, pdftotext only)
audit/coverage/p110_price_target_plan.json      488 targets, 19 OEMs, 13 blocked OEMs (written first)
audit/coverage/p110_price_evidence.json         274 rows: value/type/locator/excerpt/provenance
audit/coverage/p110_price_evidence.json.prov.json  sha256 + derivation inputs (DERIVED_PHASE1_AUDIT)
audit/coverage/p110_price_capture_log.json      new_captures 0, results []
audit/coverage/p110_price_reconciliation.json   totals + per-OEM + 214 categorised UNVERIFIED rows
audit/coverage/p110_final_result.json           KPI + gates + identity ledger frozen 488
tests/test_p110_price_pass.py                   targeted tests (red-before for every parser defect)
audit/daily-runs/20260928-p110-targeted.log     targeted run
audit/daily-runs/20260928-p110-combined.log     combined wave suites
audit/daily-runs/20260928-p110-pytest.log       full pytest (once)
```

## 8. Red-before / green-after defects fixed in this wave

| # | defect | red proof |
|---|---|---|
| 1 | minified nav block bound promo prices to grades | `test_minified_nav_block_is_not_a_price_binding` |
| 2 | promo/finance wording in another block reclassified an MSRP row | `test_promo_wording_in_another_block_does_not_reclassify_an_msrp_row` |
| 3 | start-price rows did not bind at all | `test_starting_price_is_msrp_starting` |
| 4 | structured JSON-LD prices ignored (99 Toyota nodes) | `test_structured_jsonld_price_binds_the_same_record` |
| 5 | page-level "starting from" banner not applied to grade prices | `test_introductory_price_banner_marks_the_grade_price_as_starting` |
| 6 | ordinary grade cards with links rejected by nav rule | `test_grade_card_with_a_few_links_still_binds` |
| 7 | shorter grade borrowed the longer grade's price (13 shared groups → 1 legitimate) | `test_longest_grade_label_owns_the_published_price` |

logs: `/tmp/p110_redbefore.log` (6 failed / 15 passed), `/tmp/p110_redbefore2.log` (3 failed),
`/tmp/p110_redbefore3.log` (1 failed), `/tmp/p110_green.log` (2 passed after fixes).

## 9. Gates (run once at the end of the wave)

- targeted `tests/test_p110_price_pass.py` → **26 passed in 126.21s**
  (`audit/daily-runs/20260928-p110-targeted.log`) — includes the deterministic rerun:
  driver executed twice, all four JSON outputs identical except `generated_at`, and the
  watched P108/P109 accepted artifacts byte-identical before/after
- combined wave suites (P110 26 + P109 22 + P107 18 + P106 20 + P105 50 + P104 267 +
  P103 51 + P102 40) → **494 passed in 447.34s**
  (`audit/daily-runs/20260928-p110-combined.log`)
- full pytest (once) → **913 passed, 1 error in 939.07s**
  (`audit/daily-runs/20260928-p110-pytest.log`); the only error is the unchanged
  pre-existing `_OPENROUTER_ALLOWED_MODEL` collection failure in
  `tests/test_generation_config_boundary.py` (last touched `eef8c49`), collected with
  `--continue-on-collection-errors`. An earlier full run was cut by an 880 s wrapper
  timeout at ~86 % and was re-run with a 1500 s budget — same command, one complete pass.
- `tests/test_spec_coverage_plan.py` → 8 passed (plan regenerated and consistent)
- vitest → **488 passed / 2 skipped (42 files)** · `npx tsc --noEmit` → **rc0** ·
  `npx prisma validate` → **valid**
- credential scan over the changed/new scope (`git status --porcelain -uall`, strict
  patterns, base64/PDF payloads out of scope) → **0 hits / 69 files**
- boundaries: `staging_written false · price_pass_staging false · prisma_touched false ·
  production_db_unchanged true · verifier_touched false · identity_counts_changed false ·
  accepted identity ledger frozen 488`

## 10. Honest limits

- coverage stops at 274/488 bound and 246/488 exact MSRP; the remaining 214 are a documented
  source ceiling, never closed by repair loops
- price rows carry P109 currentness pass-through; the price sheets themselves are dated
  ("Effective from 1 August 2026") only where the document says so
- official price coverage still spans 19/32 OEMs; 13 blocked OEMs contribute 0 accepted variants
- enumerator prices already on the ledger (104 `MEDIA_DISCOVERY` rows) are never read by this pass
- identity counts, verifier, Prisma, API, staging and production DB are untouched; PR #3 stays OPEN
- **never claim catalog-complete or price-complete**

