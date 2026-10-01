#!/usr/bin/env python3
"""
Phase 4 daily runner CLI (Blueprint §94 / §101) — one-shot and cron compatible.

  python3 scripts/daily_run.py --once            # manual one-shot
  python3 scripts/daily_run.py --cron            # SAME deterministic runner
  python3 scripts/daily_run.py --replay7         # 7-run exit-gate evidence
  python3 scripts/daily_run.py --events file.json [--now ISO] [--quiet]

Cron line (documented, no managed scheduler required):
  0 6 * * *  cd <repo> && /usr/bin/python3 scripts/daily_run.py --cron --quiet

Exit codes: 0 = RUN_GREEN / RUN_PARTIAL (§77 partial success is a success),
            1 = runner failure, 2 = lock busy (RUN_SKIPPED_DOUBLE).

Offline replay (default) never touches the network and never writes
catalog/price/spec tables — refresh produces QUARANTINED ChangeCandidates,
alerts and digests only; promotion stays with the AcceptanceRunner.
"""
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from thai_factory.refresh.runner import (  # noqa: E402
    RunConfig,
    build_replay7_scenario,
    run_daily,
)


def git_head() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, timeout=15)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def load_events(path: str):
    with open(path, encoding="utf-8") as fh:
        events = json.load(fh)
    if not isinstance(events, list):
        raise SystemExit("--events file must contain a JSON list of events")
    return events


def make_config(args, events, entrypoint: str) -> RunConfig:
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    return RunConfig(
        queue_dir=Path(args.queue_dir),
        digest_dir=Path(args.digest_dir),
        registry_path=args.registry,
        staging_path=args.staging,
        events=events,
        now=now,
        commit_sha=args.commit or git_head(),
        mode=args.mode,
        entrypoint=entrypoint,
        tests_log=args.tests_log,
    )


def run_replay7(args) -> int:
    """Seven consecutive green runs → audit/coverage/p118_seven_green_runs.json."""
    # artifacts live in a scratch dir; the QUEUE and DIGESTS go to the
    # canonical §99/§94 locations (audit/change-queue/ + audit/daily-runs/)
    tmp = REPO / "audit" / "_replay7_scratch"
    scenario = build_replay7_scenario(tmp)
    # replay7 owns a dedicated queue subdir, reset per invocation so the
    # exit-gate evidence is reproducible; daily digests keep their suffixes
    queue_dir = Path(args.queue_dir) / "replay7"
    if queue_dir.exists():
        shutil.rmtree(queue_dir)
    digest_dir = Path(args.digest_dir)
    results = []
    for spec in scenario["runs"]:
        cfg = RunConfig(
            queue_dir=queue_dir,
            digest_dir=digest_dir,
            registry_path=args.registry,
            staging_path=args.staging,
            events=spec["events"],
            now=spec["now"],
            commit_sha=args.commit or git_head(),
            mode="offline-replay7",
            entrypoint="replay7",
            tests_log=args.tests_log,
        )
        results.append(run_daily(cfg))

    statuses = [r["status"] for r in results]
    candidates = []
    candidates_path = queue_dir / "change-candidates.jsonl"
    if candidates_path.exists():
        for line in candidates_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                candidates.append(json.loads(line)["candidate_id"])
    dup_candidates = len(candidates) - len(set(candidates))

    alert_rows = []
    alerts_path = queue_dir / "alerts.jsonl"
    if alerts_path.exists():
        alert_rows = [json.loads(l) for l in alerts_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    alerts_by_run = {}
    for a in alert_rows:
        alerts_by_run.setdefault(a.get("run_id"), []).append(a["type"])

    evidence = {
        "schema": "p118_seven_green_runs/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": args.commit or git_head(),
        "runs": [
            {
                "run_id": r.get("run_id"),
                "status": r.get("status"),
                "alerts": alerts_by_run.get(r.get("run_id"), []),
                "candidates": len(r.get("candidates", [])),
                "classification": [s.get("classification") for s in r.get("sources", [])],
            }
            for r in results
        ],
        "statuses": statuses,
        "green_runs": sum(1 for s in statuses if s == "RUN_GREEN"),
        "duplicate_candidate_ids": dup_candidates,
        "alert_runs": sorted(alerts_by_run.keys()),
        "digests": sorted(Path(r["digest"]["json"]).name for r in results if r.get("digest")),
        "queue_dir": str(queue_dir),
        "digest_dir": str(digest_dir),
        "exit_gate": "PASS" if statuses == ["RUN_GREEN"] * 7 and dup_candidates == 0 else "FAIL",
    }
    out = REPO / "audit" / "coverage" / "p118_seven_green_runs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.quiet:
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["exit_gate"] == "PASS" else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phase 4 daily diff + alerting runner (§94)")
    ap.add_argument("--once", action="store_true", help="one-shot manual run (default)")
    ap.add_argument("--cron", action="store_true", help="scheduled run — SAME runner as --once")
    ap.add_argument("--replay7", action="store_true", help="7-run exit-gate evidence")
    ap.add_argument("--events", help="JSON file: list of replay events")
    ap.add_argument("--queue-dir", default=str(REPO / "audit" / "change-queue"))
    ap.add_argument("--digest-dir", default=str(REPO / "audit" / "daily-runs"))
    ap.add_argument("--registry", default=str(REPO / "audit" / "coverage" / "oem-registry.json"))
    ap.add_argument("--staging", default=str(REPO / "audit" / "data-staging" / "vehicle_observations.jsonl"))
    ap.add_argument("--commit", default="")
    ap.add_argument("--mode", default="offline")
    ap.add_argument("--now", default="", help="ISO clock injection (deterministic replay)")
    ap.add_argument("--tests-log", default="")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if args.replay7:
        return run_replay7(args)

    entrypoint = "cron" if args.cron else "once"  # both call the same runner below
    events = load_events(args.events) if args.events else []
    if not events:
        if not args.quiet:
            print("no events provided (--events) — nothing to refresh this cycle", file=sys.stderr)
        return 0

    cfg = make_config(args, events, entrypoint)
    result = run_daily(cfg)
    if not args.quiet:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if result["status"] == "RUN_SKIPPED_DOUBLE":
        return 2
    if result["status"] == "RUN_FAILED":
        return 1
    # RUN_GREEN and RUN_PARTIAL (§77) both exit 0 — partial is not a job failure
    return 0


if __name__ == "__main__":
    sys.exit(main())
