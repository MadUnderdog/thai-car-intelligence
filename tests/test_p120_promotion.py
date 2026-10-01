"""
P120 — production promotion worker contracts (Blueprint §101 Phase 6, A–L, P, Q).

Red-before: on base 6882756 + plan commit 0181925 the
lib/thai_factory/production/* package does not exist (gaps G1/G5/G6 of
p120_target_plan.json) — every test fails at its module-existence check.

DB boundary: tests run against an EPHEMERAL schema-only database
(thai_car_intelligence_p120_test, created from pg_dump --schema-only of the
production schema — structure only, no data). Production tables are never
written by tests. No network.
"""
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

BASE_SHA = "6882756404edde32f9ebcce7f47e35971b57f0e3"
PACKETS_PATH = REPO / "audit" / "coverage" / "p113_evidence_packets.json"
P114_LEDGER = REPO / "audit" / "coverage" / "p114_promotion_ledger.json"
CATALOG_PATH = REPO / "storage" / "thai-alias-catalog.json"
TEST_DB = "thai_car_intelligence_p120_test"

_db_ready = False


def load_mod(name: str):
    try:
        import importlib
        return importlib.import_module(f"thai_factory.production.{name}")
    except Exception:
        return None


def require(name: str):
    m = load_mod(name)
    assert m is not None, f"lib/thai_factory/production/{name}.py must exist"
    return m


# ── ephemeral test database (structure-only copy of the production schema) ──
def _env_db_url() -> str:
    txt = (REPO / ".env").read_text(encoding="utf-8")
    m = re.search(r'^DATABASE_URL="([^"]+)"', txt, re.M)
    assert m, "DATABASE_URL missing from .env"
    return m.group(1).split("?")[0]


def p120_db_url() -> str:
    """Same server, ephemeral test database (never production)."""
    from urllib.parse import urlsplit, urlunsplit
    parts = urlsplit(_env_db_url())
    return urlunsplit((parts.scheme, parts.netloc, f"/{TEST_DB}", "", ""))


def ensure_test_db() -> None:
    global _db_ready
    if _db_ready:
        return
    exists = subprocess.run(
        ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "postgres",
         "-tAc", f"SELECT 1 FROM pg_database WHERE datname='{TEST_DB}'"],
        capture_output=True, text=True, timeout=60).stdout.strip()
    if exists != "1":
        subprocess.run(["docker", "exec", "pgvector", "psql", "-U", "hermes",
                        "-d", "postgres", "-c",
                        f'CREATE DATABASE "{TEST_DB}"'],
                       capture_output=True, text=True, timeout=60, check=True)
        dump = subprocess.run(["docker", "exec", "pgvector", "pg_dump", "-U", "hermes",
                               "-d", "thai_car_intelligence", "--schema-only",
                               "--no-owner", "--no-privileges"],
                              capture_output=True, timeout=600)
        assert dump.returncode == 0, dump.stderr[-500:]
        subprocess.run(["docker", "exec", "-i", "pgvector", "psql", "-U", "hermes",
                        "-d", TEST_DB], input=dump.stdout, capture_output=True,
                       timeout=600, check=True)
    _db_ready = True


def db_conn():
    import psycopg2
    ensure_test_db()
    conn = psycopg2.connect(p120_db_url())
    conn.autocommit = False
    return conn


def q1(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None


def exec_(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# ── fixture builders ────────────────────────────────────────────────────────
def seed_identity(conn, brand=None, model=None, variant=None):
    """Seed a resolvable identity; names are marker-unique so identity
    resolution can never collide with rows leaked by an earlier run.
    Returns (variant_id, marker) with cleanup."""
    marker = "p120-" + uuid.uuid4().hex[:10]
    brand = brand or f"P120 Test Brand {marker}"
    model = model or f"P120 Test Model {marker}"
    variant = variant or f"P120 Test Variant {marker}"
    cur = conn.cursor()
    mid, cid, vid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    cur.execute('insert into "Manufacturer" (id, "nameEn", "nameTh", slug, '
                '"updatedAt") values (%s,%s,%s,%s, now())',
                (mid, brand, brand, marker + "-brand"))
    cur.execute('insert into "CarModel" (id, "nameEn", "nameTh", slug, '
                '"manufacturerId", "updatedAt") values (%s,%s,%s,%s,%s, now())',
                (cid, model, model, marker + "-model", mid))
    cur.execute('insert into "Variant" (id, "nameEn", "nameTh", slug, '
                '"modelId", "updatedAt") values (%s,%s,%s,%s,%s, now())',
                (vid, variant, variant, marker + "-variant", cid))
    conn.commit()
    return vid, marker


def cleanup_marker(conn, marker: str):
    # clear any aborted transaction first (a failed raw insert must not
    # silently disable the cleanup itself — that is how rows leaked before)
    conn.rollback()
    cur = conn.cursor()
    cur.execute('delete from "DataChangeLog" where reason like %s '
                'or reason like %s or reason like %s or reason like %s',
                (f"%{marker}%", "%PKT-P120-%",
                 "%controlled promotion%", "%bounded inverse%"))
    cur.execute('delete from "VariantSpec" where "variantId" in '
                '(select id from "Variant" where slug like %s)',
                (marker + "%",))
    cur.execute('delete from "Price" where "variantId" in '
                '(select id from "Variant" where slug like %s)',
                (marker + "%",))
    cur.execute('delete from "SourceDocument" where "sourceId" in '
                '(select id from "Source" where "nameEn" like %s)',
                (f"%{marker}%",))
    cur.execute('delete from "Source" where "nameEn" like %s or "nameEn" = %s',
                (f"%{marker}%", "p120-fix-src"))
    cur.execute('delete from "Variant" where slug like %s', (marker + "%",))
    cur.execute('delete from "CarModel" where slug like %s', (marker + "%",))
    cur.execute('delete from "Manufacturer" where slug like %s', (marker + "%",))
    conn.commit()


def make_packet(vid_marker="p120-fixture", status="ACCEPTED", tamper=None,
                provenance_state="ACQUISITION_VERIFIED", price=1234000,
                price_type="EXACT_VARIANT", is_current=True, artifact=None,
                sha=None, brand=None, model=None, variant=None,
                candidate_key=None):
    """Deterministic synthetic packet shaped exactly like the real ones."""
    pkt_id = "PKT-P120-" + uuid.uuid4().hex[:8]
    brand = brand or f"P120 Test Brand {vid_marker}"
    model = model or f"P120 Test Model {vid_marker}"
    variant = variant or f"P120 Test Variant {vid_marker}"
    artifact = artifact or "toyota_pricelist_page.html"
    if sha is None:
        # default: the REAL committed artifact's sidecar sha (coherent evidence)
        side = (REPO / "tests" / "fixtures" / "oem-artifacts"
                / f"{artifact}.prov.json")
        sha = json.loads(side.read_text(encoding="utf-8"))["sha256"]
    obs = {
        "obs_id": f"{pkt_id}.price.msrp_thb",
        "field": "msrp_thb",
        "value": price,
        "price_type": price_type,
        "msrp_status": "EXACT_CURRENT_MSRP_VERIFIED" if is_current
                       else "EXACT_BINDING_NOT_VERIFIED_CURRENT",
        "counts_as_current_msrp": is_current,
        "currentness": "CURRENT",
        "source_url": "https://www.toyota.co.th/en/pricelist",
        "source_name": "fixture",
        "artifact": artifact,
        "sha256": sha,
        "locator": {"mode": "value_in_record", "quote": f"{price:,} บาท",
                    "resolved": True},
        "source_class": "MARKET_TRUTH",
        "source_role": "MARKET_TRUTH",
        "trust_tier": "official_verified",
        "provenance_state": provenance_state,
        "runner_decision": "ACCEPTED",
        "cited": True,
    }
    if tamper == "sha":
        obs["sha256"] = hashlib.sha256(b"tampered").hexdigest()
    if tamper == "no_locator":
        obs["locator"] = None
    packet = {
        "packet_id": pkt_id,
        "status": status,
        "manufacturer": brand,
        "model": model,
        "variant": variant,
        "candidate_key": candidate_key or
            f"{brand.lower().replace(' ', '-')}|{model.lower()}||{variant.lower().replace(' ', '-')}",
        "policy": {},
        "field_gaps": [],
        "generation_context": "",
        "scope": "TH",
        "observations": {"identity": [], "price": [obs], "spec": []},
        "_fixture_marker": vid_marker,
    }
    return packet


def promoted_facts_from_ledgers():
    """(packet_id, fact) pairs already promoted — p114 ledger + production ledger."""
    facts = set()
    if P114_LEDGER.exists():
        for e in json.loads(P114_LEDGER.read_text(encoding="utf-8"))["entries"]:
            facts.add((e["packet_id"], e.get("fact") or "identity"))
    prod = REPO / "audit" / "coverage" / "production_promotion_ledger.json"
    if prod.exists():
        for e in json.loads(prod.read_text(encoding="utf-8"))["entries"]:
            facts.add((e["packet_id"], e.get("fact") or "identity"))
    return facts


def write_tmp_packets(tmp_path, packets):
    p = tmp_path / "packets.json"
    p.write_text(json.dumps({"packets": packets}), encoding="utf-8")
    return str(p)


def worker_kwargs(tmp_path, packets_path):
    return dict(
        packets_path=packets_path,
        p114_ledger_path=str(P114_LEDGER),
        production_ledger_path=str(tmp_path / "prod_ledger.json"),
        lock_path=str(tmp_path / ".promotion.lock"),
        out_dir=str(tmp_path / "out"),
        fixtures_dir=str(REPO / "tests" / "fixtures"),
        db_url=p120_db_url(),
        now="2026-09-29T12:00:00+00:00",
    )


# ══════════════════════════════════════════════════════════════════════════
def test_p120_A_unaccepted_packet_cannot_promote(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker, status="QUARANTINED")
        path = write_tmp_packets(tmp_path, [pkt])
        res = worker.run_promotion(mode="dry_run", **worker_kwargs(tmp_path, path))
        assert res["status"] in ("NO_ACTION", "DRY_RUN"), res
        by_id = {r["packet_id"]: r for r in res["eligibility"]}
        assert by_id[pkt["packet_id"]]["eligible"] is False
        reasons = {r["reason"] for r in by_id[pkt["packet_id"]]["refusals"]}
        assert reasons & {"STATUS_NOT_ACCEPTED", "CONFLICT_QUARANTINED"}, reasons
        # and nothing may reach the DB in dry-run anyway
        assert res["writes"] == 0
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_B_accepted_promotes_once_rerun_idempotent(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker)
        path = write_tmp_packets(tmp_path, [pkt])
        res1 = worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        assert res1["status"] == "PROMOTED", res1.get("refusals") or res1["status"]
        assert res1["writes"] > 0
        n1 = q1(conn, 'select count(*) from "Price" where "variantId"=%s', (vid,))
        # rerun: same packet set, fresh run
        res2 = worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        assert res2["status"] == "NO_ACTION", res2
        assert res2["writes"] == 0
        n2 = q1(conn, 'select count(*) from "Price" where "variantId"=%s', (vid,))
        assert n1 == n2 and n1 == 1, (n1, n2)
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_C_replay_creates_no_duplicate_business_rows(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker)
        path = write_tmp_packets(tmp_path, [pkt])
        before = q1(conn, 'select count(*) from "Variant"')
        worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        mid_counts = (q1(conn, 'select count(*) from "Variant"'),
                      q1(conn, 'select count(*) from "Price"'),
                      q1(conn, 'select count(*) from "VariantSpec"'))
        # replay twice more with the SAME packet set
        worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        after = (q1(conn, 'select count(*) from "Variant"'),
                 q1(conn, 'select count(*) from "Price"'),
                 q1(conn, 'select count(*) from "VariantSpec"'))
        assert mid_counts == after, (mid_counts, after)
        # identity created exactly once for this fixture
        assert q1(conn, 'select count(*) from "Variant" where slug like %s',
                  (marker + "%",)) == 1
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_D_legacy_unverified_packet_refused(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker, provenance_state="LEGACY_UNVERIFIED")
        path = write_tmp_packets(tmp_path, [pkt])
        res = worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        by_id = {r["packet_id"]: r for r in res["eligibility"]}
        reasons = {r["reason"] for r in by_id[pkt["packet_id"]]["refusals"]}
        assert "LEGACY_UNVERIFIED" in reasons, reasons
        assert res["writes"] == 0
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == 0
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_E_tampered_evidence_refused(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        bad_sha = make_packet(marker, tamper="sha")
        no_loc = make_packet(marker, tamper="no_locator")
        path = write_tmp_packets(tmp_path, [bad_sha, no_loc])
        res = worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        by_id = {r["packet_id"]: r for r in res["eligibility"]}
        for pkt in (bad_sha, no_loc):
            reasons = {r["reason"] for r in by_id[pkt["packet_id"]]["refusals"]}
            assert "EVIDENCE_TAMPERED" in reasons, (pkt["packet_id"], reasons)
        assert res["writes"] == 0
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == 0
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_F_promoted_rows_carry_packet_sha_locator(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker)
        path = write_tmp_packets(tmp_path, [pkt])
        res = worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        assert res["status"] == "PROMOTED", res
        rows = exec_(conn,
                     'select reason, evidence from "DataChangeLog" '
                     'where reason like %s', (f"%{pkt['packet_id']}%",))
        assert rows, "DataChangeLog entries must cite the packet"
        joined = json.dumps([r[1] for r in rows], default=str)
        assert pkt["packet_id"] in joined or any(
            pkt["packet_id"] in str(r[0]) for r in rows)
        obs = pkt["observations"]["price"][0]
        assert obs["sha256"] in joined, "promoted row must carry artifact sha256"
        assert "pricelist" in joined or "locator" in joined.lower() or \
            obs["sha256"] in joined
        md = json.loads(joined)
        locators = json.dumps(md)
        assert "value_in_record" in locators or "quote" in locators, \
            "locator must be recorded in the change metadata"
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_G_cross_brand_packet_refused(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        # catalog where the packet's model display belongs to ANOTHER brand
        catalog = {"brands": {"brandb": {"nameEn": "Brand B", "slug": "brandb"}},
                   "models": {"model-b": {"nameEn": "p120 test model",
                                          "slug": "model-b",
                                          "brandSlug": "brandb",
                                          "brandEn": "Brand B"}}}
        cat_path = tmp_path / "catalog.json"
        cat_path.write_text(json.dumps(catalog), encoding="utf-8")
        empty_u = tmp_path / "empty_universe.json"
        empty_u.write_text(json.dumps({"universe": {"records": []}}),
                           encoding="utf-8")
        pkt = make_packet(marker, brand="P120 Test Brand")
        pkt["candidate_key"] = "p120-test-brand|p120 test model||x"
        path = write_tmp_packets(tmp_path, [pkt])
        kw = worker_kwargs(tmp_path, path)
        kw["catalog_path"] = str(cat_path)
        kw["universe_path"] = str(empty_u)
        res = worker.run_promotion(mode="execute", **kw)
        by_id = {r["packet_id"]: r for r in res["eligibility"]}
        reasons = {r["reason"] for r in by_id[pkt["packet_id"]]["refusals"]}
        assert "CROSS_BRAND_COLLISION" in reasons, reasons
        assert res["writes"] == 0
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_H_conflict_quarantined_packet_refused(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker, status="QUARANTINED")
        pkt["policy"] = {"conflict": "unresolved field conflict"}
        path = write_tmp_packets(tmp_path, [pkt])
        res = worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        by_id = {r["packet_id"]: r for r in res["eligibility"]}
        assert by_id[pkt["packet_id"]]["eligible"] is False
        assert res["writes"] == 0
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == 0
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_I_price_semantics_survive_promotion(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        # a legacy CURRENT price of the same type is already open
        legacy_doc = str(uuid.uuid4())
        src_id = str(uuid.uuid4())
        cur = conn.cursor()
        cur.execute('select id from "Source" where "baseUrl" = %s',
                    ("https://www.toyota.co.th/",))
        got = cur.fetchone()
        if got is not None:
            src_id = got[0]
        else:
            cur.execute('insert into "Source" (id, "nameEn", "nameTh", '
                        '"baseUrl", domain, "sourceType", "updatedAt") '
                        'values (%s,%s,%s,%s,%s,%s, now())',
                        (src_id, "p120-fix-src", "p120-fix-src",
                         "https://www.toyota.co.th/", "www.toyota.co.th",
                         "OFFICIAL_MANUFACTURER"))
        cur.execute('insert into "SourceDocument" (id, "sourceId", url, '
                    '"contentHash", "updatedAt") values (%s,%s,%s,%s, now())',
                    (legacy_doc, src_id, "https://www.toyota.co.th/legacy",
                     hashlib.sha256(b"legacy").hexdigest()))
        cur.execute('insert into "Price" (id, "variantId", "sourceDocumentId", '
                    '"priceType", amount, currency, "validFrom", "isCurrent") '
                    'values (%s,%s,%s,%s,%s,%s,%s,true)',
                    (str(uuid.uuid4()), vid, legacy_doc, "MSRP",
                     "999000", "THB", "2026-01-01 00:00:00"))
        conn.commit()
        pkt = make_packet(marker, price=1234000)
        path = write_tmp_packets(tmp_path, [pkt])
        res = worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        assert res["status"] == "PROMOTED", res
        cur_rows = exec_(conn,
                         'select amount, "priceType", "isCurrent", currency '
                         'from "Price" where "variantId"=%s and "isCurrent"=true',
                         (vid,))
        assert len(cur_rows) == 1, cur_rows
        amount, ptype, is_cur, cur_code = cur_rows[0]
        # evidence semantics: msrp_status EXACT_CURRENT_MSRP_VERIFIED →
        # price_type MSRP + is_current true (P114 PRICE_MAP, reused verbatim)
        assert ptype == "MSRP", ptype
        assert is_cur in (True, 1)
        assert cur_code == "THB"
        assert str(int(float(amount))) == "1234000", amount
        legacy = q1(conn, 'select "isCurrent" from "Price" where id=%s',
                    (legacy_doc and legacy_doc,))  # legacy doc id guard
        old = exec_(conn, 'select "isCurrent" from "Price" where "variantId"=%s '
                    'and amount=%s', (vid, "999000"))
        assert old and old[0][0] is False, \
            "legacy current row must be superseded, not deleted"
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_J_failure_preserves_prior_state(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        snapshot = (q1(conn, 'select count(*) from "Price"'),
                    q1(conn, 'select count(*) from "VariantSpec"'),
                    q1(conn, 'select count(*) from "DataChangeLog"'),
                    q1(conn, 'select count(*) from "Variant"'))
        # a packet that fails eligibility must cause ZERO writes
        bad = make_packet(marker, status="REJECTED")
        path = write_tmp_packets(tmp_path, [bad])
        res = worker.run_promotion(mode="execute", **worker_kwargs(tmp_path, path))
        assert res["writes"] == 0
        after = (q1(conn, 'select count(*) from "Price"'),
                 q1(conn, 'select count(*) from "VariantSpec"'),
                 q1(conn, 'select count(*) from "DataChangeLog"'),
                 q1(conn, 'select count(*) from "Variant"'))
        assert snapshot == after, (snapshot, after)
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_K_transaction_failure_rolls_back(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker)
        path = write_tmp_packets(tmp_path, [pkt])
        kw = worker_kwargs(tmp_path, path)
        snapshot = (q1(conn, 'select count(*) from "Price"'),
                    q1(conn, 'select count(*) from "DataChangeLog"'))
        kw["fail_hook"] = "_raise_after_first_write"   # test seam
        res = worker.run_promotion(mode="execute", **kw)
        assert res["status"] == "FAILED_ROLLED_BACK", res
        assert res["writes"] == 0
        after = (q1(conn, 'select count(*) from "Price"'),
                 q1(conn, 'select count(*) from "DataChangeLog"'))
        assert snapshot == after, (snapshot, after)
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == 0
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_L_rollback_is_bounded_and_auditable(tmp_path):
    worker = require("worker")
    rollback = require("rollback")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker)
        path = write_tmp_packets(tmp_path, [pkt])
        kw = worker_kwargs(tmp_path, path)
        res = worker.run_promotion(mode="execute", **kw)
        assert res["status"] == "PROMOTED", res
        run_id = res["run_id"]
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == 1
        # pre-existing row of ANOTHER fixture must survive the rollback
        rb = rollback.rollback_run(run_id, db_url=p120_db_url(),
                                   out_dir=str(tmp_path / "rb"))
        assert rb["status"] == "ROLLED_BACK", rb
        assert rb["deleted_rows"] >= 1
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == 0
        # rollback itself is auditable: DCL entry + ledger entry exist
        dcl = q1(conn, 'select count(*) from "DataChangeLog" where reason like %s',
                 (f"%{run_id}%rollback%",))
        assert dcl >= 1, "rollback must be recorded in DataChangeLog"
        # second rollback of same run = NO_ACTION (idempotent)
        rb2 = rollback.rollback_run(run_id, db_url=p120_db_url(),
                                    out_dir=str(tmp_path / "rb2"))
        assert rb2["status"] == "NO_ACTION", rb2
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_P_concurrent_invocation_serialized(tmp_path):
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        import fcntl
        pkt = make_packet(marker)
        path = write_tmp_packets(tmp_path, [pkt])
        kw = worker_kwargs(tmp_path, path)
        lock_file = open(kw["lock_path"], "w")
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        res = worker.run_promotion(mode="execute", **kw)
        assert res["status"] == "PROMOTION_LOCKED", res
        assert res["writes"] == 0
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()
        res2 = worker.run_promotion(mode="execute", **kw)
        assert res2["status"] in ("PROMOTED", "NO_ACTION"), res2
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120_Q_no_schema_verifier_provider_changes():
    changed = subprocess.run(
        ["git", "diff", "--name-only", BASE_SHA], cwd=REPO,
        capture_output=True, text=True, timeout=30).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=REPO,
        capture_output=True, text=True, timeout=30).stdout.splitlines()
    forbidden = ("prisma/", "lib/thai_factory/acceptance/",
                 "lib/thai_factory/catalog/verifier.py", "scripts/p114_promote.py",
                 "scripts/p114_verify_promotion.py", "lib/research/",
                 "package.json", ".env", "lib/thai_factory/extract/")
    offending = [f for f in changed + untracked if f.startswith(forbidden)]
    assert not offending, f"P120 must not touch: {offending}"
