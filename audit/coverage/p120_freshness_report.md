# P120 freshness / SLO report (real dated evidence only)

- now: 2026-09-30T13:43:34.775605+00:00
- SLO: `{"current_max_days": 30, "aging_max_days": 90, "stale_after_days": 90, "rule_source": "Blueprint.md Coverage Gap States: STALE = last checked > 90 days"}`
- policy: dated rows only; UNDATED never claimed current or stale; future-dated rows are violations, excluded from buckets

## SourceDocument.fetchedAt
- CURRENT 1563 · AGING 0 · STALE 0 · UNDATED 1014 (of 2577 rows)
- dated range: 2026-09-17T11:08:42.459000 .. 2026-09-28T09:35:38.220000

## Price.observedAt
- CURRENT 1061 · AGING 0 · STALE 0 · UNDATED 0 (of 1061 rows)
- dated range: 2026-09-19T13:03:24.084000 .. 2026-09-28T14:54:54.061000

## DataChangeLog.createdAt
- CURRENT 1917 · AGING 0 · STALE 0 · UNDATED 0 (of 1917 rows)
- dated range: 2026-09-28T14:54:54.061000 .. 2026-09-28T18:32:12.001000
