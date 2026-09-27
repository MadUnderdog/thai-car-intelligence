# P104 final report — first-party catalog coverage expansion (breadth pass)

Wave: P104 (incl. REPAIR-2 hardening) · Date: 2026-09-27 ·
Branch: `fix/p1-provenance-gate` · PR #3
Baseline: accepted P103 state (`p103_final_result.json`, `identity_universe_p103.json`).
Boundary: audit/catalog acquisition + reconciliation only — no staging rows, no
production DB, no schema, no verifier, no config, no API, no price pass.

## What this wave did

Wrote `p104_target_plan.json` **before** harvesting: 19 reachable OEMs attacked
horizontally, 13 non-reachable OEMs kept verbatim blocker evidence and were never
requested. Acquisition reused committed bytes only — **no new capture** (rule:
reuse before fetch).

Three extraction methods, now gated by REPAIR-2 (structural context + provenance
verification + generation/body binding):

* `official_lineup_word_boundary` — a published model label found in a **structural
  model context**: heading, model card/lineup link (navigation/footer already
  removed), official JSON payload, official listing iframe JSON or island SSR props.
  The context type and context text are stored with the evidence (**218 rows**).
* `official_grade_table` — grade line attributed to the model anchor above it only
  when the page structure proves the pairing (**13 rows**).
* `official_sentence_grade` — model and grade stated in the same sentence (**3 rows**).

## Deliverable 1 — target plan

`audit/coverage/p104_target_plan.json` (`p104_target_plan/1`): 32 OEMs,
`reachable 19 / blocked 13`, per-row candidate + confirmed counts, deficits,
reusable index artifacts, `targeted_this_wave`; every non-REACHABLE row carries
`blockers` verbatim + `blocker_kind` + policy (no request before `next_retry_at`).

## Deliverable 2 — machine-readable reconciliation / result

| artifact | content |
|---|---|
| `p104_official_identities.json` | 234 identities + evidence (matched text, `context_type`, context text, snippet), sha256, source_url, outcome |
| `catalog_reconciliation_p104.json` | before/after, deltas, outcomes, per-method counts, new identities, ambiguous, skipped artifacts with reasons, **rejected model-context occurrences with reasons** |
| `p104_final_result.json` | before/after, per-OEM deltas, blockers, conflicts/rejects/identity-only, gates, `hardening` block |
| `identity_universe_p104.json` | universe JSON (Phase-1 audit evidence only) |

Harvest: `harvested_identities = 234` → `existing 231 / new 3 / ambiguous 0`.
New identities (3): `Changan NEVO Q05 รุ่น Max`, `Changan NEVO Q05 รุ่น Ultra`,
`GWM Haval H6 PHEV รุ่น ULTRA`, each with the reason it was absent from P103.

**Rejected / skipped evidence, recorded not hidden**

* `rejected_model_context_evidence` — **134** occurrences where a model label exists
  in the page's visible text but in **no** structural model context (menu, footer,
  meta description, stylesheet, prose, quotation), each with artifact + reason.
* `skipped_artifacts_without_provenance` — **6** artifacts with no `.prov.json`:
  `toyota_page`, `bmw_models_page`, `honda_page`, `honda_city_page`, `mazda_page`,
  `isuzu_page`. Never used as evidence.

## Deliverable 3 — updated per-OEM matrix

`audit/coverage/identity_matrix_p104.json` / `.md` — per-OEM identity block, P104
harvest artifacts and `p104_delta`, regenerated from the P104 universe.

### Metrics — P103 baseline → P104 (REPAIR-2 state)

| metric | before (P103) | after (P104 REPAIR-2) |
|---|---|---|
| first-party confirmed MODEL | 194 | **243** (+49) |
| first-party confirmed VARIANT | 401 | **404** (+3) |
| OEMs with first-party confirmation | 19/32 | **19/32** |
| identity-only records (Phase-1 only) | 840 (383 M / 457 V) | **773 (316 M / 457 V)** |
| universe records | 1389 | **1424** (+35) |
| conflicts | 27 (P103 baseline) → 26 in P104 | **26** |
| rejected identities | 1927 | **1927** |

Per-OEM `p104_delta`: **Mitsubishi +9M · MG +8M · Mazda +8M · Kia +6M · Nissan +6M ·
Toyota +5M · Honda +2M · Suzuki +2M · GWM +2M/+1V · Deepal +1M · Changan +2V** ·
BMW / Land Rover / Lexus / MINI / Porsche / Subaru = 0 (recorded explicitly).

Conflicts 27 → 26 happened in the original P104 run (`Toyota Gr Supra` gained a
MARKET_TRUTH MODEL publication; "confirmation outranks a downgrade"; the level-clash
evidence stays in `rejection_reasons`). REPAIR-2 created no conflict change (26 → 26).

### REPAIR-2 effect vs the previously accepted P104 state (`4e5f37e`)

| metric | `4e5f37e` | after REPAIR-2 |
|---|---|---|
| confirmed MODEL | 233 | **243** |
| confirmed VARIANT | 404 | **404** (unchanged) |
| identity-only | 783 (326 M / 457 V) | **773 (316 M / 457 V)** |
| harvested | 261 (258 existing / 3 new) | **234 (231 existing / 3 new)** |
| conflicts / rejected | 26 / 1927 | **26 / 1927** |

**Removed by the hardening (6 identities, all `CONFIRMED_MODEL → IDENTITY_ONLY`)**

| OEM | identity | why the occurrence is not MODEL evidence |
|---|---|---|
| MINI | MINI CONVERTIBLE / Mini 3 Door / Mini Clubman | only inside `md-fsm-navigation__level2` menu buttons (`aria-label`, menu item text) — navigation, not a model card |
| Land Rover | DEFENDER | only in `<meta name="description">` / `og:description` and inside `<style>` CSS |
| Jaguar | F-TYPE | only in anchors to `offers-and-finance/finance-calculator?nameplate=…` — a finance CTA, not a model listing |
| MG | Mg4 Electric | only in promotional `<p>` prose (and its React flight copy); the page's own heading publishes a different label (`NEW MG4 MY2026`) — labels are never guessed to be the same identity |

**Newly proved by the hardening (14, all `IDENTITY_ONLY → CONFIRMED_MODEL`)** —
structures the old whole-page text rule could not see: Mitsubishi ×9
(`ALL NEW MITSUBISHI TRITON`, `Mitsubishi Mirage`, `Mitsubishi Outlander Phev`,
`Mitsubishi Pajero`, `Mitsubishi Triton`, `Mitsubishi Xforce HEV`, `Outlander`,
`Pajero Sport`, `Xpander`) and Toyota ×5 (`Toyota Bz4X`, `Toyota Corolla`,
`Toyota Fortuner`, `Toyota Hilux`, `Toyota Innova`).

## Deliverable 4 — official artifacts and sidecars

No artifact was captured this wave: the ladder stopped at the committed bytes, and
the six sidecar-less files were excluded rather than back-filled (back-filling
provenance without an acquisition event would be fabrication).

* **124** committed artifacts verified through `AcquisitionReader.read` — SHA-256
  recomputed against the capture sidecar, `provenance_state == ACQUISITION_VERIFIED`,
  `source_url` present — **0 mismatches**.
* Verification runs in the extractor (`verify_artifact`), not only in tests: a
  hash mismatch, a non-`ACQUISITION_VERIFIED` sidecar or a missing `https://`
  source URL means the artifact cannot publish evidence.
* Every identity carries `artifact` + `sha256` + `source_url` + `evidence.context_type`.

## Blockers

No blocker cleared and none invented. All 13 non-reachable OEMs keep recorded
evidence verbatim. Smart's retry window had elapsed, so exactly one safe check was
made (default certificate verification, normal browser UA, no header spoofing),
recorded in `audit/coverage/p104_smart_retry_check.json`:

```
https://www.smart.co.th/  301  →  https://www.smartsecurity.in.th/  200
unrelated_domain: true  (body sha256 5351874dcd9c05e…)
```

Because it still redirects to an unrelated domain, the `DEALER_REDIRECT` blocker is
kept unchanged and Smart still has 0 first-party rows.

## Semantic hardening (REPAIR-2) — red-before → green-after

1. **Generation/body binding** — `BoundMatcher` resolves manufacturer + model +
   generation/body + variant in order; a candidate set spanning several
   generation/body records with no source context resolves to **AMBIGUOUS** with an
   explicit reason, never to an arbitrary record. `context=""` is passed explicitly
   because no P104 source carries a generation/body token (all 1389 baseline records
   have `generation == ""`).
2. **Structural model evidence** — `model_contexts()` yields only headings, model
   cards/lineup links (after nav/header/footer/menu/cookie/quotation regions are
   removed) and official structured payloads; a bare visible-text occurrence is
   recorded in `rejected_model_context_evidence` instead of being used.
3. **Provenance** — `verify_artifact()` (reader-bound SHA-256 + state + https URL)
   runs before any evidence is used.

**Red-before:** `12 failed, 3 passed` on the new tests (the three new symbols did
not exist yet). **Green-after:** the whole suite passes, including
`test_same_model_in_two_generations_is_ambiguous_without_context`,
`test_source_generation_context_resolves_exactly_one_generation`,
`test_generation_context_that_no_candidate_carries_is_ambiguous`,
`test_unique_generation_still_confirms`,
`test_variant_resolution_never_crosses_generations`,
`test_mere_visible_text_occurrence_is_not_model_evidence`,
`test_label_only_in_nav_footer_menu_or_quotation_is_not_model_evidence`,
`test_structured_heading_and_card_are_model_evidence`,
`test_json_model_field_is_model_evidence`,
`test_sidecar_hash_mismatch_is_skipped`,
`test_sidecar_state_other_than_acquisition_verified_is_skipped`,
`test_verified_sidecar_passes`,
`test_hardened_evidence_carries_a_structural_locator`,
`test_hardening_rejections_are_recorded_not_silent`,
`test_model_evidence_is_never_produced_from_variant_methods`.

No wholesale "mark everything ambiguous": only 6 confirmations were removed, each
with a named structural reason, and 14 stronger confirmations replaced them.

## Deliverable 5 — test log

`audit/daily-runs/20260927-p104-repair2-pytest.log`

* `tests/test_p104_catalog.py` — **267 tests**
* `tests/test_p103_catalog.py` — **51** · `tests/test_p102_identity_universe.py` — **40**
* full pytest — **756 passed, 1 error**: the pre-existing
  `tests/test_generation_config_boundary.py` collection error
  (`ImportError: cannot import name '_OPENROUTER_ALLOWED_MODEL' from
  'thai_factory.extract.ai_extractor'`, untouched since `eef8c49`, P49), collected
  with `--continue-on-collection-errors` and reported separately
* `npx vitest run` **488 / 2** · `npx tsc --noEmit` **rc0** ·
  `npx prisma validate` **rc0** · credential scan **0 hits / 11 files**
* `staging_written: false` · `price_pass: false` · `prisma_touched: false` ·
  production DB, `vehicle_observations.jsonl`, prisma schema, verifier and
  model/provider/config untouched; every new record `published_price_thb = None`

## Artifacts pushed

```
audit/coverage/p104_target_plan.json                 (plan, written before harvest)
audit/coverage/p104_official_identities.json         (234 identities + evidence)
audit/coverage/catalog_reconciliation_p104.json      (reconciliation + skip + rejected lists)
audit/coverage/identity_universe_p104.json           (baseline + P104 evidence)
audit/coverage/identity_matrix_p104.json / .md       (per-OEM matrix + deltas)
audit/coverage/p104_final_result.json                (final metrics + gates + hardening)
audit/coverage/p104_smart_retry_check.json           (Smart safe retry evidence)
audit/coverage/p104_final_report.md                  (this report)
audit/daily-runs/20260927-p104-repair2-pytest.log    (reproducible test log)
scripts/p104_first_party_breadth.py, tests/test_p104_catalog.py
```

## Honest limits

**P104 / REPAIR-2 is complete for this breadth pass only.** The catalog is NOT
complete: 13/32 OEMs remain blocked with zero first-party evidence, breadth (OEMs
with confirmation) is still 19/32, variant depth barely moved (401 → 404),
Mercedes-Benz still publishes 0 variant candidates, 1483/1927 rejections are
Brazilian FIPE scope, and 773 identity-only records stay Phase-1 evidence only —
never promoted, never guessed.
