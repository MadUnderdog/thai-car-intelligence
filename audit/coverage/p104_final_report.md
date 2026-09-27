# P104 final report — first-party catalog coverage expansion (breadth pass)

Wave: P104 · Date: 2026-09-27 · Branch: `fix/p1-provenance-gate` · PR #3
Baseline: accepted P103 state (`p103_final_result.json`, `identity_universe_p103.json`).
Boundary: audit/catalog acquisition + reconciliation only — no staging rows, no
production DB, no schema, no verifier, no config, no API, no price pass.

## What this wave did

Read state first (P103 final result, P103 matrix, P103 target plan, PR head,
per-OEM deficits, reusable official artifacts), then wrote
`p104_target_plan.json` **before** harvesting: 19 reachable OEMs attacked
horizontally, 13 non-reachable OEMs kept verbatim blocker evidence and were
never requested.

Acquisition reused committed bytes only — **no new capture this wave** (rule:
reuse before fetch). Two structural rules produced official identity evidence:

* `official_lineup_word_boundary` — a published model label found on that
  OEM's official index/lineup page, with the exact matched text and a context
  snippet stored as the locator (245 rows).
* `official_grade_table` — a grade line attributed to the model anchor above
  it only when the page structure proves the pairing: `grade | price` table
  rows, or a transmission token (`CVT`, `6MT`, `7AT`, …) followed by published
  feature prose (13 rows).
* `official_sentence_grade` — the page states the model in the same sentence
  as the grade (`CHANGAN NEVO Q05 … รุ่น Max และรุ่น Ultra`, `H6 PHEV รุ่น ULTRA`)
  (3 rows).

## Metrics — before → after

| metric | before (P103) | after (P104) |
|---|---|---|
| first-party confirmed MODEL records | 194 | **233** |
| first-party confirmed VARIANT records | 401 | **404** |
| OEMs with first-party confirmation | 19/32 | **19/32** |
| identity-only records (Phase-1 only) | 840 (383 M / 457 V) | **783 (326 M / 457 V)** |
| universe records | 1389 | **1426** (+37) |
| conflicts | 27 | **26** |
| rejected identities | 1927 | 1927 |

Harvest: `harvested_identities = 261` → `existing 258 / new 3 / ambiguous 0`.
The 3 genuinely new identities are `Changan NEVO Q05 รุ่น Max`,
`Changan NEVO Q05 รุ่น Ultra`, `GWM Haval H6 PHEV รุ่น ULTRA`, each with the
reason it was absent from P103.

Per-OEM deltas (full list in `p104_final_result.per_oem_deltas`,
matrix `identity_matrix_p104.json → p104_delta`):

* **MG +9 models**, **Mazda +8**, **Kia +6**, **Nissan +6**, **GWM +2 models / +1 variant**,
  **Honda +2**, **MINI +2**, **Suzuki +2**, **Deepal +1**, **Toyota +1**
* **Changan +2 variants** (NEVO Q05 Max / Ultra)
* BMW, Porsche, Isuzu: identity-only models confirmed (−3 / −1 / −1) without
  changing their already-confirmed model counts
* every other OEM delta is 0 and recorded explicitly

**Conflicts 27 → 26 — explained, not hidden:** `Toyota Gr Supra` moved from
CONFLICT to CONFIRMED_MODEL because this wave attached a MARKET_TRUTH MODEL
publication for that exact identity; the P102 rule "confirmation outranks a
downgrade" applies, and the original level-clash evidence stays in the
record's `rejection_reasons`. No new conflicts were created.

## Semantic defect found and fixed mid-wave (red-before → green-after)

Six committed artifacts have no AcquisitionWriter sidecar, so their
`source_url` was empty. Using them silently produced publication keys like
`Toyota Thailand Official <>`, which inflated level-clash evidence:

* **before the fix:** `level_clash_keys 26 → 29`, `level_clash_records 52 → 58`
  (new keys GR YARIS, GR COROLLA, GR SUPRA, COASTER, X SERIES, TAYCAN, CAYENNE
  were all keyed by an empty URL)
* **fix:** `usable()` fails closed — an artifact without a sidecar carrying a
  real `https://` source URL is never used as evidence, and each skip is
  recorded with its reason
* **after:** `level_clash_keys = 26`, `level_clash_records = 52` — identical to
  the accepted P103 state; 101 unusable rows dropped from the harvest
  (362 → 261) while the confirmed counts were unchanged

Skipped (never used as evidence): `toyota_page.html`, `bmw_models_page.html`,
`honda_page.html`, `honda_city_page.html`, `mazda_page.html`,
`isuzu_page.html` — reason `no .prov.json source_url — not used as evidence`.

## Blockers

No blocker cleared and none invented. All 13 non-reachable OEMs keep their
recorded evidence verbatim (`p104_target_plan.oems[].blockers` is copied from
the accepted matrix). Smart's retry window had elapsed, so exactly one safe
check was made — `requests.get` with default certificate verification and a
normal browser UA, no header spoofing — and recorded in
`audit/coverage/p104_smart_retry_check.json`:

```
https://www.smart.co.th/  301  →  https://www.smartsecurity.in.th/  200
unrelated_domain: true  (body sha256 5351874dcd9c05e…)
```

Because it still redirects to an unrelated domain, the `DEALER_REDIRECT`
blocker is kept unchanged and Smart still has 0 first-party rows.

## Artifacts pushed

```
audit/coverage/p104_target_plan.json                 (plan, written before harvest)
audit/coverage/p104_official_identities.json         (261 identities + evidence)
audit/coverage/catalog_reconciliation_p104.json      (reconciliation + skip list)
audit/coverage/identity_universe_p104.json           (baseline + P104 evidence)
audit/coverage/identity_matrix_p104.json / .md       (per-OEM matrix + deltas)
audit/coverage/p104_final_result.json                (final metrics + gates)
audit/coverage/p104_smart_retry_check.json           (Smart safe retry evidence)
audit/coverage/p104_final_report.md                  (this report)
audit/daily-runs/20260927-p104-pytest.log            (reproducible test log)
scripts/p104_first_party_breadth.py, tests/test_p104_catalog.py
```

No new artifact/sidecar was captured this wave: the ladder stopped at the
reusable bytes, and the six sidecar-less files were excluded rather than
back-filled (back-filling provenance without an acquisition event would be
fabrication).

## Gates

* `tests/test_p104_catalog.py` — **279 tests** (evidence in artifact bytes,
  sidecar + source URL, fail-closed provenance rule, generic-label refusal,
  sibling separation, reconciliation counts, no-duplicate, idempotence,
  no staging/price, blockers verbatim, matrix deltas)
* `tests/test_p103_catalog.py` — 51 passed · `tests/test_p102_identity_universe.py` — 40 passed
* full pytest — pre-existing `tests/test_generation_config_boundary.py`
  `ImportError: cannot import name '_OPENROUTER_ALLOWED_MODEL' from
  'thai_factory.extract.ai_extractor'` remains the only collection error
  (untouched since `eef8c49`, collected with `--continue-on-collection-errors`)
* `npx vitest run` / `npx tsc --noEmit` / `npx prisma validate` / credential
  scan on the changed scope — see the numbers in the delivery message
* production DB, `vehicle_observations.jsonl`, prisma schema, verifier,
  model/provider/config — untouched (`staging_written: false`,
  `price_pass: false`, every new record `published_price_thb = None`)

## Honest limits

**P104 is complete for this breadth pass only.** The catalog is NOT complete:
13/32 OEMs remain blocked with zero first-party evidence, breadth
(OEMs with confirmation) is still 19/32, variant depth is nearly untouched
this round (401 → 404), Mercedes-Benz still publishes 0 variant candidates,
and 783 identity-only records stay Phase-1 evidence only.
