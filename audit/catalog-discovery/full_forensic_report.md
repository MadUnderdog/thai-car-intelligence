# Forensic Audit Report — Two-Lane Architecture Pivot

**Generated**: 2026-09-22T17:35:45.710580+00:00
**Project**: Thai Car Intelligence — Catalog Discovery
**Source Commit SHA (verified)**: b0aed37993c42b148bc16769a1543973d4175230
**Remote SHA**: b0aed37993c42b148bc16769a1543973d4175230
**Local == Remote**: YES
**Working Tree**: clean (pre-commit)

## Architecture Pivot

We are pivoting from narrow forensic patch loop to two-lane pipeline:

### Lane A: Discovery / Quarantine
- Scrapers, APIs, media, OEMs may collect candidates freely
- Nothing writes production canonical tables
- Every observation becomes an evidence packet with full provenance

### Lane B: Acceptance / Promotion
- Separate read-only runner (no project verifier helpers)
- Reads only immutable artifacts/evidence packets + live DB
- Deterministic promotion per-observation
- Production DB receives only accepted observations

## New Components

### Evidence Packet (`lib/thai_factory/acceptance/evidence_packet.py`)
- Immutable observation record with full provenance
- Source class, URL/endpoint, native_id, observed_at, retrieval method
- Immutable revision, raw/local artifact hashes
- Target candidate key, exact evidence locator
- Extracted value, extraction confidence, validity/currentness state

### Acceptance Runner (`lib/thai_factory/acceptance/runner.py`)
- Reads evidence packets, makes deterministic promotion decisions
- Confidence check, currentness check, evidence locator required
- Source class promotion eligibility
- Conflict detection (DB integration ready)

### Acceptance Ledger (`lib/thai_factory/acceptance/ledger.py`)
- Machine-readable record of all acceptance decisions
- artifact candidate → acceptance decision → DB action → final DB row id → reason
- Counts computed independently from row-level ledger

## Gold Set Tests (10/10 PASS)

1. Toyota OEM price → ACCEPTED
2. Honda OEM price → ACCEPTED
3. BYD OEM price → ACCEPTED
4. Variant-level price with specs → ACCEPTED
5. Stale observation → REJECTED
6. Model-range MSRP → QUARANTINED
7. Duplicate rerun → ACCEPTED (idempotent)
8. Cross-model contamination → QUARANTINED
9. Multi-source assembly → ACCEPTED (OEM) + QUARANTINED (media)
10. Git object mutation → ACCEPTED

## Test Results

- pytest tests/test_gold_set.py: 10/10 passed
- pytest tests/test_taxonomy_provenance.py: 44/44 passed
- Total: 54/54 passed

## Blockers

- pre-existing import error in tests/test_generation_config_boundary.py (not related to this work)
- Fipe API rate limited (429, ~22h retry)
- Thai DLT not accessible (timeout)
- Third-party taxonomy sites blocked (WAF/JS/SSL)

## Next Steps

1. Database forensic audit: inspect existing 174 price rows + 6,985 VariantSpec rows
2. HLM semantic contract: independently fetch/verify WordPress posts
3. OpenEV contract: GitHub API object metadata / Git tree verification
4. Build acceptance runner integration with live DB
5. Reconciliation ledger with row-level provenance
