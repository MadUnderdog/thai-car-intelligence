# P109 — Current Thai-market canonical catalog (one bounded pass)

**wave:** P109 · **P108 frozen as audit history** (`f06aa15423608852358d74a26961794a7fb2e49b`,
never modified) · **date:** 2026-09-28
**principle:** stop chasing the enumerator deficit.  The 377 "deficit" was never
evidence that the Thai market lacks 377 variants — it is the number of
enumerator candidates still lacking first-party grade proof.  This wave measures
*market-current truth* instead, runs **once**, and closes every OEM with an
explicit status.  No repair loop, no follow-up implied.

---

## 1. What was measured

1. **Currentness of every already-captured first-party artifact** (339
   artifacts, no bulk re-fetch): current model/lineup page · current Thai
   configurator / grade selector · current official price/grade document ·
   current brochure/spec/press — separated from historical, discontinued and
   promotional residue by explicit signals: stale/discontinued markers,
   press publication year (≥2025 = current, older = historical, unparseable =
   undated), utility pages (privacy/contact/career/app), promotional/campaign
   pages, and non-official hosts (dealer-redirect / third-party mirror).
2. **Classification of all 1,424 universe records** into
   `CURRENT_CONFIRMED` · `HISTORICAL_OR_STALE_CANDIDATE` ·
   `UNRESOLVED_IDENTITY_ONLY` · `CONFLICT` (+ `CURRENT_UNVERIFIED`, an honest
   fifth bucket for accepted rows whose source is a utility/promo/undated page
   or has no local artifact — currentness neither confirmed nor claimed stale).
   Every record carries its sources and a reason string in
   `p109_candidate_classification.json`.
3. **P109-only semantic evidence tier** (`CURRENT_SEMANTIC_GRADE` /
   `CURRENT_SEMANTIC_MODEL`): a *current* official page that publishes
   model + exact label as a composite line is accepted as Phase-1 evidence even
   when the accepted extractor finds no table row — recorded in
   `p109_current_market_evidence.json`, never written to the accepted ledger,
   the verifier, Prisma, the API or any DB.  Shared generic tokens, ambiguous
   prose, cross-model labels, sibling brands, historical articles and image-only
   scans are still rejected.

**Ledger frozen:** accepted first-party confirmed variants remain **488**
(P108).  `accepted_ledger.changed_by_p109 = false`.

## 2. Source inventory (existing artifacts only — `p109_current_market_inventory.json`)

| artifact currentness | n |
|---|---|
| CURRENT (live official page/document) | **284** |
| HISTORICAL (stale/discontinued marker or press year ≤2024) | 7 |
| UNDETERMINED (press item with no parseable date) | 10 |
| not a currentness source (utility/promo/third-party) | 38 |
| **total** | **339** |

**New captures this wave: 0.**  Workflow step C said to use external discovery
only when a current first-party model/grade source is genuinely missing — after
step B every one of the 19 reachable OEMs already had current first-party
sources (minimum: Jaguar 8, Changan 8, Kia 16, …), so no URL was fetched again.

## 3. Classification result (all 1,424 candidates)

| status | n | meaning |
|---|---|---|
| **CURRENT_CONFIRMED** | **671** | first-party current official source publishes model + exact label (475 variant-level, 196 model-level) |
| CURRENT_UNVERIFIED | 64 | accepted row whose source is utility/promo/undated/absent — not counted current, not claimed stale |
| UNRESOLVED_IDENTITY_ONLY | 664 | enumerator/media candidate without first-party grade proof — **never counted as a missing market variant** |
| CONFLICT | 25 | conflicting identity evidence retained, never resolved by assumption |
| HISTORICAL_OR_STALE_CANDIDATE | 0 | see §5 — no candidate depends solely on a stale source |

Evidence tiers inside the 671: `MARKET_TRUTH_ROW` **645** ·
`CURRENT_SEMANTIC_MODEL` **26** · `CURRENT_SEMANTIC_GRADE` **0**.

## 4. Current Thai market, proven by first-party sources

- **current models published by first-party: 267**
- **current grades/variants published by first-party: 475**
- **first-party-confirmed current rows: 671** (645 accepted rows + 26 P109
  semantic model rows)
- identity-only records untouched: 690 in the universe, of which 26 moved to
  `CURRENT_CONFIRMED` **through the explicit P109 tier with an evidence row**,
  the rest stay unresolved
- conflicts kept: 25

**Top OEMs (current sources · models · grades · confirmed-current · stale · unresolved):**

- Toyota 16 · 52 · 110 · **149** · 0 · 95
- BMW 4 · 52 · 73 · **104** · 0 · 48 (20 conflicts)
- Porsche 13 · 8 · 69 · **74** · 0 · 25
- Honda 16 · 23 · 35 · **53** · 0 · 28
- Lexus 19 · 14 · 38 · **48** · 0 · 29
- Nissan 17 · 20 · 23 · **43** · 0 · 26
- GWM 27 · 18 · 22 · **38** · 0 · 10
- Mitsubishi 14 · 17 · 24 · **33** · 0 · 21
- MINI 10 · 13 · 15 · **26** · 0 · 9
- Mazda 30 · 7 · 22 · **24** · 0 · 38
- Suzuki 20 · 9 · 11 · 20 · 0 · 7 · Land Rover 5 · 4 · 11 · 14 · 0 · 0
- Isuzu 18 · 7 · 7 · 13 · 0 · 16 · Subaru 15 · 6 · 2 · 8 · 0 · 10
- MG 17 · 5 · 2 · 6 · 0 · 42 · Changan 8 · 3 · 3 · 5 · 0 · 2
- Deepal 11 · 7 · 4 · 9 · 0 · 7 · Kia 16 · 1 · 3 · 3 · 0 · 17
- Jaguar 8 · 1 · 1 · 1 · 0 · 16

Full 32-row table with closure status, access status, blockers and
source-gap text: `identity_matrix_p109.json` / `identity_matrix_p109.md`.

## 5. What is historical / stale, and why the answer is 0

- 7 artifacts are provably historical (stale/discontinued markers or press
  year ≤2024: Kia Carnival 2018 press, Nissan 2017 press, Lexus 2021/2024
  events, Toyota 2024 news, a stale Suzuki document) and 10 press artifacts are
  undated.
- Only **7 classification records** reference those URLs — and each of those
  records also has a *current* first-party source, so none of them is stale.
- Promotional residue (5 promo/campaign sources) and utility pages (42) push
  rows into `CURRENT_UNVERIFIED` instead of inflating the current count.
- Therefore `HISTORICAL_OR_STALE_CANDIDATE = 0` is the evidence-backed answer,
  not an omission: no candidate's identity rests solely on a stale source.

## 6. The P109 semantic tier — grade evidence is genuinely absent

Of the **374 unresolved variant candidates**, exactly **1** has a composite
`model + exact label` publication anywhere on a current first-party source:
`Gwm Tank 300 | HEV` — and `HEV` is a shared generic token, which the identity
rules reject.  So `CURRENT_SEMANTIC_GRADE = 0` is a source-availability result:
current official pages either publish those labels as rows the accepted
extractor already consumed (the 645), or do not publish them as model-bound
labels at all.  26 model names, by contrast, do appear on their own current
official pages → `CURRENT_SEMANTIC_MODEL = 26`, each with artifact, sha256 and
currentness reason in `p109_current_market_evidence.json`.

## 7. OEM closure (NO LOOP RULE)

| closure status | OEMs |
|---|---|
| `CLOSED_CURRENT_FIRST_PARTY_AS_PUBLISHED` | **19** — every reachable OEM, classified complete for what its current first-party sources publish |
| `CLOSED_BLOCKED_NO_BYPASS` | **13** — Audi, Avance, BYD, Chery, Chevrolet, Ford, Haval, Mercedes-Benz, NETA, Peugeot, Smart, Tesla, Volvo |
| `CLOSED_SOURCE_GAP_GRADES_NOT_PUBLISHED` | 0 |
| **total closed** | **32 / 32** |

Unresolved candidates still exist (664 — concentrated in Toyota 95, Audi 52,
BMW 48, MG 42, Mazda 38, BYD 35, Mercedes 30 …) but **no OEM stays open because
of them**: source availability has been exhausted for all 19 reachable OEMs,
and 13 OEMs are blocked by policy.

## 8. Gates — run once at the end of the wave

- targeted `tests/test_p109_current_market.py`: **22 passed** (deterministic
  rerun included: two runs, digest compared, artifacts snapshotted/restored)
- full pytest **887 passed, 1 error in 806.69s** →
  `audit/daily-runs/20260928-p109-pytest.log`; the single error is the unchanged
  pre-existing `_OPENROUTER_ALLOWED_MODEL` collection failure
  (`tests/test_generation_config_boundary.py`, last touched `eef8c49`), collected
  with `--continue-on-collection-errors`
- vitest **488 passed / 2 skipped (42 files)** · `tsc --noEmit` **rc 0** ·
  `prisma validate` **valid** · credential scan **0 hits** (strict
  `AKIA…/AIza…/ghp_…/xox…` patterns)
- `staging_written: false` · `price_pass: false` · `prisma_touched: false` ·
  `verifier_touched: false` · `production_db_unchanged: true` ·
  `p104_p103_p102_logic_changed: false` · `accepted_ledger_frozen: true`
- forbidden paths (`prisma/`, `src/`, `package.json`, `Blueprint.md`, `lib/`,
  `audit/data-staging/`) untouched

## 9. Audit surface

`p109_current_market_inventory.json` · `p109_current_market_evidence.json`
(26 rows, sidecars exist for every referenced artifact; **0 new captures**) ·
`p109_candidate_classification.json` (1,424 records with status + reason +
sources) · `identity_matrix_p109.json` / `identity_matrix_p109.md` ·
`p109_final_result.json` · this report · `scripts/p109_current_market.py` ·
`tests/test_p109_current_market.py` · `audit/daily-runs/20260928-p109-pytest.log`

## 10. Honest limits

Market-current truth is now explicit: **267 current models, 475 current grades,
671 first-party-confirmed current rows; 664 unresolved candidates; 25 conflicts;
64 accepted rows whose currentness cannot be verified; 13 OEMs blocked.**
Nothing was promoted: the accepted ledger stays 488, identity-only candidates
were never counted as missing market variants, a price was never read, stored
or verified.  This is one bounded pass with all 32 OEMs closed — **the catalog
is not claimed complete**, and remaining UNRESOLVED records do not by themselves
imply any further wave.
