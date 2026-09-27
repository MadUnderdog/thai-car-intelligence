# P105 final report — first-party VARIANT / grade depth pass

Wave: P105 · Date: 2026-09-27 · Branch: `fix/p1-provenance-gate` · PR #3
Baseline: accepted P104 REPAIR-2 state (`p104_final_result.json`,
`identity_universe_p104.json`).
Boundary: identity evidence only — no price pass, no staging, no production DB,
no verifier/Prisma/API/config change, no blocked-host request.

## Deliverable 1 — target plan (written before harvesting)

`audit/coverage/p105_target_plan.json` (`p105_target_plan/1`)

* 32 OEM rows, `targeted 18` / `blocked 13`, ranked by variant deficit
  (`variant_deficit 461` = the matrix's candidate−confirmed total).
* `priority_order`: Toyota → BMW → Mazda → MG → Nissan → Mitsubishi → Porsche →
  Honda → Lexus → Kia → GWM → Deepal.
* Every non-REACHABLE row carries its `blockers` verbatim from the accepted
  matrix plus `blocker_kind` and the no-request-before-`next_retry_at` policy;
  `Smart = DEALER_REDIRECT`, never targeted.

## Deliverable 2 — machine-readable reconciliation / result

| artifact | content |
|---|---|
| `p105_variant_evidence.json` | 168 variant rows: model, variant, exact published label, artifact, sha256, source_url, extraction method, locator (line + structure), reconciliation outcome/reason |
| `catalog_reconciliation_p105.json` | before/after, per-OEM before/after, outcomes, methods, new/ambiguous lists (both empty), **rejected_rows with reasons** |
| `p105_final_result.json` | before/after totals, per-OEM deltas, identity-only, conflicts, rejected, blockers, gates |
| `identity_universe_p105.json` | universe JSON (Phase-1 audit evidence only) |
| `identity_matrix_p105.json` / `.md` | per-OEM matrix with `p105_delta` |

Harvest: `harvested_rows = 168` → `existing 168 / new 0 / ambiguous 0` — no
identity was invented and nothing had to be left ambiguous.

**Evidence rules (all structural, model-bound, provenance-verified)**

| method | rows | binding |
|---|---|---|
| `official_grade_list_row` | 104 | published line starts with the record's model label and the page lists ≥2 grades of that same model |
| `official_name_price_row` | 33 | composite identity on a name row immediately followed by a published price row |
| `official_grade_list_bare_row` | 15 | bare grade row whose label is owned by exactly one model and appears in that model's grade list on the page |
| `official_page_bound_grade_list` | 11 | official URL slug names the model and the page lists ≥2 of its grades |
| `official_grade_table_row` | 5 | bare grade row followed by a published price inside the model's grade list |

Before any row is used: `AcquisitionReader.read` recomputes SHA-256 against the
capture sidecar, `provenance_state == ACQUISITION_VERIFIED`, `source_url` is
`https://`. Navigation / footer / meta / style regions are removed first.

**Rejected evidence (recorded, not hidden):** 36 rows — 33 occur only in
navigation / footer / meta / style regions, 3 are generic labels. Listed in
`catalog_reconciliation_p105.json → rejected_rows`.

## Deliverable 3 — metrics before → after

| metric | P104 baseline | P105 |
|---|---|---|
| first-party confirmed VARIANT | 404 | **466** (+62) |
| identity-only records (Phase-1 only) | 773 (316 M / 457 V) | **712 (316 M / 396 V)** |
| OEMs with variant confirmation | 19 | **19** |
| universe records | 1424 | **1424** (0 new, 0 ambiguous) |
| conflicts | 26 | **25** |
| rejected identities | 1927 | **1927** |
| first-party confirmed MODEL records | 243 | 255 (see note) |

**Status changes: exactly 62, all variant records** — 61
`IDENTITY_ONLY → CONFIRMED_VARIANT` and 1 `CONFLICT → CONFIRMED_VARIANT`
(`Isuzu D Max / X Series`, confirmed by the official Isuzu price page's
`X-SERIES` grade row; P102's "confirmation outranks a downgrade" rule, level-clash
evidence kept in the record). **No new conflicts.** Model-level records changed
status **0** times, and model-only records carrying first-party evidence are
**221 → 221** — this pass promoted no model.

> The `first_party_confirmed_models` metric moved 243 → 255 only because that
> counter scores a model as confirmed when *any* of its records carries
> first-party evidence; 12 models gained a confirmed variant. No MODEL-level
> record, label or status changed.

### Per-OEM variant deltas

| OEM | confirmed V before → after | delta | P105 rows |
|---|---|---|---|
| BMW | 49 → 66 | **+17** | 25 |
| Lexus | 27 → 36 | **+9** | 42 |
| Toyota | 98 → 105 | **+7** | 17 |
| Isuzu | 2 → 7 | **+5** | 5 |
| Mitsubishi | 19 → 24 | **+5** | 5 |
| Suzuki | 6 → 11 | **+5** | 15 |
| Mazda | 22 → 26 | **+4** | 7 |
| Deepal | 1 → 4 | **+3** | 41 |
| GWM | 18 → 21 | **+3** | 3 |
| MG | 5 → 8 | **+3** | 7 |
| Honda | 31 → 32 | **+1** | 1 |
| **total** | **404 → 466** | **+62** | 168 |

**Zero-gain priority OEMs, stated explicitly** (deficit unchanged): **Nissan**
(24 — its grade rows were already confirmed in P104, and the remaining
candidates appear only as bare powertrain/nav tokens), **Porsche** (21 — the
committed pages publish model filter entries, not grade rows bound to those
candidates), **Kia** (15 — no grade rows in the committed bytes), **Subaru**
(9), **MINI** (7), **Changan** (2), **Jaguar** (2); **Land Rover** already at
11/11. No evidence was stretched to fill them.

## Semantic defect found mid-pass — determinism (red-before → green-after)

The extractor picked a model for a shared prefix from an unordered `set`, so
the accepted counts depended on Python's hash seed:

* **red-before** (pre-fix code, same inputs, `PYTHONHASHSEED` 0 / 42 / 7):
  confirmed variants **457 / 463 / 460**, rows **138 / 163 / 170**; two plain
  reruns also disagreed (450 vs 455).
* **fix:** deterministic ordering everywhere a tie is broken — models sorted,
  `(prefix, model)` pairs sorted by `(-len(prefix), model, prefix)`, candidate
  labels sorted before one is chosen.
* **green-after:** three consecutive runs return **466 confirmed variants /
  168 rows**, and the evidence list is element-wise identical between runs
  (only `generated_at` differs). Regression test:
  `test_row_order_is_deterministic_against_set_iteration_order`.

## Deliverable 4 — official evidence artifacts and sidecars

No capture this wave: **reuse of committed bytes only** (the ladder stopped at
what the repository already holds — no network request, no acquisition event).
Every one of the 168 rows cites an artifact whose `.prov.json` verifies through
the reader (SHA-256 + `ACQUISITION_VERIFIED` + https URL); tests recompute the
hash for each cited artifact. PDF brochures in the fixture set carry **no text
layer** (`pdftotext` returns nothing / "not a PDF file"), so no evidence was
taken from them — recorded here rather than back-filled.

## Blockers

13 non-reachable OEMs unchanged and never requested: BYD, Audi, Chevrolet, Ford,
Tesla, Chery, Haval, NETA, Peugeot, Volvo, Avance, Mercedes-Benz, Smart.
Smart remains `DEALER_REDIRECT` (last safe check: `301 → smartsecurity.in.th`,
`unrelated_domain: true`), blocker kept verbatim.

## Conflicts / rejects

* conflicts **26 → 25** (only the Isuzu D Max / X Series resolution above; 0 new)
* rejected identities **1927 → 1927**
* identity-only **773 → 712** (models unchanged at 316)

## Deliverable 5 — tests and gates

* `tests/test_p105_variant_depth.py` — plan/blockers, model binding per method,
  navigation/generic refusal, provenance re-hash, status-change scope, count
  reconciliation, matrix/report agreement, determinism, no price/staging
* `tests/test_p104_catalog.py` 267 · `tests/test_p103_catalog.py` 51 ·
  `tests/test_p102_identity_universe.py` 40 — all re-run, unchanged
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

## Artifacts pushed

```
audit/coverage/p105_target_plan.json              (plan, written before harvest)
audit/coverage/p105_variant_evidence.json         (168 rows + locators)
audit/coverage/catalog_reconciliation_p105.json   (before/after + rejected_rows)
audit/coverage/identity_universe_p105.json        (baseline + P105 evidence)
audit/coverage/identity_matrix_p105.json / .md    (per-OEM matrix + p105_delta)
audit/coverage/p105_final_result.json             (metrics + gates)
audit/coverage/p105_final_report.md               (this report)
audit/daily-runs/20260927-p105-pytest.log         (reproducible test log)
scripts/p105_variant_depth.py, tests/test_p105_variant_depth.py
```

## Honest limits

**P105 is complete for this variant-depth pass only — the catalog is NOT
complete.** Remaining variant deficit is **399** (461 − 62), official breadth
is still 19/32 OEMs, 13 OEMs stay blocked, Mercedes-Benz still has 0 variant
candidates, 1483/1927 rejections are Brazilian FIPE scope, and **396**
identity-only variant records remain Phase-1 evidence — never promoted to the
accepted set, never priced, never staged.
