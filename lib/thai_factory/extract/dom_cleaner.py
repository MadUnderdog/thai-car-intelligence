"""
DOM Cleaner — BeautifulSoup-based with real CSS/XPath provenance.

Every ContentBlock has:
- deterministic block_id from DOM path + content hash
- real CSS selector
- real XPath
- exact original HTML fragment
- parent heading/section context
- table index + row + cell indexes
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag


@dataclass
class ContentBlock:
    """A cleaned content block with real DOM provenance."""
    block_id: str  # deterministic: sha256(xpath + block_type + content_hash)
    block_type: str  # heading, paragraph, table_cell, list_item
    text: str
    css: str  # real CSS selector
    xpath: str  # real XPath
    html: str  # original HTML fragment
    position: int = 0
    heading_context: str = ""  # parent heading text
    table_index: int = -1
    row_index: int = -1
    cell_index: int = -1
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


REMOVE_TAGS = {"nav", "header", "footer", "aside", "script", "style",
               "noscript", "iframe", "form", "button", "input", "select"}
REMOVE_CLASSES = {"sidebar", "side-bar", "ad", "ads", "advertisement",
                  "related", "recommend", "comment", "cookie", "social",
                  "newsletter", "subscribe", "carousel", "slider",
                  "mobile-only", "desktop-only", "popup", "modal"}


def clean_page(html: str, url: str, title: str = "",
               pub_date: str = "", author: str = "") -> CleanedPage:
    """Clean HTML with real DOM parsing. Returns CleanedPage with provenance."""
    soup = BeautifulSoup(html, "lxml")

    # Extract JSON-LD
    json_ld = _extract_json_ld(soup)

    # Extract title/date from HTML if not provided
    if not title:
        title = _extract_title(soup)
    if not pub_date:
        pub_date = _extract_pub_date(soup, json_ld)
    if not author:
        author = _extract_author(soup, json_ld)

    # Remove unwanted elements
    _remove_elements(soup)

    # Find article content area
    content_root = soup.find("article") or soup.find("main") or soup.body or soup

    # Extract content blocks with real DOM provenance
    blocks = _extract_blocks(content_root, soup)

    # Compute content hash
    content_text = "\n".join(b.text for b in blocks)
    content_hash = hashlib.sha256(content_text[:5000].encode()).hexdigest()[:16]

    return CleanedPage(
        url=url, title=title, publication_date=pub_date,
        author=author, blocks=blocks, json_ld=json_ld,
        content_hash=content_hash,
    )


def _extract_json_ld(soup: BeautifulSoup) -> List[Dict]:
    import json
    results = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)
        except (json.JSONDecodeError, ValueError):
            pass
    return results


def _remove_elements(soup: BeautifulSoup):
    """Remove unwanted elements by tag and class."""
    for tag_name in REMOVE_TAGS:
        for el in soup.find_all(tag_name):
            el.decompose()

    for el in soup.find_all(True):
        classes = " ".join(el.get("class", []))
        el_id = el.get("id", "")
        combined = f"{classes} {el_id}".lower()
        if any(cls in combined for cls in REMOVE_CLASSES):
            el.decompose()


def _get_real_css(el: Tag, root: BeautifulSoup) -> str:
    """Generate real CSS selector for an element."""
    path = []
    current = el
    while current and current != root and current.name:
        parent = current.parent
        if parent:
            siblings = [s for s in parent.children if isinstance(s, Tag) and s.name == current.name]
            if len(siblings) > 1:
                idx = siblings.index(current) + 1
                path.append(f"{current.name}:nth-of-type({idx})")
            else:
                path.append(current.name)
        else:
            path.append(current.name)
        current = parent
    path.reverse()
    return " > ".join(path) if path else el.name


def _get_real_xpath(el: Tag, root: BeautifulSoup) -> str:
    """Generate real XPath for an element."""
    path = []
    current = el
    while current and current != root:
        if current.name:
            parent = current.parent
            if parent:
                siblings = [s for s in parent.children if isinstance(s, Tag) and s.name == current.name]
                if len(siblings) > 1:
                    idx = siblings.index(current) + 1
                    path.append(f"{current.name}[{idx}]")
                else:
                    path.append(current.name)
            else:
                path.append(current.name)
        current = current.parent
    path.reverse()
    return "/" + "/".join(path)


def _compute_block_id(xpath: str, block_type: str, text: str) -> str:
    """Deterministic block_id from DOM path + type + content hash."""
    content_hash = hashlib.sha256(text.encode()).hexdigest()[:8]
    raw = f"{xpath}|{block_type}|{content_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _find_preceding_heading(el: Tag, root: BeautifulSoup) -> str:
    """Find the nearest preceding heading for context."""
    for prev in el.previous_siblings:
        if isinstance(prev, Tag):
            if prev.name and prev.name.startswith("h"):
                return prev.get_text(strip=True)
            for child in prev.find_all(True):
                if child.name and child.name.startswith("h"):
                    return child.get_text(strip=True)
    parent = el.parent
    if parent:
        for prev in parent.previous_siblings:
            if isinstance(prev, Tag) and prev.name and prev.name.startswith("h"):
                return prev.get_text(strip=True)
    return ""


def _get_position(el: Tag, soup: BeautifulSoup) -> int:
    """Get approximate position in document for sorting."""
    html_str = str(soup)
    el_str = str(el)
    idx = html_str.find(el_str[:100])
    return idx if idx >= 0 else 0


def _extract_blocks(content_root: Tag, soup: BeautifulSoup) -> List[ContentBlock]:
    """Extract content blocks with real DOM provenance."""
    blocks = []

    # Headings
    for el in content_root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = el.get_text(strip=True)
        if text and len(text) > 2:
            xpath = _get_real_xpath(el, soup)
            css = _get_real_css(el, soup)
            blocks.append(ContentBlock(
                block_id=_compute_block_id(xpath, "heading", text),
                block_type="heading", text=text, css=css, xpath=xpath,
                html=str(el), position=_get_position(el, soup),
                metadata={"level": el.name},
            ))

    # Paragraphs
    for el in content_root.find_all("p"):
        text = el.get_text(strip=True)
        if text and len(text) > 20:
            xpath = _get_real_xpath(el, soup)
            css = _get_real_css(el, soup)
            blocks.append(ContentBlock(
                block_id=_compute_block_id(xpath, "paragraph", text),
                block_type="paragraph", text=text, css=css, xpath=xpath,
                html=str(el), position=_get_position(el, soup),
                heading_context=_find_preceding_heading(el, soup),
            ))

    # Tables — each cell is a block with full row context
    for t_idx, table in enumerate(content_root.find_all("table")):
        rows = table.find_all("tr")
        for r_idx, row in enumerate(rows):
            cells = row.find_all(["td", "th"])
            row_text = " | ".join(c.get_text(strip=True) for c in cells)
            for c_idx, cell in enumerate(cells):
                text = cell.get_text(strip=True)
                if text:
                    xpath = _get_real_xpath(cell, soup)
                    css = _get_real_css(cell, soup)
                    blocks.append(ContentBlock(
                        block_id=_compute_block_id(xpath, "table_cell", text),
                        block_type="table_cell", text=text, css=css, xpath=xpath,
                        html=str(cell), position=_get_position(cell, soup),
                        heading_context=_find_preceding_heading(table, soup),
                        table_index=t_idx, row_index=r_idx, cell_index=c_idx,
                        metadata={"row_text": row_text, "is_header": row.find("th") is not None},
                    ))

    # List items
    for el in content_root.find_all("li"):
        text = el.get_text(strip=True)
        if text and len(text) > 10:
            xpath = _get_real_xpath(el, soup)
            css = _get_real_css(el, soup)
            blocks.append(ContentBlock(
                block_id=_compute_block_id(xpath, "list_item", text),
                block_type="list_item", text=text, css=css, xpath=xpath,
                html=str(el), position=_get_position(el, soup),
                heading_context=_find_preceding_heading(el, soup),
            ))

    blocks.sort(key=lambda b: b.position)
    return blocks


def _extract_title(soup: BeautifulSoup) -> str:
    tag = soup.find("title")
    return tag.get_text(strip=True) if tag else ""


def _extract_pub_date(soup: BeautifulSoup, json_ld: List[Dict]) -> str:
    for item in json_ld:
        if "datePublished" in item:
            return item["datePublished"]
    meta = soup.find("meta", property="article:published_time")
    if meta:
        return meta.get("content", "")
    return ""


def _extract_author(soup: BeautifulSoup, json_ld: List[Dict]) -> str:
    for item in json_ld:
        if "author" in item:
            author = item["author"]
            if isinstance(author, dict):
                return author.get("name", "")
            return str(author)
    meta = soup.find("meta", property="article:author")
    return meta.get("content", "") if meta else ""


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
        loc = f"css={block.css}" if block.css else f"xpath={block.xpath}"
        table_ctx = ""
        if block.table_index >= 0:
            table_ctx = f" table={block.table_index} row={block.row_index} cell={block.cell_index}"
        heading_ctx = f" section=\"{block.heading_context[:40]}\"" if block.heading_context else ""
        lines.append(f"[{block.block_id}] ({block.block_type}) {loc}{table_ctx}{heading_ctx}")
        lines.append(f"  {block.text}")
        if block.metadata.get("row_text"):
            lines.append(f"  row: {block.metadata['row_text'][:100]}")
        lines.append("")

    return "\n".join(lines)
