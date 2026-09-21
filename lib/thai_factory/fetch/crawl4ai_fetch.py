"""
Crawl4AI-based fetch layer — Crawl4AI-only for HTML sources.

Architecture: Crawl4AI → DocumentSnapshot
For HTML sources: Crawl4AI is the ONLY acquisition method.
If Crawl4AI fails → explicit error (BLOCKED/TIMEOUT/CRAWL_FAILED).
Direct HTTP allowed only for true API/JSON endpoints.
"""
import asyncio
import hashlib
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import json

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False


@dataclass
class DocumentSnapshot:
    url: str
    final_url: str = ""
    http_status: int = 0
    fetched_at: str = ""
    raw_html: str = ""
    rendered_html: str = ""
    markdown: str = ""
    links: List[str] = field(default_factory=list)
    media: List[Dict] = field(default_factory=list)
    title: str = ""
    content_hash: str = ""
    fetch_method: str = "crawl4ai"
    published_date: str = ""
    crawl_id: Optional[str] = None  # Crawl4AI request ID or None
    evidence_regions: List[Dict] = field(default_factory=list)
    tables: List[Dict] = field(default_factory=list)
    headings: List[Dict] = field(default_factory=list)
    # Acquisition status
    acquisition_status: str = "OK"  # OK, BLOCKED, TIMEOUT, CRAWL_FAILED, API_ONLY


@dataclass
class FetchProfile:
    name: str
    mode: str = "static"  # static, spa, paginated, api
    wait_for: str = ""
    js_code: str = ""
    max_pages: int = 1
    rate_limit_ms: int = 1000
    cache_ttl_s: int = 3600
    timeout_s: int = 30
    requires_browser: bool = True  # False for true API endpoints
    delay_before_return_html: float = 0.0  # seconds to wait for JS challenge


PROFILES: Dict[str, FetchProfile] = {
    "headlightmag": FetchProfile(name="HeadLight Magazine", mode="static",
                                  rate_limit_ms=1500, requires_browser=True),
    "autospinn": FetchProfile(name="AutoSpinn", mode="static",
                               rate_limit_ms=1500, requires_browser=True),
    "autolifethailand": FetchProfile(name="AutoLife Thailand", mode="static",
                                      rate_limit_ms=1500, requires_browser=True,
                                      delay_before_return_html=7.0),
    "toyota_oem": FetchProfile(name="Toyota OEM API", mode="api",
                                rate_limit_ms=2000, requires_browser=False),
}

_cache: Dict[str, DocumentSnapshot] = {}
_last_fetch: Dict[str, float] = {}


def _cache_key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _get_cached(url: str, ttl_s: int) -> Optional[DocumentSnapshot]:
    key = _cache_key(url)
    if key in _cache:
        snap = _cache[key]
        try:
            fetched = datetime.fromisoformat(snap.fetched_at)
            age = (datetime.now(timezone.utc) - fetched).total_seconds()
            if age < ttl_s:
                return snap
        except (ValueError, TypeError):
            pass
    return None


def _rate_limit(domain: str, min_interval_ms: int):
    now = time.time() * 1000
    last = _last_fetch.get(domain, 0)
    wait = min_interval_ms - (now - last)
    if wait > 0:
        time.sleep(wait / 1000)
    _last_fetch[domain] = time.time() * 1000


def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc.replace("www.", "")


async def _async_crawl(url: str, profile: FetchProfile) -> DocumentSnapshot:
    browser_config = BrowserConfig(headless=True, browser_type="chromium")
    crawl_config = CrawlerRunConfig(
        word_count_threshold=10,
        wait_until="domcontentloaded",
        page_timeout=profile.timeout_s * 1000,
    )
    if profile.wait_for:
        crawl_config.wait_until = "networkidle"
        crawl_config.css_selector = profile.wait_for
    if profile.js_code:
        crawl_config.js_code = profile.js_code
    if profile.delay_before_return_html > 0:
        crawl_config.delay_before_return_html = profile.delay_before_return_html

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=crawl_config)

    # Extract markdown
    md = ""
    if hasattr(result.markdown, 'raw_markdown'):
        md = result.markdown.raw_markdown
    elif isinstance(result.markdown, str):
        md = result.markdown

    # Extract links
    links = []
    if isinstance(result.links, dict):
        for link_list in result.links.values():
            if isinstance(link_list, list):
                for a in link_list:
                    if isinstance(a, dict) and a.get("href"):
                        links.append(a["href"])

    # Extract media
    media = []
    if isinstance(result.media, dict):
        media = result.media.get("images", [])

    # Extract metadata
    meta = result.metadata if isinstance(result.metadata, dict) else {}

    snap = DocumentSnapshot(
        url=url,
        final_url=result.url or url,
        http_status=result.status_code or 0,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        raw_html=result.html or "",
        rendered_html=result.html or "",
        markdown=md,
        links=links,
        media=media,
        title=meta.get("title", ""),
        content_hash=hashlib.sha256((result.html or "")[:5000].encode()).hexdigest()[:16],
        fetch_method="crawl4ai",
        published_date=meta.get("article:published_time", ""),
        crawl_id=None,  # Crawl4AI doesn't expose request IDs in this API
    )

    # Check for Cloudflare / blocked content
    if md and ("Please wait while your request is being verified" in md
               or "Checking your browser" in md
               or len(md.strip()) < 100):
        snap.acquisition_status = "BLOCKED"
    elif result.status_code and result.status_code >= 400:
        snap.acquisition_status = "CRAWL_FAILED"
    elif not result.html or len(result.html) < 500:
        snap.acquisition_status = "CRAWL_FAILED"

    # Extract tables from HTML
    if result.html:
        import re
        table_matches = re.findall(r'<table[^>]*>(.*?)</table>', result.html, re.DOTALL | re.I)
        for i, table_html in enumerate(table_matches[:5]):
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.I)
            snap.tables.append({"index": i, "row_count": len(rows), "html": table_html[:2000]})

        heading_matches = re.finditer(r'<(h[1-6])[^>]*>(.*?)</\1>', result.html, re.DOTALL | re.I)
        for m in heading_matches:
            snap.headings.append({
                "level": m.group(1),
                "text": re.sub(r'<[^>]+>', '', m.group(2)).strip(),
                "position": m.start(),
            })

    return snap


def _fetch_http(url: str, profile: FetchProfile) -> DocumentSnapshot:
    """Direct HTTP for API/JSON endpoints only."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=profile.timeout_s)
        body = resp.read().decode("utf-8", errors="replace")
        return DocumentSnapshot(
            url=url, final_url=url, http_status=resp.status,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_html=body, markdown=body,
            content_hash=hashlib.sha256(body[:5000].encode()).hexdigest()[:16],
            fetch_method="http",
            acquisition_status="OK",
        )
    except Exception:
        return DocumentSnapshot(
            url=url, http_status=0, fetch_method="http_error",
            acquisition_status="CRAWL_FAILED",
        )


def crawl(url: str, profile_name: str = "default") -> DocumentSnapshot:
    domain = _extract_domain(url)
    # Profile lookup: try exact domain, then try name without TLD
    profile = PROFILES.get(profile_name)
    if not profile:
        profile = PROFILES.get(domain)
    if not profile:
        # Try matching without common TLDs
        for tld in ['.tv', '.com', '.co.th', '.net']:
            if domain.endswith(tld):
                base = domain[:-len(tld)]
                profile = PROFILES.get(base)
                if profile:
                    break
    if not profile:
        profile = FetchProfile(name=domain)

    cached = _get_cached(url, profile.cache_ttl_s)
    if cached:
        return cached

    _rate_limit(domain, profile.rate_limit_ms)

    # API mode: direct HTTP allowed
    if profile.mode == "api" or not profile.requires_browser:
        snap = _fetch_http(url, profile)
        _cache[_cache_key(url)] = snap
        return snap

    # HTML sources: Crawl4AI ONLY — no HTTP fallback
    if CRAWL4AI_AVAILABLE:
        try:
            loop = asyncio.new_event_loop()
            snap = loop.run_until_complete(_async_crawl(url, profile))
            loop.close()
            _cache[_cache_key(url)] = snap
            return snap
        except Exception as e:
            # Return explicit failure — do NOT fall back to HTTP
            return DocumentSnapshot(
                url=url, http_status=0, fetch_method="crawl4ai_error",
                acquisition_status="CRAWL_FAILED",
                fetched_at=datetime.now(timezone.utc).isoformat(),
                content_hash="",
            )

    # Crawl4AI not available: explicit failure
    return DocumentSnapshot(
        url=url, http_status=0, fetch_method="unavailable",
        acquisition_status="CRAWL_FAILED",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def crawl_many(urls: List[str], profile_name: str = "default") -> List[DocumentSnapshot]:
    results = []
    for url in urls:
        results.append(crawl(url, profile_name))
    return results
