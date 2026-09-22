"""
Catalog contracts — strict data-truth model.
A. CatalogCandidate = source suggestion (unverified)
B. CanonicalCatalogEntry = identity survived reconciliation with evidence
"""
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict
from datetime import date


class MarketStatus(Enum):
    CURRENT = "CURRENT"          # Explicit current-market evidence
    UPCOMING = "UPCOMING"        # Announced, not yet available
    DISCONTINUED = "DISCONTINUED"  # No longer sold
    HISTORICAL = "HISTORICAL"    # Past generation
    UNKNOWN = "UNKNOWN"          # Insufficient evidence


class EvidenceStrength(Enum):
    OFFICIAL = "OFFICIAL"        # OEM/distributor website
    LAUNCH_DOC = "LAUNCH_DOC"    # Official price list/brochure
    HIGH_QUALITY_MEDIA = "HIGH_QUALITY_MEDIA"
    SECONDARY = "SECONDARY"
    UNRESOLVED = "UNRESOLVED"


class CandidateStatus(Enum):
    CANDIDATE = "CANDIDATE"      # Suggested by source, not verified
    VERIFIED = "VERIFIED"        # Identity confirmed by evidence
    REJECTED = "REJECTED"        # Proven false or insufficient
    MERGED = "MERGED"            # Merged into another entry


@dataclass
class EvidenceLink:
    """Single piece of evidence with exact provenance."""
    source_url: str
    source_domain: str
    source_class: str  # "official", "media", "secondary"
    evidence_strength: EvidenceStrength
    evidence_text: str  # Exact quote from source
    evidence_type: str  # "identity", "price", "spec", "status"
    acquisition_method: str
    content_hash: str = ""
    observed_at: str = ""
    
    def __post_init__(self):
        if not self.content_hash and self.source_url:
            self.content_hash = hashlib.sha256(self.source_url.encode()).hexdigest()[:16]


@dataclass
class CatalogCandidate:
    """
    A candidate identity suggested by a source.
    NOT yet canonical — needs reconciliation.
    """
    # Identity (as stated by source)
    manufacturer_name: str = ""
    model_name: str = ""           # Exact name from source
    generation_name: str = ""      # If specified
    variant_name: str = ""         # If specified
    trim_code: str = ""            # If specified
    
    # Source context
    source_url: str = ""
    source_domain: str = ""
    source_class: str = ""
    evidence_text: str = ""        # Exact quote containing the identity
    acquisition_method: str = ""
    
    # What was observed
    is_body_mention: bool = False  # True if mentioned in article body
    is_sidebar_mention: bool = False  # True if in sidebar/related
    is_nav_mention: bool = False   # True if in navigation
    
    # Candidate status
    status: CandidateStatus = CandidateStatus.CANDIDATE
    
    # Evidence
    evidence: List[EvidenceLink] = field(default_factory=list)
    
    @property
    def canonical_id(self) -> str:
        """Hierarchical canonical ID from manufacturer+model+generation+variant."""
        parts = [
            self.manufacturer_name.lower().strip(),
            self.model_name.lower().strip(),
            self.generation_name.lower().strip() if self.generation_name else "",
            self.variant_name.lower().strip() if self.variant_name else "",
        ]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


@dataclass
class CanonicalCatalogEntry:
    """
    Identity that survived reconciliation with explicit evidence.
    Never auto-promoted from Candidate.
    """
    # Hierarchical identity
    manufacturer_name: str = ""
    manufacturer_name_thai: str = ""
    model_name: str = ""
    model_name_thai: str = ""
    generation_name: str = ""
    variant_name: str = ""
    
    # Canonical IDs (hierarchical, collision-safe)
    manufacturer_id: str = ""
    model_id: str = ""
    generation_id: str = ""
    variant_id: str = ""
    
    # Status (evidence-driven, never inferred)
    market_status: MarketStatus = MarketStatus.UNKNOWN
    
    # Identity evidence (explicit quotes proving this identity exists)
    identity_evidence: List[EvidenceLink] = field(default_factory=list)
    
    # Price evidence (only if explicitly attached to this identity)
    price_thb: Optional[float] = None
    price_type: str = ""  # MSRP, MODEL_RANGE, UNKNOWN
    price_evidence: List[EvidenceLink] = field(default_factory=list)
    
    # Spec evidence (only if explicitly attached)
    specs: Dict = field(default_factory=dict)
    spec_evidence: List[EvidenceLink] = field(default_factory=list)
    
    # Aliases (proven to refer to same entity)
    aliases: List[str] = field(default_factory=list)
    
    # Conflicts (names/variants that couldn't be resolved)
    conflicts: List[str] = field(default_factory=list)
    
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
    
    def compute_ids(self):
        """Compute hierarchical canonical IDs."""
        def _hash(s):
            return hashlib.sha256(s.lower().strip().encode()).hexdigest()[:12]
        
        self.manufacturer_id = _hash(self.manufacturer_name)
        self.model_id = _hash(f"{self.manufacturer_name}|{self.model_name}")
        self.generation_id = _hash(f"{self.manufacturer_name}|{self.model_name}|{self.generation_name}") if self.generation_name else ""
        self.variant_id = _hash(f"{self.manufacturer_name}|{self.model_name}|{self.generation_name}|{self.variant_name}") if self.variant_name else ""


@dataclass
class CatalogInventory:
    """
    Complete catalog inventory with reconciliation metadata.
    """
    # Entries
    entries: List[CanonicalCatalogEntry] = field(default_factory=list)
    
    # Candidates that haven't been promoted
    candidates: List[CatalogCandidate] = field(default_factory=list)
    rejected_candidates: List[CatalogCandidate] = field(default_factory=list)
    
    # Metadata
    target_date: str = ""
    manufacturers_seeded: int = 0
    manufacturers_discovered: int = 0
    
    def add_entry(self, entry: CanonicalCatalogEntry):
        """Add canonical entry."""
        entry.compute_ids()
        self.entries.append(entry)
    
    def add_candidate(self, candidate: CatalogCandidate):
        """Add candidate for reconciliation."""
        self.candidates.append(candidate)
    
    def get_by_manufacturer(self, manufacturer: str) -> List[CanonicalCatalogEntry]:
        """Get entries for a manufacturer."""
        return [e for e in self.entries if e.manufacturer_name.lower() == manufacturer.lower()]
    
    def summary(self) -> Dict:
        """Build summary statistics."""
        by_status = {}
        for e in self.entries:
            status = e.market_status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total_entries": len(self.entries),
            "candidates": len(self.candidates),
            "rejected": len(self.rejected_candidates),
            "by_status": by_status,
            "with_price": sum(1 for e in self.entries if e.price_thb is not None),
            "with_specs": sum(1 for e in self.entries if e.specs),
            "manufacturers": list(set(e.manufacturer_name for e in self.entries)),
        }
