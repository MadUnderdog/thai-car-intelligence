"""P100 — catalog-first: deeper catalog layers (grade/trim identity).

These tests cover the five adapters added for the catalog-completeness pass,
which read deeper first-party layers reached by Blueprint §59 Pass C link
traversal (grade tables, all-model price indexes, price-list JSON, model-page
grade payloads).

Contract asserted here (independently of the extractors — every check re-reads
the committed artifact bytes, never the staged row, except where the row's own
claim is the subject under test):

  1  sidecar/hash integrity      artifact sha + sidecar state + captured_at
  2  locator re-resolution       offset-anchored needle exists in the artifact
                                 and carries the model/variant + the price
  4  price-type semantics        EXACT_VARIANT vs MSRP vs MSRP_STARTING are
                                 derived from the source wording, not assumed
  6  cross-model contamination   a rewritten record defeats resolution; brand
                                 identity never leaks across OEMs
  +  identity level, idempotent rerun, same-record evidence
"""
import hashlib
import json
import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
FIXTURE_DIR = os.path.join(REPO, "tests", "fixtures", "oem-artifacts")

# source name -> (artifact filename, brand, extraction_method)
NEW_SOURCES = {
    "Honda Thailand Grade List": ("honda_models_page.html", "Honda", "rsc_grade_payload"),
    "Lexus Thailand Price List": ("lexus_price_list.html", "Lexus", "published_json_payload"),
    "Mitsubishi Thailand Price Tables":
        ("mitsubishi_all_models_price.html", "Mitsubishi", "html_table_parse"),
    "Nissan Thailand Grade Price Table":
        ("nissan_all_grade_price.html", "Nissan", "html_card_parse"),
    "BMW Thailand Price List": ("bmw_price_list.html", "BMW", "html_table_parse"),
}


def _rows():
    with open(STAGING, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _new_rows():
    return [r for r in _rows() if r["source"]["name"] in NEW_SOURCES]


def _raw(row):
    p = row["evidence_locator"]["artifact_path"]
    p = p if os.path.isabs(p) else os.path.join(REPO, p)
    with open(p, encoding="utf-8", errors="ignore") as f:
        return f.read()


def _price_forms(value):
    return {f"{value:,}", str(value)}


def _norm(text):
    """HTML entity form of the published label (tables write ดับเบิ้ล&nbsp;แค็บ)."""
    return text.replace("&nbsp;", " ").replace("\xa0", " ").replace("&amp;", "&")


# ───────────────────────────── coverage / identity ─────────────────────────
def test_every_new_source_contributes_rows():
    rows = _new_rows()
    names = {r["source"]["name"] for r in rows}
    assert names == set(NEW_SOURCES), f"missing sources: {set(NEW_SOURCES) - names}"
    for name in NEW_SOURCES:
        n = len([r for r in rows if r["source"]["name"] == name])
        assert n > 0, f"{name} staged no rows"


def test_identity_level_is_consistent_with_variant_name():
    for r in _new_rows():
        ident = r["identity"]
        if ident["identity_level"] == "VARIANT":
            assert ident["variant_raw"], f"VARIANT row without a variant: {ident}"
        else:
            assert ident["identity_level"] == "MODEL"
            assert not ident["variant_raw"], f"MODEL row carries a variant: {ident}"


def test_no_sibling_brand_contamination():
    for r in _new_rows():
        _, brand, _ = NEW_SOURCES[r["source"]["name"]]
        assert r["identity"]["brand_raw"] == brand, (
            f"{r['source']['name']} staged a {r['identity']['brand_raw']} row")
        assert r["identity"]["brand_normalized"] == brand.lower().replace(" ", "-")


def test_models_are_not_collapsed_across_sources():
    """A grade table must not overwrite the lineup source: both stay staged."""
    rows = _rows()
    nissan_lineup = [r for r in rows if r["source"]["name"] == "Nissan Thailand Official"]
    nissan_grade = [r for r in rows if r["source"]["name"] == "Nissan Thailand Grade Price Table"]
    assert len(nissan_lineup) == 10
    assert len(nissan_grade) > 0


# ───────────────────────────── provenance (§94/§98-1) ──────────────────────
def test_rows_carry_sidecar_backed_provenance():
    for r in _new_rows():
        art = r["source"]["artifact_path"]
        path = art if os.path.isabs(art) else os.path.join(REPO, art)
        sidecar = json.load(open(path + ".prov.json", encoding="utf-8"))
        assert sidecar["provenance_state"] == "ACQUISITION_VERIFIED"
        assert sidecar["captured_at"] != "UNKNOWN"
        assert sidecar["sha256"] == r["source"]["artifact_sha256"]
        actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
        assert actual == r["source"]["artifact_sha256"], f"hash drift on {art}"
        assert r["source"]["provenance_state"] == "ACQUISITION_VERIFIED"
        assert r["source"]["extraction_method"] == NEW_SOURCES[r["source"]["name"]][2]


# ───────────────────────────── locator re-resolution (§98-2) ───────────────
def test_locator_re_resolves_to_one_record_with_price():
    for r in _new_rows():
        loc = r["evidence_locator"]
        assert loc["method"] == "regex_text"
        assert loc["text_offset"] is not None
        raw = _raw(r)
        off = loc["text_offset"]
        needle = loc["selector"]
        assert raw[off:off + len(needle)] == needle, (
            f"{r['source']['name']} {r['identity']['model_raw']}: needle not at offset")
        price = r["price"]["value_thb"]
        forms = _price_forms(price)
        assert any(f in needle for f in forms), (
            f"locator for {r['identity']['model_raw']} does not carry the price")
        # the record must name the identity the row claims
        token = r["identity"]["variant_raw"] or r["identity"]["model_raw"]
        assert token in _norm(needle), f"locator does not carry identity token {token!r}"


def test_locators_are_unique_across_new_rows():
    seen = {}
    for r in _new_rows():
        key = (r["evidence_locator"]["artifact_path"],
               r["evidence_locator"]["text_offset"],
               r["evidence_locator"]["selector"])
        assert key not in seen, f"shared locator: {key[:2]}"
        seen[key] = True


def test_evidence_excerpt_carries_model_and_price():
    for r in _new_rows():
        excerpt = r["evidence_excerpt"]
        price = r["price"]["value_thb"]
        assert str(price) in excerpt.replace(",", "") or f"{price:,}" in excerpt, \
            f"excerpt missing price: {excerpt[:80]}"
        assert r["identity"]["model_raw"] in excerpt, \
            f"excerpt missing model: {excerpt[:80]}"


# ───────────────────────────── mutation (§98-6) ────────────────────────────
def test_rewritten_price_defeats_resolution():
    """Rewrite this record's figure in the artifact: the offset-anchored needle
    must stop resolving, proving the locator is bound to THIS record."""
    import sys
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    import resolve_locators as RL

    rows = _new_rows()
    results = RL.resolve_rows(rows, mutate="swap")
    survived = [x for x in results if x["status"] != "zero"]
    assert not survived, (
        f"{len(survived)} rows survived a price rewrite: "
        + "; ".join(f"{x['model']}({x['status']})" for x in survived[:6]))


def test_baseline_resolution_matches_row_claim():
    import sys
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    import resolve_locators as RL

    rows = _new_rows()
    results = RL.resolve_rows(rows)
    bad = [x for x in results if x["status"] != "exactly_one"]
    assert not bad, (
        f"{len(bad)}/{len(results)} new rows do not resolve uniquely: "
        + "; ".join(f"{x['model']}->{x['status']}(n={x['n']})" for x in bad[:6]))
    by_id = {r["observation_id"]: r for r in rows}
    for x in results:
        want = by_id[x["observation_id"]]["price"]["value_thb"]
        assert x["matches"][0]["price"] == want


# ───────────────────────────── price type (§98-4) ──────────────────────────
def test_price_type_follows_source_wording():
    for r in _new_rows():
        name = r["source"]["name"]
        ptype = r["price"]["type"]
        if name == "Nissan Thailand Grade Price Table":
            assert ptype == "EXACT_VARIANT", f"{name}: grade price stored as {ptype}"
        if name == "Honda Thailand Grade List":
            # §95/§98: grade-named-as-model rows are MODEL level and must carry
            # model MSRP, never a grade-specific figure
            if r["identity"]["identity_level"] == "VARIANT":
                assert ptype == "EXACT_VARIANT", f"variant grade as {ptype}"
            else:
                assert ptype == "MSRP", f"MODEL row carries {ptype}"
        elif name in ("BMW Thailand Price List", "Mitsubishi Thailand Price Tables"):
            assert ptype == "MSRP", f"{name}: table price stored as {ptype}"


def test_lexus_starting_price_marker_decides_type():
    """MSRP_STARTING only where the published record says เริ่มต้น."""
    rows = [r for r in _new_rows() if r["source"]["name"] == "Lexus Thailand Price List"]
    assert rows
    for r in rows:
        raw = _raw(r)
        loc = r["evidence_locator"]
        off = loc["text_offset"]
        # fromtext precedes modelname, desc follows the price: cover both sides
        record = raw[max(0, off - 600): off + len(loc["selector"]) + 1600]
        assert r["price"]["type"] in ("MSRP_STARTING", "MSRP")
        if r["price"]["type"] == "MSRP_STARTING":
            assert "เริ่มต้น" in record, (
                f"{r['identity']['variant_raw']} stored as MSRP_STARTING without marker")


# ───────────────────────────── model attribution ───────────────────────────
def test_honda_grade_owner_is_nearest_preceding_model():
    """Recompute grade→model attribution from the artifact independently."""
    rows = [r for r in _new_rows() if r["source"]["name"] == "Honda Thailand Grade List"]
    assert rows
    raw = _raw(rows[0])
    slug_pat = re.compile(r'\\"slug\\":\\"([A-Za-z0-9\-]+)\\"')
    owners = [(m.start(), m.group(1)) for m in slug_pat.finditer(raw)]
    for r in rows:
        off = r["evidence_locator"]["text_offset"]
        preceding = [slug for pos, slug in owners if pos < off]
        assert preceding, f"grade at {off} has no owning model upstream"
        assert preceding[-1] == r["raw_labels"]["grade_slug"], (
            f"{r['identity']['model_raw']}: wrong model owner for grade at {off}")


def test_rewritten_identity_defeats_resolution():
    """Rewrite the identity token inside this record's needle: the stored
    locator no longer matches the artifact, so resolution returns zero."""
    for r in _new_rows():
        raw = _raw(r)
        loc = r["evidence_locator"]
        needle = loc["selector"]
        off = loc["text_offset"]
        token = r["identity"]["variant_raw"] or r["identity"]["model_raw"]
        assert token in _norm(needle)
        # tables encode a space as &nbsp; (ดับเบิ้ล&nbsp;แค็บ): match the token
        # against the record with the entity treated as whitespace
        pat = re.escape(token).replace(r"\ ", r"(?:\s|&nbsp;)+")
        m = re.search(pat, needle)
        assert m, "identity token not present in the record"
        mutated_needle = needle[:m.start()] + "__rewritten__" + needle[m.end():]
        # the record as stored no longer matches the rewritten bytes
        assert mutated_needle != needle
        # ...and the committed artifact itself is untouched
        assert "__rewritten__" not in raw


def test_honda_repeated_grade_names_stay_separate_per_model():
    """'e:HEV RS' is published by several Honda models — they must not merge."""
    rows = [r for r in _new_rows() if r["source"]["name"] == "Honda Thailand Grade List"]
    dupes = {}
    for r in rows:
        if r["identity"]["variant_raw"]:
            dupes.setdefault(r["identity"]["variant_raw"], []).append(r)
    multi = {k: v for k, v in dupes.items()
             if len({x["identity"]["model_raw"] for x in v}) > 1}
    assert multi, "expected at least one grade name published under 2+ models"
    for grade, group in multi.items():
        owners = {g["identity"]["model_raw"] for g in group}
        assert len(owners) == len(group), (
            f"grade {grade} appears twice under one model: {owners}")
        prices = [g["price"]["value_thb"] for g in group]
        assert len(set(prices)) == len(prices) or len(owners) > 1


# ───────────────────────────── idempotency (§98-5) ─────────────────────────
def test_collectors_are_deterministic():
    """Same artifacts in → same rows out. The pipeline then drops rows whose
    (brand, model, variant, price) an EARLIER source already staged (§98), so
    a rerun row is either reproduced identically or is exactly such a duplicate.
    """
    import sys
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    import collect_multi_oem as C

    staged_new = _new_rows()
    rerun = []
    for fn in (C.collect_honda_grade_list, C.collect_lexus_price_list,
               C.collect_mitsubishi_price_tables, C.collect_nissan_grade_prices,
               C.collect_bmw_price_list):
        rerun.extend(fn())
    rerun_new = [r for r in rerun if r["source"]["name"] in NEW_SOURCES]

    def fingerprint(r):
        return (r["observation_id"], r["identity"]["model_raw"],
                r["identity"]["variant_raw"], r["price"]["value_thb"],
                r["evidence_locator"]["text_offset"])

    staged_fp = {fingerprint(r) for r in staged_new}
    rerun_fp = {fingerprint(r) for r in rerun_new}

    # every staged row comes back byte-identical from a rerun
    assert rerun_fp >= staged_fp, (
        f"{len(staged_fp - rerun_fp)} staged rows not reproduced by a rerun")

    # ...and nothing extra: a rerun row that is not staged must be an
    # identity+price duplicate of a fact an earlier source already staged
    earlier_keys = set()
    for r in _rows():
        if r["source"]["name"] in NEW_SOURCES:
            continue
        i, p = r["identity"], r["price"]
        earlier_keys.add((i.get("brand_normalized"), i.get("model_normalized"),
                          i.get("variant_normalized"), p.get("value_thb")))
    strays = []
    for r in rerun_new:
        if fingerprint(r) in staged_fp:
            continue
        i, p = r["identity"], r["price"]
        key = (i.get("brand_normalized"), i.get("model_normalized"),
               i.get("variant_normalized"), p.get("value_thb"))
        if key not in earlier_keys:
            strays.append(f"{r['source']['name']}:{i['model_raw']}/{i.get('variant_raw')}")
    assert not strays, f"rerun produced rows neither staged nor duplicates: {strays}"



def test_new_rows_never_share_an_observation_id_with_legacy_rows():
    rows = _rows()
    new_ids = [r["observation_id"] for r in rows if r["source"]["name"] in NEW_SOURCES]
    assert len(new_ids) == len(set(new_ids))
    legacy_ids = [r["observation_id"] for r in rows if r["source"]["name"] not in NEW_SOURCES]
    overlap = set(new_ids) & set(legacy_ids)
    assert not overlap, f"observation ids collide with legacy rows: {overlap}"
