"""
Evidence Packet — immutable observation record from Discovery Lane.

Every observation becomes an evidence packet with:
- source_class, exact URL/endpoint, native_id, observed_at, retrieval method
- immutable revision when available, raw/local artifact hashes
- target candidate key, exact evidence locator
- extracted value, extraction confidence, validity/currentness state
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Any, Dict, List
import hashlib
import json
import datetime


class EvidenceClass(str, Enum):
    """Source classification for provenance tracking."""
    OEM_OFFICIAL = "OEM_OFFICIAL"           # Manufacturer website/API
    GOVERNMENT_DLT = "GOVERNMENT_DLT"       # Thai DLT or equivalent
    STRUCTURED_REF = "STRUCTURED_REF"       # Fipe, open-ev-data, etc.
    MEDIA_DISCOVERY = "MEDIA_DISCOVERY"     # Articles, reviews, news
    MARKETPLACE = "MARKETPLACE"             # One2car, Chobrod, etc.
    USER_CONTRIBUTED = "USER_CONTRIBUTED"   # Forums, social media


class AcceptanceDecision(str, Enum):
    """Final disposition of an evidence packet."""
    ACCEPTED = "ACCEPTED"           # Promoted to production
    QUARANTINED = "QUARANTINED"     # Held for review
    REJECTED = "REJECTED"           # Failed validation
    UNRESOLVED = "UNRESOLVED"       # Cannot determine validity
    CONFLICT = "CONFLICT"           # Conflicts with existing data


class CurrentnessState(str, Enum):
    """Whether the observation is current or stale."""
    CURRENT = "CURRENT"             # Believed to be current
    STALE = "STALE"                 # Known to be outdated
    UNKNOWN = "UNKNOWN"             # Cannot determine


class ExtractionConfidence(str, Enum):
    """Confidence in the extraction accuracy."""
    HIGH = "HIGH"                   # Structured data, clear extraction
    MEDIUM = "MEDIUM"               # Semi-structured, some inference
    LOW = "LOW"                     # Unstructured, significant inference
    UNCERTAIN = "UNCERTAIN"         # Cannot determine confidence


@dataclass
class EvidenceLocator:
    """Exact location of evidence within the source artifact."""
    artifact_path: str              # Path to the artifact file
    json_path: Optional[str] = None # JSON path (e.g., "$.rows[0].brand")
    html_selector: Optional[str] = None  # CSS selector for HTML content
    quote: Optional[str] = None     # Exact text quote from source
    line_number: Optional[int] = None  # Line number in source


@dataclass
class ArtifactHash:
    """Hashes for upstream and local artifacts."""
    upstream_payload_sha256: Optional[str] = None  # SHA-256 of upstream raw payload
    local_artifact_sha256: Optional[str] = None    # SHA-256 of local artifact file
    git_blob_sha: Optional[str] = None             # Git blob SHA (for GitHub sources)


@dataclass
class EvidencePacket:
    """Immutable observation record from Discovery Lane."""
    
    # Identity
    packet_id: str                          # Unique packet identifier
    candidate_key: str                      # Target candidate (e.g., "toyota:corolla:2024:z-e")
    
    # Source provenance
    source_class: EvidenceClass
    source_url: str                         # Exact URL/endpoint
    source_name: str                        # Human-readable source name
    native_id: Optional[str] = None         # Source-native identifier
    immutable_revision: Optional[str] = None  # Commit SHA, API version, etc.
    
    # Temporal
    observed_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    currentness: CurrentnessState = CurrentnessState.UNKNOWN
    
    # Extraction
    extracted_value: Any = None             # The actual extracted data
    extraction_confidence: ExtractionConfidence = ExtractionConfidence.MEDIUM
    evidence_locator: Optional[EvidenceLocator] = None
    
    # Hashes
    artifact_hashes: ArtifactHash = field(default_factory=ArtifactHash)
    
    # Acceptance (set by Lane B)
    acceptance_decision: Optional[AcceptanceDecision] = None
    acceptance_reason: Optional[str] = None
    db_row_id: Optional[str] = None         # Final DB row if accepted
    
    def compute_local_hash(self, artifact_path: str) -> str:
        """Compute SHA-256 of local artifact file."""
        h = hashlib.sha256()
        with open(artifact_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        self.artifact_hashes.local_artifact_sha256 = h.hexdigest()
        return self.artifact_hashes.local_artifact_sha256
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        d = asdict(self)
        d['source_class'] = self.source_class.value
        d['acceptance_decision'] = self.acceptance_decision.value if self.acceptance_decision else None
        d['currentness'] = self.currentness.value
        d['extraction_confidence'] = self.extraction_confidence.value
        d['observed_at'] = self.observed_at.isoformat()
        return d
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'EvidencePacket':
        """Deserialize from dictionary."""
        d['source_class'] = EvidenceClass(d['source_class'])
        d['acceptance_decision'] = AcceptanceDecision(d['acceptance_decision']) if d.get('acceptance_decision') else None
        d['currentness'] = CurrentnessState(d['currentness'])
        d['extraction_confidence'] = ExtractionConfidence(d['extraction_confidence'])
        d['observed_at'] = datetime.datetime.fromisoformat(d['observed_at'])
        if d.get('evidence_locator'):
            d['evidence_locator'] = EvidenceLocator(**d['evidence_locator'])
        d['artifact_hashes'] = ArtifactHash(**d['artifact_hashes'])
        return cls(**d)
