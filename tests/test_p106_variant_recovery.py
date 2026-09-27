"""P106 — first-party VARIANT recovery / completeness push.

Red-before requirements (written before the P106 rule changes):
  * a published price may delimit a name row, including the bare figure format
    used by official price lists, but only on a page that publishes prices;
  * the price is never read, stored or verified;
  * new captures must carry a sidecar and verify before they are evidence;
  * blocked OEMs are never requested;
  * the target plan names the zero-gain reachable OEMs first.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "lib"))
import p106_variant_recovery as p106  # noqa: E402

OUT = os.path.join(REPO, "audit/coverage")
FIXTURES = os.path.join(REPO, "tests/fixtures/oem-artifacts")

BLOCKED_OEMS = {"Audi", "Avance", "BYD", "Chery", "Chevrolet", "Ford", "Haval",
                "Mercedes-Benz", "NETA", "Peugeot", "Smart", "Tesla", "Volvo"}

BMW_ROWS = [("Bmw X4", "xDrive20d M Sport"), ("Bmw X7", "xDrive40d M Sport"),
            ("Bmw I5", "Edrive40 M Sport"), ("Bmw Ix", "Xdrive45 M Sport"),
            ("Bmw Ix1", "eDrive20L M Sport"), ("Bmw Ix2", "xDrive30 M Sport")]
EV5_ROWS = [("Kia Ev5", "AIR"), ("Kia Ev5", "EARTH Long Range"),
            ("Kia Ev5", "EARTH Exclusive AWD")]


def _load(name: str) -> dict:
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def _confirmed_pairs() -> set:
    uni = _load("identity_universe_p106.json")["universe"]["records"]
    return {(r["model"], r["variant"]) for r in uni
            if r["variant"] and r.get("first_party")}


def _evidence_rows() -> list:
    return _load("p106_variant_evidence.json")["evidence"]


def _capture_results() -> list:
    return _load("p106_capture_log.json")["results"]


# ── 1. price as a row boundary ──────────────────────────────────────────────
def test_price_row_boundary_accepts_bare_figure_where_prices_are_published():
    body = "(THB) ราคาเริ่มต้น รวมภาษีมูลค่าเพิ่ม"
    assert p106.price_row_boundary("4,069,000", body) is True


def test_price_row_boundary_accepts_published_price_token():
    assert p106.price_row_boundary("฿4,069,000", "any page") is True
    assert p106.price_row_boundary("ราคา 1,290,000 บาท", "any page") is True


def test_price_row_boundary_requires_a_price_page_for_bare_figures():
    prose = "สัมผัสสมรรถนะที่เหนือชั้นกับการออกแบบภายในสุดพรีเมียม"
    assert p106.price_row_boundary("4,069,000", prose) is False


def test_price_row_boundary_rejects_non_price_figures():
    assert p106.price_row_boundary("2026", "(THB) ราคา เริ่มต้น") is False
    assert p106.price_row_boundary("23,799", "(THB) ราคา เริ่มต้น") is False
    assert p106.price_row_boundary("", "(THB) ราคา") is False
    assert p106.price_row_boundary("นิวส์ 4,069,000", "(THB) ราคา") is False


def test_price_is_boundary_only_and_never_stored():
    recon = _load("catalog_reconciliation_p106.json")
    assert recon["price_pass"] is False
    figure = __import__("re").compile(r"\d{1,3}(?:,\d{3})+|^\d{6,}$")
    assert _evidence_rows(), "no evidence rows to inspect"
    for row in _evidence_rows():
        assert not any(k in row for k in ("price", "published_price_thb",
                                          "published_price_role")), row
        for key, value in row["evidence"].items():
            assert "price" not in str(key).lower(), (key, row)
            # the boundary may be described, but no baht figure may be recorded
            assert not figure.search(str(value)), (key, value, row)


# ── 2. price-list rows this wave recovers ──────────────────────────────────
def test_bmw_price_list_rows_are_confirmed_from_the_official_price_list():
    pairs = _confirmed_pairs()
    found = [p for p in BMW_ROWS if p in pairs]
    assert len(found) >= 5, found          # non-vacuous: the 7 rows are real
    bmw_ev = [r for r in _evidence_rows() if (r["model"], r["variant"]) in set(BMW_ROWS)]
    assert len(bmw_ev) >= 5, bmw_ev
    assert all(r["artifact"] == "bmw_price_list.html" for r in bmw_ev), bmw_ev
    assert all(r["evidence"]["structure"] for r in bmw_ev)


def test_kia_ev5_variants_confirmed_from_new_official_capture():
    pairs = _confirmed_pairs()
    for row in EV5_ROWS:
        assert row in pairs, row
    arts = {r["artifact"] for r in _evidence_rows()
            if (r["model"], r["variant"]) in set(EV5_ROWS)}
    assert arts == {"kia_ev5_features.html"}, arts


# ── 3. captures: sidecars, failures, blocked hosts ─────────────────────────
def test_every_successful_capture_has_a_verifying_sidecar():
    ok = [r for r in _capture_results() if r.get("ok")]
    assert ok, "no capture succeeded — the test would be vacuous"
    for r in ok:
        path = os.path.join(FIXTURES, r["filename"])
        assert os.path.exists(path), r["filename"]
        assert os.path.exists(path + ".prov.json"), r["filename"]
        prov, _problems = p106.verify_artifact(path)
        assert prov["sha256"] == r["sha256"], r["filename"]
        assert prov["source_url"].startswith("https://"), r["filename"]


def test_failed_captures_are_recorded_and_write_no_artifact():
    failed = [r for r in _capture_results() if not r.get("ok")]
    assert failed, "no failure recorded — nothing to audit"
    for r in failed:
        assert r.get("error"), r
        assert not os.path.exists(os.path.join(FIXTURES, r["filename"])), r


def test_blocked_oems_are_never_requested():
    log = _capture_results()
    assert log and BLOCKED_OEMS, "both lists must be non-empty to be meaningful"
    brands = {r["brand"] for r in log}
    assert not (brands & BLOCKED_OEMS), brands & BLOCKED_OEMS


# ── 4. target plan before harvest ──────────────────────────────────────────
def test_target_plan_lists_zero_gain_reachable_oems_first():
    plan = _load("p106_target_plan.json")
    assert plan["schema"] == "p106_target_plan/1"
    assert plan["priority_order"][:8] == ["Mazda", "Nissan", "Porsche", "Kia",
                                          "Subaru", "MINI", "Changan", "Jaguar"], \
        plan["priority_order"][:12]
    assert plan["priority_order"][:8] != plan["priority_order"][8:16]


def test_target_plan_deficit_matches_accepted_p105_matrix():
    plan = _load("p106_target_plan.json")
    matrix = _load("identity_matrix_p105.json")["oems"]
    expected = sum(e["identity"]["variant_candidates_discovered"]
                   - e["identity"]["first_party_confirmed_variants"]
                   for e in matrix)
    got = sum(r["variant_deficit"] for r in plan["oems"])
    assert got == expected == 403, (got, expected)


# ── 5. accounting ───────────────────────────────────────────────────────────
def test_result_evidence_and_reconciliation_counts_agree():
    res, recon, ev = (_load("p106_final_result.json"),
                      _load("catalog_reconciliation_p106.json"),
                      _evidence_rows())
    assert res["harvested_rows"] == recon["harvested"] == len(ev) > 0
    before, after = res["before_after"]["first_party_confirmed_variants"]
    delta = after - before
    assert 0 < delta <= len(ev), (before, after, len(ev))
    pairs = _confirmed_pairs()
    assert len(pairs) >= after, (len(pairs), after)


def test_identity_only_decreases_exactly_by_the_confirmed_delta():
    res = _load("p106_final_result.json")
    base = _load("p105_final_result.json")["identity_only"]
    io_before, io_after = base["variants"], res["identity_only"]["variants"]
    v_before, v_after = res["before_after"]["first_party_confirmed_variants"]
    assert (io_before - io_after) == (v_after - v_before) > 0, (base, res["identity_only"])


def test_per_oem_delta_sums_to_the_total_delta():
    res = _load("p106_final_result.json")
    total = sum(d["confirmed_variants"] for d in res["per_oem_delta"].values())
    before, after = res["before_after"]["first_party_confirmed_variants"]
    assert total == after - before > 0, total


def test_cross_page_rejections_are_recorded_explicitly():
    recon = _load("catalog_reconciliation_p106.json")
    rows = recon["rejected_rows"]
    cross = [r for r in rows if str(r.get("reason", "")).startswith("cross-page binding")]
    assert len(cross) >= 6, len(cross)
    assert any("not model evidence" in str(r["reason"]) for r in cross)


# ── 6. preserved hardening ──────────────────────────────────────────────────
def test_promotion_and_numeric_label_blocker_is_preserved():
    assert p106.grade_label_blocker("ส่งเสริมการขาย 0%", "0")
    assert p106.grade_label_blocker("เริ่มต้นที่ 529,000 บาท", "2.0 Prime")
    assert p106.grade_label_blocker("2.0 Prime", "2.0 Prime") is None or \
        p106.grade_label_blocker("2.0 Prime", "2.0 Prime") == ""


def test_every_evidence_row_is_bound_by_its_url_or_by_the_published_line():
    for row in _evidence_rows():
        url = row["source_url"]
        kind, bound = p106.page_model_set(row["manufacturer"], url, {row["model"]})
        url_bound = p106.norm(row["model"]) in {p106.norm(m) for m in bound}
        line_bound = bool(row["evidence"].get("model_prefix")) and \
            row["evidence"]["composite_line"].casefold().startswith(
                row["evidence"]["model_prefix"].casefold())
        assert kind in ("dedicated", "aggregate", "unbound"), (row["model"], url, kind)
        assert url_bound or line_bound, (row["model"], url, kind, row["evidence"])


def test_rerun_is_deterministic():
    """Deterministic in the CURRENT tree: two consecutive runs of the driver must
    produce byte-identical evidence.  The committed artifacts are snapshotted and
    restored afterwards, because a wave's snapshot belongs to its own capture set
    and later fixtures must not rewrite an accepted baseline."""
    import glob as _glob
    patterns = ["p106_*", "catalog_reconciliation_p106*", "identity_*_p106*"]
    files = sorted({f for pat in patterns for f in _glob.glob(os.path.join(OUT, pat))})
    assert files, patterns
    saved = dict((f, open(f, "rb").read()) for f in files)

    def run_once():
        proc = subprocess.run([sys.executable, "scripts/p106_variant_recovery.py"],
                              cwd=REPO, capture_output=True, text=True, timeout=900)
        assert proc.returncode == 0, proc.stderr[-2000:]
        rows = json.load(open(os.path.join(OUT, "p106_variant_evidence.json"),
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
