"""P113 — focused regression: Phase-1 evidence packets + fail-closed acceptance.

Red-first: written before `scripts/p113_evidence_packets.py` existed.
The pass must build ONE packet per frozen accepted variant, cite only
provenance-intact observations, run the EXISTING AcceptanceRunner over them,
and keep promotion disabled for every packet.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "audit/coverage")
FIXTURE_DIR = os.path.join(REPO, "tests/fixtures/oem-artifacts")
SPEC = importlib.util.spec_from_file_location(
    "p113_evidence_packets",
    os.path.join(REPO, "scripts/p113_evidence_packets.py"))
P113 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P113)

WATCHED = [
    "identity_universe_p108.json",
    "p111_price_evidence.json", "p111_price_evidence.json.prov.json",
    "p111_final_result.json", "p111_price_reconciliation.json",
    "p112_spec_evidence.json", "p112_spec_evidence.json.prov.json",
    "p112_final_result.json", "p112_spec_reconciliation.json",
]


def _load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _packets():
    return _load("p113_evidence_packets.json")["packets"]


def _ledger():
    u = _load("identity_universe_p108.json")
    return [r for r in u["universe"]["records"]
            if r["status"] == "CONFIRMED_VARIANT"]


# ───────────────────────────── plan ───────────────────────────────────────

def test_plan_written_before_build_and_matches_inputs():
    plan = _load("p113_packet_target_plan.json")
    assert plan["method"]["written_before_build"] is True
    assert plan["audit_snapshot"]["head"]
    assert plan["inputs"]["accepted_variants"] == 488
    assert plan["inputs"]["p111"]["price_rows"] == 299
    assert plan["inputs"]["p111"]["exact_current_msrp_verified"] == 269
    assert plan["inputs"]["p111"]["msrp_starting_not_exact"] == 29
    assert plan["inputs"]["p111"]["exact_binding_not_verified_current"] == 1
    assert plan["inputs"]["p111"]["unverified_price"] == 189
    assert plan["inputs"]["p112"]["spec_rows"] == 1389
    assert plan["inputs"]["p112"]["variants_with_spec_evidence"] == 126
    pol = {p["id"] for p in plan["policies"]}
    assert pol == {"IDENTITY_ACCEPTABLE", "PRICE_ACCEPTABLE",
                   "SPEC_ACCEPTABLE", "PACKET_ACCEPTED",
                   "PROMOTION_ELIGIBLE", "QUARANTINE_REASONS"}
    assert plan["boundaries"]["promotion_eligible"] is False
    assert plan["boundaries"]["staging_write"] is False
    assert plan["boundaries"]["production_db"] is False
    assert plan["boundaries"]["new_acquisition"] is False
    assert plan["boundaries"]["ai_reconciliation"] is False
    # reuse: the existing acceptance abstraction was audited, not reinvented
    assert plan["audit_snapshot"]["reused_modules"]


# ───────────────────────────── packets ────────────────────────────────────

def test_one_packet_per_frozen_ledger_row():
    packets = _packets()
    ledger = _ledger()
    assert len(packets) == len(ledger) == 488
    ledger_keys = {(r["manufacturer"], r["model"], r["variant"],
                    r["scope"]) for r in ledger}
    packet_keys = {(p["manufacturer"], p["model"], p["variant"],
                    p["scope"]) for p in packets}
    assert packet_keys == ledger_keys, "packets must be exactly the ledger"
    assert len({p["candidate_key"] for p in packets}) == 488
    led_by_key = {r["canonical_key"]: r for r in ledger}
    for p in packets:
        src = led_by_key[p["candidate_key"]]
        assert p["manufacturer"] == src["manufacturer"]
        assert p["model"] == src["model"]
        assert p["variant"] == src["variant"]
        assert p["scope"] == "TH"
        assert p["generation_context"] == (src.get("generation") or "")


def test_every_cited_observation_is_provenance_intact():
    for p in _packets():
        for group in ("identity", "price", "spec"):
            for obs in p["observations"][group]:
                assert obs["cited"] is True, obs
                assert obs["source_url"].startswith("https://")
                assert obs["provenance_state"] == "ACQUISITION_VERIFIED"
                assert obs["source_class"] == "MARKET_TRUTH"
                path = os.path.join(FIXTURE_DIR, obs["artifact"])
                assert os.path.exists(path), obs["artifact"]
                assert obs["sha256"] == _sha(path), obs
                assert obs["locator"]["resolved"] is True, obs
                assert obs["runner_decision"] in {"ACCEPTED",
                                                  "QUARANTINED", "REJECTED",
                                                  "UNRESOLVED", "CONFLICT"}
                assert obs["runner_reason"], obs


def test_identity_acceptance_is_fail_closed():
    packets = _packets()
    ledger = _ledger()
    led_keys = {(r["manufacturer"], r["model"], r["variant"]) for r in ledger}
    for p in packets:
        intact = [o for o in p["observations"]["identity"] if o["cited"]]
        failed = p["quarantine"]["identity"]
        if p["policy"]["identity_acceptable"]:
            assert intact, p["packet_id"]
            assert (p["manufacturer"], p["model"], p["variant"]) in led_keys
        else:
            assert not intact and failed, p["packet_id"]
            assert p["status"] in {"QUARANTINED", "REJECTED"}
    # the two Isuzu rows whose sole source has no sidecar must fail closed
    bad = [p for p in packets if not p["policy"]["identity_acceptable"]]
    iso = {(p["manufacturer"], p["model"], p["variant"]) for p in bad}
    assert ("Isuzu", "MU-X", "Active") in iso
    assert ("Isuzu", "Isuzu D Max", "L") in iso
    for p in bad:
        assert p["not_accepted_reasons"], p["packet_id"]
        assert all(r["reason"] for r in p["not_accepted_reasons"])
        if (p["manufacturer"], p["model"], p["variant"]) in {
                ("Isuzu", "MU-X", "Active"), ("Isuzu", "Isuzu D Max", "L")}:
            assert any("sidecar_missing" in reason
                       for entry in p["quarantine"]["identity"]
                       for reason in entry["reasons"]), p["packet_id"]


def test_price_semantics_follow_p111_buckets():
    p111 = _load("p111_price_evidence.json")
    buckets = {"EXACT_CURRENT_MSRP_VERIFIED": 0,
               "MSRP_STARTING_NOT_EXACT": 0,
               "EXACT_BINDING_NOT_VERIFIED_CURRENT": 0}
    for r in p111["rows"]:
        buckets[r["msrp_status"]] += 1
    seen = {"EXACT_CURRENT_MSRP_VERIFIED": 0,
            "MSRP_STARTING_NOT_EXACT": 0,
            "EXACT_BINDING_NOT_VERIFIED_CURRENT": 0}
    no_price = 0
    current_claimed = 0
    for p in _packets():
        st = p["policy"]["price_status"]
        if st == "NO_P111_PRICE_EVIDENCE":
            no_price += 1
            assert p["observations"]["price"] == []
            continue
        assert st in seen, st
        seen[st] += 1
        for o in p["observations"]["price"]:
            assert o["msrp_status"] == st
            if o["counts_as_current_msrp"]:
                current_claimed += 1
                assert st == "EXACT_CURRENT_MSRP_VERIFIED"
                assert o["currentness"] == "CURRENT"
    assert seen == buckets == {"EXACT_CURRENT_MSRP_VERIFIED": 269,
                               "MSRP_STARTING_NOT_EXACT": 29,
                               "EXACT_BINDING_NOT_VERIFIED_CURRENT": 1}
    assert no_price == 189
    assert current_claimed == 269
    mg = [p for p in _packets()
          if p["policy"]["price_status"] ==
          "EXACT_BINDING_NOT_VERIFIED_CURRENT"]
    assert len(mg) == 1
    assert mg[0]["manufacturer"] == "MG"
    assert mg[0]["model"] == "Mg Ep" and mg[0]["variant"] == "PLUS"
    assert all(o["counts_as_current_msrp"] is False
               for o in mg[0]["observations"]["price"])


def test_spec_semantics_follow_p112_evidence():
    p112 = _load("p112_spec_evidence.json")
    assert sum(len(p["observations"]["spec"]) for p in _packets()) == \
        len(p112["rows"]) == 1389
    with_spec = [p for p in _packets() if p["observations"]["spec"]]
    assert len(with_spec) == 126
    for p in _packets():
        for o in p["observations"]["spec"]:
            assert o["binding"] in {"variant_page", "grade_named_row",
                                    "structured_grade_node"}
            assert o["trust_tier"] == "official_verified"
            assert o["currentness"] == "CURRENT"
            if o["value_numeric"] is not None:
                assert o["unit"], o
        if not p["observations"]["spec"]:
            assert p["field_gaps"]["spec"], p["packet_id"]


def test_field_gaps_are_stated_not_filled():
    p111_unv = _load("p111_price_reconciliation.json")["unverified"]
    p112_gaps = _load("p112_spec_reconciliation.json")["gaps"]
    by_key = {p["candidate_key"]: p for p in _packets()}
    led = {(r["manufacturer"], r["model"], r["variant"]): r
           for r in _ledger()}
    for row in p111_unv:
        p = by_key[led[(row["manufacturer"], row["model"],
                        row["variant"])]["canonical_key"]]
        assert p["field_gaps"]["price"], row
        assert p["policy"]["price_status"] == "NO_P111_PRICE_EVIDENCE"
        assert p["policy"]["price_acceptable"] is False
        # the published category/reason survives verbatim — no invented gap
        assert row["category"][:40] in json.dumps(
            p["field_gaps"]["price"], ensure_ascii=False)
    for g in p112_gaps:
        p = by_key[led[(g["manufacturer"], g["model"],
                        g["variant"])]["canonical_key"]]
        assert p["field_gaps"]["spec"], g
        assert p["policy"]["spec_acceptable"] is False
        assert g["reason_class"] == p["field_gaps"]["spec"][0]["reason_class"]


def test_promotion_eligible_is_false_everywhere():
    res = _load("p113_final_result.json")
    assert res["gates"]["staging_write"] is False
    assert res["gates"]["prisma_touched"] is False
    assert res["gates"]["verifier_touched"] is False
    assert res["gates"]["production_db_unchanged"] is True
    assert res["gates"]["price_artifacts_byte_identical"] is True
    assert res["gates"]["p112_artifacts_byte_identical"] is True
    assert res["identity_ledger_unchanged"] == {"confirmed_variants": 488,
                                                "changed_by_p113": False}
    assert res["promotion_eligible_count"] == 0
    assert all(p["policy"]["promotion_eligible"] is False
               for p in _packets())


def test_acceptance_counts_are_consistent():
    acc = _load("p113_acceptance_result.json")
    rej = _load("p113_rejection_report.json")
    packets = _packets()
    assert acc["packets_built"] == len(packets) == 488
    status = {"ACCEPTED": 0, "QUARANTINED": 0, "REJECTED": 0}
    for p in packets:
        status[p["status"]] += 1
    assert acc["packets_accepted"] == status["ACCEPTED"]
    assert acc["packets_quarantined"] == status["QUARANTINED"]
    assert acc["packets_rejected"] == status["REJECTED"]
    assert sum(status.values()) == 488
    assert rej["not_accepted_count"] == \
        status["QUARANTINED"] + status["REJECTED"]
    assert len(rej["not_accepted"]) == rej["not_accepted_count"]
    for n in rej["not_accepted"]:
        assert n["reasons"], n
        assert n["status"] in {"QUARANTINED", "REJECTED"}
    for oem, v in acc["per_oem"].items():
        assert v["accepted"] + v["quarantined"] + v["rejected"] == \
            v["packets"]
    assert sum(v["packets"] for v in acc["per_oem"].values()) == 488
    assert acc["runner"]["evaluated"] >= sum(
        len(p["observations"][g]) for p in packets
        for g in ("identity", "price", "spec"))
    assert acc["usable_packet_percent"] == round(
        100.0 * status["ACCEPTED"] / 488, 1)


def test_identity_locator_matches_published_spelling():
    """Concrete defect from the first build: composed identity names failed
    to re-resolve when the publisher writes D-Max vs 'D Max', 'HEV-PRO'
    vs 'hev-pro', or an extra '+' — the matcher must compare canonically."""
    t = P113.artifact_text("isuzu_tis_page.html")
    loc = P113.identity_locator(t, "", "Isuzu D Max", "Spark")
    assert loc and loc["resolved"] and loc["mode"] == "model_and_variant"
    t = P113.artifact_text("mitsubishi_all_models_price.html")
    loc = P113.identity_locator(
        t, "", "ALL NEW MITSUBISHI TRITON", "ซิงเกิ้ล แค็บ 2.4 PRO")
    assert loc and loc["resolved"]
    t = P113.artifact_text("gwm_th_model_haval-h6.html")
    loc = P113.identity_locator(t, "", "GWM HAVAL H6", "hev-pro")
    assert loc and loc["resolved"]
    # brand-drop must still work for SHORT model tokens (BMW i5 → 'i5')
    t = P113.artifact_text("bmw_price_list.html")
    loc = P113.identity_locator(t, "", "Bmw I5", "Edrive40 M Sport")
    assert loc and loc["resolved"]


def test_fail_closed_on_corrupt_evidence_synthetic():
    # sha mismatch
    ok, reasons = P113.verify_artifact(
        "bmw_price_list.html",
        "https://www.bmw.co.th/en/topics/price-list.html", "0" * 64, {})
    assert not ok and "expected_sha_mismatch" in reasons
    # non-https
    ok, reasons = P113.verify_artifact(
        "bmw_price_list.html", "http://insecure.example/x", None, {})
    assert not ok and "non_https_source_url" in reasons
    # missing artifact
    ok, reasons = P113.verify_artifact(
        "does_not_exist.html", "https://x.example/y", None, {})
    assert not ok and "artifact_missing" in reasons
    # sidecar missing (the real Isuzu case)
    ok, reasons = P113.verify_artifact(
        "isuzu_page.html", "https://www.isuzu.co.th/", None, {})
    assert not ok and "sidecar_missing" in reasons
    # locator that does not resolve against the artifact
    text = P113.artifact_text("bmw_price_list.html")
    assert P113.locator_resolves(text, "ไม่มีตัวอักษรนี้ในไฟล์ XYZ") is False
    assert P113.locator_resolves(text, "edrive40") is True
    # wrong grade never binds (policy on observation tuples)
    assert P113.tuple_matches({"manufacturer": "Toyota", "model": "Yaris",
                               "variant": "Sport"},
                              {"manufacturer": "Toyota", "model": "Yaris",
                               "variant": "Premium"}) is False
    assert P113.tuple_matches({"manufacturer": "Toyota", "model": "Yaris",
                               "variant": "Sport"},
                              {"manufacturer": "Toyota", "model": "Yaris",
                               "variant": "Sport"}) is True


def test_runner_is_the_existing_module_not_a_rewrite():
    src = open(os.path.join(REPO, "scripts/p113_evidence_packets.py"),
               encoding="utf-8").read()
    assert "thai_factory.acceptance" in src
    assert "class AcceptanceRunner" not in src
    assert "class EvidencePacket" not in src
    acc = _load("p113_acceptance_result.json")
    assert acc["runner"]["module"] == "thai_factory.acceptance"
    counts = acc["runner"]["counts"]
    assert sum(counts.values()) == acc["runner"]["evaluated"]


def test_deterministic_rerun_and_watched_artifacts_untouched():
    watched = {n: _sha(os.path.join(OUT, n)) for n in WATCHED}
    snap = {}
    for n in ("p113_evidence_packets.json", "p113_acceptance_result.json",
              "p113_rejection_report.json", "p113_final_result.json"):
        snap[n] = json.loads(open(os.path.join(OUT, n),
                                  encoding="utf-8").read())
    try:
        r = subprocess.run(
            ["python3", "scripts/p113_evidence_packets.py", "run"],
            cwd=REPO, capture_output=True, text=True, timeout=900)
        assert r.returncode == 0, r.stderr[-2000:]
        after = {n: _sha(os.path.join(OUT, n)) for n in WATCHED}
        assert watched == after, "p111/p112/identity bytes must not move"
        for n, old in snap.items():
            new = json.loads(open(os.path.join(OUT, n),
                                  encoding="utf-8").read())
            old.pop("generated_at", None)
            new.pop("generated_at", None)
            old.pop("run_id", None)
            new.pop("run_id", None)
            assert new == old, f"{n} differs between runs"
    finally:
        for n, old in snap.items():
            with open(os.path.join(OUT, n), "w", encoding="utf-8") as fh:
                json.dump(old, fh, ensure_ascii=False, indent=2)
                fh.write("\n")


def test_pass_has_no_network_and_no_promotion_code():
    src = open(os.path.join(REPO, "scripts/p113_evidence_packets.py"),
               encoding="utf-8").read()
    assert "requests" not in src
    assert "httpx" not in src
    assert "playwright" not in src
    for token in ("prisma db push", "prisma migrate", "staging.insert",
                  "db_write"):
        assert token not in src
