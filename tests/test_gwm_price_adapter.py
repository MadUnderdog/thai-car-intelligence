"""GWM Thailand — Phase 1 coverage wave.

GWM publishes no figure on its homepage, /en/models, /gwm-data-models or
mall.gwm.co.th (all captured, all price-free). The figures live on the 13
server-rendered /th/models/<slug> pages discovered through gwm.co.th's own
sitemap index. What this file locks down:

  * artifacts are capture-time verified (AcquisitionWriter sidecars);
  * every row is bound to the record that carries it, by re-resolution from
    the artifact bytes in a real browser — never from the staged row;
  * MODEL vs VARIANT and MSRP vs MSRP_STARTING vs EXACT_VARIANT stay strict;
  * campaign-derived figures are REJECTED with a reason, never typed;
  * price-free GWM artifacts still stage nothing.
"""
import collections
import hashlib
import json
import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO, "tests", "fixtures", "oem-artifacts")
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
REGISTRY = os.path.join(REPO, "audit", "coverage", "oem-registry.json")
CANDIDATES = os.path.join(REPO, "audit", "coverage", "gwm_price_candidates_20260925.json")

import sys
if os.path.join(REPO, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "scripts"))
from collect_multi_oem import collect_gwm_prices, parse_gwm_page  # noqa: E402


def _gwm_artifacts():
    return sorted(f for f in os.listdir(FIXTURE_DIR)
                  if f.startswith("gwm_th_model_") and f.endswith(".html"))


def _rows():
    with open(STAGING, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _gwm_rows():
    return [r for r in _rows() if r["source"]["name"] == "GWM Thailand Official"]


def _loc(r):
    return r["evidence_locator"]


# ─────────────────────────── acquisition ───────────────────────────

def test_thirteen_model_pages_captured_with_verifying_sidecars():
    arts = _gwm_artifacts()
    assert len(arts) == 13, f"expected the 13 sitemap model pages, got {len(arts)}"
    for fn in arts:
        path = os.path.join(FIXTURE_DIR, fn)
        sc = json.load(open(path + ".prov.json", encoding="utf-8"))
        assert sc["provenance_state"] == "ACQUISITION_VERIFIED", fn
        assert sc["captured_at"] != "UNKNOWN", fn
        assert sc["source_url"].startswith("https://www.gwm.co.th/th/models/"), sc["source_url"]
        # the bytes on disk must reproduce the capture-time hash exactly
        assert sc["sha256"] == hashlib.sha256(open(path, "rb").read()).hexdigest(), fn


def test_gwm_rows_stage_from_the_captured_artifacts_only():
    for r in _gwm_rows():
        art = r["source"]["artifact_path"]
        assert os.path.basename(art).startswith("gwm_th_model_"), art
        assert r["source"]["provenance_state"] == "ACQUISITION_VERIFIED"
        assert r["source"]["captured_at"] != "UNKNOWN"
        assert r["source"]["artifact_sha256"] == hashlib.sha256(
            open(os.path.join(REPO, art), "rb").read()).hexdigest()


def test_gwm_staging_matches_the_adapter():
    staged = _gwm_rows()
    produced = collect_gwm_prices()
    assert len(staged) == len(produced), (
        f"staging holds {len(staged)} GWM rows but the adapter produces {len(produced)}")
    assert len(staged) >= 25


# ─────────────────────────── price-type strictness ───────────────────────────

def test_model_and_variant_levels_never_mix():
    for r in _gwm_rows():
        lvl = r["identity"]["identity_level"]
        ptype = r["price"]["type"]
        if lvl == "MODEL":
            assert r["identity"]["variant_raw"] is None, r["observation_id"]
            assert ptype in ("MSRP", "MSRP_STARTING"), (r["observation_id"], ptype)
        else:
            assert lvl == "VARIANT", lvl
            assert r["identity"]["variant_raw"], r["observation_id"]
            assert ptype == "EXACT_VARIANT", (r["observation_id"], ptype)


def test_starting_rows_carry_the_starting_marker():
    """MSRP_STARTING is only ever emitted for a figure the page labels ราคาเริ่มต้น."""
    marker = re.compile(r"เริ่มต้น")
    for r in _gwm_rows():
        if r["price"]["type"] != "MSRP_STARTING":
            continue
        assert marker.search(r["raw_labels"]["raw_source_text"]), r["observation_id"]
        assert marker.search(r["evidence_excerpt"]), r["observation_id"]
        art = os.path.join(REPO, r["source"]["artifact_path"])
        assert marker.search(open(art, encoding="utf-8").read()), art
    starting = [r for r in _gwm_rows() if r["price"]["type"] == "MSRP_STARTING"]
    assert len(starting) >= 2


def test_msrp_rows_are_labelled_msrp_or_bare_not_promo():
    for r in _gwm_rows():
        if r["price"]["type"] != "MSRP":
            continue
        label = r["raw_labels"]["price_label"]
        assert label in ("MSRP", "unlabeled"), (r["observation_id"], label)


def test_every_staged_price_is_a_published_configurator_price():
    """No staged figure may be a campaign-only number: the configurator on the
    same artifact must publish it as a configuration price."""
    for r in _gwm_rows():
        art = os.path.join(REPO, r["source"]["artifact_path"])
        raw = open(art, encoding="utf-8").read()
        figures = {int(x.replace(",", ""))
                   for x in re.findall(r"฿\s*([\d,]+)", raw)}
        assert r["price"]["value_thb"] in figures, (
            f"{r['identity']['model_raw']} staged {r['price']['value_thb']} but the "
            f"configurator on {os.path.basename(art)} publishes only {sorted(figures)}")


# ─────────────────────────── identity ───────────────────────────

def test_brand_identity_is_gwm_own_domain():
    """Every GWM row is published on gwm.co.th itself — no sibling-brand source
    (Deepal/Changan/Haval domains) is ever cited."""
    for r in _gwm_rows():
        assert r["identity"]["brand_raw"] == "GWM"
        assert r["identity"]["brand_normalized"] == "gwm"
        sc = json.load(open(os.path.join(REPO, r["source"]["artifact_path"]) + ".prov.json",
                            encoding="utf-8"))
        assert sc["source_url"].startswith("https://www.gwm.co.th/"), sc["source_url"]
        assert r["source"]["url"].startswith("https://www.gwm.co.th/")
        for foreign in ("changan.co.th", "thdeepal", "haval.co.th"):
            assert foreign not in r["source"]["artifact_path"]


def test_models_are_the_pages_own_published_titles():
    for r in _gwm_rows():
        art = os.path.join(REPO, r["source"]["artifact_path"])
        raw = open(art, encoding="utf-8").read()
        assert r["identity"]["model_raw"] in raw, (
            f"{r['identity']['model_raw']} not published by {os.path.basename(art)}")


def test_no_duplicate_identity_price():
    seen = collections.defaultdict(list)
    for r in _gwm_rows():
        i = r["identity"]
        seen[(i["model_normalized"], i["variant_normalized"],
              r["price"]["value_thb"])].append(r["observation_id"])
    dupes = {k: v for k, v in seen.items() if len(v) > 1}
    assert not dupes, dupes


# ─────────────────────────── evidence + locator re-resolution ───────────────────────────

def test_evidence_is_traceable_to_its_own_artifact():
    """VARIANT evidence is a verbatim source slice; MODEL evidence is the page's
    own published title plus the hero span's text, which must be recoverable
    from that page's price block once markup is stripped."""
    for r in _gwm_rows():
        raw = open(os.path.join(REPO, r["source"]["artifact_path"]), encoding="utf-8").read()
        ev = r["evidence_excerpt"]
        loc = _loc(r)
        if loc["method"] == "regex_text":
            assert ev in raw, (
                f"{r['identity']['model_raw']}: evidence is not verbatim source text")
            off = loc["text_offset"]
            needle = loc["selector"]
            assert raw[off:off + len(needle)] == needle, (
                f"{r['identity']['model_raw']}: needle does not sit at the recorded offset")
            continue

        parts = [p.strip() for p in ev.split("|")]
        assert parts[0] == r["identity"]["model_raw"], ev
        block = re.search(r'<div class="desc[^"]*">(.*?)</div>', raw, re.S)
        assert block, r["identity"]["model_raw"]
        plain = " ".join(re.sub(r"<[^>]+>", " ", block.group(1)).split())
        for part in parts[1:]:
            assert part and part in plain, (
                f"{r['identity']['model_raw']}: {part!r} not found in the artifact's "
                f"price block ({plain[:160]!r})")


def test_every_gwm_row_resolves_to_exactly_one_record():
    """Re-resolution runs from the artifact bytes in Chromium — same engine the
    repo-wide locator audit uses."""
    import resolve_locators as RL
    rows = _gwm_rows()
    assert rows
    res = RL.resolve_rows(rows)
    bad = [b for b in res if b["status"] != "exactly_one"]
    assert not bad, "; ".join(
        f"{b['model']}/{b['variant']} -> {b['status']} n={b['n']} {b['detail']}" for b in bad)


def test_price_swap_defeats_every_gwm_row():
    """Rewrite this record's figure: the locator must stop resolving, and the
    number must still be published elsewhere, so the check is not vacuous."""
    import resolve_locators as RL
    rows = _gwm_rows()
    res = RL.resolve_rows(rows, mutate="swap")
    survived = [x for x in res if x["status"] != "zero"]
    assert not survived, "; ".join(
        f"{x['model']}/{x['variant']} -> {x['status']}" for x in survived[:8])
    dom = [x for x in res if x["method"] in ("dom_card", "dom_query", "playwright_dom")]
    assert dom, "expected DOM-bound GWM rows"
    missing = [x for x in dom if "price_present_after=True" not in str(x["detail"])]
    assert not missing, [x["model"] for x in missing]


def test_delete_never_lands_on_another_gwm_model():
    import resolve_locators as RL
    per_model = {}
    for r in _gwm_rows():
        per_model.setdefault((r["identity"]["model_raw"], _loc(r)["method"]), r)
    sample = list(per_model.values())
    assert len(sample) >= 10
    res = RL.resolve_rows(sample, mutate="delete")
    for x in res:
        assert x["status"] in ("zero", "exactly_one"), (x["model"], x["status"])
        if x["status"] == "exactly_one":
            assert x["matches"][0]["price"] == \
                next(r for r in sample if r["observation_id"] == x["observation_id"])[
                    "price"]["value_thb"]


def test_locators_are_unique_across_the_gwm_rows():
    buckets = collections.defaultdict(list)
    for r in _gwm_rows():
        buckets[json.dumps(_loc(r), sort_keys=True, ensure_ascii=False)].append(
            r["identity"]["model_raw"])
    dupes = {k[:60]: v for k, v in buckets.items() if len(v) > 1}
    assert not dupes, dupes
    paths = [v for r in _gwm_rows() for k, v in _loc(r).items() if k in ("dom_path", "canonical_locator")]
    assert len(paths) == len(set(paths)), "GWM dom_path reused across rows"
    assert paths, "GWM model rows must carry a DOM locator"


# ─────────────────────────── rejections: nothing dropped silently ───────────────────────────

def _desc_figures(raw):
    m = re.search(r'<div class="desc[^"]*">(.*?)</div>', raw, re.S)
    if not m:
        return []
    out = []
    for tok in re.findall(r"[\d][\d,]{4,}", m.group(1)):
        v = int(tok.replace(",", ""))
        if v >= 100_000:
            out.append(v)
    return out


def test_rejection_log_exists_and_names_a_reason():
    log = json.load(open(CANDIDATES, encoding="utf-8"))
    assert log["brand"] == "GWM"
    assert log["rejected_candidates"], "expected campaign-derived figures to be rejected"
    for c in log["rejected_candidates"]:
        assert c["reason"], c
        assert c["value_thb"] and c["model"] and c["artifact"]


def test_every_hero_figure_is_staged_or_explicitly_rejected():
    """Completeness: a figure the page publishes may not simply go missing."""
    log = json.load(open(CANDIDATES, encoding="utf-8"))
    rejected = {(os.path.basename(c["artifact"]), c["value_thb"])
                for c in log["rejected_candidates"]}
    staged = {(os.path.basename(r["source"]["artifact_path"]), r["price"]["value_thb"])
              for r in _gwm_rows() if r["identity"]["identity_level"] == "MODEL"}
    missing = []
    for fn in _gwm_artifacts():
        raw = open(os.path.join(FIXTURE_DIR, fn), encoding="utf-8").read()
        for v in set(_desc_figures(raw)):
            if (fn, v) not in staged and (fn, v) not in rejected:
                missing.append((fn, v))
    assert not missing, f"hero figures neither staged nor rejected: {missing}"


def test_rejected_figures_are_never_staged():
    log = json.load(open(CANDIDATES, encoding="utf-8"))
    staged = {(os.path.basename(r["source"]["artifact_path"]), r["price"]["value_thb"])
              for r in _gwm_rows()}
    leak = [(os.path.basename(c["artifact"]), c["value_thb"])
            for c in log["rejected_candidates"]
            if (os.path.basename(c["artifact"]), c["value_thb"]) in staged]
    assert not leak, f"campaign-derived figure staged anyway: {leak}"


# ─────────────────────────── price-free artifacts stay price-free ───────────────────────────

@pytest.mark.parametrize("fn", ["gwm_home_page.html", "gwm_models_page.html",
                                "gwm_data_models_page.html", "gwm_mall_home.html"])
def test_price_free_gwm_artifacts_stage_nothing(fn):
    path = os.path.join(FIXTURE_DIR, fn)
    assert os.path.exists(path), fn
    sc = json.load(open(path + ".prov.json", encoding="utf-8"))
    assert sc["provenance_state"] == "ACQUISITION_VERIFIED", fn
    raw = open(path, encoding="utf-8").read()
    rows, rejected = parse_gwm_page(raw, f"tests/fixtures/oem-artifacts/{fn}", "x", sc)
    assert rows == [], f"{fn} has no price block yet produced {len(rows)} rows"
    assert rejected == []
    for line in open(STAGING, encoding="utf-8"):
        assert fn not in line, f"{fn} leaked into staging"


# ─────────────────────────── registry promotion ───────────────────────────

def test_registry_promotes_gwm_to_verified_parsed():
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    gwm = next(b for b in reg["brands"] if b["brand"] == "GWM")
    assert gwm["provenance_status"] == "ACQUISITION_VERIFIED"
    assert gwm["adapter_status"] == "PARSED_TESTED"
    assert gwm["access_status"] == "REACHABLE"
    assert gwm["last_success_sha256"], "last_success_sha256 must not be null"

    parsed = [e for e in gwm["captured_endpoints"]
              if e.get("provenance_state") == "ACQUISITION_VERIFIED" and e.get("parsed") is True]
    assert parsed, "no GWM endpoint marked parsed"
    # last_success must point at the most recently captured promoted artifact
    def captured(e):
        return json.load(open(os.path.join(FIXTURE_DIR, e["artifact"] + ".prov.json"),
                              encoding="utf-8"))["captured_at"]
    newest = max(parsed, key=captured)
    want_sha = hashlib.sha256(open(os.path.join(FIXTURE_DIR, newest["artifact"]), "rb").read()).hexdigest()
    assert gwm["last_success_sha256"] == want_sha
    assert gwm["last_success_at"] >= captured(newest)
    # every recorded endpoint sha must match the bytes on disk
    for e in gwm["captured_endpoints"]:
        p = os.path.join(FIXTURE_DIR, e["artifact"])
        if os.path.exists(p):
            assert e["sha256"] == hashlib.sha256(open(p, "rb").read()).hexdigest(), e["artifact"]
