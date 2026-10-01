# P113 — Evidence Packet + Acceptance Pass (Phase-1 dry-run, NO promotion)

Report date: 2026-09-28 · Base/audit HEAD: `99c01d53103c3b06d515261dbce4e06515d961ab` (P112) ·
Branch `fix/p1-provenance-gate` · PR #3 OPEN / UNMERGED

## What this pass is (and is not)

ONE bounded build → ONE acceptance run → ONE gate pass, on committed artifacts only.
It builds an `EvidencePacket` per frozen accepted variant and a fail-closed
acceptance verdict over it. It does **not** promote anything: no staging, no
production DB, no Prisma/verifier/API/config changes, no new acquisition, no
AI/inference reconciliation. `promotion_eligible = False` for every packet.

## Read-only audit first (before any code)

* Found an existing acceptance abstraction and **reused it** (not rewritten):
  * `lib/thai_factory/acceptance/evidence_packet.py` — `EvidencePacket`,
    `EvidenceClass`, `AcceptanceDecision`, `EvidenceLocator`, `ArtifactHash`
  * `lib/thai_factory/acceptance/runner.py` — `AcceptanceRunner.evaluate*`
  * `lib/thai_factory/acceptance/ledger.py`, `lib/thai_factory/quality/gates.py`,
    `tests/test_gold_set.py` (10 gold tests), Blueprint #97/#98 (G1–G8)
* No Phase-1 packet layer existed → new audit-only module
  `scripts/p113_evidence_packets.py` (separate from production schema).
* `p113_packet_target_plan.json` written **before** packet build: 488 targets,
  6 machine-readable policies, boundaries (promotion/staging/DB/new-fetch/AI all false).

## Inputs (exact, from committed artifacts — nothing re-chased)

* identity: `identity_universe_p108.json` — **488** CONFIRMED_VARIANT (frozen)
* price: `p111_price_evidence.json` — **299** bound rows
  (269 EXACT_CURRENT_MSRP_VERIFIED / 29 MSRP_STARTING_NOT_EXACT /
  1 EXACT_BINDING_NOT_VERIFIED_CURRENT) + **189** unverified (published reasons)
* spec: `p112_spec_evidence.json` — **1389** rows / **126** variants + 362 gap reasons

## Packet contract

Each packet: manufacturer + exact model + exact variant + TH scope +
generation/body context (from ledger) + per-field observations
(identity / price / spec), each citing source_url + artifact + SHA +
provenance state + locator with re-resolution result + the **existing**
AcceptanceRunner decision. Missing evidence → explicit `field_gaps` with the
published reason — never a value, never `0`/`null` pretending to be data.

Fail-closed quarantine reasons: `artifact_missing`, `sidecar_missing`,
`non_https_source_url`, `sidecar_sha_mismatch`, `sidecar_url_mismatch`,
`expected_sha_mismatch`, `provenance_state_*`, `locator_unresolvable`,
`runner_not_accepted`, `ledger_tuple_mismatch`.

## KPI (from JSON)

| metric | before (baseline) | P113 |
|---|---|---|
| packets built (1 per frozen variant) | 0 | **488 / 488** |
| packets ACCEPTED (usable) | 0 | **417 (85.5%)** |
| packets QUARANTINED (fail-closed) | 0 | **71** |
| packets REJECTED (semantic conflict) | 0 | **0** |
| field observations cited w/ provenance | 0 | **2142** (identity 454 + price 299 + spec 1389) |
| existing-runner evaluated / ACCEPTED | 0 | 2142 / 2142 |
| PROMOTION_ELIGIBLE | — | **0 (all False)** |
| identity ledger | 488 | 488 (`changed_by_p113 false`) |
| price metrics / P112 spec bytes | — | unchanged (byte-identical, sha256 entry==exit) |

Price status distribution across packets: exact current MSRP 269 · starting
not exact 29 · MG binding-not-current 1 · no price evidence 189 · quarantined
price observation 0. Spec: 126 packets cite 1389 field rows, all binding in
{variant_page, grade_named_row, structured_grade_node}, official_verified,
CURRENT, unit present on every numeric field.

## Rejections / quarantine — exact reasons (71 packets, 0 invented)

* **69 × `locator_unresolvable`** — the cited artifact does not re-resolve the
  exact identity names: Porsche 64 (cited `porsche_macan_model_page.html`
  never statically names any 718/911 grade — grades are JS-loaded), GWM 4
  (TANK 300/500 grade codes absent from the captured model pages), BMW 1
  (`M Race Track Package` not in `bmw_price_list.html`).
* **2 × `sidecar_missing`** — Isuzu MU-X Active and Isuzu D Max L: sole
  first-party source `isuzu_page.html` has no `.prov.json` sidecar → provenance
  not intact → fail closed.
* Quarantine never overwrites: failed observations are listed with reasons and
  simply not cited; the packets keep their field gaps explicit.

## Locator matcher defect found and fixed during the build (red→green)

First build over-quarantined identity: the matcher compared raw names, so
`D-Max` vs `D Max`, `HEV-PRO` vs `HEV PRO`, `NX 450h+ F Sport` and
`ALL NEW MITSUBISHI TRITON` (published with different punctuation) failed to
re-resolve even though the names ARE in the artifacts (91 → 86 → 71 after
canon + short-brand-token fixes; two concrete red tests:
`test_identity_locator_matches_published_spelling`). The canonical comparison
folds case/punctuation/spacing only — it does not weaken the rule: the exact
variant must still appear in the SAME artifact.

## Per-OEM packets / accepted / quarantined (accepted sum = 417)

Toyota 110/110/0 · Honda 35/35/0 · Nissan 25/25/0 · Mitsubishi 24/24/0 ·
Mazda 22/22/0 · Lexus 38/38/0 · MINI 15/15/0 · Suzuki 11/11/0 ·
Land Rover 11/11/0 · MG 8/8/0 · Kia 6/6/0 · Changan 5/5/0 ·
Subaru 2/2/2 · Jaguar 1/1/0 · BMW 73/72/1 · GWM 22/18/4 · Isuzu 7/5/2 ·
Porsche 69/5/64

## Gates

Run once at the end (all figures from `audit/daily-runs/20260928-p113-*.log`):

* focused `tests/test_p113_packet_acceptance.py`: **14 passed / 85.86s rc=0**
  (includes a deterministic rerun of the whole pass + byte-identity watch)
* red-before for the matcher defect: `/tmp` + in-suite RED recorded before fix
  (`1 failed` → green after canon fix)
* combined historical gates: **570 passed / 987.33s rc=0**
  (P113 14 + gold 10 + spec-plan 8 + P112 12 + P111 11 + P110 26 + P109 22 +
  P108 21 + P107 18 + P106 20 + P105 50 + P104 267 + P103 51 + P102 40)
* one full pytest: **950 passed, 1 error / 1389.47s rc=1** — the single error is
  the pre-existing `_OPENROUTER_ALLOWED_MODEL` collection error from `eef8c49`
  (reported separately every wave; never fixed as part of these passes)
* vitest: **488 passed / 2 skipped** (42 files) · tsc **rc0** ·
  `prisma validate` **rc0** · credential scan **0 hits**
* deterministic rerun: outputs identical minus `generated_at`/`run_id`,
  watched P111/P112/identity artifacts sha256 unchanged (asserted in-suite)
* post-full-run restore: tracked tree **0** before commit (p110/p111/p112
  sidecars regenerated by their own suites were `git checkout --` restored)
* PR #3 OPEN / UNMERGED; identity ledger 488; no staging/prisma/verifier/API
  changes; price metrics and P112 evidence byte-identical

## Audit surface (committed)

`audit/coverage/p113_packet_target_plan.json` · `p113_evidence_packets.json` ·
`p113_acceptance_result.json` · `p113_rejection_report.json` ·
`p113_final_result.json` · `p113_final_report.md` (this file) ·
`scripts/p113_evidence_packets.py` · `tests/test_p113_packet_acceptance.py` ·
logs `audit/daily-runs/20260928-p113-{combined,pytest}.log`

## Honest limits

* 417/488 = usable packets means *provenance-intact identity + cited fields
  verified* — **not** complete data: 189 variants still have no exact current
  MSRP, 362 still have no spec evidence (P112 ceiling, untouched).
* 71 packets stay quarantined with concrete reasons; fixing them needs a
  locator/source artifact per reason — **not** done here (no repair loop,
  no new acquisition).
* Never declared: catalog-complete / price-complete / spec-complete.
* `promotion_eligible = False` everywhere; next step (controlled promotion of
  ONLY the accepted set) is NOT started automatically.

## Defects disclosed

1. Import surface: `CurrentnessState/...` not re-exported by
   `thai_factory.acceptance.__init__` → import from
   `thai_factory.acceptance.evidence_packet` (no module change).
2. Locator matcher over-strict (see above) — fixed with red-before tests.
3. Test-side key bugs (`reasons` vs `reason`, `canonical_key`, MG row
   identification) — fixed red→green; driver semantics unchanged.
