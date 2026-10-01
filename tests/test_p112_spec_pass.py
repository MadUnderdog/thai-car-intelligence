"""P112 — focused regression for the specification evidence pass.

Red-first: written before `scripts/p112_spec_pass.py` existed.  The pass must
produce field-level, variant-bound spec evidence over the frozen 488-variant
ledger without inference, without touching price metrics, identity counts,
Prisma, the verifier, staging or the production DB.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "audit/coverage")
SPEC = importlib.util.spec_from_file_location(
    "p112_spec_pass", os.path.join(REPO, "scripts/p112_spec_pass.py"))
P112 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P112)

FIELD_KEYS = {f["key"] for f in P112.FIELDS}
BLOCKED = {"BYD", "Audi", "Chevrolet", "Ford", "Tesla", "Chery", "Haval",
           "NETA", "Peugeot", "Volvo", "Avance", "Mercedes-Benz", "Smart"}
# the unit must be *published in the record* — latin or thai spellings both
# count as published units, a value with no unit token is refused.
UNIT_TOKENS = {"mm": r"มม\.|\bmm\b", "cc": r"\bcc\b|ซีซี",
               "PS": r"PS|hp|แรงม้า", "Nm": r"\bNm\b|นิวตัน",
               "kWh": r"kWh|กิโลวัตต์\s*[-\u2010-]?\s*ชั่วโมง",
               "kW": r"\bkW\b|กิโลวัตต์(?!\s*[-\u2010-]?\s*ชั่วโมง)",
               "km": r"\bkm\b|กิโลเมตร", "kg": r"\bkg\b|กิโลกรัม",
               "seats": r"ที่นั่ง|seats"}


def _load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def _rows():
    return _load("p112_spec_evidence.json")["rows"]


# ───────────────────────────── plan / inventory ───────────────────────────

def test_plan_targets_the_frozen_ledger_and_wrote_before_harvest():
    plan = _load("p112_spec_target_plan.json")
    assert plan["accepted_variants_targeted"] == 488
    assert len(plan["variants"]) == 488
    assert plan["audit_snapshot"]["head"]
    assert plan["boundaries"]["price_metrics_modified"] is False
    assert plan["boundaries"]["identity_counts_changed"] is False
    assert plan["boundaries"]["ai_reconciliation"] is False
    assert {f["key"] for f in plan["field_dictionary"]} >= FIELD_KEYS
    counts = plan["priority_counts"]
    assert sum(counts.values()) == 488


def test_inventory_is_one_batch_over_documented_sources_only():
    inv = _load("p112_spec_source_inventory.json")
    fetches = [e for e in inv["entries"] if e.get("fetch")]
    assert fetches, "the batch must select its documented endpoints"
    for e in fetches:
        assert e["url"].startswith("https://")
        assert e["brand"] not in BLOCKED
        assert e["discovery_channel"] == "documented_official_endpoint"
    for e in inv["entries"]:
        assert e["brand"] not in BLOCKED, e
    # the Toyota chain is evidence-bound: codes come from its list response
    exp = inv.get("programmatic_expansion") or []
    if exp:
        assert exp[0]["series_codes_seen"] > 0
        assert exp[0]["matched_model_to_code"] or exp[0]["codes_fetched"] == []
    assert inv["totals"]["reuse_entries"] > 0


def test_new_captures_verify_sidecars_and_https():
    log = _load("p112_spec_capture_log.json")
    assert log["new_captures"] == sum(
        1 for r in log["results"] if r.get("ok")
        and r.get("new_capture") is not False)
    for r in log["results"]:
        if not r.get("ok") or r.get("new_capture") is False:
            continue
        path = os.path.join(REPO, "tests/fixtures/oem-artifacts", r["filename"])
        assert os.path.exists(path), r["filename"]
        side = path + ".prov.json"
        assert os.path.exists(side)
        prov = json.load(open(side, encoding="utf-8"))
        assert prov["provenance_state"] == "ACQUISITION_VERIFIED"
        assert prov["source_url"].startswith("https://")
        assert prov["sha256"] == r["sha256"] == hashlib.sha256(
            open(path, "rb").read()).hexdigest()
    for r in log["failures"]:
        assert r["brand"] not in BLOCKED or r["status"] == "BLOCKED_HOST"


# ───────────────────────────── evidence contract ──────────────────────────

def test_every_evidence_row_is_field_level_and_same_record():
    rows = _rows()
    assert rows, "the pass must produce spec evidence"
    for r in rows:
        assert r["field_key"] in FIELD_KEYS, r
        assert r["price_thb"] is None if "price_thb" in r else True
        assert r["scope"] == "TH"
        assert r["manufacturer"] not in BLOCKED
        assert r["binding"] in {"variant_page", "grade_named_row",
                                "structured_grade_node"}
        assert r["source_class"] == "MARKET_TRUTH"
        assert r["trust_tier"] in {"official_verified", "reference"}
        assert r["sha256"] and r["captured_at"] and r["provenance_state"]
        assert r["source_url"].startswith("https://")
        assert len(r["locator"]["excerpt"]) >= 5
        if r["value_numeric"] is not None:
            assert isinstance(r["value_numeric"], (int, float))
            assert r["unit"], r


def test_values_carry_their_published_unit_or_are_refused():
    for r in _rows():
        if r["unit"] in UNIT_TOKENS:
            import re
            assert re.search(UNIT_TOKENS[r["unit"]],
                             r["locator"]["excerpt"] + " " + r["value_text"],
                             re.I), r


def test_no_price_metric_is_written_anywhere():
    for r in _rows():
        assert "price" not in r["field_key"]
        assert "price" not in r
    recon = _load("p112_spec_reconciliation.json")
    assert recon["price_metrics_modified"] is False
    res = _load("p112_final_result.json")
    assert res["gates"]["price_pass_artifacts_unchanged"] is True


def test_binding_never_infers_from_model_level_or_sibling_records():
    # synthetic: a model-level spec line with no grade context must not bind
    row = {"line": "ความยาว 4,300 mm ความกว้าง 1,795 mm", "labels": ["GT Line"],
           "grade_in_record": False}
    assert P112.record_names_grade(row["line"], row["labels"]) is False
    assert P112.record_names_grade("Ranger Wildtrak ความยาว 5,359 mm",
                                   ["Wildtrak"]) is True
    # a grade of ANOTHER model must not borrow a sibling's payload grade
    assert P112.grade_matches("e:HEV ES", ["e:HEV E"]) is False
    assert P112.grade_matches("e:HEV ES", ["e:HEV ES"]) is True
    # shortest-label trap: Premium must not match Premium Luxury's payload
    assert P112.grade_matches("Premium", ["Premium Luxury"]) is False
    assert P112.grade_matches("Premium Luxury", ["Premium"]) is False
    assert P112.grade_matches("Premium Luxury", ["Premium Luxury"]) is True


def test_structured_toyota_payloads_bind_by_exact_grade_title():
    rows = [r for r in _rows() if r["binding"] == "structured_grade_node"]
    for r in rows:
        assert P112.grade_matches(r["variant"], [r["grade_title"]]), r
        assert r["series_code"], r


def test_reconciliation_is_consistent_and_reports_gaps():
    recon = _load("p112_spec_reconciliation.json")
    rows = _rows()
    assert recon["accepted_variants_targeted"] == 488
    assert recon["spec_evidence_rows"] == len(rows)
    with_ev = len({(r["manufacturer"], r["model"], r["variant"]) for r in rows})
    assert recon["variants_with_spec_evidence"] == with_ev
    assert recon["variants_with_spec_evidence"] + recon["variants_without_spec_evidence"] == 488
    assert sum(recon["field_coverage"].values()) == len(rows)
    assert sum(recon["binding_distribution"].values()) == len(rows)
    assert recon["identity_ledger_unchanged"]["confirmed_variants"] == 488
    for b, v in recon["per_oem"].items():
        assert v["with_evidence"] <= v["accepted_variants"]
    # every variant without evidence carries a categorised gap reason
    assert len(recon["gaps"]) == recon["variants_without_spec_evidence"]
    for g in recon["gaps"]:
        assert g["reason_class"] and len(g["reason"]) > 20


def test_kpi_deltas_and_baseline_are_reported_from_artifacts():
    res = _load("p112_final_result.json")
    recon = _load("p112_spec_reconciliation.json")
    assert res["variants_with_spec_evidence"] == recon["variants_with_spec_evidence"]
    assert res["baseline_variants_with_spec_evidence"] == 0, (
        "the audit found no prior spec-evidence layer — baseline is 0 and the "
        "delta must say so instead of inventing a history")
    assert res["delta_variants"] == res["variants_with_spec_evidence"]
    assert res["attribution"]["from_new_captures"] >= 0
    assert res["identity_ledger_unchanged"] == {"confirmed_variants": 488,
                                                "changed_by_p112": False}
    assert res["gates"]["staging_written"] is False
    assert res["gates"]["prisma_touched"] is False
    assert res["gates"]["verifier_touched"] is False
    assert res["gates"]["production_db_unchanged"] is True


GENERATED_P112 = ("p112_spec_evidence.json", "p112_spec_evidence.json.prov.json",
                  "p112_spec_reconciliation.json", "p112_final_result.json",
                  "p112_spec_target_plan.json")


def test_deterministic_rerun_and_frozen_price_artifacts():
    watched = [os.path.join(OUT, n) for n in
               ("p110_final_result.json", "p111_final_result.json",
                "p111_price_evidence.json", "p108_final_result.json")]
    before = {p: hashlib.sha256(open(p, "rb").read()).hexdigest()
              for p in watched}
    snap_bytes = {n: open(os.path.join(OUT, n), "rb").read()
                  for n in GENERATED_P112}
    snap = {n: json.loads(b.decode("utf-8")) for n, b in snap_bytes.items()}
    try:
        r = subprocess.run(["python3", "scripts/p112_spec_pass.py"],
                           cwd=REPO, capture_output=True, text=True, timeout=900)
        assert r.returncode == 0, r.stderr[-2000:]
        after = {p: hashlib.sha256(open(p, "rb").read()).hexdigest()
                 for p in watched}
        assert before == after, "price/identity artifacts must not be rewritten"
        for n in ("p112_spec_evidence.json", "p112_spec_reconciliation.json",
                  "p112_final_result.json"):
            new = json.loads(open(os.path.join(OUT, n), encoding="utf-8").read())
            old = snap[n]
            old.pop("generated_at", None)
            new.pop("generated_at", None)
            assert new == old, f"{n} differs between runs"
    finally:
        # the previous finally re-dumped a popped snapshot (losing
        # generated_at) — restore the exact committed bytes instead.
        for n, b in snap_bytes.items():
            with open(os.path.join(OUT, n), "wb") as fh:
                fh.write(b)
    # regression: after the test, every generated file is byte-identical
    for n, b in snap_bytes.items():
        assert open(os.path.join(OUT, n), "rb").read() == b, \
            f"{n} was not byte-restored after the rerun"


def test_pass_runs_without_network():
    src = open(os.path.join(REPO, "scripts/p112_spec_pass.py"),
               encoding="utf-8").read()
    assert "requests" not in src
    assert "httpx" not in src
    assert "playwright" not in src
    # the only subprocess in the pass is pdftotext over local files
    assert src.count("subprocess") <= 2
    assert "pdftotext" in src
