"""
Taxonomy Tree — raw source-native hierarchy + normalized candidate graph.
Two artifacts: raw_taxonomy_universe.json + reconciled_identity_universe.json.
"""
import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime


class NodeType(Enum):
    MANUFACTURER = "MANUFACTURER"
    MODEL = "MODEL"
    GENERATION = "GENERATION"
    BODY = "BODY"
    VARIANT = "VARIANT"
    POWERTRAIN = "POWERTRAIN"
    UNKNOWN = "UNKNOWN"


class SourceRole(Enum):
    IDENTITY_ENUMERATOR = "IDENTITY_ENUMERATOR"
    MARKET_TRUTH = "MARKET_TRUTH"


@dataclass
class TaxonomyNode:
    """Single node in the source-native taxonomy tree."""
    source_id: str
    source_role: str
    source_url: str
    source_name: str
    
    source_native_id: str = ""
    source_native_label: str = ""
    parent_native_id: str = ""
    
    node_type: str = "UNKNOWN"
    
    year_model_year: str = ""
    generation_name: str = ""
    body_type: str = ""
    variant_name: str = ""
    trim_name: str = ""
    powertrain: str = ""
    
    price_thb: int = 0
    price_level: str = "UNKNOWN"  # MODEL | GENERATION | VARIANT | POWERTRAIN | UNKNOWN
    
    observed_at: str = ""
    effective_from: str = ""
    effective_to: str = ""
    
    evidence_context: str = ""
    raw_payload_hash: str = ""
    
    # For decomposition tracking
    raw_label: str = ""
    decomposed_from: str = ""  # Which parent node this was decomposed from


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
class NormalizedCandidate:
    """Normalized identity candidate with decomposition."""
    canonical_id: str = ""
    
    manufacturer: str = ""
    model: str = ""
    generation: str = ""
    body: str = ""
    variant: str = ""
    trim: str = ""
    powertrain: str = ""
    
    source_representations: List[Dict] = field(default_factory=list)
    source_count: int = 0
    
    price_thb: int = 0
    price_level: str = "UNKNOWN"
    price_source: str = ""
    
    decompositions: List[Dict] = field(default_factory=list)
    
    def compute_id(self):
        parts = [
            self.manufacturer.lower().strip(),
            self.model.lower().strip(),
            self.generation.lower().strip() if self.generation else "",
            self.variant.lower().strip() if self.variant else "",
        ]
        self.canonical_id = hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


class TaxonomyNormalizer:
    """Decomposes source labels into model/variant hierarchy."""
    
    # Known trim/grade suffixes (used as fallback only)
    TRIM_SUFFIXES = [
        "GR Sport", "GR-S", "RS", "e:HEV", "HEV", "EV", "PHEV",
        "Leader", "Legender", "Standard", "Prerunner", "4TREX",
        "Essential", "Fastback", "Sedan", "Crossover",
        "Nightshade", "Overland", "Champ",
        "Standard Cab", "Double Cab", "Smart Cab",
        "Z Edition", "R Plus", "S Plus",
    ]
    
    # Known body patterns
    BODY_PATTERNS = [
        "Standard Cab", "Double Cab", "Smart Cab", "Mega Cab",
        "Fastback", "Sedan", "SUV", "Crossover", "Hatchback",
        "Pickup", "PPV", "MPV", "Van",
    ]
    
    def decompose_label(self, label: str, parent_label: str = "") -> Dict:
        """Decompose a source label into model/variant hierarchy.
        
        Uses signals:
        1. Parent-child relationship from source
        2. URL path structure
        3. Explicit headings
        4. Price-list row structure
        5. Naming patterns (fallback only)
        """
        result = {
            "raw_label": label,
            "model": "",
            "generation": "",
            "body": "",
            "variant": "",
            "trim": "",
            "powertrain": "",
            "confidence": "low",
        }
        
        # If we have parent, use it as model hint
        if parent_label:
            # Check if label starts with parent
            if label.lower().startswith(parent_label.lower()):
                remainder = label[len(parent_label):].strip()
                if remainder:
                    result["model"] = parent_label
                    result["variant"] = remainder
                    result["confidence"] = "medium"
                    return result
        
        # Try to decompose by known patterns
        for body in self.BODY_PATTERNS:
            if body.lower() in label.lower():
                parts = label.split(body, 1)
                result["model"] = parts[0].strip()
                result["body"] = body
                if len(parts) > 1 and parts[1].strip():
                    result["variant"] = parts[1].strip()
                result["confidence"] = "medium"
                return result
        
        # Try trim suffix decomposition
        for trim in self.TRIM_SUFFIXES:
            if trim.lower() in label.lower():
                parts = label.split(trim, 1)
                model_part = parts[0].strip()
                if model_part:
                    result["model"] = model_part
                    result["variant"] = trim
                    result["confidence"] = "low"
                    return result
        
        # No decomposition possible
        result["model"] = label
        result["confidence"] = "none"
        return result


def build_raw_taxonomy_toyota() -> RawTaxonomyTree:
    """Build raw taxonomy from Toyota official pricelist."""
    tree = RawTaxonomyTree(
        source_name="toyota_official",
        source_url="https://www.toyota.co.th/en/pricelist",
        source_role="MARKET_TRUTH",
        observed_at=datetime.now().isoformat(),
        acquisition_method="playwright",
    )
    
    # Real Toyota data from official pricelist
    # Format: (source_label, price_thb)
    models = [
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
    
    for i, (label, price) in enumerate(models):
        node = TaxonomyNode(
            source_id=f"toyota_{i}",
            source_role="MARKET_TRUTH",
            source_url="https://www.toyota.co.th/en/pricelist",
            source_name="toyota_official",
            source_native_id=str(i),
            source_native_label=label,
            node_type="MODEL",  # Will be decomposed later
            price_thb=price,
            price_level="UNKNOWN",
            observed_at=tree.observed_at,
            evidence_context=f"Price list entry: {label} = ฿{price:,}",
            raw_label=label,
        )
        tree.add_node(node)
    
    return tree


def build_raw_taxonomy_mazda() -> RawTaxonomyTree:
    """Build raw taxonomy from Mazda official lineup."""
    tree = RawTaxonomyTree(
        source_name="mazda_official",
        source_url="https://www.mazda.co.th/en/vehicles",
        source_role="MARKET_TRUTH",
        observed_at=datetime.now().isoformat(),
        acquisition_method="playwright",
    )
    
    models = [
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
    
    for i, (label, price) in enumerate(models):
        node = TaxonomyNode(
            source_id=f"mazda_{i}",
            source_role="MARKET_TRUTH",
            source_url="https://www.mazda.co.th/en/vehicles",
            source_name="mazda_official",
            source_native_id=str(i),
            source_native_label=label,
            node_type="MODEL",
            price_thb=price,
            price_level="UNKNOWN",
            observed_at=tree.observed_at,
            evidence_context=f"Lineup entry: {label} = ฿{price:,}",
            raw_label=label,
        )
        tree.add_node(node)
    
    return tree
