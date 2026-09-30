"""
P120 — read-only production audit report (contract 9, M).

Every statement in this module is a SELECT or a read of a committed artifact;
the test suite scans this source for write keywords. Output is deterministic
for a fixed `now` (sorted keys, counts only, no wall clock).
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional

PACKET_FILE = "audit/coverage/p113_evidence_packets.json"
P114_LEDGER = "audit/coverage/p114_promotion_ledger.json"
PROD_LEDGER = "audit/coverage/production_promotion_ledger.json"
OEM_REGISTRY = "audit/coverage/oem-registry.json"
RUN_STATE = "audit/change-queue/run-state.json"


def _one(cur, sql: str, params=None):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def _read_json(root: Path, rel: str) -> Optional[Any]:
    path = root / rel
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def build_audit_report(db_url: str, now: str,
                       repo_root: Optional[str] = None) -> Dict[str, Any]:
    import psycopg2
    from .freshness import build_freshness_report

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    packets = _read_json(root, PACKET_FILE) or {"packets": []}
    p114_led = _read_json(root, P114_LEDGER) or {"entries": []}
    prod_led = _read_json(root, PROD_LEDGER) or {"entries": []}

    accepted = sum(1 for p in packets["packets"] if p.get("status") == "ACCEPTED")
    quarantined_packets = sum(1 for p in packets["packets"]
                              if p.get("status") != "ACCEPTED")

    conn = psycopg2.connect(db_url)
    try:
        cur = conn.cursor()
        price_total = _one(cur, 'SELECT count(*) FROM "Price"') or 0
        price_current = _one(cur, 'SELECT count(*) FROM "Price" '
                                  'WHERE "isCurrent" = true') or 0
        price_quarantined = _one(cur, 'SELECT count(*) FROM "Price" '
                                      'WHERE "quarantineStatus" = %s',
                                 ("QUARANTINED",)) or 0
        spec_total = _one(cur, 'SELECT count(*) FROM "VariantSpec"') or 0
        spec_quarantined = _one(cur, 'SELECT count(*) FROM "VariantSpec" '
                                'WHERE "quarantineStatus" = %s',
                                ("QUARANTINED",)) or 0
        variant_total = _one(cur, 'SELECT count(*) FROM "Variant"') or 0
        price_with_doc = _one(cur, 'SELECT count(*) FROM "Price" '
                                   'WHERE "sourceDocumentId" IS NOT NULL') or 0
        price_doc_hashed = (_one(cur,
            'SELECT count(*) FROM "Price" p JOIN "SourceDocument" sd ON '
            'p."sourceDocumentId" = sd.id WHERE sd."contentHash" IS NOT NULL')
            or 0)
        locator_rows = (_one(cur,
            'SELECT count(*) FROM "DataChangeLog" WHERE ("evidence"::text '
            'LIKE \'%"locator"%\') OR "evidenceExcerpt" IS NOT NULL') or 0)
        changelog_rows = _one(cur, 'SELECT count(*) FROM "DataChangeLog"') or 0
        sources = _one(cur, 'SELECT count(*) FROM "Source"') or 0
        source_documents = _one(cur, 'SELECT count(*) FROM "SourceDocument"') or 0
        manufacturers = _one(cur, 'SELECT count(*) FROM "Manufacturer"') or 0
        models = _one(cur, 'SELECT count(*) FROM "CarModel"') or 0
        dup_current = (_one(cur,
            'SELECT count(*) FROM (SELECT "variantId", "priceType" FROM '
            '"Price" WHERE "isCurrent" = true GROUP BY 1, 2 HAVING '
            'count(*) > 1) d') or 0)
        dup_specs = (_one(cur,
            'SELECT count(*) FROM (SELECT "variantId", key, '
            '"sourceDocumentId" FROM "VariantSpec" GROUP BY 1, 2, 3 '
            'HAVING count(*) > 1) d') or 0)
    finally:
        conn.close()

    def ledger_section(entries):
        by_action: Dict[str, int] = {}
        for e in entries:
            a = str(e.get("db_action"))
            by_action[a] = by_action.get(a, 0) + 1
        allowed = {"insert", "update", "no_action", "rollback"}
        failures = [e for e in entries
                    if str(e.get("db_action")).lower() not in allowed]
        return {"entries": len(entries),
                "by_action": dict(sorted(by_action.items())),
                "failure_like_entries": len(failures)}

    freshness = build_freshness_report(db_url=db_url, now=now,
                                       repo_root=str(root))
    run_state = _read_json(root, RUN_STATE)
    registry = _read_json(root, OEM_REGISTRY) or {}
    raw_entries = []
    if isinstance(registry, list):
        raw_entries = [(e.get("brand") or e.get("name") or e.get("slug"), e)
                       for e in registry if isinstance(e, dict)]
    elif isinstance(registry, dict):
        listed = registry.get("brands")
        if isinstance(listed, list):
            raw_entries = [(e.get("brand") or e.get("name") or e.get("slug"), e)
                           for e in listed if isinstance(e, dict)]
        else:
            raw_entries = list((registry or {}).items())
    blocked = []
    for brand, entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        # oem-registry brands carry access_status (REACHABLE/BLOCKED_*)
        access = entry.get("access_status") or entry.get("status")
        if access in (None, "REACHABLE"):
            continue
        if entry.get("in_scope") is False:
            continue
        blocked.append({"brand": brand, "status": access,
                        "next_retry_at": entry.get("next_retry_at"),
                        "cycle_state": entry.get("cycle_state")})
    blocked.sort(key=lambda b: str(b["brand"]))

    report = {
        "schema": "p120_audit_report/v1",
        "now": now,
        "read_only": True,
        "accepted_packets": {"total": len(packets["packets"]),
                             "accepted": accepted,
                             "quarantined": quarantined_packets},
        "promoted": {
            "price_rows": price_total,
            "price_current": price_current,
            "spec_rows": spec_total,
            "variant_rows": variant_total,
            "ledger_p114": ledger_section(p114_led["entries"]),
            "ledger_production": ledger_section(prod_led["entries"]),
        },
        "provenance_coverage": {
            "price_rows_total": price_total,
            "price_rows_with_source_document": price_with_doc,
            "price_rows_with_document_content_hash": price_doc_hashed,
            "coverage_pct": round(100.0 * price_doc_hashed / price_total, 2)
                            if price_total else None,
        },
        "locator_coverage": {
            "changelog_rows_total": changelog_rows,
            "changelog_rows_with_locator_or_excerpt": locator_rows,
            "coverage_pct": round(100.0 * locator_rows / changelog_rows, 2)
                            if changelog_rows else None,
        },
        "quarantines": {"price_rows": price_quarantined,
                        "spec_rows": spec_quarantined,
                        "packets": quarantined_packets},
        "freshness_summary": freshness,
        "source_coverage": {"sources": sources,
                            "source_documents": source_documents,
                            "manufacturers": manufacturers,
                            "models": models},
        "last_successful_refresh": run_state if run_state is not None
            else {"status": "unknown", "detail": "no run-state artifact present"},
        "blocked_sources": blocked,
        "promotion_failures": {
            "p114_like_entries": ledger_section(p114_led["entries"])
                                 ["failure_like_entries"],
            "production_like_entries": ledger_section(prod_led["entries"])
                                        ["failure_like_entries"],
        },
        "duplicates": {
            "duplicate_current_price_groups": dup_current,
            "duplicate_spec_groups": dup_specs,
            "p114_ledger_no_action": ledger_section(p114_led["entries"])
                                      ["by_action"].get("NO_ACTION", 0),
            "production_ledger_no_action": ledger_section(prod_led["entries"])
                                           ["by_action"].get("NO_ACTION", 0),
        },
    }
    return report


def write_audit_report(report: Dict[str, Any], base_path: str) -> Dict[str, str]:
    base = Path(base_path)
    base.parent.mkdir(parents=True, exist_ok=True)
    json_path = Path(str(base) + ".json")
    json_path.write_text(json.dumps(report, sort_keys=True, ensure_ascii=False,
                                    indent=2, default=str), encoding="utf-8")
    md = [
        "# P120 production audit report (read-only)",
        "",
        f"- now: {report['now']}",
        f"- accepted packets: **{report['accepted_packets']['accepted']}** / "
        f"{report['accepted_packets']['total']} "
        f"(quarantined {report['accepted_packets']['quarantined']})",
        f"- promoted: price {report['promoted']['price_rows']} "
        f"(current {report['promoted']['price_current']}), "
        f"specs {report['promoted']['spec_rows']}, "
        f"variants {report['promoted']['variant_rows']}",
        f"- provenance coverage (price with hashed source doc): "
        f"**{report['provenance_coverage']['coverage_pct']}%**",
        f"- locator coverage (changelog): "
        f"**{report['locator_coverage']['coverage_pct']}%**",
        f"- quarantines: price {report['quarantines']['price_rows']}, "
        f"spec {report['quarantines']['spec_rows']}, "
        f"packets {report['quarantines']['packets']}",
        f"- freshness: `{json.dumps(report['freshness_summary']['sources'], sort_keys=True)}`",
        f"- sources: {report['source_coverage']['sources']} / "
        f"docs {report['source_coverage']['source_documents']} / "
        f"manufacturers {report['source_coverage']['manufacturers']} / "
        f"models {report['source_coverage']['models']}",
        f"- last successful refresh: `{json.dumps(report['last_successful_refresh'], default=str)}`",
        f"- blocked sources: **{len(report['blocked_sources'])}**",
        f"- promotion failures: `{json.dumps(report['promotion_failures'])}`",
        f"- duplicates: `{json.dumps(report['duplicates'])}`",
        "",
    ]
    md_path = Path(str(base) + ".md")
    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}
