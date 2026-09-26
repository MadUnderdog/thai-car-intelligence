"""
Acceptance Ledger — machine-readable record of all acceptance decisions.

Produces: artifact candidate → acceptance decision → DB action → final DB row id → reason.
Counts are computed independently from row-level ledger, not copied from report metadata.
"""
from typing import List, Dict, Optional
import json
import datetime
from .evidence_packet import EvidencePacket, AcceptanceDecision


class AcceptanceLedger:
    """
    Machine-readable acceptance ledger.
    
    Every acceptance decision is recorded with:
    - packet_id
    - candidate_key
    - source_class
    - acceptance_decision
    - reason
    - db_action (INSERT/UPDATE/NO_ACTION)
    - db_row_id (if inserted/updated)
    - timestamp
    """
    
    def __init__(self, ledger_path: Optional[str] = None):
        """Initialize ledger, optionally loading from file."""
        self.entries: List[Dict] = []
        self.ledger_path = ledger_path
        
        if ledger_path and os.path.exists(ledger_path):
            self.load(ledger_path)
    
    def record(self, packet: EvidencePacket, db_action: Optional[str] = None, db_row_id: Optional[str] = None):
        """
        Record an acceptance decision.
        
        Args:
            packet: The evidence packet with acceptance_decision set
            db_action: INSERT/UPDATE/NO_ACTION
            db_row_id: Final DB row ID if inserted/updated
        """
        entry = {
            'packet_id': packet.packet_id,
            'candidate_key': packet.candidate_key,
            'source_class': packet.source_class.value,
            'source_url': packet.source_url,
            'native_id': packet.native_id,
            'acceptance_decision': packet.acceptance_decision.value if packet.acceptance_decision else None,
            'reason': packet.acceptance_reason,
            'db_action': db_action,
            'db_row_id': db_row_id,
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'extracted_value_hash': self._hash_value(packet.extracted_value),
        }
        self.entries.append(entry)
    
    def save(self, path: Optional[str] = None):
        """Save ledger to JSON file."""
        save_path = path or self.ledger_path
        if not save_path:
            raise ValueError("No ledger path specified")
        
        with open(save_path, 'w') as f:
            json.dump(self.entries, f, indent=2)
    
    def load(self, path: str):
        """Load ledger from JSON file."""
        with open(path) as f:
            self.entries = json.load(f)
    
    def get_counts(self) -> Dict[str, int]:
        """
        Compute counts independently from row-level ledger.
        Never copies from report metadata.
        """
        counts = {d.value: 0 for d in AcceptanceDecision}
        for entry in self.entries:
            decision = entry.get('acceptance_decision')
            if decision:
                counts[decision] = counts.get(decision, 0) + 1
        return counts
    
    def get_by_candidate(self, candidate_key: str) -> List[Dict]:
        """Get all entries for a specific candidate."""
        return [e for e in self.entries if e['candidate_key'] == candidate_key]
    
    def get_by_decision(self, decision: AcceptanceDecision) -> List[Dict]:
        """Get all entries with a specific decision."""
        return [e for e in self.entries if e['acceptance_decision'] == decision.value]
    
    def get_reject_reasons(self) -> Dict[str, int]:
        """Get count of rejection reasons."""
        reasons = {}
        for entry in self.entries:
            if entry.get('acceptance_decision') == AcceptanceDecision.REJECTED.value:
                reason = entry.get('reason', 'unknown')
                reasons[reason] = reasons.get(reason, 0) + 1
        return reasons
    
    def _hash_value(self, value) -> str:
        """Compute hash of extracted value for deduplication."""
        if value is None:
            return ""
        try:
            import hashlib
            return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]
        except Exception:
            return ""


import os
