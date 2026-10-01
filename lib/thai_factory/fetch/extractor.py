"""
Structured extraction from DocumentSnapshot.

Extracts ObservationCandidates with evidence paths from DOM/tables/headings.
Never reduces a table row to plain text before scope is determined.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..models import Observation, PriceType, SourceClass, TrustState


@dataclass
class EvidenceRegion:
    """A structured evidence region with DOM path."""
    selector: str = ""  # CSS/XPath-like path
    heading_context: str = ""  # Parent heading
    table_context: str = ""  # Parent table
    row_context: str = ""  # Specific row
    text: str = ""  # Raw text in region
    position: int = 0  # Position in document


def extract_observations(snap, brand_hints: List[str] = None) -> List[Observation]:
    """
    Extract ObservationCandidates from a DocumentSnapshot.
    Uses structured DOM (tables, headings) not flat text.
    """
    observations = []
    text = snap.markdown or ""
    html = snap.raw_html or ""
    title = snap.title or ""

    # Strategy 1: Table-based extraction (most reliable)
    table_obs = _extract_from_tables(html, snap.url, title, snap.published_date, brand_hints)
    observations.extend(table_obs)

    # Strategy 2: Heading-scoped extraction
    heading_obs = _extract_from_headings(html, text, snap.url, title, snap.published_date, brand_hints)
    observations.extend(heading_obs)

    # Strategy 3: Pattern-based extraction with context
    pattern_obs = _extract_with_context(text, snap.url, title, snap.published_date, brand_hints)
    observations.extend(pattern_obs)

    return observations


def _extract_from_tables(html: str, url: str, title: str, pub_date: str,
                          brand_hints: List[str] = None) -> List[Observation]:
    """Extract observations from HTML tables with row context."""
    observations = []
    domain = _extract_domain(url)

    # Find all tables
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.I)

    for table_idx, table_html in enumerate(tables):
        # Get heading context (search backwards from table)
        heading = _find_preceding_heading(html, table_html)
        heading_text = heading.get("text", "") if heading else ""

        # Parse rows
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.I)
        header_row = rows[0] if rows else ""
        headers = [re.sub(r'<[^>]+>', '', cell).strip() for cell in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', header_row, re.DOTALL | re.I)]

        for row_idx, row_html in enumerate(rows[1:], 1):
            cells = [re.sub(r'<[^>]+>', '', cell).strip() for cell in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row_html, re.DOTALL | re.I)]

            if not cells:
                continue

            row_text = " | ".join(cells)

            # Check if this row contains price data
            price_patterns = re.findall(r'(?:ราคา|฿|price)[:\s]*(\d{1,3}(?:,\d{3}){1,3})', row_text, re.I)
            if not price_patterns:
                price_patterns = re.findall(r'(\d{1,3}(?:,\d{3}){1,3})\s*(?:บาท|฿)', row_text, re.I)

            for price_str in price_patterns:
                val = int(price_str.replace(",", ""))
                if 100_000 <= val <= 20_000_000:
                    # Determine entity from row context
                    entity = _detect_entity(row_text, heading_text, title, brand_hints)
                    if entity:
                        observations.append(Observation(
                            source_url=url, source_domain=domain,
                            source_class=SourceClass.AUTOMOTIVE_MEDIA,
                            title=title, published_date=pub_date,
                            field="price", raw_value=price_str,
                            normalized_value=str(val), unit="THB",
                            price_type=PriceType.MSRP,
                            brand=entity["brand"], model=entity["model"],
                            variant=entity.get("variant", ""),
                            trust_state=TrustState.QUALIFIED,
                            evidence_excerpt=row_text[:200],
                            evidence_path=f"table[{table_idx}]/row[{row_idx}]/heading:{heading_text[:30]}",
                        ))

            # Check for spec data
            spec_patterns = [
                (r'(\d{2,3})\s*(?:hp|ps|แรงม้า)\b', "power_hp", "hp"),
                (r'(\d{2,4})\s*(?:Nm|นิวตันเมตร)\b', "torque_nm", "Nm"),
                (r'(\d{3,4})\s*cc\b', "engine_cc", "cc"),
                (r'(\d{1,2}\.\d)\s*(?:L|ลิตร)\b', "engine_l", "L"),
            ]
            for pattern, field_name, unit in spec_patterns:
                for m in re.finditer(pattern, row_text, re.I):
                    entity = _detect_entity(row_text, heading_text, title, brand_hints)
                    if entity:
                        observations.append(Observation(
                            source_url=url, source_domain=domain,
                            source_class=SourceClass.AUTOMOTIVE_MEDIA,
                            title=title, published_date=pub_date,
                            field=field_name, raw_value=m.group(1),
                            normalized_value=m.group(1), unit=unit,
                            brand=entity["brand"], model=entity["model"],
                            variant=entity.get("variant", ""),
                            trust_state=TrustState.QUALIFIED,
                            evidence_excerpt=row_text[:200],
                            evidence_path=f"table[{table_idx}]/row[{row_idx}]/heading:{heading_text[:30]}",
                        ))

    return observations


def _extract_from_headings(html: str, text: str, url: str, title: str,
                            pub_date: str, brand_hints: List[str] = None) -> List[Observation]:
    """Extract observations scoped to heading sections."""
    observations = []
    domain = _extract_domain(url)

    # Split text by headings
    sections = re.split(r'\n#{1,6}\s+', text)
    prev_heading = ""

    for section in sections[1:]:  # Skip first (before first heading)
        lines = section.strip().split("\n")
        heading = lines[0].strip() if lines else ""
        section_text = "\n".join(lines[1:]) if len(lines) > 1 else ""

        # Find prices in this section
        for m in re.finditer(r'(?:ราคา|฿|price)[:\s]*(?:เริ่มต้น|เริ่ม)?\s*(\d{1,3}(?:,\d{3}){1,3})\s*(?:บาท|฿)?', section_text, re.I):
            val = int(m.group(1).replace(",", ""))
            if 100_000 <= val <= 20_000_000:
                entity = _detect_entity(section_text, heading, title, brand_hints)
                if entity:
                    excerpt = section_text[max(0, m.start()-60):m.end()+60]
                    observations.append(Observation(
                        source_url=url, source_domain=domain,
                        source_class=SourceClass.AUTOMOTIVE_MEDIA,
                        title=title, published_date=pub_date,
                        field="price", raw_value=m.group(1),
                        normalized_value=str(val), unit="THB",
                        price_type=PriceType.MSRP,
                        brand=entity["brand"], model=entity["model"],
                        variant=entity.get("variant", ""),
                        trust_state=TrustState.QUALIFIED,
                        evidence_excerpt=excerpt[:200],
                        evidence_path=f"heading:{heading[:30]}",
                    ))

        prev_heading = heading

    return observations


def _extract_with_context(text: str, url: str, title: str,
                           pub_date: str, brand_hints: List[str] = None) -> List[Observation]:
    """Extract observations with surrounding context for evidence."""
    observations = []
    domain = _extract_domain(url)

    # Find price patterns with context
    for m in re.finditer(r'(?:ราคา|฿|price)[:\s]*(?:เริ่มต้น|เริ่ม)?\s*(\d{1,3}(?:,\d{3}){1,3})\s*(?:บาท|฿)?', text, re.I):
        val = int(m.group(1).replace(",", ""))
        if 100_000 <= val <= 20_000_000:
            # Get surrounding context (200 chars before/after)
            start = max(0, m.start() - 200)
            end = min(len(text), m.end() + 200)
            context = text[start:end]

            entity = _detect_entity(context, "", title, brand_hints)
            if entity:
                observations.append(Observation(
                    source_url=url, source_domain=domain,
                    source_class=SourceClass.AUTOMOTIVE_MEDIA,
                    title=title, published_date=pub_date,
                    field="price", raw_value=m.group(1),
                    normalized_value=str(val), unit="THB",
                    price_type=PriceType.MSRP,
                    brand=entity["brand"], model=entity["model"],
                    variant=entity.get("variant", ""),
                    trust_state=TrustState.QUALIFIED,
                    evidence_excerpt=context[:200],
                    evidence_path=f"position:{m.start()}",
                ))

    return observations


def _detect_entity(text: str, heading: str, title: str,
                    brand_hints: List[str] = None) -> Optional[Dict]:
    """Detect brand/model/variant from text context."""
    combined = f"{heading} {title} {text}".lower()

    # Brand detection
    brand_map = {
        "toyota": ["toyota", "โตโยต้า"],
        "honda": ["honda", "ฮอนด้า"],
        "nissan": ["nissan", "นิสสัน"],
        "mazda": ["mazda", "มาสด้า"],
        "byd": ["byd", "บีวายดี"],
        "mg": ["mg"],
        "ford": ["ford", "ฟอร์ด"],
        "isuzu": ["isuzu", "อีซูซุ"],
        "suzuki": ["suzuki", "ซูซูกิ"],
        "hyundai": ["hyundai", "ฮุนได"],
        "kia": ["kia", "เกีย"],
        "volvo": ["volvo", "วอลโว่"],
        "subaru": ["subaru", "ซูบารุ"],
        "bmw": ["bmw"],
        "mercedes": ["mercedes", "benz", "เบนซ์"],
    }

    detected_brand = ""
    for brand, keywords in brand_map.items():
        for kw in keywords:
            if kw in combined:
                detected_brand = brand
                break
        if detected_brand:
            break

    if not detected_brand and brand_hints:
        detected_brand = brand_hints[0].lower() if brand_hints else ""

    if not detected_brand:
        return None

    # Model detection (from title/heading)
    model_patterns = [
        (r'(?:all\s+new|new|newest)\s+([\w\s\-]+?)(?:\s+\d{4}|\s+ราคา|\s+table|$)', title),
        (r'(?:全新|ใหม่)\s+([\w\s\-]+?)(?:\s+\d{4}|\s+ราคา|$)', title),
        (r'(honda|toyota|nissan|mazda|byd|mg|ford|isuzu|suzuki|hyundai|kia|volvo|subaru|bmw|mercedes)\s+([\w\s\-]+?)(?:\s+\d{4}|\s+ราคา|\s+table|$)', title),
    ]

    detected_model = ""
    for pattern, source in model_patterns:
        m = re.search(pattern, source, re.I)
        if m:
            detected_model = m.group(1).strip()
            break

    if not detected_model:
        # Try from heading
        for pattern, source in model_patterns:
            m = re.search(pattern, heading, re.I)
            if m:
                detected_model = m.group(1).strip()
                break

    if not detected_model:
        return None

    # Variant detection
    variant_patterns = [
        r'\b(HEV|EV|PHEV|ICE|e:HEV|e-POWER)\b',
        r'\b(Premium|Standard|Comfort|Sport|GT|RS|GR Sport|Legender)\b',
        r'\b(E|V|VL|S|SE|LE|XLE|Limited)\b',
    ]
    detected_variant = ""
    for pattern in variant_patterns:
        m = re.search(pattern, combined, re.I)
        if m:
            detected_variant = m.group(1)
            break

    return {
        "brand": detected_brand,
        "model": detected_model,
        "variant": detected_variant,
    }


def _find_preceding_heading(html: str, table_html: str) -> Optional[Dict]:
    """Find the heading that precedes a table in the HTML."""
    idx = html.find(table_html)
    if idx == -1:
        return None

    # Search backwards for heading
    before = html[:idx]
    headings = list(re.finditer(r'<(h[1-6])[^>]*>(.*?)</\1>', before, re.DOTALL | re.I))
    if headings:
        last = headings[-1]
        return {
            "level": last.group(1),
            "text": re.sub(r'<[^>]+>', '', last.group(2)).strip(),
            "position": last.start(),
        }
    return None


def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc.replace("www.", "")
