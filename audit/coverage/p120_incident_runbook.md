# P120 — Production incident & rollback runbook (Phase 6)

Scope: Thailand official-market catalog production tables. The acceptance gate
(AcceptanceRunner + append-only AcceptanceLedger) is the ONLY authority for
writes. All commands below run offline from the repository; every write path
goes through `scripts/p120_production.py promote --execute` (preflight PASS +
flock + one transaction) — there is no other authorized writer.

## 1. Provenance failure (tampered artifact / sidecar hash mismatch)

Symptoms: promotion preflight reports `EVIDENCE_TAMPERED` refusals, or an
acquisition test fails on sidecar/sha verification.

Exact recovery:
1. Do NOT promote the affected packets. The refusal is the system working.
2. Re-verify the raw artifact: its `.prov.json` sidecar sha256 must equal the
   bytes on disk (`sha256sum tests/fixtures/oem-artifacts/<file>`).
3. If the bytes were modified, quarantine the artifact (leave it in place,
   mark it) and recapture through `AcquisitionWriter` in the next permitted
   acquisition window — never hand-repair a sidecar to make a hash pass.
4. Re-run `p120_production.py preflight` and confirm the refusal clears only
   after genuinely fresh evidence exists.

## 2. Promotion-gate failure (preflight FAIL)

Symptoms: `preflight` exits 1 with `status: FAIL` (corrupt input, ledger
unreadable, DB unreachable) or `promote --execute` returns `PREFLIGHT_FAIL`
with zero writes.

Exact recovery:
1. Zero rows were written — verify: postflight file says `PREFLIGHT_FAIL`,
   `writes: 0`, and `db_counts_before` equals the current DB counts
   (`p120_production.py audit`).
2. Read `error` in `audit/coverage/p120_preflight_gate.json`; fix the input
   artifact (restore the corrupt ledger/artifact from git — raw artifacts are
   immutable in git history).
3. Re-run preflight. Never bypass with a manual SQL insert (contract 14).

## 3. Partial refresh (daily run ended PARTIAL / some sources failed)

Symptoms: P118 digest shows `RUN_PARTIAL`, some sources `BLOCKED_*`.

Exact recovery:
1. Prior accepted production state is preserved by design — failed
   acquisition/refresh never deletes or downgrades accepted rows (test J).
2. Check `audit/change-queue/run-state.json` + the day's digest for which
   sources failed and the recorded backoff (`next_retry_at`).
3. Do NOT re-run promotion: refresh failures do not make packets
   un-accepted; production rows stay as promoted. The next green daily run
   continues from committed evidence.

## 4. Blocked source transition (REACHABLE → BLOCKED_HTTP_403/DNS/TLS)

Symptoms: daily alerts record a state transition with `next_retry_at`.

Exact recovery:
1. The transition alert fires once per transition — repeat alerts mean
   deduplication broke, not that the source recovered.
2. Respect `next_retry_at` from the §94 backoff policy; never retry inside
   the window, never rotate user-agents to bypass (policy forbids
   `bypass=true`).
3. Production freshness report: the source's rows simply age into
   AGING/STALE buckets — they are NOT deleted and NOT re-marked current.

## 5. Duplicate invocation (double promotion / concurrent run)

Symptoms: one invocation returns `PROMOTION_LOCKED`; or a replayed promote
returns `NO_ACTION`.

Exact recovery:
1. `PROMOTION_LOCKED` = another run holds `audit/coverage/p120_promotion.lock`.
   Wait for it; zero writes happened on the locked invocation.
2. Replay safety: the ledger marks facts ALREADY_PROMOTED and the row-level
   `ON CONFLICT` constraints dedupe (tests B/C/P). If a duplicate row is
   somehow observed (`duplicates` section of the audit report > 0): do NOT
   delete by hand — run the bounded rollback of the LATER run id (section 6),
   which removes only what that run created.
3. Confirm with `p120_production.py audit` → `duplicates.*` back to 0.

## 6. Rollback / recovery (bounded, auditable — never blind deletion)

When a promotion run itself is bad (wrong semantics discovered after commit):

```
python3 scripts/p120_production.py rollback --run-id <P120-…> \
    --out-dir audit/coverage --ledger audit/coverage/production_promotion_ledger.json
```

Exact properties (test L):
1. It deletes ONLY business rows whose DataChangeLog CREATED entry cites that
   run id, and only those still present.
2. It restores `isCurrent=true` on exactly the price rows THAT run superseded
   (their DCL UPDATED entries), so prior accepted/current state returns.
3. Shared infrastructure (`Source` rows) and all pre-existing business rows
   are untouched; a second rollback of the same run is `NO_ACTION`.
4. The rollback writes its own DataChangeLog marker
   (`run <id> rollback — bounded inverse`) and a ledger `ROLLBACK` entry, so
   the inverse is itself auditable.
5. Verify after: `p120_production.py audit` counts match the pre-run
   snapshot (`before_counts`/`after_counts` in `p120_rollback_audit.json`).

Never recover by truncating tables or by re-inserting values from memory —
recovery = ledger + DataChangeLog-driven inverse only.
