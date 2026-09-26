#!/usr/bin/env python3
"""Promote GWM in the Phase 1 coverage registry after a completed
acquisition -> parse -> evidence -> test path.

Everything that can be recomputed IS recomputed from the artifacts and their
sidecars: endpoint sha256, captured_at, last_success_*. Nothing is copied from
a previous run report.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO, "tests", "fixtures", "oem-artifacts")
REGISTRY = os.path.join(REPO, "audit", "coverage", "oem-registry.json")
NOTE = ("official /th/models/<slug> price page (discovered via gwm.co.th sitemap "
        "index): hero ราคาเริ่มต้น/MSRP block + configurator cards -> parsed; "
        "campaign-derived hero figures rejected, see gwm_price_candidates log")


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    gwm = next(b for b in reg["brands"] if b["brand"] == "GWM")

    endpoints = gwm.setdefault("captured_endpoints", [])
    by_artifact = {e.get("artifact"): e for e in endpoints}

    parsed_artifacts = []
    for fn in sorted(os.listdir(FIXTURE_DIR)):
        if not (fn.startswith("gwm_th_model_") and fn.endswith(".html")):
            continue
        path = os.path.join(FIXTURE_DIR, fn)
        sc = json.load(open(path + ".prov.json", encoding="utf-8"))
        sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
        assert sha == sc["sha256"], fn
        entry = by_artifact.get(fn) or {}
        entry.update({
            "url": sc["source_url"],
            "artifact": fn,
            "sha256": sha,
            "provenance_state": sc["provenance_state"],
            "parsed": True,
            "note": NOTE,
        })
        if entry not in endpoints:
            endpoints.append(entry)
        parsed_artifacts.append((sc["captured_at"], fn, sha))

    # newest promoted artifact decides last_success_* (recomputed, not trusted)
    captured_at, fn, sha = max(parsed_artifacts)
    gwm["provenance_status"] = "ACQUISITION_VERIFIED"
    gwm["adapter_status"] = "PARSED_TESTED"
    gwm["access_status"] = "REACHABLE"
    gwm["acquisition_method"] = "http_get"
    gwm["last_success_at"] = captured_at
    gwm["last_success_sha256"] = sha
    gwm["blocker_evidence"] = None

    reg["generated_at"] = now
    reg["cycle"] = "2026-09-25-1"
    json.dump(reg, open(REGISTRY, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    verified = [b for b in reg["brands"]
                if b.get("in_scope") and b.get("provenance_status") == "ACQUISITION_VERIFIED"
                and b.get("adapter_status") == "PARSED_TESTED"]
    print(f"coverage: {len(verified)}/32 "
          f"({100 * len(verified) / 32:.1f}%)")
    print("verified+parsed:", sorted(b["brand"] for b in verified))
    print(f"GWM last_success: {fn} @ {captured_at} ({sha[:16]}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
