"""
Catalog Discovery — structured discovery from official sources.
NO regex mining. Uses explicit source maps and structured elements.
"""
import json
import re
import time
from typing import List, Optional, Dict, Set, Tuple
from .contracts import (
    CatalogCandidate, CanonicalCatalogEntry, CatalogInventory,
    MarketStatus, CandidateStatus, EvidenceLink, EvidenceStrength,
)


# Thai market manufacturer source maps — STRUCTURED, not regex
MANUFACTURER_SOURCES = {
    "Honda": {
        "official": [
            "https://www.honda.co.th/en/automobile",
        ],
        "media": [
            "https://www.headlightmag.com/first-impression-honda-civic-s-plus-shift/",
        ],
        "models_known": ["Civic", "City", "CR-V", "HR-V", "Accord", "ZR-V", "WR-V", "BR-V"],
        "thai_name": "ฮอนด้า",
    },
    "Toyota": {
        "official": [
            "https://www.toyota.co.th/en/model",
        ],
        "media": [],
        "models_known": ["Camry", "Corolla Altis", "Yaris Ativ", "Fortuner", "Hilux", "CHR", "bZ4X", "Vios", "Veloz", "Innova", "Alphard", "Vellfire"],
        "thai_name": "โตโยต้า",
    },
    "MG": {
        "official": [
            "https://www.mgcars.com/en/models",
        ],
        "media": [
            "https://www.headlightmag.com/first-impression-mg-urban/",
        ],
        "models_known": ["MG3", "MG5", "ZS", "HS", "EP", "MG4", "Cyberster"],
        "thai_name": "เอ็มจี",
    },
    "BYD": {
        "official": [
            "https://www.bydauto.co.th/",
        ],
        "media": [],
        "models_known": ["Atto 3", "Dolphin", "Seal", "M6", "Sealion 6", "Sealion 7"],
        "thai_name": "บีวายดี",
    },
    "Mazda": {
        "official": [
            "https://www.mazda.co.th/en/vehicles",
        ],
        "media": [],
        "models_known": ["Mazda2", "Mazda3", "CX-3", "CX-30", "CX-5", "CX-8", "BT-50"],
        "thai_name": "มาสด้า",
    },
    "Nissan": {
        "official": [
            "https://www.nissan.co.th/vehicles.html",
        ],
        "media": [],
        "models_known": ["Almera", "Kicks", "X-Trail", "Navara", "LEAF"],
        "thai_name": "นิสสัน",
    },
    "BMW": {
        "official": [
            "https://www.bmw.co.th/en/all-models.html",
        ],
        "media": [],
        "models_known": ["1 Series", "3 Series", "5 Series", "7 Series", "X1", "X3", "X5", "iX", "i4"],
        "thai_name": "บีเอ็มดับเบิลยู",
    },
    "Mercedes-Benz": {
        "official": [
            "https://www.mercedes-benz.co.th/passengercars.html",
        ],
        "media": [],
        "models_known": ["A-Class", "C-Class", "E-Class", "S-Class", "GLA", "GLC", "GLE", "EQB", "EQE"],
        "thai_name": "เมอร์เซเดส-เบนซ์",
    },
    "Wuling": {
        "official": [],
        "media": [
            "https://autolifethailand.tv/wuling-eksion-ev-bev-suv-coming-thailand-28-sep-2026/",
        ],
        "models_known": ["Air EV", "Almaz"],
        "thai_name": "วูลิง",
    },
    "Haval": {
        "official": [
            "https://www.haval.co.th/",
        ],
        "media": [],
        "models_known": ["H6", "Jolion", "Big Dog"],
        "thai_name": "ฮาเวล",
    },
}


class CatalogDiscovery:
    """
    Structured catalog discovery from official sources.
    NO regex mining. Uses explicit source maps and structured elements.
    """
    
    def __init__(self, acquisition_ladder=None):
        self.ladder = acquisition_ladder
        self.inventory = CatalogInventory(target_date="2026-09-22")
        self.candidates: List[CatalogCandidate] = []
    
    def discover_manufacturer(self, manufacturer_name: str) -> List[CatalogCandidate]:
        """
        Discover models for a manufacturer from structured sources.
        Returns candidates (NOT canonical entries).
        """
        if manufacturer_name not in MANUFACTURER_SOURCES:
            return []
        
        sources = MANUFACTURER_SOURCES[manufacturer_name]
        candidates = []
        
        # Discover from official sources
        for url in sources.get("official", []):
            new_candidates = self._discover_from_official(manufacturer_name, url, sources)
            candidates.extend(new_candidates)
        
        # Discover from media (lower confidence)
        for url in sources.get("media", []):
            new_candidates = self._discover_from_media(manufacturer_name, url, sources)
            candidates.extend(new_candidates)
        
        # Also create candidates from known model list
        for model_name in sources.get("models_known", []):
            candidate = CatalogCandidate(
                manufacturer_name=manufacturer_name,
                model_name=model_name,
                source_domain="seed_data",
                source_class="seed",
                evidence_text=f"Known Thai market model from seed data",
                status=CandidateStatus.CANDIDATE,
            )
            candidates.append(candidate)
        
        self.candidates.extend(candidates)
        return candidates
    
    def _discover_from_official(self, manufacturer_name: str, url: str, 
                                 sources: Dict) -> List[CatalogCandidate]:
        """Discover from official manufacturer page."""
        candidates = []
        
        if not self.ladder:
            return candidates
        
        result = self.ladder.acquire(url)
        if result.status.value != "OK":
            return candidates
        
        content = result.content
        method = result.acquisition_method
        
        # Extract structured model mentions
        models_found = self._extract_structured_models(content, sources)
        
        for model_name in models_found:
            evidence = EvidenceLink(
                source_url=url,
                source_domain=self._extract_domain(url),
                source_class="official",
                evidence_strength=EvidenceStrength.OFFICIAL,
                evidence_text=f"Model '{model_name}' found on official page",
                evidence_type="identity",
                acquisition_method=method,
            )
            
            candidate = CatalogCandidate(
                manufacturer_name=manufacturer_name,
                model_name=model_name,
                source_url=url,
                source_domain=self._extract_domain(url),
                source_class="official",
                evidence_text=f"Model '{model_name}' on official lineup page",
                acquisition_method=method,
                evidence=[evidence],
            )
            candidates.append(candidate)
        
        return candidates
    
    def _discover_from_media(self, manufacturer_name: str, url: str,
                              sources: Dict) -> List[CatalogCandidate]:
        """Discover from media article."""
        candidates = []
        
        if not self.ladder:
            return candidates
        
        result = self.ladder.acquire(url)
        if result.status.value != "OK":
            return candidates
        
        content = result.content
        method = result.acquisition_method
        
        # Extract structured model mentions
        models_found = self._extract_structured_models(content, sources)
        
        for model_name in models_found:
            # Check if mention is in article body vs sidebar
            is_body = self._is_body_mention(content, model_name)
            
            evidence = EvidenceLink(
                source_url=url,
                source_domain=self._extract_domain(url),
                source_class="media",
                evidence_strength=EvidenceStrength.HIGH_QUALITY_MEDIA,
                evidence_text=f"Model '{model_name}' mentioned in article",
                evidence_type="identity",
                acquisition_method=method,
            )
            
            candidate = CatalogCandidate(
                manufacturer_name=manufacturer_name,
                model_name=model_name,
                source_url=url,
                source_domain=self._extract_domain(url),
                source_class="media",
                evidence_text=f"Model '{model_name}' in article",
                acquisition_method=method,
                is_body_mention=is_body,
                is_sidebar_mention=not is_body,
                evidence=[evidence],
            )
            candidates.append(candidate)
        
        return candidates
    
    def _extract_structured_models(self, content: str, sources: Dict) -> List[str]:
        """
        Extract model names from structured content.
        Uses known model list as anchor, not regex mining.
        """
        models = set()
        known_models = sources.get("models_known", [])
        
        # Check if known models appear in content
        for model in known_models:
            # Case-insensitive search with word boundary
            pattern = re.compile(r'\b' + re.escape(model) + r'\b', re.IGNORECASE)
            if pattern.search(content):
                models.add(model)
        
        return list(models)
    
    def _is_body_mention(self, content: str, model_name: str) -> bool:
        """Check if model is mentioned in article body (not sidebar)."""
        # Simple heuristic: if model appears in first 70% of content, likely body
        pos = content.lower().find(model_name.lower())
        if pos < 0:
            return False
        return pos < len(content) * 0.7
    
    def _extract_domain(self, url: str) -> str:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    
    def reconcile(self) -> CatalogInventory:
        """
        Reconcile candidates into canonical entries.
        NO auto-promotion. Requires explicit evidence.
        """
        # Group candidates by canonical_id
        by_id = {}
        for c in self.candidates:
            cid = c.canonical_id
            if cid not in by_id:
                by_id[cid] = []
            by_id[cid].append(c)
        
        # For each group, decide if it becomes canonical
        for cid, group in by_id.items():
            # Need at least one official or high-quality evidence
            has_strong_evidence = any(
                c.source_class in ("official", "seed") for c in group
            )
            
            if not has_strong_evidence:
                # Keep as candidate, don't promote
                for c in group:
                    c.status = CandidateStatus.CANDIDATE
                continue
            
            # Need at least one actual evidence link
            has_any_evidence = any(c.evidence for c in group)
            if not has_any_evidence:
                for c in group:
                    c.status = CandidateStatus.CANDIDATE
                continue
            
            # Create canonical entry
            first = group[0]
            entry = CanonicalCatalogEntry(
                manufacturer_name=first.manufacturer_name,
                model_name=first.model_name,
                market_status=MarketStatus.UNKNOWN,  # Never infer CURRENT
            )
            
            # Add all evidence
            for c in group:
                entry.identity_evidence.extend(c.evidence)
            
            # Remove duplicate evidence
            seen_urls = set()
            unique_evidence = []
            for e in entry.identity_evidence:
                if e.source_url not in seen_urls:
                    seen_urls.add(e.source_url)
                    unique_evidence.append(e)
            entry.identity_evidence = unique_evidence
            
            self.inventory.add_entry(entry)
        
        # Store unresolved candidates
        self.inventory.candidates = [c for c in self.candidates if c.status == CandidateStatus.CANDIDATE]
        
        return self.inventory
