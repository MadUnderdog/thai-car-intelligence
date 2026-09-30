# P120-R1 — Targeted evidence-integrity repair (Phase-6 blocker)

Date: 2026-09-30 · Same thread · PR #3 (OPEN, UNMERGED)
Base: `6088d93ad2371cfbef7d11ea9323fa8cf65109f9` (reviewed P120 head)

## Defect (audit finding, confirmed against actual code)
`production/eligibility.py::check_observation()` let `_sidecar_sha_ok()` return
`None` (artifact unresolvable / sidecar missing) **without refusing**, never
hashed the **actual artifact bytes** against `obs.sha256`, and never re-resolved
price locator quotes — a crafted ACCEPTED packet with a missing artifact/sidecar
or a substituted-byte artifact could pass eligibility (contracts E/F).

## Red-before (on HEAD `6088d93`, code untouched)
`20260930-p120r1-redbefore.log`: **6 failed | 1 passed**
- N1 missing artifact / N2 missing sidecar / N4 byte mismatch / N5 quote mismatch
  → NO refusal at all (`set()`)
- N3 sidecar mismatch / N6 malformed sidecar → refused only with generic detail
  (pins for standardized reason strings)
- P1 positive already passed

## Fix (eligibility guard only — runner/verifier untouched)
Fail-closed triple-check per cited observation:
1. artifact must resolve, sidecar must exist AND parse →
   `artifact_unresolvable` / `missing_sidecar` / `malformed_sidecar`
   ⇒ **EVIDENCE_TAMPERED**
2. actual artifact **bytes** SHA-256 == `obs.sha256` **AND** sidecar sha256 ==
   `obs.sha256` ⇒ otherwise `artifact_byte_hash_mismatch` / `sidecar_sha_mismatch`
3. locator required; price quote re-resolved with P119-R5 normalisation ⇒
   `price_locator_quote_mismatch`
All refusals ⇒ zero DB writes (each negative test asserts the DB count is
unchanged after an `--execute` attempt).

**Real-set impact**: all 128 distinct cited artifacts already satisfy
file + sidecar + both hashes (verified before coding) → production dry-run under
the stricter guard: refusals unchanged (`ALREADY_PROMOTED 836`,
`STATUS_NOT_ACCEPTED 71`), **no EVIDENCE_TAMPERED, writes 0, read-only**.

## Tests (7 new: `tests/test_p120_r1_evidence_integrity.py`)
5 required negatives (missing artifact, missing sidecar, sidecar mismatch,
byte-hash mismatch, quote mismatch) + malformed-sidecar + **positive**:
real committed artifact + real sidecar + matching locator promotes on the
ephemeral test DB and rerun is NO_ACTION (idempotent).

## Gates (chain `ALL_GATES_PASS`)
focused **28** · production dry-run clean (read-only) · combined **154** ·
full vitest **563|2** · tsc **0** · prisma **OK** · credscan **0** ·
full pytest **1047 passed** · known P49 ImportError excluded + reported
separately · clean-tree check OK.

## Required distinctions (explicit)
- **P120 controlled production execute = computed eligible delta 0 → NO_ACTION →
  0 writes** (before==after counts). No new production row was created during P120.
- **The promotion worker itself is proven by the ephemeral-DB tests**
  (positive promotion P1, idempotency B/C, rollback L, lock P, transaction K) —
  not by any production write.
- **No claim that a new production row was created during P120 or P120-R1.**
  P120-R1 touched production only via a read-only dry-run.

## Boundaries
No schema/provider/model/config change; no AcceptanceRunner/verifier v9 change;
no P114 replay; ephemeral schema-only test DB for all writes; production tables
untouched in this repair.

## STOP
Bounded repair green and pushed — awaiting review; no Phase 7 (§101 ends at 6).
