"""
Acquisition contracts — the common interface for all adapters.
Every adapter returns AcquisitionResult with ContentSnapshot.
"""
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class AcquisitionStatus(Enum):
    """Status of an acquisition attempt."""
    OK = "OK"                    # Content acquired successfully
    BLOCKED = "BLOCKED"          # Site blocked the request
    INCOMPLETE = "INCOMPLETE"    # Partial content (bad boundary, truncated)
    FAILED = "FAILED"            # Network error, timeout, etc.
    CHALLENGE = "CHALLENGE"      # JS challenge detected


class ContentFormat(Enum):
    """Format of the acquired content."""
    MARKDOWN = "markdown"        # Crawl4AI markdown output
    HTML = "html"                # Raw HTML
    TEXT = "text"                # Plain text
    JSON = "json"                # Structured JSON


@dataclass
class ContentSnapshot:
    """
    A single content acquisition result.
    Immutable after creation — records exactly what was acquired.
    """
    # Source identity
    source_url: str
    final_url: str
    source_domain: str = ""
    
    # Content
    content: str = ""
    content_format: ContentFormat = ContentFormat.MARKDOWN
    content_hash: str = ""  # sha256 of content, first 16 chars
    
    # Acquisition metadata
    acquisition_method: str = ""  # e.g. "crawl4ai", "trafilatura"
    acquisition_status: AcquisitionStatus = AcquisitionStatus.FAILED
    http_status: int = 0
    elapsed_s: float = 0.0
    attempt_count: int = 1
    error_message: str = ""
    
    # Completeness signals
    has_article_body: bool = False
    article_boundary_confidence: float = 0.0  # 0-1, how confident we are about the boundary
    block_count: int = 0
    heading_count: int = 0
    
    # Metadata from page
    title: str = ""
    published_date: str = ""
    author: str = ""
    
    def __post_init__(self):
        """Compute content_hash if not set."""
        if not self.content_hash and self.content:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()[:16]
        if not self.source_domain and self.source_url:
            from urllib.parse import urlparse
            self.source_domain = urlparse(self.source_url).netloc


@dataclass
class AcquisitionResult:
    """
    Result of an acquisition attempt.
    May contain multiple snapshots from different adapters.
    """
    # Primary snapshot (best available)
    primary: Optional[ContentSnapshot] = None
    
    # All attempts (for debugging/consensus)
    attempts: List[ContentSnapshot] = field(default_factory=list)
    
    # Ladder state
    ladder_depth: int = 0  # How many adapters were tried
    fallback_used: bool = False
    
    @property
    def status(self) -> AcquisitionStatus:
        if self.primary:
            return self.primary.acquisition_status
        return AcquisitionStatus.FAILED
    
    @property
    def content(self) -> str:
        if self.primary:
            return self.primary.content
        return ""
    
    @property
    def content_hash(self) -> str:
        if self.primary:
            return self.primary.content_hash
        return ""
    
    @property
    def final_url(self) -> str:
        if self.primary:
            return self.primary.final_url
        return ""
    
    @property
    def acquisition_method(self) -> str:
        if self.primary:
            return self.primary.acquisition_method
        return ""
    
    def add_attempt(self, snapshot: ContentSnapshot):
        """Record an acquisition attempt."""
        self.attempts.append(snapshot)
        self.ladder_depth = len(self.attempts)
        
        # Update primary if this one is better
        if self._is_better(snapshot, self.primary):
            self.primary = snapshot
            self.fallback_used = self.ladder_depth > 1
    
    def _is_better(self, new: ContentSnapshot, current: Optional[ContentSnapshot]) -> bool:
        """Determine if new snapshot is better than current."""
        if current is None:
            return new.acquisition_status == AcquisitionStatus.OK
        if new.acquisition_status == AcquisitionStatus.OK:
            return current.acquisition_status != AcquisitionStatus.OK
        if new.acquisition_status == AcquisitionStatus.INCOMPLETE:
            return current.acquisition_status == AcquisitionStatus.FAILED
        return False
