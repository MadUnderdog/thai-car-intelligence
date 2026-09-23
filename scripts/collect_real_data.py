#!/usr/bin/env python3
"""
Real acquisition — fetch actual OEM pages and extract real data.

Every observation MUST have:
1. Exact URL/endpoint fetched
2. Raw artifact (HTML/JSON) stored
3. Exact locator (selector/text path)
4. Extracted value from artifact
5. Evidence excerpt

NO hardcoded values. NO manual dictionaries. NO fake currentness.
"""
import json
import os
import hashlib
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Paths
RAW_ARTIFACTS_DIR = "audit/data-staging/raw-artifacts"
STAGING_DIR = "audit/data-staging"
OBSERVATIONS_FILE = os.path.join(STAGING_DIR, "vehicle_observations.jsonl")

# Source precedence
SOURCE_PRECEDENCE = {
    "OEM_OFFICIAL": 100,
    "STRUCTURED_REF": 80,
    "MEDIA_DISCOVERY": 60,
    "MARKET_REFERENCE": 50,
}

# Brand aliases
BRAND_ALIASES = {
    "toyota": "toyota",
    "honda": "honda",
    "nissan": "nissan",
    "mazda": "mazda",
    "mg": "mg",
    "byd": "byd",
    "mitsubishi": "mitsubishi",
    "haval": "haval",
    "ford": "ford",
    "isuzu": "isuzu",
    "suzuki": "suzuki",
    "tesla": "tesla",
    "bmw": "bmw",
    "mercedes-benz": "mercedes-benz",
}


def normalize_brand(raw_brand: str) -> str:
    """Deterministic brand normalization."""
    key = raw_brand.lower().strip()
    return BRAND_ALIASES.get(key, key)


def save_raw_artifact(url: str, content: str, source_name: str) -> str:
    """Save raw artifact and return path."""
    os.makedirs(RAW_ARTIFACTS_DIR, exist_ok=True)
    
    # Create filename from URL hash
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{source_name}_{timestamp}_{url_hash}.html"
    filepath = os.path.join(RAW_ARTIFACTS_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return filepath


def fetch_with_playwright(url: str, timeout_ms: int = 30000) -> Tuple[Optional[str], str]:
    """Fetch URL using Playwright and return (html, error)."""
    script = f'''
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto("{url}", timeout={timeout_ms})
            await page.wait_for_load_state("networkidle", timeout=10000)
            content = await page.content()
            print(content)
        except Exception as e:
            print(f"ERROR: {{e}}", file=__import__('sys').stderr)
        finally:
            await browser.close()

asyncio.run(main())
'''
    
    try:
        result = subprocess.run(
            ['python3', '-c', script],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout, ""
        else:
            return None, result.stderr or "Empty response"
    except Exception as e:
        return None, str(e)


def extract_toyota_prices(html: str, url: str, artifact_path: str) -> List[Dict]:
    """Extract Toyota prices from JSON-LD structured data in actual page HTML.
    
    Parses the application/ld+json script tag which contains:
    @graph → CollectionPage → mainEntity → itemListElement → Vehicle → hasVariant → offers
    
    Each observation has exact model/variant/price linked to the same JSON-LD record.
    """
    observations = []
    import re, json as _json
    
    # Extract JSON-LD blocks from HTML
    jsonld_pattern = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL)
    jsonld_blocks = jsonld_pattern.findall(html)
    
    for block in jsonld_blocks:
        try:
            data = _json.loads(block)
        except _json.JSONDecodeError:
            continue
        
        if '@graph' not in data:
            continue
        
        for item in data['@graph']:
            if item.get('@type') != 'CollectionPage':
                continue
            
            main_entity = item.get('mainEntity', {})
            if main_entity.get('@type') != 'ItemList':
                continue
            
            for list_item in main_entity.get('itemListElement', []):
                vehicle = list_item.get('item', {})
                if vehicle.get('@type') != 'Vehicle':
                    continue
                
                vehicle_name = vehicle.get('name', '').strip()
                vehicle_url = vehicle.get('url', url)
                vehicle_config = vehicle.get('vehicleConfiguration', '')
                
                for variant in vehicle.get('hasVariant', []):
                    variant_name = variant.get('name', '').strip()
                    variant_config = variant.get('vehicleConfiguration', '')
                    offers = variant.get('offers', {})
                    
                    price_str = offers.get('price')
                    currency = offers.get('priceCurrency', 'THB')
                    availability_url = offers.get('availability', '')
                    availability = availability_url.split('/')[-1] if availability_url else 'UNKNOWN'
                    
                    if not price_str:
                        continue
                    
                    try:
                        price = int(price_str)
                    except (ValueError, TypeError):
                        continue
                    
                    if price <= 0:
                        continue
                    
                    # Determine currentness from availability
                    if availability == 'InStock':
                        currentness = 'CURRENT'
                    elif availability == 'OutOfStock':
                        currentness = 'UNKNOWN'
                    else:
                        currentness = 'UNKNOWN'
                    
                    # Clean model/variant names
                    # vehicle_name is like "Toyota Corolla Altis", strip brand prefix
                    model_name = vehicle_name
                    for prefix in ['Toyota ', 'Toyota']:
                        if model_name.startswith(prefix):
                            model_name = model_name[len(prefix):].strip()
                    
                    # variant_config is the trim name
                    trim_name = variant_config if variant_config else variant_name
                    
                    # Build JSON-LD locator path
                    position = list_item.get('position', '?')
                    json_path = f"@graph[CollectionPage].mainEntity.itemListElement[{position}].item.hasVariant[{trim_name}].offers.price"
                    
                    observations.append({
                        "observation_id": hashlib.sha256(
                            f"{url}:{model_name}:{trim_name}:{price}".encode()
                        ).hexdigest()[:16],
                        "timestamp": datetime.utcnow().isoformat(),
                        "source": {
                            "class": "OEM_OFFICIAL",
                            "url": url,
                            "name": "Toyota Thailand Official",
                            "precedence": SOURCE_PRECEDENCE["OEM_OFFICIAL"],
                            "native_id": None,
                            "immutable_revision": None,
                            "extraction_method": "playwright_jsonld_parse",
                            "artifact_path": artifact_path,
                        },
                        "identity": {
                            "brand_raw": "Toyota",
                            "model_raw": model_name,
                            "variant_raw": trim_name,
                            "year": None,  # Not hardcoded — year not in JSON-LD
                            "fuel_powertrain_raw": None,
                            "brand_normalized": "toyota",
                            "model_normalized": model_name.lower().replace(" ", "-"),
                            "variant_normalized": trim_name.lower().replace(" ", "-") if trim_name else None,
                            "identity_level": "VARIANT",
                        },
                        "price": {
                            "value_thb": price,
                            "type": "MSRP",
                            "currency": currency,
                            "currentness": currentness,
                        },
                        "specs": {},
                        "raw_labels": {
                            "vehicle_name_raw": vehicle_name,
                            "variant_name_raw": variant_name,
                            "vehicleConfiguration": variant_config,
                            "price_raw": price_str,
                            "availability_raw": availability,
                        },
                        "evidence_excerpt": f"JSON-LD Vehicle '{vehicle_name}' → variant '{trim_name}' → price {price_str} {currency} ({availability})",
                        "evidence_locator": {
                            "artifact_path": artifact_path,
                            "json_path": json_path,
                            "ldplusjson_block": True,
                        },
                    })
    
    return observations



def collect_fipe() -> List[Dict]:
    """Collect from Fipe API — STRUCTURED REFERENCE."""
    observations = []
    source_url = "https://parallelum.com.br/fipe/api/v1/carros/marcas/"
    
    capture_path = "audit/catalog-discovery/datasets/fipe_api_capture.json"
    if os.path.exists(capture_path):
        with open(capture_path) as f:
            data = json.load(f)
        
        brands = data.get("brands", {})
        for brand_name, brand_data in brands.items():
            brand_id = brand_data.get("brand_id")
            models = brand_data.get("models", [])
            
            for m in models:
                model_name = m.get("name", "")
                model_id = m.get("id")
                
                observations.append({
                    "observation_id": hashlib.sha256(
                        f"fipe:{brand_id}:{model_id}".encode()
                    ).hexdigest()[:16],
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": {
                        "class": "STRUCTURED_REF",
                        "url": f"{source_url}{brand_id}/modelos/{model_id}/anos",
                        "name": f"Fipe API ({brand_name})",
                        "precedence": SOURCE_PRECEDENCE["STRUCTURED_REF"],
                        "native_id": f"fipe:{brand_id}:{model_id}",
                        "immutable_revision": None,
                        "extraction_method": "api",
                        "artifact_path": capture_path,
                    },
                    "identity": {
                        "brand_raw": brand_name,
                        "model_raw": model_name,
                        "variant_raw": None,
                        "year": None,
                        "fuel_powertrain_raw": None,
                        "brand_normalized": normalize_brand(brand_name),
                        "model_normalized": model_name.lower().replace(" ", "-"),
                        "variant_normalized": None,
                        "identity_level": "MODEL_OR_TRIM_UNKNOWN",
                    },
                    "price": None,
                    "specs": {},
                    "raw_labels": m,
                    "evidence_excerpt": None,
                    "evidence_locator": {
                        "artifact_path": capture_path,
                        "json_path": f"brands.{brand_name}.models[{model_id}]",
                    },
                })
    
    return observations


def collect_openev() -> List[Dict]:
    """Collect from open-ev-data — STRUCTURED REFERENCE."""
    observations = []
    source_url = "https://github.com/open-ev-data/open-ev-data-dataset"
    
    capture_path = "audit/catalog-discovery/second_taxonomy_capture.json"
    if os.path.exists(capture_path):
        with open(capture_path) as f:
            data = json.load(f)
        
        pinned_commit = data.get("source", {}).get("commit_sha", "")
        rows = data.get("rows", [])
        
        for row in rows:
            brand = row.get("brand", "")
            model = row.get("model", "")
            year = row.get("year")
            trim = row.get("trim_name", "")
            raw_url = row.get("raw_url", "")
            
            observations.append({
                "observation_id": hashlib.sha256(
                    f"openev:{raw_url}".encode()
                ).hexdigest()[:16],
                "timestamp": datetime.utcnow().isoformat(),
                "source": {
                    "class": "STRUCTURED_REF",
                    "source_url": raw_url or source_url,
                    "name": "open-ev-data",
                    "precedence": SOURCE_PRECEDENCE["STRUCTURED_REF"],
                    "native_id": row.get("file_locator"),
                    "immutable_revision": pinned_commit,
                    "extraction_method": "github_api",
                    "artifact_path": capture_path,
                },
                "identity": {
                    "brand_raw": brand,
                    "model_raw": model,
                    "variant_raw": trim,
                    "year": year,
                    "fuel_powertrain_raw": "EV",
                    "brand_normalized": normalize_brand(brand),
                    "model_normalized": model.lower().replace(" ", "-"),
                    "variant_normalized": trim.lower().replace(" ", "-") if trim else None,
                    "identity_level": "VARIANT",
                },
                "price": None,
                "specs": {},
                "raw_labels": row,
                "evidence_excerpt": None,
                "evidence_locator": {
                    "artifact_path": capture_path,
                    "json_path": f"rows[{row.get('file_locator')}]",
                },
            })
    
    return observations


def main():
    """Run REAL acquisition — no hardcoded data."""
    print("=== REAL ACQUISITION (NO HARDCODED DATA) ===\n")
    
    all_observations = []
    source_counts = {}
    
    # 1. Toyota - actually fetch the page
    print("Fetching Toyota official page...")
    url = "https://www.toyota.co.th/en/pricelist"
    html, error = fetch_with_playwright(url)
    if html:
        artifact_path = save_raw_artifact(url, html, "toyota")
        print(f"  Saved artifact: {artifact_path}")
        observations = extract_toyota_prices(html, url, artifact_path)
        all_observations.extend(observations)
        source_counts["Toyota Official (fetched)"] = len(observations)
        print(f"  Extracted {len(observations)} price observations")
    else:
        print(f"  Failed to fetch: {error}")
    
    # 2. Fipe API (already have artifact)
    print("\nLoading Fipe API data (existing artifact)...")
    observations = collect_fipe()
    all_observations.extend(observations)
    source_counts["Fipe API"] = len(observations)
    print(f"  Loaded {len(observations)} identity observations")
    
    # 3. open-ev-data (already have artifact)
    print("\nLoading open-ev-data (existing artifact)...")
    observations = collect_openev()
    all_observations.extend(observations)
    source_counts["open-ev-data"] = len(observations)
    print(f"  Loaded {len(observations)} observations")
    
    # Write observations
    os.makedirs(STAGING_DIR, exist_ok=True)
    with open(OBSERVATIONS_FILE, 'w') as f:
        for obs in all_observations:
            f.write(json.dumps(obs) + '\n')
    
    print(f"\n=== RESULTS ===")
    print(f"Total observations: {len(all_observations)}")
    print(f"Source counts: {source_counts}")
    print(f"Written to: {OBSERVATIONS_FILE}")
    
    return all_observations, source_counts


if __name__ == "__main__":
    main()
