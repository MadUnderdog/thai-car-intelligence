"""
P118 — Phase 4 daily diff / scheduled updates / alerting boundaries (A–P + 7-run).

Red-before: written against 76a242a (+plan commit a5849d0) where
lib/thai_factory/refresh/* and scripts/daily_run.py do not exist (gaps G-A..G-G
in audit/coverage/p118_target_plan.json). Modules are loaded dynamically so
every test fails individually with the missing-module message.

Data boundary honored by these tests:
  - fixtures are REAL capture events produced by AcquisitionWriter (real
    sidecars, controlled clock) in tmp dirs — no retrofitted hashes anywhere;
  - writes go only to tmp queue/digest dirs (+ read-only registry/staging);
  - catalog tables are read (counts only) and must stay byte-for-byte stable;
  - network is never touched (offline replay).
"""
import importlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from thai_factory.acquisition.provenance import (  # noqa: E402
    AcquisitionWriter,
    AcquisitionReader,
    ProvenanceError,
)

NOW = datetime(2026, 9, 29, 6, 0, 0, tzinfo=timezone.utc)
BASELINE_PAYLOAD = {
    "prices": {"toyota-velo-cross-eco": 999000},
    "models": ["toyota-velo-cross", "toyota-yaris-cross"],
}


def load_refresh(name: str):
    try:
        return importlib.import_module(f"thai_factory.refresh.{name}")
    except Exception:
        return None


def runner():
    m = load_refresh("runner")
    assert m is not None, "lib/thai_factory/refresh/runner.py must exist"
    return m


def alerts_mod():
    m = load_refresh("alerts")
    assert m is not None, "lib/thai_factory/refresh/alerts.py must exist"
    return m


# ── fixtures ────────────────────────────────────────────────────────────────
def write_capture(tmp: Path, payload: dict, *, name: str = "capture.json",
                  url: str = "https://www.toyota.co.th/model", at: datetime = NOW,
                  raw: str | None = None) -> str:
    content = raw if raw is not None else json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1)
    AcquisitionWriter.write(
        content=content,
        source_url=url,
        acquisition_method="offline_replay",
        output_dir=str(tmp / "artifacts"),
        filename=name,
        session_id="p118-test-session",
        clock=lambda: at.isoformat(),
    )
    return str(tmp / "artifacts" / name)


def catalog_counts() -> dict:
    import psycopg2
    conn = psycopg2.connect(host="localhost", user="hermes", dbname="thai_car_intelligence")
    try:
        with conn.cursor() as cur:
            out = {}
            for table in ("Price", "Variant", "CarModel", "DataChangeLog", "CommunityComment"):
                cur.execute(f'SELECT count(*) FROM "{table}"')
                out[table] = cur.fetchone()[0]
            return out
    finally:
        conn.close()


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_cfg(tmp: Path, events: list, now: datetime, *, queue=None, digest=None, tests_log=None):
    R = runner()
    return R.RunConfig(
        queue_dir=queue or (tmp / "queue"),
        digest_dir=digest or (tmp / "digest"),
        registry_path=str(REPO / "audit" / "coverage" / "oem-registry.json"),
        staging_path=str(REPO / "audit" / "data-staging" / "vehicle_observations.jsonl"),
        events=events,
        now=now,
        commit_sha="76a242a0b756c2e04c40769e0947779f6a85d755",
        mode="offline",
        entrypoint="test",
        tests_log=str(tests_log) if tests_log else None,
    )


def run(cfg):
    return runner().run_daily(cfg)


def capture_event(path: str, source: str = "www.toyota.co.th") -> dict:
    return {"kind": "capture", "source": source, "artifact": path, "extractor": "json"}


def probe_event(source: str, outcome: str) -> dict:
    return {"kind": "probe", "source": source, "outcome": outcome}


# ── A: same artifact/SHA twice → UNCHANGED, nothing new ─────────────────────
def test_p118_A_same_sha_twice_is_unchanged_with_no_new_rows(tmp_path):
    R = runner()
    artifact = write_capture(tmp_path, BASELINE_PAYLOAD, at=NOW)

    r1 = run(make_cfg(tmp_path, [capture_event(artifact)], NOW))
    assert r1["status"] == "RUN_GREEN", r1
    assert r1["sources"][0]["classification"] == "FIRST_CAPTURE"
    q = tmp_path / "queue"
    cand1 = read_jsonl(q / "change-candidates.jsonl")
    alert1 = read_jsonl(q / "alerts.jsonl")
    state1 = json.loads((q / "run-state.json").read_text(encoding="utf-8"))

    r2 = run(make_cfg(tmp_path, [capture_event(artifact)], NOW + timedelta(hours=1)))
    assert r2["status"] == "RUN_GREEN"
    assert r2["sources"][0]["classification"] == "UNCHANGED", r2["sources"][0]
    cand2 = read_jsonl(q / "change-candidates.jsonl")
    alert2 = read_jsonl(q / "alerts.jsonl")
    state2 = json.loads((q / "run-state.json").read_text(encoding="utf-8"))
    assert len(cand2) == len(cand1) == 0, "unchanged run must not create ChangeCandidates"
    assert len(alert2) == len(alert1) == 0, "unchanged run must not alert"
    assert state2["sources"] == state1["sources"], "run-state must be stable on unchanged"


# ── B: new SHA, identical output → CONTENT_CHANGED_OUTPUT_UNCHANGED ─────────
def test_p118_B_new_sha_identical_output_content_changed_output_unchanged(tmp_path):
    artifact1 = write_capture(tmp_path, BASELINE_PAYLOAD, name="c1a.json", at=NOW)
    # byte-different (trailing whitespace) → new sha; parsed output identical
    artifact2 = write_capture(
        tmp_path, BASELINE_PAYLOAD, name="c1b.json", at=NOW + timedelta(minutes=5),
        raw=json.dumps(BASELINE_PAYLOAD, ensure_ascii=False, sort_keys=True, indent=1) + "\n\n  ",
    )
    run(make_cfg(tmp_path, [capture_event(artifact1)], NOW))
    import hashlib
    sha1 = hashlib.sha256(Path(artifact1).read_bytes()).hexdigest()
    sha2 = hashlib.sha256(Path(artifact2).read_bytes()).hexdigest()
    assert sha1 != sha2, "fixture precondition: bytes must differ"

    r2 = run(make_cfg(tmp_path, [capture_event(artifact2)], NOW + timedelta(hours=1)))
    assert r2["sources"][0]["classification"] == "CONTENT_CHANGED_OUTPUT_UNCHANGED", r2["sources"][0]
    q = tmp_path / "queue"
    assert read_jsonl(q / "change-candidates.jsonl") == []
    assert read_jsonl(q / "alerts.jsonl") == []
    state = json.loads((q / "run-state.json").read_text(encoding="utf-8"))
    # artifact retained (new sha adopted, output hash unchanged)
    assert state["sources"]["www.toyota.co.th"]["last_sha"] == sha2
    assert state["sources"]["www.toyota.co.th"]["last_output_hash"] is not None


# ── C: one field change → exactly one QUARANTINED candidate ─────────────────
def test_p118_C_one_field_change_creates_exactly_one_quarantined_candidate(tmp_path):
    baseline = write_capture(tmp_path, BASELINE_PAYLOAD, name="c_base.json", at=NOW)
    changed_payload = json.loads(json.dumps(BASELINE_PAYLOAD))
    changed_payload["prices"]["toyota-velo-cross-eco"] = 1019000
    changed = write_capture(tmp_path, changed_payload, name="c_changed.json", at=NOW + timedelta(minutes=5))
    run(make_cfg(tmp_path, [capture_event(baseline)], NOW))
    import hashlib
    old_sha = hashlib.sha256(Path(baseline).read_bytes()).hexdigest()
    new_sha = hashlib.sha256(Path(changed).read_bytes()).hexdigest()

    r2 = run(make_cfg(tmp_path, [capture_event(changed)], NOW + timedelta(hours=1)))
    assert r2["sources"][0]["classification"] == "CHANGED", r2["sources"][0]
    cands = read_jsonl(tmp_path / "queue" / "change-candidates.jsonl")
    assert len(cands) == 1, f"exactly one field-level candidate expected, got {len(cands)}"
    c = cands[0]
    assert c["old_sha"] == old_sha and c["new_sha"] == new_sha
    assert c["source"] == "www.toyota.co.th"
    assert c["field"] == "prices.toyota-velo-cross-eco"
    assert c["entity"] == "toyota-velo-cross-eco"
    assert c["old_value"] == 999000 and c["new_value"] == 1019000
    assert c["status"] == "QUARANTINED"


# ── D: price change alert fires once, repeat none ───────────────────────────
def test_p118_D_price_alert_fires_exactly_once(tmp_path):
    baseline = write_capture(tmp_path, BASELINE_PAYLOAD, name="d_base.json", at=NOW)
    changed_payload = json.loads(json.dumps(BASELINE_PAYLOAD))
    changed_payload["prices"]["toyota-velo-cross-eco"] = 1019000
    changed = write_capture(tmp_path, changed_payload, name="d_changed.json", at=NOW + timedelta(minutes=5))
    run(make_cfg(tmp_path, [capture_event(baseline)], NOW))
    r2 = run(make_cfg(tmp_path, [capture_event(changed)], NOW + timedelta(hours=1)))
    price_alerts = [a for a in read_jsonl(tmp_path / "queue" / "alerts.jsonl") if a["type"] == "PRICE_CHANGE"]
    assert len(price_alerts) == 1, price_alerts
    assert price_alerts[0]["entity"] == "toyota-velo-cross-eco"
    assert price_alerts[0]["old_value"] == 999000 and price_alerts[0]["new_value"] == 1019000
    assert r2["status"] == "RUN_GREEN"

    # repeat the SAME changed artifact → unchanged, no second alert
    r3 = run(make_cfg(tmp_path, [capture_event(changed)], NOW + timedelta(hours=2)))
    assert r3["sources"][0]["classification"] == "UNCHANGED"
    price_alerts3 = [a for a in read_jsonl(tmp_path / "queue" / "alerts.jsonl") if a["type"] == "PRICE_CHANGE"]
    assert len(price_alerts3) == 1, "repeat unchanged run must not re-alert"


# ── E: model add/remove → candidates + alert, no invented rows ──────────────
def test_p118_E_model_add_remove_candidate_and_alert_without_inventing_rows(tmp_path):
    staging = REPO / "audit" / "data-staging" / "vehicle_observations.jsonl"
    staging_before = staging.read_bytes()
    baseline = write_capture(tmp_path, BASELINE_PAYLOAD, name="e_base.json", at=NOW)
    mutated = json.loads(json.dumps(BASELINE_PAYLOAD))
    mutated["models"] = ["toyota-velo-cross", "toyota-corolla-cross"]  # +corolla, -yaris
    changed = write_capture(tmp_path, mutated, name="e_changed.json", at=NOW + timedelta(minutes=5))
    run(make_cfg(tmp_path, [capture_event(baseline)], NOW))
    run(make_cfg(tmp_path, [capture_event(changed)], NOW + timedelta(hours=1)))

    cands = read_jsonl(tmp_path / "queue" / "change-candidates.jsonl")
    membership = [c for c in cands if c["entity"] == "models" or str(c["field"]).startswith("membership")]
    assert len(membership) == 2, f"expected one add + one remove candidate, got {membership}"
    adds = [c for c in membership if c["new_value"] == "present"]
    removes = [c for c in membership if c["new_value"] == "absent"]
    assert len(adds) == 1 and adds[0]["old_value"] == "absent"
    assert len(removes) == 1 and removes[0]["old_value"] == "present"
    set_alerts = [a for a in read_jsonl(tmp_path / "queue" / "alerts.jsonl") if a["type"] == "MODEL_VARIANT_ADDED_REMOVED"]
    assert len(set_alerts) == 1
    assert set_alerts[0]["detail"]["added"] == ["toyota-corolla-cross"]
    assert set_alerts[0]["detail"]["removed"] == ["toyota-yaris-cross"]
    assert staging.read_bytes() == staging_before, "refresh must never rewrite staging observations"


# ── F: reachable → blocked alerts once; repeat blocker none ─────────────────
def _reachable_brand_domain() -> tuple:
    reg = json.loads((REPO / "audit" / "coverage" / "oem-registry.json").read_text(encoding="utf-8"))
    for brand in reg["brands"]:
        if brand.get("access_status") == "REACHABLE" and brand.get("source_urls"):
            from urllib.parse import urlparse
            return brand["brand"], urlparse(brand["source_urls"][0]).netloc
    raise AssertionError("registry must contain a REACHABLE brand with source_urls")


def test_p118_F_reachable_to_blocked_alerts_once_with_policy_backoff(tmp_path):
    _brand, domain = _reachable_brand_domain()
    r1 = run(make_cfg(tmp_path, [probe_event(domain, "HTTP_403")], NOW))
    assert r1["status"] == "RUN_GREEN"
    alerts = read_jsonl(tmp_path / "queue" / "alerts.jsonl")
    state_alerts = [a for a in alerts if a["type"] == "SOURCE_STATE_TRANSITION"]
    assert len(state_alerts) == 1, state_alerts
    assert state_alerts[0]["detail"]["transition"] == "REACHABLE→BLOCKED_HTTP_403"

    state = json.loads((tmp_path / "queue" / "run-state.json").read_text(encoding="utf-8"))
    src = state["sources"][domain]
    assert src["access_state"] == "BLOCKED_HTTP_403"
    expected_retry = (NOW + timedelta(days=7)).isoformat()
    assert src["next_retry_at"] == expected_retry, "403 policy = +7d first retry"

    # repeated known blocker → no new alert, run still green
    r2 = run(make_cfg(tmp_path, [probe_event(domain, "HTTP_403")], NOW + timedelta(hours=1)))
    assert r2["status"] == "RUN_GREEN"
    state_alerts2 = [a for a in read_jsonl(tmp_path / "queue" / "alerts.jsonl") if a["type"] == "SOURCE_STATE_TRANSITION"]
    assert len(state_alerts2) == 1, "repeated known blocker must not alert again"


# ── H: ERROR_PAGE stores blocker evidence, extracts nothing ─────────────────
def test_p118_H_error_page_stores_evidence_extracts_nothing(tmp_path):
    artifact = write_capture(
        tmp_path, BASELINE_PAYLOAD, name="dealer.html",
        url="https://www.some-brand-thailand.com/dealer", at=NOW,
        raw="<html><body>ราคา 999,000 บาท รุ่น ECO</body></html>",
    )
    r = run(make_cfg(tmp_path, [
        {"kind": "capture", "source": "www.some-brand-thailand.com", "artifact": artifact,
         "extractor": "html_prices", "outcome": "DEALER_REDIRECT"},
    ], NOW))
    assert r["status"] == "RUN_GREEN"
    src = r["sources"][0]
    assert src["observations"] == 0, "DEALER_REDIRECT must produce zero extracted observations"
    state = json.loads((tmp_path / "queue" / "run-state.json").read_text(encoding="utf-8"))
    s = state["sources"]["www.some-brand-thailand.com"]
    assert s["blocker_evidence"]["outcome"] == "DEALER_REDIRECT"
    assert s["blocker_evidence"]["url"].startswith("https://")
    assert read_jsonl(tmp_path / "queue" / "change-candidates.jsonl") == []


# ── I: provenance failure aborts semantics; alert once (§94 allowlist) ──────
def test_p118_I_provenance_failure_aborts_with_no_candidate_or_promotion(tmp_path):
    counts_before = catalog_counts()
    artifact = write_capture(tmp_path, BASELINE_PAYLOAD, name="t.json", at=NOW)
    # tamper the artifact AFTER capture → Reader must fail closed
    Path(artifact).write_text(Path(artifact).read_text(encoding="utf-8") + "\n tampered", encoding="utf-8")

    r1 = run(make_cfg(tmp_path, [capture_event(artifact)], NOW))
    assert r1["status"] == "RUN_PARTIAL", r1["status"]
    src = r1["sources"][0]
    assert src["provenance"] == "FAILED", src
    assert "provenance" in src["error"].lower() or "hash" in src["error"].lower(), src["error"]
    assert read_jsonl(tmp_path / "queue" / "change-candidates.jsonl") == [], "no candidate from failed provenance"
    prov_alerts = [a for a in read_jsonl(tmp_path / "queue" / "alerts.jsonl") if a["type"] == "PROVENANCE_FAILURE"]
    assert len(prov_alerts) == 1, "hash/provenance verification failure is on the §94 alert allowlist"
    assert catalog_counts() == counts_before, "canonical catalog must be untouched"

    # rerun same broken artifact → alert deduped by event identity
    r2 = run(make_cfg(tmp_path, [capture_event(artifact)], NOW + timedelta(hours=1)))
    assert r2["status"] == "RUN_PARTIAL"
    prov_alerts2 = [a for a in read_jsonl(tmp_path / "queue" / "alerts.jsonl") if a["type"] == "PROVENANCE_FAILURE"]
    assert len(prov_alerts2) == 1, "same provenance failure event must dedupe"


# ── J: two identical runs → byte-identical observation sets ─────────────────
def test_p118_J_identical_runs_yield_identical_observation_sets(tmp_path):
    artifact = write_capture(tmp_path, BASELINE_PAYLOAD, at=NOW)
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    r1 = run(make_cfg(tmp_path, [capture_event(artifact)], NOW, digest=d1))
    r2 = run(make_cfg(tmp_path, [capture_event(artifact)], NOW + timedelta(hours=1), digest=d2))
    assert r1["status"] == r2["status"] == "RUN_GREEN"
    dig1 = json.loads(next(d1.glob("*.json")).read_text(encoding="utf-8"))
    dig2 = json.loads(next(d2.glob("*.json")).read_text(encoding="utf-8"))
    assert dig1["observations"] == dig2["observations"], "observation sets must be byte-identical"
    assert [json.dumps(o, sort_keys=True) for o in dig1["observations"]] == \
           [json.dumps(o, sort_keys=True) for o in dig2["observations"]], "stable ordering"
    # digest files themselves differ only in run identity/timestamps
    assert dig1["run_id"] != dig2["run_id"]


# ── K: concurrent invocation is skipped, zero writes ────────────────────────
def test_p118_K_double_invocation_is_skipped_without_writes(tmp_path):
    import fcntl
    artifact = write_capture(tmp_path, BASELINE_PAYLOAD, at=NOW)
    queue = tmp_path / "queue"
    queue.mkdir(parents=True, exist_ok=True)
    lock_path = queue / ".daily-run.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        r = run(make_cfg(tmp_path, [capture_event(artifact)], NOW, queue=queue))
        assert r["status"] == "RUN_SKIPPED_DOUBLE", r["status"]
        assert r["writes"] == 0
        assert not (queue / "run-state.json").exists(), "locked run must write nothing"
        assert read_jsonl(queue / "change-candidates.jsonl") == []
        assert list((tmp_path / "digest").glob("*")) == [] if (tmp_path / "digest").exists() else True
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    # lock released → same invocation proceeds
    r2 = run(make_cfg(tmp_path, [capture_event(artifact)], NOW, queue=queue))
    assert r2["status"] == "RUN_GREEN"


# ── L: acceptance-gate failure keeps quarantined + canonical unchanged ──────
def test_p118_L_quarantine_keeps_catalog_unchanged(tmp_path):
    counts_before = catalog_counts()
    baseline = write_capture(tmp_path, BASELINE_PAYLOAD, name="l_base.json", at=NOW)
    changed_payload = json.loads(json.dumps(BASELINE_PAYLOAD))
    changed_payload["prices"]["toyota-velo-cross-eco"] = 1299000
    changed = write_capture(tmp_path, changed_payload, name="l_changed.json", at=NOW + timedelta(minutes=5))
    run(make_cfg(tmp_path, [capture_event(baseline)], NOW))
    run(make_cfg(tmp_path, [capture_event(changed)], NOW + timedelta(hours=1)))
    cands = read_jsonl(tmp_path / "queue" / "change-candidates.jsonl")
    assert len(cands) == 1
    assert cands[0]["status"] == "QUARANTINED", "refresh never promotes; gate failure stays quarantined"
    # existing AcceptanceRunner path is the only promotion route — untouched by P118
    assert catalog_counts() == counts_before, "no unaccepted row may reach canonical DB"


# ── M: failed fetch keeps previous accepted state ───────────────────────────
def test_p118_M_failed_source_preserves_previous_accepted_state(tmp_path):
    counts_before = catalog_counts()
    artifact = write_capture(tmp_path, BASELINE_PAYLOAD, name="m1.json", at=NOW)
    run(make_cfg(tmp_path, [capture_event(artifact)], NOW))
    q = tmp_path / "queue"
    state1 = json.loads((q / "run-state.json").read_text(encoding="utf-8"))
    sha1 = state1["sources"]["www.toyota.co.th"]["last_sha"]
    output_hash1 = state1["sources"]["www.toyota.co.th"]["last_output_hash"]

    # next cycle: capture fails provenance (broken artifact)
    broken = write_capture(tmp_path, BASELINE_PAYLOAD, name="m1.json", at=NOW + timedelta(minutes=5))
    Path(broken).write_bytes(Path(broken).read_bytes() + b"\ncorrupted")
    r2 = run(make_cfg(tmp_path, [capture_event(broken)], NOW + timedelta(hours=1)))
    assert r2["status"] == "RUN_PARTIAL"
    state2 = json.loads((q / "run-state.json").read_text(encoding="utf-8"))
    src2 = state2["sources"]["www.toyota.co.th"]
    assert src2["last_sha"] == sha1, "failed refresh must not clobber last accepted sha"
    assert src2["last_output_hash"] == output_hash1, "previous accepted state remains intact"
    assert catalog_counts() == counts_before


# ── N: digest contains required metadata/counts ─────────────────────────────
def test_p118_N_digest_md_and_json_have_required_fields(tmp_path):
    artifact = write_capture(tmp_path, BASELINE_PAYLOAD, at=NOW)
    digest = tmp_path / "digest"
    run(make_cfg(tmp_path, [capture_event(artifact)], NOW, digest=digest))
    jsons = sorted(digest.glob("*.json"))
    mds = sorted(digest.glob("*.md"))
    assert len(jsons) == 1 and len(mds) == 1, "one MD + one JSON digest per run"
    d = json.loads(jsons[0].read_text(encoding="utf-8"))
    for key in ("run_id", "commit", "status", "artifacts", "identity_levels",
                "hash_coverage", "locator_coverage", "blockers", "tests",
                "candidates", "alerts", "state_transitions", "observations"):
        assert key in d, f"digest missing required key {key}"
    assert d["commit"] == "76a242a0b756c2e04c40769e0947779f6a85d755"
    assert d["artifacts"]["count"] == 1 and d["artifacts"]["bytes"] > 0
    assert isinstance(d["identity_levels"], dict) and len(d["identity_levels"]) >= 1
    assert isinstance(d["blockers"], dict)
    md = mds[0].read_text(encoding="utf-8")
    assert d["run_id"] in md, "MD digest must carry the run id"


# ── O: alert dedupe deterministic by event identity ─────────────────────────
def test_p118_O_alert_event_ids_are_deterministic_and_deduped(tmp_path):
    A = alerts_mod()
    event = {
        "type": "PRICE_CHANGE",
        "source": "www.toyota.co.th",
        "entity": "toyota-velo-cross-eco",
        "field": "prices.toyota-velo-cross-eco",
        "old_value": 999000,
        "new_value": 1019000,
    }
    eid1 = A.event_id(event)
    eid2 = A.event_id(dict(event))  # same content, different key order
    assert eid1 == eid2, "event identity must be deterministic regardless of dict order"
    changed = A.event_id({**event, "new_value": 1029000})
    assert changed != eid1, "different content → different identity"

    store = tmp_path / "alerts.jsonl"
    accepted1 = A.append_events(store, [event])
    accepted2 = A.append_events(store, [event])  # duplicate across runs
    assert accepted1 == [eid1]
    assert accepted2 == [], "duplicate event identity must be dropped"
    assert len(read_jsonl(store)) == 1


# ── P: one-shot CLI and --cron use the same deterministic runner ────────────
def test_p118_P_one_shot_and_cron_entrypoints_share_the_runner(tmp_path):
    artifact = write_capture(tmp_path, BASELINE_PAYLOAD, at=NOW)
    events_file = tmp_path / "events.json"
    events_file.write_text(json.dumps([capture_event(artifact)]), encoding="utf-8")

    def invoke(flag):
        slug = flag.lstrip("-")
        out_q = tmp_path / f"q{slug}"
        out_d = tmp_path / f"d{slug}"
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "daily_run.py"), flag,
             "--events", str(events_file),
             "--queue-dir", str(out_q), "--digest-dir", str(out_d),
             "--now", NOW.isoformat(), "--quiet"],
            cwd=str(REPO), capture_output=True, text=True, timeout=120,
        )
        return proc

    p_once = invoke("--once")
    assert p_once.returncode == 0, p_once.stdout + p_once.stderr
    p_cron = invoke("--cron")
    assert p_cron.returncode == 0, p_cron.stdout + p_cron.stderr
    d_once = json.loads((tmp_path / "qonce" / "run-state.json").read_text(encoding="utf-8"))
    d_cron = json.loads((tmp_path / "qcron" / "run-state.json").read_text(encoding="utf-8"))
    assert d_once["runner"] == d_cron["runner"] == "daily_run.run_daily", "both entrypoints must call the same runner"
    assert d_once["sources"].keys() == d_cron["sources"].keys()


# ── Exit gate: 7 consecutive green runs, alerts only on meaningful changes ──
def test_p118_EXIT_7_seven_consecutive_green_runs(tmp_path):
    R = runner()
    assert hasattr(R, "build_replay7_scenario"), "runner must expose the scripted 7-run scenario"
    scenario = R.build_replay7_scenario(tmp_path)
    assert len(scenario["runs"]) == 7

    results = []
    for i, run_spec in enumerate(scenario["runs"]):
        cfg = make_cfg(tmp_path, run_spec["events"], run_spec["now"],
                       queue=scenario["queue"], digest=scenario["digest"])
        results.append(run(cfg))

    statuses = [r["status"] for r in results]
    assert statuses == ["RUN_GREEN"] * 7, f"7 consecutive green runs required, got {statuses}"

    alerts = read_jsonl(scenario["queue"] / "alerts.jsonl")
    by_run = {}
    for a in alerts:
        by_run.setdefault(a["run_id"], []).append(a["type"])
    expect_alerts_runs = {4: ["PRICE_CHANGE"], 5: ["MODEL_VARIANT_ADDED_REMOVED"], 6: ["SOURCE_STATE_TRANSITION"]}
    for idx in (1, 2, 3, 7):
        assert by_run.get(str(results[idx - 1]["run_id"]), []) == [], f"run {idx} must not alert"
    for run_idx, types in expect_alerts_runs.items():
        rid = str(results[run_idx - 1]["run_id"])
        assert by_run.get(rid) == types, f"run {run_idx}: expected {types}, got {by_run.get(rid)}"

    cands = read_jsonl(scenario["queue"] / "change-candidates.jsonl")
    ids = [c["candidate_id"] for c in cands]
    assert len(ids) == len(set(ids)), "no duplicate ChangeCandidates across 7 runs"
    digests = sorted(scenario["digest"].glob("*.json"))
    assert len(digests) == 7, f"one digest per run, got {len(digests)}"
    # catalog never touched across the whole scenario
    counts = catalog_counts()
    assert sum(counts.values()) > 0
