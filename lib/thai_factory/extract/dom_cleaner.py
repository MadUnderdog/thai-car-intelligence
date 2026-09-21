"""
Blockizer — consumes Crawl4AI output, produces ContentBlocks.

Crawl4AI owns: browser, JS, rendering, HTML acquisition, markdown generation.
This module owns: splitting Crawl4AI output into blocks with provenance.

Architecture: Crawl4AI → clean markdown/tables → blockize → AI extraction
No custom HTML parsing. bs4/lxml are Crawl4AI's internal dependencies only.
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ContentBlock:
    block_id: str          # deterministic: sha256(block_type + stable_index + content_hash)
    block_type: str        # "heading", "paragraph", "table", "list", "code", "metadata"
    content: str           # normalized text
    original_html: str     # raw HTML fragment (from Crawl4AI if available)
    heading_context: str   # nearest preceding heading
    stable_index: int      # position in page (for determinism)
    content_hash: str      # sha256 of normalized content
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Table-specific (when block_type == "table")
    table_index: Optional[int] = None
    row_index: Optional[int] = None
    cell_index: Optional[int] = None
    # Source provenance (from Crawl4AI)
    source_url: Optional[str] = None
    final_url: Optional[str] = None
    crawl_id: Optional[str] = None


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def blockize_from_crawl4ai(crawl_result: Dict[str, Any], source_url: str = "") -> List[ContentBlock]:
    """
    Convert Crawl4AI result dict into ContentBlocks.

    Crawl4AI returns:
    - success, html, markdown, clean_html
    - links, media, tables (if extract_links/media/tables enabled)
    - metadata (title, description, etc.)
    - depth, redirects, etc.

    This function splits the markdown into blocks.
    """
    blocks: List[ContentBlock] = []
    stable_idx = 0
    current_heading = ""
    crawl_id = crawl_result.get("success", None)
    final_url = source_url

    # Extract metadata block
    title = ""
    if isinstance(crawl_result.get("metadata"), dict):
        title = crawl_result["metadata"].get("title", "")
    if title:
        blocks.append(ContentBlock(
            block_id="", block_type="metadata", content=title,
            original_html="", heading_context="", stable_index=stable_idx,
            content_hash=_hash(title), source_url=source_url,
            final_url=final_url, crawl_id=str(crawl_id),
            metadata={"title": title}
        ))
        stable_idx += 1

    # Get markdown content
    markdown = crawl_result.get("markdown", "")
    if not markdown:
        return blocks

    # Split markdown into blocks by headings and structure
    lines = markdown.split("\n")
    current_paragraph: List[str] = []
    table_buffer: List[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()

        # Heading detection
        heading_match = re.match(r'^(#{1,6})\s+(.+)', stripped)
        if heading_match:
            # Flush paragraph
            if current_paragraph:
                text = "\n".join(current_paragraph).strip()
                if text:
                    blocks.append(_make_text_block(text, "paragraph", stable_idx,
                                                   current_heading, source_url, final_url, crawl_id))
                    stable_idx += 1
                current_paragraph = []

            # Flush table
            if in_table and table_buffer:
                blocks.extend(_make_table_blocks(table_buffer, stable_idx, current_heading,
                                                 source_url, final_url, crawl_id))
                stable_idx += len(table_buffer)
                table_buffer = []
                in_table = False

            current_heading = stripped
            blocks.append(_make_text_block(stripped, "heading", stable_idx,
                                           current_heading, source_url, final_url, crawl_id))
            stable_idx += 1
            continue

        # Table detection (markdown tables)
        if "|" in stripped and stripped.startswith("|"):
            in_table = True
            table_buffer.append(stripped)
            continue
        elif in_table:
            # Table ended
            if table_buffer:
                blocks.extend(_make_table_blocks(table_buffer, stable_idx, current_heading,
                                                 source_url, final_url, crawl_id))
                stable_idx += len(table_buffer)
            table_buffer = []
            in_table = False

        # List detection
        if re.match(r'^[-*+]\s+', stripped) or re.match(r'^\d+\.\s+', stripped):
            if current_paragraph:
                text = "\n".join(current_paragraph).strip()
                if text:
                    blocks.append(_make_text_block(text, "paragraph", stable_idx,
                                                   current_heading, source_url, final_url, crawl_id))
                    stable_idx += 1
                current_paragraph = []
            blocks.append(_make_text_block(stripped, "list", stable_idx,
                                           current_heading, source_url, final_url, crawl_id))
            stable_idx += 1
            continue

        # Code detection
        if stripped.startswith("```") or stripped.startswith("    "):
            if current_paragraph:
                text = "\n".join(current_paragraph).strip()
                if text:
                    blocks.append(_make_text_block(text, "paragraph", stable_idx,
                                                   current_heading, source_url, final_url, crawl_id))
                    stable_idx += 1
                current_paragraph = []
            blocks.append(_make_text_block(stripped, "code", stable_idx,
                                           current_heading, source_url, final_url, crawl_id))
            stable_idx += 1
            continue

        # Empty line = paragraph boundary
        if not stripped:
            if current_paragraph:
                text = "\n".join(current_paragraph).strip()
                if text:
                    blocks.append(_make_text_block(text, "paragraph", stable_idx,
                                                   current_heading, source_url, final_url, crawl_id))
                    stable_idx += 1
                current_paragraph = []
            continue

        # Regular text
        current_paragraph.append(stripped)

    # Flush remaining
    if current_paragraph:
        text = "\n".join(current_paragraph).strip()
        if text:
            blocks.append(_make_text_block(text, "paragraph", stable_idx,
                                           current_heading, source_url, final_url, crawl_id))
    if in_table and table_buffer:
        blocks.extend(_make_table_blocks(table_buffer, stable_idx, current_heading,
                                         source_url, final_url, crawl_id))

    # Assign deterministic block_ids (content-based, not position-based)
    for b in blocks:
        b.block_id = _hash(f"{b.block_type}:{b.stable_index}:{b.content_hash}")

    return blocks


def _make_text_block(text: str, block_type: str, stable_idx: int,
                     heading: str, source_url: str, final_url: str,
                     crawl_id: str) -> ContentBlock:
    content_hash = _hash(text)
    return ContentBlock(
        block_id="", block_type=block_type, content=text,
        original_html="", heading_context=heading, stable_index=stable_idx,
        content_hash=content_hash, source_url=source_url,
        final_url=final_url, crawl_id=str(crawl_id),
    )


def _make_table_blocks(rows: List[str], start_idx: int, heading: str,
                       source_url: str, final_url: str,
                       crawl_id: str) -> List[ContentBlock]:
    """Convert markdown table rows into a single table block."""
    # Skip separator row (|---|---|)
    data_rows = [r for r in rows if not re.match(r'^\|[\s\-:]+\|', r)]
    if not data_rows:
        return []

    # Parse header
    header = [c.strip() for c in data_rows[0].split("|")[1:-1]]

    blocks = []
    for row_idx, row in enumerate(data_rows):
        cells = [c.strip() for c in row.split("|")[1:-1]]
        for cell_idx, cell in enumerate(cells):
            if not cell:
                continue
            header_name = header[cell_idx] if cell_idx < len(header) else f"col{cell_idx}"
            blocks.append(ContentBlock(
                block_id="", block_type="table",
                content=f"{header_name}: {cell}",
                original_html=row, heading_context=heading,
                stable_index=start_idx + row_idx,
                content_hash=_hash(cell),
                source_url=source_url, final_url=final_url,
                crawl_id=str(crawl_id),
                table_index=0, row_index=row_idx, cell_index=cell_idx,
                metadata={"header": header, "row": cells, "header_name": header_name}
            ))

    return blocks


def extract_tables_from_crawl(crawl_result: Dict[str, Any]) -> List[Dict]:
    """
    Extract structured tables from Crawl4AI result.
    Uses Crawl4AI's table extraction if available.
    """
    tables = crawl_result.get("tables", [])
    if tables:
        return tables

    # Fallback: parse markdown tables
    markdown = crawl_result.get("markdown", "")
    result = []
    current_table = []
    in_table = False

    for line in markdown.split("\n"):
        stripped = line.strip()
        if "|" in stripped and stripped.startswith("|"):
            in_table = True
            current_table.append(stripped)
        elif in_table:
            if current_table:
                result.append(_parse_md_table(current_table))
            current_table = []
            in_table = False

    if current_table:
        result.append(_parse_md_table(current_table))

    return result


def _parse_md_table(rows: List[str]) -> Dict:
    """Parse markdown table into structured dict."""
    data_rows = [r for r in rows if not re.match(r'^\|[\s\-:]+\|', r)]
    if not data_rows:
        return {"headers": [], "rows": []}
    header = [c.strip() for c in data_rows[0].split("|")[1:-1]]
    parsed_rows = []
    for row in data_rows[1:]:
        cells = [c.strip() for c in row.split("|")[1:-1]]
        parsed_rows.append(dict(zip(header, cells)))
    return {"headers": header, "rows": parsed_rows}


# ─── Compatibility Layer ───────────────────────────────────────────
# CleanedPage and format_blocks_for_ai for ai_extractor.py

@dataclass
class CleanedPage:
    """Page with blocks — consumed by ai_extractor."""
    url: str
    blocks: List[ContentBlock] = field(default_factory=list)
    title: str = ""
    content_hash: str = ""
    fetch_method: str = "crawl4ai"


def format_blocks_for_ai(page: CleanedPage) -> str:
    """Format ContentBlocks into text for AI extraction."""
    lines = [f"URL: {page.url}", f"Title: {page.title}", ""]
    for b in page.blocks:
        header = f"[{b.block_id}] {b.block_type.upper()}"
        if b.heading_context:
            header += f" (under: {b.heading_context})"
        if b.block_type == "table":
            header += f" table={b.table_index} row={b.row_index} cell={b.cell_index}"
        lines.append(header)
        lines.append(b.content)
        lines.append("")
    return "\n".join(lines)
