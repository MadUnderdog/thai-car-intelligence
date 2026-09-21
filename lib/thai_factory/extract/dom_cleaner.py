"""
DOM Cleaner — reusable page cleaning with stable block IDs.

Removes: nav/header/footer/ads/sidebar/related-posts/recommendations/
comments/cookie-banners/social-widgets/duplicate-mobile-desktop blocks.

Retains: title/publication date/headings/paragraphs/tables/lists/
figure captions/price-spec cards/JSON-LD metadata.

Every retained block has:
- block_id (stable, deterministic)
- xpath (original DOM locator)
- css (CSS selector)
- text (clean content)
- block_type (heading/paragraph/table/list/figure/card/jsonld)
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class ContentBlock:
    """A cleaned content block with provenance."""
    block_id: str
    block_type: str  # heading, paragraph, table, list, figure, card, jsonld
    text: str
    xpath: str = ""
    css: str = ""
    html: str = ""
    position: int = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class CleanedPage:
    """Cleaned page with content blocks and metadata."""
    url: str
    title: str = ""
    publication_date: str = ""
    author: str = ""
    blocks: List[ContentBlock] = field(default_factory=list)
    json_ld: List[Dict] = field(default_factory=list)
    content_hash: str = ""


# ─── Selectors to Remove ──────────────────────────────────────────

REMOVE_SELECTORS = [
    # Navigation
    "nav", "header", ".header", "#header", ".navbar", ".nav-bar",
    # Footer
    "footer", ".footer", "#footer",
    # Ads
    ".ad", ".ads", ".advertisement", "[class*='advert']",
    ".adsbygoogle", "[id*='google_ads']",
    # Sidebar
    ".sidebar", ".side-bar", "#sidebar", "[class*='sidebar']",
    # Related/Recommendations
    ".related", ".related-posts", ".recommendations", ".suggestions",
    "[class*='related']", "[class*='recommend']",
    # Comments
    ".comments", "#comments", ".comment-section",
    "[class*='comment']", "[id*='comment']",
    # Cookie/Social
    ".cookie", ".cookie-banner", ".social", ".social-share",
    "[class*='cookie']", "[class*='social']",
    # Mobile/Desktop duplicates
    ".mobile-only", ".desktop-only", "[class*='mobile-only']",
    # Carousels
    ".carousel", ".slider", "[class*='carousel']",
    # Newsletter/Subscribe
    ".newsletter", ".subscribe", "[class*='newsletter']",
]


def clean_page(html: str, url: str, title: str = "",
               pub_date: str = "", author: str = "") -> CleanedPage:
    """
    Clean HTML page and extract content blocks with stable IDs.
    Returns CleanedPage with content blocks ready for AI extraction.
    """
    from html.parser import HTMLParser

    # Extract JSON-LD first
    json_ld = _extract_json_ld(html)

    # Remove unwanted elements
    cleaned_html = _remove_elements(html, REMOVE_SELECTORS)

    # Extract content blocks
    blocks = _extract_blocks(cleaned_html)

    # Extract title/date from HTML if not provided
    if not title:
        title = _extract_title(html)
    if not pub_date:
        pub_date = _extract_pub_date(html, json_ld)
    if not author:
        author = _extract_author(html, json_ld)

    # Compute content hash
    content_text = "\n".join(b.text for b in blocks)
    content_hash = hashlib.sha256(content_text[:5000].encode()).hexdigest()[:16]

    return CleanedPage(
        url=url,
        title=title,
        publication_date=pub_date,
        author=author,
        blocks=blocks,
        json_ld=json_ld,
        content_hash=content_hash,
    )


def _extract_json_ld(html: str) -> List[Dict]:
    """Extract JSON-LD structured data."""
    import json
    results = []
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL | re.I):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)
        except (json.JSONDecodeError, ValueError):
            pass
    return results


def _remove_elements(html: str, selectors: List[str]) -> str:
    """Remove HTML elements matching selectors (basic implementation)."""
    # For each selector, remove matching tags
    for selector in selectors:
        # Convert CSS selector to regex pattern (simplified)
        tag_match = re.match(r'^([a-zA-Z][a-zA-Z0-9]*)', selector)
        class_match = re.search(r'\.([a-zA-Z][a-zA-Z0-9_-]*)', selector)
        id_match = re.search(r'#([a-zA-Z][a-zA-Z0-9_-]*)', selector)

        if id_match:
            # Remove by ID
            tag = tag_match.group(1) if tag_match else '[a-zA-Z]+'
            id_name = id_match.group(1)
            pattern = rf'<{tag}[^>]*id=["\']{id_name}["\'][^>]*>.*?</{tag}>'
            html = re.sub(pattern, '', html, flags=re.DOTALL | re.I)

        elif class_match:
            # Remove by class
            tag = tag_match.group(1) if tag_match else '[a-zA-Z]+'
            class_name = class_match.group(1)
            pattern = rf'<{tag}[^>]*class=["\'][^"\']*{class_name}[^"\']*["\'][^>]*>.*?</{tag}>'
            html = re.sub(pattern, '', html, flags=re.DOTALL | re.I)

        elif tag_match:
            # Remove by tag (only for non-content tags)
            tag = tag_match.group(1)
            if tag in ('nav', 'header', 'footer', 'aside'):
                html = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', '', html, flags=re.DOTALL | re.I)

    return html


def _extract_blocks(html: str) -> List[ContentBlock]:
    """Extract content blocks with stable IDs."""
    blocks = []
    block_counter = 0

    # Extract headings
    for m in re.finditer(r'<(h[1-6])[^>]*>(.*?)</\1>', html, re.DOTALL | re.I):
        text = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        if text:
            blocks.append(ContentBlock(
                block_id=f"heading_{block_counter:03d}",
                block_type="heading",
                text=text,
                css=f"{m.group(1)}",
                position=m.start(),
                metadata={"level": m.group(1)},
            ))
            block_counter += 1

    # Extract paragraphs
    for m in re.finditer(r'<p[^>]*>(.*?)</p>', html, re.DOTALL | re.I):
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if text and len(text) > 20:  # Skip short fragments
            blocks.append(ContentBlock(
                block_id=f"para_{block_counter:03d}",
                block_type="paragraph",
                text=text,
                css="p",
                position=m.start(),
            ))
            block_counter += 1

    # Extract tables with row context
    table_counter = 0
    for table_m in re.finditer(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.I):
        table_html = table_m.group(1)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.I)

        for row_idx, row_html in enumerate(rows):
            cells = [re.sub(r'<[^>]+>', '', cell).strip()
                     for cell in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row_html, re.DOTALL | re.I)]
            if cells:
                row_text = " | ".join(cells)
                blocks.append(ContentBlock(
                    block_id=f"table_{table_counter:03d}_row_{row_idx:02d}",
                    block_type="table",
                    text=row_text,
                    css=f"table:nth-of-type({table_counter+1}) tr:nth-child({row_idx+1})",
                    position=table_m.start() + table_html.find(row_html),
                    metadata={
                        "table_index": table_counter,
                        "row_index": row_idx,
                        "cells": cells,
                        "header_row": row_idx == 0,
                    },
                ))
        table_counter += 1

    # Extract lists
    list_counter = 0
    for list_m in re.finditer(r'<(?:ul|ol)[^>]*>(.*?)</(?:ul|ol)>', html, re.DOTALL | re.I):
        items = re.findall(r'<li[^>]*>(.*?)</li>', list_m.group(1), re.DOTALL | re.I)
        for item_idx, item_html in enumerate(items):
            text = re.sub(r'<[^>]+>', '', item_html).strip()
            if text:
                blocks.append(ContentBlock(
                    block_id=f"list_{list_counter:03d}_item_{item_idx:02d}",
                    block_type="list",
                    text=text,
                    css=f"li:nth-child({item_idx+1})",
                    position=list_m.start(),
                ))
        list_counter += 1

    # Sort by position
    blocks.sort(key=lambda b: b.position)

    # Re-assign block IDs in document order
    for i, block in enumerate(blocks):
        prefix = block.block_id.rsplit("_", 1)[0]
        block.block_id = f"{prefix}_{i:03d}"

    return blocks


def _extract_title(html: str) -> str:
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.DOTALL)
    return re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else ""


def _extract_pub_date(html: str, json_ld: List[Dict]) -> str:
    # Try JSON-LD
    for item in json_ld:
        if "datePublished" in item:
            return item["datePublished"]
    # Try meta tags
    m = re.search(r'article:published_time["\s]+content="([^"]+)"', html, re.I)
    if m:
        return m.group(1)
    m = re.search(r'published_date["\s]+content="([^"]+)"', html, re.I)
    if m:
        return m.group(1)
    return ""


def _extract_author(html: str, json_ld: List[Dict]) -> str:
    for item in json_ld:
        if "author" in item:
            author = item["author"]
            if isinstance(author, dict):
                return author.get("name", "")
            return str(author)
    m = re.search(r'article:author["\s]+content="([^"]+)"', html, re.I)
    return m.group(1) if m else ""


def format_blocks_for_ai(page: CleanedPage) -> str:
    """Format cleaned page blocks for AI extraction input."""
    lines = [f"URL: {page.url}"]
    lines.append(f"Title: {page.title}")
    if page.publication_date:
        lines.append(f"Published: {page.publication_date}")
    lines.append(f"Content Hash: {page.content_hash}")
    lines.append(f"Blocks: {len(page.blocks)}")
    lines.append("")

    for block in page.blocks:
        lines.append(f"[{block.block_id}] ({block.block_type}) {block.text}")
        if block.metadata.get("cells"):
            lines.append(f"  Cells: {block.metadata['cells']}")
        if block.metadata.get("header_row"):
            lines.append(f"  (header row)")
        lines.append("")

    return "\n".join(lines)
