# P120 production audit report (read-only)

- now: 2026-09-30T14:21:22.884107+00:00
- accepted packets: **417** / 488 (quarantined 71)
- promoted: price 1061 (current 352), specs 8036, variants 747
- provenance coverage (price with hashed source doc): **99.91%**
- locator coverage (changelog): **97.6%**
- quarantines: price 79, spec 410, packets 71
- freshness: `{"DataChangeLog.createdAt": {"buckets": {"AGING": 0, "CURRENT": 1917, "STALE": 0, "UNDATED": 0}, "date_column": "DataChangeLog.createdAt", "future_dated": [], "newest_dated": "2026-09-28T18:32:12.001000", "oldest_dated": "2026-09-28T14:54:54.061000", "total_rows": 1917}, "Price.observedAt": {"buckets": {"AGING": 0, "CURRENT": 1061, "STALE": 0, "UNDATED": 0}, "date_column": "Price.observedAt", "future_dated": [], "newest_dated": "2026-09-28T14:54:54.061000", "oldest_dated": "2026-09-19T13:03:24.084000", "total_rows": 1061}, "SourceDocument.fetchedAt": {"buckets": {"AGING": 0, "CURRENT": 1563, "STALE": 0, "UNDATED": 1014}, "date_column": "SourceDocument.fetchedAt", "future_dated": [], "newest_dated": "2026-09-28T09:35:38.220000", "oldest_dated": "2026-09-17T11:08:42.459000", "total_rows": 2577}}`
- sources: 32 / docs 2577 / manufacturers 37 / models 284
- last successful refresh: `{"status": "unknown", "detail": "no run-state artifact present"}`
- blocked sources: **13**
- promotion failures: `{"p114_like_entries": 0, "production_like_entries": 0}`
- duplicates: `{"duplicate_current_price_groups": 0, "duplicate_spec_groups": 0, "p114_ledger_no_action": 358, "production_ledger_no_action": 0}`
