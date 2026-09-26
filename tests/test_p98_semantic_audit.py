"""P98 semantic audit + multi-source assembly invariants.

Every check recomputes from `audit/data-staging/vehicle_observations.jsonl` —
nothing is asserted from a stored summary, so a stale report cannot mask a defect.
"""
import collections
import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
JOINS = os.path.join(REPO, "audit", "data-staging", "multi_source_joins.json")


def _rows():
    with open(STAGING, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _ev(r):
    if r.get("evidence_excerpt"):
        return r["evidence_excerpt"]
    return (r.get("evidence") or {}).get("excerpt") or ""


def _lvl(r):
    return r["identity"].get("identity_level") or r["identity"].get("level")


def _pt(r):
    return r["price"].get("type") or r["price"].get("price_type")


def _loc(r):
    if r.get("evidence_locator"):
        return r["evidence_locator"]
    return (r.get("evidence") or {}).get("evidence_locator") or {}


def _oid(r):
    return r.get("observation_id") or f"{r['source']['name']}/{r['identity']['model_raw']}"


# ─── schema completeness (12 rows used a reduced shape before P98) ───

def test_every_row_carries_full_identity_and_evidence():
    for r in _rows():
        oid = _oid(r)
        for f in ("brand_normalized", "model_normalized"):
            assert f in r["identity"], f"{oid} missing identity.{f}"
        for f in ("observation_id", "evidence_excerpt", "evidence_locator",
                  "timestamp", "specs", "raw_labels"):
            assert f in r, f"{oid} missing top-level {f}"
        assert _loc(r), f"{oid} has no locator"


# ─── cross-record contamination (all must be zero) ───

def test_no_cross_model_evidence_contamination():
    rows = _rows()
    models = {r["identity"]["model_raw"] for r in rows}
    bad = []
    for r in rows:
        own = r["identity"]["model_raw"]
        ev_up = _ev(r).upper()
        if own.upper() in ev_up:
            continue
        others = [m for m in models if m and m != own and len(m) > 3
                  and re.search(r"\b" + re.escape(m.upper()) + r"\b", ev_up)]
        if others:
            bad.append((_oid(r), own, others[:3]))
    assert not bad, f"cross-model contamination: {bad[:5]}"


def test_no_cross_variant_evidence_contamination():
    rows = _rows()
    variants = {r["identity"]["variant_raw"] for r in rows if r["identity"].get("variant_raw")}
    bad = []
    for r in rows:
        var = r["identity"].get("variant_raw")
        if not var:
            continue
        ev = _ev(r)
        if var in ev:
            continue
        sib = [v for v in variants if v != var and len(v) > 3
               and re.search(r"\b" + re.escape(v) + r"\b", ev)]
        if sib:
            bad.append((_oid(r), var, sib[:3]))
    assert not bad, f"cross-variant contamination: {bad[:5]}"


def test_no_duplicate_identity_price_records():
    seen = collections.defaultdict(list)
    for r in _rows():
        i = r["identity"]
        key = (i.get("brand_normalized"), i.get("model_normalized"),
               i.get("variant_normalized"), r["price"]["value_thb"])
        seen[key].append(_oid(r))
    dupes = {k: v for k, v in seen.items() if len(v) > 1}
    assert not dupes, f"duplicate identity+price records: {dupes}"


def test_no_empty_or_media_style_evidence():
    junk = ("watch", "video", "gallery", "newsletter", "sign in", "cookie")
    for r in _rows():
        ev = _ev(r)
        assert ev.strip(), f"{_oid(r)} has empty evidence"
        assert len(ev) <= 400, f"{_oid(r)} evidence too long ({len(ev)})"
        low = ev.lower()
        assert not any(j in low for j in junk), f"{_oid(r)} evidence looks like nav/media: {ev[:80]}"
        # at most one price number should appear in a card excerpt
        prices = re.findall(r"[\d,]{5,}", ev.replace(",", ""))
        assert len(prices) <= 2, f"{_oid(r)} evidence carries multiple price figures: {ev[:90]}"


# ─── identity / price-type strictness (MODEL vs VARIANT, MSRP vs STARTING vs EXACT) ───

def test_model_level_rows_never_carry_exact_variant_price():
    bad = [(_oid(r), r["identity"]["model_raw"], _pt(r))
           for r in _rows() if _lvl(r) == "MODEL" and _pt(r) == "EXACT_VARIANT"]
    assert not bad, f"MODEL-level row with EXACT_VARIANT price: {bad}"


def test_variant_level_rows_always_name_the_variant():
    bad = [_oid(r) for r in _rows()
           if _lvl(r) == "VARIANT" and not r["identity"].get("variant_raw")]
    assert not bad, f"VARIANT-level row without a variant name: {bad}"


def test_msrp_starting_rows_have_starting_marker_evidence():
    """MSRP_STARTING must be backed by a starting marker in the artifact or the excerpt."""
    markers = re.compile(r"เริ่มต้น|starting|\bfrom\b|\*\*", re.I)
    bad = []
    for r in _rows():
        if _pt(r) != "MSRP_STARTING":
            continue
        art = r["source"].get("artifact_path")
        p = art if os.path.isabs(art) else os.path.join(REPO, art or "")
        in_art = bool(markers.search(open(p, encoding="utf-8", errors="ignore").read())) \
            if os.path.exists(p) else False
        if not in_art and not markers.search(_ev(r)):
            bad.append((_oid(r), r["identity"]["model_raw"]))
    assert not bad, f"MSRP_STARTING without any starting marker: {bad[:5]}"


# ─── currentness ───

def test_currentness_values_are_bounded_and_typed():
    allowed = {None, "UNKNOWN", "CURRENT"}
    for r in _rows():
        cur = r["price"].get("currentness")
        assert cur in allowed, f"{_oid(r)} unexpected currentness {cur!r}"
        if cur == "CURRENT":
            # must be anchored to a dated, verified acquisition record
            assert r["source"].get("captured_at") not in (None, "UNKNOWN"), \
                f"{_oid(r)} claims CURRENT without a capture date"
            assert r["source"].get("provenance_state") == "ACQUISITION_VERIFIED", \
                f"{_oid(r)} claims CURRENT without VERIFIED provenance"


# ─── provenance ───

def test_all_staged_rows_are_provenance_verified():
    for r in _rows():
        assert r["source"]["provenance_state"] == "ACQUISITION_VERIFIED", \
            f"{_oid(r)} still {r['source']['provenance_state']}"
        assert r["source"]["captured_at"] != "UNKNOWN"


# ─── multi-source assembly ───

def test_joins_artifact_recomputes_exactly():
    """The stored joins must be reproducible from staging — no hand-written joins."""
    stored = json.load(open(JOINS, encoding="utf-8"))
    rows = _rows()
    g = collections.defaultdict(list)
    for r in rows:
        i = r["identity"]
        g[(i.get("brand_normalized"), i.get("model_normalized"),
           r["price"]["value_thb"])].append(r)
    expected = sorted(
        list(k) for k, v in g.items()
        if len({m["source"]["artifact_path"] for m in v}) >= 2)
    stored_keys = sorted([list(j["join_key"].values()) for j in stored["joins"]])
    assert stored_keys == expected, f"stored joins {stored_keys} != recomputed {expected}"
    assert stored["join_count"] == len(expected)


def test_each_join_has_two_verified_artifacts_and_agreeing_price():
    stored = json.load(open(JOINS, encoding="utf-8"))
    for j in stored["joins"]:
        recs = j["supporting_records"]
        assert len(recs) >= 2, j["join_key"]
        arts = {r["artifact_path"] for r in recs}
        assert len(arts) >= 2, f"join not cross-artifact: {arts}"
        assert len({r["price_thb"] for r in recs}) == 1, "join price disagreement"
        for r in recs:
            assert r["provenance_state"] == "ACQUISITION_VERIFIED"
            assert r["source_class"] == "OEM_OFFICIAL"
            assert r["evidence_excerpt"].strip(), "join record lacks evidence"


def test_no_join_is_invented_from_a_single_artifact():
    stored = json.load(open(JOINS, encoding="utf-8"))
    assert stored["join_count"] <= len(stored["joins"])
    # every claimed support record must actually exist in staging with that price
    rows = {(r.get("observation_id"), r["price"]["value_thb"]) for r in _rows()}
    for j in stored["joins"]:
        for rec in j["supporting_records"]:
            assert (rec["observation_id"], rec["price_thb"]) in rows, \
                f"join cites a record not in staging: {rec['observation_id']}"


# ─── spec observations ───

def test_no_placeholder_spec_values():
    placeholders = {"", "tbd", "todo", "null", "none", "n/a", "na", "-", "unknown",
                    "test", "placeholder"}
    bad = []
    for r in _rows():
        for k, v in (r.get("specs") or {}).items():
            if str(v).strip().lower() in placeholders:
                bad.append((_oid(r), k, v))
    assert not bad, f"placeholder spec values: {bad[:5]}"


def test_spec_records_are_not_duplicated_within_one_brand_model():
    """Identical spec payloads are only acceptable for distinct variants."""
    seen = collections.defaultdict(list)
    for r in _rows():
        if not r.get("specs"):
            continue
        i = r["identity"]
        seen[(i.get("brand_normalized"), i.get("model_normalized"),
               json.dumps(r["specs"], sort_keys=True))].append(
            (i.get("variant_normalized"), _oid(r)))
    dupes = {}
    for k, v in seen.items():
        variants = {x[0] for x in v}
        if len(v) > 1 and len(variants) == 1:
            dupes[k] = v
    assert not dupes, f"same brand+model+specs repeated for one variant: {dupes}"
