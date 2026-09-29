"""
P119 — assembly data model: provenance mapping + trust/role tables.

Every assembled field is a FieldProvenance dict carrying value, source_id,
artifact sha256, canonical locator, observed_at, trust_tier + packet/obs ids
(§96 field-level provenance). Roles never upgrade (§96/§95).
"""
from typing import Any, Dict, Optional

# §96 source roles → §95 trust tiers (explicit table; obs-supplied trust_tier
# always wins — this only fills role-only observations like identity rows).
TIER_BY_SOURCE_CLASS = {
    "MARKET_TRUTH": "official_verified",
    "MEDIA_DISCOVERY": "secondary_verified",
    "MARKET_REFERENCE": "reference",
    "IDENTITY_ENUMERATOR": "inferred",
}

TIER_RANK = {
    "official_verified": 3,
    "secondary_verified": 2,
    "reference": 1,
    "inferred": 0,
}

SOURCE_ROLES = (
    "IDENTITY_ENUMERATOR",
    "MARKET_TRUTH",
    "MARKET_REFERENCE",
    "MEDIA_DISCOVERY",
)


def trust_for_obs(obs: Dict[str, Any]) -> str:
    """Obs-declared trust_tier wins; never derive a HIGHER tier than the role table."""
    declared = obs.get("trust_tier")
    if declared:
        return declared
    role = obs.get("source_role") or obs.get("source_class") or "IDENTITY_ENUMERATOR"
    return TIER_BY_SOURCE_CLASS.get(role, "inferred")


def field_name(category: str, obs: Dict[str, Any]) -> str:
    if category == "identity":
        return "identity.label"
    if category == "price":
        return obs.get("field") or "price"
    return obs.get("field_key") or obs.get("field") or "spec"


def obs_value(category: str, obs: Dict[str, Any]) -> Any:
    if category == "price":
        return obs.get("value")
    if category == "spec":
        return obs.get("value_numeric") if obs.get("value_numeric") is not None else obs.get("value_text")
    return obs.get("label") or obs.get("value")


def observation_to_provenance(category: str, obs: Dict[str, Any], packet: Dict[str, Any], field: str) -> Dict[str, Any]:
    """One assembled field's provenance — verbatim from its source observation."""
    provenance_state = obs.get("provenance_state") or "UNKNOWN"
    return {
        "field": field,
        "value": obs_value(category, obs),
        "source_id": obs.get("source_url"),
        "source_name": obs.get("source_name"),
        "source_class": obs.get("source_class"),
        "source_role": obs.get("source_role") or obs.get("source_class"),
        "artifact": obs.get("artifact"),
        "artifact_sha256": obs.get("sha256"),
        "locator": obs.get("locator"),
        "observed_at": packet.get("observed_at"),
        "trust_tier": trust_for_obs(obs),
        "provenance_state": provenance_state,
        "verified": provenance_state == "ACQUISITION_VERIFIED",
        "packet_id": packet.get("packet_id"),
        "obs_id": obs.get("obs_id"),
    }
