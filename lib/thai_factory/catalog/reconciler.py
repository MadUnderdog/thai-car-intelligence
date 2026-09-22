"""
Catalog Reconciler — builds inventory, detects conflicts, produces report.
"""
import json
from typing import List, Dict
from .contracts import (
    Manufacturer, Model, Variant, CatalogEntry, MarketStatus,
    EvidenceStrength, EvidenceLink,
)


class CatalogReconciler:
    """
    Reconciles catalog entries and produces inventory report.
    """
    
    def __init__(self):
        self.entries: List[CatalogEntry] = []
        self.conflicts: List[Dict] = []
        self.unresolved: List[Dict] = []
    
    def load_entries(self, entries: List[CatalogEntry]):
        """Load catalog entries for reconciliation."""
        self.entries = entries
    
    def reconcile(self) -> Dict:
        """
        Run reconciliation and produce report.
        Returns machine-readable inventory.
        """
        report = {
            "summary": self._build_summary(),
            "manufacturers": self._build_manufacturer_report(),
            "conflicts": self.conflicts,
            "unresolved": self.unresolved,
            "coverage": self._build_coverage_report(),
        }
        
        return report
    
    def _build_summary(self) -> Dict:
        """Build summary statistics."""
        total_models = 0
        total_variants = 0
        current_count = 0
        upcoming_count = 0
        discontinued_count = 0
        
        for entry in self.entries:
            model = entry.identity.model
            if model:
                total_models += 1
                for gen in model.generations:
                    total_variants += len(gen.variants)
            
            if entry.market_status == MarketStatus.CURRENT:
                current_count += 1
            elif entry.market_status == MarketStatus.UPCOMING:
                upcoming_count += 1
            elif entry.market_status == MarketStatus.DISCONTINUED:
                discontinued_count += 1
        
        return {
            "total_manufacturers": len(set(e.identity.manufacturer.manufacturer_name for e in self.entries)),
            "total_models": total_models,
            "total_variants": total_variants,
            "current": current_count,
            "upcoming": upcoming_count,
            "discontinued": discontinued_count,
            "with_price": sum(1 for e in self.entries if e.has_price),
            "with_specs": sum(1 for e in self.entries if e.has_specs),
        }
    
    def _build_manufacturer_report(self) -> List[Dict]:
        """Build per-manufacturer report."""
        by_manufacturer = {}
        
        for entry in self.entries:
            mfr_name = entry.identity.manufacturer.manufacturer_name
            if mfr_name not in by_manufacturer:
                by_manufacturer[mfr_name] = {
                    "name": mfr_name,
                    "thai_name": entry.identity.manufacturer.manufacturer_name_thai,
                    "website": entry.identity.manufacturer.official_website,
                    "models": [],
                    "model_count": 0,
                    "variant_count": 0,
                }
            
            mfr = by_manufacturer[mfr_name]
            mfr["model_count"] += 1
            
            model = entry.identity.model
            model_data = {
                "name": model.model_name if model else "",
                "status": entry.market_status.value,
                "source_count": entry.source_count,
                "strongest_source": entry.strongest_source,
                "has_price": entry.has_price,
                "has_specs": entry.has_specs,
                "variants": [],
            }
            
            if model:
                for gen in model.generations:
                    for var in gen.variants:
                        variant_data = {
                            "name": var.variant_name,
                            "price_thb": var.price_thb,
                            "fuel_type": var.powertrain.fuel_type if var.powertrain else "",
                            "status": var.market_status.value,
                        }
                        model_data["variants"].append(variant_data)
                        mfr["variant_count"] += 1
            
            mfr["models"].append(model_data)
        
        return list(by_manufacturer.values())
    
    def _build_coverage_report(self) -> Dict:
        """Build enrichment coverage report."""
        total = len(self.entries)
        if total == 0:
            return {"total": 0, "coverage": 0.0}
        
        with_price = sum(1 for e in self.entries if e.has_price)
        with_specs = sum(1 for e in self.entries if e.has_specs)
        
        return {
            "total": total,
            "with_price": with_price,
            "with_specs": with_specs,
            "price_coverage": with_price / total,
            "specs_coverage": with_specs / total,
        }
    
    def to_json(self, report: Dict) -> str:
        """Serialize report to JSON."""
        return json.dumps(report, indent=2, ensure_ascii=False, default=str)
    
    def save_report(self, report: Dict, path: str):
        """Save report to file."""
        with open(path, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
