# P115 — Search / Retrieval / RAG over Promoted Accepted Set

**Status: COMPLETE (awaiting review)** · 2026-09-29 · base `7c2fc2b0b01498248d1cfa2b619a9d7892a6c3e1` · PR #3 OPEN/UNMERGED
Antiloop: ONE read-only preflight → ONE target plan → ONE implementation pass → ONE focused regression cycle per defect → ONE combined/full gate chain → push/report → STOP.

---

## 1. STEP 0 — Read-only preflight (before any edit)

18 files read on base `7c2fc2b` (search/vector/normalize/embeddings/catalog/retreval/gates/routes/tests/schema/Blueprint).
Plan written first: `audit/coverage/p115_target_plan.json` (current behavior, gaps, files, acceptance tests, non-goals, data boundary).

Verified observations (with evidence, not assumption):
- **O1** `/api/search` called `searchCatalog()` directly; `searchHybrid()` existed but grep showed it was used by tests only.
- **O2** `/api/ai/ask` already had structured catalog + vector evidence + `mergeEvidence` + `evaluateEvidenceGate` + `trust-contract` as final boundary.
- **O3** structured eligibility = ACTIVE + isCurrent + VERIFIED doc + ACTIVE official source + VERIFIED BrochureVerification (DB probe: Honda → 5 priced models; **Honda City → 0 priced variants**, City Hatchback V → 1).
- **O4** vector SQL gates (VERIFIED/ACTIVE/BrochureVerification/dimensions) existed — but `searchHybrid` surfaced returned rows **without** `applyEvidenceThresholds`.
- **O5** canonical identity / Thai aliases / short-token rules existed and were reused verbatim — never loosened; alias maps untouched.
- Probes: exact-branch prices filter only `isCurrent` → **334/352** current price rows fail the full official chain; DB slug collision → **`mg-ep` belongs to "EP Plus"**, real EP model is `mg-ep-2`.

## 2. Concrete gaps fixed (red-before → patch → green-after)

| # | Boundary | Before → After |
|---|---|---|
| G1 | `parseSearchQuery` | brand resolved + no Thai model alias → `q=undefined` → **brand-wide** ("Honda City" returned Accord/Civic/CR-V) → scoped via repo's `parseBrandModelQuery` (4-digit year tokens excluded); brand-only queries unchanged |
| G2 | Thai alias join | substring collisions joined → `'yaris yaris cross'`/`'ep ep plus'` matches nothing → dedupe + keep **most specific** phrase (`'ยาริส ครอส'`→`yaris cross`, `'เอพี พลัส'`→`ep plus`) |
| G3 | hybrid + route | route never used hybrid, `vectorAvailable` hardcoded false, **raw ungated vector hits** in evidence → `/api/search` → `searchHybrid()`, every row through `applyEvidenceThresholds` (source/entity/distance/canonical-identity/short-token), structured `results` untouched |
| G4 | ask exact prices | any `isCurrent` price became official AI evidence — red-before proof: real **9carthai.com AUTOMOTIVE_MEDIA** row (`verificationStatus: null`) surfaced for "honda city" → `isOfficialCurrentPrice()` = same chain as `lib/catalog/queries` |
| G5 | ask fallback terms | explicit model query fell back to brand-only term (`honda`/`mg`) → arbitrary same-brand rows → brand term dropped when model scope exists (brand-browse keeps it) |
| G6 | `smartCatalogSearch` | slug `mg-ep` (**EP Plus**) returned as exact for "MG EP" → `identityAccepts()` re-check via `canonicalIdentityGate` — same single identity source as vector gate; layer-2 logic extracted unchanged, gate tests stay green |
| G7 | ask exact trigger | exact-first only for known parser entities — "MG EP" skipped exact → scope = entities **OR** `parseBrandModelQuery().model` |

**RED-BEFORE (base, unmodified): `10 failed | 9 passed (19)`** — logs `20260929-p115-redbefore{,-assertions}.log` (exact failures: 1, 2b, 1b, 3a, 3b, 3c, 4a, 4b, 10b, 12).
**GREEN-AFTER: `19 passed (19)`** — first run, chain rerun, and post-fix final-code run (all identical) — `20260929-p115-green1.log`.

## 3. Mandatory tests (12/12, all real, 0 vacuous)

1. exact `Honda City` → parse scopes `q=city, manufacturer=honda` **and live-DB run**: non-empty City-family rows, zero CR-V/Civic/Accord (red before)
2. Thai alias same behavior (`ฮอนด้า ซิตี้` → same filters/results) + colliding-alias specificity (red before)
3. `MG EP` vs `EP Plus`: route `q=ep` not brand-wide (red) · exact slug collision rejected, `Honda City` still resolves exact (red) · hybrid returns **zero** EP-Plus evidence for "MG EP" (red)
4. `/api/search` results **byte-identical** to structured while gated evidence attaches (red) · route reports hybrid from `searchHybrid` + preserves contract fields (red)
5. vector-disabled → `structured-fallback`, truthful `vectorAvailable=false`, results intact
6. dimension mismatch → `dimension_mismatch`, **query never reaches DB**
7. unverified/inactive source → SQL predicate assertions (VERIFIED/ACTIVE) + gate rejection
8. missing BrochureVerification → SQL `EXISTS (BrochureVerification VERIFIED)` assertion
9. cross-model vector evidence rejected (CR-V row for "Honda City")
10. no structured hit + unqualified vector → `insufficient_evidence`, `whyThisAnswer=[]` · explicit model never brand-guesses in fallback (red)
11. deterministic: two identical retrieval runs → same ordered IDs/evidence + gate idempotence; chain rerun identical
12. provenance: `source.url`/`documentUrl` survive hybrid output; non-official-chain prices dropped (red — real 9carthai leak captured)

## 4. Gates (ONE chain, `20260929-p115-gates.log`)

- focused P115: **19 passed** · combined retrieval/search/AI: **163 passed | 2 skipped rc=0** · full vitest: **507 passed | 2 skipped (43 files) rc=0**
- deterministic rerun: **19 passed identical**
- full pytest (once): **964 passed, 1 error rc=1** — sole error = known pre-existing `test_generation_config_boundary` `_OPENROUTER_ALLOWED_MODEL` ImportError (P49, unchanged from P114 baseline; reported separately, never fixed here)
- tsc: chain run failed on a **type-only cast in the new test file** (`as never`) → fixed → **0**; post-fix re-validation = tsc 0 + p115 19/19 (full/combined ran pre-cast-fix — runtime-identical, disclosed)
- prisma validate **0** · credential scan **0 hits**
- leaked artifacts from pytest reruns (p110/gwm/p114-verification — **timestamp-only**, pre-existing leak class) restored with `git checkout` before commit, disclosed here

## 5. Scope discipline

No Prisma schema/migration · no production DB write · no P114 promotion rerun · no acquisition/refresh · no price/spec harvesting · no provider/model/config change · no embedding generation/write pass · no verifier rewrite · no admin/community/jobs · P102–P106 identity semantics untouched · alias maps untouched · `thai-normalize`/`vector-search` SQL gates/`trust-contract`/ask route unchanged · structured result contract fields unchanged (additive: truthful `vectorAvailable` + `searchMode` + gated `evidence`).

## 6. Honest limits

- structured `q` remains a single phrase — genuinely multi-model queries fail closed (0 rows), never wrong entities
- mixed filler + English-model queries (`ราคา honda city`) fail closed to 0 rather than brand-wide; Thai phrasing resolves via alias map
- `Mg Ep` (slug `mg-ep-2`) has no priced rows/aliases — exact falls through and can end insufficient; separation holds
- no catalog/price/spec-complete claim; retrieval spans only the promoted accepted set

## 7. STOP condition mapping

A structured catalog authoritative ✓ (results never widened; price chain identical) · B vector strictly gated + supplemental ✓ · C exact-model safety ✓ (live + identity tests) · D no provider/model/config/schema changes ✓ · E tests prove A–D ✓ (12/12) · F deterministic/fail-closed ✓ · G local==remote + PR #3 OPEN — see commit section below.
