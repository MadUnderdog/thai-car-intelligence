"""
Phase 4 daily runner (Blueprint §94) — orchestration around EXISTING primitives.

Pipeline per run:
  RUN_QUEUED → LOCK_ACQUIRED | RUN_SKIPPED_DOUBLE
    → SOURCES_SELECTED (events injected: offline replay default)
    → ACQUIRE (replay: committed/new capture files; AcquisitionWriter-made)
    → PROVENANCE_VERIFY (AcquisitionReader — fail-closed)
    → DIFF_CLASSIFY (classify_capture)
    → QUARANTINE (field-level ChangeCandidates → change-candidates.jsonl)
    → ALERT_EVAL (§94 allowlist + event-identity dedupe → alerts.jsonl)
    → DIGEST (MD + JSON)
    → RUN_GREEN | RUN_PARTIAL | RUN_FAILED

Hard rules honored here:
  - NEVER writes catalog/price/spec tables (promotion stays with AcceptanceRunner)
  - failed/blocked source keeps previous accepted state (§77)
  - same sha → UNCHANGED, no rows/candidates/alerts
  - digest per run under audit/daily-runs convention (YYYYMMDD{,b,c}.{md,json})
  - deterministic lock (fcntl) so a cron double-fire cannot duplicate anything
"""
import fcntl
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..acquisition import backoff
from ..acquisition.provenance import AcquisitionReader, ProvenanceError
from . import alerts as alerts_mod
from . import classify as classify_mod

RUNNER_ID = "daily_run.run_daily"
QUEUE_CANDIDATES = "change-candidates.jsonl"
QUEUE_ALERTS = "alerts.jsonl"
STATE_FILE = "run-state.json"
LOCK_FILE = ".daily-run.lock"

# ── extractors (deterministic, offline) ────────────────────────────────────
def _extract_json(content: bytes) -> Dict:
    parsed = json.loads(content.decode("utf-8"))
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


_PRICE_RE = re.compile(r"(?:฿|ราคา)\s*([0-9][0-9,]{2,})")


def _extract_html_prices(content: bytes) -> Dict:
    text = content.decode("utf-8", errors="replace")
    prices = {}
    for i, match in enumerate(_PRICE_RE.findall(text)):
        prices[f"row{i}"] = int(match.replace(",", ""))
    return {"prices": prices}


EXTRACTORS: Dict[str, Callable[[bytes], Dict]] = {
    "json": _extract_json,
    "html_prices": _extract_html_prices,
}


@dataclass
class RunConfig:
    queue_dir: Path
    digest_dir: Path
    registry_path: str
    staging_path: Optional[str]
    events: List[Dict]
    now: datetime
    commit_sha: str
    mode: str = "offline"
    entrypoint: str = "once"
    tests_log: Optional[str] = None
    runner: str = RUNNER_ID


def _atomic_write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def reachable_brand_domain(registry_path: str) -> str:
    """First REACHABLE registry brand's host (real domains only, never invented)."""
    registry = _load_json(Path(registry_path), {})
    from urllib.parse import urlparse
    for brand in registry.get("brands", []):
        if brand.get("access_status") == "REACHABLE" and brand.get("source_urls"):
            return urlparse(brand["source_urls"][0]).netloc
    raise AssertionError("registry must contain a REACHABLE brand with source_urls")


def registry_access_state(registry_path: str, domain: str) -> str:
    registry = _load_json(Path(registry_path), {})
    from urllib.parse import urlparse
    bare = domain.replace("www.", "")
    for brand in registry.get("brands", []):
        for url in brand.get("source_urls", []):
            netloc = urlparse(url).netloc.replace("www.", "")
            if netloc == bare:
                return brand.get("access_status") or "UNKNOWN"
    return "UNKNOWN"


def _digest_paths(digest_dir: Path, now: datetime):
    """Digest FILE naming: YYYYMMDD, then b, c… for repeats in the same dir."""
    base = now.strftime("%Y%m%d")
    digest_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(p.name for p in digest_dir.glob(f"{base}*.json"))
    suffix = "" if not existing else (chr(ord("b") + len(existing) - 1) if len(existing) <= 25 else f"z{len(existing)}")
    stem = f"{base}{suffix}"
    return digest_dir / f"{stem}.json", digest_dir / f"{stem}.md"


def _next_run_id(state: Dict, now: datetime) -> str:
    """Run identity is queue-global (monotonic per queue dir) so it stays
    unique across digest dirs, runs and concurrent scenarios."""
    seq = int(state.get("run_seq") or 0) + 1
    state["run_seq"] = seq
    return f"DR-{now.strftime('%Y%m%d')}-{seq:03d}"


def _identity_levels(staging_path: Optional[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    if not staging_path or not Path(staging_path).exists():
        return {"unknown": 0}
    for line in Path(staging_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        level = ((row.get("identity") or {}).get("identity_level")
                 or (row.get("identity") or {}).get("identity_scope")
                 or (row.get("identity") or {}).get("level") or "unknown")
        counts[level] = counts.get(level, 0) + 1
    return counts or {"unknown": 0}


def _locator_coverage(staging_path: Optional[str]) -> Dict:
    if not staging_path or not Path(staging_path).exists():
        return {"rows": 0, "duplicate_dom_path": 0, "duplicate_json_path": 0}
    rows = []
    for line in Path(staging_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    def loc(r):
        return (r.get("evidence_locator")
                or (r.get("evidence") or {}).get("evidence_locator")
                or (r.get("evidence") or {}).get("locator") or {})

    def dup(key_fn):
        seen, dups = set(), 0
        for r in rows:
            key = key_fn(r)
            if key is None:
                continue
            if key in seen:
                dups += 1
            else:
                seen.add(key)
        return dups

    return {
        "rows": len(rows),
        "duplicate_dom_path": dup(lambda r: loc(r).get("dom_path")),
        "duplicate_json_path": dup(lambda r: loc(r).get("json_path")),
    }


def _hash_coverage(registry_path: str) -> Dict:
    registry = _load_json(Path(registry_path), {})
    in_scope = [b for b in registry.get("brands", []) if b.get("in_scope")]
    with_sha = [b for b in in_scope if b.get("last_success_sha256")]
    return {"in_scope": len(in_scope), "with_last_success_sha256": len(with_sha)}


def _blockers_section(registry_path: str, run_blockers: List[Dict]) -> Dict:
    registry = _load_json(Path(registry_path), {})
    histogram: Dict[str, int] = {}
    for brand in registry.get("brands", []):
        status = brand.get("access_status") or "UNKNOWN"
        histogram[status] = histogram.get(status, 0) + 1
    return {"registry": dict(sorted(histogram.items())), "run": run_blockers}


def _tests_section(tests_log: Optional[str]) -> Dict:
    if not tests_log or not Path(tests_log).exists():
        return {"status": "not_run_in_this_invocation"}
    text = Path(tests_log).read_text(encoding="utf-8", errors="replace")
    passed = re.findall(r"(\d+) passed", text)
    failed = re.findall(r"(\d+) failed", text)
    errors = re.findall(r"(\d+) error", text)
    return {
        "log": tests_log,
        "passed": int(passed[-1]) if passed else None,
        "failed": int(failed[-1]) if failed else 0,
        "errors": int(errors[-1]) if errors else 0,
    }


def _write_digest(cfg: RunConfig, run_id: str, payload: Dict) -> Dict:
    json_path, md_path = _digest_paths(Path(cfg.digest_dir), cfg.now)
    _atomic_write_json(json_path, payload)

    lines = [
        f"# Daily run digest {run_id}",
        "",
        f"- run_id: `{run_id}`",
        f"- commit: `{payload['commit']}`",
        f"- status: **{payload['status']}**",
        f"- mode: {cfg.mode} · entrypoint: {cfg.entrypoint}",
        f"- artifacts: {payload['artifacts']['count']} file(s), {payload['artifacts']['bytes']} bytes",
        f"- candidates: {payload['candidates']['count']} · alerts: {payload['alerts']['count']}",
        "",
        "## Sources",
    ]
    for src in payload["sources"]:
        detail = src.get("classification") or ""
        err = f" — {src['error']}" if src.get("error") else ""
        lines.append(f"- {src['source']} [{src['kind']}]: {detail} (observations={src.get('observations', 0)}){err}")
    lines += ["", "## Identity levels (staging)"]
    for level, count in sorted(payload["identity_levels"].items()):
        lines.append(f"- {level}: {count}")
    lines += ["", "## Blockers"]
    for status, count in sorted(payload["blockers"]["registry"].items()):
        if status.startswith("BLOCKED") or status in ("DEALER_REDIRECT", "UNKNOWN"):
            lines.append(f"- {status}: {count}")
    for blocker in payload["blockers"]["run"]:
        lines.append(f"- run: {blocker}")
    lines += ["", "## State transitions"]
    for tr in payload["state_transitions"]:
        lines.append(f"- {tr['source']}: {tr['from']} → {tr['to']}")
    if payload["alerts"]["entries"]:
        lines += ["", "## Alerts"]
        for a in payload["alerts"]["entries"]:
            lines.append(f"- [{a['type']}] {a.get('source')}: {json.dumps({k: v for k, v in a.items() if k not in ('type', 'source', 'event_id', 'run_id', 'created_at')}, ensure_ascii=False, default=str)}")
    lines += ["", "## Tests", f"- {json.dumps(payload['tests'], ensure_ascii=False, default=str)}", ""]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def run_daily(cfg: RunConfig) -> Dict:
    """One deterministic daily run. Never writes catalog tables."""
    queue_dir = Path(cfg.queue_dir)
    queue_dir.mkdir(parents=True, exist_ok=True)
    lock_path = queue_dir / LOCK_FILE
    fd = None
    try:
        fd = open(lock_path, "a+")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            return {"run_id": None, "status": "RUN_SKIPPED_DOUBLE", "writes": 0, "sources": [], "runner": cfg.runner}
        return _run_locked(cfg, queue_dir)
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                fd.close()


def _run_locked(cfg: RunConfig, queue_dir: Path) -> Dict:
    state_path = queue_dir / STATE_FILE
    state = _load_json(state_path, {"runner": RUNNER_ID, "sources": {}})
    state.setdefault("sources", {})
    state["runner"] = cfg.runner
    state["entrypoint"] = cfg.entrypoint

    candidates_path = queue_dir / QUEUE_CANDIDATES
    alert_path = queue_dir / QUEUE_ALERTS

    run_id = _next_run_id(state, cfg.now)
    now_iso = cfg.now.isoformat()

    source_entries: List[Dict] = []
    run_candidates: List[Dict] = []
    run_alerts: List[Dict] = []
    transitions: List[Dict] = []
    run_blockers: List[Dict] = []
    observation_sections: List[Dict] = []
    artifacts_count = 0
    artifacts_bytes = 0
    any_failure = False

    for event in cfg.events:
        source = event["source"]
        prev = state["sources"].get(source, {})
        if event["kind"] == "probe":
            new_state = backoff.classify_outcome(event["outcome"])
            prev_access = prev.get("access_state") or registry_access_state(cfg.registry_path, source)
            attempt = int(prev.get("attempts") or 0) + 1 if prev.get("access_state") == new_state else 1
            nxt, retry_state, actions = backoff.next_retry(new_state, attempt, cfg.now)
            if prev_access == "REACHABLE" and new_state not in ("REACHABLE", "OK"):
                run_alerts.append({
                    "type": "SOURCE_STATE_TRANSITION",
                    "source": source,
                    "detail": {"transition": f"REACHABLE→{new_state}", "outcome": event["outcome"]},
                })
                transitions.append({"source": source, "from": prev_access, "to": new_state})
            state["sources"][source] = {
                **prev,
                "access_state": new_state,
                "next_retry_at": nxt.isoformat() if nxt else None,
                "retry_state": retry_state,
                "attempts": attempt,
                "actions": actions,
            }
            if new_state not in ("REACHABLE", "OK"):
                run_blockers.append({"source": source, "outcome": new_state, "retry_state": retry_state})
            source_entries.append({
                "source": source, "kind": "probe", "classification": new_state,
                "provenance": "N/A", "observations": 0,
            })
            continue

        # ── capture event ──
        artifact = Path(event["artifact"])
        artifacts_count += 1
        artifacts_bytes += artifact.stat().st_size if artifact.exists() else 0

        try:
            content, provenance = AcquisitionReader.read(str(artifact))
        except ProvenanceError as exc:
            any_failure = True
            source_entries.append({
                "source": source, "kind": "capture", "classification": "PROVENANCE_ERROR",
                "provenance": "FAILED", "observations": 0, "error": str(exc),
            })
            run_alerts.append({
                "type": "PROVENANCE_FAILURE",
                "source": source,
                "artifact": artifact.name,
                "reason": "hash_mismatch_or_missing_sidecar",
            })
            continue  # previous accepted state (prev) is preserved untouched

        sha = provenance.get("sha256") or hashlib.sha256(content.encode("utf-8")).hexdigest()

        # §94: ERROR_PAGE / DEALER_REDIRECT → store evidence, extract nothing
        outcome = event.get("outcome")
        if outcome in ("ERROR_PAGE", "DEALER_REDIRECT"):
            state["sources"][source] = {
                **prev,
                "access_state": outcome,
                "last_sha": sha,
                "next_retry_at": None,
                "retry_state": "URL_TARGET_ISSUE",
                "attempts": int(prev.get("attempts") or 0) + 1,
                "blocker_evidence": {
                    "outcome": outcome,
                    "url": provenance.get("source_url"),
                    "checked_at": now_iso,
                },
            }
            run_blockers.append({"source": source, "outcome": outcome, "url": provenance.get("source_url")})
            source_entries.append({
                "source": source, "kind": "capture", "classification": "BLOCKED_EVIDENCE_STORED",
                "provenance": "VERIFIED", "observations": 0,
            })
            continue

        extractor_name = event.get("extractor", "json")
        extractor = EXTRACTORS.get(extractor_name)
        if extractor is None:
            any_failure = True
            source_entries.append({
                "source": source, "kind": "capture", "classification": "EXTRACTOR_MISSING",
                "provenance": "VERIFIED", "observations": 0,
                "error": f"unknown extractor {extractor_name}",
            })
            continue

        output = classify_mod.canonical_output(extractor(content.encode("utf-8")))
        verdict = classify_mod.classify_capture(
            prev.get("last_sha"), prev.get("last_output"), sha, output,
        )
        classification = verdict["status"]

        new_candidates: List[Dict] = []
        if classification == classify_mod.STATUS_CHANGED:
            for diff in verdict["field_diffs"]:
                candidate = {
                    "source": source,
                    "old_sha": prev.get("last_sha"),
                    "new_sha": sha,
                    "entity": diff["entity"],
                    "field": diff["field"],
                    "old_value": diff["old_value"],
                    "new_value": diff["new_value"],
                    "status": "QUARANTINED",
                }
                candidate["candidate_id"] = hashlib.sha256(
                    json.dumps({k: candidate[k] for k in sorted(candidate)},
                               sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
                ).hexdigest()
                candidate["run_id"] = run_id
                candidate["detected_at"] = now_iso
                new_candidates.append(candidate)
            # alerts: one per price field diff + one aggregate model/variant set event
            for cand in new_candidates:
                if cand["field"].startswith("prices."):
                    run_alerts.append({
                        "type": "PRICE_CHANGE",
                        "source": source,
                        "entity": cand["entity"],
                        "field": cand["field"],
                        "old_value": cand["old_value"],
                        "new_value": cand["new_value"],
                    })
            if verdict["set_diffs"]["added"] or verdict["set_diffs"]["removed"]:
                run_alerts.append({
                    "type": "MODEL_VARIANT_ADDED_REMOVED",
                    "source": source,
                    "entity": "models",
                    "detail": {
                        "added": verdict["set_diffs"]["added"],
                        "removed": verdict["set_diffs"]["removed"],
                    },
                })

        # persist candidates idempotently (dedupe by candidate_id)
        if new_candidates:
            existing_ids = {c.get("candidate_id") for c in _read_jsonl(candidates_path)}
            to_write = [c for c in new_candidates if c["candidate_id"] not in existing_ids]
            if to_write:
                with candidates_path.open("a", encoding="utf-8") as fh:
                    for row in to_write:
                        fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")
                run_candidates.extend(to_write)

        # successful capture → accepted state updated (failures never reach here)
        state["sources"][source] = {
            **prev,
            "last_sha": sha,
            "last_output_hash": classify_mod.output_hash(output),
            "last_output": output,
            "access_state": "REACHABLE",
            "next_retry_at": None,
            "retry_state": None,
            "attempts": 0,
            "blocker_evidence": None,
        }
        observation_sections.append({"source": source, "observations": verdict["observations"]})
        source_entries.append({
            "source": source, "kind": "capture", "classification": classification,
            "provenance": "VERIFIED", "observations": len(verdict["observations"]),
        })

    # alerts (allowlist + event-identity dedupe)
    accepted_ids = alerts_mod.append_events(alert_path, run_alerts, run_id=run_id, created_at=now_iso)
    written_alerts = [a for a in _read_jsonl(alert_path) if a.get("event_id") in set(accepted_ids)]
    run_alerts_out = written_alerts or []

    status = "RUN_PARTIAL" if any_failure else "RUN_GREEN"
    _atomic_write_json(state_path, state)

    digest_payload = {
        "run_id": run_id,
        "commit": cfg.commit_sha,
        "status": status,
        "mode": cfg.mode,
        "entrypoint": cfg.entrypoint,
        "runner": RUNNER_ID,
        "generated_at": now_iso,
        "artifacts": {"count": artifacts_count, "bytes": artifacts_bytes},
        "identity_levels": _identity_levels(cfg.staging_path),
        "hash_coverage": _hash_coverage(cfg.registry_path),
        "locator_coverage": _locator_coverage(cfg.staging_path),
        "blockers": _blockers_section(cfg.registry_path, run_blockers),
        "tests": _tests_section(cfg.tests_log),
        "candidates": {"count": len(run_candidates), "entries": run_candidates},
        "alerts": {"count": len(run_alerts_out), "entries": run_alerts_out},
        "state_transitions": transitions,
        "sources": source_entries,
        "observations": sorted(observation_sections, key=lambda o: o["source"]),
    }
    paths = _write_digest(cfg, run_id, digest_payload)

    writes = (1 if candidates_path.exists() else 0) + (1 if alert_path.exists() else 0) + 1 + 2
    return {
        "run_id": run_id,
        "status": status,
        "sources": source_entries,
        "candidates": run_candidates,
        "alerts": run_alerts_out,
        "digest": paths,
        "writes": writes,
        "runner": RUNNER_ID,
    }


def _read_jsonl(path: Path) -> List[Dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def build_replay7_scenario(tmp: Path) -> Dict:
    """
    The Blueprint Phase-4 exit scenario: 7 consecutive runs over replayed
    capture events with scripted meaningful changes (runs 4/5/6) and
    unchanged runs elsewhere (1/2/3/7).
    """
    from ..acquisition.provenance import AcquisitionWriter

    tmp = Path(tmp)
    baseline = {"prices": {"toyota-velo-cross-eco": 999000},
                "models": ["toyota-velo-cross", "toyota-yaris-cross"]}

    def capture(payload, name, at, raw=None):
        content = raw if raw is not None else json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1)
        AcquisitionWriter.write(
            content=content,
            source_url="https://www.toyota.co.th/model",
            acquisition_method="offline_replay",
            output_dir=str(tmp / "artifacts"),
            filename=name,
            session_id="p118-replay7",
            clock=lambda: at.isoformat(),
        )
        return str(tmp / "artifacts" / name)

    def at(hours: int) -> datetime:
        return datetime(2026, 9, 29, 6, 0, 0, tzinfo=timezone.utc) + timedelta(hours=hours)

    cap1 = capture(baseline, "r1.json", at(0))
    cap1b = capture(baseline, "r1b.json", at(2), raw=json.dumps(baseline, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
    price_changed = dict(baseline, prices={"toyota-velo-cross-eco": 1019000})
    cap_price = capture(price_changed, "r4.json", at(3))
    models_changed = {"prices": price_changed["prices"],
                      "models": ["toyota-velo-cross", "toyota-corolla-cross"]}
    cap_models = capture(models_changed, "r5.json", at(4))
    probe_domain = reachable_brand_domain("audit/coverage/oem-registry.json")

    runs = [
        {"now": at(0), "events": [{"kind": "capture", "source": "www.toyota.co.th", "artifact": cap1, "extractor": "json"}]},
        {"now": at(1), "events": [{"kind": "capture", "source": "www.toyota.co.th", "artifact": cap1, "extractor": "json"}]},
        {"now": at(2), "events": [{"kind": "capture", "source": "www.toyota.co.th", "artifact": cap1b, "extractor": "json"}]},
        {"now": at(3), "events": [{"kind": "capture", "source": "www.toyota.co.th", "artifact": cap_price, "extractor": "json"}]},
        {"now": at(4), "events": [{"kind": "capture", "source": "www.toyota.co.th", "artifact": cap_models, "extractor": "json"}]},
        {"now": at(5), "events": [
            {"kind": "capture", "source": "www.toyota.co.th", "artifact": cap_models, "extractor": "json"},
            {"kind": "probe", "source": probe_domain, "outcome": "HTTP_403"},
        ]},
        {"now": at(6), "events": [
            {"kind": "capture", "source": "www.toyota.co.th", "artifact": cap_models, "extractor": "json"},
            {"kind": "probe", "source": probe_domain, "outcome": "HTTP_403"},
        ]},
    ]
    return {"runs": runs, "queue": tmp / "queue", "digest": tmp / "digest"}
