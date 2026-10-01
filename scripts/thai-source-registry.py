#!/usr/bin/env python3
"""
Thai Automotive Source Registry — canonical source definitions for
Thai automotive media sources used in the extraction pipeline.

All sources in this registry are AUTOMOTIVE_MEDIA / secondary research
sources. They are NOT independent source classes — only OEM + automotive
media = 2 source classes in the taxonomy.

Usage:
    from thai_source_registry import SourceRegistry
    registry = SourceRegistry()
    registry.get("headlightmag.com")
    registry.to_json("storage/thai-source-registry.json")
"""
import json
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class SourceEntry:
    """A single source definition in the registry."""
    domain: str
    display_name: str
    source_class: str = "AUTOMOTIVE_MEDIA"
    trust_state: str = "RESEARCH_UNVERIFIED"
    language: str = "TH"
    search_method: str = ""
    content_hash_method: str = ""
    scope_requirements: List[str] = field(default_factory=list)
    known_article_patterns: List[str] = field(default_factory=list)
    has_parser: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "SourceEntry":
        return SourceEntry(**{k: v for k, v in d.items()
                             if k in SourceEntry.__dataclass_fields__})


# ─── Registry Data ─────────────────────────────────────────────────

_SOURCES: List[SourceEntry] = [
    SourceEntry(
        domain="headlightmag.com",
        display_name="HeadLight Magazine",
        source_class="AUTOMOTIVE_MEDIA",
        trust_state="RESEARCH_UNVERIFIED",
        language="TH",
        search_method="category_archive_crawl",
        content_hash_method="sha256_evidence_excerpt_16",
        scope_requirements=[
            "model_context_window_300",
            "article_title_must_contain_model",
            "model_context_validation_on_spec_extraction",
        ],
        known_article_patterns=[
            r"Model Trim X,XXX,XXX",
            r"รุ่น Trim ราคา X,XXX,XXX",
            r"ราคาอย่างเป็นทางการ Model : X,XXX,XXX บาท",
            r"Trim | Price",
            r"\d+ (?:แรงม้า|hp|PS) ... \d+ (?:Nm|นิวตันเมตร)",
        ],
        has_parser=True,
        notes="WordPress site. Category archive crawl for article URLs. "
              "Extracts price+spec pairs with cross-model contamination guard.",
    ),
    SourceEntry(
        domain="autospinn.com",
        display_name="AutoSpinn",
        source_class="AUTOMOTIVE_MEDIA",
        trust_state="RESEARCH_UNVERIFIED",
        language="TH",
        search_method="brand_category_page_crawl",
        content_hash_method="sha256_evidence_excerpt_16",
        scope_requirements=[
            "model_context_from_heading",
            "reject_prices_without_model_scope",
            "price_range_as_model_scope_not_variant",
        ],
        known_article_patterns=[
            r"Model Trim ราคา X,XXX,XXX",
            r"Model Trim : X,XXX,XXX",
            r"ราคาอย่างเป็นทางการ Model X,XXX,XXX บาท",
            r"รุ่น Trim ราคา X,XXX,XXX",
        ],
        has_parser=False,
        notes="Thai automotive news/review site. Similar content structure "
              "to headlightmag. Article pages with model-specific content.",
    ),
    SourceEntry(
        domain="autolifethailand.tv",
        display_name="AutoLife Thailand",
        source_class="AUTOMOTIVE_MEDIA",
        trust_state="RESEARCH_UNVERIFIED",
        language="TH",
        search_method="category_page_crawl",
        content_hash_method="sha256_evidence_excerpt_16",
        scope_requirements=[
            "model_context_from_heading",
            "reject_prices_without_model_scope",
            "price_range_as_model_scope_not_variant",
        ],
        known_article_patterns=[
            r"Model Trim ราคา X,XXX,XXX",
            r"Model Trim : X,XXX,XXX บาท",
            r"รุ่น Trim ราคา X,XXX,XXX",
            r"ราคา Model X,XXX,XXX บาท",
        ],
        has_parser=False,
        notes="Thai automotive lifestyle/news site. Article-driven content "
              "with model+price extraction potential.",
    ),
    SourceEntry(
        domain="9carthai.com",
        display_name="9CARTHAI",
        source_class="AUTOMOTIVE_MEDIA",
        trust_state="RESEARCH_UNVERIFIED",
        language="TH",
        search_method="brand_price_page_crawl",
        content_hash_method="sha256_evidence_excerpt_16",
        scope_requirements=[
            "model_identity_from_h2_h3_heading",
            "reject_prices_without_model_context",
            "price_range_as_model_range",
            "deduplicate_by_model_variant_price_source",
        ],
        known_article_patterns=[
            r"รุ่น Trim ราคา X,XXX,XXX",
            r"Model Trim : X,XXX,XXX บาท",
            r"Model Trim ราคา X,XXX,XXX",
            r"ราคาอย่างเป็นทางการ Model X,XXX,XXX บาท",
        ],
        has_parser=True,
        notes="Brand price pages (/{brand}-price/). One page per brand, "
              "ALL models listed. Prices in Thai text, not tables.",
    ),
]


class SourceRegistry:
    """Registry of Thai automotive media sources.

    Provides lookup by domain, iteration over all sources,
    JSON export, and validation.
    """

    def __init__(self):
        self._sources: Dict[str, SourceEntry] = {}
        for entry in _SOURCES:
            self._sources[entry.domain] = entry

    def get(self, domain: str) -> Optional[SourceEntry]:
        return self._sources.get(domain)

    def all(self) -> List[SourceEntry]:
        return list(self._sources.values())

    def domains(self) -> List[str]:
        return list(self._sources.keys())

    def count(self) -> int:
        return len(self._sources)

    def has_parser(self, domain: str) -> bool:
        entry = self.get(domain)
        return entry.has_parser if entry else False

    def by_parser_status(self, with_parser: bool = True) -> List[SourceEntry]:
        return [s for s in self._sources.values() if s.has_parser == with_parser]

    def validate(self) -> List[str]:
        """Check registry entries for required fields. Returns list of errors."""
        errors = []
        required = ["domain", "display_name", "source_class", "trust_state",
                     "language", "search_method", "content_hash_method"]
        for entry in self._sources.values():
            for r in required:
                val = getattr(entry, r, None)
                if not val:
                    errors.append(f"{entry.domain}: missing {r}")
            if entry.source_class != "AUTOMOTIVE_MEDIA":
                errors.append(f"{entry.domain}: source_class must be "
                              f"AUTOMOTIVE_MEDIA, got {entry.source_class}")
            if entry.trust_state != "RESEARCH_UNVERIFIED":
                errors.append(f"{entry.domain}: trust_state must be "
                              f"RESEARCH_UNVERIFIED, got {entry.trust_state}")
            if entry.language != "TH":
                errors.append(f"{entry.domain}: language must be TH, "
                              f"got {entry.language}")
        return errors

    def to_dicts(self) -> List[dict]:
        return [s.to_dict() for s in self._sources.values()]

    def to_json(self, path: str) -> str:
        """Export registry as JSON to the given path. Returns the path."""
        data = {
            "version": "1.0",
            "source_class": "AUTOMOTIVE_MEDIA",
            "trust_state": "RESEARCH_UNVERIFIED",
            "language": "TH",
            "content_hash_method": "sha256_evidence_excerpt_16",
            "sources": self.to_dicts(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path

    @classmethod
    def from_json(cls, path: str) -> "SourceRegistry":
        """Load a registry from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        reg = cls.__new__(cls)
        reg._sources = {}
        for d in data.get("sources", []):
            entry = SourceEntry.from_dict(d)
            reg._sources[entry.domain] = entry
        return reg

    def __repr__(self) -> str:
        return f"SourceRegistry({self.count()} sources)"


# ─── Module-level convenience ──────────────────────────────────────

_default_registry = None

def get_registry() -> SourceRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = SourceRegistry()
    return _default_registry


if __name__ == "__main__":
    import sys
    registry = get_registry()
    errors = registry.validate()
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = "storage/thai-source-registry.json"
    if len(sys.argv) > 1:
        out_path = sys.argv[1]
    registry.to_json(out_path)
    print(f"Exported {registry.count()} sources to {out_path}")
    for s in registry.all():
        parser_flag = " [PARSER]" if s.has_parser else ""
        print(f"  - {s.domain} ({s.display_name}){parser_flag}")
