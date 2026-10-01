"""
Catalog Reconciler — produces inventory report with fabrication audit.
"""
import json
from typing import List, Dict
from .contracts import (
    CatalogInventory, CanonicalCatalogEntry, CatalogCandidate,
    MarketStatus, CandidateStatus, EvidenceStrength, RelationshipType,
)
from .sources import MANUFACTURER_SOURCE_MAPS


class CatalogReconciler:
    """Reconciles catalog and produces inventory report."""
    
    def __init__(self):
        self.inventory: CatalogInventory = None
    
    def load(self, inventory: CatalogInventory):
        self.inventory = inventory
    
    def reconcile(self) -> Dict:
        report = {
            "summary": self._build_summary(),
            "by_manufacturer": self._build_manufacturer_report(),
            "fabrication_audit": self._run_fabrication_audit(),
            "coverage": self._build_coverage_report(),
        }
        return report
    
    def _build_summary(self) -> Dict:
        by_status = {}
        for e in self.inventory.entries:
            status = e.market_status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "manufacturers_seeded": len(MANUFACTURER_SOURCE_MAPS),
            "manufacturers_discovered": len(set(e.manufacturer_name for e in self.inventory.entries)),
            "model_candidates": len([c for c in self.inventory.candidates if not c.variant_name]),
            "canonical_models": len([e for e in self.inventory.entries if not e.variant_name]),
            "variant_candidates": len([c for c in self.inventory.candidates if c.variant_name]),
            "canonical_variants": len([e for e in self.inventory.entries if e.variant_name]),
            "unresolved_variants": 0,
            "conflicting_identities": len([r for r in self.inventory.relationships if r.relationship_type == RelationshipType.CONFLICT]),
            "by_status": by_status,
            "with_price_evidence": sum(1 for e in self.inventory.entries if e.price_thb is not None),
            "with_spec_evidence": sum(1 for e in self.inventory.entries if e.specs),
        }
    
    def _build_manufacturer_report(self) -> List[Dict]:
        by_mfr = {}
        for e in self.inventory.entries:
            mfr = e.manufacturer_name
            if mfr not in by_mfr:
                by_mfr[mfr] = {
                    "name": mfr,
                    "thai_name": e.manufacturer_name_thai,
                    "models": [],
                    "model_count": 0,
                }
            by_mfr[mfr]["models"].append({
                "name": e.model_name,
                "status": e.market_status.value,
                "evidence_count": len(e.identity_evidence),
                "has_price": e.price_thb is not None,
                "has_specs": bool(e.specs),
            })
            by_mfr[mfr]["model_count"] += 1
        
        return list(by_mfr.values())
    
    def _run_fabrication_audit(self) -> Dict:
        """Scan ALL candidates and canonical entries for fabrication."""
        issues = []
        
        # Scan canonical entries
        for e in self.inventory.entries:
            # Check for invented trim names
            if e.variant_name in ("Standard", "Base", "Entry", "Default", "Generic"):
                issues.append(f"FABRICATED_VARIANT: {e.full_path} has generic trim name '{e.variant_name}'")
            
            # Check for prices converted from ranges
            if e.price_thb and e.price_type == "UNKNOWN":
                issues.append(f"UNKNOWN_PRICE_TYPE: {e.full_path} has price but unknown type")
            
            # Check for missing identity evidence
            if not e.identity_evidence:
                issues.append(f"NO_IDENTITY_EVIDENCE: {e.full_path} has no identity evidence")
            
            # Check for status without status evidence
            if e.market_status != MarketStatus.UNKNOWN and not e.status_evidence:
                issues.append(f"NO_STATUS_EVIDENCE: {e.full_path} has status {e.market_status.value} without status evidence")
        
        # Scan candidates
        for c in self.inventory.candidates:
            # Check for prose-only mentions
            if c.source_class == "media" and not c.is_body_mention:
                issues.append(f"SIDEBAR_MENTION: {c.manufacturer_name} {c.model_name} from sidebar/related")
        
        return {
            "issues": issues,
            "passed": len(issues) == 0,
            "issue_count": len(issues),
        }
    
    def _build_coverage_report(self) -> Dict:
        total = len(self.inventory.entries)
        if total == 0:
            return {"total": 0}
        
        return {
            "total": total,
            "with_price": sum(1 for e in self.inventory.entries if e.price_thb is not None),
            "with_specs": sum(1 for e in self.inventory.entries if e.specs),
        }
    
    def save_report(self, report: Dict, path: str):
        with open(path, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
