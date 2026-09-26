"""Multi-path acquisition ladder for Thai automotive content."""
from .contracts import ContentSnapshot, AcquisitionResult, AcquisitionStatus
from .ladder import AcquisitionLadder
from .adapters import Crawl4AIAdapter, TrafilaturaAdapter

__all__ = [
    "ContentSnapshot", "AcquisitionResult", "AcquisitionStatus",
    "AcquisitionLadder", "Crawl4AIAdapter", "TrafilaturaAdapter",
]
