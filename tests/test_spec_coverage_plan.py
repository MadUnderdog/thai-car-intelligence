"""The spec-expansion plan must track reality and must never claim work done.

Guards for requirement P100-D: identify high-value sources, stage nothing,
harvest nothing.
"""
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(REPO, "audit", "spec-coverage-plan.json")
ART_DIR = os.path.join(REPO, "tests", "fixtures", "oem-artifacts")
MARKERS = {
    "thai_ps": r"แรงม้า",
    "torque_nm": r"\b\d{3}\s*(?:Nm|นิวตันเมตร)",
    "kw": r"\b\d{2,3}\s*kW\b",
    "kwh": r"\b\d{2,3}\s*kWh\b",
    "displacement": r"\b\d\.\d\s*(?:L|ลิตร|cc)\b",
    "fuel_consumption": r"(?:ประหยัดน้ำมัน|km/l|กม\./ลิตร)",
}


def _plan():
    with open(PLAN, encoding="utf-8") as f:
        return json.load(f)


def _fresh_scan():
    out = {}
    for name in sorted(os.listdir(ART_DIR)):
        if not name.endswith(".html"):
            continue
        raw = open(os.path.join(ART_DIR, name), encoding="utf-8", errors="ignore").read()
        counts = {k: len(re.findall(p, raw)) for k, p in MARKERS.items()}
        if sum(counts.values()):
            out[f"tests/fixtures/oem-artifacts/{name}"] = counts
    return out


def test_plan_exists_and_admits_no_work_was_done():
    plan = _plan()
    assert plan["purpose"].startswith("evidence-led spec expansion")
    assert "stages no specs" in plan["purpose"]
    assert plan["current_state"]["rows_with_specs"] == 72
    assert plan["current_state"]["brands_with_specs"] == ["porsche"]


def test_tier1_evidence_matches_a_fresh_artifact_scan():
    plan = _plan()
    tier1 = plan["tiers"][0]
    assert tier1["name"].startswith("already-captured")
    fresh = _fresh_scan()
    listed = {e["artifact"]: e["marker_counts"] for e in tier1["evidence"]}
    # every listed artifact still carries its figures, and nothing was invented
    assert listed, "plan lists no in-hand spec evidence"
    for artifact, counts in listed.items():
        assert artifact in fresh, f"{artifact} no longer carries spec markers"
        for key, n in counts.items():
            assert fresh[artifact][key] == n, (
                f"{artifact}:{key} plan says {n}, artifact scan says {fresh[artifact][key]}"
            )
    # and the plan is not quietly omitting an artifact that carries more
    omitted = {k: v for k, v in fresh.items() if k not in listed
               and sum(v.values()) > 0}
    assert not omitted, f"artifacts with spec markers missing from the plan: {list(omitted)}"


def test_tier2_targets_come_from_captured_documents_not_speculation():
    plan = _plan()
    tier2 = plan["tiers"][1]
    assert tier2["evidence"], "no linked targets recorded"
    spec_link = re.compile(r'href="([^"]*(?:spec|specification|technical)[^"]*)"', re.I)
    for artifact, urls in tier2["evidence"].items():
        path = os.path.join(REPO, artifact)
        raw = open(path, encoding="utf-8", errors="ignore").read()
        real = sorted(set(spec_link.findall(raw)))
        assert sorted(set(urls)) == real, (
            f"{artifact}: plan targets differ from the links actually in the document"
        )
    # targets must be navigable: real URLs, or in-page anchors (e.g. Mini's
    # #technical-data-... sections — which themselves prove the tables are on
    # the artifact we already hold, so tier 2 partly needs no fetch at all)
    every = [u for urls in tier2["evidence"].values() for u in urls]
    assert every, "tier 2 lists no targets at all"
    junk = [u for u in every if u.lower().startswith(("javascript:", "mailto:")) or not u.strip()]
    assert not junk, f"non-navigable spec targets: {junk[:5]}"
    anchors = [u for u in every if u.startswith("#")]
    absolute = [u for u in every if u.startswith(("http://", "https://", "/"))]
    assert absolute or anchors
    assert any(("spec" in u.lower() or "technical" in u.lower()) for u in every)
    # anchors vs remote URLs, surfaced so the plan's cost estimate stays honest
    assert len(anchors) + len(absolute) == len(every), "unclassified targets present"


def test_plan_proposes_no_harvesting_and_keeps_media_secondary():
    plan = _plan()
    guards = " ".join(plan["guardrails"])
    assert "no mass harvesting" in guards
    assert "mutation test" in guards
    tier3 = plan["tiers"][2]
    body = json.dumps(tier3, ensure_ascii=False)
    assert "RESEARCH_UNVERIFIED" in body
    assert "never promoted to official" in body
    assert tier3["action"].startswith("only where")
