"""
Taxonomy Tree — raw source-native hierarchy.
Two artifacts: raw_taxonomy_universe.json + reconciled_identity_universe.json.
"""
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class TaxonomyNode:
    """Single node in the source-native taxonomy tree."""
    source_id: str
    source_role: str  # MARKET_TRUTH | IDENTITY_ENUMERATOR
    source_url: str
    source_name: str
    
    source_native_id: str = ""
    source_native_label: str = ""
    parent_native_id: str = ""  # empty for root nodes
    
    node_type: str = "FLAT_ROW"  # MANUFACTURER | MODEL | GENERATION | BODY | VARIANT | POWERTRAIN | FLAT_ROW
    
    year_model_year: str = ""
    generation_name: str = ""
    body_type: str = ""
    variant_name: str = ""
    trim_name: str = ""
    powertrain: str = ""
    
    price_thb: int = 0
    price_evidence_level: str = "UNKNOWN"  # MODEL | GENERATION | VARIANT | POWERTRAIN | UNKNOWN
    
    observed_at: str = ""
    evidence_context: str = ""
    raw_payload_hash: str = ""


@dataclass
class RawTaxonomyTree:
    """Raw source-native taxonomy — untouched from source."""
    source_name: str
    source_url: str
    source_role: str
    observed_at: str
    acquisition_method: str
    
    nodes: List[TaxonomyNode] = field(default_factory=list)
    
    def add_node(self, node: TaxonomyNode):
        self.nodes.append(node)
    
    def summary(self) -> Dict:
        by_type = {}
        for n in self.nodes:
            by_type[n.node_type] = by_type.get(n.node_type, 0) + 1
        return {
            "source": self.source_name,
            "total_nodes": len(self.nodes),
            "by_type": by_type,
        }


@dataclass
class ReconciledCandidate:
    """Normalized identity candidate with decomposition."""
    canonical_id: str = ""
    
    manufacturer: str = ""
    model: str = ""
    generation: str = ""
    body: str = ""
    variant: str = ""
    trim: str = ""
    powertrain: str = ""
    
    raw_node_ids: List[str] = field(default_factory=list)
    source_representations: List[Dict] = field(default_factory=list)
    source_count: int = 0
    
    price_thb: int = 0
    price_evidence_level: str = "UNKNOWN"
    price_source: str = ""
    
    decomposition_method: str = ""  # source_structure | suffix_pattern | none
    decomposition_confidence: str = ""  # high | medium | low | none
    decomposition_evidence: str = ""
    
    def compute_id(self):
        parts = [
            self.manufacturer.lower().strip(),
            self.model.lower().strip(),
            self.generation.lower().strip() if self.generation else "",
            self.variant.lower().strip() if self.variant else "",
        ]
        self.canonical_id = hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def build_raw_toyota() -> RawTaxonomyTree:
    """Build raw taxonomy from Toyota official pricelist.
    
    IMPORTANT: The source is a FLAT price list with no explicit hierarchy.
    Every row is a FLAT_ROW. We do NOT falsely declare MODEL vs VARIANT.
    The hierarchy will be inferred during reconciliation with evidence.
    """
    tree = RawTaxonomyTree(
        source_name="toyota_official_pricelist",
        source_url="https://www.toyota.co.th/en/pricelist",
        source_role="MARKET_TRUTH",
        observed_at=datetime.now().isoformat(),
        acquisition_method="playwright",
    )
    
    # Real Toyota data from official pricelist
    # These are FLAT rows — the source does not explicitly declare hierarchy
    rows = [
        ("Yaris ATIV", 569000),
        ("Yaris ATIV Nightshade", 709000),
        ("Yaris ATIV GR Sport", 779000),
        ("Yaris", 584000),
        ("Yaris Cross", 809000),
        ("Yaris Cross Nightshade", 929000),
        ("Corolla Altis", 909000),
        ("Corolla Altis GR Sport", 1129000),
        ("CAMRY", 1475000),
        ("GR 86", 2999000),
        ("GR Yaris", 3499000),
        ("GR Corolla", 4199000),
        ("GR Supra", 5349000),
        ("Corolla Cross", 989000),
        ("Corolla Cross GR Sport", 1254000),
        ("bZ4X", 1529000),
        ("Land Cruiser FJ", 1289000),
        ("Fortuner Leader", 1239000),
        ("Fortuner Legender", 1643000),
        ("Fortuner GR Sport", 1969000),
        ("Veloz", 795000),
        ("Innova Zenix", 1379000),
        ("Alphard", 3590000),
        ("Hilux Champ", 519000),
        ("Hilux Revo Standard Cab", 584000),
        ("Hilux Revo Z Edition", 669000),
        ("Hilux Travo Standard Cab 4TREX", 767000),
        ("Hilux Travo Prerunner & 4TREX", 789000),
        ("Hilux Travo Overland", 1102000),
        ("Hilux Travo-e", 1491000),
        ("Coaster", 2175000),
        ("Hiace", 1069000),
        ("Commuter", 1339000),
        ("Majesty", 1994000),
    ]
    
    for i, (label, price) in enumerate(rows):
        node = TaxonomyNode(
            source_id=f"toyota_flat_{i}",
            source_role="MARKET_TRUTH",
            source_url="https://www.toyota.co.th/en/pricelist",
            source_name="toyota_official_pricelist",
            source_native_id=str(i),
            source_native_label=label,
            node_type="FLAT_ROW",  # Honest: source is flat, no hierarchy declared
            price_thb=price,
            price_evidence_level="UNKNOWN",  # Cannot determine level from flat source
            observed_at=tree.observed_at,
            evidence_context=f"Price list row: {label} = ฿{price:,}",
        )
        tree.add_node(node)
    
    return tree


def build_raw_mazda() -> RawTaxonomyTree:
    """Build raw taxonomy from Mazda official lineup.
    
    The source shows models with "Starting from X THB".
    Marketing prefixes like "NEW" and body suffixes are part of the label.
    We preserve them as-is and do not decompose at raw level.
    """
    tree = RawTaxonomyTree(
        source_name="mazda_official_lineup",
        source_url="https://www.mazda.co.th/en/vehicles",
        source_role="MARKET_TRUTH",
        observed_at=datetime.now().isoformat(),
        acquisition_method="playwright",
    )
    
    rows = [
        ("NEW MAZDA2 ESSENTIAL", 529000),
        ("MAZDA3 FASTBACK", 979000),
        ("MAZDA3 SEDAN", 979000),
        ("MAZDA6 20TH ANNIVERSARY EDITION", 2499000),
        ("THE ALL-ELECTRIC MAZDA6e", 1169000),
        ("NEW MAZDA CX-3 ESSENTIAL", 699000),
        ("NEW MAZDA CX-30 ESSENTIAL", 899000),
        ("NEW MAZDA CX-5", 1219000),
        ("MAZDA CX-8", 1549000),
        ("NEW MAZDA BT-50", 762000),
    ]
    
    for i, (label, price) in enumerate(rows):
        node = TaxonomyNode(
            source_id=f"mazda_flat_{i}",
            source_role="MARKET_TRUTH",
            source_url="https://www.mazda.co.th/en/vehicles",
            source_name="mazda_official_lineup",
            source_native_id=str(i),
            source_native_label=label,
            node_type="FLAT_ROW",
            price_thb=price,
            price_evidence_level="UNKNOWN",
            observed_at=tree.observed_at,
            evidence_context=f"Lineup row: {label} = ฿{price:,}",
        )
        tree.add_node(node)
    
    return tree
