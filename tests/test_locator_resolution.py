"""Locator integrity: every staged row must resolve to EXACTLY ONE record.

Regression guard for the P99 defect where 20 rows carried ambiguous locators
(Toyota JSON-LD paths keyed only by variant name across a shared block, Nissan
sharing the generic `.vehicle-in-category-wrapper:has(.price-figure)` selector).

`scripts/resolve_locators.py` re-resolves each locator from the artifact bytes in
a real Chromium — never from the staged row — and the mutations rewrite the
artifact so a locator that merely searched for a price, or that could drift onto
a neighbouring model, stops resolving.
"""
import collections
import json
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
RESOLVER = os.path.join(REPO, "scripts")

PREVIOUSLY_AMBIGUOUS_TOYOTA_TRIMS = {"HEV Premium", "HEV Premium GR-S", "Sport", "Sport GR-S"}


def _rows():
    with open(STAGING, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _loc(row):
    if row.get("evidence_locator"):
        return row["evidence_locator"]
    return (row.get("evidence") or {}).get("evidence_locator") or {}


def _resolve(rows, mutate=None):
    import sys
    if RESOLVER not in sys.path:
        sys.path.insert(0, RESOLVER)
    import resolve_locators as RL
    return RL.resolve_rows(rows, mutate=mutate)


@pytest.fixture(scope="module")
def baseline():
    return _resolve(_rows())


@pytest.fixture(scope="module")
def swapped():
    """One shared pass: rewriting every record's figure costs a browser run, so
    it is computed once and asserted by several tests."""
    return _resolve(_rows(), mutate="swap")


# ───────────────────── A4: the standing regression assertion ─────────────────────

def test_every_accepted_row_resolves_to_exactly_one_record(baseline):
    """No staged row may resolve to zero records or to more than one."""
    bad = [b for b in baseline if b["status"] != "exactly_one"]
    assert not bad, (
        f"{len(bad)}/{len(baseline)} rows do not resolve uniquely: "
        + "; ".join(f"{b['method']}:{b['model']}->{b['status']}(n={b['n']})" for b in bad[:8])
    )
    assert len(baseline) == len(_rows())


def test_every_resolution_matches_the_row_claim(baseline):
    """The single record a locator lands on must carry this row's own number."""
    rows = {_rows()[i].get("observation_id"): _rows()[i] for i in range(len(_rows()))}
    for b in baseline:
        if b["status"] != "exactly_one":
            continue
        match = b["matches"][0]
        want = rows[b["observation_id"]]["price"]["value_thb"]
        assert match["price"] == want, (
            f"{b['model']}: locator resolved to price {match['price']} but the row claims {want}"
        )


def test_locators_are_globally_unique():
    """Two accepted rows must never share one locator (the P99 defect)."""
    rows = _rows()
    buckets = collections.defaultdict(list)
    for i, r in enumerate(rows):
        buckets[json.dumps(_loc(r), sort_keys=True, ensure_ascii=False)].append(i)
    dupes = {k: v for k, v in buckets.items() if len(v) > 1}
    assert not dupes, f"shared locators: {list(dupes.values())[:5]}"


def test_canonical_path_fields_are_unique_per_record():
    rows = _rows()
    for field in ("json_path", "dom_path", "canonical_locator"):
        vals = [_loc(r)[field] for r in rows if _loc(r).get(field)]
        dupes = [v for v, n in collections.Counter(vals).items() if n > 1]
        assert not dupes, f"{field} reused across rows: {dupes[:3]}"


# ───────────────────────── A1/A2: the 20 formerly-ambiguous rows ─────────────────────────

def test_toyota_paths_carry_model_and_block_identity():
    """Toyota's block is shared by every model, so the path must name the record."""
    toyota = [r for r in _rows() if r["source"]["name"].startswith("Toyota")]
    assert len(toyota) == 99
    for r in toyota:
        loc = _loc(r)
        assert loc["ldjson_block_index"] is not None
        assert loc["item_name"], "path does not name the vehicle"
        assert loc["variant_name"] == r["identity"]["variant_raw"]
        assert loc["item_name"] in loc["json_path"], "json_path lacks the model identity"
    # the trims that used to collide must now sit on distinct paths
    colliding = [r for r in toyota if r["identity"]["variant_raw"] in PREVIOUSLY_AMBIGUOUS_TOYOTA_TRIMS]
    assert colliding, "expected the formerly colliding trims to still be staged"
    paths = [_loc(r)["json_path"] for r in colliding]
    assert len(paths) == len(set(paths)), "formerly colliding trims still share a path"
    models = {r["identity"]["model_raw"] for r in colliding}
    assert len(models) >= 3, f"expected several models carrying those trims, saw {models}"


def test_toyota_locator_rejects_a_foreign_model(baseline):
    """A locator whose item_name is replaced must resolve to nothing."""
    rows = _rows()
    sample = [r for r in rows if _loc(r).get("ldjson_path") or _loc(r).get("ldplusjson_block")]
    sample = sample[:5]
    assert len(sample) == 5
    import copy
    tampered = copy.deepcopy(sample)
    for r in tampered:
        _loc(r)["item_name"] = "Toyota C-HR Nonexistent"
    res = _resolve(tampered)
    assert all(x["status"] == "zero" for x in res), (
        "a locator with a foreign model name still resolved: "
        + str([(x["model"], x["status"]) for x in res])
    )


def test_nissan_rows_carry_a_unique_dom_path():
    nissan = [r for r in _rows() if r["source"]["name"].startswith("Nissan")]
    assert len(nissan) == 10, f"expected 10 Nissan rows, got {len(nissan)}"
    paths = []
    for r in nissan:
        loc = _loc(r)
        assert loc.get("dom_path"), f"nissan row missing dom_path: {r['identity']['model_raw']}"
        assert loc["dom_path"].startswith("body"), "dom_path must be document-absolute"
        paths.append(loc["dom_path"])
    assert len(set(paths)) == len(paths), "nissan dom_paths collide"
    # the generic convenience selector must not be the canonical locator
    for r in nissan:
        assert _loc(r)["selector"] != _loc(r)["dom_path"]


# ───────────────────────── A3: mutations ─────────────────────────

def test_price_swap_defeats_every_row(swapped):
    """Rewrite each record's figure: the locator must stop resolving, and the
    number must still be published somewhere on the page — proving resolution
    binds to THIS record instead of 'wherever the price appears'."""
    res = swapped
    survived = [x for x in res if x["status"] != "zero"]
    assert not survived, (
        f"{len(survived)} rows survived a price rewrite: "
        + "; ".join(f"{x['method']}:{x['model']}({x['status']})" for x in survived[:8])
    )
    # for DOM rows the number is re-published elsewhere, so this is not vacuous
    dom = [x for x in res if x["method"] in ("dom_card", "dom_query", "playwright_dom")]
    assert dom, "expected DOM rows in the sample"
    missing = [x for x in dom if "price_present_after=True" not in str(x["detail"])]
    assert not missing, (
        f"{len(missing)} DOM mutations did not keep the number on the page "
        f"(vacuous test): {[x['model'] for x in missing[:5]]}"
    )


def test_deletion_never_resolves_to_another_model():
    """Delete each source's record. Requirement: the locator must not silently
    resolve to ANOTHER model.

    Outcome is either (a) zero — the record is gone, or (b) the identical
    record. (b) happens on mini_home_page.html, where the page's own framework
    re-creates the node immediately (marker removed, a NEW node reappears), and
    on positional paths that re-land after the shift — in which case the matched
    text must still carry this row's price and must not name any other model of
    the same brand."""
    rows = _rows()
    per_source = {}
    for r in rows:
        key = (r["source"]["name"], (_loc(r).get("method") or "ldjson_path"))
        per_source.setdefault(key, r)
    sample = list(per_source.values())
    assert len(sample) >= 10, f"expected coverage across sources, got {len(sample)}"

    res = _resolve(sample, mutate="delete")
    by_id = {r.get("observation_id"): r for r in sample}
    models_by_brand = collections.defaultdict(set)
    for r in rows:
        models_by_brand[r["identity"]["brand_normalized"]].add(r["identity"]["model_raw"])

    defeated, survived = [], []
    for x in res:
        row = by_id[x["observation_id"]]
        if x["status"] == "zero":
            defeated.append(x)
            continue
        survived.append(x)
        assert x["status"] == "exactly_one" and len(x["matches"]) == 1, (
            x["model"], x["status"], x["n"])
        match = x["matches"][0]
        want = row["price"]["value_thb"]
        text = str(match.get("text", ""))
        assert match["price"] == want, (
            f"{row['identity']['model_raw']}: deletion resolved at {match['price']}, "
            f"row claims {want}")
        brand_models = models_by_brand[row["identity"]["brand_normalized"]]
        foreign = [m for m in brand_models
                   if m != row["identity"]["model_raw"] and len(m) > 3 and m in text]
        assert not foreign, (
            f"{row['identity']['model_raw']}: after deletion the locator landed on "
            f"another model's record: {foreign}")

    assert len(defeated) >= max(6, int(0.5 * len(sample))), (
        f"only {len(defeated)}/{len(sample)} deletions detected — too few to prove "
        f"anything: {[(x['model'], x['status']) for x in survived]}")
    # report which sources self-heal, so the exception stays visible
    if survived:
        print("self-healing after delete:", [(x["model"], x["status"]) for x in survived])
