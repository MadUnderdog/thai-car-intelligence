#!/usr/bin/env python3
"""
P119 — bounded offline assembly runner (no network, packet-artifacts only).

Assembles ACCEPTED EvidencePackets into field-level provenance records +
explicit conflict records + join errors, then writes deterministic JSONL and
the machine-readable MD+JSON audit report.

Usage:
  python3 scripts/assemble_records.py \
      [--packets audit/coverage/p113_evidence_packets.json] \
      [--alias-catalog storage/thai-alias-catalog.json] \
      [--fixtures-dir tests/fixtures] \
      [--out-dir audit/assembly] \
      [--report-dir audit/coverage] \
      [--commit <sha>] [--tests-log <path>]
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from thai_factory.assembly.assemble import assemble, write_outputs  # noqa: E402
from thai_factory.assembly.report import write_report  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="P119 deterministic multi-source assembly")
    ap.add_argument("--packets", default=str(REPO / "audit/coverage/p113_evidence_packets.json"))
    ap.add_argument("--alias-catalog", default=str(REPO / "storage/thai-alias-catalog.json"))
    ap.add_argument("--fixtures-dir", default=str(REPO / "tests/fixtures"))
    ap.add_argument("--out-dir", default=str(REPO / "audit/assembly"))
    ap.add_argument("--report-dir", default=str(REPO / "audit/coverage"))
    ap.add_argument("--commit", default="")
    ap.add_argument("--tests-log", default="")
    args = ap.parse_args()

    payload = json.loads(Path(args.packets).read_text(encoding="utf-8"))
    packets = payload["packets"] if isinstance(payload, dict) else payload
    catalog = json.loads(Path(args.alias_catalog).read_text(encoding="utf-8"))

    commit = args.commit
    if not commit:
        import subprocess
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                capture_output=True, text=True, timeout=30).stdout.strip()

    result = assemble(packets, catalog, fixtures_dir=args.fixtures_dir)
    outputs = write_outputs(result, args.out_dir)
    report = write_report(result, args.report_dir, commit_sha=commit,
                          tests_log=args.tests_log or None)

    summary = {
        "commit": commit,
        "stats": result.stats,
        "outputs": outputs,
        "report": report,
    }
    print(json.dumps(summary, sort_keys=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
