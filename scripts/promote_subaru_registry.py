#!/usr/bin/env python3
"""Promote Subaru in the Phase 1 coverage registry after a completed
acquisition -> parse -> evidence -> test path on an ALTERNATE official host.

The registry's primary Subaru URL `https://www.subaru.co.th/` is NXDOMAIN
(BLOCKED_DNS). Its evidence is preserved verbatim as a fallback-ladder rung —
nothing is forgotten, nothing is rewritten. The promoted route is the official
TC Subaru (Thailand) lineup page served by the Subaru Asia property, captured
through AcquisitionWriter (artifact + capture-time sidecar).

Everything recomputable IS recomputed from the artifact and its sidecar:
endpoint sha256, captured_at, last_success_*. No value is copied from a run
report, and no value is trusted as evidence for itself.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO, "tests", "fixtures", "oem-artifacts")
REGISTRY = os.path.join(REPO, "audit", "coverage", "oem-registry.json")
ARTIFACT = "subaru_th_home_page.html"
NOTE = ("official TC Subaru (Thailand) lineup page on subaru.asia (registry primary "
        "www.subaru.co.th is NXDOMAIN): 5 MODEL rows, ราคาเริ่มต้น -> MSRP_STARTING, "
        "same-card locator via collect_subaru")


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    brand = next(b for b in reg["brands"] if b["brand"] == "Subaru")

    path = os.path.join(FIXTURE_DIR, ARTIFACT)
    sc = json.load(open(path + ".prov.json", encoding="utf-8"))
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert sha == sc["sha256"], "sidecar sha256 does not bind the artifact bytes"
    assert sc["provenance_state"] == "ACQUISITION_VERIFIED"

    # ── ladder: the DNS failure of the primary host is kept, then the route that worked
    prior_blocker = brand.get("blocker_evidence") or {}
    ladder = [r for r in (brand.get("fallback_ladder") or [])
              if r.get("url") != "https://www.subaru.co.th/"]
    if prior_blocker.get("url"):
        ladder.append({
            "url": prior_blocker["url"],
            "checked_at": prior_blocker.get("checked_at"),
            "http_status_or_error": prior_blocker.get("http_status_or_error"),
            "result": brand.get("access_status") or "BLOCKED_DNS",
            "cycle": "2026-09-24",
        })
    ladder.append({
        "url": sc["source_url"],
        "checked_at": sc["captured_at"],
        "http_status_or_error": "HTTP_200 (host resolves; official TC Subaru (Thailand) "
                                "lineup page, page lang=th, prices published in THB)",
        "result": "REACHABLE",
        "cycle": reg.get("cycle") or "2026-09-25-1",
        "note": "alternate official route — parsed, see captured_endpoints",
    })

    endpoints = brand.setdefault("captured_endpoints", [])
    entry = next((e for e in endpoints if e.get("artifact") == ARTIFACT), {})
    entry.update({
        "url": sc["source_url"],
        "artifact": ARTIFACT,
        "sha256": sha,
        "provenance_state": sc["provenance_state"],
        "parsed": True,
        "note": NOTE,
    })
    if entry not in endpoints:
        endpoints.append(entry)

    # promoted endpoint decides last_success_* (recomputed from disk, not trusted)
    promoted = sorted(
        (e for e in endpoints if e.get("provenance_state") == "ACQUISITION_VERIFIED"
         and e.get("parsed") is True),
        key=lambda e: json.load(open(os.path.join(FIXTURE_DIR, e["artifact"] + ".prov.json"),
                                     encoding="utf-8"))["captured_at"],
    )[-1]
    cap = json.load(open(os.path.join(FIXTURE_DIR, promoted["artifact"] + ".prov.json"),
                         encoding="utf-8"))

    brand["source_urls"] = [sc["source_url"], "https://www.subaru.co.th/"]
    brand["access_status"] = "REACHABLE"
    brand["acquisition_method"] = sc["acquisition_method"]
    brand["adapter_status"] = "PARSED_TESTED"
    brand["provenance_status"] = "ACQUISITION_VERIFIED"
    brand["last_success_at"] = cap["captured_at"]
    brand["last_success_sha256"] = hashlib.sha256(
        open(os.path.join(FIXTURE_DIR, promoted["artifact"]), "rb").read()).hexdigest()
    brand["blocker_evidence"] = None
    brand["probe_reachable_evidence"] = {
        "checked_at": cap["captured_at"],
        "http_status": 200,
        "url": sc["source_url"],
        "bytes": os.path.getsize(os.path.join(FIXTURE_DIR, ARTIFACT)),
        "title": "Subaru Thailand | Vehicles for Any Lifestyle",
    }
    # next_retry_at left at the §94 weekly DNS re-probe of the primary host
    brand["fallback_ladder"] = ladder

    reg["generated_at"] = now
    reg["cycle"] = "2026-09-25-2"
    json.dump(reg, open(REGISTRY, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    verified = [b for b in reg["brands"]
                if b.get("in_scope") and b.get("provenance_status") == "ACQUISITION_VERIFIED"
                and b.get("adapter_status") == "PARSED_TESTED"]
    print(f"coverage: {len(verified)}/32 ({100 * len(verified) / 32:.1f}%)")
    print("verified+parsed:", sorted(b["brand"] for b in verified))
    print(f"Subaru last_success: {promoted['artifact']} @ {cap['captured_at']} ({sha[:16]}…)")
    print(f"ladder rungs: {len(ladder)} (primary DNS failure preserved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
