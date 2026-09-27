"""P102 — identity universe: catalog-universe behaviour and identity/evidence
boundaries.

Everything here is asserted from committed artifacts (offline).  The contract
under test is the P102 acceptance boundary:

  1  identity-only candidates live in the Phase-1 universe artifact only —
     never in staging, never in the production DB;
  2  a candidate is first-party confirmed ONLY when a MARKET_TRUTH record
     carries the same identity (§96 roles never silently upgrade);
  3  no price is invented: prices keep the role of the source that published
     them, and only first-party rows carry MARKET_TRUTH prices;
  4  variant labels are verbatim published labels — never split, never generic;
  5  sibling brands never contaminate each other;
  6  blocked OEMs keep their official blocker and are never shown as covered;
  7  every enumerator artifact round-trips through its provenance sidecar.
"""
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "lib"))

from thai_factory.catalog.identity_pass import (  # noqa: E402
    BRAND_ALIASES, FirstPartyStatus, IdentityReconciliation, clean_model_label,
    leading_brand, match_key, parse_index_page,
)
from thai_factory.catalog.universe import SourceRole  # noqa: E402

UNIVERSE = os.path.join(REPO, "audit", "coverage", "identity_universe_p102.json")
MATRIX = os.path.join(REPO, "audit", "coverage", "identity_matrix_p102.json")
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
REGISTRY = os.path.join(REPO, "audit", "coverage", "oem-registry.json")
ENUM_DIR = os.path.join(REPO, "tests", "fixtures", "identity-enumerator-artifacts")

NON_TRUTH_SOURCES = {
    "9carthai price index", "bangkok_insurance_motor_quote", "viriyah",
    "one2car", "chobrod", "headlightmag", "thai_market_reference",
    "open_ev_data", "fipe_brazilian_vehicle_reference",
}


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def universe():
    return _load(UNIVERSE)


@pytest.fixture(scope="module")
def matrix():
    return _load(MATRIX)


@pytest.fixture(scope="module")
def records(universe):
    return universe["universe"]["records"]


@pytest.fixture(scope="module")
def staging_rows():
    with open(STAGING, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


@pytest.fixture(scope="module")
def in_scope():
    reg = _load(REGISTRY)
    return [b["brand"] for b in reg["brands"] if b.get("in_scope")]


# ── 1. the universe is a separate Phase-1 artifact ──────────────────────────
def test_universe_declares_its_acceptance_boundary(universe):
    assert "identity-only" in universe["acceptance_boundary"]
    assert "production DB" in universe["acceptance_boundary"]


def test_universe_never_writes_staging(staging_rows):
    """No enumerator/reference/media source may ever appear as a staged row."""
    staged_sources = {r["source"]["name"] for r in staging_rows}
    assert not (staged_sources & NON_TRUTH_SOURCES), sorted(
        staged_sources & NON_TRUTH_SOURCES)


def test_staging_rows_are_all_first_party(staging_rows):
    classes = {r["source"]["class"] for r in staging_rows}
    assert classes <= {"OEM_OFFICIAL"}, classes


def test_universe_has_no_priceless_rows_promoted(universe):
    """An identity-only record can never claim an accepted status."""
    for r in universe["universe"]["records"]:
        if r["status"] == FirstPartyStatus.IDENTITY_ONLY.value:
            assert not r["first_party"], r["canonical_key"]
            assert any("identity-only" in x for x in r["rejection_reasons"]), r


# ── 2. §96 role separation ──────────────────────────────────────────────────
def test_confirmed_records_carry_market_truth(records):
    for r in records:
        if r["status"] in (FirstPartyStatus.CONFIRMED_MODEL.value,
                           FirstPartyStatus.CONFIRMED_VARIANT.value):
            roles = {s["source_role"] for s in r["sources"]}
            assert SourceRole.MARKET_TRUTH.value in roles, r["canonical_key"]
            assert r["first_party"], r["canonical_key"]


def test_identity_only_records_never_carry_market_truth(records):
    for r in records:
        if r["status"] == FirstPartyStatus.IDENTITY_ONLY.value:
            roles = {s["source_role"] for s in r["sources"]}
            assert SourceRole.MARKET_TRUTH.value not in roles, r["canonical_key"]
            assert not r["first_party"], r["canonical_key"]


def test_only_official_artifacts_set_official_confidence(universe):
    conf = universe["universe"]["summary"]["confidence"]
    official = sum(1 for r in universe["universe"]["records"]
                   if SourceRole.MARKET_TRUTH.value in
                   {s["source_role"] for s in r["sources"]})
    assert conf["OFFICIAL_VERIFIED"] == official
    assert conf["UNRESOLVED"] == 0


def test_role_values_are_the_declared_four(records):
    allowed = {r.value for r in SourceRole}
    assert allowed == {"IDENTITY_ENUMERATOR", "MARKET_TRUTH",
                       "MARKET_REFERENCE", "MEDIA_DISCOVERY"}
    for r in records:
        for s in r["sources"]:
            assert s["source_role"] in allowed, s


# ── 3. prices are never invented ────────────────────────────────────────────
def test_prices_keep_their_source_role(records):
    allowed = {SourceRole.MARKET_TRUTH.value, SourceRole.MEDIA_DISCOVERY.value,
               SourceRole.MARKET_REFERENCE.value,
               SourceRole.IDENTITY_ENUMERATOR.value}
    for r in records:
        if r["published_price_thb"] is not None:
            assert isinstance(r["published_price_thb"], int) and \
                r["published_price_thb"] > 0, r["canonical_key"]
            assert r["published_price_role"] in allowed, r
            if r["published_price_role"] == SourceRole.MARKET_TRUTH.value:
                assert r["first_party"], r["canonical_key"]


def test_no_record_invents_a_price(records):
    """A record with no published price keeps None — never a placeholder."""
    for r in records:
        assert r["published_price_thb"] in (None,) or \
            isinstance(r["published_price_thb"], int)
        if r["published_price_thb"] is None:
            assert r["published_price_role"] == ""


# ── 4. variant labels are verbatim and never fabricated ────────────────────
GENERIC = {"STANDARD", "BASE", "ENTRY", "DEFAULT", "GENERIC", "OTHER", "อื่นๆ"}


def test_no_generic_variant_names(records):
    for r in records:
        assert r["variant"].upper() not in GENERIC, r["canonical_key"]
        assert r["variant"].strip() == r["variant"], r


def test_variant_labels_appear_verbatim_in_their_source(records):
    for r in records:
        if not r["variant"]:
            continue
        labels = [s.get("label", "") for s in r["sources"]]
        assert any(r["variant"] in lab for lab in labels), (
            f"{r['canonical_key']} not found in any source label")


def test_identity_level_matches_the_record(records):
    for r in records:
        expected = "VARIANT" if r["variant"] else "MODEL"
        assert r["identity_level"] == expected
        assert r["variant"] == "" or r["model"] != ""
        # publication-level: every source entry must have declared its own
        # level at ingestion (the generated P102 artifact ships 0 undeclared)
        assert r["sources"], r
        for s in r["sources"]:
            assert s.get("identity_level") in ("MODEL", "VARIANT"), (r, s)


# ── 5. sibling-brand separation ─────────────────────────────────────────────
def test_model_labels_attribute_to_their_own_manufacturer(records):
    for r in records:
        lb = leading_brand(r["model"])
        assert lb in (r["manufacturer"], None), (
            f"{r['manufacturer']} claims {r['model']!r} (leading brand {lb})")


def test_sibling_brands_are_not_merged(records):
    def owned(mfr, model):
        for r in records:
            if r["manufacturer"] == mfr and \
                    match_key(mfr, r["model"]) == match_key(mfr, model):
                return True
        return False

    # Deepal and Changan are separate OEMs — a Deepal identity is never Changan
    deepal = [r for r in records if r["manufacturer"] == "Deepal"]
    for r in deepal:
        assert r["manufacturer"] == "Deepal"
        assert leading_brand(r["model"]) in ("Deepal", None)

    # Haval and GWM likewise
    for r in records:
        if r["manufacturer"] == "Haval":
            assert leading_brand(r["model"]) in ("Haval", None)
        if r["manufacturer"] == "GWM":
            assert leading_brand(r["model"]) in ("GWM", None)


def test_manufacturer_aliases_never_cross():
    """A brand's own aliases must not be registered under another brand."""
    owned = {}
    for brand, aliases in BRAND_ALIASES.items():
        for a in aliases:
            owned.setdefault(a.upper(), set()).add(brand)
    clashes = {a: b for a, b in owned.items() if len(b) > 1}
    assert clashes == {}, clashes


# ── 6. coverage of every in-scope OEM + honest blockers ─────────────────────
def test_every_in_scope_oem_is_in_the_matrix(matrix, in_scope):
    got = [e["brand"] for e in matrix["oems"]]
    assert sorted(got) == sorted(in_scope)
    assert matrix["totals"]["oems_in_scope"] == len(in_scope)


def test_blocked_official_oems_keep_their_blocker(matrix, in_scope):
    for e in matrix["oems"]:
        if e["official_access_status"] == "REACHABLE":
            continue
        official_blockers = [b for b in e["blockers"]
                             if b["layer"] == "official_first_party"]
        assert official_blockers, e["brand"]
        assert official_blockers[0]["blocker"] == e["official_access_status"]


def test_blocked_oems_are_never_marked_officially_confirmed(matrix, staging_rows):
    staged = {b for b in (r["identity"]["brand_normalized"] for r in staging_rows)}
    for e in matrix["oems"]:
        if e["staged_first_party_rows"]:
            continue
        ident = e["identity"]
        assert ident["first_party_confirmed_models"] == 0, e["brand"]
        assert ident["first_party_confirmed_variants"] == 0, e["brand"]
        assert ident["first_party_confirmation"] in (
            "NONE_FIRST_PARTY_MISSING", "NO_ENUMERATOR_AND_NO_FIRST_PARTY"), e["brand"]


def test_identity_only_candidates_are_labelled_as_such(matrix):
    for e in matrix["oems"]:
        ident = e["identity"]
        assert ident["identity_only_models"] == (
            ident["model_candidates_discovered"] -
            ident["first_party_confirmed_models"])
        assert ident["identity_only_variants"] == (
            ident["variant_candidates_discovered"] -
            ident["first_party_confirmed_variants"])


def test_gap_oems_have_identity_candidates(matrix):
    """The P101 gap OEMs must actually gain identity candidates here."""
    by_brand = {e["brand"]: e for e in matrix["oems"]}
    for brand in ("Mazda", "MG", "Subaru", "BMW", "Toyota", "Honda", "GWM",
                  "Mitsubishi", "Nissan", "Changan"):
        assert by_brand[brand]["identity"]["variant_candidates_discovered"] > 0, brand


def test_blocked_oem_identity_comes_only_from_enumerators(matrix, records):
    """A blocked OEM's identity candidates may come from non-truth sources
    only: no record for it may carry MARKET_TRUTH, and none may be confirmed."""
    truth = SourceRole.MARKET_TRUTH.value
    blocked = {e["brand"] for e in matrix["oems"]
               if e["official_access_status"] != "REACHABLE"}
    assert blocked, "no blocked OEM in the matrix — assertion would be vacuous"
    seen = {}
    for r in records:
        if r["manufacturer"] in blocked:
            for src in r["sources"]:
                seen.setdefault(r["manufacturer"], set()).add(
                    (src["source_name"], src["source_role"]))
    # the role check must actually have something to look at
    assert seen, "no blocked OEM carries any enumerator evidence — vacuous"
    for e in matrix["oems"]:
        if e["brand"] not in blocked:
            continue
        pairs = seen.get(e["brand"], set())
        if not pairs:
            # zero candidates is only acceptable when the gap is explicit
            assert any(b["layer"] == "identity_enumerator"
                       for b in e["blockers"]), e["brand"]
        else:
            assert all(role != truth for _, role in pairs), (e["brand"], pairs)
            assert all(name in NON_TRUTH_SOURCES for name, _ in pairs), \
                (e["brand"], pairs)
        assert e["identity"]["candidate_sources"] or \
            e["identity"]["model_candidates_discovered"] == 0, e["brand"]
        assert e["identity"]["first_party_confirmed_models"] == 0, e["brand"]
        assert e["identity"]["first_party_confirmed_variants"] == 0, e["brand"]
        assert e["identity"]["first_party_confirmation"] in (
            "NONE_FIRST_PARTY_MISSING", "NO_ENUMERATOR_AND_NO_FIRST_PARTY"), \
            e["brand"]


# ── 7. provenance of the enumerator evidence ────────────────────────────────
def test_enumerator_artifacts_round_trip_through_sidecars():
    sys.path.insert(0, os.path.join(REPO, "lib"))
    from thai_factory.acquisition.provenance import AcquisitionReader
    if not os.path.isdir(ENUM_DIR):
        pytest.skip("no enumerator artifacts captured")
    artifacts = [f for f in os.listdir(ENUM_DIR)
                 if not f.endswith(".prov.json")]
    assert artifacts, "capture log produced no artifacts"
    for name in sorted(artifacts):
        content, prov = AcquisitionReader.read(os.path.join(ENUM_DIR, name))
        assert prov["provenance_state"] == "ACQUISITION_VERIFIED"
        assert prov["session_id"].startswith("p102-")
        assert prov["source_url"].startswith("https://")
        assert len(content) > 500


def test_capture_log_entries_have_provenance(universe):
    for cap in universe["capture_log"]:
        if cap["status"] in ("CAPTURED", "REUSED_VERIFIED"):
            assert cap.get("sha256"), cap
            assert cap.get("captured_at"), cap
        else:
            assert str(cap["status"]).startswith(
                ("BLOCKED", "SKIPPED", "PROVENANCE")), cap


# ── 8. parser behaviour (pure, synthetic — no network) ──────────────────────
def _page(body):
    # a Thai furniture heading: not a model identity, so it never becomes one
    return f"<html><body><h1>รายการราคา</h1>{body}</body></html>"


def test_grade_line_splits_model_and_variant():
    page = _page(
        '<h2><a>TOYOTA FORTUNER ราคา</a></h2>'
        '<p>2.4 Leader G AT ราคา 1,400,000.</p>')
    out = parse_index_page(page, "Toyota", "unit", "https://unit.test/",
                           "MEDIA_DISCOVERY")
    assert [m["model"] for m in out.models] == ["TOYOTA FORTUNER"]
    assert [v["variant"] for v in out.variants] == ["2.4 Leader G AT"]
    assert out.variants[0]["published_price_thb"] == 1400000
    assert out.variants[0]["published_price_role"] == "MEDIA_DISCOVERY"


def test_ru_son_marker_in_a_heading_sets_model_and_grade():
    page = _page("<h2>TOYOTA VELLFIRE รุ่น HEV PREMIUM ราคา</h2>"
                 "<p>ราคา 4,290,000.</p>")
    out = parse_index_page(page, "Toyota", "unit", "https://unit.test/",
                           "MEDIA_DISCOVERY")
    assert [m["model"] for m in out.models] == ["TOYOTA VELLFIRE"]
    assert [v["variant"] for v in out.variants] == ["HEV PREMIUM"]


def test_cross_brand_strong_label_is_rejected_and_context_is_cleared():
    page = _page(
        '<h2><strong>GWM TANK 300 ราคา</strong></h2>'
        '<p><strong>Wuling Binguo ราคา</strong> 369,000.</p>'
        '<p>ULTRA ราคา 1,199,000.</p>')
    out = parse_index_page(page, "GWM", "unit", "https://unit.test/",
                           "MEDIA_DISCOVERY")
    assert [m["model"] for m in out.models] == ["GWM TANK 300"]
    assert [v["variant"] for v in out.variants] == []  # context was cleared
    # the foreign-brand label is recorded with an explicit rejection reason,
    # never dropped silently and never attributed to GWM
    assert any(r["kind"] in ("no_brand_token", "other_brand_contamination")
               for r in out.unresolved)


def test_comment_block_never_becomes_identity():
    page = _page(
        '<h2><strong>MAZDA CX-5 ราคา</strong></h2>'
        '<p>2.0 S 6AT 2WD ราคา 1,499,000.</p>'
        '<div id="comments"><h2>ผู้ใช้รถ CX-9 ราคา 999,999</h2></div>')
    out = parse_index_page(page, "Mazda", "unit", "https://unit.test/",
                           "MEDIA_DISCOVERY")
    assert [m["model"] for m in out.models] == ["MAZDA CX-5"]
    assert not any("CX-9" in m["model"] for m in out.models)


def test_generic_grade_label_is_rejected_with_a_reason():
    page = _page('<h2><strong>MG EP ราคา</strong></h2>'
                 '<p>Standard ราคา 761,000.</p>')
    out = parse_index_page(page, "MG", "unit", "https://unit.test/",
                           "MEDIA_DISCOVERY")
    assert out.variants == []
    assert any(r["kind"] == "generic_variant_rejected" for r in out.unresolved)


def test_furniture_heading_clears_the_model_context():
    assert clean_model_label("TOYOTA 2026-2027 ราคารถ โตโยต้า") is None
    page = _page('<h2>TOYOTA YARIS ราคา</h2><p>1.5 G ราคา 584,000.</p>'
                 '<h2>ดูราคารถแบรนด์อื่นๆ ที่น่าสนใจ</h2>'
                 '<p>Honda Civic ราคา 1,199,000.</p>')
    out = parse_index_page(page, "Toyota", "unit", "https://unit.test/",
                           "MEDIA_DISCOVERY")
    assert not any(leading_brand(v["variant"]) == "Honda"
                   for v in out.variants)


def test_reconciliation_never_confirms_without_market_truth():
    rec = IdentityReconciliation(target_date="unit")
    rec.add_enumerator("Mazda", "CX-5", "2.0 S", {
        "source_name": "unit", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/", "label": "MAZDA CX-5 2.0 S ราคา",
        "identity_level": "VARIANT"})
    rec.resolve_statuses()
    assert rec.records[0].status == FirstPartyStatus.IDENTITY_ONLY.value
    assert rec.confidence["SINGLE_SOURCE"] == 1
    assert rec.confidence["OFFICIAL_VERIFIED"] == 0

    rec.add_first_party("Mazda", "CX-5", "2.0 S", {
        "source_name": "Mazda Thailand Official",
        "source_role": SourceRole.MARKET_TRUTH.value,
        "source_url": "https://www.mazda.co.th/", "label": "CX-5 2.0 S",
        "model": "CX-5", "identity_level": "VARIANT"})
    rec.resolve_statuses()
    assert rec.records[0].status == FirstPartyStatus.CONFIRMED_VARIANT.value
    assert rec.confidence["OFFICIAL_VERIFIED"] == 1


def test_one_shared_source_attributing_a_label_to_two_oems_is_a_conflict():
    """Cross-manufacturer conflict requires provenance disagreement: the SAME
    source must attribute the same identity to two different OEMs."""
    rec = IdentityReconciliation(target_date="unit")
    rec.add_enumerator("Changan", "Lumin", "L DC", {
        "source_name": "shared-source", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/same-page", "label": "ChangAn Lumin L DC",
        "identity_level": "VARIANT"})
    rec.add_enumerator("Deepal", "Lumin", "L DC", {
        "source_name": "shared-source", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/same-page", "label": "Lumin L DC",
        "identity_level": "VARIANT"})
    rec.resolve_statuses()
    statuses = {r.manufacturer: r.status for r in rec.records}
    assert statuses["Changan"] == FirstPartyStatus.CONFLICT.value
    assert statuses["Deepal"] == FirstPartyStatus.CONFLICT.value
    assert all(
        any("shared publication: shared-source "
            "<https://unit.test/same-page>" in y
            for y in r.rejection_reasons) for r in rec.records)


def test_same_source_name_on_different_urls_is_not_a_shared_publication():
    """Publication identity is (source_name, source_url). One enumerator with
    brand-specific pages (e.g. a BMW page and a Suzuki page) must never become
    a cross-manufacturer conflict just because source_name matches."""
    rec = IdentityReconciliation(target_date="unit")
    rec.add_enumerator("Changan", "Lumin", "L DC", {
        "source_name": "one enumerator", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/brand-a", "label": "ChangAn Lumin L DC",
        "identity_level": "VARIANT"})
    rec.add_enumerator("Deepal", "Lumin", "L DC", {
        "source_name": "one enumerator", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/brand-b", "label": "Lumin L DC",
        "identity_level": "VARIANT"})
    rec.resolve_statuses()
    assert {r.status for r in rec.records} == {
        FirstPartyStatus.IDENTITY_ONLY.value}
    assert all(any("legitimate same-name identity" in n for n in r.notes)
               for r in rec.records)
    assert all(not any("shared publication" in y for y in r.rejection_reasons)
               for r in rec.records)


def test_same_label_under_two_oems_from_different_sources_is_not_a_conflict():
    """Two internally-consistent sources naming the same label for their own
    OEM is a legitimate same-name identity — recorded, never merged, never
    accused of disagreement."""
    rec = IdentityReconciliation(target_date="unit")
    rec.add_enumerator("Changan", "Lumin", "L DC", {
        "source_name": "unit-a", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/a", "label": "ChangAn Lumin L DC",
        "identity_level": "VARIANT"})
    rec.add_enumerator("Deepal", "Lumin", "L DC", {
        "source_name": "unit-b", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/b", "label": "Lumin L DC",
        "identity_level": "VARIANT"})
    rec.resolve_statuses()
    assert {r.status for r in rec.records} == {
        FirstPartyStatus.IDENTITY_ONLY.value}
    # still explicit: both records name the other OEM instead of being merged
    assert all(any("legitimate same-name identity" in n for n in r.notes)
               for r in rec.records)
    assert len(rec.records) == 2


def test_declared_level_never_falls_back_to_record_shape():
    """identity_level must be READ, never manufactured from the reconciled
    record's shape (a fallback derived from `variant` is a guess)."""
    dl = IdentityReconciliation.declared_level
    assert dl({"identity_level": "MODEL"}, "") == "MODEL"
    assert dl({"identity_level": "MODEL"}, "Grade One") == "MODEL"
    assert dl({"identity_level": "VARIANT"}, "") == "VARIANT"
    assert dl({"identity_level": "variant"}, "") == "VARIANT"
    # missing / unusable → empty, never MODEL or VARIANT
    assert dl({}, "") == ""
    assert dl({}, "Grade One") == ""
    assert dl({"identity_level": None}, "Grade One") == ""
    assert dl({"identity_level": ""}, "") == ""
    assert dl({"identity_level": "SOMETHING_ELSE"}, "x") == ""
    assert dl({}, "x") not in ("MODEL", "VARIANT")


def test_source_without_identity_level_becomes_no_level_evidence():
    """A publication that declares no level is kept verbatim, listed as
    unlevelled, and must never be counted as MODEL or VARIANT evidence."""
    rec = IdentityReconciliation(target_date="unit")
    rec.add_enumerator("Mazda", "CX-5", "", {
        "source_name": "src-a", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/a", "label": "MAZDA CX-5"})
    rec.add_enumerator("Mazda", "CX-3", "CX-5", {
        "source_name": "src-b", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/b", "label": "CX-3 CX-5"})
    rec.resolve_statuses()
    # entry stays undeclared — the level is NOT guessed from the record shape
    for r in rec.records:
        for entry in r.sources:
            assert entry.get("identity_level") == "", entry
    # and neither publication may manufacture a level clash
    assert {r.status for r in rec.records} == {
        FirstPartyStatus.IDENTITY_ONLY.value}, [
        (r.model, r.variant, r.rejection_reasons) for r in rec.records]
    assert len(rec.unlevelled_publications) == 2, rec.unlevelled_publications
    assert {u["source_name"] for u in rec.unlevelled_publications} == {
        "src-a", "src-b"}
    assert rec.summary()["unlevelled_publications"] == 2
    assert rec.level_clash_evidence == []


def test_variant_only_publication_is_never_model_evidence():
    """A publication may only support the level it actually declares.

    Source `src-b` here appears on a record whose MODEL context is `Alpha`, but
    src-b itself only ever published a VARIANT.  Counting it as MODEL evidence
    manufactures a level clash out of thin air.
    """
    rec = IdentityReconciliation(target_date="unit")
    # src-b publishes VARIANT of Alpha (never Alpha as a model)
    rec.add_enumerator("Mazda", "Alpha", "Grade One", {
        "source_name": "src-b", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/b", "label": "Alpha Grade One",
        "identity_level": "VARIANT"})
    # src-a publishes Alpha as a VARIANT of Beta
    rec.add_enumerator("Mazda", "Beta", "Alpha", {
        "source_name": "src-a", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/a", "label": "Beta Alpha",
        "identity_level": "VARIANT"})
    rec.resolve_statuses()
    assert {r.status for r in rec.records} == {
        FirstPartyStatus.IDENTITY_ONLY.value}, [
        (r.model, r.variant, r.rejection_reasons) for r in rec.records]
    # neither publication is allowed to masquerade as MODEL evidence
    for r in rec.records:
        assert not any("published as a MODEL by one source" in y
                       for y in r.rejection_reasons), r.rejection_reasons
        assert all(s.get("identity_level") in ("MODEL", "VARIANT")
                   for s in r.sources), r.sources


def test_model_only_and_variant_only_publications_are_a_genuine_clash():
    """Source A declared MODEL only + Source B declared VARIANT only, both on
    the same identity key, must still produce a level clash."""
    rec = IdentityReconciliation(target_date="unit")
    rec.add_enumerator("Mazda", "CX-5", "", {
        "source_name": "src-a", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/a", "label": "MAZDA CX-5",
        "identity_level": "MODEL"})
    rec.add_enumerator("Mazda", "CX-3", "CX-5", {
        "source_name": "src-b", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/b", "label": "CX-3 CX-5",
        "identity_level": "VARIANT"})
    rec.resolve_statuses()
    assert {r.status for r in rec.records} == {
        FirstPartyStatus.CONFLICT.value}
    reason = next(y for r in rec.records
                  for y in r.rejection_reasons if "MODEL evidence" in y)
    assert "src-a" in reason and "src-b" in reason
    assert rec.records[0].sources[0].get("identity_level") == "MODEL"
    assert rec.records[1].sources[0].get("identity_level") == "VARIANT"


def test_single_publication_at_both_levels_stays_unresolved_not_conflict():
    """One source publishing an identity at both levels is ambiguous, not a
    source-level disagreement, so it is not labelled a conflict."""
    rec = IdentityReconciliation(target_date="unit")
    src = {"source_name": "unit-a",
           "source_role": SourceRole.MEDIA_DISCOVERY.value,
           "source_url": "https://unit.test/a"}
    rec.add_enumerator("Mazda", "CX-5", "",
                       dict(src, label="MAZDA CX-5", identity_level="MODEL"))
    rec.add_enumerator("Mazda", "MAZDA3", "CX-5",
                       dict(src, label="MAZDA3 CX-5", identity_level="VARIANT"))
    rec.resolve_statuses()
    assert {r.status for r in rec.records} == {
        FirstPartyStatus.IDENTITY_ONLY.value}
    assert all(any("kept unresolved rather than called a conflict" in n
                   for n in r.notes) for r in rec.records)


def test_model_published_as_variant_by_another_source_is_a_conflict():
    rec = IdentityReconciliation(target_date="unit")
    rec.add_enumerator("Mazda", "CX-5", "", {
        "source_name": "unit-a", "source_role": SourceRole.MEDIA_DISCOVERY.value,
        "source_url": "https://unit.test/a", "label": "MAZDA CX-5",
        "identity_level": "MODEL"})
    rec.add_enumerator("Mazda", "MAZDA3", "CX-5", {
        "source_name": "unit-b", "source_role": SourceRole.IDENTITY_ENUMERATOR.value,
        "source_url": "https://unit.test/b", "label": "MAZDA3 CX-5",
        "identity_level": "VARIANT"})
    rec.resolve_statuses()
    assert all(r.status == FirstPartyStatus.CONFLICT.value for r in rec.records)
