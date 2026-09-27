# P105 final report — first-party VARIANT / grade depth pass (REPAIR-1)

Wave: P105 · REPAIR-1 · Date: 2026-09-27 · Branch: `fix/p1-provenance-gate` · PR #3
Baseline: accepted P104 REPAIR-2 state (`p104_final_result.json`,
`identity_universe_p104.json`).
Boundary: identity evidence only — no price pass, no staging, no production DB,
no verifier/Prisma/API/config change, no blocked-host request, no new capture.

> **REPAIR-1 supersedes the first P105 report.** The first pass claimed 466
> confirmed variants, but 6 were cross-bound: Deepal E07 rows harvested from
> *other models'* dedicated pages and Mazda CX-3 rows (including a `0%`
> promotion fragment minted as variant `0`) harvested from a CX-30 page. Those
> rows are now **rejected and recorded**. The corrected, published total is
> **404 → 460**. 466 must not be quoted.

## Deliverable 1 — target plan (written before harvesting)

`audit/coverage/p105_target_plan.json` (`p105_target_plan/1`)

* 32 OEM rows, `targeted 18` / `blocked 13`, ranked by variant deficit
  (`variant_deficit 461` = the matrix's candidate−confirmed total).
* `priority_order`: Toyota → BMW → Mazda → MG → Nissan → Mitsubishi → Porsche →
  Honda → Lexus → Kia → GWM → Deepal.
* Every non-REACHABLE row carries its `blockers` verbatim from the accepted
  matrix plus `blocker_kind` and the no-request-before-`next_retry_at` policy;
  `Smart = DEALER_REDIRECT`, never targeted.

## Defect 1 — dedicated-page cross-model contamination (audit head `e33eb45`)

`official_grade_list_row` only required the *published line* to start with the
record's model label, so a page that carries another model's grade rows
confirmed that other model:

| artifact | official URL | claimed model | rows |
|---|---|---|---|
| `deepal_hunter_k50.html` | `…/deepal/hunter-k50-th/` | Deepal E07 | 6 |
| `deepal_s05.html` | `…/deepal/s05-th/` | Deepal E07 | 6 |
| `deepal_s05_reev.html` | `…/deepal/s05-reev-th/` | Deepal E07 | 6 |
| `deepal_s07.html` | `…/deepal/s07-th/` | Deepal E07 | 6 |
| `mazda_car_mazda-cx30-essential.html` | `…/cars/mazda-cx30-essential` | Mazda Cx-3 | 3 |
| `mazda_spec_mazda-cx30-essential.html` | `…/cars/mazda-cx30-essential/spec` | Mazda Cx-3 | 3 |

40 of 41 Deepal rows were E07 text on S05 / S05 REEV / Hunter K50 / S07 pages;
all 7 Mazda rows were `Mazda Cx-3` rows taken from a **CX-30** page, one with
`composite_line = "0%"`.

## Defect 2 — promotion token minted as a variant

`0%` normalized to `0` and matched the unconfirmed enumerator candidate
`Mazda Cx-3 / 0`. Normalization stripping `%` must never create a grade label.

## Repair A — strict `page_model_set()` binding (generalized, no per-brand exception)

`page_model_set(brand, url, models)` classifies every artifact:

* `("dedicated", {models})` — the official URL names exactly these universe
  models, so **only their rows may be confirmed on that page**. A row for
  another model is recorded and dropped (`emit()`), reason
  `cross-page binding: page URL … names … but the row claims … — not model evidence`.
* `("aggregate", ∅)` — price list / model index / news / promotion / brochure /
  home / catalog pages: multi-model, no page restriction, and the *same*
  same-model structural binding (line prefix or grade list) still applies.
* `("unbound", ∅)` — the URL names no universe model (site root, error page):
  structural binding only, exactly as before.

URL normalization is token-boundary based, never a proximity guess:

* **brand-prefix omission** — `…/deepal/s05-th/` binds `Deepal S05` and `s05`
  after the brand token is stripped from both sides;
* **hyphenation + alpha/digit boundaries** — `mazda-cx30-essential` →
  `['mazda','cx','30','essential']`, binds `CX-30` and can **never** bind
  `Mazda Cx-3` (`['cx','3']` is not a prefix of `['cx','30','essential']`);
* **trailing locale / child path segments** — `-th`, `-en`, `th.html` stripped;
  a page-kind child resolves through its parent slug
  (`…/mazda-cx30-essential/spec` → `CX-30`, `…/model/fronx/equipment` →
  `Suzuki Fronx`).

Applied to **every** rule — name|price row, grade list row, page-bound grade
list, bare grade row, grade table row — not to one method.

## Repair B — promotion / numeric label class rule

`grade_label_blocker(line, label)` rejects a row when

* the published line carries a promotion token — `%`, `฿`, `THB`, `บาท`,
  `ผ่อน`, `ดาวน์`, `โปรโมชั่น`, `ดอกเบี้ย`, `APR`, `interest`, `down payment`,
  `ฟรี` (reason `promotion / percent token in the published line (…) — never a
  grade label`), or
* the candidate label carries no letter at all (`^[0-9.]+$` →
  `numeric-only label '0' is not a grade name`).

Class rule, not a whitelist: exactly one universe label is numeric-only
(`Mazda Cx-3 / 0`) and no already-confirmed label is.

## Red-before → green-after

* **red-before** — the seven reviewer cases were written first and run against
  the shipped `e33eb45` code: **10 failed / 30 passed**, including
  `test_s05_page_must_not_confirm_e07`, `test_s05_reev_page_must_not_confirm_e07`,
  `test_hunter_k50_page_must_not_confirm_e07`, `test_s07_page_must_not_confirm_e07`,
  `test_cx30_essential_page_must_not_confirm_cx3`,
  `test_percent_promotion_token_never_becomes_a_variant`,
  `test_numeric_only_label_is_never_a_grade`,
  `test_page_binding_accepts_brand_omission_hyphenation_and_locale`,
  `test_aggregate_and_unbound_pages_are_not_dedicated`,
  `test_cross_page_rejection_is_recorded_with_the_binding`.
* **green-after** — `tests/test_p105_variant_depth.py` **40 passed**. Both
  "must not regress" cases were green in *both* runs:
  `test_dedicated_model_page_still_confirms_its_own_grades` (the E07 pages
  still confirm E07; the `S05 REEV` page still confirms
  `Deepal S05 / Reev`) and `test_multi_model_price_index_still_confirms`
  (Lexus / BMW / Toyota price lists + Isuzu home price page still confirm).
* **determinism preserved**: two consecutive runs produce an identical
  canonicalized evidence list (sha256 `9df4ddc90699f0fe` both runs), and
  `test_row_order_is_deterministic_against_set_iteration_order` still passes.

## Metrics before → after (corrected)

| metric | P104 baseline | P105 REPAIR-1 |
|---|---|---|
| first-party confirmed VARIANT | 404 | **460** (+56) |
| identity-only records (Phase-1 only) | 773 (316 M / 457 V) | **718 (316 M / 402 V)** |
| OEMs with variant confirmation | 19 | **19** |
| universe records | 1424 | **1424** (0 new, 0 ambiguous) |
| conflicts | 26 | **25** |
| rejected identities | 1927 | **1927** |
| harvested rows | — | **141** (`existing 141 / new 0 / ambiguous 0`) |
| first-party confirmed MODEL records | 243 | 255 (counter note below) |

Status changes: **exactly 56, all variant records** — 55
`IDENTITY_ONLY → CONFIRMED_VARIANT` and 1 `CONFLICT → CONFIRMED_VARIANT`
(`Isuzu D Max / X Series`, P102 confirmation-outranks-downgrade; level-clash
evidence kept). **Model-level status changes: 0**; model-only records carrying
first-party evidence **221 → 221** — no model promotion. `No new conflicts.`
The `first_party_confirmed_models` 243 → 255 movement is only the counter's
definition (a model counts as confirmed when *any* of its records carries
first-party evidence); no MODEL-level record, label or status changed.

**Correction vs the first P105 report: 466 → 460 (−6), decomposed not hidden**

| OEM | first report | repaired | reason |
|---|---|---|---|
| Mazda | +4 | **+0** | all 7 rows came from CX-30 pages claiming CX-3 (6 cross-page + 1 promotion) |
| GWM | +3 | **+1** | `models/tank-500` binds `Gwm Tank 500` only; rows claiming sibling model records (`TANK 500 HEV` / `DIESEL`) dropped |

### Per-OEM variant deltas (repaired)

| OEM | confirmed V before → after | delta | rows |
|---|---|---|---|
| BMW | 49 → 66 | **+17** | 25 |
| Lexus | 27 → 36 | **+9** | 42 |
| Toyota | 98 → 105 | **+7** | 17 |
| Isuzu | 2 → 7 | **+5** | 5 |
| Mitsubishi | 19 → 24 | **+5** | 5 |
| Suzuki | 6 → 11 | **+5** | 21 |
| Deepal | 1 → 4 | **+3** | 17 |
| MG | 5 → 8 | **+3** | 7 |
| GWM | 18 → 19 | **+1** | 1 |
| Honda | 31 → 32 | **+1** | 1 |
| **total** | **404 → 460** | **+56** | **141** |

**Targeted OEMs with zero gain, stated explicitly** (deficit unchanged):
**Mazda (33)** — every candidate row sits on a page whose URL binds another
model, or is a promotion fragment; **Nissan (24)**, **Porsche (21)**,
**Kia (15)**, **Subaru (9)**, **MINI (7)**, **Changan (2)**, **Jaguar (2)**.
Blocked non-targeted OEMs (BYD 24, Audi 21, Chevrolet 16, Ford 15, Tesla 9,
Chery 6, Haval 5, NETA 2, Peugeot 2, Volvo 1) were never requested.

## Evidence rules (structural, model-bound, provenance-verified)

| method | rows | binding |
|---|---|---|
| `official_grade_list_row` | 80 | line starts with the record's model label **and** the page lists ≥2 grades of that model **and** the page URL does not bind another model |
| `official_name_price_row` | 33 | composite identity on a name row immediately followed by a published price row (+ the same page binding) |
| `official_page_bound_grade_list` | 15 | page is `dedicated` to the model and lists ≥2 of its candidate grades |
| `official_grade_list_bare_row` | 8 | bare grade row uniquely owned by one model, inside that model's grade list (+ page binding) |
| `official_grade_table_row` | 5 | as above with a published price row next (+ page binding) |

Provenance: `AcquisitionReader.read` recomputes SHA-256 against the capture
sidecar, requires `provenance_state == ACQUISITION_VERIFIED` and an `https`
`source_url`; tests recompute the hash of every cited artifact. Navigation /
footer / meta / style regions are removed before any row is considered.

**Rejected rows — 65, every one recorded with a reason** in
`catalog_reconciliation_p105.json → rejected_rows`:

| class | rows | what was cut |
|---|---|---|
| navigation / footer / meta / style region | 31 | occurrence-only text |
| **cross-page binding** | **30** | 6 × `deepal_s05`, 6 × `deepal_s05_reev`, 6 × `deepal_hunter_k50`, 6 × `deepal_s07`, 3 + 3 × CX-30 pages |
| generic label | 3 | label class that can never be a variant |
| **promotion / percent token** | **1** | `0%` → variant `0` |

## Artifacts pushed

```
scripts/p105_variant_depth.py          (page_model_set, grade_label_blocker, emit)
tests/test_p105_variant_depth.py       (40 tests incl. the 10 repair cases)
audit/coverage/p105_target_plan.json   (plan, written before harvest)
audit/coverage/p105_variant_evidence.json        (141 rows + locators)
audit/coverage/catalog_reconciliation_p105.json  (before/after + rejected_rows 65)
audit/coverage/identity_universe_p105.json       (baseline + P105 evidence)
audit/coverage/identity_matrix_p105.json / .md   (per-OEM matrix + p105_delta)
audit/coverage/p105_final_result.json            (metrics + gates)
audit/coverage/p105_final_report.md              (this report)
audit/daily-runs/20260927-p105-pytest.log        (reproducible test log)
```

No capture this wave: reuse of committed bytes only, zero network requests.
Every cited artifact verifies through the reader (SHA-256 + `ACQUISITION_VERIFIED`
+ https URL). PDF brochures in the fixture set still carry no usable text
layer, so no evidence was taken from them — recorded rather than back-filled.

## Blockers

13 non-reachable OEMs unchanged and never requested: BYD, Audi, Chevrolet, Ford,
Tesla, Chery, Haval, NETA, Peugeot, Volvo, Avance, Mercedes-Benz, Smart.
Smart remains `DEALER_REDIRECT` (last safe check: `301 → smartsecurity.in.th`,
`unrelated_domain: true`), blocker kept verbatim.

## Conflicts / rejects

* conflicts **26 → 25** (only the Isuzu D Max / X Series resolution above; 0 new)
* rejected identities **1927 → 1927**
* identity-only **773 → 718** (models unchanged at 316)

## Tests and gates

* `tests/test_p105_variant_depth.py` **40** (includes the 10 REPAIR-1 cases
  and the 2 must-not-regress cases) · `tests/test_p104_catalog.py` **267** ·
  `tests/test_p103_catalog.py` **51** · `tests/test_p102_identity_universe.py` **40**
* full pytest with `--continue-on-collection-errors`: the pre-existing
  `tests/test_generation_config_boundary.py` collection error
  (`ImportError: cannot import name '_OPENROUTER_ALLOWED_MODEL' from
  'thai_factory.extract.ai_extractor'`, untouched since `eef8c49`) is the only
  error and is reported separately
* `npx vitest run` / `npx tsc --noEmit` / `npx prisma validate` / credential
  scan on the changed scope
* `staging_written: false` · `price_pass: false` · `prisma_touched: false` ·
  `production_db_unchanged: true` · every record's `published_price_thb`
  byte-identical to the P104 baseline

## Honest limits

**P105 REPAIR-1 is complete for this variant-depth pass only — the catalog is
NOT complete.** Remaining variant deficit is **405** (461 − 56), official
breadth is still 19/32 OEMs, 13 OEMs stay blocked, Mercedes-Benz has 0 variant
candidates, 1483/1927 rejections are Brazilian FIPE scope, and **402**
identity-only variant records remain Phase-1 evidence — never promoted to the
accepted set, never priced, never staged.
