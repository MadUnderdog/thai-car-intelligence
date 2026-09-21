"""
Quality gates — executable invariants for the data factory.

These gates prevent bad data from entering the canonical layer.
Each gate returns (passed, reason) tuples.
"""
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
    """MODEL_RANGE cannot become VARIANT_MSRP."""
    if obs.price_type == PriceType.MODEL_RANGE and "variant" in obs.raw_value.lower():
        return False, "model_range_as_variant_msrp"
    return True, "ok"


def gate_historical_not_current(obs: Observation) -> Tuple[bool, str]:
    """Historical cannot become current without a currentness rule."""
    if obs.price_type == PriceType.HISTORICAL:
        return False, "historical_price"
    return True, "ok"


def gate_secondary_not_official(obs: Observation) -> Tuple[bool, str]:
    """Secondary source cannot become OFFICIAL_VERIFIED."""
    if obs.verification_state == VerificationState.VERIFIED:
        if obs.source_class in (SourceClass.AUTOMOTIVE_MEDIA, SourceClass.NEWS_MEDIA,
                                 SourceClass.SECONDARY_DATABASE, SourceClass.DEALER):
            return False, f"secondary_verified:{obs.source_class.value}"
    return True, "ok"


def gate_evidence_path_required(obs: Observation) -> Tuple[bool, str]:
    """Evidence path must exist for promoted observations."""
    if not obs.evidence_excerpt and not obs.evidence_path:
        return False, "no_evidence"
    return True, "ok"


def gate_idempotent_rerun(existing_fingerprints: Set[str],
                          obs: Observation) -> Tuple[bool, str]:
    """Duplicate input rerun produces zero duplicate observations."""
    if obs.fingerprint in existing_fingerprints:
        return False, "duplicate_fingerprint"
    return True, "ok"


def gate_source_class_cardinality(source_classes: Set[str]) -> Tuple[bool, str]:
    """Source-class cardinality counts classes, not URLs."""
    # This is informational — multi-source assembly requires distinct classes
    if len(source_classes) >= 2:
        return True, f"multi_source:{len(source_classes)}"
    return True, f"single_source:{len(source_classes)}"


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
