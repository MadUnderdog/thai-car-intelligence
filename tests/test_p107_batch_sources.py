"""P107 — batch source discovery + official acquisition tests.

Written before the single P107 rule change: an English published price row
(`Start Price 4,290,000 Baht`) on a dedicated model page must delimit a name
row exactly like a Thai one — the red run fails that case while every other
acceptance gate (same-model binding, exact label, no price stored) already holds.
"""
from __future__ import annotations

import base64
import collections
import hashlib
import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "lib"))
import p107_variant_harvest as p107  # noqa: E402

OUT = os.path.join(REPO, "audit/coverage")
FIXTURES = os.path.join(REPO, "tests/fixtures/oem-artifacts")

TARGETED = ["Mazda", "Nissan", "Porsche", "Subaru", "MINI", "Changan", "Jaguar",
            "Toyota", "MG", "Honda", "Mitsubishi", "Lexus", "GWM", "Deepal",
            "Isuzu", "Suzuki"]
BLOCKED_OEMS = {"Audi", "Avance", "BYD", "Chery", "Chevrolet", "Ford", "Haval",
                "Mercedes-Benz", "NETA", "Peugeot", "Smart", "Tesla", "Volvo"}


def _load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def _evidence():
    return _load("p107_variant_evidence.json")["evidence"]


def _pairs():
    uni = _load("identity_universe_p107.json")["universe"]["records"]
    return {(r["model"], r["variant"]) for r in uni
            if r["variant"] and r.get("first_party")}


# ── 1. published price rows in English ──────────────────────────────────────
def test_english_price_row_delimits_a_name_row():
    body = "(THB) Start Price 4,290,000 Baht — grades of this model"
    assert p107.price_row_boundary("Start Price 4,290,000 Baht", body) is True


def test_price_row_still_needs_a_real_price_to_be_a_boundary():
    assert p107.price_row_boundary("Start Price 2026 Baht", "price page") is False
    assert p107.price_row_boundary("Price list of the range", "price page") is False
    assert p107.price_row_boundary("2026", "price page") is False
    assert p107.price_row_boundary("", "price page") is False


def test_thai_price_rows_still_work():
    assert p107.price_row_boundary("ราคา 1,290,000 บาท", "any") is True
    assert p107.price_row_boundary("4,069,000", "(THB) ราคา เริ่มต้น") is True


def test_price_is_boundary_only_and_never_stored():
    assert _load("catalog_reconciliation_p107.json")["price_pass"] is False
    rows = _evidence()
    assert rows, "no evidence rows to inspect"
    figure = __import__("re").compile(r"\d{1,3}(?:,\d{3})+|^\d{6,}$")
    for row in rows:
        assert not any(k in row for k in ("price", "published_price_thb",
                                          "published_price_role")), row
        for key, value in row["evidence"].items():
            assert "price" not in str(key).lower(), (key, row)
            if key in ("composite_line", "structure", "selector"):
                assert not figure.search(str(value)) or "Start Price" not in str(value), \
                    (key, value)


def test_dedicated_alphard_page_confirms_its_own_grade_rows():
    pairs = _pairs()
    found = [p for p in [("Toyota Alphard", "HEV SMART"),
                         ("Toyota Alphard", "HEV PREMIUM"),
                         ("Toyota Alphard", "HEV PREMIUM LUXURY"),
                         ("Toyota Vellfire", "HEV PREMIUM")] if p in pairs]
    assert len(found) >= 3, found
    arts = {r["artifact"] for r in _evidence()
            if (r["model"], r["variant"]) in set(found)}
    assert any("alphard" in a for a in arts), arts


# ── 2. source inventory / capture log / reacquisition ───────────────────────
def test_inventory_covers_every_targeted_oem_with_a_status_and_blocker():
    inv = _load("p107_source_inventory.json")
    brands = {e["brand"] for e in inv["entries"]}
    assert set(TARGETED) <= brands, set(TARGETED) - brands
    assert inv["attempted"] >= 100, inv["attempted"]
    for e in inv["entries"]:
        assert e.get("status"), e
        if e.get("ok"):
            assert e.get("artifact") and e.get("sha256"), e
        else:
            assert e.get("blocker"), e
            assert e.get("url") is None or e.get("status") != "CAPTURED", e


def test_capture_log_agrees_with_inventory():
    log = _load("p107_capture_log.json")["results"]
    inv = _load("p107_source_inventory.json")["entries"]
    ok_log = [r for r in log if r.get("ok")]
    ok_inv = [e for e in inv if e.get("ok")]
    assert len(ok_log) == len(ok_inv) >= 80, (len(ok_log), len(ok_inv))
    assert {r["url"] for r in ok_log} == {e["url"] for e in ok_inv}
    for r in log:
        if not r.get("ok"):
            assert r.get("error"), r


def test_non_source_captures_were_discarded_and_recorded():
    inv = _load("p107_source_inventory.json")
    discarded = inv.get("discarded_non_source")
    assert discarded, "nothing was discarded — test would be vacuous"
    for fn in discarded:
        assert not os.path.exists(os.path.join(FIXTURES, fn)), fn
        assert not os.path.exists(os.path.join(FIXTURES, fn + ".prov.json")), fn
    statuses = [e.get("status") for e in inv["entries"]]
    assert "DISCARDED_NON_SOURCE" in statuses


def test_every_stored_pdf_artifact_still_decodes():
    for fn in sorted(os.listdir(FIXTURES)):
        if "_p107_" in fn and fn.endswith(".b64"):
            raw = open(os.path.join(FIXTURES, fn), "rb").read()
            data = base64.b64decode(raw, validate=False)
            assert data[:4] == b"%PDF", fn
            assert b"REDACTED" not in raw, fn


def test_sanitizer_corrupted_pdfs_were_reacquired_or_dropped():
    """Cumulative view: every re-acquired text artifact exists with its own
    sidecar, every replaced raw-PDF artifact is gone, and the PDFs that had no
    text layer are recorded as dropped instead of being used as evidence."""
    log = _load("p107_capture_log.json")
    assert "reacquired" in log, "reacquisition record missing"
    txt = sorted(f for f in os.listdir(FIXTURES)
                 if "_p107_" in f and f.endswith(".txt"))
    assert len(txt) >= 5, txt
    for fn in txt:
        prov = json.load(open(os.path.join(FIXTURES, fn + ".prov.json"), encoding="utf-8"))
        assert prov["acquisition_method"] == "http_get_pdf_pdftotext", fn
        assert prov["source_url"].startswith("https://"), fn
        assert prov["provenance_state"] == "ACQUISITION_VERIFIED", fn
    replaced = [r for r in log["results"] if r.get("replaced_artifact")]
    assert replaced, "nothing was reacquired"
    for r in replaced:
        assert not os.path.exists(os.path.join(FIXTURES, r["replaced_artifact"])), r
        assert r.get("pdf_sha256") and r.get("tool") == "pdftotext -layout", r
    dropped = [r for r in log["results"] if not r.get("ok")
               and "NO_TEXT_LAYER" in str(r.get("error", ""))]
    assert dropped, "no no-text-layer source recorded"
    used = {e["artifact"] for e in json.load(open(
        os.path.join(OUT, "p107_source_inventory.json")))["entries"] if e.get("artifact")}
    for r in dropped:
        assert r.get("filename") not in used


def test_blocked_oems_were_never_requested():
    log = _load("p107_capture_log.json")["results"]
    assert log and BLOCKED_OEMS
    assert not ({r["brand"] for r in log} & BLOCKED_OEMS)


# ── 3. evidence quality ─────────────────────────────────────────────────────
def test_every_evidence_row_verifies_and_is_model_bound():
    for row in _evidence():
        path = os.path.join(FIXTURES, row["artifact"])
        prov, reason = p107.verify_artifact(path)
        assert prov and reason is None, (row["artifact"], reason)
        assert prov["sha256"] == row["sha256"], row["artifact"]
        assert prov["source_url"].startswith("https://")
        assert prov["source_url"] == row["source_url"], row
        kind, bound = p107.page_model_set(row["manufacturer"],
                                          row["source_url"], {row["model"]})
        url_bound = p107.norm(row["model"]) in {p107.norm(m) for m in bound}
        line_bound = bool(row["evidence"].get("model_prefix")) and \
            row["evidence"]["composite_line"].casefold().startswith(
                row["evidence"]["model_prefix"].casefold())
        if url_bound or line_bound:
            continue
        # a bare grade row binds by ownership: the exact label belongs to one
        # model only, and this page lists ≥2 of that model's candidate labels
        assert row["extraction_method"] == "official_grade_list_bare_row", (
            row["model"], row["source_url"], kind, row["extraction_method"])
        recs = _load("identity_universe_p107.json")["universe"]["records"]
        owners = collections.defaultdict(set)
        for r in recs:
            if r["variant"]:
                owners[p107.norm(r["variant"])].add(r["model"])
        label = p107.norm(row["variant"])
        assert owners[label] == {row["model"]}, (row["variant"], owners[label])
        own_labels = {p107.norm(r["variant"]) for r in recs
                      if r["model"] == row["model"] and r["variant"]}
        on_page = {p107.norm(l) for l in p107.flattened(row["artifact"])} & own_labels
        assert len(on_page) >= 2, (row["model"], sorted(on_page))


def test_no_candidate_is_promoted_without_being_identity_only_at_baseline():
    base = _load("identity_universe_p106.json")["universe"]["records"]
    was = {(r["model"], r["variant"]) for r in base
           if r["variant"] and not r.get("first_party")}
    got = {(r["model"], r["variant"]) for r in _evidence()}
    assert got and got <= was, sorted(got - was)


def test_counts_agree_across_artifacts():
    res, recon = _load("p107_final_result.json"), _load("catalog_reconciliation_p107.json")
    ev = _evidence()
    assert res["harvested_rows"] == recon["harvested"] == len(ev) > 0
    before, after = res["before_after"]["first_party_confirmed_variants"]
    delta = after - before
    assert 0 < delta <= len(ev)
    assert delta == sum(d["confirmed_variants"] for d in res["per_oem_delta"].values())
    io = res["identity_only"]
    base_io = _load("p106_final_result.json")["identity_only"]
    assert base_io["variants"] - io["variants"] == delta
    assert io["records"] - len({(r["model"], r["variant"]) for r in ev}) <= base_io["records"]
    assert len(_pairs()) >= after


def test_rejected_rows_keep_explicit_reasons():
    recon = _load("catalog_reconciliation_p107.json")
    rows = recon["rejected_rows"]
    assert rows, "no rejection record"
    cross = [r for r in rows if str(r.get("reason", "")).startswith("cross-page")]
    assert cross, "cross-page rejections disappeared"
    assert all(r.get("reason") for r in rows)


def test_promotion_blocker_is_preserved():
    assert p107.grade_label_blocker("ส่งเสริมการขาย 0%", "0")
    assert p107.grade_label_blocker("ราคา 529,000 บาท", "2.0 Prime")


def test_rerun_is_deterministic():
    """Deterministic in the CURRENT tree: two consecutive runs of the driver must
    produce byte-identical evidence.  The committed artifacts are snapshotted and
    restored afterwards, because a wave's snapshot belongs to its own capture set
    and later fixtures must not rewrite an accepted baseline."""
    import glob as _glob
    patterns = ["p107_*", "catalog_reconciliation_p107*", "identity_*_p107*"]
    files = sorted({f for pat in patterns for f in _glob.glob(os.path.join(OUT, pat))})
    assert files, patterns
    saved = dict((f, open(f, "rb").read()) for f in files)

    def run_once():
        proc = subprocess.run([sys.executable, "scripts/p107_variant_harvest.py"],
                              cwd=REPO, capture_output=True, text=True, timeout=900)
        assert proc.returncode == 0, proc.stderr[-2000:]
        rows = json.load(open(os.path.join(OUT, "p107_variant_evidence.json"),
                              encoding="utf-8"))["evidence"]
        canon = json.dumps(rows, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
        return hashlib.sha256(canon.encode()).hexdigest(), len(rows)

    try:
        first = run_once()
        second = run_once()
    finally:
        for f, data in saved.items():
            with open(f, "wb") as fh:
                fh.write(data)
    assert first == second, (first, second)
    assert first[1] > 0


def test_this_suite_contains_no_vacuous_assertions():
    text = open(os.path.abspath(__file__), encoding="utf-8").read()
    needle = "or" + " True"
    assert needle not in text
    assert "assert" + " True" not in text
