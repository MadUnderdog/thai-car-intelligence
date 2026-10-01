"""
P119-R1 — targeted assembly safety repairs (Blueprint §96/§95).

Defect 1 (trust tier upgrade guard): models.trust_for_obs() returned an
obs-declared trust_tier verbatim, so an observation with a low-trust role
(IDENTITY_ENUMERATOR / MARKET_REFERENCE / …) could declare a higher tier and
assemble above its role ceiling — violating non-increasing trust (§95/§96,
hard contract 3).

Defect 2 (sibling-brand join isolation): join_keys.resolve_join_key() used
the alias-catalog lookup without proving the catalog hit belongs to the
packet's manufacturer. Real evidence on HEAD b3c9178: PKT-0250/0251
(`lexus|es`) resolved through MG's catalog entry (`nameEn: ES`, `brandSlug:
mg`) and assembled join keys carrying model_slug `mg-es` under
manufacturer_slug `lexus`.

Red-before: both defect reproductions fail on HEAD b3c9178.
"""
import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from thai_factory.assembly.models import (  # noqa: E402
    TIER_BY_SOURCE_CLASS,
    TIER_RANK,
    trust_for_obs,
)
from thai_factory.assembly.join_keys import _slug_norm, resolve_join_key  # noqa: E402

PACKETS_PATH = REPO / "audit" / "coverage" / "p113_evidence_packets.json"
ALIAS_PATH = REPO / "storage" / "thai-alias-catalog.json"


def _packets():
    return json.loads(PACKETS_PATH.read_text(encoding="utf-8"))["packets"]


def _catalog():
    return json.loads(ALIAS_PATH.read_text(encoding="utf-8"))


def _accept(packets):
    return [p for p in packets if p.get("status") == "ACCEPTED"]


def _price_packet():
    return copy.deepcopy(next(p for p in _accept(_packets()) if p["observations"].get("price")))


# ── Defect 1: trust tier ceiling ────────────────────────────────────────────
def test_p119r1_T1_identity_enumerator_cannot_declare_official_verified():
    obs = {"source_role": "IDENTITY_ENUMERATOR", "trust_tier": "official_verified"}
    tier = trust_for_obs(obs)
    assert tier != "official_verified", "an identity enumerator must never assemble above its role ceiling"
    assert tier == "inferred", tier


def test_p119r1_T2_declared_lower_tier_is_preserved_not_raised():
    # a MARKET_TRUTH observation may declare a LOWER tier; policy keeps it
    obs = {"source_role": "MARKET_TRUTH", "trust_tier": "reference"}
    assert trust_for_obs(obs) == "reference"


def test_p119r1_T3_unknown_role_fails_closed_to_inferred():
    obs = {"source_role": "TOTALLY_MADE_UP_ROLE", "trust_tier": "official_verified"}
    assert trust_for_obs(obs) == "inferred", "unknown role must fail closed, never inherit the declared tier"


def test_p119r1_T4_malformed_declared_tier_resolves_to_role_ceiling():
    obs = {"source_role": "IDENTITY_ENUMERATOR", "trust_tier": "SUPER_TRUSTED"}
    assert trust_for_obs(obs) == "inferred"
    obs2 = {"source_class": "MARKET_REFERENCE", "trust_tier": 12345}
    assert trust_for_obs(obs2) == "reference"


def test_p119r1_T5_role_ceiling_table_is_the_non_increasing_contract():
    for role, ceiling in TIER_BY_SOURCE_CLASS.items():
        assert TIER_RANK[ceiling] <= TIER_RANK["official_verified"]
    # enum roles only — no silent extra roles
    assert set(TIER_BY_SOURCE_CLASS) == {
        "MARKET_TRUTH", "MEDIA_DISCOVERY", "MARKET_REFERENCE", "IDENTITY_ENUMERATOR"
    }


def test_p119r1_T6_real_set_fields_never_exceed_role_ceiling():
    """Invariant over the REAL accepted set: assembled tier ≤ obs role ceiling."""
    import importlib
    assemble = importlib.import_module("thai_factory.assembly.assemble")
    packets = _accept(_packets())
    obs_by_id = {}
    for p in packets:
        for cat in ("identity", "price", "spec"):
            for o in p["observations"].get(cat) or []:
                obs_by_id[o.get("obs_id")] = o
    result = assemble.assemble(packets, _catalog(), fixtures_dir=str(REPO / "tests" / "fixtures"))
    checked = 0
    for rec in result.records:
        for field, prov in rec["fields"].items():
            src = obs_by_id.get(prov.get("obs_id"))
            assert src is not None, f"provenance obs_id {prov.get('obs_id')} not in packet set"
            ceiling = TIER_BY_SOURCE_CLASS.get(src.get("source_role") or src.get("source_class"), "inferred")
            assert TIER_RANK[prov["trust_tier"]] <= TIER_RANK[ceiling], \
                f"{field} assembles {prov['trust_tier']} above {ceiling}"
            checked += 1
    assert checked > 1000, checked


# ── Defect 2: sibling-brand / cross-manufacturer isolation ──────────────────
def _synthetic_catalog():
    """Same display 'Model X' published under two brands; brandb listed FIRST
    so a naive name lookup returns brandb."""
    return {
        "brands": {
            "brandb": {"nameEn": "Brand B", "slug": "brandb", "aliases": []},
            "branda": {"nameEn": "Brand A", "slug": "branda", "aliases": []},
        },
        "models": {
            "model-b": {"nameEn": "Model X", "slug": "model-b", "brandSlug": "brandb",
                        "brandEn": "Brand B", "aliases": ["Model X"]},
            "model-a": {"nameEn": "Model X", "slug": "model-a", "brandSlug": "branda",
                        "brandEn": "Brand A", "aliases": ["Model X"]},
        },
    }


def _empty_universe(tmp_path: Path) -> str:
    p = tmp_path / "empty_universe.json"
    p.write_text(json.dumps({"universe": {"records": []}}), encoding="utf-8")
    return str(p)


def test_p119r1_T7_packet_brand_a_never_resolves_to_brand_b(tmp_path):
    catalog = _synthetic_catalog()
    packet = {"packet_id": "PX-1", "candidate_key": "branda|model x||mx"}
    result = resolve_join_key(packet, catalog, universe_path=_empty_universe(tmp_path))
    if result.get("ok"):
        assert result["join_key"]["manufacturer_slug"] == "branda", result
        assert result["join_key"]["model_slug"] != "model-b", "must not take brandb's model slug"
    else:
        assert "cross_brand" in str(result.get("reason")) or "display_string_only" in str(result.get("reason")), result


def test_p119r1_T8_cross_brand_catalog_hit_is_rejected_with_explicit_reason(tmp_path):
    catalog = _synthetic_catalog()
    # naive lookup returns brandb's entry (listed first) for packet branda
    packet = {"packet_id": "PX-2", "candidate_key": "branda|model x||mx"}
    result = resolve_join_key(packet, catalog, universe_path=_empty_universe(tmp_path))
    # whichever way it goes, brandb must never be selected silently:
    if result.get("ok"):
        assert result["join_key"]["manufacturer_slug"] == "branda"
        assert result["join_key"]["model_slug"] != "model-b"
    else:
        assert result.get("reason"), "rejection must carry an explicit reason"


def test_p119r1_T9_same_model_name_different_oisolated(tmp_path):
    catalog = _synthetic_catalog()
    upath = _empty_universe(tmp_path)
    ra = resolve_join_key({"packet_id": "A", "candidate_key": "branda|model x||mx"}, catalog, universe_path=upath)
    rb = resolve_join_key({"packet_id": "B", "candidate_key": "brandb|model x||mx"}, catalog, universe_path=upath)
    if ra.get("ok") and rb.get("ok"):
        assert ra["join_key"]["manufacturer_slug"] == "branda"
        assert rb["join_key"]["manufacturer_slug"] == "brandb"
        assert ra["join_key"] != rb["join_key"], "same display under different OEMs must stay isolated"


def test_p119r1_T10_real_lexus_es_join_is_not_contaminated_by_mg():
    """Real defect on HEAD b3c9178: PKT-0250/0251 (lexus|es) assembled with
    model_slug 'mg-es' via MG's catalog entry."""
    packets = {p["packet_id"]: p for p in _packets()}
    pkt = packets.get("PKT-0250")
    assert pkt is not None
    result = resolve_join_key(pkt, _catalog())
    assert result.get("ok"), result
    jk = result["join_key"]
    assert jk["manufacturer_slug"] == "lexus"
    assert jk["model_slug"] != "mg-es", "cross-brand catalog slug leaked into the join key"
    assert jk["model_slug"] == "es", jk


def test_p119r1_T11_real_set_manufacturer_never_crosses_brands():
    """Invariant over the REAL accepted set: assembled manufacturer_slug ==
    the packet's own candidate_key brand (evidence-backed identity)."""
    import importlib
    assemble = importlib.import_module("thai_factory.assembly.assemble")
    packets = _accept(_packets())
    brand_of = {p["packet_id"]: _slug_norm((p["candidate_key"].split("|") or [""])[0]) for p in packets}
    result = assemble.assemble(packets, _catalog(), fixtures_dir=str(REPO / "tests" / "fixtures"))
    for rec in result.records:
        for cid in rec["candidate_ids"]:
            assert rec["join_key"]["manufacturer_slug"] == brand_of[cid], \
                f"{cid}: join manufacturer {rec['join_key']['manufacturer_slug']} != packet brand {brand_of[cid]}"


def test_p119r1_T12_same_brand_universe_enrichment_still_works():
    """Positive control: a real same-brand universe+catalog join keeps its
    evidence-backed path (repair must not break legitimate enrichment)."""
    packets = _accept(_packets())
    for p in packets:
        r = resolve_join_key(p, _catalog())
        if r.get("matched_via", "").startswith("identity_universe"):
            assert r["join_key"]["manufacturer_slug"] == _slug_norm((p["candidate_key"].split("|") or [""])[0])
            if r["matched_via"] != "identity_universe":
                # enrichment retained → catalog entry must be same brand
                assert "+" in r["matched_via"]
            return
    raise AssertionError("no universe-backed real packet found")
