"""
P120 — production promotion worker (contract 2, 3, 7, 8, 14, 15).

Lifecycle (state machine from p120_target_plan.json):

  build_preflight (writes MD+JSON BEFORE any write — G8)
    → status FAIL            → PREFLIGHT_FAIL, zero writes
    → dry_run                → DRY_RUN, zero writes
    → flock (non-blocking)   → PROMOTION_LOCKED, zero writes
    → promotable set empty   → NO_ACTION + postflight (counts unchanged)
    → ONE transaction        → PROMOTED (+ postflight) | FAILED_ROLLED_BACK
                               (rollback → pre-transaction state, zero writes)

Reuses (imported read-only, never executed wholesale): p114's ensure_source /
ensure_doc / insert_changelog / record / field_packet / norm / slugify / Ctx /
PRICE_MAP / SPEC_KEY_MAP — record() re-runs the FROZEN AcceptanceRunner before
every ledger write, so the acceptance gate stays the only authority.
No ad-hoc DB writes exist outside the transaction below (contract 14).
"""
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .eligibility import evaluate_packets, load_promoted_facts

REPO = Path(__file__).resolve().parents[3]
DEFAULT_PACKETS = REPO / "audit" / "coverage" / "p113_evidence_packets.json"
DEFAULT_P114_LEDGER = REPO / "audit" / "coverage" / "p114_promotion_ledger.json"
DEFAULT_PROD_LEDGER = REPO / "audit" / "coverage" / "production_promotion_ledger.json"
DEFAULT_LOCK = REPO / "audit" / "coverage" / "p120_promotion.lock"
DEFAULT_CATALOG = REPO / "storage" / "thai-alias-catalog.json"
DEFAULT_UNIVERSE = REPO / "audit" / "coverage" / "identity_universe_p108.json"
DEFAULT_FIXTURES = REPO / "tests" / "fixtures"
CHANGE_REASON = "P120 controlled promotion (preflight PASS)"

_p114 = None


def p114():
    """Import scripts/p114_promote.py read-only (its helpers, never its main)."""
    global _p114
    if _p114 is None:
        spec = importlib.util.spec_from_file_location(
            "p120_p114_helpers", REPO / "scripts" / "p114_promote.py")
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _p114 = mod
    return _p114


def db_url(override: Optional[str] = None) -> str:
    if override:
        return override
    env = os.environ.get("P120_DATABASE_URL")
    if env:
        return env
    txt = (REPO / ".env").read_text(encoding="utf-8")
    m = re.search(r'^DATABASE_URL="([^"]+)"', txt, re.M)
    if not m:
        raise RuntimeError("DATABASE_URL missing")
    return m.group(1).split("?")[0]


def _resolve_db(override: Optional[str] = None) -> str:
    """Module-level db resolution (immune to parameter shadowing)."""
    return db_url(override)


def _sha(path) -> Optional[str]:
    p = Path(path)
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def db_counts(conn) -> Dict[str, int]:
    out = {}
    queries = {
        "variant": 'select count(*) from "Variant"',
        "price": 'select count(*) from "Price"',
        "price_current": 'select count(*) from "Price" where "isCurrent" = true',
        "variantspec": 'select count(*) from "VariantSpec"',
        "datachangelog": 'select count(*) from "DataChangeLog"',
        "source": 'select count(*) from "Source"',
        "sourcedocument": 'select count(*) from "SourceDocument"',
    }
    with conn.cursor() as cur:
        for key, sql in queries.items():
            cur.execute(sql)
            out[key] = cur.fetchone()[0]
    return out


def _connect(url):
    import psycopg2
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


def _load_packets(path: str) -> List[Dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["packets"] if isinstance(data, dict) else data


def _resolve_identities(conn, packets) -> Dict[str, Optional[str]]:
    """Read-only identity resolution: packet → variant id (or None)."""
    m = p114()
    with conn.cursor() as cur:
        cur.execute('select v.id, v."nameEn", c."nameEn", mf."nameEn" '
                    'from "Variant" v join "CarModel" c on v."modelId" = c.id '
                    'join "Manufacturer" mf on c."manufacturerId" = mf.id')
        index = {}
        for vid, vname, cname, mfname in cur.fetchall():
            index.setdefault((m.norm(mfname), m.norm(cname), m.norm(vname)), [])\
                .append(vid)
    resolved = {}
    for p in packets:
        key = (m.norm(p.get("manufacturer")), m.norm(p.get("model")),
               m.norm(p.get("variant")))
        ids = sorted(index.get(key) or [])
        resolved[p.get("packet_id")] = ids[0] if ids else None
    return resolved


def build_preflight(packets_path: str, p114_ledger_path: str,
                    production_ledger_path: str, out_dir: str, *,
                    db: Optional[str] = None, fixtures_dir: str = str(DEFAULT_FIXTURES),
                    catalog_path: Optional[str] = None,
                    universe_path: Optional[str] = None,
                    now: Optional[str] = None, repo_root: Optional[str] = None,
                    write: bool = True) -> Dict[str, Any]:
    """Gate report BEFORE any write. Never touches the DB read-write."""
    now = now or datetime.now(timezone.utc).isoformat()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    input_paths = {
        "packets": packets_path,
        "p114_ledger": p114_ledger_path,
        "production_ledger": production_ledger_path,
        "catalog": catalog_path or str(DEFAULT_CATALOG),
        "universe": universe_path or str(DEFAULT_UNIVERSE),
    }
    pre: Dict[str, Any] = {
        "schema": "p120_preflight_gate/v1",
        "now": now,
        "input_shas": {k: _sha(v) for k, v in input_paths.items()},
        "status": "PASS",
        "error": None,
        "eligibility": [],
        "eligible": 0,
        "promotable_packets": [],
        "refusals": {},
    }
    try:
        packets = _load_packets(packets_path)
        json.loads(Path(p114_ledger_path).read_text(encoding="utf-8"))
        if Path(production_ledger_path).exists():
            json.loads(Path(production_ledger_path).read_text(encoding="utf-8"))
        catalog = json.loads(Path(input_paths["catalog"]).read_text(encoding="utf-8"))
    except Exception as exc:                       # corrupt/missing input → FAIL
        pre["status"] = "FAIL"
        pre["error"] = f"input load failed: {type(exc).__name__}: {exc}"
        if write:
            _write_preflight(pre, out)
        return pre

    promoted = load_promoted_facts(p114_ledger_path, production_ledger_path)
    elig = evaluate_packets(packets, promoted, fixtures_dir=fixtures_dir,
                            catalog=catalog, universe_path=input_paths["universe"])

    conn = None
    try:
        conn = _connect(db_url(db))
        pre["db_counts_before"] = db_counts(conn)
        identity = _resolve_identities(conn, packets)
    except Exception as exc:
        pre["status"] = "FAIL"
        pre["error"] = f"database preflight failed: {type(exc).__name__}: {exc}"
        if write:
            _write_preflight(pre, out)
        if conn:
            conn.close()
        return pre
    finally:
        if conn:
            try:
                conn.rollback()          # read-only preflight
            except Exception:
                pass

    by_packet = {p["packet_id"]: p for p in packets}
    for r in elig:
        pkt = by_packet.get(r["packet_id"]) or {}
        has_identity_refusal = any(
            x["reason"] in ("STATUS_NOT_ACCEPTED", "CONFLICT_QUARANTINED",
                            "CROSS_BRAND_COLLISION") for x in r["refusals"])
        if r["facts"] and not has_identity_refusal:
            if identity.get(r["packet_id"]) is None:
                r["refusals"].append({"reason": "IDENTITY_NOT_RESOLVABLE",
                                      "detail": "no variant matches "
                                                "(manufacturer, model, variant)"})
                r["eligible"] = False
        # unknown price semantics cannot promote
        for fact in r["facts"]:
            if fact["fact"] == "price":
                for obs in fact["obs"]:
                    st = obs.get("msrp_status")
                    if st and st not in p114().PRICE_MAP:
                        r["refusals"].append(
                            {"reason": "RUNNER_REJECTED",
                             "detail": f"unknown msrp_status {st}"})
                        r["eligible"] = False
    for r in elig:
        if r["eligible"]:
            pre["promotable_packets"].append(r["packet_id"])
        for x in r["refusals"]:
            pre["refusals"].setdefault(x["reason"], 0)
            pre["refusals"][x["reason"]] += 1
    pre["eligibility"] = elig
    pre["eligible"] = len(pre["promotable_packets"])
    pre["identity_resolution"] = {k: v for k, v in identity.items()
                                  if k in set(pre["promotable_packets"])}
    if write:
        _write_preflight(pre, out)
    return pre


def _write_preflight(pre: Dict[str, Any], out: Path) -> None:
    (out / "p120_preflight_gate.json").write_text(
        json.dumps(pre, sort_keys=True, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    md = [
        "# P120 promotion preflight gate (BEFORE any write)",
        "",
        f"- status: **{pre['status']}**",
        f"- now: {pre['now']}",
        f"- promotable packets: **{pre.get('eligible', 0)}**",
        f"- refusals: `{json.dumps(pre.get('refusals', {}), ensure_ascii=False)}`",
    ]
    if pre.get("error"):
        md.append(f"- error: `{pre['error']}`")
    if pre.get("db_counts_before"):
        md.append(f"- db counts before: `{json.dumps(pre['db_counts_before'])}`")
    md.append(f"- input shas: `{json.dumps(pre.get('input_shas', {}), sort_keys=True)}`")
    md.append("")
    (out / "p120_preflight_gate.md").write_text("\n".join(md), encoding="utf-8")


def _write_postflight(post: Dict[str, Any], out: Path) -> None:
    (out / "p120_postflight_audit.json").write_text(
        json.dumps(post, sort_keys=True, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    md = [
        "# P120 promotion postflight audit (AFTER writes)",
        "",
        f"- status: **{post['status']}**  run_id: `{post.get('run_id')}`",
        f"- writes: {post.get('writes', 0)}",
        f"- before: `{json.dumps(post.get('before_counts', {}))}`",
        f"- after: `{json.dumps(post.get('after_counts', {}))}`",
        f"- provenance: `{json.dumps(post.get('provenance', {}), ensure_ascii=False)}`",
        f"- actions: `{json.dumps(post.get('actions', []), ensure_ascii=False, default=str)}`",
        "",
    ]
    (out / "p120_postflight_audit.md").write_text("\n".join(md), encoding="utf-8")


def run_promotion(mode: str, packets_path: str, p114_ledger_path: str,
                  production_ledger_path: str, lock_path: str, out_dir: str,
                  fixtures_dir: str = str(DEFAULT_FIXTURES), db_url: Optional[str] = None,
                  now: Optional[str] = None, catalog_path: Optional[str] = None,
                  universe_path: Optional[str] = None, fail_hook: Optional[str] = None,
                  repo_root: Optional[str] = None) -> Dict[str, Any]:
    assert mode in ("dry_run", "execute")
    resolved_db = _resolve_db(db_url)
    now = now or datetime.now(timezone.utc).isoformat()
    out = Path(out_dir)
    pre = build_preflight(packets_path, p114_ledger_path, production_ledger_path,
                          str(out), db=resolved_db, fixtures_dir=fixtures_dir,
                          catalog_path=catalog_path, universe_path=universe_path,
                          now=now, repo_root=repo_root)
    result_base = {"preflight": str(out / "p120_preflight_gate.json"),
                   "eligibility": pre["eligibility"],
                   "refusals": pre.get("refusals", {}),
                   "writes": 0}

    if pre["status"] != "PASS":
        return {"status": "PREFLIGHT_FAIL", **result_base}
    if mode == "dry_run":
        return {"status": "DRY_RUN", **result_base,
                "eligible": pre["eligible"]}

    # ── serialize: concurrent/double invocation (contract P) ───────────────
    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    lock_fh = open(lock_path, "a+")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_fh.close()
        return {"status": "PROMOTION_LOCKED", **result_base}

    try:
        promotable = [r for r in pre["eligibility"] if r["eligible"]]
        if not promotable:
            post = {
                "schema": "p120_postflight_audit/v1", "status": "NO_ACTION",
                "run_id": None, "writes": 0,
                "before_counts": pre["db_counts_before"],
                "after_counts": pre["db_counts_before"],
                "provenance": {"rows_with_packet_sha": 0},
                "actions": [], "now": now,
            }
            _write_postflight(post, out)
            return {"status": "NO_ACTION", "run_id": None, **result_base,
                    "postflight": str(out / "p120_postflight_audit.json")}

        m = p114()
        packets = {p["packet_id"]: p for p in _load_packets(packets_path)}
        run_id = "P120-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") \
                 + "-" + uuid.uuid4().hex[:6]
        conn = _connect(resolved_db)
        before = db_counts(conn)
        ledger = m.AcceptanceLedger()
        runner = m.AcceptanceRunner()
        ctx = m.Ctx()
        actions: List[Dict[str, Any]] = []
        writes = 0
        created_docs: List[str] = []
        rollback_error: Optional[str] = None
        try:
            cur = conn.cursor()
            identity = _resolve_identities(conn, [packets[r["packet_id"]]
                                                  for r in promotable])
            host_map: Dict[str, Any] = {}
            from urllib.parse import urlparse
            cur.execute('select id, "baseUrl" from "Source"')
            for sid, base in cur.fetchall():
                host_map[urlparse(base).netloc] = sid
            doc_cache: Dict[tuple, Any] = {}

            def ts3(cap: Optional[str]) -> Optional[str]:
                """timestamp(3) without offset (p114 precision lesson)."""
                if not cap:
                    return None
                return str(cap).replace("T", " ").split("+")[0][:23]

            for r in promotable:
                p = packets[r["packet_id"]]
                pid = p["packet_id"]
                vid = identity.get(pid)
                if vid is None:
                    raise RuntimeError(f"identity lost for {pid}")
                for fact in r["facts"]:
                    group = fact["fact"]
                    obs_list = fact["obs"]
                    # sources + documents (shared infra; DCL-tracked per run)
                    for o in obs_list:
                        key = (o["source_url"], o["sha256"])
                        if key in doc_cache:
                            continue
                        sid = m.ensure_source(cur, host_map, o["source_url"],
                                              p["manufacturer"], ctx)
                        cap = None
                        for side in (Path(fixtures_dir) / f"{o['artifact']}.prov.json",
                                     Path(fixtures_dir) / "oem-artifacts"
                                     / f"{o['artifact']}.prov.json",
                                     Path(fixtures_dir) / "media-artifacts"
                                     / f"{o['artifact']}.prov.json"):
                            if side.exists():
                                cap = json.loads(side.read_text(encoding="utf-8")) \
                                    .get("captured_at")
                                break
                        if cap is None:
                            cap = packet_capture_date = p.get("observed_at")
                        else:
                            packet_capture_date = cap
                        did, created = m.ensure_doc(cur, ctx, sid, o["source_url"],
                                                    o["sha256"], o["artifact"], cap)
                        doc_cache[key] = (did, cap)
                        if created:
                            created_docs.append(did)
                            m.insert_changelog(
                                cur, ctx, "SourceDocument", did, "CREATED", did,
                                f"{CHANGE_REASON} run {run_id} — source document",
                                {"packet_id": pid, "sha256": o["sha256"],
                                 "source_url": o["source_url"], "run_id": run_id},
                                {"url": o["source_url"]})

                    if group == "price":
                        for o in obs_list:
                            sem = m.PRICE_MAP[o["msrp_status"]]
                            did, cap = doc_cache[(o["source_url"], o["sha256"])]
                            valid_from = ts3(cap)
                            if valid_from is None:
                                valid_from = ts3(p.get("observed_at"))
                            if valid_from is None:
                                raise RuntimeError(
                                    "no dated capture evidence for validFrom — "
                                    "refusing to invent a timestamp")
                            if sem["is_current"]:
                                cur.execute(
                                    'select id from "Price" where "variantId" = %s '
                                    'and "priceType" = %s and "isCurrent" = true',
                                    (vid, sem["price_type"]))
                                for (old_id,) in cur.fetchall():
                                    cur.execute(
                                        'update "Price" set "isCurrent" = false '
                                        'where id = %s', (old_id,))
                                    m.insert_changelog(
                                        cur, ctx, "Price", old_id, "UPDATED", did,
                                        f"{CHANGE_REASON} run {run_id} — legacy current superseded",
                                        {"packet_id": pid, "run_id": run_id,
                                         "sha256": o["sha256"]},
                                        {"isCurrent": False},
                                        before_value={"isCurrent": True})
                            cur.execute(
                                'insert into "Price" (id, "variantId", '
                                '"sourceDocumentId", "priceType", amount, '
                                'currency, "validFrom", "observedAt", confidence, '
                                '"isCurrent") values (%s,%s,%s,%s,%s,\'THB\',%s,'
                                'now(),%s,%s) on conflict ("variantId",'
                                '"sourceDocumentId","priceType",amount,"validFrom") '
                                'do nothing returning id',
                                (str(uuid.uuid4()), vid, did,
                                 sem["price_type"], str(o["value"]), valid_from,
                                 m.CONFIDENCE_MAP[o["trust_tier"]],
                                 sem["is_current"]))
                            row = cur.fetchone()
                            if row:
                                rid, action = row[0], "INSERT"
                                writes += 1
                                m.insert_changelog(
                                    cur, ctx, "Price", rid, "CREATED", did,
                                    f"{CHANGE_REASON} run {run_id} — packet {pid}",
                                    {"packet_id": pid, "run_id": run_id,
                                     "sha256": o["sha256"],
                                     "artifact": o["artifact"],
                                     "source_url": o["source_url"],
                                     "locator": o.get("locator")},
                                    {"priceType": sem["price_type"],
                                     "amount": o["value"],
                                     "isCurrent": sem["is_current"]},
                                    excerpt=(o.get("locator") or {}).get("quote"))
                            else:
                                cur.execute(
                                    'select id from "Price" where "variantId" = %s '
                                    'and "sourceDocumentId" = %s and "priceType" = %s '
                                    'and amount = %s and "validFrom" = %s',
                                    (vid, did, sem["price_type"],
                                     str(o["value"]), valid_from))
                                got = cur.fetchone()
                                assert got is not None, "NO_ACTION price row must exist"
                                rid, action = got[0], "NO_ACTION"
                            fp = m.field_packet(
                                pid, "price", p["candidate_key"],
                                {"source_url": o["source_url"],
                                 "source_name": o.get("source_name")},
                                {"price_thb": o["value"],
                                 "price_type": o["price_type"]},
                                m.EvidenceLocator(
                                    artifact_path=f"tests/fixtures/oem-artifacts/"
                                                  f"{o['artifact']}",
                                    quote=str((o.get("locator") or {}).get("quote")
                                              or o["value"])),
                                o["sha256"], m.CurrentnessState.CURRENT)
                            m.record(ledger, runner, fp, "price", action, rid,
                                     {"price_type": sem["price_type"],
                                      "is_current": sem["is_current"],
                                      "amount": o["value"]},
                                     {"msrp_status": o["msrp_status"],
                                      "evidence_id": o["obs_id"],
                                      "source_document_id": did},
                                     base_pid=pid)
                            actions.append({"packet_id": pid, "fact": "price",
                                            "action": action, "row_id": rid})
                            if fail_hook == "_raise_after_first_write" and writes:
                                raise RuntimeError("injected transaction failure")

                    elif group == "spec":
                        for o in obs_list:
                            did, _cap = doc_cache[(o["source_url"], o["sha256"])]
                            key = m.SPEC_KEY_MAP.get(o.get("field_key"),
                                                     o.get("field_key"))
                            vt = o.get("value_text")
                            vn = o.get("value_numeric")
                            cur.execute(
                                'insert into "VariantSpec" (id, "variantId", '
                                '"sourceDocumentId", key, "valueTh", "valueEn", '
                                '"valueNumeric", unit, confidence) values '
                                '(%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict '
                                '("variantId",key,"sourceDocumentId") do nothing '
                                'returning id',
                                (str(uuid.uuid4()), vid, did, key, vt, vt,
                                 (str(vn) if vn is not None else None),
                                 o.get("unit"),
                                 m.CONFIDENCE_MAP[o["trust_tier"]]))
                            row = cur.fetchone()
                            if row:
                                rid, action = row[0], "INSERT"
                                writes += 1
                                m.insert_changelog(
                                    cur, ctx, "VariantSpec", rid, "CREATED", did,
                                    f"{CHANGE_REASON} run {run_id} — packet {pid}",
                                    {"packet_id": pid, "run_id": run_id,
                                     "sha256": o["sha256"],
                                     "artifact": o["artifact"],
                                     "source_url": o["source_url"],
                                     "locator": o.get("locator")},
                                    {"key": key, "value_text": vt},
                                    excerpt=(o.get("locator") or {}).get("quote"))
                            else:
                                cur.execute(
                                    'select id from "VariantSpec" where '
                                    '"variantId" = %s and key = %s and '
                                    '"sourceDocumentId" = %s',
                                    (vid, key, did))
                                got = cur.fetchone()
                                assert got is not None, "NO_ACTION spec row must exist"
                                rid, action = got[0], "NO_ACTION"
                            fp = m.field_packet(
                                pid, "spec", p["candidate_key"],
                                {"source_url": o["source_url"],
                                 "source_name": o.get("source_name")},
                                {"spec": key, "value": vt},
                                m.EvidenceLocator(
                                    artifact_path=f"tests/fixtures/oem-artifacts/"
                                                  f"{o['artifact']}",
                                    quote=str((o.get("locator") or {}).get("quote")
                                              or vt)),
                                o["sha256"], m.CurrentnessState.CURRENT)
                            m.record(ledger, runner, fp, "spec", action, rid,
                                     {"key": key}, {"evidence_id": o["obs_id"],
                                                    "source_document_id": did},
                                     base_pid=pid)
                            actions.append({"packet_id": pid, "fact": "spec",
                                            "action": action, "row_id": rid})
                            if fail_hook == "_raise_after_first_write" and writes:
                                raise RuntimeError("injected transaction failure")

                    elif group == "identity":
                        for o in obs_list:
                            did, _cap = doc_cache[(o["source_url"], o["sha256"])]
                            fp = m.field_packet(
                                pid, "identity", p["candidate_key"],
                                {"source_url": o["source_url"],
                                 "source_name": o.get("source_name")},
                                {"label": o.get("label")},
                                m.EvidenceLocator(
                                    artifact_path=f"tests/fixtures/oem-artifacts/"
                                                  f"{o['artifact']}",
                                    quote=str((o.get("locator") or {}).get("quote")
                                              or o.get("label"))),
                                o["sha256"], m.CurrentnessState.CURRENT)
                            m.record(ledger, runner, fp, "identity", "NO_ACTION",
                                     vid, {"label": o.get("label")},
                                     {"evidence_id": o.get("obs_id"),
                                      "source_document_id": did},
                                     base_pid=pid)
                            actions.append({"packet_id": pid, "fact": "identity",
                                            "action": "NO_ACTION", "row_id": vid})

            conn.commit()
            status = "PROMOTED"
        except Exception as exc:
            conn.rollback()
            status = "FAILED_ROLLED_BACK"
            rollback_error = f"{type(exc).__name__}: {exc}"
            writes = 0
            actions = []
        finally:
            try:
                after = db_counts(conn)
            except Exception:
                after = before
            conn.close()

        prov_rows = 0
        if status == "PROMOTED":
            prov_rows = writes
            # production ledger written AFTER commit (p114 pattern)
            existing = []
            if Path(production_ledger_path).exists():
                existing = json.loads(Path(production_ledger_path)
                                      .read_text(encoding="utf-8"))["entries"]
            Path(production_ledger_path).parent.mkdir(parents=True, exist_ok=True)
            Path(production_ledger_path).write_text(json.dumps({
                "schema": "production_promotion_ledger/v1",
                "generated_at": now, "run_id": run_id,
                "append_only": True,
                "entries": existing + ledger.entries,
            }, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        post = {
            "schema": "p120_postflight_audit/v1",
            "status": status,
            "run_id": run_id if status == "PROMOTED" else None,
            "writes": writes,
            "before_counts": before,
            "after_counts": after,
            "provenance": {"rows_with_packet_sha": prov_rows,
                           "change_reason": CHANGE_REASON,
                           "ledger_entries_written": len(ledger.entries)
                           if status == "PROMOTED" else 0},
            "actions": actions,
            "error": None if status == "PROMOTED" else rollback_error,
            "now": now,
        }
        _write_postflight(post, out)
        # result_base carries writes:0 — spread it FIRST so the real count wins
        res = {**result_base, "status": status, "writes": writes,
               "run_id": post["run_id"],
               "postflight": str(out / "p120_postflight_audit.json")}
        if status == "FAILED_ROLLED_BACK":
            res["error"] = rollback_error
        return res
    finally:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        finally:
            lock_fh.close()
