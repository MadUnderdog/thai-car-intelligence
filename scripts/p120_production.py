#!/usr/bin/env python3
"""
P120 — production promotion + observability CLI (Phase 6).

Subcommands (all offline; the only writer is the promote transaction):
  preflight  build the gate report BEFORE any write (MD+JSON)
  promote    dry-run (preflight only) | --execute (gated transaction + postflight)
  audit      read-only audit report (MD+JSON)
  freshness  dated-evidence freshness/SLO report (MD+JSON)
  rollback   bounded inverse of ONE promotion run (auditable, idempotent)
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from thai_factory.production import audit as audit_mod        # noqa: E402
from thai_factory.production import freshness as fresh_mod    # noqa: E402
from thai_factory.production import rollback as rollback_mod  # noqa: E402
from thai_factory.production import worker as worker_mod      # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P120 production worker")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_common(p):
        p.add_argument("--packets", default=str(worker_mod.DEFAULT_PACKETS))
        p.add_argument("--p114-ledger", default=str(worker_mod.DEFAULT_P114_LEDGER))
        p.add_argument("--production-ledger",
                       default=str(worker_mod.DEFAULT_PROD_LEDGER))
        p.add_argument("--out-dir",
                       default=str(REPO / "audit" / "coverage"))
        p.add_argument("--now", default=None)
        p.add_argument("--db-url", default=None)

    p_pre = sub.add_parser("preflight", help="gate report, never writes")
    add_common(p_pre)
    p_pre.add_argument("--lock-path", default=str(worker_mod.DEFAULT_LOCK))

    p_pro = sub.add_parser("promote", help="dry-run or execute")
    add_common(p_pro)
    p_pro.add_argument("--execute", action="store_true")
    p_pro.add_argument("--lock-path", default=str(worker_mod.DEFAULT_LOCK))
    p_pro.add_argument("--catalog-path", default=None)
    p_pro.add_argument("--universe-path", default=None)

    p_aud = sub.add_parser("audit", help="read-only audit report")
    p_aud.add_argument("--out", default=str(REPO / "audit" / "coverage" / "p120_audit_report"))
    p_aud.add_argument("--now", default=None)
    p_aud.add_argument("--db-url", default=None)

    p_fresh = sub.add_parser("freshness", help="dated-evidence SLO report")
    p_fresh.add_argument("--out", default=str(REPO / "audit" / "coverage" / "p120_freshness_report"))
    p_fresh.add_argument("--now", default=None)
    p_fresh.add_argument("--db-url", default=None)

    p_rb = sub.add_parser("rollback", help="bounded inverse of one run")
    p_rb.add_argument("--run-id", required=True)
    p_rb.add_argument("--out-dir", default=str(REPO / "audit" / "coverage"))
    p_rb.add_argument("--ledger", default=str(worker_mod.DEFAULT_PROD_LEDGER))
    p_rb.add_argument("--db-url", default=None)
    p_rb.add_argument("--now", default=None)

    args = ap.parse_args(argv)
    now = args.now or datetime.now(timezone.utc).isoformat()

    if args.cmd == "preflight":
        pre = worker_mod.build_preflight(
            args.packets, args.p114_ledger, args.production_ledger,
            args.out_dir, db=args.db_url, now=now)
        print(json.dumps({"status": pre["status"], "eligible": pre["eligible"],
                          "refusals": pre["refusals"]},
                         sort_keys=True, ensure_ascii=False))
        return 0 if pre["status"] == "PASS" else 1

    if args.cmd == "promote":
        res = worker_mod.run_promotion(
            "execute" if args.execute else "dry_run",
            args.packets, args.p114_ledger, args.production_ledger,
            args.lock_path, args.out_dir, db_url=args.db_url, now=now,
            catalog_path=args.catalog_path, universe_path=args.universe_path)
        print(json.dumps({k: res[k] for k in
                          ("status", "writes", "run_id", "refusals")
                          if k in res}, sort_keys=True, ensure_ascii=False))
        return 0 if res["status"] in ("DRY_RUN", "NO_ACTION", "PROMOTED") else 1

    if args.cmd == "audit":
        rep = audit_mod.build_audit_report(args.db_url or worker_mod.db_url(),
                                           now, repo_root=str(REPO))
        paths = audit_mod.write_audit_report(rep, args.out)
        print(json.dumps(paths, sort_keys=True))
        return 0

    if args.cmd == "freshness":
        rep = fresh_mod.build_freshness_report(
            args.db_url or worker_mod.db_url(), now, repo_root=str(REPO))
        paths = fresh_mod.write_freshness_report(rep, args.out)
        print(json.dumps(paths, sort_keys=True))
        return 0

    if args.cmd == "rollback":
        res = rollback_mod.rollback_run(args.run_id, db_url=args.db_url,
                                        out_dir=args.out_dir,
                                        ledger_path=args.ledger, now=now)
        print(json.dumps({k: res[k] for k in
                          ("status", "deleted_rows", "restored_current_flags")
                          if k in res}, sort_keys=True))
        return 0 if res["status"] in ("ROLLED_BACK", "NO_ACTION") else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
