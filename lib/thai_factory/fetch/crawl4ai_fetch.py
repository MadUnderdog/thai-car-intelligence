"""
Crawl4AI-based fetch layer — Crawl4AI-only for HTML sources.

Challenge handling:
- Detect JS challenge pages (title/body markers)
- Retry with increasing delays: 3s → 7s → 12s
- Return JS_CHALLENGE_TIMEOUT if challenge can't resolve
- Record attempt metadata for provenance
"""
import asyncio
import hashlib
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import json

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False

# ─── Challenge Detection ───────────────────────────────────────────
CHALLENGE_TITLE_MARKERS = [
    "One moment, please...",
    "Please wait while your request is being verified",
    "Checking your browser",
    "Just a moment...",
    "Attention Required!",
    "Access denied",
]
CHALLENGE_BODY_MARKERS = [
    "Please wait while your request is being verified",
    "Checking your browser",
    "Verify you are human",
    "Checking if the site connection is secure",
    "Enable JavaScript and cookies to continue",
]
CHALLENGE_RETRY_DELAYS = [3.0, 7.0, 12.0]  # increasing delays per attempt


def _is_challenge_page(title: str, markdown: str) -> bool:
    """Detect if the page is a JS challenge / bot detection page."""
    title_lower = title.lower()
    for marker in CHALLENGE_TITLE_MARKERS:
        if marker.lower() in title_lower:
            return True
    md_lower = markdown[:2000].lower()
    for marker in CHALLENGE_BODY_MARKERS:
        if marker.lower() in md_lower:
            return True
    # Very short markdown after large HTML = likely challenge
    # Only check if we have SOME markdown but it's suspiciously short
    # Don't flag legitimately short pages (like empty category pages)
    return False


@dataclass
class CrawlAttempt:
    """Record of a single crawl attempt."""
    attempt_number: int
    delay_used: float
    success: bool
    is_challenge: bool
    http_status: int
    final_url: str
    content_hash: str
    elapsed_s: float
    title: str = ""


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
    crawl_id: Optional[str] = None
    evidence_regions: List[Dict] = field(default_factory=list)
    # Acquisition status
    acquisition_status: str = "OK"  # OK, BLOCKED, JS_CHALLENGE_TIMEOUT, CRAWL_FAILED, API_ONLY
    # Attempt provenance
    attempts: List[CrawlAttempt] = field(default_factory=list)
    retry_count: int = 0


@dataclass
class FetchProfile:
    name: str
    mode: str = "static"
    wait_for: str = ""
    js_code: str = ""
    max_pages: int = 1
    rate_limit_ms: int = 1000
    cache_ttl_s: int = 3600
    timeout_s: int = 30
    requires_browser: bool = True
    # Challenge retry policy
    has_js_challenge: bool = False  # True for sources with JS challenge pages
    challenge_retry_delays: List[float] = field(default_factory=lambda: list(CHALLENGE_RETRY_DELAYS))


PROFILES: Dict[str, FetchProfile] = {
    "headlightmag": FetchProfile(name="HeadLight Magazine", mode="static",
                                  rate_limit_ms=1500, requires_browser=True),
    "autospinn": FetchProfile(name="AutoSpinn", mode="static",
                               rate_limit_ms=1500, requires_browser=True),
    "autolifethailand": FetchProfile(name="AutoLife Thailand", mode="static",
                                      rate_limit_ms=1500, requires_browser=True,
                                      has_js_challenge=True,
                                      challenge_retry_delays=[3.0, 7.0, 12.0]),
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


async def _single_crawl(url: str, delay: float) -> tuple:
    """Single Crawl4AI crawl attempt. Returns (result_html, result_markdown, result_metadata, result_url, result_status)."""
    browser_config = BrowserConfig(headless=True, browser_type="chromium")
    crawl_config = CrawlerRunConfig(
        word_count_threshold=10,
        wait_until="domcontentloaded",
        page_timeout=30000,
        delay_before_return_html=delay,
    )
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=crawl_config)
    return result


async def _async_crawl_with_retry(url: str, profile: FetchProfile) -> DocumentSnapshot:
    """Crawl with retry policy for JS challenge pages."""
    attempts = []
    delays = profile.challenge_retry_delays if profile.has_js_challenge else [0.0]

    for attempt_num, delay in enumerate(delays):
        start_time = time.time()
        try:
            result = await _single_crawl(url, delay)
        except Exception as e:
            elapsed = time.time() - start_time
            attempts.append(CrawlAttempt(
                attempt_number=attempt_num + 1, delay_used=delay,
                success=False, is_challenge=False, http_status=0,
                final_url=url, content_hash="", elapsed_s=elapsed,
            ))
            continue

        elapsed = time.time() - start_time

        # Extract markdown
        md = ""
        if hasattr(result.markdown, 'raw_markdown'):
            md = result.markdown.raw_markdown
        elif isinstance(result.markdown, str):
            md = result.markdown

        # Extract metadata
        meta = result.metadata if isinstance(result.metadata, dict) else {}
        title = meta.get("title", "")

        content_hash = hashlib.sha256((result.html or "")[:5000].encode()).hexdigest()[:16]

        is_challenge = _is_challenge_page(title, md)
        is_success = not is_challenge and len(md.strip()) > 100

        attempts.append(CrawlAttempt(
            attempt_number=attempt_num + 1, delay_used=delay,
            success=is_success, is_challenge=is_challenge,
            http_status=result.status_code or 0,
            final_url=result.url or url,
            content_hash=content_hash,
            elapsed_s=elapsed,
            title=title,
        ))

        if is_success:
            # Build successful snapshot
            links = []
            if isinstance(result.links, dict):
                for link_list in result.links.values():
                    if isinstance(link_list, list):
                        for a in link_list:
                            if isinstance(a, dict) and a.get("href"):
                                links.append(a["href"])

            media = []
            if isinstance(result.media, dict):
                media = result.media.get("images", [])

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
                title=title,
                content_hash=content_hash,
                fetch_method="crawl4ai",
                published_date=meta.get("article:published_time", ""),
                crawl_id=None,
                acquisition_status="OK",
                attempts=attempts,
                retry_count=attempt_num,
            )
            return snap

    # All attempts failed
    last = attempts[-1] if attempts else None
    status = "JS_CHALLENGE_TIMEOUT" if any(a.is_challenge for a in attempts) else "CRAWL_FAILED"

    return DocumentSnapshot(
        url=url,
        final_url=last.final_url if last else url,
        http_status=last.http_status if last else 0,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        raw_html="",
        markdown="",
        content_hash="",
        fetch_method="crawl4ai",
        acquisition_status=status,
        attempts=attempts,
        retry_count=len(attempts),
    )


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
    profile = PROFILES.get(profile_name)
    if not profile:
        profile = PROFILES.get(domain)
    if not profile:
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
            snap = loop.run_until_complete(_async_crawl_with_retry(url, profile))
            loop.close()
            _cache[_cache_key(url)] = snap
            return snap
        except Exception as e:
            return DocumentSnapshot(
                url=url, http_status=0, fetch_method="crawl4ai_error",
                acquisition_status="CRAWL_FAILED",
                fetched_at=datetime.now(timezone.utc).isoformat(),
                content_hash="",
            )

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
