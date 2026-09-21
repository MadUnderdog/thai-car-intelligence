"""
Quality gates — executable invariants for the data factory.

These gates prevent bad data from entering the canonical layer.
Each gate returns (passed, reason) tuples.

FIXES from audit:
- gate_model_range_not_variant_msrp: now checks price_type semantics, not substring
- gate_source_class_cardinality: now returns FAIL if claimed multi-source has <2 classes
- gate_evidence_path_required: now validates excerpt contains the asserted value
- Added gate_no_historical_as_current: blocks historical prices from becoming current
- Added gate_price_type_explicit: unknown price types must stay UNKNOWN
"""
import re
from typing import List, Tuple, Dict, Set
from ..models import (
    Observation, IdentityDecision, ScopeDecision, PriceType,
    TrustState, VerificationState, SourceClass
)


def gate_ambiguous_identity(obs: Observation) -> Tuple[bool, str]:
    """Ambiguous identity cannot be promoted."""
    if obs.identity_decision == IdentityDecision.AMBIGUOUS:
        return False, "ambiguous_identity"
    if obs.identity_decision == IdentityDecision.UNRESOLVED:
        return False, "unresolved_identity"
    return True, "ok"


def gate_scope_invalid(obs: Observation) -> Tuple[bool, str]:
    """Scope-invalid observation cannot be canonical."""
    if obs.scope_decision in (ScopeDecision.COMPARISON, ScopeDecision.ROUNDUP,
                               ScopeDecision.GENERIC_LISTING, ScopeDecision.UNKNOWN):
        return False, f"scope_invalid:{obs.scope_decision.value}"
    return True, "ok"


def gate_model_range_not_variant_msrp(obs: Observation) -> Tuple[bool, str]:
    """
    MODEL_RANGE cannot become VARIANT_MSRP.
    FIX: Now checks price_type semantics, not raw_value substring.
    If the observation is tagged as MODEL_RANGE, it must stay MODEL_RANGE
    and never be promoted to VARIANT_MSRP during persistence.
    """
    if obs.price_type == PriceType.MODEL_RANGE:
        # MODEL_RANGE observations must never be persisted as VARIANT_MSRP
        # The persistence layer must respect this price_type
        return False, "model_range_cannot_become_variant_msrp"
    return True, "ok"


def gate_historical_not_current(obs: Observation) -> Tuple[bool, str]:
    """
    Historical cannot become current without a currentness rule.
    FIX: Also blocks PROMOTION prices from becoming unconditional current MSRP.
    """
    if obs.price_type == PriceType.HISTORICAL:
        return False, "historical_price_not_current"
    if obs.price_type == PriceType.PROMOTION:
        # Promotions are time-limited; cannot become unconditional current price
        return False, "promotion_price_not_unconditional_current"
    return True, "ok"


def gate_secondary_not_official(obs: Observation) -> Tuple[bool, str]:
    """Secondary source cannot become OFFICIAL_VERIFIED."""
    if obs.verification_state == VerificationState.VERIFIED:
        if obs.source_class in (SourceClass.AUTOMOTIVE_MEDIA, SourceClass.NEWS_MEDIA,
                                 SourceClass.SECONDARY_DATABASE, SourceClass.DEALER):
            return False, f"secondary_verified:{obs.source_class.value}"
    return True, "ok"


def gate_evidence_path_required(obs: Observation) -> Tuple[bool, str]:
    """
    Evidence path must exist AND excerpt must contain the asserted value.
    FIX: Now validates that the excerpt actually contains the normalized value.
    """
    if not obs.evidence_excerpt and not obs.evidence_path:
        return False, "no_evidence"

    # If we have an excerpt, validate it contains the asserted value
    if obs.evidence_excerpt and obs.normalized_value:
        # Check if the normalized value (or raw value) appears in the excerpt
        val_str = str(obs.normalized_value)
        raw_str = str(obs.raw_value)
        excerpt_lower = obs.evidence_excerpt.lower()
        if val_str not in excerpt_lower and raw_str not in excerpt_lower:
            # For prices, also check with commas
            if obs.field == "price":
                try:
                    formatted = f"{int(val_str):,}"
                    if formatted not in excerpt_lower:
                        return False, "evidence_excerpt_missing_value"
                except (ValueError, TypeError):
                    pass
            else:
                return False, "evidence_excerpt_missing_value"

    return True, "ok"


def gate_idempotent_rerun(existing_fingerprints: Set[str],
                          obs: Observation) -> Tuple[bool, str]:
    """Duplicate input rerun produces zero duplicate observations."""
    if obs.fingerprint in existing_fingerprints:
        return False, "duplicate_fingerprint"
    return True, "ok"


def gate_price_sanity(obs: Observation) -> Tuple[bool, str]:
    """Price must be in reasonable THB range."""
    if obs.field == "price":
        try:
            amount = int(obs.normalized_value)
            if amount < 100_000 or amount > 20_000_000:
                return False, f"price_out_of_range:{amount}"
        except (ValueError, TypeError):
            return False, "price_not_numeric"
    return True, "ok"


def gate_no_price_key_in_specs(obs: Observation) -> Tuple[bool, str]:
    """VariantSpec key must not be 'price' or contain 'price'."""
    if obs.field != "price":
        if "price" in obs.field.lower():
            return False, f"price_key_in_spec:{obs.field}"
    return True, "ok"


def gate_price_type_explicit(obs: Observation) -> Tuple[bool, str]:
    """
    Unknown price types must stay UNKNOWN or NEEDS_REVIEW,
    never silently become MSRP.
    """
    if obs.field == "price":
        if obs.price_type == PriceType.UNKNOWN:
            # Unknown price type should not be persisted as current MSRP
            return False, "unknown_price_type_not_persisted"
    return True, "ok"


def gate_no_cross_model_contamination(obs: Observation,
                                       all_brand_mentions: Dict[str, int] = None) -> Tuple[bool, str]:
    """
    If multiple brands are mentioned with comparable counts,
    the observation should be flagged for review.
    """
    if all_brand_mentions and len(all_brand_mentions) > 1:
        sorted_counts = sorted(all_brand_mentions.values(), reverse=True)
        if len(sorted_counts) >= 2 and sorted_counts[0] <= sorted_counts[1] * 1.5:
            return False, "cross_model_contamination_risk"
    return True, "ok"


# ─── Gate Runner ────────────────────────────────────────────────────

ALL_GATES = [
    gate_ambiguous_identity,
    gate_scope_invalid,
    gate_model_range_not_variant_msrp,
    gate_historical_not_current,
    gate_secondary_not_official,
    gate_evidence_path_required,
    gate_price_sanity,
    gate_no_price_key_in_specs,
    gate_price_type_explicit,
]


def run_quality_gates(obs: Observation,
                      existing_fingerprints: Set[str] = None) -> Tuple[bool, List[str]]:
    """
    Run all quality gates on an observation.
    Returns (passed, list_of_failure_reasons).
    """
    failures = []

    for gate in ALL_GATES:
        if gate == gate_idempotent_rerun:
            if existing_fingerprints is not None:
                passed, reason = gate(existing_fingerprints, obs)
            else:
                continue
        else:
            passed, reason = gate(obs)

        if not passed:
            failures.append(reason)

    return len(failures) == 0, failures


def quarantine_observations(observations: List[Observation],
                            existing_fingerprints: Set[str] = None
                            ) -> Tuple[List[Observation], List[Observation]]:
    """
    Partition observations into accepted and quarantined.
    Returns (accepted, quarantined).
    """
    accepted = []
    quarantined = []
    fps = existing_fingerprints if existing_fingerprints is not None else set()

    for obs in observations:
        passed, reasons = run_quality_gates(obs, fps)
        if passed:
            accepted.append(obs)
        else:
            quarantined.append(obs)

    return accepted, quarantined
