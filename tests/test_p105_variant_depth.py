"""P105 — first-party VARIANT depth pass.

Contract asserted here (offline, from committed fixtures and committed JSON):

  1  every variant row is bound to its model inside the published line, or to a
     page whose official URL names that model, and is a grade row (name|price
     adjacency, a grade list of that model, or a bare grade row uniquely owned
     by one model) — never a bare occurrence
  2  navigation / footer / meta / style text is never evidence, and generic
     labels are never variants
  3  provenance is verified before evidence is used (SHA-256 vs sidecar,
     ACQUISITION_VERIFIED, https source URL)
  4  no model promotion, no sibling-brand attribution, no cross-generation
     fallback, no price pass, no staging/production write
  5  ordering is deterministic: the same input produces the same rows
     regardless of set iteration order (the pre-fix extractor produced
     457 / 463 / 460 confirmations under three PYTHONHASHSEED values)
  6  counts reconcile: plan < result == reconciliation == evidence artifact,
     and the report prose equals those JSON numbers
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import random
import re
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "lib"))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import p105_variant_depth as p105  # noqa: E402
from p105_variant_depth import norm  # noqa: E402

OUT = os.path.join(REPO, "audit", "coverage")
PLAN = os.path.join(OUT, "p105_target_plan.json")
EVIDENCE = os.path.join(OUT, "p105_variant_evidence.json")
RECON = os.path.join(OUT, "catalog_reconciliation_p105.json")
RESULT = os.path.join(OUT, "p105_final_result.json")
MATRIX = os.path.join(OUT, "identity_matrix_p105.json")
REPORT = os.path.join(OUT, "p105_final_report.md")
U104 = os.path.join(OUT, "identity_universe_p104.json")
U105 = os.path.join(OUT, "identity_universe_p105.json")

METHODS = {"official_name_price_row", "official_grade_list_row",
           "official_page_bound_grade_list", "official_grade_table_row",
           "official_grade_list_bare_row"}


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def evidence():
    return _load(EVIDENCE)["evidence"]


# ── 1. plan ────────────────────────────────────────────────────────────────
def test_target_plan_exists_and_is_versioned():
    plan = _load(PLAN)
    assert plan["schema"] == "p105_target_plan/1"
    assert plan["baseline_artifact"] == "audit/coverage/p104_final_result.json"
    assert plan["objective"].startswith("first-party VARIANT")


def test_plan_covers_32_oems_and_ranks_the_deficit():
    plan = _load(PLAN)
    assert plan["totals"]["rows"] == 32
    assert plan["totals"]["blocked"] == 13
    deficits = [r["variant_deficit"] for r in plan["oems"]]
    assert deficits == sorted(deficits, reverse=True)
    top = plan["priority_order"]
    assert top[:4] == ["Toyota", "BMW", "Mazda", "MG"], top


def test_plan_keeps_every_blocker_verbatim_and_never_targets_it():
    plan = _load(PLAN)
    matrix = _load(os.path.join(OUT, "identity_matrix_p104.json"))
    by_brand = {e["brand"]: e for e in matrix["oems"]}
    for row in plan["oems"]:
        if row["official_access_status"] == "REACHABLE":
            assert "blockers" not in row
            continue
        assert row["targeted_this_wave"] is False
        assert row["blockers"] == (by_brand[row["brand"]].get("blockers") or []), row["brand"]
        assert row["blocker_kind"] == by_brand[row["brand"]]["official_access_status"]
    smart = [r for r in plan["oems"] if r["brand"] == "Smart"][0]
    assert smart["blocker_kind"] == "DEALER_REDIRECT"
    assert smart["targeted_this_wave"] is False


def test_plan_totals_match_the_matrix_deficit():
    plan = _load(PLAN)
    matrix = _load(os.path.join(OUT, "identity_matrix_p104.json"))
    expected = sum(e["identity"]["variant_candidates_discovered"] -
                   e["identity"]["first_party_confirmed_variants"]
                   for e in matrix["oems"])
    assert plan["totals"]["variant_deficit"] == expected == 461


# ── 2. evidence shape, model binding, provenance ───────────────────────────
def test_every_row_is_a_variant_level_identity():
    for row in evidence():
        assert row["identity_level"] == "VARIANT", row
        assert row["variant"], row
        assert row["extraction_method"] in METHODS, row["extraction_method"]


def test_every_row_is_bound_to_its_model_by_the_published_line_or_url():
    universe = _load(U105)["universe"]["records"]
    models = {(r["manufacturer"], r["model"]) for r in universe}
    for row in evidence():
        assert (row["manufacturer"], row["model"]) in models, row
        line = row["evidence"]["composite_line"]
        base = row["evidence"]["model_prefix"]
        if row["extraction_method"] == "official_page_bound_grade_list":
            # page-level binding: the official URL slug names the model
            assert row["evidence"]["structure"].startswith("page URL names")
        elif row["extraction_method"] in ("official_grade_list_bare_row",
                                          "official_grade_table_row"):
            # bare grade row: the page lists ≥2 grades only this model owns
            assert f"only {row['model']} owns" in row["evidence"]["structure"], row
            assert norm(row["variant"]) in norm(line)
        else:
            assert line.casefold().startswith(base.casefold() + " "), (line, base)
            assert norm(line) != norm(row["model"])      # never the bare model name
            assert norm(row["variant"]) in norm(line)


def test_rows_are_grade_rows_not_mere_occurrences():
    for row in evidence():
        structure = row["evidence"]["structure"]
        assert ("price" in structure or "grade list" in structure
                or "grades" in structure or "grade row" in structure), structure
        assert row["evidence"]["selector"].startswith("official")


def test_no_row_comes_from_navigation_footer_meta_or_style():
    rejected = {norm(r.get("text", "")) for r in _load(RECON)["rejected_rows"]
                if r.get("text")}
    for row in evidence():
        body = p105.body_text(row["artifact"])
        assert norm(row["evidence"]["composite_line"]) in norm(body), row


def test_generic_labels_are_never_published_as_variants():
    generic = {norm(x) for x in __import__(
        "p104_first_party_breadth", fromlist=["GENERIC_LABELS"]).GENERIC_LABELS}
    for row in evidence():
        assert norm(row["variant"]) not in generic, row


def test_every_row_cites_verified_provenance():
    from p104_first_party_breadth import artifact_path, artifact_sha, verify_artifact
    for row in evidence():
        path = artifact_path(row["artifact"])
        prov, reason = verify_artifact(path)
        assert prov is not None, (row["artifact"], reason)
        assert prov.get("provenance_state") == "ACQUISITION_VERIFIED"
        assert prov["source_url"].startswith("https://")
        assert row["source_url"] == prov["source_url"]
        assert row["sha256"] == artifact_sha(path)
        with open(path, "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == row["sha256"]


def test_rejected_rows_are_recorded_with_a_reason():
    rows = _load(RECON)["rejected_rows"]
    assert rows, "navigation/generic rejections must be visible"
    for row in rows:
        assert row["reason"]
        assert "navigation" in row["reason"] or "generic" in row["reason"]


# ── 3. reconciliation boundaries ───────────────────────────────────────────
def test_no_model_promotion_and_no_sibling_contamination():
    before = {(r["manufacturer"], r["model"], r["variant"]): r
              for r in _load(U104)["universe"]["records"]}
    after = {(r["manufacturer"], r["model"], r["variant"]): r
             for r in _load(U105)["universe"]["records"]}
    assert set(before) == set(after), "P105 must not invent or drop identities"
    for key, rec in after.items():
        assert rec["manufacturer"] == before[key]["manufacturer"]
        assert rec["model"] == before[key]["model"]
        if not rec["variant"]:
            assert rec["first_party"] == before[key]["first_party"], key
            assert rec["status"] == before[key]["status"], key


def test_only_variant_records_changed_status():
    before = {(r["manufacturer"], r["model"], r["variant"]): r["status"]
              for r in _load(U104)["universe"]["records"]}
    after = {(r["manufacturer"], r["model"], r["variant"]): r["status"]
             for r in _load(U105)["universe"]["records"]}
    changed = [(k, before[k], after[k]) for k in before if before[k] != after[k]]
    assert changed, "the pass must confirm something"
    for key, old, new in changed:
        assert key[2], f"model-level record changed status: {key}"
        assert new == "CONFIRMED_VARIANT", (key, old, new)
        assert old in ("IDENTITY_ONLY", "CONFLICT")


def test_reconciliation_outcomes_are_existing_only_and_never_ambiguous():
    recon = _load(RECON)
    assert recon["outcomes"] == {"existing": recon["harvested"]}
    assert recon["new_identities"] == []
    assert recon["ambiguous"] == []


def test_row_order_is_deterministic_against_set_iteration_order():
    """The defect that made counts depend on PYTHONHASHSEED (457/463/460)."""
    models = {"Toyota Yaris", "Yaris ATIV", "Toyota Corolla", "GR Yaris",
              "Toyota Fortuner", "Corolla Altis"}
    first = p105.model_bases("Toyota", set(models))
    for _ in range(5):
        shuffled = list(models)
        random.shuffle(shuffled)
        assert p105.model_bases("Toyota", set(shuffled)) == first
    assert first == sorted(first, key=lambda x: (-len(x[0]), x[1], x[0]))


def test_rows_are_unique_per_publication_slot():
    keys = [(r["manufacturer"], r["model"], r["variant"], r["artifact"],
             r["evidence"]["line"]) for r in evidence()]
    assert len(keys) == len(set(keys))


def test_no_source_carries_a_generation_context_it_did_not_publish():
    for row in evidence():
        assert row["source_generation_context"] == ""


# ── 4. count reconciliation ────────────────────────────────────────────────
def test_evidence_reconciliation_and_result_agree():
    ev = evidence()
    recon = _load(RECON)
    result = _load(RESULT)
    assert recon["harvested"] == len(ev)
    assert result["harvested_rows"] == len(ev)
    assert recon["outcomes"] == result["outcomes"]
    assert recon["by_method"] == result["by_method"]
    methods = collections.Counter(r["extraction_method"] for r in ev)
    assert dict(methods) == result["by_method"]


def test_confirmed_variant_totals_move_by_exactly_the_status_changes():
    result = _load(RESULT)
    before, after = result["before_after"]["first_party_confirmed_variants"]
    before_u = _load(U104)["universe"]["records"]
    after_u = _load(U105)["universe"]["records"]
    cb = sum(1 for r in before_u if r["variant"] and r["first_party"])
    ca = sum(1 for r in after_u if r["variant"] and r["first_party"])
    assert (before, after) == (cb, ca) == (404, 466)
    assert after - before == 62


def test_identity_only_falls_by_the_same_amount_models_do_not_move():
    result = _load(RESULT)
    io = result["identity_only"]
    before_u = _load(U104)["universe"]["records"]
    after_u = _load(U105)["universe"]["records"]
    assert io["variants"] == len([r for r in after_u
                                  if r["variant"] and r["status"] == "IDENTITY_ONLY"])
    assert io["models"] == len([r for r in after_u
                                if not r["variant"] and r["status"] == "IDENTITY_ONLY"])
    assert io["models"] == 316                    # models untouched
    assert 457 - io["variants"] == 61
    assert sum(1 for r in before_u if not r["variant"] and r["first_party"]) == \
        sum(1 for r in after_u if not r["variant"] and r["first_party"]) == 221


def test_conflicts_and_rejects_are_reconciled_not_hidden():
    result = _load(RESULT)
    assert result["conflicts"]["records"] == 25       # was 26
    assert result["rejected"]["records"] == 1927      # unchanged
    u104 = _load(U104)["universe"]["records"]
    u105 = _load(U105)["universe"]["records"]
    gone = [r for r in u104 if r["status"] == "CONFLICT" and
            { (x["model"], x["variant"]): x["status"] for x in u105 }
            .get((r["model"], r["variant"])) != "CONFLICT"]
    assert len(gone) == 1
    assert (gone[0]["manufacturer"], gone[0]["model"], gone[0]["variant"]) == \
        ("Isuzu", "Isuzu D Max", "X Series")
    gained = [r for r in u105 if r["status"] == "CONFLICT" and
              {(x["model"], x["variant"]): x["status"] for x in u104}
              .get((r["model"], r["variant"])) != "CONFLICT"]
    assert gained == []


def test_per_oem_deltas_sum_to_the_total():
    result = _load(RESULT)
    total = sum(v["confirmed_variants"] for v in result["per_oem_delta"].values())
    assert total == 62 == (result["before_after"]["first_party_confirmed_variants"][1]
                           - result["before_after"]["first_party_confirmed_variants"][0])
    assert set(result["per_oem_delta"]) <= {"BMW", "Deepal", "GWM", "Honda", "Isuzu",
                                            "Lexus", "MG", "Mazda", "Mitsubishi",
                                            "Suzuki", "Toyota"}


def test_matrix_p105_matches_the_result():
    matrix = _load(MATRIX)
    result = _load(RESULT)
    total = sum(e["p105_delta"]["confirmed_variants"] for e in matrix["oems"])
    assert total == 62
    rows = sum(e["p105_delta"]["rows"] for e in matrix["oems"])
    assert rows == result["harvested_rows"]
    for entry in matrix["oems"]:
        if entry["official_access_status"] != "REACHABLE":
            assert entry["p105_delta"] == {"confirmed_variants": 0, "rows": 0}


# ── 5. report prose follows the JSON ───────────────────────────────────────
def test_report_exists_and_states_the_json_numbers():
    result = _load(RESULT)
    text = open(REPORT, encoding="utf-8").read()
    before, after = result["before_after"]["first_party_confirmed_variants"]
    assert f"{before} → {after}" in text or f"{before} -> {after}" in text, (before, after)
    assert str(result["identity_only"]["records"]) in text
    assert str(result["conflicts"]["records"]) in text
    assert str(result["rejected"]["records"]) in text
    assert str(result["harvested_rows"]) in text
    assert "</think" not in text and "<think" not in text


def test_report_lists_every_zero_gain_priority_oem():
    result = _load(RESULT)
    text = open(REPORT, encoding="utf-8").read()
    for brand in ("Nissan", "Porsche", "Kia", "Subaru", "MINI", "Changan", "Jaguar"):
        assert brand in text, brand
        assert result["per_oem_delta"].get(brand) is None or \
            result["per_oem_delta"][brand]["confirmed_variants"] == 0


# ── 6. gates ───────────────────────────────────────────────────────────────
def test_no_price_pass_no_staging_no_production_write():
    result = _load(RESULT)
    gates = result["gates"]
    assert gates["staging_written"] is False
    assert gates["price_pass"] is False
    assert gates["prisma_touched"] is False
    assert gates["production_db_unchanged"] is True
    assert _load(RECON)["staging_written"] is False
    assert _load(RECON)["price_pass"] is False


def test_no_published_price_was_written_by_this_pass():
    after = _load(U105)["universe"]["records"]
    before = {(r["manufacturer"], r["model"], r["variant"]): r["published_price_thb"]
              for r in _load(U104)["universe"]["records"]}
    for rec in after:
        key = (rec["manufacturer"], rec["model"], rec["variant"])
        assert rec["published_price_thb"] == before.get(key), key


def test_p104_p103_p102_artifacts_and_code_are_untouched_by_the_result():
    result = _load(RESULT)
    assert result["gates"]["p104_p103_p102_logic_changed"] is False
    baseline = _load(os.path.join(OUT, "p104_final_result.json"))
    assert baseline["before_after"]["first_party_confirmed_variants"] == [401, 404]
    assert baseline["before_after"]["first_party_confirmed_models"] == [194, 243]
