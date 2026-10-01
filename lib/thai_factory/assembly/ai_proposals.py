"""
P119 — proposal-only semantic reconciliation boundary (§97 AI role).

AI may PROPOSE alias merges / conflict resolutions / dedupes — nothing else:
  - every proposal must cite packet IDs that EXIST in the packet set,
  - every proposed fact (value / canonical path) must already be present in
    the cited packets' observations — no facts absent from packets,
  - proposals are validated and stored; they are NEVER auto-applied (the
    acceptance/promotion path stays the only route to canonical data).

No model/provider code lives in this module: this file is the contract that
any future proposal source (human or model) must pass through.
"""
import json
from typing import Any, Dict, List


def _obs_value_universe(packet: Dict[str, Any]) -> set:
    universe = set()
    for category in ("identity", "price", "spec"):
        for obs in (packet.get("observations") or {}).get(category, []):
            for key in ("value", "value_numeric", "value_text", "label"):
                if obs.get(key) is not None:
                    universe.add(json.dumps(obs[key], sort_keys=True, default=str))
    return universe


def validate_proposal(proposal: Dict[str, Any], packets_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate a proposal against the cited packets.
    Returns {"ok": bool, "errors": [str]}.
    """
    errors: List[str] = []
    packet_ids = proposal.get("packet_ids") or []
    if not packet_ids:
        errors.append("no_packet_ids_cited")
        return {"ok": False, "errors": errors}

    cited = []
    for pid in packet_ids:
        if pid not in packets_by_id:
            errors.append(f"unknown_packet_id:{pid}")
        else:
            cited.append(packets_by_id[pid])
    if errors:
        return {"ok": False, "errors": errors}

    rationale = str(proposal.get("rationale") or "").strip()
    if not rationale:
        errors.append("missing_rationale")

    if not str(proposal.get("type") or "") in ("alias_merge", "conflict_resolution", "dedupe"):
        errors.append("unknown_proposal_type")

    universe = set().union(*(_obs_value_universe(p) for p in cited)) if cited else set()

    if "proposed_value" in proposal and proposal["proposed_value"] is not None:
        key = json.dumps(proposal["proposed_value"], sort_keys=True, default=str)
        if key not in universe:
            errors.append("proposed_value_not_in_cited_packets")

    if proposal.get("type") == "alias_merge":
        allowed_keys = {p.get("candidate_key") for p in cited}
        if proposal.get("proposed_canonical_key") not in allowed_keys:
            errors.append("canonical_path_not_in_cited_packets")

    return {"ok": not errors, "errors": errors}
