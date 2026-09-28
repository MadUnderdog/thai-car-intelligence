"""P114 — focused regression: controlled promotion of accepted evidence.

Red-first: written before scripts/p114_promote.py and
scripts/p114_verify_promotion.py existed.

Contracts proven here:
  * preflight gates all PASS and were committed before the write (G8);
  * ledger covers ONLY the 417 ACCEPTED packets — zero quarantined rows;
  * result counts == counts recomputed from the ledger (never report-only);
  * DB deltas == ledger INSERT counts, verifier (independent module) PASS;
  * idempotent rerun: second run is all NO_ACTION, DB counts unchanged,
    committed ledger/result bytes unchanged;
  * price semantics per P111 (MSRP current / LIST_PRICE not-exact /
    MG MSRP never current), spec values identical to P112 rows (zero
    invented values), identity ledger still exactly 488.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "audit/coverage")


def _load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _db_url():
    txt = open(os.path.join(REPO, ".env"), encoding="utf-8").read()
    m = re.search(r'^DATABASE_URL="([^"]+)"', txt, re.M)
    return m.group(1).split("?")[0]


def _sql(query):
    r = subprocess.run(["psql", _db_url(), "-tAc", query],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[:300]
    return [l for l in r.stdout.splitlines() if l]


def _accepted_ids():
    p = _load("p113_evidence_packets.json")
    return {x["packet_id"] for x in p["packets"] if x["status"] == "ACCEPTED"}


def _counts():
    tables = ("Manufacturer", "CarModel", "Variant", "Price", "VariantSpec",
              "Source", "SourceDocument", "DataChangeLog")
    return {t: int(_sql('select count(*) from "%s"' % t)[0]) for t in tables}


# ───────────────────────────── preflight / G8 ─────────────────────────────

def test_preflight_gates_all_pass_and_committed_first():
    pf = _load("p114_promotion_preflight.json")
    gates = _load("p114_promotion_gates.json")
    assert pf["all_gates_pass"] is True
    assert gates["all_gates_pass"] is True
    assert all(g["status"] == "PASS" for g in pf["gates"].values())
    assert pf["gates"]["G6_sample_reopen"]["sample_size"] >= 8
    assert pf["gates"]["G6_sample_reopen"]["pass"] == \
        pf["gates"]["G6_sample_reopen"]["sample_size"]
    assert pf["inputs"]["accepted_packets"] == 417
    assert pf["inputs"]["frozen_identity_ledger"] == 488
    # G8: the gate report predates the producer script in git history
    r = subprocess.run(
        ["git", "log", "--oneline", "--follow", "--",
         "audit/coverage/p114_promotion_gates.md"],
        cwd=REPO, capture_output=True, text=True)
    gate_commit = r.stdout.split()[0]
    r2 = subprocess.run(
        ["git", "log", "--oneline", "--reverse", "--",
         "scripts/p114_promote.py"],
        cwd=REPO, capture_output=True, text=True)
    prod_commit = r2.stdout.split()[0]
    order = subprocess.run(
        ["git", "rev-list", "--count", f"{gate_commit}..{prod_commit}"],
        cwd=REPO, capture_output=True, text=True).stdout.strip()
    assert int(order) >= 1, "gate report must be committed before producer"


def test_preflight_planned_delta_matches_source_artifacts():
    pf = _load("p114_promotion_preflight.json")
    p111 = _load("p111_price_evidence.json")
    p112 = _load("p112_spec_evidence.json")
    p113 = _load("p113_evidence_packets.json")
    acc = [x for x in p113["packets"] if x["status"] == "ACCEPTED"]
    price = {}
    spec = 0
    for pk in acc:
        for o in pk["observations"]["price"]:
            price[o["msrp_status"]] = price.get(o["msrp_status"], 0) + 1
        spec += len(pk["observations"]["spec"])
    planned = pf["planned_delta"]
    assert planned["price_inserts_by_status"] == price
    assert planned["spec_inserts_total"] == spec
    assert sum(planned["price_inserts_by_status"].values()) <= \
        len(p111["rows"])
    assert spec <= len(p112["rows"])
    # upstream artifact bytes recorded at preflight still hold now
    for name, sha in pf["inputs"]["upstream_artifact_shas"].items():
        assert _sha(os.path.join(OUT, name)) == sha, name


# ───────────────────────────── ledger ─────────────────────────────────────

def test_ledger_covers_only_accepted_packets():
    led = _load("p114_promotion_ledger.json")
    accepted = _accepted_ids()
    assert led["entries"], "ledger must have entries"
    for e in led["entries"]:
        assert e["packet_id"] in accepted, e
        assert e["acceptance_decision"] == "ACCEPTED"
        assert e["db_action"] in {"INSERT", "UPDATE", "NO_ACTION"}
        if e["db_action"] == "INSERT":
            assert e["db_row_id"], e
    # quarantined packets appear nowhere
    p113 = _load("p113_evidence_packets.json")
    quarantined = {x["packet_id"] for x in p113["packets"]
                   if x["status"] != "ACCEPTED"}
    assert not quarantined & {e["packet_id"] for e in led["entries"]}
    # identity: exactly one identity entry per accepted packet
    ident = [e for e in led["entries"] if e.get("fact") == "identity"]
    assert {e["packet_id"] for e in ident} == accepted


def test_result_counts_equal_recomputed_ledger_counts():
    res = _load("p114_promotion_result.json")
    led = _load("p114_promotion_ledger.json")
    ins = [e for e in led["entries"] if e["db_action"] == "INSERT"]
    upd = [e for e in led["entries"] if e["db_action"] == "UPDATE"]
    assert res["targeted_packets"] == 417
    assert res["identity_variants_inserted"] == sum(
        1 for e in ins if e.get("fact") == "identity")
    assert res["price_rows_inserted"] == sum(
        1 for e in ins if e.get("fact") == "price")
    assert res["spec_rows_inserted"] == sum(
        1 for e in ins if e.get("fact") == "spec")
    assert res["legacy_current_price_demotions"] == sum(
        1 for e in upd if e.get("fact") == "price_current")
    assert res["packets_promoted"] + res["packets_skipped"] == 417
    assert res["packets_failed"] == 0
    assert res["quarantined_promoted"] == 0
    assert res["values_invented"] == 0
    assert res["identity_ledger_unchanged"] == {
        "confirmed_variants": 488, "changed_by_p114": False}


def test_price_semantics_in_ledger_follow_p111():
    led = _load("p114_promotion_ledger.json")
    price_entries = [e for e in led["entries"] if e.get("fact") == "price"]
    for e in price_entries:
        st = e["msrp_status"]
        if st == "EXACT_CURRENT_MSRP_VERIFIED":
            assert e["db_value"]["price_type"] == "MSRP"
            assert e["db_value"]["is_current"] is True
        elif st == "MSRP_STARTING_NOT_EXACT":
            assert e["db_value"]["price_type"] == "LIST_PRICE"
            assert e["db_value"]["is_current"] is False
        elif st == "EXACT_BINDING_NOT_VERIFIED_CURRENT":
            assert e["db_value"]["is_current"] is False, "MG never current"
        else:
            raise AssertionError(st)


def test_spec_values_are_verbatim_p112_rows():
    led = _load("p114_promotion_ledger.json")
    p112 = _load("p112_spec_evidence.json")
    by_ev = {r["evidence_id"]: r for r in p112["rows"]}
    checked = 0
    for e in led["entries"]:
        if e.get("fact") != "spec":
            continue
        src = by_ev[e["evidence_id"]]
        assert e["db_value"]["value_text"] == src["value_text"], e
        assert (e["db_value"].get("unit") or None) == (src.get("unit") or None)
        checked += 1
    assert checked == 1388


# ───────────────────────────── DB / verifier ──────────────────────────────

def test_verifier_passes_and_is_independent_of_producer():
    prod = open(os.path.join(REPO, "scripts/p114_promote.py"),
                encoding="utf-8").read()
    ver = open(os.path.join(REPO, "scripts/p114_verify_promotion.py"),
               encoding="utf-8").read()
    assert "p114_verify_promotion" not in prod.replace(
        '"scripts/p114_verify_promotion.py"', "")
    assert "p114_promote" not in ver
    assert "class AcceptanceRunner" not in prod
    r = subprocess.run(
        ["python3", "scripts/p114_verify_promotion.py"],
        cwd=REPO, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, (r.stdout[-1500:], r.stderr[-1500:])
    assert "VERIFY_PASS" in r.stdout
    v = _load("p114_promotion_verification.json")
    assert v["status"] == "PASS"
    assert v["quarantined_rows_promoted"] == 0
    assert v["invented_values"] == 0


def test_promotion_rerun_is_idempotent_and_noop():
    committed_ledger = _sha(os.path.join(OUT, "p114_promotion_ledger.json"))
    committed_result = _sha(os.path.join(OUT, "p114_promotion_result.json"))
    before = _counts()
    r = subprocess.run(
        ["python3", "scripts/p114_promote.py",
         "--ledger", "/tmp/p114_ledger_rerun.json",
         "--result", "/tmp/p114_result_rerun.json"],
        cwd=REPO, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, (r.stdout[-2000:], r.stderr[-2000:])
    after = _counts()
    assert before == after, "second run must change no DB counts"
    rerun = json.load(open("/tmp/p114_result_rerun.json", encoding="utf-8"))
    assert rerun["identity_variants_inserted"] == 0
    assert rerun["price_rows_inserted"] == 0
    assert rerun["spec_rows_inserted"] == 0
    assert rerun["legacy_current_price_demotions"] == 0
    assert rerun["manufacturers_inserted"] == 0
    assert rerun["models_inserted"] == 0
    assert rerun["source_documents_inserted"] == 0
    assert _sha(os.path.join(OUT, "p114_promotion_ledger.json")) == \
        committed_ledger
    assert _sha(os.path.join(OUT, "p114_promotion_result.json")) == \
        committed_result


def test_db_rows_match_ledger_and_semantics():
    led = _load("p114_promotion_ledger.json")
    pf = _load("p114_promotion_preflight.json")
    base = pf["db_baseline"]
    now = _counts()
    ins = [e for e in led["entries"] if e["db_action"] == "INSERT"]
    # identity INSERTs: models+variants+mans counted via dedicated fields
    assert now["Manufacturer"] - base["Manufacturer"] == \
        res_field("manufacturers_inserted")
    assert now["CarModel"] - base["CarModel"] == res_field("models_inserted")
    assert now["Variant"] - base["Variant"] == \
        res_field("identity_variants_inserted")
    assert now["Price"] - base["Price"] == \
        res_field("price_rows_inserted")
    assert now["VariantSpec"] - base["VariantSpec"] == \
        res_field("spec_rows_inserted")
    # source docs: inserted docs must all carry our artifact sha256
    cited_shas = set()
    p113 = _load("p113_evidence_packets.json")
    for pk in p113["packets"]:
        if pk["status"] != "ACCEPTED":
            continue
        for g in ("identity", "price", "spec"):
            for o in pk["observations"][g]:
                cited_shas.add(o["sha256"])
    in_list = ",".join("'%s'" % s for s in cited_shas)
    rows = _sql('select "contentHash" from "SourceDocument" where '
                '"contentHash" in (%s)' % in_list)
    assert set(rows) == cited_shas, "every cited artifact must be registered"
    # price semantics straight from the DB
    rows = _sql("select price_type::text, \"isCurrent\", count(*) from "
                "\"Price\" where \"sourceDocumentId\" in "
                "(select id from \"SourceDocument\" where \"contentHash\" "
                "in (%s)) group by 1,2" % in_list)
    got = {}
    for l in rows:
        t, cur, n = l.split("|")
        got[(t, cur)] = int(n)
    led_price = {}
    for e in [x for x in led["entries"] if x.get("fact") == "price"]:
        k = (e["db_value"]["price_type"],
             str(e["db_value"]["is_current"]).lower())
        led_price[k] = led_price.get(k, 0) + 1
    assert got == led_price, (got, led_price)
    # no variant WE touched keeps two current prices (pre-existing
    # duplicates on untouched legacy variants are out of scope)
    dup = _sql(
        "select count(*) from (select \"variantId\" from \"Price\" "
        "where \"isCurrent\" = true and \"variantId\" in "
        "(select distinct \"variantId\" from \"Price\" where "
        "\"sourceDocumentId\" in (select id from \"SourceDocument\" "
        "where \"contentHash\" in (%s))) "
        "group by 1 having count(*) > 1) x" % in_list)[0]
    assert int(dup) == 0, "touched variants must have at most one current price"


def res_field(name):
    return _load("p114_promotion_result.json")[name]


def test_upstream_evidence_and_identity_ledger_untouched():
    pf = _load("p114_promotion_preflight.json")
    for name, sha in pf["inputs"]["upstream_artifact_shas"].items():
        assert _sha(os.path.join(OUT, name)) == sha, name
    u = _load("identity_universe_p108.json")
    acc = [r for r in u["universe"]["records"]
           if r["status"] == "CONFIRMED_VARIANT"]
    assert len(acc) == 488


def test_no_quarantined_packet_is_referenced_anywhere_in_db_logs():
    accepted = _accepted_ids()
    rows = _sql("select reason from \"DataChangeLog\" where reason like "
                "'P114%'")
    assert rows, "promotion must write DataChangeLog entries"
    seen = set()
    for r in rows:
        m = re.search(r"PKT-\d{4}", r)
        assert m, r
        seen.add(m.group(0))
    assert seen <= accepted


def test_g6_sample_results_are_committed_and_passing():
    pf = _load("p114_promotion_preflight.json")
    g6 = pf["gates"]["G6_sample_reopen"]
    assert g6["status"] == "PASS"
    oems = {r["oem"] for r in g6["rows"]}
    fields = {r["field"] for r in g6["rows"]}
    assert len(oems) >= 6, oems
    assert fields == {"identity", "price", "spec"}
