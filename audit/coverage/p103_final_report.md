# P103 final report — first-party catalog coverage expansion

Wave: P103 · Date: 2026-09-27 · Branch: `fix/p1-provenance-gate` · PR #3
Boundary: audit/catalog acquisition + reconciliation only — no staging rows, no
production DB, no schema, no verifier, no config, no price pass.

## What this wave did

Read first, then batched: `identity_matrix_p102.json`,
`p102_final_result.json`, the OEM registry/blocker evidence, the catalog
discovery artifacts, the source-role architecture, the staged first-party rows
and the P100/P101 reports produced `p103_target_plan.json` **before** any
harvest. Targets: 19 reachable OEMs, 13 blocked (never requested), attack order
`Mazda → MG → Subaru → Isuzu → BMW → Toyota → Honda → …`.

Acquisition followed the ladder and reused committed bytes first:
lineup/model pages already in `tests/fixtures/oem-artifacts` carried the grade
layers for Mazda, MG and Isuzu; only Subaru had no reusable grade bytes, so the
official Thai importer model pages (`www.subaru.asia/th/th/{forester,crosstrek,brz}/`)
were captured through `AcquisitionWriter` (3 artifacts + 3 `.prov.json`
sidecars, `p103_capture_log.json`). The registry host `subaru.co.th`
(`BLOCKED_DNS`) was **not** requested; no other blocked host was requested.

## Metrics — before → after

| metric | before (P102) | after (P103) |
|---|---|---|
| first-party confirmed MODEL records | 192 | **194** |
| first-party confirmed VARIANT records | 370 | **401** |
| OEMs with first-party confirmation | 19/32 | **19/32** |
| identity-only records (Phase-1 only) | 842 (383 M / 459 V) | **840 (383 M / 457 V)** |
| candidate models / variants | 572 / 833 | 572 / **862** |
| universe records | 1360 | **1389** (+29) |
| conflicts | 27 (cross 0) | **27 (cross 0)** — unchanged |
| rejected identities | 1927 | 1927 — unchanged |

Per-OEM deltas (all from official publications, see
`identity_matrix_p103.json` → `p103_delta`):

* **Mazda** +22 confirmed variants (22 official grade objects across 5 official
  model pages; each page publishes exactly one `ModelID`, asserted)
* **MG** +5 confirmed variants, +1 confirmed model (`mg_home_page.html`
  publishes `MG3 HYBRID+ รุ่น D/X` and `NEW MGS5 EV PLUS รุ่น D+/V+/X+`;
  the two MG3 grades are exact matches to existing identity-only candidates
  and were **confirmed, not duplicated**)
* **Isuzu** +2 confirmed variants, +1 confirmed model (`มิว-เอ็กซ์ เกรด Active`,
  `ดีแมคซ์ 4 ประตู เกรด L` published in official prose)
* **Subaru** +2 confirmed variants (`BRZ รุ่น BRZ AT`, `Crosstrek 2.0i-S EyeSight`)
* every other OEM delta is 0, recorded explicitly (no counter inflation)

Reconciliation outcomes (`catalog_reconciliation_p103.json`):
`new = 29`, `existing = 2`, `ambiguous = 0`.
The 2 `existing` rows are P102 identity-only candidates confirmed by
publication; the 29 `new` rows each carry the reason they were absent from
P102 (`model_matched_variant_absent`). Every unresolved row keeps an explicit
reason — this wave has none.

## Evidence rules enforced

* `identity_level` is declared at extraction, never inferred from label shape
  (all 26 harvests are grade layers → `VARIANT`).
* Every harvested identity must appear in the artifact bytes it cites; each
  row stores artifact path + sha256 + extraction method + exact source URL.
* Model attribution is per-page (Mazda `ModelID` uniqueness asserted;
  MG titles must be model-prefixed; Subar</think>
* Model attribution is per-page (Mazda `ModelID` uniqueness asserted;
  MG titles must be model-prefixed; Subaru grade comes from the model's own
  official page; Isuzu grade sits in the same published sentence as the model).
* Sibling brands never inherit each other's publication: every P103 source
  carries `manufacturer` and its artifact name, and the test asserts both
  against the record it was attached to.
* Generation/body lines stay separate verbatim (BT-50 `DBL 3.0 XTR HI-RACER 6AT`
  vs `DBL 3.0 XTR 4x4 6AT`; Mazda2 `... SPORTS` vs base).
* No price pass: the new records carry `published_price_thb = None`; published
  prices are kept only as extraction evidence.
* Duplicate suppression: `add_first_party` now ignores a publication it already
  attached to the same identity (red-before `assert 2 == 1` on
  `test_attaching_the_same_publication_twice_is_idempotent`, green-after after
  the one-line guard in `identity_pass.add_first_party`).

## Blockers

No blocker changed. All 13 blocked OEMs keep their exact `access_status` and
blocker evidence (`p103_target_plan.blocked_oems` is a verbatim copy of the
P102 matrix). No blocked host was requested. Smart remains `DEALER_REDIRECT`
in the registry and was **not** retried - this wave only recorded that status.

## Artifacts pushed

```
audit/coverage/p103_target_plan.json                 (plan, written before harvest)
audit/coverage/p103_official_identities.json         (26 identities + provenance)
audit/coverage/catalog_reconciliation_p103.json      (reconciliation result)
audit/coverage/identity_universe_p103.json           (baseline + P103 evidence)
audit/coverage/identity_matrix_p103.json / .md       (per-OEM matrix + deltas)
audit/coverage/p103_final_result.json                (final metrics + gates)
audit/coverage/p103_capture_log.json                 (3 captures, 0 refetches)
audit/coverage/p103_final_report.md                  (this report)
audit/daily-runs/20260927-p103-pytest.log            (reproducible test log)
tests/fixtures/oem-artifacts/subaru_th_model_{forester,crosstrek,brz}.html(.prov.json)
scripts/p103_target_plan.py, scripts/p103_capture_official.py,
scripts/p103_first_party_catalog.py, tests/test_p103_catalog.py
audit/spec-coverage-plan.json                        (+3 new artifacts, additive)
lib/thai_factory/catalog/identity_pass.py            (first_party duplicate guard)
```

## Gates

* `tests/test_p103_catalog.py` - **47 passed** (evidence, provenance,
  reconciliation, separation, idempotence, boundary tests)
* `tests/test_p102_identity_universe.py` - **40 passed** (no P102 regression)
* full pytest - **485 passed, 1 error**: the pre-existing
  `tests/test_generation_config_boundary.py` -> `ImportError: cannot import name
  '_OPENROUTER_ALLOWED_MODEL' from 'thai_factory.extract.ai_extractor'`
  (untouched since `eef8c49`, collected with `--continue-on-collection-errors`)
* `npx vitest run` - 488 passed / 2 skipped · `npx tsc --noEmit` - rc 0 ·
  `npx prisma validate` - rc 0
* credential scan on the changed scope - **0 hits / 22 files**
* production DB, `vehicle_observations.jsonl`, prisma schema, verifier,
  model/provider/config - **untouched** (`staging_written: false`)

## Honest limits

**P103 is complete for this acquisition wave only.** The project catalog is
NOT complete: 13/32 OEMs are still blocked with zero first-party evidence,
Mercedes-Benz still publishes 0 variant candidates, 840 identity-only records
remain Phase-1 evidence only, and reachable OEMs (BMW 49/86, Toyota 98/179,
Honda 31/50, Nissan 23/47 ...) still hold large official variant deficits.
Breadth (19/32) did not change this wave - this wave deepened four OEMs.
