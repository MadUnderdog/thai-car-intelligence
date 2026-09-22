"""
Catalog contracts — strict data-truth model with reconciliation.
"""
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict
from datetime import date


class MarketStatus(Enum):
    CURRENT = "CURRENT"
    UPCOMING = "UPCOMING"
    DISCONTINUED = "DISCONTINUED"
    HISTORICAL = "HISTORICAL"
    UNKNOWN = "UNKNOWN"


class EvidenceStrength(Enum):
    OFFICIAL = "OFFICIAL"
    LAUNCH_DOC = "LAUNCH_DOC"
    HIGH_QUALITY_MEDIA = "HIGH_QUALITY_MEDIA"
    SECONDARY = "SECONDARY"
    UNRESOLVED = "UNRESOLVED"


class CandidateStatus(Enum):
    CANDIDATE = "CANDIDATE"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    MERGED = "MERGED"


class RelationshipType(Enum):
    SAME_ENTITY = "SAME_ENTITY"
    ALIAS = "ALIAS"
    DISTINCT_ENTITY = "DISTINCT_ENTITY"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    CONFLICT = "CONFLICT"


@dataclass
class EvidenceLink:
    source_url: str
    source_domain: str
    source_class: str  # "official", "media", "secondary"
    evidence_strength: EvidenceStrength
    evidence_text: str  # Exact quote
    evidence_type: str  # "identity", "price", "spec", "status"
    acquisition_method: str
    content_hash: str = ""
    observed_at: str = ""
    
    def __post_init__(self):
        if not self.content_hash and self.source_url:
            self.content_hash = hashlib.sha256(self.source_url.encode()).hexdigest()[:16]


@dataclass
class Relationship:
    """Relationship between two candidates."""
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    evidence: List[EvidenceLink] = field(default_factory=list)
    notes: str = ""


@dataclass
class CatalogCandidate:
    manufacturer_name: str = ""
    model_name: str = ""
    generation_name: str = ""
    variant_name: str = ""
    trim_code: str = ""
    
    source_url: str = ""
    source_domain: str = ""
    source_class: str = ""
    evidence_text: str = ""
    acquisition_method: str = ""
    
    is_body_mention: bool = False
    is_sidebar_mention: bool = False
    
    status: CandidateStatus = CandidateStatus.CANDIDATE
    evidence: List[EvidenceLink] = field(default_factory=list)
    
    @property
    def canonical_id(self) -> str:
        parts = [
            self.manufacturer_name.lower().strip(),
            self.model_name.lower().strip(),
            self.generation_name.lower().strip() if self.generation_name else "",
            self.variant_name.lower().strip() if self.variant_name else "",
        ]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


@dataclass
class CanonicalCatalogEntry:
    manufacturer_name: str = ""
    manufacturer_name_thai: str = ""
    model_name: str = ""
    model_name_thai: str = ""
    generation_name: str = ""
    variant_name: str = ""
    
    manufacturer_id: str = ""
    model_id: str = ""
    generation_id: str = ""
    variant_id: str = ""
    
    market_status: MarketStatus = MarketStatus.UNKNOWN
    
    identity_evidence: List[EvidenceLink] = field(default_factory=list)
    status_evidence: List[EvidenceLink] = field(default_factory=list)
    
    price_thb: Optional[float] = None
    price_type: str = ""
    price_evidence: List[EvidenceLink] = field(default_factory=list)
    
    specs: Dict = field(default_factory=dict)
    spec_evidence: List[EvidenceLink] = field(default_factory=list)
    
    aliases: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    
    def compute_ids(self):
        def _hash(s):
            return hashlib.sha256(s.lower().strip().encode()).hexdigest()[:12]
        
        self.manufacturer_id = _hash(self.manufacturer_name)
        self.model_id = _hash(f"{self.manufacturer_name}|{self.model_name}")
        self.generation_id = _hash(f"{self.manufacturer_name}|{self.model_name}|{self.generation_name}") if self.generation_name else ""
        self.variant_id = _hash(f"{self.manufacturer_name}|{self.model_name}|{self.generation_name}|{self.variant_name}") if self.variant_name else ""
    
    @property
    def full_path(self) -> str:
        parts = [self.manufacturer_name]
        if self.model_name:
            parts.append(self.model_name)
        if self.generation_name:
            parts.append(self.generation_name)
        if self.variant_name:
            parts.append(self.variant_name)
        return " > ".join(parts)


@dataclass
class CatalogInventory:
    entries: List[CanonicalCatalogEntry] = field(default_factory=list)
    candidates: List[CatalogCandidate] = field(default_factory=list)
    rejected_candidates: List[CatalogCandidate] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    
    target_date: str = ""
    manufacturers_seeded: int = 0
    manufacturers_discovered: int = 0
    
    def add_entry(self, entry: CanonicalCatalogEntry):
        entry.compute_ids()
        self.entries.append(entry)
    
    def add_candidate(self, candidate: CatalogCandidate):
        self.candidates.append(candidate)
    
    def get_by_manufacturer(self, manufacturer: str) -> List[CanonicalCatalogEntry]:
        return [e for e in self.entries if e.manufacturer_name.lower() == manufacturer.lower()]
    
    def summary(self) -> Dict:
        by_status = {}
        for e in self.entries:
            status = e.market_status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "manufacturers_seeded": self.manufacturers_seeded,
            "manufacturers_discovered": len(set(e.manufacturer_name for e in self.entries)),
            "model_candidates": len([c for c in self.candidates if not c.variant_name]),
            "canonical_models": len([e for e in self.entries if not e.variant_name]),
            "variant_candidates": len([c for c in self.candidates if c.variant_name]),
            "canonical_variants": len([e for e in self.entries if e.variant_name]),
            "unresolved_variants": 0,
            "conflicting_identities": len([r for r in self.relationships if r.relationship_type == RelationshipType.CONFLICT]),
            "by_status": by_status,
            "with_price_evidence": sum(1 for e in self.entries if e.price_thb is not None),
            "with_spec_evidence": sum(1 for e in self.entries if e.specs),
        }
