"""
P120 — freshness / SLO report from REAL dated evidence only (contract 10, N).

Date sources (all existing columns, read-only):
  SourceDocument.fetchedAt  — sidecar capture date of the committed artifact
  Price.observedAt          — observation/promotion timestamp on the row
  DataChangeLog.createdAt   — when a change was recorded

Buckets against an explicit `now` (never wall clock inside the report):
  CURRENT  ≤ 30 days      AGING 31–90 days      STALE > 90 days
  UNDATED  no date on the row — never called current, never called stale
  future-dated rows are listed as violations and excluded from every bucket.
The 90-day staleness rule comes from Blueprint Coverage Gap States (STALE =
last checked > 90 days). Nothing is dated unless the evidence is dated.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

SLO = {
    "current_max_days": 30,
    "aging_max_days": 90,
    "stale_after_days": 90,
    "rule_source": "Blueprint.md Coverage Gap States: STALE = last checked > 90 days",
}

SOURCES = {
    "SourceDocument.fetchedAt": ('SELECT "fetchedAt" FROM "SourceDocument"',),
    "Price.observedAt": ('SELECT "observedAt" FROM "Price"',),
    "DataChangeLog.createdAt": ('SELECT "createdAt" FROM "DataChangeLog"',),
}


def _now_naive(now: str) -> datetime:
    dt = datetime.fromisoformat(str(now).replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def build_freshness_report(db_url: str, now: str,
                           repo_root: Optional[str] = None) -> Dict[str, Any]:
    import psycopg2
    now_dt = _now_naive(now)
    conn = psycopg2.connect(db_url)
    try:
        cur = conn.cursor()
        sections: Dict[str, Any] = {}
        for label, (sql,) in SOURCES.items():
            cur.execute(sql)
            buckets = {"CURRENT": 0, "AGING": 0, "STALE": 0, "UNDATED": 0}
            future: list = []
            oldest = None
            newest = None
            total = 0
            for (value,) in cur.fetchall():
                total += 1
                if value is None:
                    buckets["UNDATED"] += 1
                    continue
                dt = value.replace(tzinfo=None) if value.tzinfo else value
                if dt > now_dt:
                    future.append(dt.isoformat())
                    continue
                age = (now_dt - dt).days
                oldest = dt.isoformat() if oldest is None or dt.isoformat() < oldest \
                    else oldest
                newest = dt.isoformat() if newest is None or dt.isoformat() > newest \
                    else newest
                if age <= SLO["current_max_days"]:
                    buckets["CURRENT"] += 1
                elif age <= SLO["aging_max_days"]:
                    buckets["AGING"] += 1
                else:
                    buckets["STALE"] += 1
            sections[label] = {
                "date_column": label,
                "buckets": buckets,
                "future_dated": sorted(future),
                "total_rows": total,
                "oldest_dated": oldest,
                "newest_dated": newest,
            }
    finally:
        conn.close()
    return {
        "schema": "p120_freshness_report/v1",
        "now": now,
        "slo": dict(SLO),
        "sources": sections,
        "policy": "dated rows only; UNDATED never claimed current or stale; "
                  "future-dated rows are violations, excluded from buckets",
    }


def write_freshness_report(report: Dict[str, Any], base_path: str) -> Dict[str, str]:
    base = Path(base_path)
    base.parent.mkdir(parents=True, exist_ok=True)
    json_path = Path(str(base) + ".json")
    json_path.write_text(json.dumps(report, sort_keys=True, ensure_ascii=False,
                                    indent=2, default=str), encoding="utf-8")
    md = [
        "# P120 freshness / SLO report (real dated evidence only)",
        "",
        f"- now: {report['now']}",
        f"- SLO: `{json.dumps(report['slo'])}`",
        f"- policy: {report['policy']}",
        "",
    ]
    for label, sec in report["sources"].items():
        b = sec["buckets"]
        md.append(f"## {label}")
        md.append(f"- CURRENT {b['CURRENT']} · AGING {b['AGING']} · "
                  f"STALE {b['STALE']} · UNDATED {b['UNDATED']} "
                  f"(of {sec['total_rows']} rows)")
        md.append(f"- dated range: {sec['oldest_dated']} .. {sec['newest_dated']}")
        if sec["future_dated"]:
            md.append(f"- future-dated violations: {sec['future_dated']}")
        md.append("")
    md_path = Path(str(base) + ".md")
    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}
