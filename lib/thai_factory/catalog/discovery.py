"""
Catalog Discovery — Playwright-based structured extraction.
"""
import re
import asyncio
from typing import List, Dict, Tuple
from .contracts import (
    CatalogCandidate, CanonicalCatalogEntry, CatalogInventory,
    MarketStatus, CandidateStatus, EvidenceLink, EvidenceStrength,
    Relationship, RelationshipType,
)
from .sources import MANUFACTURER_SOURCE_MAPS, ManufacturerSources

# Patterns that indicate non-model content
SKIP_PATTERNS = [
    'motorcycle', 'used-car', 'leasing', 'modulo', 'services', 'brand', 'ทั่ว',
    'philosophy', 'certified', 'family', 'overview', 'design', 'heritage',
    'sustainability', 'special offer', 'dealer', 'brochure', 'accessories',
    'owner manual', 'maintenance', 'recall', 'events', 'activities', 'updates',
    'global', 'ownership', 'benefit', 'promotion', 'news', 'contact', 'career',
    'quotation', 'test drive', 'filter', 'found', 'view detail',
]


async def _playwright_extract(url: str, wait_ms: int = 5000) -> Tuple[str, str]:
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(wait_ms)
            text = await page.inner_text('body')
            title = await page.title()
            await browser.close()
            return text, title
    except Exception as e:
        return "", str(e)


def _extract_models_from_price_page(text: str) -> List[Dict]:
    """Extract model+price pairs from Toyota-style price page."""
    models = []
    lines = text.split('\n')
    seen = set()
    
    for i, line in enumerate(lines):
        line = line.strip()
        price_match = re.search(r'฿([\d,]+)', line)
        if price_match:
            for back in range(1, 4):
                if i - back >= 0:
                    name = lines[i-back].strip()
                    if (name and len(name) < 60 and 
                        name not in seen and
                        not name.startswith('฿') and 
                        not name.startswith('Found') and
                        not any(p in name.lower() for p in SKIP_PATTERNS)):
                        price = int(price_match[1].replace(',', ''))
                        models.append({"name": name, "price": price})
                        seen.add(name)
                        break
    return models


def _extract_models_from_lineup_page(text: str) -> List[Dict]:
    """Extract model names and prices from Mazda-style lineup page."""
    models = []
    lines = text.split('\n')
    seen = set()
    
    for i, line in enumerate(lines):
        line = line.strip()
        price_match = re.search(r'(?:Starting from|ราคา)\s*฿?([\d,]+)', line, re.IGNORECASE)
        if price_match:
            for back in range(1, 4):
                if i - back >= 0:
                    name = lines[i-back].strip()
                    if (name and len(name) < 60 and 
                        name not in seen and
                        not name.startswith('฿') and 
                        not name.startswith('Starting') and
                        not any(p in name.lower() for p in SKIP_PATTERNS)):
                        price = int(price_match[1].replace(',', ''))
                        models.append({"name": name, "price": price})
                        seen.add(name)
                        break
    return models


def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc


class CatalogDiscovery:
    def __init__(self, acquisition_ladder=None):
        self.ladder = acquisition_ladder
        self.inventory = CatalogInventory(target_date="2026-09-22")
        self.candidates: List[CatalogCandidate] = []
        self.relationships: List[Relationship] = []
    
    def discover_manufacturer(self, manufacturer_name: str) -> List[CatalogCandidate]:
        if manufacturer_name not in MANUFACTURER_SOURCE_MAPS:
            return []
        
        sources = MANUFACTURER_SOURCE_MAPS[manufacturer_name]
        candidates = []
        
        for source in sources.sources:
            new_candidates = self._discover_from_source(sources, source)
            candidates.extend(new_candidates)
        
        self.candidates.extend(candidates)
        return candidates
    
    def _discover_from_source(self, mfr_sources: ManufacturerSources, source) -> List[CatalogCandidate]:
        candidates = []
        content = ""
        method = ""
        
        if source.extraction_method == "playwright":
            content, title = asyncio.get_event_loop().run_until_complete(
                _playwright_extract(source.url)
            )
            method = "playwright"
        elif source.extraction_method == "crawl4ai" and self.ladder:
            result = self.ladder.acquire(source.url)
            if result.status.value == "OK":
                content = result.content
                method = result.acquisition_method
        
        if not content:
            return candidates
        
        if source.source_type == "official_price":
            models = _extract_models_from_price_page(content)
        elif source.source_type == "official_lineup":
            models = _extract_models_from_lineup_page(content)
        else:
            models = _extract_models_from_lineup_page(content)
        
        for model_data in models:
            price_text = f", price ฿{model_data['price']:,}" if model_data.get('price') else ""
            evidence = EvidenceLink(
                source_url=source.url,
                source_domain=_extract_domain(source.url),
                source_class=source.source_class,
                evidence_strength=EvidenceStrength.OFFICIAL,
                evidence_text=f"Model '{model_data['name']}' found on {source.source_type}{price_text}",
                evidence_type="identity",
                acquisition_method=method,
            )
            
            candidate = CatalogCandidate(
                manufacturer_name=mfr_sources.name,
                model_name=model_data["name"],
                source_url=source.url,
                source_domain=_extract_domain(source.url),
                source_class=source.source_class,
                evidence_text=f"Model '{model_data['name']}' on {source.source_type}",
                acquisition_method=method,
                evidence=[evidence],
            )
            candidates.append(candidate)
        
        return candidates
    
    def reconcile(self) -> CatalogInventory:
        by_key = {}
        for c in self.candidates:
            key = f"{c.manufacturer_name.lower()}|{c.model_name.lower().strip()}"
            if key not in by_key:
                by_key[key] = []
            by_key[key].append(c)
        
        for key, group in by_key.items():
            has_official = any(c.source_class == "official" for c in group)
            if not has_official:
                for c in group:
                    c.status = CandidateStatus.CANDIDATE
                continue
            
            has_evidence = any(c.evidence for c in group)
            if not has_evidence:
                for c in group:
                    c.status = CandidateStatus.CANDIDATE
                continue
            
            first = group[0]
            # Extract price from evidence
            price_thb = None
            price_type = ""
            for c in group:
                for e in c.evidence:
                    price_match = re.search(r'price ฿([\d,]+)', e.evidence_text)
                    if price_match:
                        price_thb = int(price_match[1].replace(',', ''))
                        price_type = "OFFICIAL"
                        break
                if price_thb:
                    break
            
            entry = CanonicalCatalogEntry(
                manufacturer_name=first.manufacturer_name,
                model_name=first.model_name,
                market_status=MarketStatus.UNKNOWN,
                price_thb=price_thb,
                price_type=price_type,
            )
            
            for c in group:
                entry.identity_evidence.extend(c.evidence)
            
            seen_urls = set()
            unique = []
            for e in entry.identity_evidence:
                if e.source_url not in seen_urls:
                    seen_urls.add(e.source_url)
                    unique.append(e)
            entry.identity_evidence = unique
            
            self.inventory.add_entry(entry)
        
        self.inventory.candidates = [c for c in self.candidates if c.status == CandidateStatus.CANDIDATE]
        self.inventory.relationships = self.relationships
        
        return self.inventory
