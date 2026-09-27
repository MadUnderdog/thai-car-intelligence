# P105 final report — first-party VARIANT / grade depth pass (REPAIR-2)

Wave: P105 · REPAIR-2 · Date: 2026-09-27 · Branch: `fix/p1-provenance-gate` · PR #3
Baseline: accepted P104 REPAIR-2 state (`p104_final_result.json`,
`identity_universe_p104.json`), rehydrated and re-run end to end — no count in
this report was patched by hand.
Boundary: identity evidence only — no price pass, no staging, no production DB,
no verifier/Prisma/API/config change, no blocked-host request, no new capture.

> **REPAIR-2 supersedes REPAIR-1.** The first pass published 466 (6 rows
> cross-bound → REPAIR-1: 460); the classifier gap below is fixed and the pass
> was **rerun from the accepted P104 baseline**. The published total is now
> **404 → 462**. Neither 466 nor 460 is final.

## Deliverable 1 — target plan (written before harvesting)

`audit/coverage/p105_target_plan.json` (`p105_target_plan/1`): 32 OEM rows,
`targeted 18` / `blocked 13`, ranked by variant deficit (`461`); priority
Toyota → BMW → Mazda → MG → Nissan → Mitsubishi → Porsche → Honda → Lexus → Kia
→ GWM → Deepal; every non-REACHABLE row keeps its blockers verbatim and is
never requested (`Smart = DEALER_REDIRECT`).

## Defect REPAIR-1 — dedicated-page cross-model contamination (head `e33eb45`)

`official_grade_list_row` only required the published line to start with the
record's model label, so a page carrying another model's grade rows confirmed
that other model: 40 of 41 Deepal rows were E07 text sitting on S05 / S05 REEV
/ Hunter K50 / S07 pages (6 rows each), and all 7 Mazda rows were `Mazda Cx-3`
rows taken from a **CX-30** page — one with `composite_line = "0%"`, which
normalization minted as the variant `0`.

## Defect REPAIR-2 — `/model(s)/<slug>` mis-classified as aggregate (head `ffb8fa0`)

`page_model_set()` ran `AGGREGATE_WORDS` over **last + parent** path segments,
so a parent of `model` / `models` made the page `aggregate` and bypassed the
strict binding REPAIR-1 had just added:

| official URL | REPAIR-1 kind | rows resting on plain structural binding |
|---|---|---|
| `https://www.gwm.co.th/th/models/tank-500-diesel` | `aggregate` | 1 |
| `https://www.suzuki.co.th/model/fronx` | `aggregate` | 3 |
| `https://www.suzuki.co.th/model/xl7` | `aggregate` | 5 |

## Repair A — generalized classifier (no GWM/Suzuki special case)

Classification order in `page_model_set(brand, url, models)`:

1. **terminal route → `aggregate`**: the *last* segment itself is the index /
   price / article route — `/news`, `/price-list`, `/pricelist`,
   `/all-models-price`, `/brochure`, `/promotion`, bare `/models` or `/model`.
2. **article container parent → `aggregate`** — proven multi-model:
   `/news/<slug>`, `/util/promotion/<slug>` (parent ∈ news, press, stories,
   article(s), discover, events, promotion(s), promo, util, topics, archive(s),
   blog, media, download(s), tools).
3. **locale strip, then page-kind strip** (`-th`, `th.html`; `/spec`,
   `/equipment`, `/features`, `/gallery`, `/detail`, `/overview`) — a child
   route binds through its **parent model slug**.
4. **model match → `dedicated`, else `unbound`.** `model` / `models` / `cars`
   in the parent are *containers*: stripped as structure, never an aggregate
   verdict. Matching stays token-boundary based — brand-prefix omission,
   hyphenation with alpha/digit split, prefix at a token boundary only, no
   proximity guess.

`accept_row()` (extracted from the loop closure so it is unit-testable)
enforces `dedicated` on **every** rule: a row for another model is written to
`rejected_rows` as
`cross-page binding: page URL … names … but the row claims … — not model evidence`
and dropped.

**Classification diff across the 131 verified artifacts (REPAIR-1 → REPAIR-2):**
18 changes — `aggregate` 68 → **51**, `dedicated` 27 → **43**, `unbound` 36 →
**37**: 13 GWM `…/models/<slug>` pages and 3 Suzuki `/model/<slug>` pages became
`dedicated`; `/pap/_thailand_/models/macan` → `dedicated {Macan, Porsche Macan}`;
`/range-rover/overview` → `dedicated {RANGE ROVER}` (was `unbound`); and
`…/models/sahar(-diesel)` → `unbound` because the slug matches no universe
record — those two keep structural binding only, exactly as before.

## Repair B — promotion / numeric label class rule (REPAIR-1, kept)

`grade_label_blocker(line, label)` refuses a row whose published line carries
`%` `฿` `THB` `บาท` `ผ่อน` `ดาวน์` `โปรโมชั่น` `ดอกเบี้ย` `APR` `interest`
`down payment` `ฟรี`, or whose candidate label carries no letter at all
(`^[0-9.]+$`). A class rule, not a whitelist: the only numeric-only label in
the universe is `Mazda Cx-3 / 0`, and no confirmed label is numeric.

## Red-before → green-after

* **red-before (REPAIR-2)** — the eight reviewer cases written first and run
  against shipped head `ffb8fa0`: **8 failed / 42 passed**
  (`test_models_tank500_url_is_dedicated_and_binds_only_tank500`,
  `test_models_tank300_url_is_dedicated_and_binds_only_tank300`,
  `test_models_tank500_diesel_url_binds_only_tank500_records`,
  `test_model_fronx_url_is_dedicated_and_binds_only_fronx`,
  `test_model_xl7_url_is_dedicated_and_binds_only_xl7`,
  `test_model_xl7_equipment_inherits_the_xl7_binding`,
  `test_wrong_model_row_on_a_container_url_is_rejected`,
  `test_every_container_url_evidence_row_is_bound_to_that_url_model`).
  Log: `/tmp/p105_repair2_redbefore.log`.
* **red-before (REPAIR-1)** — the seven earlier cases against head `e33eb45`:
  **10 failed / 30 passed**.
* **green-after** — `tests/test_p105_variant_depth.py` **50 passed**, and the
  guards that must hold on *both* sides pass on both sides:
  `test_index_and_article_routes_remain_aggregate`,
  `test_root_and_unknown_urls_stay_unbound`,
  `test_dedicated_model_page_still_confirms_its_own_grades`,
  `test_multi_model_price_index_still_confirms`.
* **determinism** — two consecutive reruns: identical canonicalized evidence
  list (sha256 `b2d320b1e7b15f2f` both runs) and identical counts
  (`[404, 462]`, 143 rows).

## What the rerun changed (measured, never patched)

Rows **141 → 143**: 5 added, 3 removed.

* **removed (3)** — `suzuki_model_fronx.html` bare-row attributions of
  `Suzuki Fronx / GL, GLX, GLX PLUS`; the same three identities were
  **re-proved** as `official_page_bound_grade_list` on their own dedicated
  page. No identity lost, no status reverted.
* **added (5)** — `official_page_bound_grade_list`: `Gwm Tank 300 / PRO`,
  `Gwm Tank 500 / PRO` (**new identities**) and the three Fronx grades
  (re-attributed).
* **cross-page withdrawals inside this URL family: 0.** Every pre-existing row
  on `/model(s)/<slug>` already claimed exactly the model its URL names —
  asserted by
  `test_every_container_url_evidence_row_is_bound_to_that_url_model`
  (non-vacuous: the family carries evidence). The 30 cross-page rejections from
  REPAIR-1 (Deepal ×24, CX-30 ×6) are unchanged.
* **rejected rows 65 → 67** — navigation-only occurrences 31 → 33 because rule C
  now also runs on the newly dedicated pages and records what it refuses.
* no classification moved in a loosening direction: every `dedicated → unbound`
  case is a slug that matches no universe model and keeps structural binding.

## Metrics before → after (final for this wave)

| metric | P104 baseline | P105 REPAIR-2 |
|---|---|---|
| first-party confirmed VARIANT | 404 | **462** (+58) |
| identity-only records (Phase-1 only) | 773 (316 M / 457 V) | **716 (316 M / 400 V)** |
| OEMs with variant confirmation | 19 | **19** |
| universe records | 1424 | **1424** (0 new, 0 ambiguous) |
| conflicts | 26 | **25** |
| rejected identities | 1927 | **1927** |
| harvested rows | — | **143** (`existing 143 / new 0 / ambiguous 0`) |
| first-party confirmed MODEL records | 243 | 255 (counter note below) |

Status changes: **exactly 58, all variant records** — 57
`IDENTITY_ONLY → CONFIRMED_VARIANT` + 1 `CONFLICT → CONFIRMED_VARIANT`
(`Isuzu D Max / X Series`). **Model-level status changes: 0**; model-only
records carrying first-party evidence **221 → 221** — no model promotion.
`first_party_confirmed_models` 243 → 255 is the counter's definition only (a
model scores when *any* of its records carries first-party evidence); no
MODEL-level record, label or status changed. **No new conflicts.**

**Wave ledger: 466 (first report, cross-bound) → 460 (REPAIR-1) → 462
(REPAIR-2 rerun).**

| OEM | P104 → P105 R2 | delta | rows |
|---|---|---|---|
| BMW | 49 → 66 | **+17** | 25 |
| Lexus | 27 → 36 | **+9** | 42 |
| Toyota | 98 → 105 | **+7** | 17 |
| Isuzu | 2 → 7 | **+5** | 5 |
| Mitsubishi | 19 → 24 | **+5** | 5 |
| Suzuki | 6 → 11 | **+5** | 21 |
| GWM | 18 → 21 | **+3** | 3 |
| Deepal | 1 → 4 | **+3** | 17 |
| MG | 5 → 8 | **+3** | 7 |
| Honda | 31 → 32 | **+1** | 1 |
| **total** | **404 → 462** | **+58** | **143** |

GWM moved +1 → **+3**: `/models/tank-300` and `/models/tank-500` are now
dedicated pages whose own grade rows can be proved page-bound.

**Targeted OEMs with zero gain, stated explicitly** (deficit unchanged):
**Mazda (33)** — every candidate row sits on a page whose URL binds another
model, or is a promotion fragment; **Nissan (24)**, **Porsche (21)**, **Kia
(15)**, **Subaru (9)**, **MINI (7)**, **Changan (2)**, **Jaguar (2)**. Blocked
non-targeted OEMs (BYD 24, Audi 21, Chevrolet 16, Ford 15, Tesla 9, Chery 6,
Haval 5, NETA 2, Peugeot 2, Volvo 1) were never requested.

## Evidence rules (structural, model-bound, provenance-verified)

| method | rows | binding |
|---|---|---|
| `official_grade_list_row` | 80 | line starts with the record's model label **and** the page lists ≥2 grades of that model **and** the page URL does not bind another model |
| `official_name_price_row` | 33 | composite identity on a name row immediately followed by a published price row (+ the same page binding) |
| `official_page_bound_grade_list` | 20 | page is `dedicated` to the model (URL-bound) and lists ≥2 of its candidate grades |
| `official_grade_list_bare_row` | 5 | bare grade row uniquely owned by one model inside that model's grade list (+ page binding) |
| `official_grade_table_row` | 5 | as above with a published price row next (+ page binding) |

Provenance: `AcquisitionReader.read` recomputes SHA-256 against the capture
sidecar, requires `provenance_state == ACQUISITION_VERIFIED` and an `https`
`source_url`; tests recompute the hash of every cited artifact. Navigation /
footer / meta / style regions are removed before any row is considered.

**Rejected rows — 67, every one recorded with a reason** in
`catalog_reconciliation_p105.json → rejected_rows`:

| class | rows | what was cut |
|---|---|---|
| navigation / footer / meta / style region | 33 | occurrence-only text |
| **cross-page binding** | **30** | 6 × `deepal_s05`, 6 × `deepal_s05_reev`, 6 × `deepal_hunter_k50`, 6 × `deepal_s07`, 3 + 3 × CX-30 pages |
| generic label | 3 | label class that can never be a variant |
| **promotion / percent token** | **1** | `0%` → variant `0` |

## Artifacts pushed

```
scripts/p105_variant_depth.py          (TERMINAL_AGGREGATE / ARTICLE_CONTAINER /
                                        MODEL_CONTAINER classifier, accept_row,
                                        grade_label_blocker)
tests/test_p105_variant_depth.py       (50 tests: 10 REPAIR-1 + 10 REPAIR-2 cases)
audit/coverage/p105_target_plan.json   (plan, written before harvest)
audit/coverage/p105_variant_evidence.json        (143 rows + locators)
audit/coverage/catalog_reconciliation_p105.json  (before/after + rejected_rows 67)
audit/coverage/identity_universe_p105.json       (P104 baseline + P105 evidence)
audit/coverage/identity_matrix_p105.json / .md   (per-OEM matrix + p105_delta)
audit/coverage/p105_final_result.json            (metrics + gates)
audit/coverage/p105_final_report.md              (this report)
audit/daily-runs/20260927-p105-pytest.log        (reproducible test log)
```

No capture this wave: reuse of committed bytes only, zero network requests.
Every cited artifact verifies through the reader (SHA-256 + `ACQUISITION_VERIFIED`
+ https URL). PDF brochures still carry no usable text layer — recorded, never
back-filled.

## Blockers

13 non-reachable OEMs unchanged and never requested: BYD, Audi, Chevrolet, Ford,
Tesla, Chery, Haval, NETA, Peugeot, Volvo, Avance, Mercedes-Benz, Smart.
Smart remains `DEALER_REDIRECT` (last safe check: `301 → smartsecurity.in.th`,
`unrelated_domain: true`), blocker kept verbatim, no bypass.

## Conflicts / rejects

* conflicts **26 → 25** (only the Isuzu D Max / X Series resolution; 0 new)
* rejected identities **1927 → 1927**
* identity-only **773 → 716** (models unchanged at 316)

## Tests and gates

* `tests/test_p105_variant_depth.py` **50** (10 REPAIR-1 + 10 REPAIR-2 cases
  plus the must-not-regress guards) · `tests/test_p104_catalog.py` **267** ·
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

**P105 REPAIR-2 is complete for this variant-depth pass only — the catalog is
NOT complete.** Remaining variant deficit is **403** (461 − 58), official
breadth is still 19/32 OEMs, 13 OEMs stay blocked, Mercedes-Benz has 0 variant
candidates, 1483/1927 rejections are Brazilian FIPE scope, and **400**
identity-only variant records remain Phase-1 evidence — never promoted to the
accepted set, never priced, never staged.
