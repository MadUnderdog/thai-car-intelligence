"""
P119 — machine-readable + MD audit report for the assembly run.
Deterministic: no wall-clock timestamps; every count derived from the result.
"""
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Optional


def _provenance_coverage(result) -> Dict[str, Any]:
    total = 0
    verified = 0
    legacy = 0
    sha_present = 0
    locator_present = 0
    artifacts = set()
    for rec in result.records:
        for field, prov in rec["fields"].items():
            total += 1
            if prov.get("verified"):
                verified += 1
            else:
                legacy += 1
            if prov.get("artifact_sha256"):
                sha_present += 1
            if prov.get("locator") is not None:
                locator_present += 1
            if prov.get("artifact"):
                artifacts.add(prov["artifact"])
    return {
        "fields_with_provenance": total,
        "verified": verified,
        "unverified_or_legacy": legacy,
        "sha_present": sha_present,
        "locator_present": locator_present,
        "distinct_artifacts": len(artifacts),
    }


def _per_source_contribution(result) -> Dict[str, int]:
    counter: Counter = Counter()
    for rec in result.records:
        for field, prov in rec["fields"].items():
            counter[prov.get("source_id") or "unknown"] += 1
    return dict(sorted(counter.items()))


def _resolutions(result) -> Dict[str, int]:
    counter: Counter = Counter()
    for conflict in result.conflicts:
        counter[conflict["status"]] += 1
    return dict(sorted(counter.items()))


def build_report(result, commit_sha: str, tests_log: Optional[str] = None) -> Dict[str, Any]:
    stats = result.stats or {}
    blockers = []
    if stats.get("join_errors"):
        blockers.append({
            "kind": "join_errors",
            "count": stats["join_errors"],
            "note": "packets whose candidate_key did not resolve through the alias catalog (display-string-only, rejected)",
        })
    if stats.get("validation_failures"):
        blockers.append({
            "kind": "contamination_guard_failures",
            "count": stats["validation_failures"],
            "note": "observations failing sha/locator coherence — quarantined, never assembled",
        })
    quarantined_fields = sum(1 for c in result.conflicts if c["status"] == "QUARANTINED")
    if quarantined_fields:
        blockers.append({
            "kind": "quarantined_fields_ceiling",
            "count": quarantined_fields,
            "note": "fields whose observations could not be resolved by policy (same tier, no dated winner) — both sides recorded, value NOT emitted; assembly is NOT complete for these fields",
        })

    tests: Dict[str, Any] = {"status": "not_run_in_this_invocation"}
    if tests_log and Path(tests_log).exists():
        text = Path(tests_log).read_text(encoding="utf-8", errors="replace")
        import re
        passed = re.findall(r"(\\d+) passed", text)
        failed = re.findall(r"(\\d+) failed", text)
        errors = re.findall(r"(\\d+) error", text)
        tests = {
            "log": tests_log,
            "passed": int(passed[-1]) if passed else None,
            "failed": int(failed[-1]) if failed else 0,
            "errors": int(errors[-1]) if errors else 0,
        }

    return {
        "schema": "p119_assembly_report/v1",
        "commit": commit_sha,
        "packets_in": stats.get("packets_in", 0),
        "packets_accepted_input": stats.get("packets_accepted", 0),
        "packets_quarantined_input": stats.get("packets_quarantined_input", 0),
        "records": stats.get("records", 0),
        "fields_assembled": stats.get("fields_assembled", 0),
        "per_source_contribution": _per_source_contribution(result),
        "conflicts": {
            "count": len(result.conflicts),
            "by_status": _resolutions(result),
            "entries": result.conflicts,
        },
        "quarantines": [c for c in result.conflicts if c["status"] == "QUARANTINED"],
        "join_errors": result.join_errors,
        "validation_failures": result.failures,
        "provenance_coverage": _provenance_coverage(result),
        "resolutions": _resolutions(result),
        "blockers": blockers,
        "tests": tests,
        "promotion": "none — audit/quarantine outputs only; AcceptanceRunner/Ledger untouched",
    }


def write_report(result, out_dir, commit_sha: str, tests_log: Optional[str] = None) -> Dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = build_report(result, commit_sha, tests_log=tests_log)

    json_path = out_dir / "p119_assembly_report.json"
    json_path.write_text(json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    md = [
        "# P119 — Multi-source assembly report (§96–97)",
        "",
        f"- commit: `{data['commit']}`",
        f"- packets in: **{data['packets_in']}** (accepted input: {data['packets_accepted_input']}, quarantined input: {data['packets_quarantined_input']})",
        f"- assembled records: **{data['records']}** · fields: **{data['fields_assembled']}**",
        f"- conflicts: **{data['conflicts']['count']}** by status: `{json.dumps(data['conflicts']['by_status'], ensure_ascii=False)}`",
        f"- quarantines (unresolved, value NOT emitted): **{len(data['quarantines'])}**",
        f"- join errors (display-string-only rejected): **{len(data['join_errors'])}**",
        f"- contamination/validation failures (fail closed): **{len(data['validation_failures'])}**",
        f"- provenance coverage: `{json.dumps(data['provenance_coverage'], ensure_ascii=False)}`",
        f"- promotion: {data['promotion']}",
        "",
        "## Per-source contribution (assembled fields)",
    ]
    for source, count in data["per_source_contribution"].items():
        md.append(f"- {source}: {count}")
    md += ["", "## Resolutions"]
    for status, count in data["resolutions"].items():
        md.append(f"- {status}: {count}")
    if data["blockers"]:
        md += ["", "## Blockers / ceilings"]
        for b in data["blockers"]:
            md.append(f"- {b['kind']} ({b['count']}): {b['note']}")
    md += ["", f"## Tests", f"- `{json.dumps(data['tests'], ensure_ascii=False)}`", ""]

    md_path = out_dir / "p119_assembly_report.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}
