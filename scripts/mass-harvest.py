#!/usr/bin/env python3
"""
Mass harvest engine — fetches from multiple Thai automotive sources,
extracts prices using HTTP/HTML/JSON techniques, and outputs observations.
"""

import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from typing import List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

@dataclass
class Observation:
    source_name: str
    source_tier: str
    source_url: str
    article_title: Optional[str]
    publication_date: Optional[str]
    manufacturer: str
    model: str
    variant: str
    reported_price: int
    price_text: str
    price_type: str
    market: str
    model_year: Optional[str]
    source_excerpt: str
    retrieval_timestamp: str
    content_hash: str

def fetch_url(url: str, retries: int = 2) -> Optional[str]:
    """Step 1: HTTP fetch with retries."""
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept-Language": "th,en;q=0.9",
            })
            with urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                print(f"  FAIL: {url} — {e}", file=sys.stderr)
                return None

def extract_prices_from_html(html: str) -> List[tuple]:
    """Step 2: Extract prices from raw HTML."""
    prices = []
    # Pattern: "1,299,000 บาท" or "ราคา 1,299,000"
    for m in re.finditer(r'(\d{1,3}(?:,\d{3})+)\s*บาท', html):
        price_str = m.group(1)
        num = int(price_str.replace(",", ""))
        if num >= 300000:  # Filter noise
            # Get context around price
            start = max(0, m.start() - 150)
            end = min(len(html), m.end() + 50)
            context = re.sub(r'<[^>]+>', ' ', html[start:end]).strip()
            prices.append((num, price_str, context))
    
    # Also try "ราคา X" pattern
    for m in re.finditer(r'ราคา\s*(\d{1,3}(?:,\d{3})+)', html):
        price_str = m.group(1)
        num = int(price_str.replace(",", ""))
        if num >= 300000:
            prices.append((num, price_str, "ราคา " + price_str))
    
    return list(set(prices))  # Dedupe

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
    slug = re.sub(r'^(official-price|special-price|estimated-price)-', '', slug)
    # Remove date prefix if present
    slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug)
    return slug.replace("-", " ").title()

def extract_title(html: str) -> Optional[str]:
    m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
    return m.group(1).strip() if m else None

def detect_price_type(text: str) -> str:
    if re.search(r'อย่างเป็นทางการ|official price|ราคาจำหน่าย', text):
        return "manufacturer_msrp_reported"
    if re.search(r'เปิดตัว|launch', text):
        return "launch_price"
    if re.search(r'เริ่มต้น|starting', text):
        return "starting_price"
    if re.search(r'โปรโมชั่น|พิเศษ|campaign|ลด|discount', text):
        return "campaign_price"
    if re.search(r'หลังหักส่วนลด', text):
        return "after_discount"
    return "unknown"

def content_hash(url: str, model: str, variant: str, price: int) -> str:
    s = f"{url}|{model}|{variant}|{price}"
    return hashlib.md5(s.encode()).hexdigest()[:12]

def harvest_headlight(url: str) -> List[Observation]:
    """Extract observations from HeadLight Magazine article."""
    html = fetch_url(url)
    if not html:
        return []
    
    prices = extract_prices_from_html(html)
    title = extract_title(html)
    manufacturer = extract_manufacturer(html, url)
    model = extract_model_from_url(url)
    ts = "2026-09-17T14:00:00Z"
    
    obs_list = []
    for num, price_text, context in prices[:15]:  # Cap at 15 per article
        variant = "Standard"
        # Try to extract variant from context
        vm = re.search(r'(?:รุ่น|variant|grade)\s*[:：]?\s*([A-Za-z0-9\s\-\+\.]+)', context)
        if vm:
            variant = vm.group(1).strip()
        else:
            # Try to find variant name before price
            vm2 = re.search(r'([A-Z][A-Za-z0-9\s\-\+\.]{2,20})\s*\d{1,3}(?:,\d{3})+', context)
            if vm2:
                variant = vm2.group(1).strip()
        
        obs_list.append(Observation(
            source_name="HeadLight Magazine",
            source_tier="secondary_automotive_media",
            source_url=url,
            article_title=title,
            publication_date=None,
            manufacturer=manufacturer,
            model=model,
            variant=variant,
            reported_price=num,
            price_text=price_text,
            price_type=detect_price_type(context),
            market="Thailand",
            model_year=None,
            source_excerpt=context[:200],
            retrieval_timestamp=ts,
            content_hash=content_hash(url, model, variant, num),
        ))
    
    return obs_list

def harvest_autolife(url: str) -> List[Observation]:
    """Extract observations from AutoLifeThailand article."""
    html = fetch_url(url)
    if not html:
        return []
    
    prices = extract_prices_from_html(html)
    title = extract_title(html)
    manufacturer = extract_manufacturer(html, url)
    model = extract_model_from_url(url)
    ts = "2026-09-17T14:00:00Z"
    
    obs_list = []
    for num, price_text, context in prices[:10]:
        variant = "Standard"
        obs_list.append(Observation(
            source_name="AutoLifeThailand",
            source_tier="secondary_automotive_media",
            source_url=url,
            article_title=title,
            publication_date=None,
            manufacturer=manufacturer,
            model=model,
            variant=variant,
            reported_price=num,
            price_text=price_text,
            price_type=detect_price_type(context),
            market="Thailand",
            model_year=None,
            source_excerpt=context[:200],
            retrieval_timestamp=ts,
            content_hash=content_hash(url, model, variant, num),
        ))
    
    return obs_list

def harvest_9carthai(url: str) -> List[Observation]:
    """Extract observations from 9CARTHAI price list page."""
    html = fetch_url(url)
    if not html:
        return []
    
    # 9CARTHAI uses table format: "Model Variant ราคา X,XXX,XXX"
    prices = []
    for m in re.finditer(r'((?:BYD|MG|Honda|Toyota|Ford|Hyundai|Nissan|Suzuki|BMW|Tesla|Geely|GWM|Changan|NIO|Mazda|Subaru|Mitsubishi|Kia|Volvo|Zeekr|Avatr|Denza)[^<]*?(?:Dynamic|Premium|Standard|Extended|Performance|Sport|Smart|Elite|PLUS|HEV|BEV|PHEV|e:HEV|DM-i|Type R|Long Range|AWD|RWD|2WD|MT|AT|CVT|X|D|E|EL|RS|SV|GR|EL+|S\+|Shift|Wolftrak|Wildtrak|Platinum|NightShade|Luxury)[^<]*?)\s+(\d{1,3}(?:,\d{3})+)', html):
        variant_text = m.group(1).strip()
        price_str = m.group(2)
        num = int(price_str.replace(",", ""))
        if num >= 300000:
            prices.append((variant_text, num, price_str))
    
    # Fallback: simpler pattern
    if not prices:
        for m in re.finditer(r'((?:BYD|MG|Honda|Toyota|Ford|Hyundai|Nissan|Suzuki)[^<]{5,60})\s+(\d{1,3}(?:,\d{3})+)', html):
            variant_text = m.group(1).strip()
            price_str = m.group(2)
            num = int(price_str.replace(",", ""))
            if num >= 300000:
                prices.append((variant_text, num, price_str))
    
    title = extract_title(html)
    manufacturer = extract_manufacturer(html, url)
    ts = "2026-09-17T14:00:00Z"
    
    obs_list = []
    for variant_text, num, price_text in prices[:30]:
        # Parse manufacturer and model from variant_text
        parts = variant_text.split()
        model = " ".join(parts[:2]) if len(parts) > 2 else parts[0] if parts else "Unknown"
        variant = " ".join(parts[2:]) if len(parts) > 2 else "Standard"
        
        obs_list.append(Observation(
            source_name="9CARTHAI",
            source_tier="secondary_automotive_reference",
            source_url=url,
            article_title=title,
            publication_date=None,
            manufacturer=manufacturer,
            model=model,
            variant=variant,
            reported_price=num,
            price_text=price_text,
            price_type="manufacturer_msrp_reported",
            market="Thailand",
            model_year="2026",
            source_excerpt=variant_text[:200],
            retrieval_timestamp=ts,
            content_hash=content_hash(url, model, variant, num),
        ))
    
    return obs_list

def harvest_autospinn(url: str) -> List[Observation]:
    """Extract observations from AutoSpinn article."""
    html = fetch_url(url)
    if not html:
        return []
    
    prices = []
    # AutoSpinn format: "Model Variant = X,XXX,XXX" or "Model Variant X,XXX,XXX"
    for m in re.finditer(r'((?:BYD|MG|Honda|Toyota|Ford|Hyundai|Nissan|Suzuki|BMW|Tesla|Geely|GWM)[A-Za-z0-9\s\-\+\.]+?)\s*[=:]\s*(\d{1,3}(?:,\d{3})+)', html):
        variant_text = m.group(1).strip()
        price_str = m.group(2)
        num = int(price_str.replace(",", ""))
        if num >= 300000:
            prices.append((variant_text, num, price_str))
    
    title = extract_title(html)
    manufacturer = extract_manufacturer(html, url)
    ts = "2026-09-17T14:00:00Z"
    
    obs_list = []
    for variant_text, num, price_text in prices[:20]:
        parts = variant_text.split()
        model = parts[0] if parts else "Unknown"
        variant = " ".join(parts[1:]) if len(parts) > 1 else "Standard"
        
        obs_list.append(Observation(
            source_name="AutoSpinn",
            source_tier="secondary_automotive_media",
            source_url=url,
            article_title=title,
            publication_date=None,
            manufacturer=manufacturer,
            model=model,
            variant=variant,
            reported_price=num,
            price_text=price_text,
            price_type="manufacturer_msrp_reported",
            market="Thailand",
            model_year=None,
            source_excerpt=variant_text[:200],
            retrieval_timestamp=ts,
            content_hash=content_hash(url, model, variant, num),
        ))
    
    return obs_list

# === MAIN HARVEST ===

def main():
    all_observations: List[Observation] = []
    
    # === HEADLIGHT ARTICLES ===
    headlight_urls = [
        "https://www.headlightmag.com/official-price-ford-ranger-wolftrak-2026/",
        "https://www.headlightmag.com/official-price-lepas-l6/",
        "https://www.headlightmag.com/official-price-honda-civic-ehev-2026-s-plus-shift/",
        "https://www.headlightmag.com/official-price-byd-seal-6-2026/",
        "https://www.headlightmag.com/official-price-byd-sealion-5-dm-i-super-phev/",
        "https://www.headlightmag.com/official-price-suzuki-carry-my2026/",
        "https://www.headlightmag.com/official-price-avatr-11-my2026/",
        "https://www.headlightmag.com/official-price-mitsubishi-attrage-my2026/",
        "https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/",
        "https://www.headlightmag.com/official-price-mg-urban-2026/",
        "https://www.headlightmag.com/official-price-changan-nevo-q05/",
        "https://www.headlightmag.com/official-price-honda-accord-2026/",
        "https://www.headlightmag.com/official-price-suzuki-jimny-with-safety-support-my2026/",
        "https://www.headlightmag.com/official-price-mg4-my2026-2/",
        "https://www.headlightmag.com/official-price-mg-im-5-long-range-rwd/",
        "https://www.headlightmag.com/official-price-nio-firefly/",
        "https://www.headlightmag.com/official-price-tesla-model-y-l-long-wheelbase/",
        "https://www.headlightmag.com/2026-03-23-official-price-byd-atto1/",
        "https://www.headlightmag.com/official-price-geely-ex5-my2026/",
        "https://www.headlightmag.com/official-price-nissan-kicks-e-power-minorchange-2026/",
        "https://www.headlightmag.com/official-price-honda-en2/",
        "https://www.headlightmag.com/official-price-lexus-is-300h-minorchange-2026/",
        "https://www.headlightmag.com/official-price-hyundai-santa-fe-my2026/",
        "https://www.headlightmag.com/official-price-gwm-ora-5-hev/",
        "https://www.headlightmag.com/official-price-subaru-crosstrek/",
        "https://www.headlightmag.com/official-price-ford-everest-platinum-my2026/",
        "https://www.headlightmag.com/official-price-ford-ranger-wildtrak-x-my2026/",
        "https://www.headlightmag.com/official-price-mazda-6e-edit/",
        "https://www.headlightmag.com/official-price-toyota-land-cruiser-fj/",
        "https://www.headlightmag.com/official-price-bmw-ix3-na5/",
        "https://www.headlightmag.com/official-price-zeekr-x-my-2026/",
        "https://www.headlightmag.com/official-price-toyota-corolla-altis-my2026/",
        "https://www.headlightmag.com/special-price-kia-carnival-sxl-diesel-11-seats-2026/",
        "https://www.headlightmag.com/special-price-suzuki-fronx-august-2026/",
        "https://www.headlightmag.com/official-price-denza-z9gt/",
        "https://www.headlightmag.com/official-price-hyundai-staria-hybrid-minorchange-2026/",
        "https://www.headlightmag.com/official-price-hyundai-ioniq-5-n-line-ckd-thailand-2nd-lot/",
        "https://www.headlightmag.com/official-price-byd-sealion-7-2026-awd-ultimate/",
        "https://www.headlightmag.com/official-price-gwm-tank-500-diesel-2026/",
        "https://www.headlightmag.com/official-price-honda-super-one/",
        "https://www.headlightmag.com/official-price-geely-starray-em-r-reev/",
        "https://www.headlightmag.com/official-price-toyota-alphard-vellfire-my2026/",
        "https://www.headlightmag.com/official-price-mini-aceman-collections-mini-aceman-collections-multitone-shadow-jcw/",
        "https://www.headlightmag.com/official-price-kia-pv5-cargo/",
        "https://www.headlightmag.com/special-price-hyundai-palisade-august-2026/",
    ]
    
    print(f"=== Harvesting HeadLight ({len(headlight_urls)} articles) ===")
    for i, url in enumerate(headlight_urls):
        obs = harvest_headlight(url)
        all_observations.extend(obs)
        print(f"  [{i+1}/{len(headlight_urls)}] {url.split('/')[-2]}: {len(obs)} obs")
        time.sleep(0.3)  # Be polite
    
    # === AUTOLIFETHAILAND ===
    autolife_urls = [
        "https://autolifethailand.tv/official-special-price-byd-seal-5-dm-i-phev-plug-in-hybrid-sep-2026/",
        "https://autolifethailand.tv/official-price-discount-byd-sealion-5-dm-i-phev-sep-2026/",
        "https://autolifethailand.tv/offcial-price-denza-z9gt-ev-bev-thailand-2026/",
        "https://autolifethailand.tv/official-price-discount-byd-atto-2-ev-bev-sep-2026/",
        "https://autolifethailand.tv/official-price-tesla-model-y-thailand/",
        "https://autolifethailand.tv/official-price-tesla-model-3-official-thailand/",
    ]
    
    print(f"\n=== Harvesting AutoLifeThailand ({len(autolife_urls)} articles) ===")
    for i, url in enumerate(autolife_urls):
        obs = harvest_autolife(url)
        all_observations.extend(obs)
        print(f"  [{i+1}/{len(autolife_urls)}] {url.split('/')[-2][:40]}: {len(obs)} obs")
        time.sleep(0.3)
    
    # === 9CARTHAI (full price lists) ===
    ninecar_urls = [
        "https://www.9carthai.com/honda-price/",
        "https://www.9carthai.com/toyota-price/",
        "https://www.9carthai.com/byd-price/",
        "https://www.9carthai.com/mg-price/",
    ]
    
    print(f"\n=== Harvesting 9CARTHAI ({len(ninecar_urls)} price lists) ===")
    for i, url in enumerate(ninecar_urls):
        obs = harvest_9carthai(url)
        all_observations.extend(obs)
        print(f"  [{i+1}/{len(ninecar_urls)}] {url.split('/')[-2]}: {len(obs)} obs")
        time.sleep(0.3)
    
    # === AUTOSPINN ===
    autospinn_urls = [
        "https://www.autospinn.com/2026/03/byd-price-updated-148444",
    ]
    
    print(f"\n=== Harvesting AutoSpinn ({len(autospinn_urls)} articles) ===")
    for i, url in enumerate(autospinn_urls):
        obs = harvest_autospinn(url)
        all_observations.extend(obs)
        print(f"  [{i+1}/{len(autospinn_urls)}] {url.split('/')[-2][:40]}: {len(obs)} obs")
        time.sleep(0.3)
    
    # === OUTPUT ===
    print(f"\n=== TOTAL: {len(all_observations)} observations ===")
    
    # Write to JSON for ingestion
    output = [asdict(o) for o in all_observations]
    with open("/home/ubuntu/Projects/thai-car-intelligence/scripts/harvested-observations.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"Written to scripts/harvested-observations.json")
    
    # Stats
    sources = {}
    for o in all_observations:
        sources[o.source_name] = sources.get(o.source_name, 0) + 1
    print("\nBy source:")
    for s, c in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")

if __name__ == "__main__":
    main()
