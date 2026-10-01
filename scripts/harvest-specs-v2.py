#!/usr/bin/env python3
"""
Spec harvest engine v2 — extracts vehicle specifications from multiple Thai sources.
Priority: EV/HEV/PHEV specs first.
"""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, asdict
from typing import List, Optional
from urllib.request import Request, urlopen

@dataclass
class SpecObservation:
    source_name: str
    source_tier: str
    source_url: str
    article_title: Optional[str]
    manufacturer: str
    model: str
    variant: str
    spec_class: str
    spec_key: str
    raw_value: str
    normalized_value: Optional[float]
    unit: Optional[str]
    source_excerpt: str
    retrieval_timestamp: str
    content_hash: str
    model_year: Optional[str]
    market: str

CACHE_DIR = "/tmp/thai-car-spec-cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def fetch_url(url: str, retries: int = 2) -> Optional[str]:
    cache_key = hashlib.md5(url.encode()).hexdigest()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.html")
    if os.path.exists(cache_file):
        age = time.time() - os.path.getmtime(cache_file)
        if age < 86400:
            with open(cache_file, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept-Language": "th,en;q=0.9",
            })
            with urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(content)
                return content
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                print(f"  FAIL: {url} — {e}")
                return None

def extract_title(html: str) -> Optional[str]:
    m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
    return m.group(1).strip() if m else None

def extract_manufacturer(html: str, url: str) -> str:
    lower = (html + url).lower()
    for m in ["honda", "toyota", "byd", "mg", "ford", "hyundai", "nissan",
              "suzuki", "bmw", "mercedes", "lexus", "tesla", "geely", "gwm",
              "changan", "nio", "mazda", "subaru", "mitsubishi", "kia", "volvo",
              "zeekr", "avatr", "denza", "porsche", "ferrari", "bentley", "mini",
              "lepas", "deepal", "xpeng"]:
        if m in lower:
            return m.capitalize()
    return "Unknown"

def extract_model_from_url(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(r'^(official-price|special-price|estimated-price|spec|specification)-', '', slug)
    slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug)
    return slug.replace("-", " ").title()

def content_hash(url: str, model: str, variant: str, key: str, value: str) -> str:
    s = f"{url}|{model}|{variant}|{key}|{value}"
    return hashlib.md5(s.encode()).hexdigest()[:12]

def normalize_numeric(raw: str) -> Optional[float]:
    cleaned = raw.replace(",", "").replace(" ", "")
    m = re.search(r'([\d.]+)', cleaned)
    if m:
        try:
            return float(m.group(1))
        except:
            pass
    return None

def extract_spec_value(html: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, html, re.I)
    return m.group(1).strip() if m else None

def harvest_article_specs(url: str, source_name: str, source_tier: str) -> List[SpecObservation]:
    """Extract specs from any article page."""
    html = fetch_url(url)
    if not html:
        return []
    
    title = extract_title(html)
    manufacturer = extract_manufacturer(html, url)
    model = extract_model_from_url(url)
    ts = "2026-09-18T16:00:00Z"
    observations = []
    
    specs = {
        # Performance
        "power_hp": (r'(\d+[\d,.]*)\s*(?:แรงม้า|PS|hp| horsepower)', "performance", "powerKw", "hp"),
        "torque_nm": (r'(\d+[\d,.]*)\s*(?:Nm|นิวตันเมตร| Newton)', "performance", "torqueNm", "Nm"),
        "range_km": (r'(?:Range|ระยะทาง|วิ่งได้|วิ่งไกลสุด)[^<]*?(\d+[\d,.]*)\s*(?:km|กม)', "performance", "rangeKm", "km"),
        "acceleration": (r'(?:0-100|acceleration)[^<]*?(\d+[\d,.]*)\s*(?:s|วินาที)', "performance", "acceleration0To100S", "s"),
        "top_speed": (r'(?:Top Speed|ความเร็วสูงสุด)[^<]*?(\d+[\d,.]*)\s*(?:km/h)', "performance", "topSpeedKph", "km/h"),
        
        # Battery
        "battery_kwh": (r'(\d+[\d,.]*)\s*(?:kWh|กิโลวัตต์)', "battery", "capacityKwh", "kWh"),
        "battery_chemistry": (r'(?:Battery|แบตเตอรี่)[^<]*?(?:Type|ชนิด|Technology)[^<]*?(\w+)', "battery", "chemistry", None),
        
        # Charging
        "ac_charging": (r'(?:AC Charging|ชาร์จ AC|ชาร์จ alternating)[^<]*?(\d+[\d,.]*)\s*(?:kW|กิโลวัตต์)', "charging", "acPowerKw", "kW"),
        "dc_charging": (r'(?:DC Fast|DC Charging|ชาร์จ DC|ชาร์จ direct|ชาร์จเร็ว)[^<]*?(\d+[\d,.]*)\s*(?:kW|กิโลวัตต์)', "charging", "dcPowerKw", "kW"),
        
        # Dimensions
        "length_mm": (r'(?:Length|ความยาว|ยาว)[^<]*?(\d+[\d,.]*)\s*(?:mm|มม)', "dimensions", "lengthMm", "mm"),
        "width_mm": (r'(?:Width|ความกว้าง|กว้าง)[^<]*?(\d+[\d,.]*)\s*(?:mm|มม)', "dimensions", "widthMm", "mm"),
        "height_mm": (r'(?:Height|ความสูง|สูง)[^<]*?(\d+[\d,.]*)\s*(?:mm|มม)', "dimensions", "heightMm", "mm"),
        "wheelbase_mm": (r'(?:Wheelbase|ฐานล้อ)[^<]*?(\d+[\d,.]*)\s*(?:mm|มม)', "dimensions", "wheelbaseMm", "mm"),
        "ground_clearance": (r'(?:Ground Clearance|ระยะต่ำสุด| Clearance)[^<]*?(\d+[\d,.]*)\s*(?:mm|มม)', "dimensions", "groundClearanceMm", "mm"),
        "curb_weight": (r'(?:Weight|น้ำหนัก|Curb Weight)[^<]*?(\d+[\d,.]*)\s*(?:kg|กก)', "dimensions", "curbWeightKg", "kg"),
        
        # Drivetrain
        "motor_count": (r'(?:Motor|มอเตอร์)[^<]*?(\d+)\s*(?:motor|ตัว)', "drivetrain", "motorCount", "count"),
        "driven_wheels": (r'(?:Driven|ขับเคลื่อน)[^<]*?(FWD|RWD|AWD|4WD|2WD|หน้า|หลัง|สี่ล้อ)', "drivetrain", "driveType", None),
        
        # Warranty
        "warranty_years": (r'(?:Warranty|ประกัน)[^<]*?(\d+)\s*(?:year|ปี)', "warranty", "vehicleYears", "years"),
        "warranty_km": (r'(?:Warranty|ประกัน)[^<]*?(\d+[\d,.]*)\s*(?:km|กม)', "warranty", "vehicleDistanceKm", "km"),
        
        # Safety
        "airbags": (r'(?:Airbag|ถุงลม)[^<]*?(\d+)\s*(?:ลูก|airbag)', "safety", "airbags", "count"),
        
        # Body
        "seats": (r'(?:Seat|ที่นั่ง)[^<]*?(\d+)\s*(?:ที่นั่ง|seat)', "body", "seatingCapacity", "count"),
    }
    
    for key, (pattern, spec_class, spec_key, unit) in specs.items():
        value = extract_spec_value(html, pattern)
        if value:
            num = normalize_numeric(value)
            excerpt_start = max(0, html.lower().find(value.lower()) - 50)
            excerpt = re.sub(r'<[^>]+>', ' ', html[excerpt_start:excerpt_start+150]).strip()
            
            observations.append(SpecObservation(
                source_name=source_name,
                source_tier=source_tier,
                source_url=url,
                article_title=title,
                manufacturer=manufacturer,
                model=model,
                variant="Standard",
                spec_class=spec_class,
                spec_key=spec_key,
                raw_value=value,
                normalized_value=num,
                unit=unit,
                source_excerpt=excerpt[:200],
                retrieval_timestamp=ts,
                content_hash=content_hash(url, model, "Standard", spec_key, value),
                model_year="2026",
                market="Thailand",
            ))
    
    return observations

def main():
    all_observations: List[SpecObservation] = []
    
    # === HEADLIGHT ARTICLES (price articles often contain specs) ===
    headlight_urls = [
        "https://www.headlightmag.com/official-price-byd-seal-6-2026/",
        "https://www.headlightmag.com/official-price-byd-sealion-5-dm-i-super-phev/",
        "https://www.headlightmag.com/official-price-mg4-my2026-2/",
        "https://www.headlightmag.com/official-price-mg-im-5-long-range-rwd/",
        "https://www.headlightmag.com/official-price-honda-en2/",
        "https://www.headlightmag.com/official-price-tesla-model-y-l-long-wheelbase/",
        "https://www.headlightmag.com/official-price-nio-firefly/",
        "https://www.headlightmag.com/official-price-zeekr-x-my-2026/",
        "https://www.headlightmag.com/official-price-geely-ex5-my2026/",
        "https://www.headlightmag.com/official-price-hyundai-ioniq-5-n-line-ckd-thailand-2nd-lot/",
        "https://www.headlightmag.com/official-price-byd-sealion-7-2026-awd-ultimate/",
        "https://www.headlightmag.com/official-price-gwm-tank-500-diesel-2026/",
        "https://www.headlightmag.com/official-price-honda-super-one/",
        "https://www.headlightmag.com/official-price-geely-starray-em-r-reev/",
        "https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/",
        "https://www.headlightmag.com/official-price-honda-accord-2026/",
        "https://www.headlightmag.com/official-price-mg-urban-2026/",
        "https://www.headlightmag.com/official-price-nissan-kicks-e-power-minorchange-2026/",
        "https://www.headlightmag.com/official-price-ford-everest-platinum-my2026/",
        "https://www.headlightmag.com/official-price-ford-ranger-wildtrak-x-my2026/",
        "https://www.headlightmag.com/official-price-hyundai-santa-fe-my2026/",
        "https://www.headlightmag.com/official-price-subaru-crosstrek/",
        "https://www.headlightmag.com/official-price-mazda-6e-edit/",
        "https://www.headlightmag.com/official-price-toyota-land-cruiser-fj/",
        "https://www.headlightmag.com/official-price-bmw-ix3-na5/",
        "https://www.headlightmag.com/official-price-toyota-corolla-altis-my2026/",
        "https://www.headlightmag.com/official-price-suzuki-jimny-with-safety-support-my2026/",
        "https://www.headlightmag.com/official-price-changan-nevo-q05/",
        "https://www.headlightmag.com/official-price-lepas-l6/",
        "https://www.headlightmag.com/official-price-avatr-11-my2026/",
    ]
    
    print(f"=== Harvesting HeadLight Specs ({len(headlight_urls)} articles) ===")
    for i, url in enumerate(headlight_urls):
        obs = harvest_article_specs(url, "HeadLight Magazine", "secondary_automotive_media")
        all_observations.extend(obs)
        print(f"  [{i+1}/{len(headlight_urls)}] {url.split('/')[-2][:40]}: {len(obs)} specs")
        time.sleep(0.3)
    
    # === AUTOLIFETHAILAND ===
    autolife_urls = [
        "https://autolifethailand.tv/official-price-tesla-model-y-thailand/",
        "https://autolifethailand.tv/official-price-tesla-model-3-official-thailand/",
        "https://autolifethailand.tv/offcial-price-denza-z9gt-ev-bev-thailand-2026/",
        "https://autolifethailand.tv/official-special-price-byd-seal-5-dm-i-phev-plug-in-hybrid-sep-2026/",
        "https://autolifethailand.tv/official-price-discount-byd-sealion-5-dm-i-phev-sep-2026/",
        "https://autolifethailand.tv/official-price-discount-byd-atto-2-ev-bev-sep-2026/",
    ]
    
    print(f"\n=== Harvesting AutoLifeThailand Specs ({len(autolife_urls)} articles) ===")
    for i, url in enumerate(autolife_urls):
        obs = harvest_article_specs(url, "AutoLifeThailand", "secondary_automotive_media")
        all_observations.extend(obs)
        print(f"  [{i+1}/{len(autolife_urls)}] {url.split('/')[-2][:40]}: {len(obs)} specs")
        time.sleep(0.3)
    
    # === HEADLIGHT SPEC ARTICLES ===
    headlight_spec_urls = [
        "https://www.headlightmag.com/xpeng-l03-standard-long-range-thailand-specs/",
        "https://www.headlightmag.com/specification-gwm-tank-500-diesel-3000-turbo-my2026/",
        "https://www.headlightmag.com/2026-08-14-picture-specs-honda-super-one/",
        "https://www.headlightmag.com/2026-08-13-picture-specs-all-new-lexus-es-350h-grand-luxury-es-350e-premium/",
        "https://www.headlightmag.com/2026-09-08-picture-specs-geely-starray-em-r-max/",
        "https://www.headlightmag.com/2026-09-28-picture-specs-mazda-6e-exclusive/",
        "https://www.headlightmag.com/2026-09-26-picture-specs-toyota-land-cruiser-fj-edit/",
    ]
    
    print(f"\n=== Harvesting HeadLight Spec Articles ({len(headlight_spec_urls)} articles) ===")
    for i, url in enumerate(headlight_spec_urls):
        obs = harvest_article_specs(url, "HeadLight Magazine", "secondary_automotive_media")
        all_observations.extend(obs)
        print(f"  [{i+1}/{len(headlight_spec_urls)}] {url.split('/')[-2][:40]}: {len(obs)} specs")
        time.sleep(0.3)
    
    # === OUTPUT ===
    print(f"\n=== TOTAL: {len(all_observations)} spec observations ===")
    
    output = [asdict(o) for o in all_observations]
    with open("/home/ubuntu/Projects/thai-car-intelligence/scripts/harvested-specs-v2.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"Written to scripts/harvested-specs-v2.json")
    
    sources = {}
    classes = {}
    for o in all_observations:
        sources[o.source_name] = sources.get(o.source_name, 0) + 1
        classes[o.spec_class] = classes.get(o.spec_class, 0) + 1
    
    print("\nBy source:")
    for s, c in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")
    
    print("\nBy spec class:")
    for cl, c in sorted(classes.items(), key=lambda x: -x[1]):
        print(f"  {cl}: {c}")

if __name__ == "__main__":
    main()
