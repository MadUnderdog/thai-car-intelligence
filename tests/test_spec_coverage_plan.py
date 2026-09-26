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


def _fresh_state():
    """Recompute the plan's current_state from the staging file itself."""
    staging = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
    total = with_specs = 0
    brands = set()
    with open(staging, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            total += 1
            if row.get("specs"):
                with_specs += 1
                brands.add(row["identity"]["brand_normalized"])
    return {
        "rows_with_specs": with_specs,
        "total_rows": total,
        "coverage_pct": round(100.0 * with_specs / total, 1) if total else 0.0,
        "brands_with_specs": sorted(brands),
    }


def _generator():
    import importlib.util
    path = os.path.join(REPO, "scripts", "generate_spec_coverage_plan.py")
    spec = importlib.util.spec_from_file_location("gen_spec_coverage_plan", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    # numbers are recomputed from the staging file, never remembered: a literal
    # here would start lying the moment a later wave adds rows
    fresh = _fresh_state()
    state = plan["current_state"]
    for key, value in fresh.items():
        assert state[key] == value, f"current_state.{key}: plan {state[key]} != staging {value}"
    assert state["rows_with_specs"] > 0
    assert state["brands_with_specs"]


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


def test_tier1_confidence_is_derived_from_the_artifact_not_declared():
    """The plan's ranking claim has to be reproducible from the bytes it points at."""
    plan = _plan()
    gen = _generator()
    evidence = plan["tiers"][0]["evidence"]
    assert evidence, "tier 1 lists no in-hand source"
    for entry in evidence:
        raw = open(os.path.join(REPO, entry["artifact"]), encoding="utf-8",
                   errors="ignore").read()
        for key, value in gen.structure_signal(raw).items():
            assert entry[key] == value, (
                f"{entry['artifact']}:{key} plan says {entry[key]}, artifact says {value}"
            )
    totals = [e["marker_total"] for e in evidence]
    assert totals == sorted(totals, reverse=True), "tier 1 must rank highest-value first"
    assert evidence[0]["confidence"] == "high", (
        "the lead spec source must be a structured one, not prose"
    )


def test_route_safety_matches_the_registry_blocked_hosts():
    """No tier-2 target may be planned against a host the registry has blocked."""
    plan = _plan()
    safety = plan["route_safety"]
    with open(os.path.join(REPO, "audit", "coverage", "oem-registry.json"),
              encoding="utf-8") as f:
        reg = json.load(f)

    def host(url):
        m = re.match(r"https?://([^/:]+)", url or "")
        return m.group(1).lower() if m else None

    expect = {}
    for brand in reg["brands"]:
        status = brand.get("access_status") or ""
        if status == "REACHABLE" or not status:
            continue
        urls = list(brand.get("source_urls") or [])
        urls.append((brand.get("blocker_evidence") or {}).get("url"))
        for url in urls:
            h = host(url)
            if h:
                expect.setdefault(h, status)
    flagged = {h: v["access_status"]
               for h, v in safety["registry_hosts_not_reachable"].items()}
    assert flagged == expect, (
        f"route_safety hosts {sorted(flagged)} differ from registry {sorted(expect)}"
    )
    for artifact, urls in plan["tiers"][1]["evidence"].items():
        for url in urls:
            h = host(url)
            if h and h in flagged:
                rec = safety["tier2_hosts"].get(h)
                assert rec, f"{artifact}: target host {h} not classified by route_safety"
                assert rec["blocked_or_wrong_target"] is True, h
                assert rec["registry_state"] == flagged[h], h
    assert safety["rule"].endswith("makes no request")


def test_wrong_target_captures_never_feed_the_plan():
    plan = _plan()
    excluded = plan["route_safety"]["excluded_wrong_target_artifacts"]
    assert excluded, "no wrong-target capture recorded — Smart's capture must be excluded"
    for name in excluded:
        for tier in plan["tiers"]:
            listed = tier["evidence"]
            if isinstance(listed, list):
                hits = [e["artifact"] for e in listed if e["artifact"].endswith(name)]
            elif isinstance(listed, dict):
                hits = [k for k in listed if str(k).endswith(name)]
            else:
                hits = []
            assert not hits, f"{name} still feeds tier {tier['tier']}: {hits}"


def test_plan_generation_is_offline_and_reproducible(monkeypatch):
    """Regenerating the plan must touch no network and rewrite identical bytes."""
    import socket
    before = open(PLAN, "rb").read()

    def deny(*args, **kwargs):
        raise AssertionError("spec plan generation attempted network I/O")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    _generator().main()
    after = open(PLAN, "rb").read()
    assert after == before, "plan is not reproducible from the current artifacts"
