"""
Typed source adapter contract and observation model.

Every source adapter implements: discover → fetch → extract.
Every observation carries full provenance and structured decisions.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Tuple
import hashlib
import json
from datetime import datetime, timezone


# ─── Enums ──────────────────────────────────────────────────────────

class SourceClass(str, Enum):
    OEM_OFFICIAL = "OEM_OFFICIAL"
    OFFICIAL_PDF = "OFFICIAL_PDF"
    OFFICIAL_SOCIAL = "OFFICIAL_SOCIAL"
    AUTOMOTIVE_MEDIA = "AUTOMOTIVE_MEDIA"
    NEWS_MEDIA = "NEWS_MEDIA"
    DEALER = "DEALER"
    SECONDARY_DATABASE = "SECONDARY_DATABASE"
    SEARCH_LEAD = "SEARCH_LEAD"


class TrustState(str, Enum):
    OFFICIAL_VERIFIED = "OFFICIAL_VERIFIED"
    QUALIFIED = "QUALIFIED"
    UNVERIFIED = "UNVERIFIED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class VerificationState(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_OFFICIAL = "NOT_OFFICIAL"
    UNCHECKED = "UNCHECKED"


class IdentityDecision(str, Enum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


class ScopeDecision(str, Enum):
    SINGLE_MODEL = "SINGLE_MODEL"
    SINGLE_VARIANT = "SINGLE_VARIANT"
    MULTI_MODEL_EXPLICIT = "MULTI_MODEL_EXPLICIT"
    COMPARISON = "COMPARISON"
    ROUNDUP = "ROUNDUP"
    GENERIC_LISTING = "GENERIC_LISTING"
    UNKNOWN = "UNKNOWN"


class PriceType(str, Enum):
    MSRP = "MSRP"
    LIST_PRICE = "LIST_PRICE"
    PROMOTION = "PROMOTION"
    MODEL_RANGE = "MODEL_RANGE"
    HISTORICAL = "HISTORICAL"
    UNKNOWN = "UNKNOWN"


class ObservationField(str, Enum):
    PRICE = "price"
    POWER_HP = "power_hp"
    POWER_KW = "power_kw"
    TORQUE_NM = "torque_nm"
    ENGINE_CC = "engine_cc"
    ENGINE_L = "engine_l"
    FUEL_TYPE = "fuel_type"
    TRANSMISSION = "transmission"
    DRIVE_TYPE = "drive_type"
    LENGTH_MM = "length_mm"
    WIDTH_MM = "width_mm"
    HEIGHT_MM = "height_mm"
    WHEELBASE_MM = "wheelbase_mm"
    WEIGHT_KG = "weight_kg"
    BATTERY_KWH = "battery_kwh"
    RANGE_KM = "range_km"
    SEATING = "seating"


# ─── Source Reference ───────────────────────────────────────────────

@dataclass
class SourceRef:
    """Reference to a discoverable document."""
    url: str
    title: str = ""
    published_date: str = ""
    source_domain: str = ""
    discovery_method: str = ""  # rss, category, web_search
    metadata: Dict = field(default_factory=dict)


# ─── Document Snapshot ──────────────────────────────────────────────

@dataclass
class DocumentSnapshot:
    """Fetched document with content and metadata."""
    url: str
    html: str
    text: str
    content_hash: str
    fetched_at: str = ""
    title: str = ""
    published_date: str = ""

    def __post_init__(self):
        if not self.fetched_at:
            self.fetched_at = datetime.now(timezone.utc).isoformat()
        if not self.content_hash and self.text:
            self.content_hash = hashlib.sha256(self.text[:5000].encode()).hexdigest()[:16]


# ─── Identity Decision ──────────────────────────────────────────────

@dataclass
class IdentityResult:
    """Structured identity resolution output."""
    decision: IdentityDecision
    canonical_brand: str = ""
    canonical_model: str = ""
    canonical_variant: str = ""
    canonical_model_id: str = ""
    canonical_variant_id: str = ""
    confidence: float = 0.0
    reason: str = ""  # EXACT_ALIAS, THAI_ALIAS, BODY_CONTEXT, AMBIGUOUS, UNRESOLVED
    evidence: List[str] = field(default_factory=list)


# ─── Scope Decision ─────────────────────────────────────────────────

@dataclass
class ScopeResult:
    """Structured scope validation output."""
    decision: ScopeDecision
    primary_brand: str = ""
    primary_model: str = ""
    brand_mentions: Dict[str, int] = field(default_factory=dict)
    model_mentions: Dict[str, int] = field(default_factory=dict)
    region_text: str = ""  # the text region that established this scope
    confidence: float = 0.0
    reason: str = ""


# ─── Observation ────────────────────────────────────────────────────

@dataclass
class Observation:
    """
    A single source-backed observation with full provenance.
    Immutable after creation — never overwrite, always append new observations.
    """
    # Identity
    observation_id: str = ""
    source_url: str = ""
    source_domain: str = ""
    source_class: SourceClass = SourceClass.AUTOMOTIVE_MEDIA
    title: str = ""
    published_date: str = ""

    # Entity
    brand: str = ""
    model: str = ""
    variant: str = ""

    # Field evidence
    field: str = ""  # ObservationField value
    raw_value: str = ""
    normalized_value: str = ""
    unit: str = ""
    price_type: PriceType = PriceType.UNKNOWN

    # Decisions
    identity_decision: IdentityDecision = IdentityDecision.UNRESOLVED
    identity_confidence: float = 0.0
    identity_reason: str = ""
    scope_decision: ScopeDecision = ScopeDecision.UNKNOWN
    scope_confidence: float = 0.0
    scope_reason: str = ""

    # Trust & verification
    trust_state: TrustState = TrustState.UNVERIFIED
    verification_state: VerificationState = VerificationState.UNCHECKED

    # Provenance
    evidence_excerpt: str = ""
    evidence_path: str = ""  # CSS/XPath/heading context
    content_hash: str = ""
    extractor_version: str = "1.0.0"
    observed_at: str = ""

    # Persistence
    persisted: bool = False
    canonical_model_id: str = ""
    canonical_variant_id: str = ""
    source_document_id: str = ""

    def __post_init__(self):
        if not self.observed_at:
            self.observed_at = datetime.now(timezone.utc).isoformat()
        if not self.observation_id:
            raw = f"{self.source_url}|{self.brand}|{self.model}|{self.field}|{self.normalized_value}"
            self.observation_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    @property
    def fingerprint(self) -> str:
        """Dedup fingerprint: domain + content_hash + entity + field + value."""
        return f"{self.source_domain}|{self.content_hash}|{self.brand}|{self.model}|{self.field}|{self.normalized_value}"

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert enums to strings
        for k in ["source_class", "trust_state", "verification_state",
                   "identity_decision", "scope_decision", "price_type"]:
            if k in d and hasattr(d[k], 'value'):
                d[k] = d[k].value
        return d


# ─── Source Metadata ────────────────────────────────────────────────

@dataclass
class SourceMetadata:
    """Metadata about a source adapter."""
    name: str
    domain: str
    source_class: SourceClass
    trust_state: TrustState
    verification_state: VerificationState
    has_rss: bool = False
    has_category_pages: bool = False
    supports_pagination: bool = False
    notes: str = ""


# ─── Source Adapter Interface ───────────────────────────────────────

class SourceAdapter(ABC):
    """
    Typed source adapter contract.
    Every source implements discover → fetch → extract.
    Adapters must NOT directly mutate DB tables.
    """

    @abstractmethod
    def metadata(self) -> SourceMetadata:
        """Return source metadata."""
        ...

    @abstractmethod
    def discover(self, max_articles: int = 15) -> List[SourceRef]:
        """Discover documents from this source."""
        ...

    @abstractmethod
    def fetch(self, ref: SourceRef) -> Optional[DocumentSnapshot]:
        """Fetch a document snapshot."""
        ...

    @abstractmethod
    def extract(self, snapshot: DocumentSnapshot) -> List[Observation]:
        """Extract observation candidates from a snapshot."""
        ...

    def classify_scope(self, snapshot: DocumentSnapshot) -> ScopeResult:
        """Classify the scope of a document. Default: single model."""
        return ScopeResult(
            decision=ScopeDecision.SINGLE_MODEL,
            confidence=0.5,
            reason="default",
        )
