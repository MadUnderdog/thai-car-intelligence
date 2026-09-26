"""
Thai market source maps — structured discovery sources per manufacturer.
Playwright-based for JS-rendered sites, Crawl4AI for server-rendered.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class SourceEntry:
    url: str
    source_type: str  # "official_lineup", "official_price", "media_article"
    source_class: str  # "official", "media", "secondary"
    extraction_method: str = "playwright"  # "playwright", "crawl4ai", "trafilatura"
    notes: str = ""


@dataclass
class ManufacturerSources:
    name: str
    thai_name: str
    official_website: str = ""
    sources: List[SourceEntry] = field(default_factory=list)
    expected_models: List[str] = field(default_factory=list)


# PILOT MANUFACTURER SOURCE MAPS
MANUFACTURER_SOURCE_MAPS: Dict[str, ManufacturerSources] = {
    "Toyota": ManufacturerSources(
        name="Toyota",
        thai_name="โตโยต้า",
        official_website="https://www.toyota.co.th",
        sources=[
            SourceEntry("https://www.toyota.co.th/en/pricelist", "official_price", "official", "playwright", "Full price list with models and prices"),
        ],
    ),
    "Honda": ManufacturerSources(
        name="Honda",
        thai_name="ฮอนด้า",
        official_website="https://www.honda.co.th",
        sources=[
            SourceEntry("https://www.honda.co.th/en/automobile", "official_lineup", "official", "playwright", "Model index"),
            SourceEntry("https://www.honda.co.th/en/automobile/civic", "official_model", "official", "playwright", "Civic"),
            SourceEntry("https://www.honda.co.th/en/automobile/city", "official_model", "official", "playwright", "City"),
            SourceEntry("https://www.honda.co.th/en/automobile/cr-v", "official_model", "official", "playwright", "CR-V"),
            SourceEntry("https://www.honda.co.th/en/automobile/hr-v", "official_model", "official", "playwright", "HR-V"),
        ],
    ),
    "Mazda": ManufacturerSources(
        name="Mazda",
        thai_name="มาสด้า",
        official_website="https://www.mazda.co.th",
        sources=[
            SourceEntry("https://www.mazda.co.th/en/vehicles", "official_lineup", "official", "playwright", "All models with prices"),
        ],
    ),
    "MG": ManufacturerSources(
        name="MG",
        thai_name="เอ็มจี",
        official_website="https://www.mgcars.com",
        sources=[
            SourceEntry("https://www.mgcars.com/en/models", "official_lineup", "official", "playwright", "Model index"),
        ],
    ),
    "Nissan": ManufacturerSources(
        name="Nissan",
        thai_name="นิสสัน",
        official_website="https://www.nissan.co.th",
        sources=[
            SourceEntry("https://www.nissan.co.th/vehicles.html", "official_lineup", "official", "playwright", "All vehicles"),
        ],
    ),
    "BMW": ManufacturerSources(
        name="BMW",
        thai_name="บีเอ็มดับเบิลยู",
        official_website="https://www.bmw.co.th",
        sources=[
            SourceEntry("https://www.bmw.co.th/en/all-models.html", "official_lineup", "official", "crawl4ai", "All models"),
        ],
    ),
    "Mercedes-Benz": ManufacturerSources(
        name="Mercedes-Benz",
        thai_name="เมอร์เซเดส-เบนซ์",
        official_website="https://www.mercedes-benz.co.th",
        sources=[
            SourceEntry("https://www.mercedes-benz.co.th/passengercars.html", "official_lineup", "official", "playwright", "Passenger cars"),
        ],
    ),
    "BYD": ManufacturerSources(
        name="BYD",
        thai_name="บีวายดี",
        official_website="https://www.byd.com/th",
        sources=[
            SourceEntry("https://www.byd.com/th/car.html", "official_lineup", "official", "playwright", "All models"),
        ],
    ),
    "Wuling": ManufacturerSources(
        name="Wuling",
        thai_name="วูลิง",
        official_website="",
        sources=[
            SourceEntry("https://autolifethailand.tv/wuling-eksion-ev-bev-suv-coming-thailand-28-sep-2026/", "media_article", "media", "crawl4ai", "EKSION EV launch"),
        ],
    ),
    "GWM": ManufacturerSources(
        name="GWM",
        thai_name="เกรท วอลล์ มอเตอร์",
        official_website="https://www.gwm.co.th",
        sources=[
            SourceEntry("https://www.gwm.co.th/th/vehicle.html", "official_lineup", "official", "playwright", "All models"),
        ],
    ),
}
