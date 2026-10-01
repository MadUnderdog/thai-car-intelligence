"""Second-source layer: AUTOMOTIVE_MEDIA stays media.

Rules enforced here (P100-B):
  * media records are source_class=AUTOMOTIVE_MEDIA, trust_state=RESEARCH_UNVERIFIED,
    staged in their own file — never promoted to official, never merged into the
    official staging lane;
  * every join field carries BOTH sides' own artifact SHA, locator, excerpt,
    captured_at, source class and trust state;
  * contamination guards: an OEM value can never inherit a media locator, and a
    media value can never inherit an OEM locator.
"""
import collections
import hashlib
import json
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(REPO, "audit", "data-staging", "media_observations.jsonl")
OFFICIAL = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
JOINS = os.path.join(REPO, "audit", "data-staging", "cross_class_joins.json")
ART_DIR = os.path.join(REPO, "tests", "fixtures", "media-artifacts")
SOURCE_CLASS = "AUTOMOTIVE_MEDIA"
TRUST = "RESEARCH_UNVERIFIED"


def _load(path):
    if path.endswith(".jsonl"):
        with open(path, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def media():
    return _load(MEDIA)


@pytest.fixture(scope="module")
def official():
    return _load(OFFICIAL)


@pytest.fixture(scope="module")
def joins():
    return _load(JOINS)


# ───────────────────────────── media staging ─────────────────────────────

def test_media_batch_is_small_and_real(media):
    """Three documented brand_price_page_crawl pages, not speculative bulk."""
    assert 0 < len(media) <= 150, f"batch too large to call it small: {len(media)}"
    artifacts = {r["source"]["artifact_path"] for r in media}
    assert len(artifacts) == 3, sorted(artifacts)
    for a in sorted(artifacts):
        assert a.startswith("tests/fixtures/media-artifacts/")
        assert a.endswith(".html")
    # the URLs themselves must be the registry's documented brand price pages
    urls = {r["source"]["url"] for r in media}
    assert urls == {
        "https://www.9carthai.com/toyota-price/",
        "https://www.9carthai.com/honda-price/",
        "https://www.9carthai.com/mazda-price/",
    }, urls


def test_every_media_record_carries_full_provenance(media):
    for r in media:
        s = r["source"]
        assert r["source_class"] == SOURCE_CLASS, r["source_class"]
        assert r["trust_state"] == TRUST, r["trust_state"]
        assert s["artifact_sha256"] and len(s["artifact_sha256"]) == 64
        assert s["captured_at"], "missing captured_at"
        assert s["url"].startswith("https://www.9carthai.com/")
        assert s["acquisition_method"], "missing acquisition_method"
        loc = r["evidence"]["locator"]
        assert loc["method"] == "text_search"
        assert loc["text_offset"] is not None and loc["text_offset"] >= 0
        assert r["evidence"]["excerpt"], "missing excerpt"
        assert r["evidence"]["content_hash"], "missing content hash"


def test_media_artifact_sha_matches_sidecar_and_disk(media):
    seen = {}
    for r in media:
        p = os.path.join(REPO, r["source"]["artifact_path"])
        if p in seen:
            continue
        disk = hashlib.sha256(open(p, "rb").read()).hexdigest()
        side = json.load(open(p + ".prov.json", encoding="utf-8"))
        assert side["sha256"] == disk, "sidecar sha disagrees with disk"
        assert r["source"]["artifact_sha256"] == disk, "row sha disagrees with disk"
        seen[p] = disk
    assert len(seen) == 3


def test_subject_scope_is_proven_per_record(media):
    """Article/brand subject must be provable from title, heading and URL scope."""
    for r in media:
        sc = r["subject_scope"]
        brand = r["identity"]["brand_normalized"]
        assert brand in sc["url_scope"].lower(), (brand, sc["url_scope"])
        assert sc["title_declares_brand"] is True, sc["page_title"]
        assert sc["page_title"].lower().count(brand) >= 1, sc["page_title"]
        assert r["identity"]["model_raw"].lower() in sc["model_heading"].lower(), (
            r["identity"]["model_raw"], sc["model_heading"]
        )
        assert sc["identity_scope"] in ("MODEL", "VARIANT")


def test_media_rows_are_never_promoted_to_official(media, official):
    official_ids = {r.get("observation_id") for r in official}
    for r in media:
        assert r["observation_id"] not in official_ids, "media id leaked into official staging"
        assert r["source_class"] != "OEM_OFFICIAL"
        assert r["trust_state"] != "VERIFIED"
    # and the official file has no media class at all
    classes = collections.Counter(r["source"]["class"] for r in official)
    assert set(classes) == {"OEM_OFFICIAL"}, classes


# ─────────────────────────── contamination guards ───────────────────────────

def test_no_official_row_can_inherit_a_media_locator(media, official):
    media_art = {r["source"]["artifact_path"] for r in media}
    media_locs = {json.dumps(r["evidence"]["locator"], sort_keys=True, ensure_ascii=False)
                  for r in media}
    for r in official:
        loc = r.get("evidence_locator") or (r.get("evidence") or {}).get("evidence_locator") or {}
        assert r["source"]["artifact_path"] not in media_art, (
            f"{r['identity']['model_raw']}: official row points at a media artifact"
        )
        assert json.dumps(loc, sort_keys=True, ensure_ascii=False) not in media_locs, (
            f"{r['identity']['model_raw']}: official row carries a media locator"
        )


def test_no_media_row_can_inherit_an_official_locator(media, official):
    official_art = {r["source"]["artifact_path"] for r in official}
    official_locs = {}
    for r in official:
        loc = r.get("evidence_locator") or (r.get("evidence") or {}).get("evidence_locator") or {}
        official_locs[json.dumps(loc, sort_keys=True, ensure_ascii=False)] = r["observation_id"]
    for r in media:
        assert r["source"]["artifact_path"] not in official_art, (
            f"{r['observation_id']}: media row points at an official artifact"
        )
        key = json.dumps(r["evidence"]["locator"], sort_keys=True, ensure_ascii=False)
        assert key not in official_locs, (
            f"{r['observation_id']}: media row carries an official locator "
            f"({official_locs[key]})"
        )


def test_media_and_official_locators_are_disjoint(media, official):
    def key(r, loc):
        return (r["source"]["artifact_path"], json.dumps(loc, sort_keys=True, ensure_ascii=False))
    med = {key(r, r["evidence"]["locator"]) for r in media}
    off = set()
    for r in official:
        loc = r.get("evidence_locator") or (r.get("evidence") or {}).get("evidence_locator") or {}
        off.add(key(r, loc))
    assert not (med & off), f"shared artifact+locator: {list(med & off)[:3]}"


def test_mutating_a_media_artifact_does_not_affect_official_resolution(media, official):
    """Media resolution must depend only on media bytes: rewriting a media
    artifact's figure has to break media resolution and leave official rows
    untouched (they are staged from other artifacts entirely)."""
    import sys
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    import resolve_locators as RL

    media_art = {r["source"]["artifact_path"] for r in media}
    for r in official:
        assert r["source"]["artifact_path"] not in media_art

    sample = media[:5]
    base = RL.resolve_rows(sample)
    assert all(x["status"] == "exactly_one" for x in base)
    mutated = RL.resolve_rows(sample, mutate="delete")
    assert all(x["status"] == "zero" for x in mutated), (
        [(x["model"], x["status"]) for x in mutated]
    )
    # official sample still resolves (different artifacts, no shared state)
    off_sample = official[:5]
    off_base = RL.resolve_rows(off_sample)
    assert all(x["status"] == "exactly_one" for x in off_base)


# ───────────────────────────── cross-class joins ─────────────────────────────

def test_joins_are_genuine_cross_class(joins):
    assert joins["join_count"] >= 3, f"only {joins['join_count']} joins"
    assert joins["join_count"] == len(joins["joins"])
    for j in joins["joins"]:
        assert j["classes"] == ["OEM_OFFICIAL", "AUTOMOTIVE_MEDIA"], j["classes"]
        assert j["official"]["source_class"] == "OEM_OFFICIAL"
        assert j["media"]["source_class"] == SOURCE_CLASS
        assert j["official"]["value_thb"] == j["media"]["value_thb"] == j["value_thb"]
        assert j["model"]["brand"] and j["model"]["normalized"]


def test_each_join_side_retains_its_own_provenance(joins):
    for j in joins["joins"]:
        for side_name in ("official", "media"):
            s = j[side_name]
            assert s["artifact_sha256"] and len(s["artifact_sha256"]) == 64, side_name
            assert s["locator"], side_name
            assert s["excerpt"], side_name
            assert s["captured_at"], side_name
            assert s["source_class"] and s["trust_state"], side_name
        # sides must be independently evidenced, never one locator shared
        assert j["official"]["locator"] != j["media"]["locator"]
        assert j["official"]["artifact_path"] != j["media"]["artifact_path"]
        assert j["official"]["observation_id"] != j["media"]["observation_id"]


def test_join_locator_re_resolves_in_its_own_artifact(joins):
    import sys
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    import resolve_locators as RL

    rows = []
    for j in joins["joins"][:6]:
        rows.append({"observation_id": j["official"]["observation_id"],
                     "source": {"artifact_path": j["official"]["artifact_path"],
                                "name": j["official"]["source_name"]},
                     "evidence_locator": j["official"]["locator"],
                     "price": {"value_thb": j["official"]["value_thb"]},
                     "identity": {"model_raw": j["model"]["official_name"]}})
        rows.append({"observation_id": j["media"]["observation_id"],
                     "source": {"artifact_path": j["media"]["artifact_path"],
                                "name": j["media"]["source_name"]},
                     "evidence": {"locator": j["media"]["locator"]},
                     "price": {"value_thb": j["media"]["value_thb"]},
                     "identity": {"model_raw": j["model"]["media_name"]}})
    res = RL.resolve_rows(rows)
    bad = [x for x in res if x["status"] != "exactly_one"]
    assert not bad, [(x["model"], x["status"]) for x in bad]


def test_media_trust_state_never_upgrades_in_a_join(joins):
    """A join corroboration must not launder media trust into official, or the
    reverse: each side keeps the trust it earned."""
    for j in joins["joins"]:
        assert j["media"]["trust_state"] == TRUST, j["media"]["trust_state"]
        assert j["official"]["trust_state"] == "ACQUISITION_VERIFIED", j["official"]["trust_state"]
        assert j["media"]["trust_state"] != j["official"]["trust_state"]
