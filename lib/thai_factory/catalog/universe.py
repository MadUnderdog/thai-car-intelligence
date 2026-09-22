"""
Vehicle Identity Universe — high-recall enumeration from taxonomy sources.
Uses insurance/used-car/finance databases for enumeration.
Official OEM sources for market truth reconciliation.
"""
import hashlib
import json
import re
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Set, Tuple
from datetime import date


class SourceRole(Enum):
    IDENTITY_ENUMERATOR = "IDENTITY_ENUMERATOR"  # High-recall taxonomy (insurance, used-car)
    MARKET_TRUTH = "MARKET_TRUTH"  # Official OEM/distributor/price-list


class CandidateConfidence(Enum):
    UNRESOLVED = "UNRESOLVED"
    SINGLE_SOURCE = "SINGLE_SOURCE"
    MULTI_SOURCE = "MULTI_SOURCE"
    OFFICIAL_VERIFIED = "OFFICIAL_VERIFIED"


@dataclass
class TaxonomyOption:
    """A single option from a taxonomy source dropdown/API."""
    source_id: str  # Source-specific option ID/code
    source_label: str  # Exact label as published
    parent_id: str = ""  # Parent option ID
    level: str = ""  # "manufacturer", "model", "generation", "variant", "trim"
    year_range: str = ""  # Year context if available
    source_url: str = ""
    observed_at: str = ""
    raw_payload: Dict = field(default_factory=dict)
    payload_hash: str = ""
    
    def __post_init__(self):
        if not self.payload_hash and self.raw_payload:
            self.payload_hash = hashlib.sha256(
                json.dumps(self.raw_payload, sort_keys=True).encode()
            ).hexdigest()[:16]


@dataclass
class IdentityUniverseCandidate:
    """A vehicle identity suggested by a taxonomy source."""
    manufacturer_name: str
    model_name: str
    generation_name: str = ""
    variant_name: str = ""
    trim_code: str = ""
    powertrain: str = ""
    
    source_name: str = ""
    source_role: SourceRole = SourceRole.IDENTITY_ENUMERATOR
    source_url: str = ""
    source_label: str = ""  # Exact label from source
    source_id: str = ""  # Source-specific ID
    source_code: str = ""  # Source-specific code
    
    year_context: str = ""
    acquisition_method: str = ""
    
    evidence: List[Dict] = field(default_factory=list)
    
    @property
    def canonical_key(self) -> str:
        parts = [
            self.manufacturer_name.lower().strip(),
            self.model_name.lower().strip(),
            self.generation_name.lower().strip() if self.generation_name else "",
            self.variant_name.lower().strip() if self.variant_name else "",
        ]
        return "|".join(parts)


@dataclass
class IdentityUniverse:
    """Union of all taxonomy candidates across sources."""
    candidates: List[IdentityUniverseCandidate] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
    target_date: str = "2026-09-22"
    
    def add_candidate(self, candidate: IdentityUniverseCandidate):
        self.candidates.append(candidate)
    
    def by_manufacturer(self, manufacturer: str) -> List[IdentityUniverseCandidate]:
        return [c for c in self.candidates if c.manufacturer_name.lower() == manufacturer.lower()]
    
    def summary(self) -> Dict:
        by_mfr = {}
        for c in self.candidates:
            mfr = c.manufacturer_name
            if mfr not in by_mfr:
                by_mfr[mfr] = {"models": set(), "variants": set()}
            by_mfr[mfr]["models"].add(c.model_name)
            if c.variant_name:
                by_mfr[mfr]["variants"].add(f"{c.model_name}|{c.variant_name}")
        
        return {
            "total_candidates": len(self.candidates),
            "manufacturers": len(by_mfr),
            "by_manufacturer": {
                m: {
                    "models": len(v["models"]),
                    "variants": len(v["variants"]),
                }
                for m, v in by_mfr.items()
            },
            "sources": self.sources_used,
        }


class TaxonomyDiscoveryAdapter:
    """Base class for taxonomy discovery adapters."""
    
    def __init__(self):
        self.name = "base"
        self.role = SourceRole.IDENTITY_ENUMERATOR
    
    def discover(self, manufacturer: str) -> List[IdentityUniverseCandidate]:
        raise NotImplementedError


class ViriyahAdapter(TaxonomyDiscoveryAdapter):
    """Viriyah V-Store taxonomy adapter."""
    
    def __init__(self):
        super().__init__()
        self.name = "viriyah"
    
    def discover(self, manufacturer: str) -> List[IdentityUniverseCandidate]:
        """Discover from Viriyah V-Store."""
        candidates = []
        
        try:
            from playwright.async_api import async_playwright
            
            async def _extract():
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    
                    # Viriyah V-Store URL pattern
                    url = f"https://www.viriyah.co.th/vstore/used-car?brand={manufacturer.lower()}"
                    
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=30000)
                        await page.wait_for_timeout(3000)
                        
                        # Extract model options from dropdowns
                        models = await page.evaluate("""
                            () => {
                                const selects = document.querySelectorAll('select');
                                const results = [];
                                for (const select of selects) {
                                    const options = select.querySelectorAll('option');
                                    for (const opt of options) {
                                        if (opt.value && opt.textContent.trim()) {
                                            results.push({
                                                id: opt.value,
                                                label: opt.textContent.trim(),
                                                parent: select.name || select.id
                                            });
                                        }
                                    }
                                }
                                return results;
                            }
                        """)
                        
                        for m in models:
                            candidates.append(IdentityUniverseCandidate(
                                manufacturer_name=manufacturer,
                                model_name=m["label"],
                                source_name="viriyah",
                                source_role=self.role,
                                source_url=url,
                                source_label=m["label"],
                                source_id=m["id"],
                                acquisition_method="playwright",
                            ))
                    finally:
                        await browser.close()
            
            asyncio.get_event_loop().run_until_complete(_extract())
        except Exception as e:
            pass
        
        return candidates


class One2carAdapter(TaxonomyDiscoveryAdapter):
    """One2car taxonomy adapter."""
    
    def __init__(self):
        super().__init__()
        self.name = "one2car"
    
    def discover(self, manufacturer: str) -> List[IdentityUniverseCandidate]:
        candidates = []
        
        try:
            from playwright.async_api import async_playwright
            
            async def _extract():
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    
                    url = f"https://www.one2car.com/sell?brand={manufacturer.lower()}"
                    
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=30000)
                        await page.wait_for_timeout(3000)
                        
                        # Extract model links/cards
                        models = await page.evaluate("""
                            () => {
                                const links = document.querySelectorAll('a[href*="/sell/"]');
                                const results = [];
                                const seen = new Set();
                                for (const link of links) {
                                    const href = link.getAttribute('href') || '';
                                    const text = link.textContent.trim();
                                    if (text && text.length > 1 && text.length < 50 && !seen.has(text)) {
                                        seen.add(text);
                                        results.push({label: text, href: href});
                                    }
                                }
                                return results.slice(0, 50);
                            }
                        """)
                        
                        for m in models:
                            candidates.append(IdentityUniverseCandidate(
                                manufacturer_name=manufacturer,
                                model_name=m["label"],
                                source_name="one2car",
                                source_role=self.role,
                                source_url=m["href"] if m["href"].startswith("http") else f"https://www.one2car.com{m['href']}",
                                source_label=m["label"],
                                acquisition_method="playwright",
                            ))
                    finally:
                        await browser.close()
            
            asyncio.get_event_loop().run_until_complete(_extract())
        except Exception as e:
            pass
        
        return candidates


class ChobrodAdapter(TaxonomyDiscoveryAdapter):
    """Chobrod taxonomy adapter."""
    
    def __init__(self):
        super().__init__()
        self.name = "chobrod"
    
    def discover(self, manufacturer: str) -> List[IdentityUniverseCandidate]:
        candidates = []
        
        try:
            from playwright.async_api import async_playwright
            
            async def _extract():
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    
                    url = f"https://www.chobrod.com/买车?brand={manufacturer}"
                    
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=30000)
                        await page.wait_for_timeout(3000)
                        
                        # Extract model options
                        models = await page.evaluate("""
                            () => {
                                const items = document.querySelectorAll('[class*="model"], [class*="brand"], option, li');
                                const results = [];
                                const seen = new Set();
                                for (const item of items) {
                                    const text = item.textContent.trim();
                                    if (text && text.length > 1 && text.length < 50 && !seen.has(text)) {
                                        seen.add(text);
                                        results.push({label: text});
                                    }
                                }
                                return results.slice(0, 50);
                            }
                        """)
                        
                        for m in models:
                            candidates.append(IdentityUniverseCandidate(
                                manufacturer_name=manufacturer,
                                model_name=m["label"],
                                source_name="chobrod",
                                source_role=self.role,
                                source_url=url,
                                source_label=m["label"],
                                acquisition_method="playwright",
                            ))
                    finally:
                        await browser.close()
            
            asyncio.get_event_loop().run_until_complete(_extract())
        except Exception as e:
            pass
        
        return candidates


class OfficialOEMAdapter(TaxonomyDiscoveryAdapter):
    """Official OEM lineup adapter for market truth."""
    
    def __init__(self):
        super().__init__()
        self.name = "official_oem"
        self.role = SourceRole.MARKET_TRUTH
    
    def discover(self, manufacturer: str) -> List[IdentityUniverseCandidate]:
        candidates = []
        
        # Official source URLs per manufacturer (tested working)
        official_urls = {
            "Toyota": "https://www.toyota.co.th/en/pricelist",
            "Mazda": "https://www.mazda.co.th/en/vehicles",
            "BMW": "https://www.bmw.co.th/en/all-models.html",
            "Honda": "https://www.honda.co.th/en/automobile",
            "Mercedes-Benz": "https://www.mercedes-benz.co.th/passengercars.html",
            "Nissan": "https://www.nissan.co.th/vehicles.html",
            "MG": "https://www.mgcars.com/en/models",
            "GWM": "https://www.gwm.co.th/th/vehicle.html",
        }
        
        if manufacturer not in official_urls:
            return candidates
        
        url = official_urls[manufacturer]
        
        try:
            from playwright.async_api import async_playwright
            
            async def _extract():
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=30000)
                        await page.wait_for_timeout(5000)
                        text = await page.inner_text('body')
                        
                        # Extract model+price pairs
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
                                            not name.startswith('฿')):
                                            price = int(price_match[1].replace(',', ''))
                                            candidates.append(IdentityUniverseCandidate(
                                                manufacturer_name=manufacturer,
                                                model_name=name,
                                                source_name="official_oem",
                                                source_role=self.role,
                                                source_url=url,
                                                source_label=name,
                                                acquisition_method="playwright",
                                                evidence=[{
                                                    "type": "price",
                                                    "value": price,
                                                    "currency": "THB",
                                                }],
                                            ))
                                            seen.add(name)
                                            break
                    finally:
                        await browser.close()
            
            asyncio.get_event_loop().run_until_complete(_extract())
        except Exception as e:
            pass
        
        return candidates
