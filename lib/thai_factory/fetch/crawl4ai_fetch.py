"""
Crawl4AI-based fetch layer for structured web acquisition.

Provides:
- crawl(url, config) -> DocumentSnapshot
- crawl_many(urls, config) -> list[DocumentSnapshot]
- Per-source fetch profiles (static, SPA, paginated, API)
- Cache/retry/rate-limit
"""
import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Crawl4AI imports
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False


@dataclass
class DocumentSnapshot:
    """Unified document snapshot from any fetch method."""
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
    # Structured extraction hints
    evidence_regions: List[Dict] = field(default_factory=list)
    tables: List[Dict] = field(default_factory=list)
    headings: List[Dict] = field(default_factory=list)


@dataclass
class FetchProfile:
    """Per-source fetch configuration."""
    name: str
    mode: str = "static"  # static, spa, paginated, api
    wait_for: str = ""  # CSS selector or condition
    js_code: str = ""  # JS to execute
    max_pages: int = 1
    rate_limit_ms: int = 1000
    cache_ttl_s: int = 3600
    timeout_s: int = 30


# ─── Fetch Profiles ────────────────────────────────────────────────

PROFILES: Dict[str, FetchProfile] = {
    "headlightmag": FetchProfile(
        name="HeadLight Magazine",
        mode="static",
        rate_limit_ms=1500,
        cache_ttl_s=7200,
    ),
    "9carthai": FetchProfile(
        name="9CARTHAI",
        mode="static",
        rate_limit_ms=1500,
        cache_ttl_s=7200,
    ),
    "autospinn": FetchProfile(
        name="AutoSpinn",
        mode="static",
        rate_limit_ms=1500,
        cache_ttl_s=7200,
    ),
    "autolifethailand": FetchProfile(
        name="AutoLife Thailand",
        mode="static",
        rate_limit_ms=1500,
        cache_ttl_s=7200,
    ),
    "car2day": FetchProfile(
        name="Car2Day",
        mode="static",
        rate_limit_ms=1500,
        cache_ttl_s=7200,
    ),
    "toyota_oem": FetchProfile(
        name="Toyota OEM API",
        mode="api",
        rate_limit_ms=2000,
        cache_ttl_s=86400,
    ),
}


# ─── Cache ─────────────────────────────────────────────────────────

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


def _rate_limit(domain: str, ms: int):
    now = time.time() * 1000
    last = _last_fetch.get(domain, 0)
    wait = (ms - (now - last)) / 1000
    if wait > 0:
        time.sleep(wait)
    _last_fetch[domain] = time.time() * 1000


# ─── Crawl4AI Fetch ────────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc.replace("www.", "")


async def _async_crawl(url: str, profile: FetchProfile) -> DocumentSnapshot:
    """Single URL crawl using Crawl4AI."""
    browser_config = BrowserConfig(
        headless=True,
        browser_type="chromium",
    )

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

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=crawl_config)

    snap = DocumentSnapshot(
        url=url,
        final_url=result.url or url,
        http_status=result.status_code or 0,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        raw_html=result.html or "",
        rendered_html=result.html or "",
        markdown=(result.markdown.raw_markdown if hasattr(result.markdown, 'raw_markdown') else result.markdown if isinstance(result.markdown, str) else ""),
        links=[a.get("href", "") for a in ((result.links or {}).get("internal", []) + (result.links or {}).get("external", [])) if isinstance(a, dict) and a.get("href")],
        media=(result.media or {}).get("images", []) if isinstance(result.media, dict) else [],
        title=result.metadata.get("title", "") if result.metadata else "",
        content_hash=hashlib.sha256((result.html or "")[:5000].encode()).hexdigest()[:16],
        fetch_method="crawl4ai",
        published_date=result.metadata.get("article:published_time", "") if result.metadata else "",
    )

    # Extract tables and headings for evidence paths
    if result.html:
        import re
        # Extract tables
        table_matches = re.findall(r'<table[^>]*>(.*?)</table>', result.html, re.DOTALL | re.I)
        for i, table_html in enumerate(table_matches[:5]):
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.I)
            snap.tables.append({
                "index": i,
                "row_count": len(rows),
                "html": table_html[:2000],
            })

        # Extract headings with context
        heading_matches = re.finditer(r'<(h[1-6])[^>]*>(.*?)</\1>', result.html, re.DOTALL | re.I)
        for m in heading_matches:
            snap.headings.append({
                "level": m.group(1),
                "text": re.sub(r'<[^>]+>', '', m.group(2)).strip(),
                "position": m.start(),
            })

    return snap


def crawl(url: str, profile_name: str = "default") -> DocumentSnapshot:
    """
    Crawl a single URL using the appropriate fetch method.
    Returns DocumentSnapshot with structured evidence.
    """
    domain = _extract_domain(url)
    profile = PROFILES.get(profile_name, PROFILES.get(domain, FetchProfile(name=domain)))

    # Check cache
    cached = _get_cached(url, profile.cache_ttl_s)
    if cached:
        return cached

    # Rate limit
    _rate_limit(domain, profile.rate_limit_ms)

    # API mode: use direct HTTP
    if profile.mode == "api":
        return _fetch_http(url, profile)

    # Crawl4AI mode
    if CRAWL4AI_AVAILABLE:
        try:
            loop = asyncio.new_event_loop()
            snap = loop.run_until_complete(_async_crawl(url, profile))
            loop.close()
            _cache[_cache_key(url)] = snap
            return snap
        except Exception as e:
            # Fallback to HTTP
            pass

    return _fetch_http(url, profile)


def crawl_many(urls: List[str], profile_name: str = "default") -> List[DocumentSnapshot]:
    """Crawl multiple URLs with rate limiting."""
    results = []
    for url in urls:
        results.append(crawl(url, profile_name))
    return results


# ─── HTTP Fallback ─────────────────────────────────────────────────

def _fetch_http(url: str, profile: FetchProfile) -> DocumentSnapshot:
    """Direct HTTP fetch (for APIs or fallback)."""
    import re
    from urllib.request import Request, urlopen

    domain = _extract_domain(url)
    _rate_limit(domain, profile.rate_limit_ms)

    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/131"})
        with urlopen(req, timeout=profile.timeout_s) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            final_url = resp.url
            status = resp.status

        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        # Extract tables
        tables = []
        table_matches = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.I)
        for i, table_html in enumerate(table_matches[:5]):
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.I)
            tables.append({"index": i, "row_count": len(rows), "html": table_html[:2000]})

        # Extract headings
        headings = []
        heading_matches = re.finditer(r'<(h[1-6])[^>]*>(.*?)</\1>', html, re.DOTALL | re.I)
        for m in heading_matches:
            headings.append({
                "level": m.group(1),
                "text": re.sub(r'<[^>]+>', '', m.group(2)).strip(),
                "position": m.start(),
            })

        # Extract title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.DOTALL)
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""

        # Extract published date
        pub_match = re.search(r'article:published_time["\s]+content="([^"]+)"', html, re.I)
        if not pub_match:
            pub_match = re.search(r'published_date["\s]+content="([^"]+)"', html, re.I)
        pub_date = pub_match.group(1) if pub_match else ""

        snap = DocumentSnapshot(
            url=url,
            final_url=final_url,
            http_status=status,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_html=html,
            rendered_html=html,
            markdown=text,
            title=title,
            content_hash=hashlib.sha256(html[:5000].encode()).hexdigest()[:16],
            fetch_method="http",
            published_date=pub_date,
            tables=tables,
            headings=headings,
        )
        _cache[_cache_key(url)] = snap
        return snap

    except Exception as e:
        return DocumentSnapshot(
            url=url, final_url=url, http_status=0,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            content_hash="", fetch_method="http_error",
        )
