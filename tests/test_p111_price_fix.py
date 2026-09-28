"""P111 — focused regression for the price semantic edge + the bounded pass.

Red-first target (reported by the P110 audit): the MG EP / PLUS row is
`price_type=EXACT_VARIANT` while `trust_tier=reference` and
`currentness=NOT_A_CURRENTNESS_SOURCE`, so it is an *exact binding* that is
NOT a verified current official MSRP.  The pass must classify that explicitly
and keep the four buckets mutually exclusive, without touching the identity
ledger, verifier or any production contract.
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
    "p111_price_pass", os.path.join(REPO, "scripts/p111_price_pass.py"))
P111 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P111)

MSRP_STATUSES = {"EXACT_CURRENT_MSRP_VERIFIED", "EXACT_BINDING_NOT_VERIFIED_CURRENT",
                 "MSRP_STARTING_NOT_EXACT", "NON_MSRP_TYPE"}


def _load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def _rows():
    return _load("p111_price_evidence.json")["rows"]


# ───────────────── A. the one known price semantic edge ────────────────────

def test_mg_row_is_classified_as_binding_but_not_verified_current_msrp():
    rows = [r for r in _rows()
            if r["manufacturer"] == "MG" and r["model"] == "Mg Ep" and r["variant"] == "PLUS"]
    assert rows, "the audited MG row must survive the pass with its evidence preserved"
    row = rows[0]
    assert row["price_thb"] == 771_000 and row["artifact"] == "mg_home_page.html"
    assert row["price_type"] == "EXACT_VARIANT"
    assert row["msrp_status"] == "EXACT_BINDING_NOT_VERIFIED_CURRENT", row
    assert row["is_exact_msrp"] is False
    assert row["trust_tier"] == "reference"
    assert row["currentness"] == "NOT_A_CURRENTNESS_SOURCE"
    assert "reference" in row["msrp_status_reason"] or "not current" in row["msrp_status_reason"]


def test_msrp_status_is_derived_from_evidence_not_from_price_type_alone():
    row = {"price_type": "EXACT_VARIANT", "trust_tier": "official_verified",
           "currentness": "CURRENT"}
    assert P111.msrp_status(row) == "EXACT_CURRENT_MSRP_VERIFIED"
    row = {"price_type": "EXACT_VARIANT", "trust_tier": "reference",
           "currentness": "CURRENT"}
    assert P111.msrp_status(row) == "EXACT_BINDING_NOT_VERIFIED_CURRENT"
    row = {"price_type": "EXACT_VARIANT", "trust_tier": "official_verified",
           "currentness": "HISTORICAL"}
    assert P111.msrp_status(row) == "EXACT_BINDING_NOT_VERIFIED_CURRENT"
    row = {"price_type": "MSRP_STARTING", "trust_tier": "official_verified",
           "currentness": "CURRENT"}
    assert P111.msrp_status(row) == "MSRP_STARTING_NOT_EXACT"
    row = {"price_type": "PROMOTIONAL", "trust_tier": "official_verified",
           "currentness": "CURRENT"}
    assert P111.msrp_status(row) == "NON_MSRP_TYPE"


def test_every_price_row_carries_an_msrp_status_and_reason():
    for r in _rows():
        assert r["msrp_status"] in MSRP_STATUSES, r
        assert len(r["msrp_status_reason"]) > 15


def test_buckets_are_mutually_exclusive_and_cover_every_bound_row():
    recon = _load("p111_price_reconciliation.json")
    buckets = ["exact_msrp_verified", "exact_binding_not_verified_current",
               "msrp_starting_not_exact", "non_msrp_type_rows"]
    total = sum(recon[b] for b in buckets)
    assert total == recon["price_bound"] == len(_rows()), (total, recon["price_bound"])
    dist = recon["msrp_status_distribution"]
    assert set(dist) <= MSRP_STATUSES and sum(dist.values()) == recon["price_bound"]
    assert recon["exact_msrp_verified"] == sum(
        1 for r in _rows() if r["msrp_status"] == "EXACT_CURRENT_MSRP_VERIFIED")
    assert recon["exact_binding_not_verified_current"] == sum(
        1 for r in _rows() if r["msrp_status"] == "EXACT_BINDING_NOT_VERIFIED_CURRENT")


def test_verified_msrp_baseline_rises_and_stays_official_current_only():
    res = _load("p111_final_result.json")
    recon = _load("p111_price_reconciliation.json")
    assert res["exact_msrp_verified"] == recon["exact_msrp_verified"]
    assert res["exact_msrp_verified"] >= 246, "KPI must not regress vs P110"
    for r in _rows():
        if r["msrp_status"] == "EXACT_CURRENT_MSRP_VERIFIED":
            assert r["trust_tier"] == "official_verified"
            assert r["currentness"] == "CURRENT"
            assert r["price_type"] == "EXACT_VARIANT"


# ───────────────────────── B. bounded source expansion ─────────────────────

def test_identity_ledger_and_boundaries_unchanged():
    base = _load("p108_final_result.json")
    assert base["before_after"]["first_party_confirmed_variants"] == [482, 488]
    res = _load("p111_final_result.json")
    assert res["identity_ledger_unchanged"] == {"confirmed_variants": 488,
                                                "changed_by_p111": False}
    assert res["gates"] == {"staging_written": False, "price_pass_staging": False,
                            "prisma_touched": False, "production_db_unchanged": True,
                            "verifier_touched": False, "identity_counts_changed": False}
    assert _load("p110_final_result.json")["identity_ledger_unchanged"][
        "confirmed_variants"] == 488


def test_new_captures_have_sidecars_and_hashes():
    log = _load("p111_price_capture_log.json")
    assert log["new_captures"] == len([r for r in log["results"] if r.get("ok")])
    for r in log["results"]:
        if not r.get("ok"):
            continue
        path = os.path.join(REPO, "tests/fixtures/oem-artifacts", r["filename"])
        assert os.path.exists(path), r["filename"]
        side = path + ".prov.json"
        assert os.path.exists(side), f"missing sidecar for {r['filename']}"
        prov = json.load(open(side, encoding="utf-8"))
        assert prov["provenance_state"] == "ACQUISITION_VERIFIED"
        assert prov["sha256"] == r["sha256"]
        assert hashlib.sha256(open(path, "rb").read()).hexdigest() == r["sha256"]
        assert prov["source_url"].startswith("https://")


def test_inventory_is_one_batch_of_official_thai_price_sources():
    inv = _load("p111_price_source_inventory.json")
    assert inv["entries"], "discovery must produce an inventory"
    assert inv["unverified_baseline"]["Porsche"] == 69
    blocked = {"BYD", "Audi", "Chevrolet", "Ford", "Tesla", "Chery", "Haval",
               "NETA", "Peugeot", "Volvo", "Avance", "Mercedes-Benz", "Smart"}
    allowed_family = {"price_document", "grade_table", "configurator",
                      "structured_payload", "model_page", "downloadable_pdf",
                      "other"}
    selected = [e for e in inv["entries"] if e.get("selected")]
    assert selected, "one inventory must select a bounded batch"
    assert len(selected) == inv["selected"] <= 140
    priceish = 0
    for e in inv["entries"]:
        assert e["brand"] not in blocked, f"blocked OEM reached discovery: {e['brand']}"
        if e.get("selected"):
            assert e["url"].startswith(("https://", "http://")), e["url"]
            assert e["source_family"] in allowed_family, e
            assert e["discovery_channel"] in {"stored_pool_p108", "fresh_sitemap_index",
                                              "known_official_pattern"}, e
            assert e["unverified_at_baseline"] > 0, e
            if e["source_family"] in {"price_document", "grade_table", "configurator",
                                      "structured_payload"}:
                priceish += 1
    assert priceish >= 10, "the batch must be anchored on dedicated price sources"


def test_no_third_party_row_is_promoted_to_verified_msrp():
    recon = _load("p111_price_reconciliation.json")
    assert recon["prices_invented"] == 0
    assert recon["third_party_promoted_to_msrp"] == 0
    for r in _rows():
        if r["msrp_status"] == "EXACT_CURRENT_MSRP_VERIFIED":
            assert r["source_class"] == "MARKET_TRUTH"
            assert r["trust_tier"] != "reference"


def test_unverified_rows_keep_their_reasons_and_the_no_loop_rule():
    recon = _load("p111_price_reconciliation.json")
    assert recon["price_bound"] + recon["unverified_price"] == 488
    assert recon["price_bound"] == recon["before"]["price_bound"] + recon["delta_price_bound"] \
        if recon.get("before") else True
    for u in recon["unverified"]:
        assert u["status"] == "UNVERIFIED_PRICE" and len(u["reason"]) > 40


GENERATED = ("p111_price_evidence.json", "p111_price_evidence.json.prov.json",
             "p111_price_reconciliation.json", "p111_final_result.json",
             "p111_price_capture_log.json", "p111_price_source_inventory.json")


def test_deterministic_rerun_and_frozen_inputs():
    watched = [os.path.join(OUT, n) for n in
               ("p108_final_result.json", "p110_final_result.json",
                "identity_universe_p108.json")]
    before = {p: hashlib.sha256(open(p, "rb").read()).hexdigest() for p in watched}
    snap_bytes = {n: open(os.path.join(OUT, n), "rb").read()
                  for n in GENERATED}
    snap = {n: json.loads(b.decode("utf-8")) for n, b in snap_bytes.items()}
    try:
        r = subprocess.run(["python3", "scripts/p111_price_pass.py"], cwd=REPO,
                           capture_output=True, text=True, timeout=900)
        assert r.returncode == 0, r.stderr[-2000:]
        after = {p: hashlib.sha256(open(p, "rb").read()).hexdigest()
                 for p in watched}
        assert before == after, "P108/P110 accepted artifacts must not be rewritten"
        for n in ("p111_price_evidence.json", "p111_price_reconciliation.json",
                  "p111_final_result.json"):
            new = json.loads(open(os.path.join(OUT, n), encoding="utf-8").read())
            old = snap[n]
            old.pop("generated_at", None)
            new.pop("generated_at", None)
            assert new == old, f"{n} differs between runs"
    finally:
        # the rerun rewrites committed artifacts (run stamps); restore the
        # exact byte snapshot so no later test sees a dirty tree.
        for n, b in snap_bytes.items():
            with open(os.path.join(OUT, n), "wb") as fh:
                fh.write(b)
    # regression: after the test, every generated file is byte-identical
    for n, b in snap_bytes.items():
        assert open(os.path.join(OUT, n), "rb").read() == b, \
            f"{n} was not byte-restored after the rerun"
