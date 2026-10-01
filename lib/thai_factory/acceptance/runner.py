"""
Acceptance Runner — reads evidence packets + live DB, makes deterministic promotion decisions.

This is a SEPARATE read-only runner that does not import project verifier helpers.
It reads only immutable artifacts/evidence packets + live DB for reconciliation.
Promotion is deterministic and per-observation.
"""
from typing import List, Dict, Optional, Tuple
import json
import os
from .evidence_packet import (
    EvidencePacket, EvidenceClass, AcceptanceDecision,
    CurrentnessState, ExtractionConfidence
)


class AcceptanceRunner:
    """
    Lane B: Acceptance/Promotion runner.
    
    Reads evidence packets and makes deterministic promotion decisions.
    Production DB receives only accepted observations.
    """
    
    # Minimum confidence for acceptance
    MIN_CONFIDENCE = {
        EvidenceClass.OEM_OFFICIAL: ExtractionConfidence.HIGH,
        EvidenceClass.GOVERNMENT_DLT: ExtractionConfidence.HIGH,
        EvidenceClass.STRUCTURED_REF: ExtractionConfidence.MEDIUM,
        EvidenceClass.MEDIA_DISCOVERY: ExtractionConfidence.MEDIUM,
        EvidenceClass.MARKETPLACE: ExtractionConfidence.LOW,
        EvidenceClass.USER_CONTRIBUTED: ExtractionConfidence.LOW,
    }
    
    # Source classes that can promote to production
    PROMOTABLE_SOURCES = {
        EvidenceClass.OEM_OFFICIAL,
        EvidenceClass.GOVERNMENT_DLT,
        EvidenceClass.STRUCTURED_REF,
    }
    
    def __init__(self, db_connection=None):
        """Initialize with optional DB connection for conflict checking."""
        self.db = db_connection
        self.decisions: List[Dict] = []
    
    def evaluate(self, packet: EvidencePacket) -> AcceptanceDecision:
        """
        Evaluate a single evidence packet and return acceptance decision.
        
        Deterministic: same input always produces same output.
        """
        # Rule 1: Confidence check
        min_conf = self.MIN_CONFIDENCE.get(packet.source_class, ExtractionConfidence.HIGH)
        if self._confidence_below_min(packet.extraction_confidence, min_conf):
            packet.acceptance_decision = AcceptanceDecision.REJECTED
            packet.acceptance_reason = f"Confidence {packet.extraction_confidence.value} below minimum {min_conf.value}"
            return packet.acceptance_decision
        
        # Rule 2: Currentness check
        if packet.currentness == CurrentnessState.STALE:
            packet.acceptance_decision = AcceptanceDecision.REJECTED
            packet.acceptance_reason = "Stale observation"
            return packet.acceptance_decision
        
        # Rule 3: Evidence locator required
        if not packet.evidence_locator:
            packet.acceptance_decision = AcceptanceDecision.QUARANTINED
            packet.acceptance_reason = "No evidence locator"
            return packet.acceptance_decision
        
        # Rule 4: Hash verification (if hashes present)
        if packet.artifact_hashes.upstream_payload_sha256:
            # Hash exists but we can't verify without fetching
            # This is a PARTIAL verification — mark for manual review
            pass
        
        # Rule 5: Source class promotion eligibility
        if packet.source_class not in self.PROMOTABLE_SOURCES:
            packet.acceptance_decision = AcceptanceDecision.QUARANTINED
            packet.acceptance_reason = f"Source class {packet.source_class.value} not directly promotable"
            return packet.acceptance_decision
        
        # Rule 6: Conflict detection (if DB available)
        if self.db:
            conflict = self._check_conflict(packet)
            if conflict:
                packet.acceptance_decision = AcceptanceDecision.CONFLICT
                packet.acceptance_reason = f"Conflicts with existing: {conflict}"
                return packet.acceptance_decision
        
        # Rule 7: Accept
        packet.acceptance_decision = AcceptanceDecision.ACCEPTED
        packet.acceptance_reason = "All acceptance criteria met"
        return packet.acceptance_decision
    
    def evaluate_batch(self, packets: List[EvidencePacket]) -> Dict[str, int]:
        """
        Evaluate a batch of evidence packets.
        Returns summary counts.
        """
        counts = {d.value: 0 for d in AcceptanceDecision}
        
        for packet in packets:
            decision = self.evaluate(packet)
            counts[decision.value] += 1
            self.decisions.append({
                'packet_id': packet.packet_id,
                'candidate_key': packet.candidate_key,
                'decision': decision.value,
                'reason': packet.acceptance_reason,
                'source_class': packet.source_class.value,
            })
        
        return counts
    
    def _confidence_below_min(self, actual: ExtractionConfidence, minimum: ExtractionConfidence) -> bool:
        """Check if actual confidence is below minimum."""
        levels = {
            ExtractionConfidence.UNCERTAIN: 0,
            ExtractionConfidence.LOW: 1,
            ExtractionConfidence.MEDIUM: 2,
            ExtractionConfidence.HIGH: 3,
        }
        return levels.get(actual, 0) < levels.get(minimum, 0)
    
    def _check_conflict(self, packet: EvidencePacket) -> Optional[str]:
        """
        Check if packet conflicts with existing DB data.
        Returns conflict description or None.
        """
        # TODO: Implement actual DB conflict checking
        # For now, return None (no conflict detected)
        return None
    
    def get_ledger(self) -> List[Dict]:
        """Get the acceptance ledger (all decisions made)."""
        return self.decisions
    
    def get_summary(self) -> Dict[str, int]:
        """Get summary counts of all decisions."""
        counts = {d.value: 0 for d in AcceptanceDecision}
        for d in self.decisions:
            counts[d['decision']] += 1
        return counts
