# P114 — Controlled Promotion of Accepted Evidence (Production Data Layer)

Date: 2026-09-28 · Branch `fix/p1-provenance-gate` · Base `4da86e63` (P113)
Scope: write ONLY the P113-ACCEPTED set (417 packets) into the canonical
Postgres DB (`thai_car_intelligence`, pgvector :5432) — transaction-safe,
idempotent, ledger-traced. No Prisma schema change, no verifier/API/config
change, no staging write, no new acquisition, no promotion of quarantined
packets, no synthesized values.

## 0. Sequence actually executed (audit trail)

1. READ-ONLY PREFLIGHT at `4da86e6` → `p114_promotion_preflight.json`
   (G1–G8 computed, DB baseline captured, planned delta derived).
2. G6 sample re-open: run 1 (Playwright, 2 s hydration) = 6/11 — method
   defect (SPA shells); red-before recorded, re-check with hydration wait +
   HTML/raw fallback = **11/11 PASS** (9 OEMs × identity/price/spec).
3. **G8 commit `3bbd290`** — preflight + G1–G8 gate report committed
   BEFORE any DB write.
4. Attempt-1 promotion transaction: DB writes COMMITTED, then crashed in
   post-commit ledger assembly (`KeyError 'PKT-0001.identity'` — packet_id
   carried the fact suffix). Ledger/result never written → the run could not
   honestly record its own INSERTs.
   **Reverted EXACTLY to the committed baseline** via
   `scripts/p114_revert_attempt1.py` (all 8 table counts == baseline,
   `isCurrent` 96, pre-existing dup-current variants 13). Revert defect: its
   "document-set" condition also matched one pre-baseline Source row
   (changan, held only attempt-1 documents) → recreated with
   codebase-convention fields (original id/name unrecoverable: statement
   logging off, no dump). Disclosed here and in the revert log.
5. Code committed pre-write: `82bf4f2` (producer + independent verifier +
   focused tests; red-before traces = attempt-1 KeyError + 405-vs-404 twin
   probe).
6. **Canonical promotion** (ONE transaction) → committed.
7. Independent verifier → `p114_promotion_verification.json` **PASS (18/18)**.
8. Focused suite: red (2 failed: validFrom timestamp(3) precision on rerun
   lookup; boolean key format t/f) → fixed at the concrete boundary →
   **12 passed / 9.98 s rc=0** (includes idempotent rerun: second run all
   NO_ACTION, DB counts unchanged, committed ledger/result bytes unchanged).
9. One full gate chain (below).

## 1. G1–G8 gates (from `p114_promotion_gates.md` / committed preflight)

- **G1 sidecar+SHA**: 2136/2136 cited observations re-verified (sha256 +
  sidecar URL match), 0 failures.
- **G2 locator re-resolution + mutation**: 2136/2136 resolve in their own
  artifact via the P113 functions; red-before recorded on 8 price
  digit-normalized mismatches (recheck initially omitted P113's
  value_digits mode) — fixed by reusing `P113.price_locator` verbatim;
  fail-closed mutation tests ship in the P113/P114 suites.
- **G3 semantics**: mapping tables committed —
  EXACT_CURRENT_MSRP_VERIFIED → PriceType MSRP `isCurrent=true`;
  MSRP_STARTING_NOT_EXACT → LIST_PRICE `isCurrent=false` (never rewritten as
  MSRP); EXACT_BINDING_NOT_VERIFIED_CURRENT (MG) → MSRP `isCurrent=false`;
  NO_P111_PRICE_EVIDENCE → no row. Spec keys: 12 P112 field keys → 12
  VariantSpec keys (schema-namespace rule documented in preflight);
  confidence official_verified 0.90 / reference 0.75 (mirrors existing
  Price rows).
- **G4 idempotent rerun**: SELECT-first + `ON CONFLICT DO NOTHING` on the
  real unique indexes; rerun proof = focused test (all NO_ACTION, counts
  identical, committed artifacts byte-stable).
- **G5 contamination**: 0 tuple mismatches (every cited obs bound to its
  packet's (manufacturer, model, variant)); historical suites in the chain.
- **G6 sample re-open**: 11/11 PASS — real browser/curl re-open of 11
  accepted-row URLs (Toyota/Changan/Jaguar/Land Rover/Porsche/Lexus/BMW…),
  identity + price value + spec label re-found; artifact side re-checked
  11/11.
- **G7 producer ≠ verifier**: `scripts/p114_promote.py` vs
  `scripts/p114_verify_promotion.py` — separate modules, test asserts no
  cross-import; verifier recomputes all counts from the DB.
- **G8**: gate report MD+JSON committed (`3bbd290`) before any write.

## 2. Promotion result (from `p114_promotion_result.json`, recomputed = ledger)

```
targeted accepted packets                     417
packets promoted (≥1 INSERT)                  414
packets skipped (all NO_ACTION)                 3   (PKT-0164/0426/0427:
                                                     identity+price already
                                                     in DB, no spec facts)
packets failed                                  0
manufacturers inserted                          3   (Deepal, Jaguar, Land Rover)
car models inserted                           127
variants inserted                             404   (13 already present → NO_ACTION)
sources inserted                              11
source documents inserted (contentHash=cited) 122
price rows inserted                           294
  EXACT_CURRENT_MSRP_VERIFIED → MSRP/current  264
  MSRP_STARTING_NOT_EXACT → LIST_PRICE        29   (semantic retained)
  EXACT_BINDING_NOT_VERIFIED_CURRENT → MSRP/not current  1 (MG)
spec rows inserted                          1043   (1388 cited obs; 345 were
                                                     same variant+key+doc → NO_ACTION)
  by key: length_mm 158, height_mm 156, wheelbase_mm 134, seats 120,
          width_mm 99, torque_nm 98, displacement_cc 91, drivetrain 65,
          ground_clearance_mm 58, power_ps 58, range_km 6
legacy current-price demotions (flag only,   8
  history in DataChangeLog; values untouched)
DataChangeLog rows (CREATED/UPDATED)        1879
promotion ledger entries                    2107   (INSERT 1741,
                                                  UPDATE 8, NO_ACTION 358)
quarantined packets promoted                    0
values invented                                 0
identity ledger                             488 (changed_by_p114=false)
```

DB after: Manufacturer 37 · CarModel 284 · Variant 747 · Price 1061 ·
VariantSpec 8036 · Source 32 · SourceDocument 2577 · DataChangeLog 1879
(baseline 34/157/343/767/6993/21/2455/0 → deltas == ledger INSERTs exactly;
verifier 18/18).

Per-OEM (packets / identity / price / spec inserts):
BMW 72/72/67/4 · Changan 5/5/1/0 · Deepal 4/4/0/12 · GWM 18/18/0/4 ·
Honda 35/34/26/0 · Isuzu 5/5/0/0 · Jaguar 1/1/1/0 · Kia 6/6/3/0 ·
Land Rover 11/11/11/0 · Lexus 38/38/27/208 · MG 8/6/1/1 · MINI 15/15/0/0 ·
Mazda 22/22/14/0 · Mitsubishi 24/24/20/0 · Nissan 25/25/2/0 ·
Porsche 5/4/0/1 · Subaru 2/2/1/0 · Suzuki 11/11/10/0 ·
Toyota 110/101/110/813

## 3. Provenance kept on every fact

Price → `sourceDocumentId` (SourceDocument.contentHash = artifact sha256,
url = P111 source_url), `validFrom` = P111 captured_at (UTC, ms), currency
THB, confidence by trust tier. VariantSpec → `sourceDocumentId` + unit +
valueNumeric/valueText verbatim from P112. Identity rows lack per-row
source columns in this schema → every created Manufacturer/CarModel/Variant
carries a DataChangeLog CREATED entry with packet id, artifact, sha256,
source_url, locator excerpt, `applied=true`. Demoted legacy current prices
carry DataChangeLog UPDATED entries with before/after values (flag only —
amounts never altered).

## 4. Honest limits

- 417/488 packets promoted ≠ complete data: 189 variants still have no
  exact current MSRP, 362 have no spec evidence (P112 ceiling), 71 packets
  remain quarantined (P113 reasons) — **zero rows were promoted for them**.
- 3 accepted packets contributed no new row (already present; NO_ACTION).
- Never catalog/price/spec-complete. Identity-only candidates (374) never
  promoted. `nameTh` for created identity rows = `nameEn` (no Thai name in
  identity evidence — disclosed in DataChangeLog evidence).
- **Cross-language identity duplication exists in the FROZEN ledger itself**
  (accepted rows carry both Thai labels — ไทรทัน/มิราจ/นิสสัน… — and Latin
  labels — `ALL NEW MITSUBISHI TRITON`, `Nissan Almera` — for the same real
  models; the seed DB holds Latin rows). P114 promoted exactly what the
  ledger froze; merging the two language trees is an identity-ledger
  question, explicitly NOT performed here.
- Attempt-1 + its revert + the changan Source recreation are fully logged
  (`audit/daily-runs/20260928-p114-attempt1-revert.log`); baseline verified
  exact before the canonical run.

## 4b. Close-out fixes after the first gate chain (red-before → green-after)

Gate chain #1 (committed `20260928-p114-{combined,pytest}.log`) exposed
four boundary defects; each was fixed at its own boundary and revalidated:

1. **p113 determinism test compared a `head` stamp.** `p113_final_result`
   records the HEAD it ran under; comparing it against the committed
   `99c01d5` fails on every later commit (red: `head 82bf4f2… !=
   99c01d5…`). Fix: treat `head` as run provenance (popped alongside
   generated_at/run_id) and `git restore` the committed bytes in `finally`
   instead of re-dumping a popped snapshot.
2. **p111/p112 rerun tests leaked rewritten bytes.** Red-before proof
   (kept at `.hermes/cache/scratch/p114_fix1_redbefore.txt`): the old code
   left 5 files dirty with `generated_at 08:24 → 18:26`
   (`p111_final_result/evidence(+prov)/reconciliation`,
   `p112_spec_evidence.prov`); p112's `finally` also stripped
   `generated_at` by re-dumping a popped snapshot. Fix: byte-snapshot every
   generated file up front, restore those exact bytes in `finally`, and
   assert byte-identity after the finally. Green: **2 passed / 253.49s,
   `git status` empty afterwards**. Evidence semantics untouched (content
   comparison scope unchanged).
3. **thai-aliases asserted the seed baseline as if it were an invariant.**
   Red-before: `37 == 34`, `278 == 157`, export `37 == 34`, `assert ''`.
   Fix: replaced hardcoded counts with current-dataset invariants via an
   independent query path — catalog brand keys == live Manufacturer slugs,
   catalog model keys == live CarModel slugs, every catalog entry maps back
   to a real (brand, model) row (no phantoms), export round-trips the
   generated catalog; non-empty slug kept as its own regression. No DB
   rows were added/removed to make counts match. Green: **45 passed**.
4. **slugify dropped every non-[a-z0-9] character.** Red-before:
   `slugify('เอ็กซ์ฟอร์ส เอชอีวี') == ''` and
   `degenerate P114 model slugs: 16`. Fix: slugify now folds only
   punctuation/whitespace to `-` and keeps Thai letters/marks (`ก-๙`) —
   the repo carries no transliteration source, so Unicode is the only
   non-invented option (URL-safe via percent-encoding). Data repair was
   restricted to rows the promotion created (DataChangeLog CREATED reason
   `P114%`): **38 slug UPDATEs (17 CarModel + 21 Variant)**, each with a
   DataChangeLog UPDATED entry carrying before/after, packet id and reason
   (`p114_slug_repairs.json`). Examples:
   - `ไทรทัน ขับเคลื่อน 2 ล้อ`: `'2'` → `'ไทรทัน-ขับเคลื่อน-2-ล้อ'` (PKT-0268)
   - `นิสสัน คิกส์ อี-พาวเวอร์ ใหม่`: `''` → `'นิสสัน-คิกส์-อี-พาวเวอร์-ใหม่'` (PKT-0276)
   - `ปาเจโร สปอร์ต`: `'-2-2-2-2'` → `'ปาเจโร-สปอร์ต'` (PKT-0272)
   - variant `ซิงเกิ้ล แค็บ 2.4 PRO`: `'2-4-pro'` → `'ซิงเกิ้ล-แค็บ-2-4-pro'` (PKT-0433)
   No historical row was touched. Green: p114 focused **14 passed /
   10.20s**, verifier **VERIFY_PASS checks=19 failures=[]** (now
   reconciling DataChangeLog as promotion 1879 + slug repairs 38 = 1917
   with zero unjustified entries).

## 5. Gates (ONE bounded chain after the close-out fixes)

- Combined suites `tests/test_p114_promotion.py tests/test_p113_packet_acceptance.py tests/test_p112_spec_pass.py tests/test_p111_price_fix.py`
  — **51 passed in 348.64s, rc=0**
  (`audit/daily-runs/20260928-p114-combined2.log`).
- Full `pytest tests/` — **964 passed, 1 error, 0 failed** in 1370.05s;
  the single error is the pre-existing `_OPENROUTER_ALLOWED_MODEL`
  ImportError in `test_generation_config_boundary.py` (touched last in
  `eef8c49`, P49 — causes rc=1, deliberately not fixed in these waves)
  (`audit/daily-runs/20260928-p114-pytest2.log`).
- Deterministic rerun + byte identity inside those suites: p111/p112/p113
  rerun tests all green with byte-restore; `git status` after the full run
  shows **zero** modified P111/P112/P113 artifacts (p110's rerun test
  still rewrites its own artifacts — pre-existing, restored before commit).
- `npx vitest run` 42 files, **488 passed / 2 skipped** · `tsc --noEmit`
  rc=0 · `prisma validate` rc=0 · credential scan over the whole P114
  surface: **0 hits**.
- Independent verifier (final, post-fix): **VERIFY_PASS checks=19
  failures=[]** — every table delta == result == live counts, DataChangeLog
  split 1879 promotion + 38 slug repairs with 0 unjustified, quarantined
  rows promoted 0, invented 0.
- Fix-specific gates: FIX1 green **2 passed / 253.49s + `git status` empty
  after the tests**; FIX2 green **45 passed**; FIX3 green **14 passed /
  10.20s**; red-before evidence kept (`p114_fix1_redbefore.txt`,
  `/tmp/p114_redbefore.log`, failures quoted in section 4b).

## 6. Audit surface (committed)

`p114_promotion_preflight.json` · `p114_promotion_gates.{md,json}` ·
`p114_promotion_ledger.json` (append-only, 2107 entries) ·
`p114_promotion_result.json` · `p114_promotion_verification.json` ·
`p114_slug_repairs.json` (38 justified slug UPDATEs) ·
`p114_promotion_report.md` · scripts `p114_promotion_preflight.py`,
`p114_g6_sample_audit.py`, `p114_promote.py`, `p114_verify_promotion.py`,
`p114_slug_repair.py`, `p114_revert_attempt1.py` ·
`tests/test_p114_promotion.py` (14) + close-out fixes in
`test_p111_price_fix.py`, `test_p112_spec_pass.py`,
`test_p113_packet_acceptance.py`, `test_thai_aliases.py` ·
logs `20260928-p114-{attempt1-revert,combined,pytest,combined2,pytest2,fixes-green}.*`

## 7. Next phase (report only — not started)

Search / retrieval / RAG over the promoted accepted set → public
car/compare/search UX → community/admin → scheduled refresh/deploy.
