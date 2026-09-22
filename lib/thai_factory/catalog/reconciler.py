"""
Catalog Reconciler — produces inventory report with fabrication audit.
"""
import json
from typing import List, Dict
from .contracts import (
    CatalogInventory, CanonicalCatalogEntry, CatalogCandidate,
    MarketStatus, CandidateStatus, EvidenceStrength,
)


class CatalogReconciler:
    """Reconciles catalog and produces inventory report."""
    
    def __init__(self):
        self.inventory: CatalogInventory = None
    
    def load(self, inventory: CatalogInventory):
        self.inventory = inventory
    
    def reconcile(self) -> Dict:
        """Run reconciliation and produce report."""
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
            "manufacturers_seeded": len(MANUFACTURER_NAMES),
            "manufacturers_discovered": len(set(e.manufacturer_name for e in self.inventory.entries)),
            "model_candidates": len(self.inventory.candidates),
            "canonical_models": len(self.inventory.entries),
            "variant_candidates": 0,
            "canonical_variants": 0,
            "unresolved_variants": 0,
            "conflicting_identities": 0,
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
        """Check for fabricated data."""
        issues = []
        
        for e in self.inventory.entries:
            # Check for invented trim names
            if e.variant_name in ("Standard", "Base", "Entry", "Default"):
                issues.append(f"FABRICATED_VARIANT: {e.full_path} has generic trim name '{e.variant_name}'")
            
            # Check for prices converted from ranges
            if e.price_thb and e.price_type == "UNKNOWN":
                issues.append(f"UNKNOWN_PRICE_TYPE: {e.full_path} has price but unknown type")
            
            # Check for current status without evidence
            if e.market_status == MarketStatus.CURRENT:
                has_date_evidence = any("date" in ev.evidence_text.lower() or "2026" in ev.evidence_text for ev in e.identity_evidence)
                if not has_date_evidence:
                    issues.append(f"INFERRED_CURRENT: {e.full_path} marked CURRENT without date evidence")
            
            # Check for missing identity evidence
            if not e.identity_evidence:
                issues.append(f"NO_IDENTITY_EVIDENCE: {e.full_path} has no identity evidence")
        
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


MANUFACTURER_NAMES = list({
    "Honda", "Toyota", "Mazda", "Nissan", "Mitsubishi", "Suzuki", "Isuzu",
    "MG", "BYD", "Haval", "GWM", "BMW", "Mercedes-Benz", "Volvo", "Ford",
    "Chevrolet", "Subaru", "Kia", "Hyundai", "Lexus", "MINI", "ZEEKR",
    "Deepal", "Changan", "Wuling", "NETA", "ORA",
})
