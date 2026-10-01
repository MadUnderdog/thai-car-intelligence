"""
Phase 4 refresh orchestration (Blueprint §94/§99) — deterministic pure layers
around the EXISTING primitives:

  classify  — UNCHANGED / CONTENT_CHANGED_OUTPUT_UNCHANGED / CHANGED + diffs
  alerts    — §94 allowlist + deterministic event identity + dedupe
  runner    — daily pipeline: lock → due sources → provenance → classify →
              quarantine queue (jsonl) → alerts → digest (MD+JSON)

The runner NEVER writes catalog/price/spec tables: refresh produces
ChangeCandidates (QUARANTINED) and alerts only; promotion stays with the
frozen AcceptanceRunner/Ledger path.
"""
