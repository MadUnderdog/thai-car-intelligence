"""
Acquisition adapters — concrete implementations for each path.
Each adapter implements the same interface.
"""
import time
from typing import Optional
from .contracts import ContentSnapshot, AcquisitionResult, AcquisitionStatus, ContentFormat


class BaseAdapter:
    """Base class for all acquisition adapters."""
    
    name: str = "base"
    priority: int = 0  # Lower = tried first
    
    def acquire(self, url: str, timeout_s: float = 30) -> ContentSnapshot:
        """Acquire content from URL. Returns ContentSnapshot."""
        raise NotImplementedError
    
    def can_acquire(self, url: str) -> bool:
        """Check if this adapter can handle this URL."""
        return True


class Crawl4AIAdapter(BaseAdapter):
    """Primary adapter using Crawl4AI."""
    
    name = "crawl4ai"
    priority = 0
    
    def __init__(self):
        self._crawl_func = None
        self._cache = None
    
    def _get_crawl(self):
        if self._crawl_func is None:
            from thai_factory.fetch.crawl4ai_fetch import crawl, _cache
            self._crawl_func = crawl
            self._cache = _cache
        return self._crawl_func, self._cache
    
    def acquire(self, url: str, timeout_s: float = 60) -> ContentSnapshot:
        try:
            crawl, cache = self._get_crawl()
            cache.clear()
            start = time.time()
            doc = crawl(url)
            elapsed = time.time() - start
            
            status_map = {
                "OK": AcquisitionStatus.OK,
                "BLOCKED": AcquisitionStatus.BLOCKED,
                "CRAWL_FAILED": AcquisitionStatus.FAILED,
                "JS_CHALLENGE_TIMEOUT": AcquisitionStatus.CHALLENGE,
            }
            status = status_map.get(doc.acquisition_status, AcquisitionStatus.FAILED)
            
            return ContentSnapshot(
                source_url=url,
                final_url=doc.final_url or url,
                content=doc.markdown or "",
                content_format=ContentFormat.MARKDOWN,
                acquisition_method=self.name,
                acquisition_status=status,
                elapsed_s=elapsed,
                title=doc.title or "",
                error_message="" if status == AcquisitionStatus.OK else doc.acquisition_status,
            )
        except Exception as e:
            return ContentSnapshot(
                source_url=url,
                final_url=url,
                acquisition_method=self.name,
                acquisition_status=AcquisitionStatus.FAILED,
                error_message=str(e),
            )
    
    def can_acquire(self, url: str) -> bool:
        return True  # Crawl4AI can try any URL


class TrafilaturaAdapter(BaseAdapter):
    """Fallback adapter using trafilatura for article extraction."""
    
    name = "trafilatura"
    priority = 2  # After Playwright (priority 1)
    
    def __init__(self):
        self._available = None
    
    def _check_available(self):
        if self._available is None:
            try:
                import trafilatura
                self._available = True
            except ImportError:
                self._available = False
        return self._available
    
    def acquire(self, url: str, timeout_s: float = 30) -> ContentSnapshot:
        if not self._check_available():
            return ContentSnapshot(
                source_url=url,
                final_url=url,
                acquisition_method=self.name,
                acquisition_status=AcquisitionStatus.FAILED,
                error_message="trafilatura not installed",
            )
        
        try:
            import trafilatura
            start = time.time()
            
            # Download
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return ContentSnapshot(
                    source_url=url,
                    final_url=url,
                    acquisition_method=self.name,
                    acquisition_status=AcquisitionStatus.FAILED,
                    error_message="download failed",
                )
            
            # Extract main content
            result = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=True,
                output_format='txt',
                favor_precision=False,
                favor_recall=True,
            )
            
            elapsed = time.time() - start
            
            if not result:
                return ContentSnapshot(
                    source_url=url,
                    final_url=url,
                    acquisition_method=self.name,
                    acquisition_status=AcquisitionStatus.INCOMPLETE,
                    elapsed_s=elapsed,
                    error_message="extraction returned empty",
                )
            
            # Also extract metadata
            metadata = trafilatura.extract(
                downloaded,
                output_format='json',
                include_comments=False,
            )
            
            title = ""
            if metadata:
                import json
                try:
                    meta = json.loads(metadata)
                    title = meta.get("title", "")
                except:
                    pass
            
            return ContentSnapshot(
                source_url=url,
                final_url=url,
                content=result,
                content_format=ContentFormat.TEXT,
                acquisition_method=self.name,
                acquisition_status=AcquisitionStatus.OK,
                elapsed_s=elapsed,
                title=title,
                has_article_body=len(result) > 500,
                article_boundary_confidence=0.8,  # Trafilatura is good at article extraction
            )
        except Exception as e:
            return ContentSnapshot(
                source_url=url,
                final_url=url,
                acquisition_method=self.name,
                acquisition_status=AcquisitionStatus.FAILED,
                error_message=str(e),
            )
    
    def can_acquire(self, url: str) -> bool:
        return self._check_available()


class Newspaper4kAdapter(BaseAdapter):
    """Fallback adapter using newspaper4k for article metadata."""
    
    name = "newspaper4k"
    priority = 3
    
    def __init__(self):
        self._available = None
    
    def _check_available(self):
        if self._available is None:
            try:
                import newspaper
                self._available = True
            except ImportError:
                self._available = False
        return self._available
    
    def acquire(self, url: str, timeout_s: float = 30) -> ContentSnapshot:
        if not self._check_available():
            return ContentSnapshot(
                source_url=url,
                final_url=url,
                acquisition_method=self.name,
                acquisition_status=AcquisitionStatus.FAILED,
                error_message="newspaper4k not installed",
            )
        
        try:
            import newspaper
            start = time.time()
            article = newspaper.Article(url)
            article.download()
            article.parse()
            elapsed = time.time() - start
            
            content = article.text or ""
            if not content:
                return ContentSnapshot(
                    source_url=url,
                    final_url=url,
                    acquisition_method=self.name,
                    acquisition_status=AcquisitionStatus.INCOMPLETE,
                    elapsed_s=elapsed,
                    error_message="no text extracted",
                )
            
            return ContentSnapshot(
                source_url=url,
                final_url=url,
                content=content,
                content_format=ContentFormat.TEXT,
                acquisition_method=self.name,
                acquisition_status=AcquisitionStatus.OK,
                elapsed_s=elapsed,
                title=article.title or "",
                published_date=str(article.publish_date) if article.publish_date else "",
                author=", ".join(article.authors) if article.authors else "",
                has_article_body=len(content) > 500,
                article_boundary_confidence=0.7,
            )
        except Exception as e:
            return ContentSnapshot(
                source_url=url,
                final_url=url,
                acquisition_method=self.name,
                acquisition_status=AcquisitionStatus.FAILED,
                error_message=str(e),
            )
    
    def can_acquire(self, url: str) -> bool:
        return self._check_available()
