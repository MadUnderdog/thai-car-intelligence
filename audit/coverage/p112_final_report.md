# P112 — Specification Evidence Pass (Phase-1 audit layer over the frozen 488)

Date: 2026-09-28 · Branch `fix/p1-provenance-gate` · PR #3
Scope: field-level, variant-bound OFFICIAL specification evidence for the
frozen accepted VARIANT ledger (488). Prices untouched, identity untouched.

## A. Pre-harvest audit (state at HEAD before this wave)

- HEAD at entry: `a49f13676d452ae4b9c94bf619b21f4d15ece949` (P111 price pass,
  accepted) · PR #3 OPEN/UNMERGED · tracked tree clean.
- Existing spec-related surface: `scripts/generate_spec_coverage_plan.py` +
  `audit/spec-coverage-plan.json` are TEST-coverage artifacts, not spec data;
  no prior spec-evidence artifact/test/report existed (`p1xx_spec_*` = none).
- Prisma carries the eventual target shape read-only (`VariantSpec`,
  `DimensionsSpec`, `VariantSpecExtra`) — mirrored as Phase-1 field keys,
  schema NOT touched.
- Committed official corpus: 497 fixtures, 487 with
  `ACQUISITION_VERIFIED` sidecars; P109 classifier applied live (its
  inventory file stays byte-identical): CURRENT 403, HISTORICAL 10,
  NOT_A_CURRENTNESS_SOURCE 53, UNDETERMINED press 13 (of sidecar fixtures).
- Machine-readable plan written BEFORE harvesting:
  `p112_spec_target_plan.json` — 488/488 variants, 15-field dictionary,
  priority P1 variant-scoped 27 / P2 model-scoped 156 / P3 305,
  boundaries: identity 488 frozen, no price changes, no AI reconciliation.

## B. ONE inventory → ONE acquisition batch → ONE extraction pass → validation

Inventory (`p112_spec_source_inventory.json`): 290 entries = 274 reuse
candidates (committed spec/brochure/model artifacts) + 2 documented endpoint
fetches (Toyota official `car-series` list + `web-init`) + 14 ceiling rows
for P3 brands with no documented first-party spec endpoint. Blocked OEMs
never enter discovery (asserted). Toyota series codes are evidence-bound:
34 codes seen in its own list response, 31 matched accepted models by exact
compact equality (then a guarded containment fallback), all fetched inside
the SAME batch — no URL-by-URL selection.

Batch (`p112_spec_capture_log.json`): new_captures 30, reused 2 (idempotent
re-run key = host+path+query), failed 1 (`web-init` HTTP 405, recorded as a
failure, never bypassed). Every capture = AcquisitionWriter + `.prov.json`
+ SHA + HTTPS; JSON payloads kept raw. Programmatic expansion block records
one entry (list_url, 34 seen, 31 matched pairs, codes fetched).

Extraction (`scripts/p112_spec_pass.py`, local-only — no fetch code):
- Same-record contract: every emitted field appears in ONE published record
  (table row / text line / structured payload item) that carries
  manufacturer + model + exact variant + TH scope. Bindings:
  `variant_page` 62 · `grade_named_row` 220 · `structured_grade_node` 1107.
- Grade binding is exact-normalized equality only: `Premium` never matches
  `Premium Luxury`/`HEV Premium`; `e:HEV E` never matches `e:HEV ES`
  (red-first synthetic tests).
- Unit rule: the published record must contain the unit token for the field
  (latin or thai spelling: mm/มม., PS/แรงม้า, Nm/นิวตัน, kWh/กิโลวัตต์-ชั่วโมง,
  km/กิโลเมตร, ที่นั่ง/seats …). No unit → refused, never inferred.
- Combo L×W×H cells resolve once to three fields; bore/stroke/deck cells are
  never body dimensions; `น้ำหนัก…บรรทุก` payload ≠ curb weight; kW(PS)
  payloads take the PS inside the parentheses, PS(hp) payloads take the
  leading number.
- Only `ACQUISITION_VERIFIED` sidecars whose SHA matches the payload, on
  P109-CURRENT official sources, enter evidence. Sidecar/payload mismatch or
  non-current source → skipped (fail-closed).

## C. KPI (values from the JSON artifacts)

```
                                          P111   P112    delta
variants w/ field-level spec evidence       0     126    +126   ← baseline 0
spec evidence rows                          0    1389    +1389
  from new captures (Toyota API)           —     1128 rows / 100 variants
  from committed fixtures                  —      261 rows /  30 variants
variants WITHOUT evidence                488     362    −126   ← source ceiling
price metrics modified                   none    none     0
identity ledger                           488     488  frozen (changed_by_p112 false)
```

Field coverage (rows per field, sum = 1389):
`length_mm 273 · height_mm 194 · width_mm 178 · seats 159 · wheelbase_mm 134
· torque_nm 126 · power_ps 104 · displacement_cc 91 · drivetrain 65 ·
ground_clearance_mm 58 · range_km 6 · warranty 1` (battery_kwh, charging_kw
= 0 → see ceiling).

Per-OEM (accepted / with evidence / rows):
- Toyota 110 / 100 / 1135 — grade payloads bind exact grade titles
- Lexus 38 / 17 / 230 — grade-scoped pages
- BMW 73 / 2 / 4 · Deepal 4 / 2 / 13 · GWM 22 / 2 / 4 · Isuzu 7 / 1 / 1
  · MG 8 / 1 / 1 · Porsche 69 / 1 / 1
- ZERO: Changan 5, Honda 35, Jaguar 1, Kia 6, Land Rover 11, MINI 15,
  Mazda 22, Mitsubishi 24, Nissan 25, Subaru 2, Suzuki 11

## D. Source ceiling — 362 variants (classified, no repair loop)

100% classified `model_level_context`: their in-scope official artifacts
publish spec rows only at model level (or in JS-rendered grade UIs), and
none names the exact grade in the same static record — model-level-only
claims are never promoted to variant evidence. Battery/charging fields
publish without a unit-bound record or only inside configurator payloads
outside this batch. Every gap row carries the reason string. This is ONE
bounded pass: no URL-by-URL chase, no second acquisition, NO P113 implied
by the remaining rows.

## E. Boundaries (all asserted by tests)

Identity ledger stays exactly 488 (`changed_by_p112 false`); no price metric
modified (`price_pass_artifacts_unchanged`, watched price artifacts hashed
before/after the pass); Prisma/verifier/API/model-config/staging/production
DB untouched; blocked OEMs (13) contribute zero rows; AI reconciliation
never used; no value invented (unit-or-refuse, unknown stays unknown).

## F. Regression (red-before)

`tests/test_p112_spec_pass.py` —12 tests; RED before implementation
(`/tmp/p112_redbefore.log`: collection error, module absent) → GREEN after.

## G. Gates

(run outputs in `audit/daily-runs/20260928-p112-*.log`)

- targeted P112: 12 passed / 87.38s (rc=0) · red-before log:
  `/tmp/p112_redbefore.log` (module absent)
- spec coverage plan regen + its suite: 8 passed / 42.82s (rc=0)
- combined historical (P112 12 + P111 11 + P110 26 + P109 22 + P107 18 +
  P106 20 + P105 50 + P104 267 + P103 51 + P102 40):
  _517 passed / 752.81s (rc=0)_
- full pytest (once, `--continue-on-collection-errors`):
  _936 passed, 1 error / 1285.80s_, `full rc=1` — the only error is the
  pre-existing `_OPENROUTER_ALLOWED_MODEL` collection error from `eef8c49`
  (`tests/test_generation_config_boundary.py`), reported separately as always
- vitest: 488 passed / 2 skipped (42 files) · tsc: rc0 · prisma: schema valid
- credential scan: 0 hits over every changed/new file (final count at commit)
- deterministic rerun: inside the focused suite (driver rerun byte-equal
  modulo generated_at; watched price artifacts byte-identical) — after the
  full run the evidence still holds 1389 rows / 126 variants

## H. Honest limits

126/488 variants — 488 identity rows remain frozen and price metrics remain
as P111 left them. Official spec evidence is thin outside Toyota/Lexus
because first-party Thai pages publish grade-level spec UIs client-side or
model-level-only. Nothing here is catalog-complete or spec-complete; 13
non-REACHABLE OEMs remain out of scope entirely.

## I. Next remaining work (reported, NOT started)

Per the project sequence: evidence packets → acceptance → controlled
promotion of verified data → search/retrieval/RAG → public car/compare/
search UX → community/admin → scheduled refresh/deployment/release.
The 362 spec-gap rows are input to a future source-ceiling review, not a
standing order to continue.
