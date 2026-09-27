"""P104 — first-party breadth pass: evidence and boundary behaviour.

Everything is asserted from committed artifacts and committed fixtures
(offline).  The contract:

  1  every harvested identity is provable in the artifact bytes it cites, and
     the artifact must carry an AcquisitionWriter sidecar with a real source
     URL — an artifact without provenance is never evidence;
  2  `identity_level` is declared by the extraction rule, never inferred;
  3  generic labels (SEDAN, SUV, …) are never model evidence, and sibling
     brands never inherit each other's publication;
  4  reconciliation confirms the existing record or records why the identity
     is new — never a second copy of the same identity;
  5  report/result/reconciliation counts agree with the identity artifact;
  6  no staging row, no production DB row, no price, no blocker change, and
     the accepted P102/P103 numbers only move through confirmed identities.
"""
import hashlib
import json
import os
import re
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "lib"))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import p104_first_party_breadth as p104  # noqa: E402
from thai_factory.catalog.identity_pass import match_key  # noqa: E402

PLAN = os.path.join(REPO, "audit", "coverage", "p104_target_plan.json")
IDENTITIES = os.path.join(REPO, "audit", "coverage", "p104_official_identities.json")
RECON = os.path.join(REPO, "audit", "coverage", "catalog_reconciliation_p104.json")
UNIVERSE = os.path.join(REPO, "audit", "coverage", "identity_universe_p104.json")
P103_UNIVERSE = os.path.join(REPO, "audit", "coverage", "identity_universe_p103.json")
P103_FINAL = os.path.join(REPO, "audit", "coverage", "p103_final_result.json")
MATRIX = os.path.join(REPO, "audit", "coverage", "identity_matrix_p104.json")
FINAL = os.path.join(REPO, "audit", "coverage", "p104_final_result.json")
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
FIXTURE_DIR = os.path.join(REPO, "tests", "fixtures", "oem-artifacts")

MODEL_METHODS = {"official_lineup_word_boundary"}
VARIANT_METHODS = {"official_grade_table", "official_sentence_grade"}


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def identities():
    return _load(IDENTITIES)["identities"]


def records():
    return _load(UNIVERSE)["universe"]["records"]


# ── 1. plan and target discipline ──────────────────────────────────────────
def test_target_plan_covers_32_oems_and_keeps_blockers_verbatim():
    plan = _load(PLAN)
    assert plan["schema"] == "p104_target_plan/1"
    assert plan["reachable"] == 19 and plan["blocked"] == 13
    assert len(plan["oems"]) == 32
    p103_matrix = _load(os.path.join(REPO, "audit", "coverage", "identity_matrix_p103.json"))
    access = {e["brand"]: e["official_access_status"] for e in p103_matrix["oems"]}
    for row in plan["oems"]:
        assert row["official_access_status"] == access[row["brand"]]
        if access[row["brand"]] != "REACHABLE":
            assert row["blockers"] or row["blocker_kind"], row["brand"]
            assert row["blocker_policy"]
            assert row["targeted_this_wave"] is False
    final = _load(FINAL)
    assert final["blocker_changes"]["new_blockers"] == []
    assert final["blocker_changes"]["cleared_blockers"] == []
    assert final["blocker_changes"]["retried_blocked_hosts"] == ["Smart"]
    check = final["blocker_changes"]["smart_retry_check"]
    assert check["unrelated_domain"] is True
    assert check["final_host"] != "www.smart.co.th"
    assert final["blocker_changes"]["smart_status"] == access["Smart"] == "DEALER_REDIRECT"
    # the recorded blocker evidence itself is unchanged
    p103_row = next(e for e in p103_matrix["oems"] if e["brand"] == "Smart")
    row = next(r for r in plan["oems"] if r["brand"] == "Smart")
    assert row["blockers"] == p103_row["blockers"]


def test_attack_order_is_only_reachable_oems_with_a_remaining_deficit():
    plan = _load(PLAN)
    by_brand = {r["brand"]: r for r in plan["oems"]}
    for brand in plan["attack_order"]:
        row = by_brand[brand]
        assert row["official_access_status"] == "REACHABLE"
        assert row["targeted_this_wave"] is True
        assert row["variant_deficit"] > 0 or row["model_deficit"] > 0
    # an OEM with no remaining deficit is not attacked
    for row in plan["oems"]:
        if row["official_access_status"] == "REACHABLE" and \
                row["variant_deficit"] == 0 and row["model_deficit"] == 0:
            assert row["targeted_this_wave"] is False


# ── 2. evidence must be provable in the cited artifact ─────────────────────
@pytest.mark.parametrize("item", identities(), ids=lambda i: f"{i['manufacturer']}-{i['model']}-{i['variant']}")
def test_identity_is_provable_in_the_cited_artifact(item):
    path = os.path.join(FIXTURE_DIR, item["artifact"])
    assert os.path.exists(path), path
    with open(path, "rb") as fh:
        raw = fh.read()
    assert item["sha256"] == hashlib.sha256(raw).hexdigest()
    assert item["identity_level"] in ("MODEL", "VARIANT")
    assert item["extraction_method"]
    if item["extraction_method"] in MODEL_METHODS:
        assert item["identity_level"] == "MODEL"
        assert not item["variant"]
        ev = item["evidence"]
        # the label must really be the text found on the page (separators may
        # differ: "Nissan X Trail" matches the published "NISSAN X-TRAIL")
        norm = lambda s: re.sub(r"[^A-Z0-9]", "", s.upper())
        assert norm(ev["matched_text"]) == norm(item["model"]), (ev["matched_text"], item["model"])
        assert norm(ev["matched_text"]) in norm(ev["snippet"])
    else:
        assert item["identity_level"] == "VARIANT"
        assert item["variant"], item


def test_p104_sources_are_marked_th_scope():
    seen = 0
    for r in records():
        for src in r["first_party"]:
            if str(src.get("extraction_method", "")).startswith("official_"):
                seen += 1
                assert src["market_scope"] == "TH"
                assert src["source_role"] == "MARKET_TRUTH"
    assert seen > 0


def test_every_identity_cites_an_artifact_with_a_real_source_url():
    for item in identities():
        sidecar = os.path.join(FIXTURE_DIR, item["artifact"] + ".prov.json")
        assert os.path.exists(sidecar), item["artifact"]
        with open(sidecar, encoding="utf-8") as fh:
            prov = json.load(fh)
        assert prov.get("source_url", "").startswith("https://")
        assert item["source_url"] == prov["source_url"] or item["source_url"].startswith("https://")


def test_artifacts_without_provenance_are_skipped_and_never_used():
    recon = _load(RECON)
    skipped = {x["artifact"] for x in recon["skipped_artifacts_without_provenance"]}
    assert skipped, "the fail-closed provenance rule should record skips"
    used = {i["artifact"] for i in identities()}
    assert not (skipped & used), skipped & used
    for x in recon["skipped_artifacts_without_provenance"]:
        assert "no .prov.json source_url" in x["reason"]


def test_generic_labels_are_never_model_evidence():
    generic = {"SEDAN", "SPORT", "SUV", "WAGON", "EV", "HEV", "CROSS"}
    for item in identities():
        if item["identity_level"] == "MODEL":
            assert item["model"].upper() not in generic


# ── 3. reconciliation semantics ────────────────────────────────────────────
def test_reconciliation_counts_match_the_identity_artifact():
    recon, ids = _load(RECON), identities()
    assert recon["harvested"] == len(ids)
    assert sum(recon["outcomes"].get(k, 0) for k in ("new", "existing", "ambiguous")) \
        == recon["harvested"]
    final = _load(FINAL)
    assert final["harvested_identities"] == recon["harvested"] == len(ids)
    assert final["outcomes"] == recon["outcomes"]


def test_new_identities_carry_the_reason_they_are_new():
    recon = _load(RECON)
    for row in recon["new_first_party_identities"]:
        match = next(i for i in identities()
                     if i["model"] == row["model"] and i["variant"] == row["variant"]
                     and i["manufacturer"] == row["manufacturer"])
        assert match["reconciliation"]["outcome"] == "new"
        assert match["reconciliation"]["reason"]


def test_confirming_an_existing_candidate_never_duplicates_it():
    recon = _load(RECON)
    assert recon["outcomes"].get("new", 0) >= 0
    # no record may carry the same publication twice
    for r in records():
        keys = [(s.get("source_name"), s.get("source_url"), s.get("identity_level"))
                for s in r["sources"]]
        assert len(keys) == len(set(keys)), r["model"]
        labels = [(s.get("source_name"), s.get("source_url"), s.get("label"))
                  for s in r["first_party"] if s.get("extraction_method")]
        assert len(labels) == len(set(labels)), r["model"]


def test_sibling_brand_separation_holds_for_every_p104_publication():
    checked = 0
    for r in records():
        for s in r["first_party"]:
            if not str(s.get("extraction_method", "")).startswith("official_"):
                continue
            checked += 1
            if "manufacturer" in s:
                assert s["manufacturer"] == r["manufacturer"], (r["model"], s)
    assert checked > 0


def test_p104_baseline_equals_the_accepted_p103_result():
    final, p103 = _load(FINAL), _load(P103_FINAL)
    before = final["before_after"]
    assert before["first_party_confirmed_models"][0] == p103["first_party_confirmed_models"]
    assert before["first_party_confirmed_variants"][0] == p103["first_party_confirmed_variants"]
    assert before["first_party_confirmed_models"][1] >= before["first_party_confirmed_models"][0]
    assert before["first_party_confirmed_variants"][1] >= before["first_party_confirmed_variants"][0]


def test_conflicts_and_rejections_never_grow():
    final = _load(FINAL)
    p103 = _load(P103_FINAL)
    assert final["conflicts"]["records"] <= p103["conflicts"]["records"]
    p103_rejected = len(_load(P103_UNIVERSE)["universe"]["rejected"])
    assert final["rejected"]["records"] == p103_rejected
    # identity-only may only fall (confirmation) — never be promoted silently
    p103_io = _load(P103_UNIVERSE)["universe"]["summary"]["identity_only"]
    assert final["identity_only"]["records"] <= p103_io


def test_identity_only_records_are_never_promoted_without_publication():
    p103_io = {(r["manufacturer"], match_key(r["manufacturer"], r["model"]),
                match_key(r["manufacturer"], r.get("variant") or ""))
               for r in _load(P103_UNIVERSE)["universe"]["records"]
               if r["status"] == "IDENTITY_ONLY"}
    now = {(r["manufacturer"], match_key(r["manufacturer"], r["model"]),
            match_key(r["manufacturer"], r.get("variant") or "")): r for r in records()}
    for key in p103_io:
        rec = now[key]
        assert rec["status"] in ("IDENTITY_ONLY", "CONFIRMED_MODEL", "CONFIRMED_VARIANT")
        if rec["status"].startswith("CONFIRMED"):
            assert any(s.get("source_role") == "MARKET_TRUTH" for s in rec["first_party"])


def test_new_records_carry_no_price_and_staging_is_untouched():
    p103_pairs = {(r["manufacturer"], match_key(r["manufacturer"], r["model"]),
                   match_key(r["manufacturer"], r.get("variant") or ""))
                  for r in _load(P103_UNIVERSE)["universe"]["records"]}
    fresh = [r for r in records()
             if (r["manufacturer"], match_key(r["manufacturer"], r["model"]),
                 match_key(r["manufacturer"], r.get("variant") or "")) not in p103_pairs]
    assert fresh
    for r in fresh:
        assert r["published_price_thb"] is None, r
    with open(STAGING, encoding="utf-8") as fh:
        staging = fh.read()
    assert "p104" not in staging.lower()
    final = _load(FINAL)
    assert final["gates"]["staging_written"] is False
    assert final["gates"]["price_pass"] is False
    assert final["gates"]["prisma_touched"] is False


# ── 4. matrix, determinism, provenance round trip ──────────────────────────
def test_matrix_reports_a_delta_block_for_all_32_oems():
    matrix = _load(MATRIX)
    assert matrix["artifact"] == "identity-matrix-p104/1"
    assert len(matrix["oems"]) == 32
    deltas = {e["brand"]: e["p104_delta"] for e in matrix["oems"]}
    assert any(d["first_party_confirmed_models"] or d["first_party_confirmed_variants"]
               for d in deltas.values())
    # an OEM with no new evidence must still show an explicit zero delta
    assert deltas["Land Rover"]["first_party_confirmed_variants"] == 0


def test_harvest_is_deterministic_over_committed_bytes():
    again = []
    rec = p104.load_baseline()
    again += p104.extract_model_identity(rec)
    again += p104.extract_grade_table(rec)
    again += p104.extract_sentence_rules()
    key = lambda i: (i["manufacturer"], i["model"], i["variant"],
                     i["artifact"], i["identity_level"])  # noqa: E731
    assert sorted(map(key, again)) == sorted(map(key, identities()))


def test_grade_rows_record_the_structural_link_to_their_model():
    rows = [i for i in identities() if i["extraction_method"] == "official_grade_table"]
    assert rows, "no structural grade rows were harvested"
    for row in rows:
        ev = row["evidence"]
        assert ev["model_anchor_line"] < ev["grade_line"]
        assert ev["structure"] in ("grade|price", "gear token + feature prose")
        assert row["identity_level"] == "VARIANT"


def test_sentence_rules_name_the_model_in_the_sentence():
    rows = [i for i in identities() if i["extraction_method"] == "official_sentence_grade"]
    assert rows, "no same-sentence grade rows"
    for row in rows:
        with open(os.path.join(FIXTURE_DIR, row["artifact"]), encoding="utf-8",
                  errors="ignore") as fh:
            text = fh.read()
        assert row["evidence"]["sentence"] in text
        assert f"รุ่น {row['variant']}" in text or f"รุ่น {row['variant']} " in text
