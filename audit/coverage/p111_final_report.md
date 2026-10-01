# P111 — ONE bounded price fix + source-expansion pass

Date: 2026-09-28 · Session: `p111_price_pass_20260928` · Branch: `fix/p1-provenance-gate` · PR #3 (OPEN, unmerged)

P111 does exactly the two jobs the P110 audit asked for, in one bounded pass:

* **A — fix the one known price semantic edge**: the MG EP / PLUS row binds an exact
  price from a *reference* source that is `NOT_A_CURRENTNESS_SOURCE`; it must be
  classified as a non-current binding, never counted as verified current official MSRP.
* **B — batch price-source expansion** for the 214 `UNVERIFIED_PRICE` rows left by P110:
  one discovery inventory → one acquisition batch → the same strict harvest.

No identity/verifier/Prisma/API/production/staging changes. The identity ledger stays
frozen at 488 confirmed variants. No repair loop: whatever remains UNVERIFIED is
reported as an evidence-backed source ceiling.

---

## 1. Success KPI (headline)

| metric | P110 | P111 | delta |
| --- | ---: | ---: | ---: |
| accepted variants targeted | 488 | 488 | 0 (frozen ledger) |
| **exact current official MSRP verified** | **246** | **269** | **+23** |
| price bound to the same published record | 274 | 299 | +25 |
| `UNVERIFIED_PRICE` (remaining source ceiling) | 214 | 189 | −25 |
| MG reference row ambiguously counted as verified MSRP | 1 ambiguity | **0** | fixed |
| prices invented | 0 | 0 | 0 |
| third-party promoted to MSRP | 0 | 0 | 0 |
| identity ledger (confirmed variants) | 488 | 488 | unchanged |

Exact MSRP rose **above 246** as the KPI requires; the remaining 189 are reported,
reason-categorised and not chased.

## 2. A — the MG semantic edge, fixed

The audit row (evidence preserved verbatim):

```
MG / Mg Ep / PLUS   ฿771,000   price_type=EXACT_VARIANT   trust_tier=reference
artifact=mg_home_page.html   currentness=NOT_A_CURRENTNESS_SOURCE (utility page)
```

Fix: every bound row now carries an explicit, mutually exclusive `msrp_status`
(+ a reason string), derived from price_type × trust tier × currentness:

* `EXACT_CURRENT_MSRP_VERIFIED` — EXACT_VARIANT + official_verified + CURRENT → **269**
* `EXACT_BINDING_NOT_VERIFIED_CURRENT` — exact binding preserved but *not* a verified
  current MSRP → **1** (the MG row; reason text: `trust_tier=reference,
  currentness=NOT_A_CURRENTNESS_SOURCE (utility page); excluded from
  exact_msrp_verified and reported separately`)
* `MSRP_STARTING_NOT_EXACT` — starting-from figures → **29**
* `NON_MSRP_TYPE` — promotional/finance/range → **0**

Invariant asserted by test: `269 + 1 + 29 + 0 = 299 = price_bound = len(evidence rows)`.
`msrp_status_distribution` sums to `price_bound`. The MG price/value/evidence/locator
are unchanged — only classification and reporting changed. Focused regression
`tests/test_p111_price_fix.py` was written red-first (9 failed / 2 passed before the
pass existed; red logs `/tmp/p111_redbefore.log`, `/tmp/p111_redbefore2.log`) and is
green after the pass.

## 3. B — source expansion: one inventory, one batch

### Discovery (`p111_price_source_inventory.json`)

* Priority = P110 unverified count (Porsche 69 … Suzuki 1); blocked OEMs never appear
  (test asserts).
* Channels: stored P108 sitemap/search pools + fresh robots/sitemap-index fetches
  (MG, Isuzu, Changan, Toyota, Porsche `pap/_thailand_/Sitemap.smap`, GWM, Nissan …) +
  `known_official_pattern` entries (Honda has no sitemap — its slugs came from the
  `/en/` navigation, each probed HTTP 200 before recording).
* **342 candidates → 138 selected** (per-OEM cap 14, global cap 140, price sources first),
  de-duplicated by normalized (host, locale-stripped path) against every prior capture.

### Acquisition (`p111_price_capture_log.json`)

* **138 attempted in ONE batch → 127 captured**, every capture = `AcquisitionWriter` +
  `.prov.json` sidecar + SHA256; PDFs converted with `pdftotext -layout` (sanitizer can
  never corrupt payloads); politeness 0.4 s; blocked-OEM token guard pre-request.
* Failures (11, all evidence-recorded): 2 blocked-token hits (Kia image assets whose URL
  contains "smart" — fail-closed false positive, never requested), 5 HTTP 302 loop
  (Mitsubishi `/triton` sub-pages), 4 HTTP 404 (Porsche sustainability stubs, Subaru BRZ).
* `new_captures = 127`; the http:// BMW legacy URLs redirected to https (all 127 sidecars
  are https).

### Classification of the new captures

`family_of()` / `currentness()` from `scripts/p109_current_market.py` are reused verbatim;
the p109 inventory artifact itself is byte-untouched:

* currentness: CURRENT 106 / NOT_A_CURRENTNESS_SOURCE 17 / UNDETERMINED 3 / HISTORICAL 1
* family: model_lineup 50, official_page 40, utility 11, promotion 6, spec_page 6,
  press 5, price_document 4, configurator 3, brochure_spec 2

### Scan-scope rule (how new captures enter the harvest)

New captures are attached to a record only when the page is *about that model*:
segment-prefix URL match (`/en/crv` ↔ "CR-V e:HEV"), a model-scoped composite label
(`"<model> <grade>"`) in the normalised page text, or a model-index page
(`/en/models`). During the pass the attach rule was tightened twice after row-level
diff review caught cross-model contamination (bare grade labels such as "e:HEV E" are
shared across Accord/CR-V/HR-V, and bare model mentions live in the site navigation of
every page). The contaminated rows were removed before the reported numbers — disclosed
here rather than hidden; final rows are each bound on their own model's page (checker:
every p111-sourced row's URL matches its model).

## 4. Result detail

Buckets: `269 / 1 / 29 / 0` (mutually exclusive) · price_type distribution:
`EXACT_VARIANT 270, MSRP_STARTING 29` · `price_bound 299 + unverified 189 = 488`.

New/changed bound rows vs P110 (25 + 1 canonical change):

* **Honda +18** (BR-V 4, CR-V 4, City Hatchback 4, HR-V 3, STEP WGN 1, WR-V 2) — each
  from its own model page (`honda.co.th/en/<model>`), unverified 27 → 9.
* **Porsche +5** — 718 derivative pages carry `"<derivative> = <n> THB"` JSON-LD
  (Boxster 6,390,000 / Boxster Style Edition 6,990,000 / Boxster GTS 4.0 9,990,000 /
  Cayman GTS 4.0 9,790,000 / Cayman GT4 RS 16,990,000); unverified 69 → 64.
* **Toyota +2** — Yaris ATIV page publishes `ราคาเริ่มต้น 599,000 / 569,000` →
  `MSRP_STARTING_NOT_EXACT` (starting wording, never EXACT); unverified 2 → 0 (100%).
* **Canonical change (disclosed)**: identity row `Toyota Yaris / Ativ` moved from
  ฿599,000 (`toyota_pricelist_page.html`, JSON-LD) to ฿569,000
  (`toyota_p111_yarisativ.html`, dedicated model page) — both official + current,
  type stays EXACT_VARIANT; the old evidence row is still recorded in P110's artifact.

Per-OEM coverage (P110 → P111: bound / exact / unverified):

```
Honda        8→26   7→25   27→9    (74.3%)     Porsche     0→5    0→5   69→64  (7.2%)
Toyota     108→110 104→104  2→0   (100%)       BMW         67→67  67→67   6→6  (91.8%)
Mitsubishi  20→20  20→20     4→4   (83.3%)     Suzuki      10→10  10→10   1→1  (90.9%)
Mazda       14→14  14→14     8→8   (63.6%)     Lexus       27→27   6→6   11→11 (71.1%)
Land Rover  11→11  10→10     0→0  (100%)       Jaguar       1→1    1→1    0→0  (100%)
Kia          3→3    3→3      3→3   (50.0%)     Subaru       1→1    1→1    1→1  (50.0%)
Nissan       2→2    2→2     23→23   (8.0%)     MG           1→1    0→0    7→7  (12.5%)
GWM          0→0    0→0     22→22   (0%)       MINI         0→0    0→0   15→15  (0%)
Isuzu        0→0    0→0      7→7    (0%)       Changan      1→1    1→1    4→4  (20.0%)
Deepal       0→0    0→0      4→4    (0%)       Toyota 100%, Jaguar/Land Rover 100%
```

## 5. Remaining source ceiling — 189 rows, every one reason-categorised

| reason | count |
| --- | ---: |
| no captured first-party record publishes this exact grade label next to a price (label wording differs, or grade not priced on any captured page) | 106 |
| the grade is published on a captured first-party page but that record carries no grade price (model-level/range only — never promoted) | 79 |
| captured file has no readable text layer (image-only PDF) | 2 |
| cited artifact dropped in an earlier acquisition wave | 2 |

Zero-yield OEMs after their batch share (GWM, MINI, Isuzu, Nissan, MG, Mazda-page gaps,
Changan/Deepal): their current pages expose model-level or range prices, JS-rendered
configurator payloads without grade prices, or Thai labels that differ from the accepted
identity labels. This is the source ceiling — **no repair loop was created to chase the
number**, and no model-level price was spread to a grade.

Blocked OEMs (13: BYD, Audi, Chevrolet, Ford, Tesla, Chery, Haval, NETA, Peugeot, Volvo,
Avance, Mercedes-Benz, Smart) were never discovered, requested or priced; they hold 0
accepted variants, so `blocked_oem_accepted_variants = 0`.

## 6. Boundaries (asserted by tests)

* identity ledger: `confirmed_variants 488`, `changed_by_p111 false`; P108/P110
  artifacts hash-identical across the deterministic rerun.
* `staging_written false / price_pass_staging false / prisma_touched false /
  production_db_unchanged true / verifier_touched false / identity_counts_changed false`.
* no network inside tests (the pass and the tests run over captured fixtures; the only
  subprocess permitted in tests is `pdftotext` for local PDFs).
* prices_invented 0 · third_party_promoted_to_msrp 0 · every `EXACT_CURRENT_MSRP_VERIFIED`
  row is MARKET_TRUTH + official_verified + CURRENT + EXACT_VARIANT (asserted).

## 7. Gates (run once at the end)

| gate | result |
| --- | --- |
| focused `tests/test_p111_price_fix.py` | **11 passed / 164.84s** (`20260928-p111-targeted.log`) |
| combined P111+P110+P109+P107+P106+P105+P104+P103+P102 | **505 passed / 654.10s** (11+26+22+18+20+50+267+51+40; `20260928-p111-combined.log`) |
| full pytest once | **924 passed, 1 error / 1187.48s** (`20260928-p111-pytest.log`; the single error is the unchanged, pre-existing `_OPENROUTER_ALLOWED_MODEL` ImportError from `eef8c49`, collected via `--continue-on-collection-errors`) |
| spec coverage plan | regenerated (`scripts/generate_spec_coverage_plan.py`) → `test_spec_coverage_plan` **8 passed** |
| vitest / tsc / prisma validate / credential scan | **vitest 488 passed / 2 skipped (42 files)** · **tsc rc0** · **prisma valid** · **credential scan 0 hits / 268 changed-new files** (wave files only; probe/dry-run leftovers excluded) |
| deterministic rerun | inside `test_deterministic_rerun_and_frozen_inputs` (passed in targeted, combined and full runs) |
| identity ledger / staging / DB | 488 / `staging_written false` / production DB unchanged |
| P106/P110 snapshot discipline | P106 test restored its committed artifacts after the rerun; P110 rerun differs only in `generated_at` (verified field-by-field) and its committed bytes were restored before commit |

## 8. Audit surface

`p111_price_source_inventory.json` · `p111_price_capture_log.json` ·
`p111_price_evidence.json` + `.prov.json` (DERIVED_PHASE1_AUDIT) ·
`p111_price_reconciliation.json` · `p111_final_result.json` · this report ·
`scripts/p111_price_sources.py` · `scripts/p111_price_pass.py` ·
`tests/test_p111_price_fix.py` · logs `20260928-p111-{targeted,combined,pytest}.log`.

## 9. Honest limits (must repeat)

* **Not price-complete**: 269/488 exact current official MSRP; 189 rows remain
  UNVERIFIED with reasons; 13 blocked OEMs have no accepted variants and no prices.
* Discovery/first-party access is still 19/32 OEMs.
* One batch only — leftover rows do **not** imply a P112; the pass stops here.
* Never invent a price, never spread a model-level price to a grade, never declare
  price-complete or catalog-complete.
