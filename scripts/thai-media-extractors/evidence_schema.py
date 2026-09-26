#!/usr/bin/env python3
"""
Evidence schema — typed observation records for Thai automotive data extraction.

Every accepted observation MUST have:
- entity identity (brand + model + variant)
- field + raw/normalized value + scope
- source URL + class + published/observed date
- extraction method + exact excerpt
- content hash + trust state

NO confidence numbers without defined rules.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal
from datetime import datetime
import hashlib
import json

TrustState = Literal[
    "VERIFIED",              # Official source, confirmed
    "QUALIFIED",             # Official API/web, not manually verified
    "RESEARCH_UNVERIFIED",   # Secondary media, not confirmed
    "REJECTED",              # Failed validation
    "UNRESOLVED",            # Needs human review
]

SourceClass = Literal[
    "OFFICIAL_API",
    "OFFICIAL_WEB",
    "OFFICIAL_PDF",
    "OFFICIAL_SOCIAL",
    "DEALER_WEB",
    "AUTO_MEDIA",            # Headlightmag, AutoSpinn, etc.
    "REFERENCE_MEDIA",       # 9CARTHAI, etc.
    "SEARCH_LEAD",           # Discovery only, never evidence
]

ObservationScope = Literal["MODEL", "VARIANT"]

PriceType = Literal[
    "LIST_PRICE",            # Model-range / starting price
    "MSRP",                  # Specific trim price
    "CAMPAIGN_PRICE",        # Promotion / special price
    "AFTER_DISCOUNT",        # After discount price
]


@dataclass
class Observation:
    """A single source-backed observation with full provenance."""
    # Entity identity
    brand: str
    model: str
    variant: str               # "__MODEL_RANGE__" for model-level pricing
    scope: ObservationScope     # "MODEL" or "VARIANT"

    # Field evidence
    obs_field: str              # "price", "power_kw", "torque_nm", etc.
    raw_value: str              # Raw text from source
    normalized_value: Optional[str] = None  # Normalized numeric/string
    unit: Optional[str] = None  # "THB", "kW", "Nm", etc.
    price_type: Optional[PriceType] = None  # For price observations

    # Source provenance
    source_url: str = ""
    source_class: SourceClass = "SEARCH_LEAD"
    published_date: Optional[str] = None
    observed_date: str = field(default_factory=lambda: datetime.now().isoformat())
    extraction_method: str = ""
    evidence_excerpt: str = ""
    content_hash: str = ""

    # Trust
    trust_state: TrustState = "UNRESOLVED"

    # Metadata
    article_title: Optional[str] = None
    source_name: Optional[str] = None
    source_tier: Optional[str] = None

    def __post_init__(self):
        if not self.content_hash and self.evidence_excerpt:
            self.content_hash = hashlib.sha256(self.evidence_excerpt.encode()).hexdigest()[:16]
        if not self.normalized_value and self.raw_value:
            self.normalized_value = self.raw_value

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class RejectionRecord:
    """A rejected candidate with reason — never silently dropped."""
    brand: str
    model_hint: str            # What we thought it might be
    reason: str                # WHY it was rejected
    source_url: str = ""
    evidence_excerpt: str = ""
    extraction_method: str = ""
    observed_date: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractionRun:
    """Tracks a complete extraction run."""
    run_id: str
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finished_at: Optional[str] = None
    raw_candidates: int = 0
    accepted_observations: int = 0
    rejected_candidates: int = 0
    unresolved_candidates: int = 0
    per_brand: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "raw_candidates": self.raw_candidates,
            "accepted_observations": self.accepted_observations,
            "rejected_candidates": self.rejected_candidates,
            "unresolved_candidates": self.unresolved_candidates,
            "per_brand": self.per_brand,
        }
