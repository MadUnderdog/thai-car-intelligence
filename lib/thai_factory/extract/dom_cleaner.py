"""
Blockizer — consumes Crawl4AI output, produces ContentBlocks.

Two distinct concepts:
- content_block: AI-facing normalized content block from Crawl4AI markdown
- source_locator: structured extraction metadata from Crawl4AI (tables, headings)

Block IDs: deterministic from source_url + heading_ancestry + block_type + ordinal + content_hash
No fake HTML provenance. Markdown rows are NOT HTML fragments.
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class SourceLocator:
    """Structured extraction metadata from Crawl4AI, NOT fabricated."""
    source_type: str  # "crawled_markdown", "crawled_table", "crawled_heading"
    crawl_content_hash: str  # hash of the source page content
    crawl_id: Optional[str] = None  # Crawl4AI request ID if available
    original_url: str = ""
    final_url: str = ""
    table_index: Optional[int] = None
    row_index: Optional[int] = None
    cell_index: Optional[int] = None


@dataclass
class ContentBlock:
    block_id: str           # deterministic: url + heading_ancestry + type + ordinal + content_hash
    block_type: str         # "heading", "paragraph", "table", "list", "metadata"
    content: str            # normalized text from Crawl4AI markdown
    heading_context: str    # nearest preceding heading
    heading_ancestry: str   # full heading path for determinism
    stable_ordinal: int     # structural position within heading section
    content_hash: str       # sha256 of normalized content
    source_locator: SourceLocator = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Table-specific
    table_ordinal: Optional[int] = None
    row_ordinal: Optional[int] = None
    cell_ordinal: Optional[int] = None


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _normalize_text(text: str) -> str:
    """Normalize text for content hashing (strip whitespace, normalize spaces)."""
    return re.sub(r'\s+', ' ', text.strip())


def blockize_from_crawl4ai(crawl_result: Dict[str, Any], source_url: str = "") -> List[ContentBlock]:
    """
    Convert Crawl4AI result dict into ContentBlocks.
    Block IDs use: source_url + heading_ancestry + block_type + ordinal + content_hash
    """
    blocks: List[ContentBlock] = []
    heading_stack: List[str] = []  # stack of heading levels for ancestry
    heading_counter = 0
    section_counter = 0
    current_heading = ""
    current_ancestry = ""

    # Metadata
    meta = crawl_result.get("metadata", {})
    title = meta.get("title", "") if isinstance(meta, dict) else ""
    content_hash = crawl_result.get("content_hash", "")

    if title:
        blocks.append(ContentBlock(
            block_id="", block_type="metadata", content=title,
            heading_context="", heading_ancestry="", stable_ordinal=0,
            content_hash=_hash(title),
            source_locator=SourceLocator(
                source_type="crawled_markdown", crawl_content_hash=content_hash,
                original_url=source_url, final_url=source_url,
            ),
        ))
        section_counter += 1

    markdown = crawl_result.get("markdown", "")
    if not markdown:
        # Assign block IDs
        for b in blocks:
            b.block_id = _make_block_id(source_url, b)
        return blocks

    lines = markdown.split("\n")
    current_paragraph: List[str] = []
    paragraph_ordinal = 0
    table_buffer: List[str] = []
    in_table = False

    def flush_paragraph():
        nonlocal paragraph_ordinal
        if current_paragraph:
            text = "\n".join(current_paragraph).strip()
            if text and len(text) > 5:
                blocks.append(ContentBlock(
                    block_id="", block_type="paragraph", content=text,
                    heading_context=current_heading, heading_ancestry=current_ancestry,
                    stable_ordinal=paragraph_ordinal, content_hash=_hash(_normalize_text(text)),
                    source_locator=SourceLocator(
                        source_type="crawled_markdown", crawl_content_hash=content_hash,
                        original_url=source_url, final_url=source_url,
                    ),
                ))
                paragraph_ordinal += 1
            current_paragraph.clear()

    def flush_table():
        nonlocal section_counter
        if not table_buffer:
            return
        data_rows = [r for r in table_buffer if not re.match(r'^\|[\s\-:]+\|', r)]
        if not data_rows:
            return
        header = [c.strip() for c in data_rows[0].split("|")[1:-1]]
        for row_idx, row in enumerate(data_rows):
            cells = [c.strip() for c in row.split("|")[1:-1]]
            for cell_idx, cell in enumerate(cells):
                if not cell:
                    continue
                header_name = header[cell_idx] if cell_idx < len(header) else f"col{cell_idx}"
                text = f"{header_name}: {cell}"
                blocks.append(ContentBlock(
                    block_id="", block_type="table", content=text,
                    heading_context=current_heading, heading_ancestry=current_ancestry,
                    stable_ordinal=section_counter, content_hash=_hash(_normalize_text(text)),
                    source_locator=SourceLocator(
                        source_type="crawled_table", crawl_content_hash=content_hash,
                        original_url=source_url, final_url=source_url,
                        table_index=0, row_index=row_idx, cell_index=cell_idx,
                    ),
                    table_ordinal=0, row_ordinal=row_idx, cell_ordinal=cell_idx,
                    metadata={"header": header, "row": cells, "header_name": header_name},
                ))
                section_counter += 1

    for line in lines:
        stripped = line.strip()

        # Heading
        heading_match = re.match(r'^(#{1,6})\s+(.+)', stripped)
        if heading_match:
            flush_paragraph()
            if in_table:
                flush_table()
                table_buffer.clear()
                in_table = False

            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            # Update heading stack
            while heading_stack and len(heading_stack) >= level:
                heading_stack.pop()
            heading_stack.append(text)
            current_heading = text
            current_ancestry = " > ".join(heading_stack)

            blocks.append(ContentBlock(
                block_id="", block_type="heading", content=text,
                heading_context=text, heading_ancestry=current_ancestry,
                stable_ordinal=0, content_hash=_hash(_normalize_text(text)),
                source_locator=SourceLocator(
                    source_type="crawled_heading", crawl_content_hash=content_hash,
                    original_url=source_url, final_url=source_url,
                ),
                metadata={"level": level},
            ))
            paragraph_ordinal = 0
            section_counter += 1
            continue

        # Table row
        if "|" in stripped and stripped.startswith("|"):
            in_table = True
            table_buffer.append(stripped)
            continue
        elif in_table:
            flush_table()
            table_buffer.clear()
            in_table = False

        # List
        if re.match(r'^[-*+]\s+', stripped) or re.match(r'^\d+\.\s+', stripped):
            flush_paragraph()
            blocks.append(ContentBlock(
                block_id="", block_type="list", content=stripped,
                heading_context=current_heading, heading_ancestry=current_ancestry,
                stable_ordinal=paragraph_ordinal, content_hash=_hash(_normalize_text(stripped)),
                source_locator=SourceLocator(
                    source_type="crawled_markdown", crawl_content_hash=content_hash,
                    original_url=source_url, final_url=source_url,
                ),
            ))
            paragraph_ordinal += 1
            continue

        # Empty line
        if not stripped:
            flush_paragraph()
            continue

        # Regular text
        current_paragraph.append(stripped)

    flush_paragraph()
    if in_table:
        flush_table()

    # Assign deterministic block IDs
    for b in blocks:
        b.block_id = _make_block_id(source_url, b)

    return blocks


def _make_block_id(source_url: str, block: ContentBlock) -> str:
    """
    Deterministic block ID: source_url + heading_ancestry + block_type + ordinal + content_hash
    Stable across reruns of the same page content.
    """
    parts = [
        source_url or "",
        block.heading_ancestry or "",
        block.block_type,
        str(block.stable_ordinal),
        block.content_hash,
    ]
    if block.block_type == "table":
        parts.extend([str(block.table_ordinal or 0),
                      str(block.row_ordinal or 0),
                      str(block.cell_ordinal or 0)])
    return _hash(":".join(parts))


# ─── Compatibility Layer ───────────────────────────────────────────

@dataclass
class CleanedPage:
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
            header += f" table={b.table_ordinal} row={b.row_ordinal} cell={b.cell_ordinal}"
        lines.append(header)
        lines.append(b.content)
        lines.append("")
    return "\n".join(lines)
