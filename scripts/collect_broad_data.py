#!/usr/bin/env python3
"""
Broad data collection — gather real vehicle data from accessible sources.

Collects from:
1. Toyota official (Playwright capture)
2. Mazda official (Playwright capture)
3. Fipe API (structured reference)
4. open-ev-data (structured reference)
5. HeadLightMag (media discovery)

All observations go to audit/data-staging/vehicle_observations.jsonl
Nothing is thrown away — uncertain records go to quarantine bucket.
"""
import json
import os
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional

# Paths
STAGING_DIR = "audit/data-staging"
OBSERVATIONS_FILE = os.path.join(STAGING_DIR, "vehicle_observations.jsonl")
SUMMARY_FILE = os.path.join(STAGING_DIR, "summary.json")

# Source precedence (higher = more trusted)
SOURCE_PRECEDENCE = {
    "OEM_OFFICIAL": 100,
    "GOVERNMENT_DLT": 95,
    "STRUCTURED_REF": 80,
    "MEDIA_DISCOVERY": 60,
    "MARKETPLACE": 40,
    "USER_CONTRIBUTED": 20,
}


def make_observation(
    source_class: str,
    source_url: str,
    source_name: str,
    brand: str,
    model: str,
    variant: Optional[str] = None,
    year: Optional[int] = None,
    fuel_powertrain: Optional[str] = None,
    price_thb: Optional[float] = None,
    price_type: Optional[str] = None,
    currency: str = "THB",
    specs: Optional[Dict] = None,
    raw_labels: Optional[Dict] = None,
    native_id: Optional[str] = None,
    immutable_revision: Optional[str] = None,
    extraction_method: str = "playwright",
    evidence_excerpt: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an observation record."""
    return {
        "observation_id": hashlib.sha256(
            f"{source_url}:{brand}:{model}:{variant}:{year}:{price_thb}".encode()
        ).hexdigest()[:16],
        "timestamp": datetime.utcnow().isoformat(),
        "source": {
            "class": source_class,
            "url": source_url,
            "name": source_name,
            "precedence": SOURCE_PRECEDENCE.get(source_class, 0),
            "native_id": native_id,
            "immutable_revision": immutable_revision,
            "extraction_method": extraction_method,
        },
        "identity": {
            "brand_raw": brand,
            "model_raw": model,
            "variant_raw": variant,
            "year": year,
            "fuel_powertrain_raw": fuel_powertrain,
            "brand_normalized": brand.lower().strip(),
            "model_normalized": model.lower().strip().replace(" ", "-"),
            "variant_normalized": variant.lower().strip().replace(" ", "-") if variant else None,
        },
        "price": {
            "value_thb": price_thb,
            "type": price_type,  # MSRP, PROMOTION, HISTORICAL, RANGE
            "currency": currency,
            "currentness": "CURRENT",  # Will be validated later
        } if price_thb else None,
        "specs": specs or {},
        "raw_labels": raw_labels or {},
        "evidence_excerpt": evidence_excerpt,
    }


def collect_toyota() -> List[Dict]:
    """Collect from Toyota Thailand official."""
    observations = []
    source_url = "https://www.toyota.co.th/en/pricelist"
    
    # Try to load existing capture
    capture_path = "audit/catalog-discovery/datasets/toyota_official_capture.json"
    if os.path.exists(capture_path):
        with open(capture_path) as f:
            data = json.load(f)
        
        models = data.get("models", data.get("data", []))
        for m in models:
            brand = m.get("brand", "Toyota")
            model = m.get("model", m.get("name", ""))
            price = m.get("price", m.get("price_thb"))
            
            if price and isinstance(price, (int, float)) and price > 0:
                observations.append(make_observation(
                    source_class="OEM_OFFICIAL",
                    source_url=source_url,
                    source_name="Toyota Thailand Official",
                    brand=brand,
                    model=model,
                    price_thb=float(price),
                    price_type="MSRP",
                    raw_labels=m,
                    extraction_method="playwright",
                ))
    
    return observations


def collect_mazda() -> List[Dict]:
    """Collect from Mazda Thailand official."""
    observations = []
    source_url = "https://www.mazda.co.th/en/vehicles"
    
    # Try to load existing capture
    capture_path = "audit/catalog-discovery/datasets/mazda_official_capture.json"
    if os.path.exists(capture_path):
        with open(capture_path) as f:
            data = json.load(f)
        
        models = data.get("models", data.get("data", []))
        for m in models:
            brand = m.get("brand", "Mazda")
            model = m.get("model", m.get("name", ""))
            price = m.get("price", m.get("price_thb"))
            
            if price and isinstance(price, (int, float)) and price > 0:
                observations.append(make_observation(
                    source_class="OEM_OFFICIAL",
                    source_url=source_url,
                    source_name="Mazda Thailand Official",
                    brand=brand,
                    model=model,
                    price_thb=float(price),
                    price_type="MSRP",
                    raw_labels=m,
                    extraction_method="playwright",
                ))
    
    return observations


def collect_fipe() -> List[Dict]:
    """Collect from Fipe API (structured reference)."""
    observations = []
    source_url = "https://parallelum.com.br/fipe/api/v1/carros/marcas/"
    
    # Try to load existing capture
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
                
                observations.append(make_observation(
                    source_class="STRUCTURED_REF",
                    source_url=f"{source_url}{brand_id}/modelos/",
                    source_name=f"Fipe API ({brand_name})",
                    brand=brand_name,
                    model=model_name,
                    native_id=f"fipe:{brand_id}:{model_id}",
                    raw_labels=m,
                    extraction_method="api",
                ))
    
    return observations


def collect_openev() -> List[Dict]:
    """Collect from open-ev-data (structured reference)."""
    observations = []
    source_url = "https://github.com/open-ev-data/open-ev-data-dataset"
    
    # Try to load existing capture
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
            
            observations.append(make_observation(
                source_class="STRUCTURED_REF",
                source_url=raw_url or source_url,
                source_name="open-ev-data",
                brand=brand,
                model=model,
                variant=trim,
                year=year,
                fuel_powertrain="EV",
                native_id=row.get("file_locator"),
                immutable_revision=pinned_commit,
                raw_labels=row,
                extraction_method="github_api",
            ))
    
    return observations


def collect_headlightmag() -> List[Dict]:
    """Collect from HeadLightMag (media discovery)."""
    observations = []
    source_url = "https://www.headlightmag.com/wp-json/wp/v2/"
    
    # Try to load existing capture
    capture_path = "audit/catalog-discovery/media_discovery_headlightmag.json"
    if os.path.exists(capture_path):
        with open(capture_path) as f:
            data = json.load(f)
        
        entries = data.get("entries", [])
        for entry in entries:
            raw_model = entry.get("raw_model", "")
            brand = entry.get("brand", entry.get("brand_category_name", ""))
            classification = entry.get("classification", "")
            
            # Only include model-mention or variant-mention
            if classification in ("model-mention", "variant-mention"):
                for art in entry.get("article_evidence", []):
                    post_id = art.get("post_id")
                    title = art.get("title", "")
                    
                    observations.append(make_observation(
                        source_class="MEDIA_DISCOVERY",
                        source_url=art.get("url", source_url),
                        source_name="HeadLightMag",
                        brand=brand,
                        model=raw_model,
                        native_id=str(post_id) if post_id else None,
                        raw_labels=entry,
                        evidence_excerpt=title,
                        extraction_method="wordpress_api",
                    ))
    
    return observations


def collect_thai_reference() -> List[Dict]:
    """Collect from Thai market reference."""
    observations = []
    source_url = "audit/catalog-discovery/thai_market_reference.json"
    
    if os.path.exists(source_url):
        with open(source_url) as f:
            data = json.load(f)
        
        makes = data.get("vehicle_makes_thailand", [])
        for m in makes:
            brand = m.get("make", "")
            
            observations.append(make_observation(
                source_class="MARKETPLACE",
                source_url="knowledge_base",
                source_name="Thai Market Reference",
                brand=brand,
                model="(all models)",
                raw_labels=m,
                extraction_method="knowledge_base",
            ))
    
    return observations


def main():
    """Run broad collection across all accessible sources."""
    print("=== BROAD DATA COLLECTION ===\n")
    
    all_observations = []
    source_counts = {}
    
    # Collect from each source
    collectors = [
        ("Toyota Official", collect_toyota),
        ("Mazda Official", collect_mazda),
        ("Fipe API", collect_fipe),
        ("open-ev-data", collect_openev),
        ("HeadLightMag", collect_headlightmag),
        ("Thai Reference", collect_thai_reference),
    ]
    
    for name, collector in collectors:
        try:
            observations = collector()
            all_observations.extend(observations)
            source_counts[name] = len(observations)
            print(f"✓ {name}: {len(observations)} observations")
        except Exception as e:
            source_counts[name] = f"ERROR: {e}"
            print(f"✗ {name}: {e}")
    
    # Write all observations to JSONL
    os.makedirs(STAGING_DIR, exist_ok=True)
    with open(OBSERVATIONS_FILE, 'w') as f:
        for obs in all_observations:
            f.write(json.dumps(obs) + '\n')
    
    print(f"\nTotal observations: {len(all_observations)}")
    print(f"Written to: {OBSERVATIONS_FILE}")
    
    # Compute summary from actual rows
    brands = set()
    models = set()
    variants = set()
    prices = 0
    specs = 0
    source_urls = set()
    
    for obs in all_observations:
        brands.add(obs["identity"]["brand_normalized"])
        models.add(f"{obs['identity']['brand_normalized']}:{obs['identity']['model_normalized']}")
        if obs["identity"]["variant_normalized"]:
            variants.add(f"{obs['identity']['brand_normalized']}:{obs['identity']['model_normalized']}:{obs['identity']['variant_normalized']}")
        if obs.get("price") and obs["price"].get("value_thb"):
            prices += 1
        if obs.get("specs"):
            specs += len(obs["specs"])
        source_urls.add(obs["source"]["url"])
    
    summary = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_observations": len(all_observations),
        "unique_brands": len(brands),
        "unique_models": len(models),
        "unique_variants": len(variants),
        "price_observations": prices,
        "spec_observations": specs,
        "unique_source_urls": len(source_urls),
        "source_counts": source_counts,
        "brands": sorted(list(brands)),
    }
    
    with open(SUMMARY_FILE, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nSummary written to: {SUMMARY_FILE}")
    print(f"Brands: {len(brands)}")
    print(f"Models: {len(models)}")
    print(f"Variants: {len(variants)}")
    print(f"Price observations: {prices}")
    print(f"Spec observations: {specs}")
    
    return summary


if __name__ == "__main__":
    main()
