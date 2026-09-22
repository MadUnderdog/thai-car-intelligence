"""
Catalog contracts — the data model for Thai market vehicle identity.
Separates: Manufacturer → Model → Generation → Variant/Trim → Powertrain
"""
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Set
from datetime import date


class MarketStatus(Enum):
    """Market availability status."""
    CURRENT = "CURRENT"          # Currently sold/marketed
    UPCOMING = "UPCOMING"        # Announced but not yet available
    DISCONTINUED = "DISCONTINUED"  # No longer sold but was available
    HISTORICAL = "HISTORICAL"    # Past generation, not relevant now
    UNKNOWN = "UNKNOWN"          # Cannot determine


class EvidenceStrength(Enum):
    """Strength of identity evidence."""
    OFFICIAL = "OFFICIAL"        # OEM/distributor website
    LAUNCH_DOC = "LAUNCH_DOC"    # Official price list/brochure
    HIGH_QUALITY_MEDIA = "HIGH_QUALITY_MEDIA"  # Reputable Thai automotive media
    SECONDARY = "SECONDARY"      # Other sources
    UNRESOLVED = "UNRESOLVED"    # Cannot determine


@dataclass
class EvidenceLink:
    """A single piece of evidence for identity."""
    source_url: str
    source_domain: str
    source_class: str  # "official", "media", "secondary"
    evidence_strength: EvidenceStrength
    evidence_text: str  # What the source says
    acquisition_method: str  # Which adapter acquired it
    content_hash: str = ""
    observed_at: str = ""
    
    def __post_init__(self):
        if not self.content_hash and self.source_url:
            self.content_hash = hashlib.sha256(self.source_url.encode()).hexdigest()[:16]


@dataclass
class Powertrain:
    """Powertrain specification for a variant."""
    fuel_type: str = ""          # Gasoline, Diesel, Electric, Hybrid, PHEV
    engine_displacement_l: float = 0.0
    engine_code: str = ""
    horsepower_hp: int = 0
    torque_nm: int = 0
    transmission: str = ""       # Automatic, Manual, CVT, DCT
    drivetrain: str = ""         # FWD, RWD, AWD, 4WD
    battery_kwh: float = 0.0
    range_km: int = 0
    motor_count: int = 0
    
    # Evidence
    evidence: List[EvidenceLink] = field(default_factory=list)


@dataclass
class Variant:
    """A specific trim/variant of a model."""
    # Identity
    variant_name: str = ""         # e.g. "RS", "E", "Comfort"
    variant_name_thai: str = ""    # Thai name if different
    trim_code: str = ""            # OEM trim code if known
    
    # What this variant is
    body_type: str = ""            # Sedan, SUV, MPV, Hatchback
    seats: int = 0
    
    # Price (opportunistic)
    price_thb: Optional[float] = None
    price_type: str = ""           # MSRP, MODEL_RANGE, PROMOTION
    price_source_url: str = ""
    price_observed_at: str = ""
    
    # Powertrain (opportunistic)
    powertrain: Optional[Powertrain] = None
    
    # Identity evidence
    identity_evidence: List[EvidenceLink] = field(default_factory=list)
    
    # Status
    market_status: MarketStatus = MarketStatus.UNKNOWN
    
    # Aliases
    aliases: List[str] = field(default_factory=list)
    
    @property
    def canonical_id(self) -> str:
        """Deterministic canonical ID from variant name."""
        if self.variant_name:
            return hashlib.sha256(self.variant_name.lower().strip().encode()).hexdigest()[:12]
        return ""


@dataclass
class Generation:
    """A model generation / facelift / model year."""
    generation_name: str = ""      # e.g. "11th Gen", "2024", "Facelift"
    model_year: str = ""           # e.g. "2024", "2025"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    
    # Variants in this generation
    variants: List[Variant] = field(default_factory=list)
    
    # Identity evidence
    identity_evidence: List[EvidenceLink] = field(default_factory=list)
    
    # Status
    market_status: MarketStatus = MarketStatus.UNKNOWN
    
    @property
    def canonical_id(self) -> str:
        if self.generation_name:
            return hashlib.sha256(self.generation_name.lower().strip().encode()).hexdigest()[:12]
        return ""


@dataclass
class Model:
    """A vehicle model under a manufacturer."""
    # Identity
    model_name: str = ""           # e.g. "Civic", "Camry", "Atto 3"
    model_name_thai: str = ""      # Thai name if different
    model_code: str = ""           # OEM model code if known
    
    # What it is
    segment: str = ""              # B-Sedan, C-SUV, D-MPV
    body_type: str = ""            # Primary body type
    
    # Generations
    generations: List[Generation] = field(default_factory=list)
    
    # Identity evidence
    identity_evidence: List[EvidenceLink] = field(default_factory=list)
    
    # Status
    market_status: MarketStatus = MarketStatus.UNKNOWN
    
    # Aliases
    aliases: List[str] = field(default_factory=list)
    
    @property
    def canonical_id(self) -> str:
        if self.model_name:
            return hashlib.sha256(self.model_name.lower().strip().encode()).hexdigest()[:12]
        return ""


@dataclass
class Manufacturer:
    """A vehicle manufacturer / brand."""
    # Identity
    manufacturer_name: str = ""    # e.g. "Honda", "Toyota", "BYD"
    manufacturer_name_thai: str = ""  # Thai name if different
    
    # Official presence
    official_website: str = ""
    official_website_th: str = ""
    thai_distributor: str = ""
    
    # Models
    models: List[Model] = field(default_factory=list)
    
    # Identity evidence
    identity_evidence: List[EvidenceLink] = field(default_factory=list)
    
    # Status
    market_status: MarketStatus = MarketStatus.CURRENT
    
    @property
    def canonical_id(self) -> str:
        if self.manufacturer_name:
            return hashlib.sha256(self.manufacturer_name.lower().strip().encode()).hexdigest()[:12]
        return ""


@dataclass
class CatalogIdentity:
    """Complete identity chain: Manufacturer → Model → Generation → Variant."""
    manufacturer: Manufacturer
    model: Optional[Model] = None
    generation: Optional[Generation] = None
    variant: Optional[Variant] = None
    
    @property
    def full_path(self) -> str:
        parts = [self.manufacturer.manufacturer_name]
        if self.model:
            parts.append(self.model.model_name)
        if self.generation:
            parts.append(self.generation.generation_name)
        if self.variant:
            parts.append(self.variant.variant_name)
        return " > ".join(parts)
    
    @property
    def canonical_id(self) -> str:
        parts = [self.manufacturer.canonical_id]
        if self.model:
            parts.append(self.model.canonical_id)
        if self.generation:
            parts.append(self.generation.canonical_id)
        if self.variant:
            parts.append(self.variant.canonical_id)
        return "-".join(parts)


@dataclass
class CatalogEntry:
    """A single entry in the catalog inventory."""
    identity: CatalogIdentity
    market_status: MarketStatus = MarketStatus.UNKNOWN
    
    # Source count
    source_count: int = 0
    strongest_source: str = ""
    strongest_strength: EvidenceStrength = EvidenceStrength.UNRESOLVED
    
    # Evidence links
    all_evidence: List[EvidenceLink] = field(default_factory=list)
    
    # Conflicts
    conflicting_names: List[str] = field(default_factory=list)
    unresolved_issues: List[str] = field(default_factory=list)
    
    # Enrichment status
    has_price: bool = False
    has_specs: bool = False
    enrichment_coverage: float = 0.0  # 0-1
    
    def add_evidence(self, evidence: EvidenceLink):
        """Add evidence and update counts."""
        self.all_evidence.append(evidence)
        self.source_count = len(set(e.source_domain for e in self.all_evidence))
        
        # Update strongest source
        strength_order = {
            EvidenceStrength.OFFICIAL: 0,
            EvidenceStrength.LAUNCH_DOC: 1,
            EvidenceStrength.HIGH_QUALITY_MEDIA: 2,
            EvidenceStrength.SECONDARY: 3,
            EvidenceStrength.UNRESOLVED: 4,
        }
        current_strength = strength_order.get(self.strongest_strength, 4)
        new_strength = strength_order.get(evidence.evidence_strength, 4)
        if new_strength < current_strength:
            self.strongest_strength = evidence.evidence_strength
            self.strongest_source = evidence.source_domain
