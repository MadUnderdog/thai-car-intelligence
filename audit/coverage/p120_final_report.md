# P120 FINAL REPORT — Phase 6: production hardening + observability

Date: 2026-09-30 · PR #3 (OPEN, UNMERGED) · branch `fix/p1-provenance-gate`
Base (reviewed R1 head): `6882756404edde32f9ebcce7f47e35971b57f0e3`
Plan-first commit: `018192530f5e8b108c2309eaa33fedfc878e8f9e` (audit/coverage/p120_target_plan.json — before any code)

## Entry proof (Phase 6 ← Phase 5)
- Phase 5 exit: P119 (`b3c9178`) + R1 (`6882756`) — field provenance, alias joins,
  contamination fail-closed, conflict quarantine, deterministic assembly; gates 30/126/1019.
- G1–G8 on the promoted set: P114 preflight `all_gates_pass=true`, runner/ledger intact,
  idempotency evidenced by the ledger (2107 entries / 417 packets: 1741 INSERT, 358 NO_ACTION,
  8 UPDATE), committed gate report before writes (G8).

## Red-before → green
`20260930-p120-redbefore.log`: **20 failed | 3 passed** on `6882756`+plan — the
`lib/thai_factory/production/*` package did not exist (gaps G1–G6: no worker/preflight,
no audit tooling, no freshness SLO, no runbook, no lock, no run-scoped rollback).
After implementation: focused **21 passed** (all contracts A–Q).

## Phase 6 objective delivered
- **Promotion worker around the frozen gate** (`production/{eligibility,worker}.py` +
  `scripts/p120_production.py`): eligibility with explicit refusals
  (STATUS_NOT_ACCEPTED / CONFLICT_QUARANTINED / LEGACY_UNVERIFIED / EVIDENCE_TAMPERED /
  CROSS_BRAND_COLLISION / IDENTITY_NOT_RESOLVABLE / ALREADY_PROMOTED) → **preflight MD+JSON
  BEFORE any write** → flock serialization → ONE transaction (p114 helpers imported
  read-only; `record()` re-runs AcceptanceRunner before every ledger write) → postflight
  MD+JSON. Preflight FAIL / lock held / empty delta = zero writes (tests O2/P/B).
- **Controlled production promotion of the exact gate-passed set** (chain steps 2–3):
  dry-run → PASS, eligible **0** (refusals: ALREADY_PROMOTED 836 fact-level, STATUS_NOT_ACCEPTED 71);
  execute → **NO_ACTION, writes 0, before==after counts** — the gate-passed set is fully
  promoted already; idempotency proven on production by computation, not assumed.
- **Read-only audit report** (`production/audit.py`, source-scanned for write SQL):
  accepted 417/488 (71 quarantined), provenance coverage **99.91%** (1060/1061 price rows
  with hashed source doc — the 1 uncovered row reported honestly), locator coverage
  **97.6%** (1871/1917), quarantines 71 packets/79 price/410 spec, **13 blocked sources**
  with statuses + next_retry_at, promotion failures 0, duplicates 0/0, last-refresh from
  run-state artifact.
- **Freshness SLO from real dates only**: SourceDocument.fetchedAt 1563 CURRENT /
  1014 UNDATED (never called current or stale), Price.observedAt 1061 CURRENT,
  DataChangeLog 1917 CURRENT; 90-day STALE rule cited from Blueprint; future-dated →
  violation list (test N).
- **Incident/rollback runbook** (`p120_incident_runbook.md`): provenance failure,
  promotion-gate failure, partial refresh, blocked-source transition, duplicate
  invocation, rollback/recovery — rollback = DataChangeLog run-scoped inverse, deletes
  only rows THAT run created, restores superseded isCurrent flags, records its own
  audit marker, second rollback = NO_ACTION (test L).

## Gates
- focused **21** · production dry-run PASS · execute NO_ACTION (0 writes) · audit ✓ ·
  freshness ✓ · combined **147** · full vitest **563|2 (47)** · tsc **0** · prisma **OK** ·
  credscan **0** · full pytest chain run **1039 passed + 1 flake**
  (suzuki Playwright `set_content` 30s timeout — same known class as P119-R1) →
  standalone **2 passed** → bounded rerun **1040 passed** · known P49 ImportError
  excluded and reported separately · tree check OK (only wave work modified).

## Disclosures
1. Chain step-11 flake handled with standalone + bounded rerun (both counts reported;
   no test/code changed to go green).
2. Registry parser uses `access_status` (fixed mid-chain before the p120 combined tests;
   blocked count went 0 → 13 real; audit regenerated; full pytest covered final code).
3. Identity resolution is resolve-existing-only: new-identity packets are refused
   IDENTITY_NOT_RESOLVABLE (identity creation stays P114 mechanics; delta=0 today).
4. Rollback never deletes shared `Source` rows; P114 historical revert unchanged.
5. 1014 undated documents → UNDATED; every date source labeled by column.
6. `production_promotion_ledger.json` not created (no entries written on NO_ACTION).
7. Tests run on an ephemeral schema-only DB (`thai_car_intelligence_p120_test`);
   production tables received ZERO writes (before==after in preflight+postflight).
8. No schema/provider/model/config/verifier change (test Q), no AI in the write path,
   no new source class, P114 not replayed (contract 15: helpers imported read-only).

## Audit surface
`p120_target_plan.json` (commit first) · `p120_preflight_gate.{json,md}` ·
`p120_postflight_audit.{json,md}` · `p120_audit_report.{json,md}` ·
`p120_freshness_report.{json,md}` · `p120_incident_runbook.md` ·
`p120_final_result.json` · this file · `20260930-p120-*.log` ·
`tests/test_p120_{promotion,observability}.py` · `lib/thai_factory/production/*` ·
`scripts/p120_production.py`.

## STOP
Phase 6 chain complete — awaiting review; no Phase 7 / scope expansion started.
