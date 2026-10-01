"""P110 — dedicated price pass tests (targeted, run once at end of wave).

The pass binds prices to the *same published record* of the frozen 488-variant
ledger and classifies price_type strictly (Blueprint §95/§98).  Two defects are
captured red-first: (a) a minified page whose giant first block lists every
model plus promotional text must not become a price binding; (b) promotional or
finance wording that lives in a *different* block must not reclassify a
grade-specific list price.
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
    "p110_price_pass", os.path.join(REPO, "scripts/p110_price_pass.py"))
P110 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P110)

ALLOWED_TYPES = {"EXACT_VARIANT", "MSRP_STARTING", "PROMOTIONAL",
                 "FINANCE_INSTALLMENT", "RANGE"}
PRICE_FIELDS = ("price_thb", "price_type", "currency", "scope", "artifact",
                "source_url", "sha256", "provenance_state", "captured_at",
                "session_id", "locator", "source_class", "trust_tier", "currentness")


def _load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def _evidence():
    return _load("p110_price_evidence.json")["rows"]


def _ledger():
    uni = _load("identity_universe_p108.json")
    return {(r["manufacturer"], r["model"], r["variant"])
            for r in uni["universe"]["records"] if r["status"] == "CONFIRMED_VARIANT"}


def _rec(model, variant, manufacturer="Kia"):
    return {"manufacturer": manufacturer, "model": model, "variant": variant,
            "identity_level": "VARIANT", "scope": "TH",
            "sources": [{"source_name": manufacturer, "source_role": "MARKET_TRUTH",
                         "source_url": "https://example.co.th/model", "label": None,
                         "artifact": "synthetic.html", "model": model,
                         "identity_level": "VARIANT"}]}


def _artifact(fn, raw, url="https://example.co.th/model"):
    return {"artifact": fn, "url": url, "sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "captured_at": "2026-09-28T00:00:00+00:00", "session_id": "p110-test",
            "provenance_state": "ACQUISITION_VERIFIED", "raw": raw,
            "lines": raw.split("\n")}


# ───────────────────────────── structural gates ─────────────────────────────

def test_target_plan_exists_and_targets_all_488():
    plan = _load("p110_price_target_plan.json")
    assert plan["schema"] == "p110_price_target_plan/1"
    assert plan["accepted_variants_targeted"] == 488
    assert sum(o["accepted_variants"] for o in plan["oems"]) == 488
    assert plan["totals"]["blocked_oems"] and len(plan["totals"]["blocked_oems"]) == 13


def test_identity_ledger_is_frozen():
    base = _load("p108_final_result.json")
    assert base["before_after"]["first_party_confirmed_variants"] == [482, 488]
    res = _load("p110_final_result.json")
    assert res["identity_ledger_unchanged"]["confirmed_variants"] == 488
    assert res["identity_ledger_unchanged"]["changed_by_p110"] is False
    assert res["gates"]["identity_counts_changed"] is False
    assert _load("p109_final_result.json")["accepted_ledger"]["confirmed_variants"] == 488


def test_every_evidence_row_binds_an_accepted_ledger_identity():
    ledger = _ledger()
    assert len(ledger) == 488
    for r in _evidence():
        key = (r["manufacturer"], r["model"], r["variant"])
        assert key in ledger, f"price row outside accepted ledger: {key}"
        assert r["scope"] == "TH"
        assert r["same_record"] is True


def test_price_field_contract_is_complete_on_every_row():
    for r in _evidence():
        missing = [f for f in PRICE_FIELDS if not r.get(f)]
        assert not missing, f"{r['model']}/{r['variant']} missing {missing}"
        assert r["price_type"] in ALLOWED_TYPES, r["price_type"]
        assert r["currency"] == "THB"
        assert 100_000 <= r["price_thb"] <= 60_000_000
        assert r["locator"]["excerpt"], "excerpt required (same record evidence)"


def test_exact_msrp_flag_requires_official_current_exact_variant():
    for r in _evidence():
        expected = (r["price_type"] == "EXACT_VARIANT"
                    and r["trust_tier"] == "official_verified"
                    and r["currentness"] == "CURRENT")
        assert r["is_exact_msrp"] is expected, r["model"]
        assert r["trust_tier"] in {"official_verified", "reference"}
        assert r["currentness"] in {"CURRENT", "HISTORICAL", "UNDETERMINED",
                                    "NOT_A_CURRENTNESS_SOURCE", "UNKNOWN"}


def test_starting_prices_never_count_as_exact_msrp():
    recon = _load("p110_price_reconciliation.json")
    rows = [r for r in _evidence() if r["price_type"] == "MSRP_STARTING"]
    assert all(not r["is_exact_msrp"] for r in rows)
    assert recon["exact_msrp_verified"] == sum(1 for r in _evidence() if r["is_exact_msrp"])


def test_non_msrp_types_never_count_as_exact_msrp():
    recon = _load("p110_price_reconciliation.json")
    bad = [r for r in _evidence()
           if r["price_type"] in {"PROMOTIONAL", "FINANCE_INSTALLMENT", "RANGE"}
           and r["is_exact_msrp"]]
    assert bad == []
    assert recon["exact_non_msrp_only"] == sum(
        1 for r in _evidence() if not r["is_exact_msrp"])


def test_price_evidence_sidecar_documents_derivation():
    prov = _load("p110_price_evidence.json.prov.json")
    ev = open(os.path.join(OUT, "p110_price_evidence.json"), "rb").read()
    assert prov["sha256"] == hashlib.sha256(ev).hexdigest()
    assert prov["provenance_state"] == "DERIVED_PHASE1_AUDIT"
    assert prov["inputs"]


def test_artifact_sha_in_every_price_row_verifies():
    for r in _evidence():
        path = os.path.join(REPO, "tests/fixtures/oem-artifacts", r["artifact"])
        assert os.path.exists(path), r["artifact"]
        assert hashlib.sha256(open(path, "rb").read()).hexdigest() == r["sha256"]
        side = path + ".prov.json"
        assert os.path.exists(side), f"missing sidecar {side}"
        assert json.load(open(side, encoding="utf-8"))["provenance_state"] == \
            r["provenance_state"]


def test_reconciliation_totals_are_internally_consistent():
    recon = _load("p110_price_reconciliation.json")
    assert recon["accepted_variants_targeted"] == 488
    assert recon["price_bound"] + recon["unverified_price"] == 488
    assert recon["price_bound"] == len(_evidence())
    assert sum(recon["price_type_distribution"].values()) == recon["price_bound"]
    per = recon["per_oem"]
    assert sum(v["accepted_variants"] for v in per.values()) == 488
    assert sum(v["price_bound"] for v in per.values()) == recon["price_bound"]
    assert sum(v["exact_msrp_verified"] for v in per.values()) == recon["exact_msrp_verified"]
    assert sum(v["unverified_price"] for v in per.values()) == recon["unverified_price"]
    # blocked OEMs have no accepted variants: every not-priced variant is a gap
    assert recon["blocked_oem_accepted_variants"] == 0
    assert recon["blocked_or_source_gap"] == recon["unverified_price"]


def test_no_price_was_invented_or_promoted_from_third_party():
    recon = _load("p110_price_reconciliation.json")
    assert recon["prices_invented"] == 0
    assert recon["third_party_promoted_to_msrp"] == 0
    for r in _evidence():
        assert r["source_class"] == "MARKET_TRUTH", r["source_class"]
    # the driver never reads the enumerator's stored price fields
    src = open(os.path.join(REPO, "scripts/p110_price_pass.py"), encoding="utf-8").read()
    assert "published_price_thb" not in src
    assert "published_price_role" not in src


def test_unverified_rows_carry_a_reason():
    recon = _load("p110_price_reconciliation.json")
    assert recon["unverified_price"] == len(recon["unverified"])
    for u in recon["unverified"]:
        assert u["status"] == "UNVERIFIED_PRICE"
        assert len(u["reason"]) > 40
        assert u["scope"] == "TH"


def test_capture_log_shape():
    log = _load("p110_price_capture_log.json")
    assert log["schema"] == "p110_price_capture_log/1"
    assert isinstance(log["results"], list)
    assert log["new_captures"] == len(log["results"])
    for r in log["results"]:
        assert os.path.exists(os.path.join(REPO, r["artifact"] + ".prov.json"))


def test_forbidden_paths_untouched():
    res = _load("p110_final_result.json")
    assert res["gates"] == {"staging_written": False, "price_pass_staging": False,
                            "prisma_touched": False, "production_db_unchanged": True,
                            "verifier_touched": False, "identity_counts_changed": False}
    src = open(os.path.join(REPO, "scripts/p110_price_pass.py"), encoding="utf-8").read()
    for needle in ("urllib", "httpx", "requests.get", "playwright", "curl",
                   "wget", "AcquisitionWriter", "socket"):
        assert needle not in src, f"price pass must not call {needle}"
    # subprocess exists only to run the LOCAL pdftotext extractor
    for line in src.split("\n"):
        if "subprocess.run" in line:
            assert "pdftotext" in src, "only pdftotext may be spawned"
    for bad in ("subprocess.Popen", "os.system", "check_output", "check_call"):
        assert bad not in src, f"forbidden process spawn: {bad}"
    # Prisma / verifier may only appear as prose, never as an API call
    assert "Prisma Client" not in src and "prisma." not in src


def test_driver_writes_only_p110_outputs():
    src = open(os.path.join(REPO, "scripts/p110_price_pass.py"), encoding="utf-8").read()
    for name in ("identity_universe_p108.json", "identity_matrix_p109.json",
                 "p108_final_result.json", "p109_final_result.json"):
        assert f'dump("{name}"' not in src, f"must not rewrite {name}"


# ───────────────────── red-first parser defect coverage ─────────────────────

def test_minified_nav_block_is_not_a_price_binding():
    """nav listing every model + promo words + a price in one giant block must
    not become a price binding for any of those models."""
    nav = ("<div class='nav'>EV5 AIR EV5 EARTH ... โปรโมชัน ผ่อน 0% "
           "ราคาพิเศษ 1,299,000 ดาวน์ 99,000</div>")
    body = ("<table><tr><td>EV5 AIR Long Range</td><td>1,399,000</td></tr></table>")
    art = _artifact("synthetic.html", f"<html><body>{nav}{body}</body></html>")
    rec = _rec("EV5", "AIR Long Range")
    rows = P110.harvest_record(rec, {"synthetic.html": art},
                               {"synthetic.html": {"currentness": "CURRENT",
                                                   "reason": "live official page",
                                                   "family": "model_lineup"}})
    assert rows, "the real grade row must still bind"
    assert [r["price_thb"] for r in rows] == [1_399_000], \
        f"nav/promo block leaked into the binding: {rows}"
    assert all(r["price_type"] == "EXACT_VARIANT" for r in rows), rows


def test_promo_wording_in_another_block_does_not_reclassify_an_msrp_row():
    art = _artifact(
        "synthetic.html",
        "<html><body>"
        "<nav><a href='/promo'>โปรโมชั่น</a><a href='/finance'>ผ่อนดาวน์</a></nav>"
        "<table><tr><td>EV5 EARTH Long Range</td><td>ราคา 1,349,000 บาท</td></tr></table>"
        "</body></html>")
    rec = _rec("EV5", "EARTH Long Range")
    rows = P110.harvest_record(rec, {"synthetic.html": art},
                               {"synthetic.html": {"currentness": "CURRENT",
                                                   "reason": "live official page",
                                                   "family": "price_document"}})
    assert rows, "row must bind"
    assert rows[0]["price_type"] == "EXACT_VARIANT", \
        f"promo/finance in a different block contaminated the type: {rows[0]}"


def test_finance_row_is_classified_finance_not_msrp():
    art = _artifact(
        "synthetic.html",
        "<html><body><tr><td>EV5 AIR</td><td>ผ่อนเดือนละ 15,900 บาท "
        "ดาวน์ 199,000</td></tr></body></html>")
    rec = _rec("EV5", "AIR")
    rows = P110.harvest_record(rec, {"synthetic.html": art},
                               {"synthetic.html": {"currentness": "CURRENT",
                                                   "reason": "live official page",
                                                   "family": "official_page"}})
    assert rows, "row must bind"
    assert rows[0]["price_type"] == "FINANCE_INSTALLMENT", rows[0]
    assert not rows[0].get("is_exact_msrp")


def test_starting_price_is_msrp_starting():
    art = _artifact(
        "synthetic.html",
        "<html><body><p>CITY e:HEV</p><p>ราคาเริ่มต้น 879,000 บาท</p></body></html>")
    rec = _rec("City", "e:HEV", manufacturer="Honda")
    rows = P110.harvest_record(rec, {"synthetic.html": art},
                               {"synthetic.html": {"currentness": "CURRENT",
                                                   "reason": "live official page",
                                                   "family": "model_lineup"}})
    assert rows, "row must bind"
    assert rows[0]["price_type"] == "MSRP_STARTING", rows[0]


def test_reference_tier_price_is_never_official_msrp():
    recon = _load("p110_price_reconciliation.json")
    for r in _evidence():
        if r["trust_tier"] != "official_verified":
            assert r["is_exact_msrp"] is False
    assert recon["exact_msrp_verified"] <= recon["price_bound"]


def test_structured_jsonld_price_binds_the_same_record():
    """structured Vehicle data (application/ld+json) is a same-record source."""
    raw = ("<html><head><script type='application/ld+json'>"
           "{\"@context\":\"https://schema.org\",\"@type\":\"Vehicle\","
           "\"name\":\"Toyota GR 86 GR86\","
           "\"offers\":{\"@type\":\"Offer\",\"price\":\"2999000\","
           "\"priceCurrency\":\"THB\"}}</script></head>"
           "<body><p>GR 86</p></body></html>")
    art = _artifact("synthetic.html", raw, url="https://toyota.co.th/model/gr86")
    rec = _rec("GR 86", "GR86", manufacturer="Toyota")
    rows = P110.harvest_record(rec, {"synthetic.html": art},
                               {"synthetic.html": {"currentness": "CURRENT",
                                                   "reason": "live official page",
                                                   "family": "price_document"}})
    assert rows, "structured price node must bind"
    assert rows[0]["price_thb"] == 2_999_000, rows[0]
    assert rows[0]["price_type"] == "EXACT_VARIANT", rows[0]
    assert rows[0]["locator"]["origin"] == "jsonld"


def test_introductory_price_banner_marks_the_grade_price_as_starting():
    raw = ("<html><body>"
           "<h1>Special Introductory Price Starting from 569,000 THB "
           "Offer valid until 30 SEP 26</h1>"
           "<tr><td>CITY e:HEV SV</td><td>689,000 บาท</td></tr>"
           "</body></html>")
    art = _artifact("synthetic.html", raw, url="https://honda.co.th/en/city")
    rec = _rec("City", "e:HEV SV", manufacturer="Honda")
    rows = P110.harvest_record(rec, {"synthetic.html": art},
                               {"synthetic.html": {"currentness": "CURRENT",
                                                   "reason": "live official page",
                                                   "family": "model_lineup"}})
    assert rows, "grade row must bind"
    assert rows[0]["price_type"] == "MSRP_STARTING", \
        f"page-level starting-from wording must qualify the grade price: {rows[0]}"


def test_grade_card_with_a_few_links_still_binds():
    raw = ("<html><body><div><p><a href='/x'>CITY e:HEV SV</a>"
           "<a href='/y'>ดูรายละเอียด</a><a href='/z'>brochure</a></p>"
           "<p><a href='/c'>689,000 บาท</a></p></div></body></html>")
    art = _artifact("synthetic.html", raw, url="https://honda.co.th/en/city")
    rec = _rec("City", "e:HEV SV", manufacturer="Honda")
    rows = P110.harvest_record(rec, {"synthetic.html": art},
                               {"synthetic.html": {"currentness": "CURRENT",
                                                   "reason": "live official page",
                                                   "family": "model_lineup"}})
    assert rows, "a grade card with ordinary links is still one record"
    assert rows[0]["price_thb"] == 689_000, rows[0]


def test_unverified_reasons_carry_an_evidence_category():
    recon = _load("p110_price_reconciliation.json")
    assert recon["unverified_price"] == len(recon["unverified"])
    for u in recon["unverified"]:
        cat = u.get("category", "")
        assert len(cat) > 40, f"{u['model']}/{u['variant']} has no ceiling reason"
        assert any(k in cat for k in ("artifact", "record", "label", "page",
                                      "text layer", "fixture", "price")), cat


def test_longest_grade_label_owns_the_published_price():
    """a shorter grade must never take the price of a longer grade of the same
    model (Premium vs Premium Luxury, Supra vs Supra Track Edition)."""
    raw = ("<html><head><script type='application/ld+json'>"
           "{\"@context\":\"https://schema.org\",\"@graph\":[{\"@type\":\"Vehicle\","
           "\"name\":\"Toyota Yaris ATIV Premium Luxury\","
           "\"offers\":{\"@type\":\"Offer\",\"price\":\"709000\","
           "\"priceCurrency\":\"THB\"}}]}</script></head>"
           "<body><p>ราคา 709,000 บาท</p></body></html>")
    art = _artifact("synthetic.html", raw, url="https://toyota.co.th/pricelist")
    luxury = _rec("Yaris ATIV", "Premium Luxury", manufacturer="Toyota")
    premium = _rec("Yaris ATIV", "Premium", manufacturer="Toyota")
    all_labels = sorted(set(P110.label_variants(luxury) + P110.label_variants(premium)),
                        key=len, reverse=True)
    cur = {"synthetic.html": {"currentness": "CURRENT", "reason": "live official page",
                              "family": "price_document"}}
    best = {}
    lux_rows = P110.harvest_record(luxury, {"synthetic.html": art}, cur,
                                   all_labels=all_labels, best_cache=best)
    pre_rows = P110.harvest_record(premium, {"synthetic.html": art}, cur,
                                   all_labels=all_labels, best_cache=best)
    assert lux_rows, "the longest label must own the price node"
    assert lux_rows[0]["price_thb"] == 709_000, lux_rows[0]
    assert pre_rows == [], f"a shorter grade leaked into the longer grade's price: {pre_rows}"


# ───────────────────────────── determinism ─────────────────────────────────

def test_deterministic_rerun_without_tearing_down_p108_p109():
    watched = [os.path.join(OUT, n) for n in
               ("p108_final_result.json", "p109_final_result.json",
                "identity_universe_p108.json")]
    before = {p: hashlib.sha256(open(p, "rb").read()).hexdigest() for p in watched}
    snap = {}
    for n in ("p110_price_evidence.json", "p110_price_reconciliation.json",
              "p110_price_target_plan.json", "p110_final_result.json"):
        snap[n] = json.loads(open(os.path.join(OUT, n), encoding="utf-8").read())
    r = subprocess.run(["python3", "scripts/p110_price_pass.py"], cwd=REPO,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    after = {p: hashlib.sha256(open(p, "rb").read()).hexdigest() for p in watched}
    assert before == after, "P108/P109 accepted artifacts must not be rewritten"
    for n, old in snap.items():
        new = json.loads(open(os.path.join(OUT, n), encoding="utf-8").read())
        old.pop("generated_at", None)
        new.pop("generated_at", None)
        assert new == old, f"{n} differs between runs"
