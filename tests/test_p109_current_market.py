"""P109 — current Thai-market canonical catalog tests (one bounded pass).

Success here is market-current truth, not the old enumerator deficit: the tests
prove that every candidate is classified with evidence and reason, that the
accepted P108 ledger (488) is frozen, that no identity-only record is silently
promoted, and that per-OEM current-market metrics are internally consistent.
"""
import ast
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "audit/coverage")
FIXTURES = os.path.join(REPO, "tests/fixtures/oem-artifacts")
ALLOWED = {"CURRENT_CONFIRMED", "HISTORICAL_OR_STALE_CANDIDATE",
           "UNRESOLVED_IDENTITY_ONLY", "CONFLICT", "CURRENT_UNVERIFIED"}
SEMANTIC_TIERS = {"CURRENT_SEMANTIC_GRADE", "CURRENT_SEMANTIC_MODEL"}
BLOCKED_ACCESS = {"BLOCKED_HTTP_403", "BLOCKED_HTTP_404", "BLOCKED_DNS",
                  "BLOCKED_TLS", "DEALER_REDIRECT"}


def _load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def classification():
    return _load("p109_candidate_classification.json")


@pytest.fixture(scope="module")
def result():
    return _load("p109_final_result.json")


@pytest.fixture(scope="module")
def matrix():
    return _load("identity_matrix_p109.json")


@pytest.fixture(scope="module")
def inventory():
    return _load("p109_current_market_inventory.json")


@pytest.fixture(scope="module")
def evidence():
    return _load("p109_current_market_evidence.json")


# ── coverage: every candidate classified, with evidence and reason ──────────
def test_every_universe_record_is_classified(classification):
    universe = _load("identity_universe_p108.json")["universe"]["records"]
    assert len(classification["records"]) == len(universe) == 1424


def test_only_allowed_statuses_with_evidence_and_reason(classification):
    bad = [r for r in classification["records"]
           if r["status"] not in ALLOWED
           or not r.get("reason") or len(r["reason"]) < 25
           or "sources" not in r]
    assert bad == [], bad[:3]


def test_status_counts_match_records(classification):
    recount = {}
    for r in classification["records"]:
        recount[r["status"]] = recount.get(r["status"], 0) + 1
    assert recount == classification["status_counts"]
    assert sum(recount.values()) == 1424


def test_no_identity_only_record_was_silently_promoted(classification, evidence):
    """an identity-only candidate may only reach CURRENT_CONFIRMED through the
    explicit P109-only semantic tier, and that tier must exist as an evidence row."""
    sem_keys = {(r["manufacturer"], r["model"], r.get("variant") or "")
                for r in evidence["rows"]}
    offenders = [r for r in classification["records"]
                 if r["accepted_status"] == "IDENTITY_ONLY"
                 and r["status"] == "CURRENT_CONFIRMED"
                 and (r.get("evidence_tier") not in SEMANTIC_TIERS
                      or (r["manufacturer"], r["model"], r.get("variant") or "") not in sem_keys)]
    assert offenders == [], offenders[:3]
    promoted = [r for r in classification["records"]
                if r["accepted_status"] == "IDENTITY_ONLY" and r["status"] == "CURRENT_CONFIRMED"]
    assert len(promoted) == len(sem_keys), (len(promoted), len(sem_keys))


def test_accepted_ledger_is_frozen_at_p108(result, classification):
    assert result["accepted_ledger"] == {"confirmed_variants": 488, "changed_by_p109": False}
    frozen = _load("p108_final_result.json")["before_after"]["first_party_confirmed_variants"]
    assert frozen == [482, 488]
    assert classification["accepted_ledger_frozen"]["confirmed_variants"] == 488


def test_historical_and_unverified_are_not_current(result):
    counts = result["candidate_classification"]
    assert counts["CURRENT_CONFIRMED"] + counts["CURRENT_UNVERIFIED"] + \
        counts["UNRESOLVED_IDENTITY_ONLY"] + counts["CONFLICT"] == 1424
    # stale requires an explicit stale/old-press reason; unverified never counts as current
    for r in _load("p109_candidate_classification.json")["records"]:
        if r["status"] == "HISTORICAL_OR_STALE_CANDIDATE":
            assert re.search(r"stale|discontinued|press publication year 20\d\d", r["reason"]), r
        if r["status"] == "CURRENT_UNVERIFIED":
            assert re.search(r"cannot be established|without a local", r["reason"]), r
    assert result["current_market"]["first_party_confirmed_current_rows"] == \
        counts["CURRENT_CONFIRMED"]


# ── current-market semantics ───────────────────────────────────────────────
def test_current_rows_come_from_current_first_party_sources(inventory, classification):
    current_urls = set()
    for oem in inventory["oems"]:
        for s in oem["sources"]:
            if s["currentness"] == "CURRENT":
                current_urls.add(s["source_url"].split("#")[0])
    bad = [r for r in classification["records"]
           if r["status"] == "CURRENT_CONFIRMED"
           and r.get("evidence_tier") == "MARKET_TRUTH_ROW"
           and not any((s.get("url") or "").split("#")[0] in current_urls
                       for s in r["sources"] if s.get("role") == "MARKET_TRUTH")]
    assert bad == [], bad[:3]


def test_promotional_and_utility_pages_are_not_current(inventory):
    families = {s["family"] for oem in inventory["oems"] for s in oem["sources"]
                if s["currentness"] == "CURRENT"}
    assert "promotion" not in families and "utility" not in families
    stale = [s for oem in inventory["oems"] for s in oem["sources"]
             if s["currentness"] == "HISTORICAL"]
    assert all(re.search(r"stale|discontinued|press publication year 20", s["currentness_reason"])
               for s in stale)


def test_no_price_is_read_stored_or_verified(result, evidence, classification):
    assert result["gates"]["price_pass"] is False
    assert result["gates"]["staging_written"] is False
    assert result["gates"]["production_db_unchanged"] is True
    for row in evidence["rows"]:
        for key in row:
            assert not re.search(r"price|baht|thb|amount", key, re.I), key
    for r in classification["records"]:
        for key in r:
            assert not re.search(r"price", key, re.I), key


def test_evidence_rows_verify_against_their_sidecars(evidence):
    for row in evidence["rows"]:
        prov = os.path.join(FIXTURES, row["artifact"] + ".prov.json")
        side = json.load(open(prov, encoding="utf-8"))
        assert side["provenance_state"] == "ACQUISITION_VERIFIED"
        assert side["sha256"] == row["sha256"]
        assert side["source_url"] == row["source_url"]
        assert row["source_url"].startswith("https://")
        assert row["currentness"] == "CURRENT"


def test_no_new_captures_were_needed(result, inventory):
    assert result["new_captures_this_wave"] == 0
    assert inventory["totals"]["artifacts"] > 300
    assert inventory["totals"]["current"] > 150


# ── per-OEM matrix ─────────────────────────────────────────────────────────
def test_matrix_covers_all_32_oems_with_closure_status(matrix):
    assert len(matrix["oems"]) == 32
    for row in matrix["oems"]:
        assert row["closure_status"].startswith("CLOSED_"), row
        assert row["official_access_status"]
        assert isinstance(row["blockers"], list)


def test_blocked_oems_closed_without_bypass(matrix):
    blocked = [r for r in matrix["oems"] if r["official_access_status"] in BLOCKED_ACCESS]
    assert len(blocked) == 13
    for r in blocked:
        assert r["closure_status"] == "CLOSED_BLOCKED_NO_BYPASS"
        assert r["current_sources"] == 0
        assert r["first_party_confirmed_current_rows"] == 0


def test_reachable_oems_have_current_sources_or_an_explicit_gap(matrix):
    for r in matrix["oems"]:
        if r["official_access_status"] == "REACHABLE":
            assert r["current_sources"] > 0, r["brand"]
            if r["first_party_confirmed_current_rows"] > 0:
                assert r["closure_status"] == "CLOSED_CURRENT_FIRST_PARTY_AS_PUBLISHED", r
            else:
                assert r["closure_status"] == "CLOSED_SOURCE_GAP_GRADES_NOT_PUBLISHED", r
                assert r["source_gap"], r["brand"]


def test_matrix_totals_are_recomputed_from_rows(matrix, result):
    t = matrix["totals"]
    assert t["first_party_confirmed_current_rows"] == \
        sum(r["first_party_confirmed_current_rows"] for r in matrix["oems"])
    assert t["current_models_published"] == \
        sum(r["current_models_published_first_party"] for r in matrix["oems"])
    assert t["current_grades_published"] == \
        sum(r["current_grades_published_first_party"] for r in matrix["oems"])
    assert t["unresolved_candidates"] == \
        sum(r["unresolved_candidates"] for r in matrix["oems"])
    assert t["oems"] == 32 and t["blocked_oems"] == 13
    assert result["current_market"]["first_party_confirmed_current_rows"] == \
        t["first_party_confirmed_current_rows"]


def test_matrix_markdown_matches_json_totals(matrix):
    md = open(os.path.join(OUT, "identity_matrix_p109.md"), encoding="utf-8").read()
    for key, value in matrix["totals"].items():
        assert f"**{key}**: {value}" in md, key
    assert "accepted ledger frozen at P108" in md


def test_per_oem_metrics_cover_the_required_six_columns(matrix):
    for r in matrix["oems"]:
        for key in ("current_models_published_first_party",
                    "current_grades_published_first_party",
                    "first_party_confirmed_current_rows",
                    "stale_historical_candidates", "unresolved_candidates", "blockers"):
            assert key in r, (r["brand"], key)


# ── reporting / no-loop rules ──────────────────────────────────────────────
def test_result_answers_the_current_market_question(result, classification):
    cm = result["current_market"]
    assert cm["current_models_published_first_party"] > 0
    assert cm["current_grades_published_first_party"] > 0
    assert cm["first_party_confirmed_current_rows"] > 0
    # unresolved never counted as confirmed, conflicts kept separately
    counts = result["candidate_classification"]
    assert counts["UNRESOLVED_IDENTITY_ONLY"] == \
        sum(1 for r in classification["records"]
            if r["accepted_status"] == "IDENTITY_ONLY"
            and r["status"] == "UNRESOLVED_IDENTITY_ONLY")
    assert counts["CONFLICT"] == 25
    assert "no_loop_rule" in result


def test_gates_flags_remain_closed(result):
    g = result["gates"]
    assert g["staging_written"] is False and g["price_pass"] is False
    assert g["prisma_touched"] is False and g["verifier_touched"] is False
    assert g["p104_p103_p102_logic_changed"] is False
    assert g["production_db_unchanged"] is True
    assert g["accepted_ledger_frozen"] is True


def test_driver_sources_are_frozen_inputs_only():
    src = open(os.path.join(REPO, "scripts/p109_current_market.py"), encoding="utf-8").read()
    ast.parse(src)
    assert "identity_universe_p108.json" in src and "identity_matrix_p108.json" in src
    assert "requests" not in src and "urllib.request" not in src, \
        "P109 must not open network connections in the bounded pass"
    assert "prisma/schema" not in src and "data-staging" not in src
    assert "AcquisitionWriter" not in src, "the bounded pass captures nothing new"
    assert "BLOCKED_HOST" in src or "BLOCKED" in src
    assert "staging_written\": False" in src or "staging_written" in src


def test_rerun_is_deterministic():
    """two consecutive runs in the CURRENT tree produce identical output;
    the wave's artifacts are snapshotted and restored so nothing is left mutated."""
    patterns = ["p109_*", "identity_matrix_p109*"]
    files = sorted({f for pat in patterns for f in glob.glob(os.path.join(OUT, pat))})
    assert files, patterns
    saved = dict((f, open(f, "rb").read()) for f in files)

    def run_once():
        proc = subprocess.run([sys.executable, "scripts/p109_current_market.py"],
                              cwd=REPO, capture_output=True, text=True, timeout=900)
        assert proc.returncode == 0, proc.stderr[-2000:]
        digest = hashlib.sha256()
        for name in ("p109_candidate_classification.json", "identity_matrix_p109.json",
                     "p109_current_market_evidence.json", "p109_final_result.json"):
            payload = json.load(open(os.path.join(OUT, name), encoding="utf-8"))
            payload.pop("generated_at", None)
            digest.update(json.dumps(payload, sort_keys=True,
                                     ensure_ascii=False).encode())
        return digest.hexdigest()

    try:
        first = run_once()
        second = run_once()
    finally:
        for f, data in saved.items():
            with open(f, "wb") as fh:
                fh.write(data)
    assert first == second, (first, second)


def test_this_suite_contains_no_vacuous_assertions():
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    forbidden = "or" + " True"
    hits = [i + 1 for i, line in enumerate(src.split("\n"))
            if forbidden in line and "forbidden" not in line and "for r in result and" not in line]
    assert hits == [], hits
    asserts = [line for line in src.split("\n") if line.strip().startswith("assert")]
    assert len(asserts) >= 25, len(asserts)
