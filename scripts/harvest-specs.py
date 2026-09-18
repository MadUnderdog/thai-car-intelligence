#!/usr/bin/env python3
"""
Spec harvest engine — extracts vehicle specifications from Thai automotive sources.
Priority: EV/HEV/PHEV specs first (battery, charging, motor, range, dimensions).
"""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
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
    spec_class: str  # performance, dimensions, battery, charging, drivetrain, safety, warranty, body, features
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
    slug = re.sub(r'^(official-price|special-price|estimated-price|spec)-', '', slug)
    slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug)
    return slug.replace("-", " ").title()

def content_hash(url: str, model: str, variant: str, key: str, value: str) -> str:
    s = f"{url}|{model}|{variant}|{key}|{value}"
    return hashlib.md5(s.encode()).hexdigest()[:12]

def normalize_numeric(raw: str) -> Optional[float]:
    """Extract numeric value from string."""
    cleaned = raw.replace(",", "").replace(" ", "")
    m = re.search(r'([\d.]+)', cleaned)
    if m:
        try:
            return float(m.group(1))
        except:
            pass
    return None

def extract_spec_value(html: str, pattern: str) -> Optional[str]:
    """Extract a spec value using regex pattern."""
    m = re.search(pattern, html, re.I)
    return m.group(1).strip() if m else None

def harvest_9carthai_specs(url: str, model_name: str) -> List[SpecObservation]:
    """Extract specs from 9CARTHAI specification page."""
    html = fetch_url(url)
    if not html:
        return []
    
    title = extract_title(html)
    manufacturer = extract_manufacturer(html, url)
    ts = "2026-09-18T15:00:00Z"
    observations = []
    
    # Performance specs
    specs = {
        "power": (r'(?:กำลังเครื่องยนต์|Power|แรงม้า| horsepower)[^<]*?(\d+[\d,.]*)\s*(?:PS|hp| kW|馬力)', "performance", "powerKw", "kW"),
        "torque": (r'( torque|แรงบิด)[^<]*?(\d+[\d,.]*)\s*(?:Nm|kg-m)', "performance", "torqueNm", "Nm"),
        "battery": (r'(?:Battery|แบตเตอรี่|ความจุ)[^<]*?(\d+[\d,.]*)\s*(?:kWh|กิโลวัตต์)', "battery", "capacityKwh", "kWh"),
        "range": (r'(?:Range|ระยะทาง|วิ่งได้)[^<]*?(\d+[\d,.]*)\s*(?:km|กม)', "performance", "rangeKm", "km"),
        "ac_charging": (r'(?:AC Charging|ชาร์จ AC)[^<]*?(\d+[\d,.]*)\s*(?:kW|กิโลวัตต์)', "charging", "acPowerKw", "kW"),
        "dc_charging": (r'(?:DC Charging|ชาร์จ DC)[^<]*?(\d+[\d,.]*)\s*(?:kW|กิโลวัตต์)', "charging", "dcPowerKw", "kW"),
        "length": (r'(?:Length|ความยาว)[^<]*?(\d+[\d,.]*)\s*(?:mm|มม)', "dimensions", "lengthMm", "mm"),
        "width": (r'(?:Width|ความกว้าง)[^<]*?(\d+[\d,.]*)\s*(?:mm|มม)', "dimensions", "widthMm", "mm"),
        "height": (r'(?:Height|ความสูง)[^<]*?(\d+[\d,.]*)\s*(?:mm|มม)', "dimensions", "heightMm", "mm"),
        "wheelbase": (r'(?:Wheelbase|ฐานล้อ)[^<]*?(\d+[\d,.]*)\s*(?:mm|มม)', "dimensions", "wheelbaseMm", "mm"),
        "ground_clearance": (r'(?:Ground Clearance|ระยะต่ำสุด)[^<]*?(\d+[\d,.]*)\s*(?:mm|มม)', "dimensions", "groundClearanceMm", "mm"),
        "weight": (r'(?:Weight|น้ำหนัก|Curb Weight)[^<]*?(\d+[\d,.]*)\s*(?:kg|กก)', "dimensions", "curbWeightKg", "kg"),
        "acceleration": (r'(?:0-100|acceleration)[^<]*?(\d+[\d,.]*)\s*(?:s|วินาที)', "performance", "acceleration0To100S", "s"),
        "top_speed": (r'(?:Top Speed|ความเร็วสูงสุด)[^<]*?(\d+[\d,.]*)\s*(?:km/h)', "performance", "topSpeedKph", "km/h"),
        "airbags": (r'(?:Airbag|ถุงลม)[^<]*?(\d+)\s*(?:ลูก|airbag)', "safety", "airbags", "count"),
    }
    
    for key, (pattern, spec_class, spec_key, unit) in specs.items():
        value = extract_spec_value(html, pattern)
        if value:
            num = normalize_numeric(value)
            excerpt_start = max(0, html.lower().find(value.lower()) - 50)
            excerpt = re.sub(r'<[^>]+>', ' ', html[excerpt_start:excerpt_start+150]).strip()
            
            observations.append(SpecObservation(
                source_name="9CARTHAI",
                source_tier="secondary_automotive_reference",
                source_url=url,
                article_title=title,
                manufacturer=manufacturer,
                model=model_name,
                variant="Standard",
                spec_class=spec_class,
                spec_key=spec_key,
                raw_value=value,
                normalized_value=num,
                unit=unit,
                source_excerpt=excerpt[:200],
                retrieval_timestamp=ts,
                content_hash=content_hash(url, model_name, "Standard", spec_key, value),
                model_year="2026",
                market="Thailand",
            ))
    
    return observations

def harvest_headlight_specs(url: str) -> List[SpecObservation]:
    """Extract specs from HeadLight Magazine article."""
    html = fetch_url(url)
    if not html:
        return []
    
    title = extract_title(html)
    manufacturer = extract_manufacturer(html, url)
    model = extract_model_from_url(url)
    ts = "2026-09-18T15:00:00Z"
    observations = []
    
    specs = {
        "power": (r'(?:กำลัง|Power|แรงม้า| horsepower)[^<]*?(\d+[\d,.]*)\s*(?:PS|hp| kW)', "performance", "powerKw", "kW"),
        "torque": (r'( torque|แรงบิด)[^<]*?(\d+[\d,.]*)\s*(?:Nm)', "performance", "torqueNm", "Nm"),
        "battery": (r'(?:Battery|แบตเตอรี่|ความจุ)[^<]*?(\d+[\d,.]*)\s*(?:kWh)', "battery", "capacityKwh", "kWh"),
        "range": (r'(?:Range|ระยะทาง)[^<]*?(\d+[\d,.]*)\s*(?:km|กม)', "performance", "rangeKm", "km"),
        "dc_charging": (r'(?:DC Fast|ชาร์จเร็ว)[^<]*?(\d+[\d,.]*)\s*(?:kW)', "charging", "dcPowerKw", "kW"),
        "length": (r'(?:ยาว|Length)[^<]*?(\d+[\d,.]*)\s*(?:mm)', "dimensions", "lengthMm", "mm"),
        "width": (r'(?:กว้าง|Width)[^<]*?(\d+[\d,.]*)\s*(?:mm)', "dimensions", "widthMm", "mm"),
        "height": (r'(?:สูง|Height)[^<]*?(\d+[\d,.]*)\s*(?:mm)', "dimensions", "heightMm", "mm"),
    }
    
    for key, (pattern, spec_class, spec_key, unit) in specs.items():
        value = extract_spec_value(html, pattern)
        if value:
            num = normalize_numeric(value)
            excerpt_start = max(0, html.lower().find(value.lower()) - 50)
            excerpt = re.sub(r'<[^>]+>', ' ', html[excerpt_start:excerpt_start+150]).strip()
            
            observations.append(SpecObservation(
                source_name="HeadLight Magazine",
                source_tier="secondary_automotive_media",
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

def harvest_autolife_specs(url: str) -> List[SpecObservation]:
    """Extract specs from AutoLifeThailand article."""
    html = fetch_url(url)
    if not html:
        return []
    
    title = extract_title(html)
    manufacturer = extract_manufacturer(html, url)
    model = extract_model_from_url(url)
    ts = "2026-09-18T15:00:00Z"
    observations = []
    
    specs = {
        "power": (r'(?:กำลัง|Power|แรงม้า| horsepower)[^<]*?(\d+[\d,.]*)\s*(?:PS|hp| kW)', "performance", "powerKw", "kW"),
        "battery": (r'(?:Battery|แบตเตอรี่|ความจุ)[^<]*?(\d+[\d,.]*)\s*(?:kWh)', "battery", "capacityKwh", "kWh"),
        "range": (r'(?:Range|ระยะทาง)[^<]*?(\d+[\d,.]*)\s*(?:km|กม)', "performance", "rangeKm", "km"),
        "dc_charging": (r'(?:DC Fast|ชาร์จเร็ว)[^<]*?(\d+[\d,.]*)\s*(?:kW)', "charging", "dcPowerKw", "kW"),
    }
    
    for key, (pattern, spec_class, spec_key, unit) in specs.items():
        value = extract_spec_value(html, pattern)
        if value:
            num = normalize_numeric(value)
            excerpt_start = max(0, html.lower().find(value.lower()) - 50)
            excerpt = re.sub(r'<[^>]+>', ' ', html[excerpt_start:excerpt_start+150]).strip()
            
            observations.append(SpecObservation(
                source_name="AutoLifeThailand",
                source_tier="secondary_automotive_media",
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
    
    # === 9CARTHAI SPEC PAGES ===
    # Priority: EV/HEV/PHEV models first
    ninecar_spec_urls = [
        ("https://www.9carthai.com/byd-seal-6-spec/", "Seal 6"),
        ("https://www.9carthai.com/byd-sealion-5-spec/", "Sealion 5"),
        ("https://www.9carthai.com/byd-atto-3-spec/", "Atto 3"),
        ("https://www.9carthai.com/byd-dolphin-spec/", "Dolphin"),
        ("https://www.9carthai.com/mg-zs-ev-spec/", "ZS EV"),
        ("https://www.9carthai.com/mg4-spec/", "MG4"),
        ("https://www.9carthai.com/mg-im5-spec/", "IM5"),
        ("https://www.9carthai.com/mg-im6-spec/", "IM6"),
        ("https://www.9carthai.com/honda-city-ehev-spec/", "City e:HEV"),
        ("https://www.9carthai.com/honda-civic-ehev-spec/", "Civic e:HEV"),
        ("https://www.9carthai.com/honda-hr-v-ehev-spec/", "HR-V e:HEV"),
        ("https://www.9carthai.com/honda-cr-v-ehev-spec/", "CR-V e:HEV"),
        ("https://www.9carthai.com/honda-accord-ehev-spec/", "Accord e:HEV"),
        ("https://www.9carthai.com/honda-en2-spec/", "e:N2"),
        ("https://www.9carthai.com/toyota-yaris-cross-hev-spec/", "Yaris Cross HEV"),
        ("https://www.9carthai.com/toyota-camry-hev-spec/", "Camry HEV"),
        ("https://www.9carthai.com/hyundai-ioniq-5-spec/", "Ioniq 5"),
        ("https://www.9carthai.com/hyundai-kona-ev-spec/", "Kona EV"),
        ("https://www.9carthai.com/tesla-model-y-spec/", "Model Y"),
        ("https://www.9carthai.com/tesla-model-3-spec/", "Model 3"),
        ("https://www.9carthai.com/nissan-leaf-spec/", "Leaf"),
        ("https://www.9carthai.com/bmw-ix3-spec/", "iX3"),
        ("https://www.9carthai.com/zeekr-x-spec/", "Zeekr X"),
        ("https://www.9carthai.com/nio-firefly-spec/", "Firefly"),
        ("https://www.9carthai.com/geely-ex5-spec/", "EX5"),
        ("https://www.9carthai.com/gwm-ora-5-spec/", "ORA 5"),
        ("https://www.9carthai.com/mazda-6e-spec/", "Mazda 6e"),
        ("https://www.9carthai.com/avatr-11-spec/", "Avatr 11"),
        ("https://www.9carthai.com/denza-z9gt-spec/", "Z9GT"),
        ("https://www.9carthai.com/honda-super-one-spec/", "Super-ONE"),
    ]
    
    print(f"=== Harvesting 9CARTHAI Specs ({len(ninecar_spec_urls)} pages) ===")
    for i, (url, model) in enumerate(ninecar_spec_urls):
        obs = harvest_9carthai_specs(url, model)
        all_observations.extend(obs)
        print(f"  [{i+1}/{len(ninecar_spec_urls)}] {model}: {len(obs)} specs")
        time.sleep(0.3)
    
    # === HEADLIGHT SPEC ARTICLES ===
    headlight_spec_urls = [
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
    ]
    
    print(f"\n=== Harvesting HeadLight Specs ({len(headlight_spec_urls)} articles) ===")
    for i, url in enumerate(headlight_spec_urls):
        obs = harvest_headlight_specs(url)
        all_observations.extend(obs)
        print(f"  [{i+1}/{len(headlight_spec_urls)}] {url.split('/')[-2][:40]}: {len(obs)} specs")
        time.sleep(0.3)
    
    # === AUTOLIFETHAILAND SPEC ARTICLES ===
    autolife_spec_urls = [
        "https://autolifethailand.tv/official-price-tesla-model-y-thailand/",
        "https://autolifethailand.tv/official-price-tesla-model-3-official-thailand/",
        "https://autolifethailand.tv/offcial-price-denza-z9gt-ev-bev-thailand-2026/",
    ]
    
    print(f"\n=== Harvesting AutoLifeThailand Specs ({len(autolife_spec_urls)} articles) ===")
    for i, url in enumerate(autolife_spec_urls):
        obs = harvest_autolife_specs(url)
        all_observations.extend(obs)
        print(f"  [{i+1}/{len(autolife_spec_urls)}] {url.split('/')[-2][:40]}: {len(obs)} specs")
        time.sleep(0.3)
    
    # === OUTPUT ===
    print(f"\n=== TOTAL: {len(all_observations)} spec observations ===")
    
    output = [asdict(o) for o in all_observations]
    with open("/home/ubuntu/Projects/thai-car-intelligence/scripts/harvested-specs.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"Written to scripts/harvested-specs.json")
    
    # Stats
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
