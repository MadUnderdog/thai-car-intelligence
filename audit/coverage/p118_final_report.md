# P118 — PHASE 4 DAILY DIFF + SCHEDULED UPDATES + ALERTING

**Status: COMPLETE (awaiting review) · 2026-09-29 · base `76a242a0b756c2e04c40769e0947779f6a85d755` · plan committed FIRST as `a5849d0` · PR #3 OPEN/UNMERGED**

## Architecture decision (no parallel system)

Built ONLY the missing §94/§99 orchestration around existing primitives: `AcquisitionWriter/Reader` + ladder + `oem-registry.json` (single source of truth) + digest file convention + frozen AcceptanceRunner. The TS `lib/research` refresh stub was **not** revived — it writes `RefreshRun/ChangeCandidate/SourceHealth` tables that were never migrated (absent from DB and Prisma); reviving needs a schema change (default NO) — disclosed as follow-up. §99's spec — `audit/change-queue/*.jsonl` — is the queue that got built.

## Before → after (red-before `20260929-p118-redbefore.log` = 25 failed / 0 passed)

| Gap | Before (76a242a) | After |
|---|---|---|
| G-A runner | nothing ran the pipeline; no cron/one-shot entrypoint | `scripts/daily_run.py`: `--once` (default) / `--cron` (SAME runner) / `--replay7`; documented cron line; exit 0/1/2 |
| G-B backoff | grep `BLOCKED_TLS\|backoff` over lib/ = zero; ladder is adapter fallback only | `acquisition/backoff.py` — full §94 table as pure functions: 403 +7d→monthly with `rotate_ua/bypass=False`; 404 +14d ≤2 alternates/cycle; DNS weekly×4→monthly; TLS monthly `disable_cert_verification=False` (never); timeout 30s/120s→CYCLE_BLOCKED; 5xx 30s/120s→RETRY_NEXT_RUN; politeness gap ≥5s |
| G-C diff/queue | no classification; `audit/change-queue/` absent | `refresh/classify.py` → FIRST_CAPTURE / UNCHANGED / CONTENT_CHANGED_OUTPUT_UNCHANGED / CHANGED (+field & set diffs); append-only `change-candidates.jsonl` deduped by candidate_id, status QUARANTINED |
| G-D alerts | no store/rules/dedupe | `refresh/alerts.py` — §94 allowlist (6 types), content-derived event_id dedupe |
| G-F digest | only the cycle report | per-run MD+JSON `YYYYMMDD{,b..u}.{md,json}` with run_id/commit/artifacts bytes/identity levels/hash+locator coverage/blockers/tests/candidates/alerts/state transitions/observations |
| G-G lock | none → cron double-fire duplicates | `fcntl` lock → `RUN_SKIPPED_DOUBLE`, exit 2, zero writes |
| G-H exit | no 7-run proof | `audit/coverage/p118_seven_green_runs.json` → **exit_gate PASS** |

Test-precision fix (disclosed): politeness assertion rewritten to `elapsed+wait ≥5000ms` — the policy is a ≥5s *gap*; the original assertion was stricter than §94 itself.

## 7 consecutive green runs (Blueprint Phase 4 exit)

`DR-20260929-001…007` — all **RUN_GREEN**, `duplicate_candidate_ids: 0`, digests `20260929{o..u}.{md,json}`, queue in `audit/change-queue/replay7/`:

- 001 FIRST_CAPTURE (baseline, no alert) · 002 UNCHANGED · 003 CONTENT_CHANGED_OUTPUT_UNCHANGED
- 004 CHANGED → **PRICE_CHANGE** (exactly one) · 005 CHANGED → **MODEL_VARIANT_ADDED_REMOVED** (add+remove, staging bytes untouched)
- 006 capture UNCHANGED + probe 403 → **SOURCE_STATE_TRANSITION** `REACHABLE→BLOCKED_HTTP_403`, `next_retry_at` = +7d per policy
- 007 repeat blocker → **no alerts**

Re-run proof: `--replay7` invoked 3× (2 manual + chain) — every invocation PASS/7-7/0 dup.

## Red→green cycle

Focused after implementation: 23/25 — two real defects caught: **J** run_id identical across digest dirs → run identity moved to queue-global monotonic sequence; **P** CLI test dir naming → both entrypoints verified by subprocess (exit 0, same `runner` field). Green: **25/25**, rerun 25/25.

## Gates — ONE chain (`proc_212d6f7d946b`)

tsc **0** · focused **25** · rerun **25** · combined python (acquisition/provenance/diff/change/acceptance incl. p111–p114) **146 passed / 424s rc=0** · vitest combined **67 (6 files) rc=0** · full vitest **563 passed|2 skipped (47) rc=0** · full pytest **989 passed, 1 error (1450.86s)** — ONLY error = known P49 `_OPENROUTER_ALLOWED_MODEL` (disclosed only; 989 = 964 + 25 new) · prisma **0** · credscan **0** · **REPLAY7 rc=0 PASS 7/7** · git tree clean of non-P118 mods (8 pytest-regenerated timestamp artifacts restored + disclosed)

## Contracts proven (A–Q, all non-vacuous)

A same-SHA UNCHANGED no rows · B new-sha/identical-output no mutation · C exactly one QUARANTINED field candidate (old_sha/new_sha/source/entity/field) · D price alert once · E add/remove candidates+alert, staging bytes identical · F transition once +7d · G full policy incl. TLS/403 safety flags · H ERROR_PAGE/DEALER_REDIRECT evidence stored, obs=0 · I ProvenanceError → RUN_PARTIAL, 0 candidates, catalog counts equal, alert deduped on rerun · J byte-identical observation sets · K lock skip zero-writes · L quarantine + Price/Variant/CarModel/DataChangeLog/CommunityComment counts unchanged · M failed refresh preserves last_sha/output_hash · N digest required keys · O deterministic event ids + dedupe · P `--once`/`--cron` same runner · Q suites green

## Boundaries

registry = single source of truth (real domains only, no invented URLs) · every fixture = real `AcquisitionWriter` capture with real sidecar (Reader fail-closed) · legacy stays LEGACY_UNVERIFIED · **zero catalog/price/spec writes** (L/M assert counts) · no promotion, gates untouched · no AI reconciliation · no new source class · no schema/provider/config change · no network in CI · P114–P117 suites green.

## Honest limits

fixture extractors (`json`/`html_prices`) — live adapter wiring = follow-up · TS refresh stub dead (schema-gated) · registry retry timestamps not retrofetched · politeness state in-memory · two earlier manual replay digest batches superseded by the chain batch and removed (reproducible via `--replay7`) · cron documented, not installed · never declares refresh coverage complete.
