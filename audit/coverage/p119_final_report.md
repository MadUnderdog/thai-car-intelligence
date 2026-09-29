# P119 FINAL REPORT — Phase 5: Multi-source assembly + semantic enrichment at scale (§96–97)

Date: 2026-09-29 · PR #3 (OPEN, UNMERGED) · branch `fix/p1-provenance-gate`
Base (P118 reviewed head): `d8b3ef661e4ca5cbd609cc790fce55873d60ebf1`
Plan-first commit: `dc0357b8a77aa1a748ff55589396668df09765ea` (audit/coverage/p119_target_plan.json — BEFORE any code)

## Entry condition (Phase 5 ← Phase 4)
- Phase 4 exit gate: `p118_seven_green_runs.json` PASS 7/7 RUN_GREEN, dup_candidates 0.
- Accepted packet volume: `p113_evidence_packets.json` = 488 packets (417 ACCEPTED, 71 QUARANTINED).
- Alias evidence: `storage/thai-alias-catalog.json` = 34 brands / 157 models / 506 aliases (P110).
- Identity universe: `identity_universe_p108.json` (frozen 488-variant ledger artifact, CONFIRMED_* records with source evidence).

## Architecture actually present (preflight, §95–99)
- EvidencePacket dataclass + AcceptanceRunner (frozen v9) + FILE-based AcceptanceLedger — no schema needed.
- Staging-level joins exist (`build_multi_source_joins.py` → multi_source_joins / cross_class_joins) — a SEPARATE layer, not field-level packet assembly.
- `lib/research/*.ts` dead stub targets never-migrated tables → explicitly separated, untouched.
- Gap: NO field-level assembly, NO conflict policy, NO contamination guard, NO evidence-backed join at field level, NO proposal boundary, NO deterministic assembly output (gaps G1–G7, each reproduced red).

## Red-before (on d8b3ef6 + plan)
`audit/daily-runs/20260929-p119-redbefore.log` → **17 failed | 1 passed** (missing-module red for assembly/ai_proposals; the 1 pass = boundary-scope guard M).

## Before → after (the bounded fix)
- **Field-level assembly** (`lib/thai_factory/assembly/assemble.py`): 417 accepted packets → **417 records, 1,323 assembled fields**, each field = {value, source_id, artifact_sha256, locator, observed_at, trust_tier, packet_id, obs_id, provenance_state, verified} — exact verbatim provenance from its source observation.
- **Evidence-backed join** (`join_keys.py`): candidate_key → identity-universe CONFIRMED records (with sources/label/artifact evidence) enriched by alias catalog; display-string-only keys REJECTED (0 join errors on the real set; rejection path proven by test G). candidate_id always retained; canonical_id only via deterministic reconcile().
- **Conflict policy**: 261 conflicts found in REAL data — all QUARANTINED (same tier, no dated winner; e.g. `seats=1187` vs `seats=2.0` across artifacts) — both sides + full evidence recorded, values NOT emitted. Policy: same tier newest-dated wins (SELECTED_SAME_TIER_NEWEST), cross-tier higher wins with lower retained (SELECTED_HIGHER_TIER), tie → QUARANTINED.
- **Contamination guard** (fail closed): R2 packet artifact↔sha coherence, R4 sidecar sha256 must equal observation sha, R5 price locator quote must re-resolve to value (normalised for ฿3,499,000-style quotes). 0 failures on real set; mutation tests C prove both sha/locator swap and quote mismatch are rejected.
- **Proposal-only boundary** (`ai_proposals.py`): validates packet-ID citations ⊆ packet set, proposed values/canonical paths ⊆ cited packets' observations, no provider/model imports anywhere in the module.
- **Determinism**: two full CLI runs → byte-identical assembled_records/conflicts/join_errors JSONL (chain step 2 PASS).

## Gates (chain `p119_gate_chain_fixed.log` → ALL_GATES_PASS)
- focused: **18 passed** · combined (p111→p112→p113→p114→p119×2→thai_aliases, full-pytest order): **114 passed**
- full vitest: **563 passed | 2 skipped (47 files)** · tsc **0** · prisma **validate OK** · credential scan **0**
- full pytest: **1007 passed** (989 baseline + 18 P119); only known P49 `test_generation_config_boundary.py` ImportError (`_OPENROUTER_ALLOWED_MODEL`, eef8c49) reported separately
- determinism: byte-identical rerun PASS · tree clean (only P119 work + pre-existing untracked strays, disclosed)

## Disclosures (no repair loops opened)
1. Combined chain v1 failed (1 failed test = pre-existing `test_p111` frozen-input check) because an ORPHANED full-pytest from the first chain attempt (pkill missed the child) ran concurrently and rewrote timestamped artifacts mid-test. Sequential proof with the same pre-existing suite order: **51 passed** (`20260929-p119-combined-order-proof.log`). Final chain sequential: 114 passed. No test/code changed to go green; combined order aligned to full-pytest alphabetical order.
2. Chain script v1 had two script-only bugs (grep pattern; wrong filename `test_p113_evidence_sla` → `test_p113_packet_acceptance`) — fixed at script level.
3. R5 guard initially false-positived 201 comma-formatted price quotes — fixed at normalisation (strip commas/spaces, integral float → int); mutation C still fails closed.
4. 261 quarantined conflicts are REAL extraction disagreements surfaced by assembly — assembly is NOT complete for those fields (blocker recorded in report).
5. Honest limits: model_year always None (no year in packets); proposal boundary = validator only (zero LLM calls, per contract); no DB reads; no promotion; no schema/verifier/provider/model/config change (test M).

## Audit surface (O)
- `audit/coverage/p119_target_plan.json` (commit before code) · `audit/coverage/p119_final_result.json` · `audit/coverage/p119_final_report.md` (this file) · `audit/coverage/p119_assembly_report.{json,md}` (machine-readable, per-source contribution, conflicts, quarantines, coverage, blockers)
- `audit/assembly/{assembled_records,conflicts,join_errors,validation_failures}.jsonl`
- `audit/daily-runs/20260929-p119-*.log` (redbefore, focused, combined, order-proof, determinism1/2, full-vitest, tsc, prisma, full-pytest, p49, assembly-run)
- Exact final SHA, local==remote, clean tree, PR #3 OPEN/UNMERGED — see push message.

## STOP
P119 complete per contract A–O. No Phase 6 / promotion / acquisition started. Awaiting review.
