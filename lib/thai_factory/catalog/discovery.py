"""
Catalog Discovery — discovers manufacturers, models, and variants.
Uses acquisition ladder + source adapters.
"""
import json
import re
import time
from typing import List, Optional, Dict, Set
from .contracts import (
    Manufacturer, Model, Variant, Generation, Powertrain,
    MarketStatus, CatalogEntry, CatalogIdentity, EvidenceLink,
    EvidenceStrength,
)


# Known Thai market manufacturers (seed data)
THAI_MANUFACTURERS = [
    {"name": "Honda", "website": "https://www.honda.co.th", "thai": "ฮอนด้า"},
    {"name": "Toyota", "website": "https://www.toyota.co.th", "thai": "โตโยต้า"},
    {"name": "Mazda", "website": "https://www.mazda.co.th", "thai": "มาสด้า"},
    {"name": "Nissan", "website": "https://www.nissan.co.th", "thai": "นิสสัน"},
    {"name": "Mitsubishi", "website": "https://www.mitsubishi-motors.co.th", "thai": "มิตซูบิชิ"},
    {"name": "Suzuki", "website": "https://www.suzuki.co.th", "thai": "ซูซูกิ"},
    {"name": "Isuzu", "website": "https://www.isuzu.co.th", "thai": "อีซูซุ"},
    {"name": "MG", "website": "https://www.mgcars.com", "thai": "เอ็มจี"},
    {"name": "BYD", "website": "https://www.bydauto.co.th", "thai": "บีวายดี"},
    {"name": "Haval", "website": "https://www.haval.co.th", "thai": "ฮาเวล"},
    {"name": "GWM", "website": "https://www.gwm.co.th", "thai": "จีดับบลิวเอ็ม"},
    {"name": "BMW", "website": "https://www.bmw.co.th", "thai": "บีเอ็มดับเบิลยู"},
    {"name": "Mercedes-Benz", "website": "https://www.mercedes-benz.co.th", "thai": "เมอร์เซเดส-เบนซ์"},
    {"name": "Volvo", "website": "https://www.volvo.co.th", "thai": "วอลโว่"},
    {"name": "Ford", "website": "https://www.ford.co.th", "thai": "ฟอร์ด"},
    {"name": "Chevrolet", "website": "https://www.chevrolet.co.th", "thai": "เชฟโรเลต"},
    {"name": "Subaru", "website": "https://www.subaru.co.th", "thai": "ซูบารุ"},
    {"name": "Kia", "website": "https://www.kia.com/th", "thai": "เกีย"},
    {"name": "Hyundai", "website": "https://www.hyundai.co.th", "thai": "ฮุนได"},
    {"name": "Lexus", "website": "https://www.lexus.co.th", "thai": "เล็กซัส"},
    {"name": "MINI", "website": "https://www.mini.co.th", "thai": "มินิ"},
    {"name": "ZEEKR", "website": "", "thai": "ซีคאר์"},
    {"name": "Deepal", "website": "", "thai": "ดีปอล"},
    {"name": "Changan", "website": "", "thai": "ฉางอัน"},
    {"name": "Wuling", "website": "", "thai": "วูลิง"},
    {"name": "NETA", "website": "", "thai": "เนต้า"},
    {"name": "ORA", "website": "", "thai": "โอร่า"},
]


class CatalogDiscovery:
    """
    Discovers Thai market vehicle catalog.
    Phase A: Identity discovery.
    Phase B: Opportunistic enrichment.
    """
    
    def __init__(self, acquisition_ladder=None):
        self.manufacturers: Dict[str, Manufacturer] = {}
        self.entries: List[CatalogEntry] = []
        self.ladder = acquisition_ladder
        
        # Initialize seed manufacturers
        for m in THAI_MANUFACTURERS:
            mfr = Manufacturer(
                manufacturer_name=m["name"],
                manufacturer_name_thai=m["thai"],
                official_website=m["website"],
                market_status=MarketStatus.CURRENT,
            )
            self.manufacturers[m["name"].lower()] = mfr
    
    def discover_from_official_pages(self, manufacturer_name: str, urls: List[str]):
        """
        Discover models from official manufacturer pages.
        This is Phase A — identity discovery.
        """
        if manufacturer_name.lower() not in self.manufacturers:
            return
        
        mfr = self.manufacturers[manufacturer_name.lower()]
        
        for url in urls:
            # Acquire content
            if self.ladder:
                result = self.ladder.acquire(url)
                if result.status.value != "OK":
                    continue
                content = result.content
                method = result.acquisition_method
            else:
                continue
            
            # Extract model names from content
            models = self._extract_models_from_content(content, manufacturer_name)
            
            for model_name in models:
                # Create or find model
                model = self._find_or_create_model(mfr, model_name)
                
                # Add identity evidence
                evidence = EvidenceLink(
                    source_url=url,
                    source_domain=self._extract_domain(url),
                    source_class="official",
                    evidence_strength=EvidenceStrength.OFFICIAL,
                    evidence_text=f"Model '{model_name}' found on official page",
                    acquisition_method=method,
                )
                model.identity_evidence.append(evidence)
                model.market_status = MarketStatus.CURRENT
    
    def discover_from_media(self, manufacturer_name: str, urls: List[str]):
        """
        Discover models from automotive media.
        Phase A — identity discovery with weaker evidence.
        """
        if manufacturer_name.lower() not in self.manufacturers:
            return
        
        mfr = self.manufacturers[manufacturer_name.lower()]
        
        for url in urls:
            if self.ladder:
                result = self.ladder.acquire(url)
                if result.status.value != "OK":
                    continue
                content = result.content
                method = result.acquisition_method
            else:
                continue
            
            # Extract model names
            models = self._extract_models_from_content(content, manufacturer_name)
            
            for model_name in models:
                model = self._find_or_create_model(mfr, model_name)
                
                evidence = EvidenceLink(
                    source_url=url,
                    source_domain=self._extract_domain(url),
                    source_class="media",
                    evidence_strength=EvidenceStrength.HIGH_QUALITY_MEDIA,
                    evidence_text=f"Model '{model_name}' mentioned in article",
                    acquisition_method=method,
                )
                model.identity_evidence.append(evidence)
    
    def capture_opportunistic_specs(self, manufacturer_name: str, model_name: str,
                                     variant_name: str, specs: Dict):
        """
        Phase B: Opportunistic enrichment.
        Capture price/spec when encountered during discovery.
        """
        mfr = self.manufacturers.get(manufacturer_name.lower())
        if not mfr:
            return
        
        model = self._find_or_create_model(mfr, model_name)
        variant = self._find_or_create_variant(model, variant_name)
        
        # Capture price if present
        if "price" in specs:
            variant.price_thb = specs["price"]
            variant.price_type = specs.get("price_type", "UNKNOWN")
            variant.price_source_url = specs.get("source_url", "")
        
        # Capture powertrain if present
        if any(k in specs for k in ["fuel_type", "horsepower", "engine_displacement"]):
            if not variant.powertrain:
                variant.powertrain = Powertrain()
            pt = variant.powertrain
            if "fuel_type" in specs:
                pt.fuel_type = specs["fuel_type"]
            if "horsepower" in specs:
                pt.horsepower_hp = specs["horsepower"]
            if "torque" in specs:
                pt.torque_nm = specs["torque"]
            if "transmission" in specs:
                pt.transmission = specs["transmission"]
            if "drivetrain" in specs:
                pt.drivetrain = specs["drivetrain"]
            if "battery_kwh" in specs:
                pt.battery_kwh = specs["battery_kwh"]
            if "range_km" in specs:
                pt.range_km = specs["range_km"]
    
    def _extract_models_from_content(self, content: str, manufacturer_name: str) -> List[str]:
        """Extract model names from article content."""
        models = set()
        
        # Known model patterns for Thai market
        model_patterns = {
            "Honda": [r"Civic", r"City", r"CR-V", r"HR-V", r"Accord", r"ZR-V", r"WR-V", r"BR-V", r"Odyssey", r"Freed", r"Jazz"],
            "Toyota": [r"Camry", r"Corolla", r"Yaris", r"Fortuner", r"Hilux", r"CHR", r"RAV4", r"Alphard", r"Vellfire", r"Innova", r"Avanza", r"Veloz", r"bZ4X", r"Vios", r"Altis"],
            "Mazda": [r"Mazda2", r"Mazda3", r"Mazda6", r"CX-3", r"CX-30", r"CX-5", r"CX-8", r"CX-9", r"BT-50", r"MX-5"],
            "Nissan": [r"Almera", r"Kicks", r"X-Trail", r"Navara", r"Z", r"LEAF"],
            "Mitsubishi": [r"Attrage", r"Mirage", r"Xpander", r"Triton", r"Pajero", r"Outlander"],
            "Suzuki": [r"Celerio", r"Swift", r"Jimny", r"Ertiga", r"XL7", r"Ciaz"],
            "Isuzu": [r"D-Max", r"MU-X", r"MUX"],
            "MG": [r"MG3", r"MG5", r"ZS", r"HS", r"EP", r"MG4", r"Cyberster", r"MG EV"],
            "BYD": [r"Atto 3", r"Dolphin", r"Seal", r"M6", r"Sealion 6", r"Sealion 7"],
            "Haval": [r"H6", r"Jolion", r"Big Dog"],
            "GWM": [r"Haval", r"Tank", r"Poer"],
            "BMW": [r"Series [1-8]", r"X[1-7]", r"Z[3-4]", r"iX", r"i[3-7]"],
            "Mercedes-Benz": [r"A-Class", r"B-Class", r"C-Class", r"E-Class", r"S-Class", r"GLA", r"GLB", r"GLC", r"GLE", r"GLS", r"EQ"],
            "Volvo": [r"XC40", r"XC60", r"XC90", r"XC40 Recharge", r"XC60 Recharge", r"EX30", r"EX40", r"EC40"],
            "Ford": [r"Ranger", r"Everest", r"Territory", r"Mustang"],
            "Chevrolet": [r"Trailblazer", r"Colorado", r"Captiva", r"Corvette"],
            "Subaru": [r"Forester", r"XV", r"Outback", r"BRZ"],
            "Kia": [r"Carnival", r"Sportage", r"Seltos", r"EV6", r"EV9", r"Niro"],
            "Hyundai": [r"Accent", r"Tucson", r"Santa Fe", r"Ioniq"],
            "Wuling": [r"EKSION", r"Air EV", r"Almaz"],
            "ZEEKR": [r"001", r"009", r"X"],
            "NETA": [r"V", r"S", r"X", r"L"],
            "ORA": [r"Good Cat", r"07", r"03"],
            "Deepal": [r"S07", r"SL03"],
            "Changan": [r"CORS", r"UNI", r"Hunter"],
        }
        
        patterns = model_patterns.get(manufacturer_name, [])
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for m in matches:
                models.add(m.strip())
        
        return list(models)
    
    def _find_or_create_model(self, manufacturer: Manufacturer, model_name: str) -> Model:
        """Find existing model or create new one."""
        for m in manufacturer.models:
            if m.model_name.lower() == model_name.lower():
                return m
        
        model = Model(
            model_name=model_name,
        )
        manufacturer.models.append(model)
        return model
    
    def _find_or_create_variant(self, model: Model, variant_name: str) -> Variant:
        """Find existing variant or create new one."""
        # Check in all generations
        for gen in model.generations:
            for v in gen.variants:
                if v.variant_name.lower() == variant_name.lower():
                    return v
        
        # Create in default generation
        if not model.generations:
            model.generations.append(Generation(generation_name="current"))
        
        gen = model.generations[0]
        variant = Variant(variant_name=variant_name)
        gen.variants.append(variant)
        return variant
    
    def _extract_domain(self, url: str) -> str:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    
    def build_inventory(self) -> List[CatalogEntry]:
        """Build catalog inventory from discovered data."""
        entries = []
        
        for mfr in self.manufacturers.values():
            for model in mfr.models:
                # Model-level entry
                identity = CatalogIdentity(
                    manufacturer=mfr,
                    model=model,
                )
                
                # Find strongest evidence
                all_evidence = model.identity_evidence[:]
                for gen in model.generations:
                    all_evidence.extend(gen.identity_evidence)
                    for var in gen.variants:
                        all_evidence.extend(var.identity_evidence)
                
                # Determine market status
                status = model.market_status
                if status == MarketStatus.UNKNOWN and all_evidence:
                    status = MarketStatus.CURRENT  # Assume current if we found it
                
                entry = CatalogEntry(
                    identity=identity,
                    market_status=status,
                    all_evidence=all_evidence,
                    source_count=len(set(e.source_domain for e in all_evidence)),
                    has_price=any(v.price_thb for gen in model.generations for v in gen.variants),
                    has_specs=any(v.powertrain for gen in model.generations for v in gen.variants),
                )
                
                if entry.source_count > 0:
                    entry.strongest_source = max(
                        all_evidence,
                        key=lambda e: {
                            EvidenceStrength.OFFICIAL: 0,
                            EvidenceStrength.LAUNCH_DOC: 1,
                            EvidenceStrength.HIGH_QUALITY_MEDIA: 2,
                            EvidenceStrength.SECONDARY: 3,
                            EvidenceStrength.UNRESOLVED: 4,
                        }.get(e.evidence_strength, 4)
                    ).source_domain
                    entry.strongest_strength = max(
                        all_evidence,
                        key=lambda e: -{
                            EvidenceStrength.OFFICIAL: 0,
                            EvidenceStrength.LAUNCH_DOC: 1,
                            EvidenceStrength.HIGH_QUALITY_MEDIA: 2,
                            EvidenceStrength.SECONDARY: 3,
                            EvidenceStrength.UNRESOLVED: 4,
                        }.get(e.evidence_strength, 4)
                    ).evidence_strength
                
                entries.append(entry)
        
        self.entries = entries
        return entries
