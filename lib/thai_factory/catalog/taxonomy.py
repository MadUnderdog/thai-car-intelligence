"""
Taxonomy Discovery — browser-based extraction with XHR capture.
Normal browser context, proper failure classification.
"""
import hashlib
import json
import re
import asyncio
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Optional, Set
from datetime import datetime


class FailureClass(Enum):
    OK = "OK"
    WAF_403 = "WAF_403"
    JS_SHELL = "JS_SHELL"
    TIMEOUT = "TIMEOUT"
    SSL_ERROR = "SSL_ERROR"
    DNS_FAILURE = "DNS_FAILURE"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


@dataclass
class TaxonomyOption:
    """Single taxonomy option."""
    label: str
    value: str
    parent_value: str = ""
    level: str = ""  # "year", "brand", "model", "variant", "trim"


@dataclass
class TaxonomySnapshot:
    """Snapshot of taxonomy data from a source."""
    source_name: str
    source_url: str
    observed_at: str = ""
    acquisition_method: str = "playwright"
    browser_user_agent: str = ""
    
    year_options: List[TaxonomyOption] = field(default_factory=list)
    brand_options: List[TaxonomyOption] = field(default_factory=list)
    model_options: List[TaxonomyOption] = field(default_factory=list)
    variant_options: List[TaxonomyOption] = field(default_factory=list)
    trim_options: List[TaxonomyOption] = field(default_factory=list)
    
    discovered_endpoints: List[str] = field(default_factory=list)
    raw_responses: List[Dict] = field(default_factory=list)
    
    status: FailureClass = FailureClass.UNKNOWN
    error_message: str = ""
    http_status: int = 0
    page_title: str = ""
    
    @property
    def payload_hash(self) -> str:
        data = {
            "source": self.source_name,
            "models": [o.label for o in self.model_options],
            "variants": [o.label for o in self.variant_options],
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class IdentityCandidate:
    """Candidate from taxonomy source."""
    manufacturer: str
    model: str
    generation: str = ""
    variant: str = ""
    trim: str = ""
    powertrain: str = ""
    year_context: str = ""
    source_name: str = ""
    source_role: str = "IDENTITY_ENUMERATOR"
    source_label: str = ""
    source_id: str = ""
    source_url: str = ""
    evidence: List[Dict] = field(default_factory=list)


class BrowserTaxonomyAdapter:
    """Base class for browser-based taxonomy adapters."""
    
    def __init__(self):
        self.name = "base"
        self.captured_xhr: List[Dict] = []
    
    async def _create_context(self):
        """Create normal browser context."""
        from playwright.async_api import async_playwright
        
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="th-TH",
            timezone_id="Asia/Bangkok",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
        )
        
        # Capture XHR/fetch requests
        self.captured_xhr = []
        
        async def on_response(response):
            url = response.url
            content_type = response.headers.get("content-type", "")
            if any(t in content_type for t in ["json", "javascript", "text/plain"]):
                try:
                    body = await response.text()
                    if len(body) > 50:  # Skip tiny responses
                        self.captured_xhr.append({
                            "url": url,
                            "status": response.status,
                            "content_type": content_type,
                            "body_preview": body[:500],
                            "body_length": len(body),
                        })
                except:
                    pass
        
        self.context.on("response", on_response)
        
        self.page = await self.context.new_page()
    
    async def _close(self):
        await self.browser.close()
        await self.pw.stop()
    
    def _extract_options(self, text: str, level: str) -> List[TaxonomyOption]:
        """Extract options from page text."""
        options = []
        lines = text.split('\n')
        seen = set()
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 1 and len(line) < 80 and line not in seen:
                # Skip navigation/UI elements
                skip_words = ['menu', 'search', 'login', 'register', 'contact', 'about',
                              'home', 'news', 'promotion', 'dealer', 'test drive', 'quotation']
                if not any(w in line.lower() for w in skip_words):
                    options.append(TaxonomyOption(label=line, value=line, level=level))
                    seen.add(line)
        
        return options[:50]  # Limit to 50 options
    
    async def discover(self, manufacturer: str) -> TaxonomySnapshot:
        """Override in subclass."""
        raise NotImplementedError


class ViriyahTaxonomyAdapter(BrowserTaxonomyAdapter):
    """Viriyah V-Store taxonomy."""
    
    def __init__(self):
        super().__init__()
        self.name = "viriyah"
    
    async def discover(self, manufacturer: str) -> TaxonomySnapshot:
        snapshot = TaxonomySnapshot(
            source_name=self.name,
            source_url="https://www.viriyah.co.th/vstore",
            observed_at=datetime.now().isoformat(),
        )
        
        try:
            await self._create_context()
            
            # Navigate to V-Store
            resp = await self.page.goto(
                "https://www.viriyah.co.th/vstore",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            snapshot.http_status = resp.status if resp else 0
            
            await self.page.wait_for_timeout(5000)
            snapshot.page_title = await self.page.title()
            
            # Check for 403/WAF
            if resp and resp.status == 403:
                snapshot.status = FailureClass.WAF_403
                snapshot.error_message = "403 Forbidden"
                await self._close()
                return snapshot
            
            # Extract dropdown options
            options_data = await self.page.evaluate("""
                () => {
                    const results = {years: [], brands: [], models: [], variants: []};
                    
                    // Get all select elements
                    const selects = document.querySelectorAll('select');
                    for (const select of selects) {
                        const name = (select.name || select.id || '').toLowerCase();
                        const options = [];
                        for (const opt of select.options) {
                            if (opt.value && opt.textContent.trim()) {
                                options.push({
                                    label: opt.textContent.trim(),
                                    value: opt.value
                                });
                            }
                        }
                        
                        if (name.includes('year') || name.includes('ปี')) {
                            results.years = options;
                        } else if (name.includes('brand') || name.includes('make') || name.includes('ยี่ห้อ')) {
                            results.brands = options;
                        } else if (name.includes('model') || name.includes('รุ่น')) {
                            results.models = options;
                        } else if (name.includes('variant') || name.includes('submodel') || name.includes('รุ่นย่อย')) {
                            results.variants = options;
                        }
                    }
                    
                    // Also check for custom dropdowns
                    const dropdowns = document.querySelectorAll('[class*="dropdown"], [class*="select"], [role="listbox"]');
                    for (const dd of dropdowns) {
                        const items = dd.querySelectorAll('[role="option"], li, .option');
                        const options = [];
                        for (const item of items) {
                            const text = item.textContent.trim();
                            if (text && text.length > 1 && text.length < 50) {
                                options.push({label: text, value: text});
                            }
                        }
                        if (options.length > 0) {
                            results.models = results.models.length ? results.models : options;
                        }
                    }
                    
                    return results;
                }
            """)
            
            # Convert to TaxonomyOptions
            for opt in options_data.get("years", []):
                snapshot.year_options.append(TaxonomyOption(**opt, level="year"))
            for opt in options_data.get("brands", []):
                snapshot.brand_options.append(TaxonomyOption(**opt, level="brand"))
            for opt in options_data.get("models", []):
                snapshot.model_options.append(TaxonomyOption(**opt, level="model"))
            for opt in options_data.get("variants", []):
                snapshot.variant_options.append(TaxonomyOption(**opt, level="variant"))
            
            # Check if we got any data
            if not snapshot.model_options and not snapshot.brand_options:
                # Try extracting from page text
                text = await self.page.inner_text('body')
                snapshot.model_options = self._extract_options(text, "model")[:20]
            
            # Record discovered endpoints
            snapshot.discovered_endpoints = [x["url"] for x in self.captured_xhr]
            snapshot.raw_responses = self.captured_xhr[:5]
            
            snapshot.status = FailureClass.OK if snapshot.model_options else FailureClass.JS_SHELL
            
        except Exception as e:
            snapshot.status = FailureClass.BLOCKED
            snapshot.error_message = str(e)[:200]
        
        await self._close()
        return snapshot


class One2carTaxonomyAdapter(BrowserTaxonomyAdapter):
    """One2car taxonomy."""
    
    def __init__(self):
        super().__init__()
        self.name = "one2car"
    
    async def discover(self, manufacturer: str) -> TaxonomySnapshot:
        snapshot = TaxonomySnapshot(
            source_name=self.name,
            source_url="https://www.one2car.com",
            observed_at=datetime.now().isoformat(),
        )
        
        try:
            await self._create_context()
            
            # Try sell page
            resp = await self.page.goto(
                "https://www.one2car.com/sell",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            snapshot.http_status = resp.status if resp else 0
            
            await self.page.wait_for_timeout(5000)
            snapshot.page_title = await self.page.title()
            
            if resp and resp.status == 403:
                snapshot.status = FailureClass.WAF_403
                await self._close()
                return snapshot
            
            # Extract model links
            models = await self.page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a');
                    const results = [];
                    const seen = new Set();
                    for (const link of links) {
                        const href = link.getAttribute('href') || '';
                        const text = link.textContent.trim();
                        if (text && text.length > 2 && text.length < 50 && 
                            !seen.has(text) && href.includes('sell')) {
                            seen.add(text);
                            results.push({label: text, value: text});
                        }
                    }
                    return results.slice(0, 50);
                }
            """)
            
            for m in models:
                snapshot.model_options.append(TaxonomyOption(**m, level="model"))
            
            snapshot.discovered_endpoints = [x["url"] for x in self.captured_xhr]
            snapshot.status = FailureClass.OK if snapshot.model_options else FailureClass.TIMEOUT
            
        except Exception as e:
            snapshot.status = FailureClass.TIMEOUT
            snapshot.error_message = str(e)[:200]
        
        await self._close()
        return snapshot


class OfficialTaxonomyAdapter(BrowserTaxonomyAdapter):
    """Official OEM taxonomy adapter."""
    
    def __init__(self):
        super().__init__()
        self.name = "official"
    
    async def discover(self, manufacturer: str) -> TaxonomySnapshot:
        snapshot = TaxonomySnapshot(
            source_name=self.name,
            source_url="",
            observed_at=datetime.now().isoformat(),
        )
        
        urls = {
            "Toyota": "https://www.toyota.co.th/en/pricelist",
            "Mazda": "https://www.mazda.co.th/en/vehicles",
            "BMW": "https://www.bmw.co.th/en/all-models.html",
        }
        
        if manufacturer not in urls:
            snapshot.status = FailureClass.BLOCKED
            snapshot.error_message = "No official URL configured"
            return snapshot
        
        snapshot.source_url = urls[manufacturer]
        
        try:
            await self._create_context()
            
            resp = await self.page.goto(
                urls[manufacturer],
                wait_until="networkidle",
                timeout=30000,
            )
            snapshot.http_status = resp.status if resp else 0
            await self.page.wait_for_timeout(5000)
            
            # Extract model+price pairs
            text = await self.page.inner_text('body')
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
                                snapshot.model_options.append(TaxonomyOption(
                                    label=name,
                                    value=name,
                                    level="model",
                                ))
                                snapshot.raw_responses.append({
                                    "model": name,
                                    "price": price,
                                })
                                seen.add(name)
                                break
            
            snapshot.status = FailureClass.OK if snapshot.model_options else FailureClass.JS_SHELL
            
        except Exception as e:
            snapshot.status = FailureClass.BLOCKED
            snapshot.error_message = str(e)[:200]
        
        await self._close()
        return snapshot


async def discover_taxonomy(manufacturer: str) -> List[TaxonomySnapshot]:
    """Run all taxonomy adapters for a manufacturer."""
    adapters = [
        OfficialTaxonomyAdapter(),
        ViriyahTaxonomyAdapter(),
        One2carTaxonomyAdapter(),
    ]
    
    snapshots = []
    for adapter in adapters:
        try:
            snapshot = await adapter.discover(manufacturer)
            snapshots.append(snapshot)
        except Exception as e:
            snapshots.append(TaxonomySnapshot(
                source_name=adapter.name,
                source_url="",
                status=FailureClass.BLOCKED,
                error_message=str(e)[:200],
            ))
    
    return snapshots
