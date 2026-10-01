"""
P120-R1 — evidence-integrity repair negative/positive tests (contracts E/F).

Defect on HEAD 6088d93: eligibility.check_observation() let _sidecar_sha_ok()
return None (artifact unresolvable / sidecar missing) WITHOUT refusing, never
hashed the actual artifact bytes against obs.sha256, and never re-resolved a
price locator quote — a crafted ACCEPTED packet could pass eligibility.

Red-before: these tests fail on HEAD 6088d93 (except the sidecar-mismatch pin,
which already refused). All negatives must refuse with EVIDENCE_TAMPERED and
perform ZERO DB writes; the positive proves a real committed artifact +
real sidecar + matching locator still promotes on the ephemeral test DB and
stays idempotent. Production tables are never touched.
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from test_p120_promotion import (  # noqa: E402
    require, db_conn, q1, seed_identity, cleanup_marker, make_packet,
    write_tmp_packets, worker_kwargs, p120_db_url, TEST_DB,
)


def _tmp_fixtures(tmp_path: Path, *, artifact_bytes=b"X",
                  sidecar_sha=None, write_sidecar=True,
                  artifact_name="r1_artifact.html") -> str:
    """Build an isolated fixtures dir with exact evidence properties."""
    root = tmp_path / "fx"
    (root / "oem-artifacts").mkdir(parents=True, exist_ok=True)
    art = root / "oem-artifacts" / artifact_name
    art.write_bytes(artifact_bytes)
    if write_sidecar:
        sha = sidecar_sha if sidecar_sha is not None else \
            hashlib.sha256(artifact_bytes).hexdigest()
        (root / "oem-artifacts" / f"{artifact_name}.prov.json").write_text(
            json.dumps({"sha256": sha, "captured_at":
                        "2026-09-24T18:57:17.345495+00:00"}), encoding="utf-8")
    return str(root)


def _refusal_reasons(res, packet_id):
    by_id = {r["packet_id"]: r for r in res["eligibility"]}
    return {x["reason"] + ":" + x["detail"] for x in by_id[packet_id]["refusals"]}


def _execute_with(tmp_path, packets, fixtures_dir):
    worker = require("worker")
    path = write_tmp_packets(tmp_path, packets)
    kw = worker_kwargs(tmp_path, path)
    kw["fixtures_dir"] = fixtures_dir
    return worker.run_promotion(mode="execute", **kw)


def test_p120r1_N1_missing_artifact_refused_zero_writes(tmp_path):
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker, artifact="definitely_absent.html",
                          sha=hashlib.sha256(b"ghost").hexdigest())
        before = q1(conn, 'select count(*) from "Price" where "variantId"=%s', (vid,))
        res = _execute_with(tmp_path, [pkt], _tmp_fixtures(tmp_path))
        reasons = _refusal_reasons(res, pkt["packet_id"])
        assert any(r.startswith("EVIDENCE_TAMPERED") for r in reasons), reasons
        assert res["writes"] == 0
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == before
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120r1_N2_missing_sidecar_refused_zero_writes(tmp_path):
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        fx = _tmp_fixtures(tmp_path, write_sidecar=False)
        sha = hashlib.sha256(b"X").hexdigest()
        pkt = make_packet(marker, artifact="r1_artifact.html", sha=sha)
        before = q1(conn, 'select count(*) from "Price" where "variantId"=%s', (vid,))
        res = _execute_with(tmp_path, [pkt], fx)
        reasons = _refusal_reasons(res, pkt["packet_id"])
        assert any("EVIDENCE_TAMPERED" in r and "missing_sidecar" in r
                   for r in reasons), reasons
        assert res["writes"] == 0
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == before
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120r1_N3_sidecar_mismatch_refused_zero_writes(tmp_path):
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        # bytes match obs sha; sidecar declares a DIFFERENT sha
        bytes_sha = hashlib.sha256(b"X").hexdigest()
        fx = _tmp_fixtures(tmp_path, artifact_bytes=b"X",
                           sidecar_sha=hashlib.sha256(b"Y").hexdigest())
        pkt = make_packet(marker, artifact="r1_artifact.html", sha=bytes_sha)
        before = q1(conn, 'select count(*) from "Price" where "variantId"=%s', (vid,))
        res = _execute_with(tmp_path, [pkt], fx)
        reasons = _refusal_reasons(res, pkt["packet_id"])
        assert any("EVIDENCE_TAMPERED" in r and "sidecar_sha_mismatch" in r
                   for r in reasons), reasons
        assert res["writes"] == 0
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == before
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120r1_N4_artifact_byte_hash_mismatch_refused_zero_writes(tmp_path):
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        # sidecar matches obs sha, but the actual bytes differ from it
        claimed_sha = hashlib.sha256(b"Y").hexdigest()
        fx = _tmp_fixtures(tmp_path, artifact_bytes=b"X",
                           sidecar_sha=claimed_sha)
        pkt = make_packet(marker, artifact="r1_artifact.html", sha=claimed_sha)
        before = q1(conn, 'select count(*) from "Price" where "variantId"=%s', (vid,))
        res = _execute_with(tmp_path, [pkt], fx)
        reasons = _refusal_reasons(res, pkt["packet_id"])
        assert any("EVIDENCE_TAMPERED" in r and "artifact_byte_hash_mismatch" in r
                   for r in reasons), reasons
        assert res["writes"] == 0
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == before
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120r1_N5_price_locator_quote_mismatch_refused_zero_writes(tmp_path):
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        # real committed artifact + real sidecar (coherent) but a locator
        # quote that does not carry the observation's value
        pkt = make_packet(marker)   # default: real toyota artifact + sidecar
        pkt["observations"]["price"][0]["locator"] = {
            "mode": "value_digits", "quote": "000000", "resolved": True}
        before = q1(conn, 'select count(*) from "Price" where "variantId"=%s', (vid,))
        res = _execute_with(tmp_path, [pkt], str(REPO / "tests" / "fixtures"))
        reasons = _refusal_reasons(res, pkt["packet_id"])
        assert any("EVIDENCE_TAMPERED" in r and "price_locator_quote_mismatch" in r
                   for r in reasons), reasons
        assert res["writes"] == 0
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == before
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120r1_N6_malformed_sidecar_refused(tmp_path):
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        fx = _tmp_fixtures(tmp_path, write_sidecar=False)
        Path(fx, "oem-artifacts", "r1_artifact.html.prov.json").write_text(
            "{not json", encoding="utf-8")
        pkt = make_packet(marker, artifact="r1_artifact.html",
                          sha=hashlib.sha256(b"X").hexdigest())
        res = _execute_with(tmp_path, [pkt], fx)
        reasons = _refusal_reasons(res, pkt["packet_id"])
        assert any("EVIDENCE_TAMPERED" in r and "malformed_sidecar" in r
                   for r in reasons), reasons
        assert res["writes"] == 0
    finally:
        cleanup_marker(conn, marker)
        conn.close()


def test_p120r1_P1_positive_real_artifact_promotes_and_is_idempotent(tmp_path):
    """Real committed artifact + real sidecar + matching locator → promotes
    on the ephemeral DB, rerun is NO_ACTION (idempotent)."""
    worker = require("worker")
    conn = db_conn()
    vid, marker = seed_identity(conn)
    try:
        pkt = make_packet(marker)   # toyota_pricelist_page.html + real sidecar
        path = write_tmp_packets(tmp_path, [pkt])
        kw = worker_kwargs(tmp_path, path)
        kw["fixtures_dir"] = str(REPO / "tests" / "fixtures")
        res1 = worker.run_promotion(mode="execute", **kw)
        assert res1["status"] == "PROMOTED", res1.get("refusals") or res1
        assert res1["writes"] == 1, res1
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == 1
        res2 = worker.run_promotion(mode="execute", **kw)
        assert res2["status"] == "NO_ACTION", res2
        assert res2["writes"] == 0
        assert q1(conn, 'select count(*) from "Price" where "variantId"=%s',
                  (vid,)) == 1
    finally:
        cleanup_marker(conn, marker)
        conn.close()
