"""
P119-I — AI semantic reconciliation is PROPOSAL-ONLY and packet-cited.

Red-before: lib/thai_factory/assembly/ai_proposals.py does not exist on
d8b3ef6+plan. The validator (not any model) is the boundary: proposals may
cite only packet IDs that exist, and may only propose values that are already
present in the cited packets' observations — no facts absent from packets.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

PACKETS_PATH = REPO / "audit" / "coverage" / "p113_evidence_packets.json"


def load_mod():
    try:
        import importlib
        return importlib.import_module("thai_factory.assembly.ai_proposals")
    except Exception:
        return None


def validator():
    m = load_mod()
    assert m is not None, "lib/thai_factory/assembly/ai_proposals.py must exist"
    return m


def packets_by_id():
    packets = json.loads(PACKETS_PATH.read_text(encoding="utf-8"))["packets"]
    return {p["packet_id"]: p for p in packets}


def test_p119_I1_valid_proposal_citing_real_packet_ids_is_accepted():
    V = validator()
    by_id = packets_by_id()
    pkt = next(p for p in by_id.values() if p["observations"].get("price"))
    obs = pkt["observations"]["price"][0]
    proposal = {
        "type": "conflict_resolution",
        "packet_ids": [pkt["packet_id"]],
        "proposed_value": obs["value"],
        "rationale": "same artifact price row, kept verbatim",
    }
    out = V.validate_proposal(proposal, by_id)
    assert out["ok"], out


def test_p119_I2_unknown_packet_id_is_rejected():
    V = validator()
    out = V.validate_proposal(
        {"type": "dedupe", "packet_ids": ["PKT-999999"], "proposed_value": 1, "rationale": "x"},
        packets_by_id(),
    )
    assert not out["ok"]
    assert any("packet" in e for e in out["errors"]), out


def test_p119_I3_fact_absent_from_cited_packets_is_rejected():
    V = validator()
    by_id = packets_by_id()
    pkt = next(p for p in by_id.values() if p["observations"].get("price"))
    # a value that exists nowhere in the cited packet
    proposal = {
        "type": "conflict_resolution",
        "packet_ids": [pkt["packet_id"]],
        "proposed_value": 123456789,
        "rationale": "invented",
    }
    out = V.validate_proposal(proposal, by_id)
    assert not out["ok"]
    assert any("packet" in e or "value" in e or "facts" in e for e in out["errors"]), out


def test_p119_I4_proposal_module_imports_no_provider_or_model_code():
    m = load_mod()
    assert m is not None
    path = Path(str(m.__file__))
    src = path.read_text(encoding="utf-8")
    forbidden = ("openai", "anthropic", "ollama", "langchain", "requests", "httpx", "urllib.request", "litellm")
    for token in forbidden:
        assert token not in src, f"proposal boundary must not reference {token}"
    # and no dynamic provider import patterns
    assert re.search(r"import\s+(openai|anthropic)", src) is None


def test_p119_I5_alias_merge_proposal_must_cite_existing_canonical_paths():
    V = validator()
    by_id = packets_by_id()
    pkt = next(p for p in by_id.values() if p["observations"].get("identity"))
    label = pkt["observations"]["identity"][0].get("label")
    ok = V.validate_proposal(
        {"type": "alias_merge", "packet_ids": [pkt["packet_id"]], "proposed_canonical_key": pkt["candidate_key"],
         "rationale": "same identity evidence", "proposed_value": label},
        by_id,
    )
    assert ok["ok"], ok
    bad = V.validate_proposal(
        {"type": "alias_merge", "packet_ids": [pkt["packet_id"]], "proposed_canonical_key": "brandx|ghost-model||ghost",
         "rationale": "made up", "proposed_value": label},
        by_id,
    )
    assert not bad["ok"], "canonical path absent from cited packets must be rejected"
