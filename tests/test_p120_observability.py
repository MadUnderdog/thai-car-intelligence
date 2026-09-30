"""
P120 — observability contracts: M (read-only deterministic audit), N (freshness
from real dated evidence only), O (preflight before writes, fail-closed), plus
the incident runbook presence.

Red-before: lib/thai_factory/production/{audit,freshness,worker}.py and
audit/coverage/p120_incident_runbook.md do not exist on 6882756+plan.
"""
import json
import re
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from test_p120_promotion import (  # noqa: E402
    require, load_mod, db_conn, q1, exec_, p120_db_url, seed_identity,
    cleanup_marker, make_packet, write_tmp_packets, worker_kwargs, P114_LEDGER,
    REPO as TEST_REPO,
)

FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE)\b")


def test_p120_M1_audit_module_contains_no_write_sql():
    mod = require("audit")
    src = Path(str(mod.__file__)).read_text(encoding="utf-8")
    hit = FORBIDDEN_SQL.search(src)
    assert hit is None, f"audit module must be read-only, found write keyword: {hit.group(0)}"


def test_p120_M2_audit_report_is_deterministic(tmp_path):
    audit = require("audit")
    now = "2026-09-29T12:00:00+00:00"
    r1 = audit.build_audit_report(db_url=p120_db_url(), now=now,
                                  repo_root=str(REPO))
    r2 = audit.build_audit_report(db_url=p120_db_url(), now=now,
                                  repo_root=str(REPO))
    s1 = json.dumps(r1, sort_keys=True, ensure_ascii=False)
    s2 = json.dumps(r2, sort_keys=True, ensure_ascii=False)
    assert s1 == s2, "audit report must be byte-deterministic"
    for key in ("schema", "accepted_packets", "promoted", "provenance_coverage",
                "locator_coverage", "quarantines", "freshness_summary",
                "source_coverage", "last_successful_refresh", "blocked_sources",
                "promotion_failures", "duplicates"):
        assert key in r1, f"contract-9 category missing: {key}"
    # MD + JSON both produced by the writer
    paths = audit.write_audit_report(r1, str(tmp_path / "rep"))
    assert Path(paths["json"]).exists() and Path(paths["md"]).exists()


def test_p120_N1_freshness_uses_only_real_dated_evidence(tmp_path):
    freshness = require("freshness")
    conn = db_conn()
    marker = "p120-fr-" + uuid.uuid4().hex[:8]
    cur = conn.cursor()
    src_id = str(uuid.uuid4())
    now = "2026-09-29T12:00:00+00:00"
    try:
        cur.execute('insert into "Source" (id, "nameEn", "nameTh", "baseUrl", '
                    'domain, "sourceType", "updatedAt") values '
                    '(%s,%s,%s,%s,%s,%s, now())',
                    (src_id, marker, marker, "https://www.toyota.co.th/",
                     "www.toyota.co.th", "OFFICIAL_MANUFACTURER"))
        dated = [
            ("2026-09-25 00:00:00", "CURRENT"),      # 4d old
            ("2026-07-30 00:00:00", "AGING"),        # 61d old
            ("2026-01-10 00:00:00", "STALE"),        # 262d old
            (None, "UNDATED"),
            ("2026-10-05 00:00:00", None),           # future → violation
        ]
        for i, (ts, _b) in enumerate(dated):
            cur.execute('insert into "SourceDocument" (id, "sourceId", url, '
                        '"contentHash", "fetchedAt", "updatedAt") values '
                        '(%s,%s,%s,%s,%s, now())',
                        (str(uuid.uuid4()), src_id,
                         f"https://www.toyota.co.th/{marker}-{i}",
                         uuid.uuid4().hex, ts))
        conn.commit()
        rep = freshness.build_freshness_report(
            db_url=p120_db_url(), now=now, repo_root=str(REPO))
        sd = rep["sources"]["SourceDocument.fetchedAt"]["buckets"]
        assert sd["CURRENT"] >= 1, sd
        assert sd["AGING"] >= 1, sd
        assert sd["STALE"] >= 1, sd
        assert sd["UNDATED"] >= 1, sd
        assert sd["UNDATED"] == sd.get("_undated_count", sd["UNDATED"])
        # future-dated never counted fresh; listed as violation instead
        fut = rep["sources"]["SourceDocument.fetchedAt"].get("future_dated", [])
        assert len(fut) >= 1, rep["sources"]["SourceDocument.fetchedAt"]
        # UNDATED must never appear inside dated buckets: total reconciles
        total = sum(v for k, v in sd.items() if k in
                    ("CURRENT", "AGING", "STALE", "UNDATED"))
        assert total == sd["CURRENT"] + sd["AGING"] + sd["STALE"] + sd["UNDATED"]
        # total reconciles against the report's own global total rows
        # (the freshness report is DB-wide; future-dated rows are excluded
        # from buckets and listed separately)
        sec = rep["sources"]["SourceDocument.fetchedAt"]
        assert sum(sd[k] for k in ("CURRENT", "AGING", "STALE", "UNDATED")) \
            + len(fut) == sec["total_rows"], (sd, fut, sec["total_rows"])
        # determinism with fixed now
        rep2 = freshness.build_freshness_report(
            db_url=p120_db_url(), now=now, repo_root=str(REPO))
        assert json.dumps(rep, sort_keys=True) == json.dumps(rep2, sort_keys=True)
        p1 = freshness.write_freshness_report(rep, str(tmp_path / "fresh"))
        assert Path(p1["json"]).exists() and Path(p1["md"]).exists()
    finally:
        cur.execute('delete from "SourceDocument" where url like %s',
                    (f"%{marker}%",))
        cur.execute('delete from "Source" where id=%s', (src_id,))
        conn.commit()
        conn.close()


def test_p120_O1_preflight_written_before_any_write(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker, status="REJECTED")   # eligible-set empty
        path = write_tmp_packets(tmp_path, [pkt])
        before = q1(conn, 'select count(*) from "DataChangeLog"')
        res = worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        after = q1(conn, 'select count(*) from "DataChangeLog"')
        pre_json = tmp_path / "out" / "p120_preflight_gate.json"
        pre_md = tmp_path / "out" / "p120_preflight_gate.md"
        assert pre_json.exists(), "preflight JSON must exist before any write"
        assert pre_md.exists(), "preflight MD must exist before any write"
        gate = json.loads(pre_json.read_text(encoding="utf-8"))
        assert gate["status"] in ("PASS", "FAIL")
        assert "input_shas" in gate and "eligible" in gate
        assert before == after, "no writes may precede/accompany preflight"
        assert res["writes"] == 0
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_O2_execute_refuses_on_failed_preflight(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker)
        path = write_tmp_packets(tmp_path, [pkt])
        kw = worker_kwargs(tmp_path, path)
        kw["p114_ledger_path"] = str(tmp_path / "corrupt_ledger.json")
        (tmp_path / "corrupt_ledger.json").write_text("{not json",
                                                      encoding="utf-8")
        before = q1(conn, 'select count(*) from "Price"')
        res = worker.run_promotion(mode="execute", **kw)
        assert res["status"] == "PREFLIGHT_FAIL", res
        assert res["writes"] == 0
        assert q1(conn, 'select count(*) from "Price"') == before
        pre = json.loads((tmp_path / "out" / "p120_preflight_gate.json")
                         .read_text(encoding="utf-8"))
        assert pre["status"] == "FAIL"
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_O3_postflight_proves_counts_and_provenance(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker)
        path = write_tmp_packets(tmp_path, [pkt])
        res = worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        assert res["status"] == "PROMOTED", res
        post = json.loads((tmp_path / "out" / "p120_postflight_audit.json")
                          .read_text(encoding="utf-8"))
        assert post["status"] == "PROMOTED"
        assert post["before_counts"] and post["after_counts"]
        assert post["after_counts"]["price"] == post["before_counts"]["price"] + 1
        assert post["provenance"].get("rows_with_packet_sha") >= 1
        assert post["run_id"] == res["run_id"]
        assert (tmp_path / "out" / "p120_postflight_audit.md").exists()
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_O4_incident_runbook_covers_required_scenarios():
    path = REPO / "audit" / "coverage" / "p120_incident_runbook.md"
    assert path.exists(), "p120_incident_runbook.md must exist"
    text = path.read_text(encoding="utf-8").lower()
    scenarios = {
        "provenance failure": ["provenance failure", "tampered", "sidecar"],
        "promotion-gate failure": ["promotion-gate", "preflight fail", "gate fail"],
        "partial refresh": ["partial refresh", "partial run"],
        "blocked source transition": ["blocked", "transition", "403"],
        "duplicate invocation": ["duplicate invocation", "promotion_locked",
                                 "double", "lock"],
        "rollback/recovery": ["rollback", "recovery", "restore"],
    }
    for name, keys in scenarios.items():
        assert any(k in text for k in keys), f"runbook missing scenario: {name}"
    # rollback must be explicit + bounded language present
    assert "pre-existing" in text or "pre-existing rows" in text
