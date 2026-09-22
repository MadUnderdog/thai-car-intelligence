"""
Acquisition Ladder — orchestrates adapter fallbacks.
Primary succeeds → stop. Primary fails → fallback.
"""
from typing import List, Optional
from .contracts import ContentSnapshot, AcquisitionResult, AcquisitionStatus
from .adapters import BaseAdapter, Crawl4AIAdapter, TrafilaturaAdapter, Newspaper4kAdapter


class AcquisitionLadder:
    """
    Multi-path acquisition ladder.
    
    Policy:
    1. Try primary adapter (Crawl4AI)
    2. If OK with good completeness → stop
    3. If failed/blocked/incomplete → try next adapter
    4. Record all attempts
    5. Never bypass validation
    """
    
    def __init__(self, adapters: Optional[List[BaseAdapter]] = None):
        if adapters is None:
            # Default ladder: Crawl4AI → Trafilatura → Newspaper4k
            adapters = [
                Crawl4AIAdapter(),    # priority 0
                TrafilaturaAdapter(), # priority 2
                Newspaper4kAdapter(), # priority 3
            ]
        # Sort by priority
        self.adapters = sorted(adapters, key=lambda a: a.priority)
    
    def acquire(self, url: str, timeout_s: float = 60) -> AcquisitionResult:
        """
        Run the acquisition ladder for a URL.
        Returns AcquisitionResult with all attempts.
        """
        result = AcquisitionResult()
        
        for adapter in self.adapters:
            if not adapter.can_acquire(url):
                continue
            
            snapshot = adapter.acquire(url, timeout_s=timeout_s)
            result.add_attempt(snapshot)
            
            # If OK with good completeness → stop
            if snapshot.acquisition_status == AcquisitionStatus.OK:
                if snapshot.has_article_body or len(snapshot.content) > 1000:
                    break
            
            # If blocked → try fallback
            if snapshot.acquisition_status in (AcquisitionStatus.BLOCKED, AcquisitionStatus.CHALLENGE):
                continue
            
            # If failed → try fallback
            if snapshot.acquisition_status == AcquisitionStatus.FAILED:
                continue
        
        return result
    
    def register(self, adapter: BaseAdapter):
        """Register a new adapter."""
        self.adapters.append(adapter)
        self.adapters.sort(key=lambda a: a.priority)
    
    def list_adapters(self):
        """List registered adapters."""
        return [(a.name, a.priority) for a in self.adapters]
