"""
P120 — run-scoped, bounded, auditable rollback (contract 11, L).

Inverse of ONE promotion run: deletes only the business rows that run created
(DataChangeLog rows whose reason cites that run with change_type CREATED),
restores current-price flags the run superseded, records the rollback itself
in DataChangeLog + the production ledger, and is idempotent (a second rollback
of the same run is NO_ACTION). Pre-existing rows are never deleted; shared
infrastructure (Source rows) is never touched.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def db_url(override: Optional[str] = None) -> str:
    from .worker import db_url as _db_url
    return _db_url(override)


def _db_url_env() -> str:
    return db_url(None)


def _counts(conn) -> Dict[str, int]:
    from .worker import db_counts
    return db_counts(conn)


def rollback_run(run_id: str, db_url: Optional[str] = None,
                 out_dir: Optional[str] = None,
                 ledger_path: Optional[str] = None,
                 now: Optional[str] = None) -> Dict[str, Any]:
    import psycopg2
    now = now or datetime.now(timezone.utc).isoformat()
    conn = psycopg2.connect(db_url or _db_url_env())
    conn.autocommit = False
    result: Dict[str, Any] = {"schema": "p120_rollback/v1", "run_id": run_id,
                              "status": None, "deleted_rows": 0,
                              "restored_current_flags": 0, "now": now,
                              "details": []}
    try:
        cur = conn.cursor()
        # idempotency marker: a previous rollback of this run recorded itself
        cur.execute('select count(*) from "DataChangeLog" where reason like %s',
                    (f"%{run_id}%rollback%",))
        if cur.fetchone()[0] > 0:
            result["status"] = "NO_ACTION"
            return result

        cur.execute(
            'select "entityId", "entityType", "changeType", reason from '
            '"DataChangeLog" where reason like %s',
            (f"%{run_id}%",))
        created: Dict[str, list] = {}
        superseded: list = []
        for _cid, entity_type, change_type, reason in cur.fetchall():
            if change_type == "CREATED":
                created.setdefault(entity_type, []).append(str(_cid))
            elif change_type == "UPDATED" and "superseded" in (reason or ""):
                superseded.append(str(_cid))

        before = _counts(conn)
        deleted = 0
        # bounded order: children first (VariantSpec/Price), then documents
        for entity_type in ("VariantSpec", "Price"):
            ids = created.get(entity_type) or []
            if ids:
                cur.execute(f'delete from "{entity_type}" where id = any(%s::uuid[])',
                            (ids,))
                deleted += cur.rowcount
                result["details"].append({"entity_type": entity_type,
                                          "deleted": cur.rowcount})
        doc_ids = created.get("SourceDocument") or []
        if doc_ids:
            cur.execute(
                'delete from "SourceDocument" where id = any(%s::uuid[]) and not '
                'exists (select 1 from "Price" where "sourceDocumentId" = '
                'any(%s::uuid[])) and not exists (select 1 from "VariantSpec" '
                'where "sourceDocumentId" = any(%s::uuid[]))',
                (doc_ids, doc_ids, doc_ids))
            result["details"].append({"entity_type": "SourceDocument",
                                      "deleted": cur.rowcount})
        restored = 0
        for price_id in superseded:
            cur.execute('select "isCurrent" from "Price" where id = %s',
                        (price_id,))
            row = cur.fetchone()
            if row is not None:
                cur.execute('update "Price" set "isCurrent" = true where id = %s',
                            (price_id,))
                restored += cur.rowcount
        result["restored_current_flags"] = restored

        # the rollback itself is auditable: one DCL marker row + ledger entries
        marker_id = str(uuid.uuid4())
        cur.execute(
            'insert into "DataChangeLog" (id, "entityType", "entityId", '
            '"changeType", "beforeValue", "afterValue", reason, evidence, '
            'proposed, applied, "reviewStatus", "createdAt") values '
            '(%s,%s,%s,%s,%s,%s,%s,%s,false,true,\'APPROVED\',now())',
            (marker_id, "PromotionRun", str(uuid.uuid5(uuid.NAMESPACE_URL, run_id)),
             "CORRECTED",
             None, json.dumps({"deleted_rows": deleted,
                               "restored_current_flags": restored}),
             f"run {run_id} rollback — bounded inverse of P120 promotion",
             json.dumps({"run_id": run_id, "rollback_of": run_id,
                         "before_counts": before}, sort_keys=True)))
        conn.commit()
        after = _counts(conn)
        result["status"] = "ROLLED_BACK"
        result["deleted_rows"] = deleted
        result["before_counts"] = before
        result["after_counts"] = after
        result["marker_dcl_id"] = marker_id
    except Exception as exc:
        conn.rollback()
        result["status"] = "FAILED_ROLLED_BACK"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        conn.close()

    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "p120_rollback_audit.json").write_text(
            json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2,
                       default=str), encoding="utf-8")
        md = [
            "# P120 rollback audit", "",
            f"- run_id: `{run_id}`  status: **{result['status']}**",
            f"- deleted_rows: {result['deleted_rows']}",
            f"- restored_current_flags: {result['restored_current_flags']}",
            f"- details: `{json.dumps(result['details'], ensure_ascii=False)}`",
            "- boundary: only rows CREATED by this run; Source rows and all "
            "pre-existing business rows untouched", "",
        ]
        (out / "p120_rollback_audit.md").write_text("\n".join(md),
                                                    encoding="utf-8")
    if ledger_path:
        path = Path(ledger_path)
        entries = []
        if path.exists():
            entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
        entries.append({
            "packet_id": None, "fact": "rollback", "run_id": run_id,
            "db_action": "ROLLBACK" if result["status"] == "ROLLED_BACK"
                         else result["status"],
            "timestamp": now,
            "deleted_rows": result["deleted_rows"],
            "restored_current_flags": result["restored_current_flags"],
            "reason": f"rollback of run {run_id}",
        })
        path.write_text(json.dumps({
            "schema": "production_promotion_ledger/v1",
            "generated_at": now, "append_only": True, "entries": entries,
        }, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        result["ledger_path"] = str(path)
    return result
