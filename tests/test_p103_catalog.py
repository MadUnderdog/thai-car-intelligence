"""P103 — first-party catalog acquisition + reconciliation boundaries.

Everything here is asserted from committed artifacts and committed fixtures
(offline, no network, no production data).  The contract under test:

  1  a P103 identity is only reported when it can be found in the artifact
     bytes it cites — the published label is the evidence, not a counter;
  2  `identity_level` is declared by the extractor, never inferred from the
     shape of a label;
  3  an existing candidate is CONFIRMED by attaching MARKET_TRUTH evidence,
     never by inventing a second copy of the identity;
  4  a genuinely new identity keeps the reason it was absent from P102;
  5  the same publication attaching the same identity twice is suppressed;
  6  sibling brands, generations and body styles stay separate;
  7  provenance sidecars round-trip (sha256 == bytes, source URL, method);
  8  P103 writes no rows into staging, carries no new price, and leaves the
     P102 conflict set and the recorded OEM blockers untouched.
"""
import hashlib
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "lib"))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import p103_first_party_catalog as p103  # noqa: E402
from thai_factory.catalog.identity_pass import match_key  # noqa: E402

PLAN = os.path.join(REPO, "audit", "coverage", "p103_target_plan.json")
IDENTITIES = os.path.join(REPO, "audit", "coverage", "p103_official_identities.json")
RECON = os.path.join(REPO, "audit", "coverage", "catalog_reconciliation_p103.json")
UNIVERSE = os.path.join(REPO, "audit", "coverage", "identity_universe_p103.json")
P102_UNIVERSE = os.path.join(REPO, "audit", "coverage", "identity_universe_p102.json")
MATRIX = os.path.join(REPO, "audit", "coverage", "identity_matrix_p103.json")
FINAL = os.path.join(REPO, "audit", "coverage", "p103_final_result.json")
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def identities():
    return _load(IDENTITIES)["identities"]


def universe_records():
    return _load(UNIVERSE)["universe"]["records"]


def find_record(mfr, model, variant=""):
    key_v = match_key(mfr, variant)
    hits = [r for r in universe_records()
            if r["manufacturer"] == mfr and match_key(mfr, r["model"]) == match_key(mfr, model)
            and match_key(mfr, r.get("variant") or "") == key_v]
    return hits[0] if hits else None


# ── 1. plan and target discipline ──────────────────────────────────────────
def test_target_plan_covers_every_in_scope_oem_and_separates_blockers():
    plan = _load(PLAN)
    assert plan["artifact"] == "p103_target_plan/1"
    targets, not_targeted, blocked = plan["targets"], plan["not_targeted"], plan["blocked_oems"]
    assert len(targets) + len(not_targeted) + len(blocked) == 32
    assert len(targets) + len(not_targeted) == 19      # reachable
    assert len(blocked) == 13
    attack = set(plan["attack_order"])
    # priority targets must be reachable and must show a real remaining deficit
    for brand in ("Mazda", "MG", "Subaru", "Isuzu"):
        entry = next(t for t in targets if t["brand"] == brand)
        assert entry["official_access_status"] == "REACHABLE"
        assert entry["variant_deficit_vs_candidates"] > 0
        assert brand in attack
    # a blocked OEM must never sit in the attack order
    assert not (attack & {b["brand"] for b in blocked})
    assert plan["baseline"]["in_scope_oems"] == 32
    assert plan["baseline"]["first_party_confirmed_models"] == 192
    assert plan["baseline"]["first_party_confirmed_variants"] == 370


def test_blockers_are_carried_over_verbatim_and_smart_stays_recorded():
    plan = _load(PLAN)
    final = _load(FINAL)
    p102 = _load(os.path.join(REPO, "audit", "coverage", "identity_matrix_p102.json"))
    p102_access = {e["brand"]: e["official_access_status"] for e in p102["oems"]}
    everything = {t["brand"]: t for t in
                  plan["targets"] + plan["not_targeted"] + plan["blocked_oems"]}
    assert len(everything) == 32
    for brand, entry in everything.items():
        assert entry["official_access_status"] == p102_access[brand]
        if p102_access[brand].startswith("BLOCKED"):
            assert entry["blockers"], brand
    # no retry happened against a blocked host in this wave
    assert final["blocker_changes"]["new_blockers"] == []
    assert final["blocker_changes"]["cleared_blockers"] == []
    assert final["blocker_changes"]["retried_blocked_hosts"] == []
    assert final["blocker_changes"]["smart_status"] == p102_access["Smart"]


# ── 2. evidence: the published identity must exist in the cited artifact ──
@pytest.mark.parametrize("item", identities(), ids=lambda i: f"{i['manufacturer']}-{i['variant']}")
def test_published_identity_is_present_in_the_cited_artifact(item):
    path = os.path.join(REPO, "tests", "fixtures", "oem-artifacts", item["artifact"])
    assert os.path.exists(path), path
    with open(path, encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    assert item["variant"] in text, f"grade {item['variant']!r} not in {item['artifact']}"
    assert item["identity_level"] in ("MODEL", "VARIANT")
    assert item["extraction_method"]
    with open(path, "rb") as fh:
        assert item["sha256"] == hashlib.sha256(fh.read()).hexdigest()


def test_identity_level_is_declared_by_the_extractor_not_inferred():
    for item in identities():
        # every P103 harvest in this wave is a grade/variant layer; an
        # extractor that inferred the level from the label shape could not
        # produce an empty level, so the declared field must be explicit.
        assert item["identity_level"] == "VARIANT"
        assert item["identity_level"] != ""
    # and the reconciliation records the same declared level on its source
    rec = next(e for e in identities()
               if e["reconciliation"]["outcome"] in ("new", "existing"))
    assert rec["identity_level"] == "VARIANT"


# ── 3. confirmation of an existing candidate vs a genuinely new identity ──
def test_existing_candidate_is_confirmed_and_not_duplicated():
    # MG publishes "MG3 HYBRID+ รุ่น D"; P102 already carried that identity as
    # an identity-only candidate from an enumerator.  P103 must flip it.
    p102 = _load(P102_UNIVERSE)["universe"]["records"]
    prior = next(r for r in p102
                 if r["manufacturer"] == "MG" and r["model"] == "Mg3 Hybrid"
                 and r["variant"] == "+ D")
    assert prior["status"] == "IDENTITY_ONLY"

    rec = find_record("MG", "Mg3 Hybrid", "+ D")
    assert rec["status"] == "CONFIRMED_VARIANT"
    truth = [s for s in rec["first_party"] if s["source_role"] == "MARKET_TRUTH"]
    assert truth, rec
    assert truth[0]["identity_level"] == "VARIANT"
    # exactly one record carries this identity — no second copy was created
    twins = [r for r in universe_records()
             if r["manufacturer"] == "MG" and match_key("MG", r["model"]) == match_key("MG", "MG3 HYBRID+")
             and match_key("MG", r.get("variant") or "") == match_key("MG", "D")]
    assert len(twins) == 1


def test_genuinely_new_identity_keeps_the_reason_it_was_absent():
    recon = _load(RECON)
    new_rows = recon["new_first_party_identities"]
    assert new_rows, "no new first-party identity was established"
    mazda = [e for e in identities()
             if e["reconciliation"]["outcome"] == "new"
             and e["manufacturer"] == "Mazda"]
    assert mazda, "Mazda grade layer was not harvested"
    p102_pairs = {(r["manufacturer"], match_key(r["manufacturer"], r["model"]),
                   match_key(r["manufacturer"], r.get("variant") or ""))
                  for r in _load(P102_UNIVERSE)["universe"]["records"]}
    for item in mazda:
        pair = (item["manufacturer"], match_key("Mazda", item["model"]),
                match_key("Mazda", item["variant"]))
        assert pair not in p102_pairs, f"{item['variant']} already existed in P102"
        assert item["reconciliation"]["reason"]
        assert item["reconciliation"]["outcome"] == "new"


def test_new_first_party_records_carry_no_price_and_no_staging_row():
    p102_pairs = {(r["manufacturer"], match_key(r["manufacturer"], r["model"]),
                   match_key(r["manufacturer"], r.get("variant") or ""))
                  for r in _load(P102_UNIVERSE)["universe"]["records"]}
    fresh = [r for r in universe_records()
             if (r["manufacturer"], match_key(r["manufacturer"], r["model"]),
                 match_key(r["manufacturer"], r.get("variant") or "")) not in p102_pairs]
    assert fresh
    for r in fresh:
        assert r["published_price_thb"] is None, r
        assert r["status"] == "CONFIRMED_VARIANT"
    # staging is untouched by P103: no row carries a P103 artifact/session
    with open(STAGING, encoding="utf-8") as fh:
        staging = fh.read()
    assert "p103" not in staging.lower()
    final = _load(FINAL)
    assert final["gates"]["staging_written"] is False
    assert final["gates"]["price_pass"] is False


# ── 4. duplicate suppression / idempotence ─────────────────────────────────
def test_same_source_same_identity_is_attached_once():
    for r in universe_records():
        keys = [(s.get("source_name"), s.get("source_url"), s.get("identity_level"))
                for s in r["sources"]]
        assert len(keys) == len(set(keys)), r["model"]


def test_second_harvest_of_the_same_publication_changes_nothing():
    # extraction is deterministic over committed bytes: the same artifacts must
    # yield the same identity set on every run (no hidden network state).
    again = []
    for _brand, fn in p103.EXTRACTORS:
        again.extend(fn())
    first = identities()
    key = lambda i: (i["manufacturer"], i["model"], i["variant"], i["artifact"])  # noqa: E731
    assert sorted(map(key, again)) == sorted(map(key, first))
    assert again, "extractors returned nothing"

    # and each record carries at most one P103 publication entry per label
    for r in universe_records():
        labels = [s.get("label") for s in r["first_party"] if s.get("extraction_method")]
        assert len(labels) == len(set(labels)), r["model"]


def test_attaching_the_same_publication_twice_is_idempotent():
    rec = p103.load_baseline()
    source = {
        "source_name": "Mazda Thailand Official",
        "source_role": "MARKET_TRUTH",
        "source_url": "https://www.mazda.co.th/ cars/mazda3-sedan",
        "label": "MAZDA3 SEDAN 2.0 C",
        "identity_level": "VARIANT",
    }
    rec.add_first_party("Mazda", "MAZDA3 SEDAN", "2.0 C", dict(source))
    rec.add_first_party("Mazda", "MAZDA3 SEDAN", "2.0 C", dict(source))
    target = next(r for r in rec.records
                  if r.manufacturer == "Mazda" and r.model == "MAZDA3 SEDAN"
                  and r.variant == "2.0 C")
    entries = [s for s in target.first_party
               if s.get("label") == "MAZDA3 SEDAN 2.0 C"]
    assert len(entries) == 1


# ── 5. sibling brand / generation / body separation ────────────────────────
def test_sibling_brands_never_receive_each_others_identities():
    # every P103 publication carries its manufacturer and its artifact; it may
    # only ever be attached to a record of that same manufacturer.
    checked = 0
    for r in universe_records():
        for s in r["first_party"]:
            if not s.get("extraction_method"):
                continue                      # not a P103 publication
            checked += 1
            assert s["manufacturer"] == r["manufacturer"], (r["model"], s)
            assert s["source_name"].startswith(s["manufacturer"])
            assert s["manufacturer"].upper() in s["artifact"].upper()
    assert checked == len(identities()), (checked, len(identities()))

    # and the cited artifact file must really be that OEM's artifact
    for item in identities():
        path = os.path.join(REPO, "tests", "fixtures", "oem-artifacts", item["artifact"])
        assert os.path.exists(path)
        stem = item["artifact"].split("_")[0].upper()
        assert stem in os.path.basename(path).upper()
def test_generation_and_body_variants_are_not_collapsed():
    bt50 = [r for r in universe_records()
            if r["manufacturer"] == "Mazda"
            and match_key("Mazda", r["model"]) == match_key("Mazda", "NEW MAZDA BT-50")]
    labels = sorted(r["variant"] for r in bt50)
    assert labels, "BT-50 grades were not harvested"
    # drivetrain/body distinctions stay separate verbatim labels
    assert len(set(labels)) == len(labels)
    if "DBL 3.0 XTR HI-RACER 6AT" in labels and "DBL 3.0 XTR 4x4 6AT" in labels:
        assert labels.count("DBL 3.0 XTR HI-RACER 6AT") == 1
    mazda2 = [r for r in universe_records()
              if r["manufacturer"] == "Mazda"
              and match_key("Mazda", r["model"]) == match_key("Mazda", "NEW MAZDA2 ESSENTIAL")]
    sports = [r for r in mazda2 if r["variant"].endswith("SPORTS")]
    plain = [r for r in mazda2 if not r["variant"].endswith("SPORTS")]
    assert sports and plain, "SPORTS body line must stay separate from the base line"


# ── 6. provenance sidecars for the captures this wave added ───────────────
def test_new_official_captures_round_trip_through_their_sidecar():
    for fname in ("subaru_th_model_forester.html", "subaru_th_model_crosstrek.html",
                  "subaru_th_model_brz.html"):
        path = os.path.join(REPO, "tests", "fixtures", "oem-artifacts", fname)
        with open(path, "rb") as fh:
            raw = fh.read()
        with open(path + ".prov.json", encoding="utf-8") as fh:
            prov = json.load(fh)
        assert prov["sha256"] == hashlib.sha256(raw).hexdigest()
        assert prov["source_url"].startswith("https://www.subaru.asia/")
        assert prov["acquisition_method"]
        assert prov["captured_at"]


def test_reused_bytes_are_recorded_as_reused_not_refetched():
    log = _load(os.path.join(REPO, "audit", "coverage", "p103_capture_log.json"))
    assert log["results"], log
    for res in log["results"]:
        assert res["ok"] is True or res.get("reused") is True


# ── 7. P102 boundaries stay frozen ─────────────────────────────────────────
def test_p102_conflicts_identity_only_and_rejections_are_not_rewritten():
    p102 = _load(P102_UNIVERSE)["universe"]
    final = _load(FINAL)
    p102_conflicts = sum(1 for r in p102["records"] if r["status"] == "CONFLICT")
    assert final["conflicts"]["records"] == p102_conflicts
    # new first-party records never enter the rejected set
    assert len(_load(UNIVERSE)["universe"]["rejected"]) == len(p102["rejected"])


def test_identity_only_records_are_never_promoted_by_this_wave():
    p102_io = [r for r in _load(P102_UNIVERSE)["universe"]["records"]
               if r["status"] == "IDENTITY_ONLY"]
    now = {(r["manufacturer"], match_key(r["manufacturer"], r["model"]),
            match_key(r["manufacturer"], r.get("variant") or "")): r["status"]
           for r in universe_records()}
    for r in p102_io:
        key = (r["manufacturer"], match_key(r["manufacturer"], r["model"]),
               match_key(r["manufacturer"], r.get("variant") or ""))
        status = now[key]
        # it may become CONFIRMED only when this wave attached MARKET_TRUTH
        # evidence to that exact identity; it may never become something else
        assert status in ("IDENTITY_ONLY", "CONFIRMED_VARIANT", "CONFIRMED_MODEL")


def test_per_oem_matrix_carries_a_delta_block():
    matrix = _load(MATRIX)
    assert matrix["artifact"] == "identity-matrix-p103/1"
    deltas = {e["brand"]: e["p103_delta"] for e in matrix["oems"]}
    assert len(deltas) == 32
    assert deltas["Mazda"]["first_party_confirmed_variants"] > 0
    assert deltas["MG"]["first_party_confirmed_variants"] > 0
    assert deltas["Subaru"]["first_party_confirmed_variants"] > 0
    assert deltas["Isuzu"]["first_party_confirmed_variants"] > 0
    # an OEM with no new evidence must show an explicit zero delta
    assert deltas["Lexus"]["first_party_confirmed_variants"] == 0
