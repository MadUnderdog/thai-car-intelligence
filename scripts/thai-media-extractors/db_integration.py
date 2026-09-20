#!/usr/bin/env python3
"""
DB Integration — takes pipeline output and persists to PostgreSQL.

Flow: pipeline-output.json → normalize → dedup → identity resolve → DB.
Idempotent: re-run skips existing records.
No mass-delete of valid records.
"""
import json
import hashlib
import sys
import os
import re
from datetime import datetime
from decimal import Decimal

# DB connection via subprocess to docker psql
def psql(sql, fetch=True):
    """Execute SQL via docker exec psql."""
    import subprocess
    cmd = ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence",
           "-t", "-A", "-F", "|", "-c", sql]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"  SQL ERROR: {result.stderr}", file=sys.stderr)
        return []
    if not fetch:
        return result.stdout.strip()
    lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
    return lines

def psql_batch(sql_statements, fetch=False):
    """Execute multiple SQL statements in a single docker exec call via stdin."""
    import subprocess
    combined = ";\n".join(sql_statements) + ";\n"
    cmd = ["docker", "exec", "-i", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence",
           "-t", "-A", "-F", "|"]
    result = subprocess.run(cmd, input=combined, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"  BATCH SQL ERROR: {result.stderr[:500]}", file=sys.stderr)
        return []
    if not fetch:
        return result.stdout.strip()
    lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
    return lines

def get_existing_sources():
    """Get existing Source records by domain."""
    rows = psql('SELECT id, "nameEn", "baseUrl", "domain" FROM "Source"')
    sources = {}
    for row in rows:
        parts = row.split("|")
        if len(parts) >= 4:
            sources[parts[3]] = {"id": parts[0], "name": parts[1], "url": parts[2]}
    return sources

def get_existing_variants():
    """Get variant ID by (carModel.nameEn + variant slug/name)."""
    rows = psql('''
        SELECT v.id, v.slug, v."nameEn", cm."nameEn" as model_name, m."nameEn" as brand_name
        FROM "Variant" v
        JOIN "CarModel" cm ON v."modelId" = cm.id
        JOIN "Manufacturer" m ON cm."manufacturerId" = m.id
    ''')
    variants = {}
    for row in rows:
        parts = row.split("|")
        if len(parts) >= 5:
            key = f"{parts[4].lower()}|{parts[3].lower()}|{parts[1].lower()}"
            variants[key] = parts[0]  # variant ID
            # Also store brand|model -> variant IDs
            bm_key = f"{parts[4].lower()}|{parts[3].lower()}"
            if bm_key not in variants:
                variants[bm_key] = []
            variants[bm_key].append({"id": parts[0], "slug": parts[1], "name": parts[2]})
    return variants

def get_or_create_source(sources, source_name, source_class, source_url):
    """Get or create a Source record."""
    from urllib.parse import urlparse
    parsed = urlparse(source_url)
    domain = parsed.netloc.replace("www.", "")
    # Use path-aware key for sites with multiple brand pages (e.g. 9CARTHAI)
    source_key = f"{domain}{parsed.path.rstrip('/')}"

    if source_key in sources:
        return sources[source_key]["id"]
    if domain in sources:
        return sources[domain]["id"]

    # Map source_class to SourceType
    type_map = {
        "OFFICIAL_API": "OFFICIAL_MANUFACTURER",
        "OFFICIAL_WEB": "OFFICIAL_MANUFACTURER",
        "OFFICIAL_PDF": "OFFICIAL_MANUFACTURER_BROCHURE",
        "OFFICIAL_SOCIAL": "SOCIAL",
        "DEALER_WEB": "AUTHORIZED_DEALER",
        "AUTO_MEDIA": "AUTOMOTIVE_MEDIA",
        "REFERENCE_MEDIA": "AUTOMOTIVE_MEDIA",
    }
    source_type = type_map.get(source_class, "AUTOMOTIVE_MEDIA")

    source_id = str(__import__("uuid").uuid4())
    psql(f'''
        INSERT INTO "Source" (id, "nameTh", "nameEn", "sourceType", "baseUrl", "domain", "status", "createdAt", "updatedAt")
        VALUES ('{source_id}', '{source_name}', '{source_name}', '{source_type}'::"SourceType",
                '{source_url}', '{domain}', 'ACTIVE'::"RecordStatus", NOW(), NOW())
    ''', fetch=False)
    sources[source_key] = {"id": source_id, "name": source_name, "url": source_url}
    sources[domain] = {"id": source_id, "name": source_name, "url": source_url}
    return source_id

def create_source_document(source_id, url, content_hash, extraction_method, title=""):
    """Create a SourceDocument record. Returns doc ID (existing or new)."""
    # Check if document already exists
    existing = psql(f'''
        SELECT id FROM "SourceDocument"
        WHERE "sourceId" = '{source_id}' AND "contentHash" = '{content_hash}'
    ''')
    if existing:
        return existing[0]

    doc_id = str(__import__("uuid").uuid4())
    psql(f'''
        INSERT INTO "SourceDocument" (id, "sourceId", url, "contentHash", "extractionMethod",
              "fetchedAt", status, "extractionStatus", "createdAt", "updatedAt")
        VALUES ('{doc_id}', '{source_id}', '{url}', '{content_hash}', '{extraction_method}',
                NOW(), 'VERIFIED'::"DocumentStatus", 'SUCCEEDED'::"ExtractionStatus", NOW(), NOW())
    ''', fetch=False)
    return doc_id

def resolve_variant(brand, model, variant, variants_map):
    """Map brand+model+variant to a DB variant ID."""
    brand_l = brand.lower()
    model_l = model.lower().strip()

    # Model name normalization for DB matching
    MODEL_NORM = {
        "hilux revo": "hilux", "hilux revo z edition": "hilux",
        "hilux travo": "hilux", "hilux champ": "hilux",
        "innova crysta": "innova zenix", "innova": "innova zenix",
        "corolla altis gr sport": "corolla altis",
        "corolla cross gr sport": "corolla cross",
        "fortuner gr sport": "fortuner", "fortuner legender": "fortuner",
        "fortuner leader": "fortuner",
        "yaris ativ gr sport": "yaris ativ", "yaris ativ nightshade": "yaris ativ",
        "yaris cross nightshade": "yaris cross",
        "gr corolla": "corolla altis", "gr yaris": "yaris",
        "land cruiser fj": "land cruiser",
        "almera with stylish package": "almera",
        "new almera": "almera", "new almera 22my": "almera",
        "new terra": "terra", "nissan terra mc": "terra",
        "new navara single cab": "navara", "new navara king cab": "navara",
        "new navara calibre": "navara", "np300 navara double cab": "navara",
        "np300 navara king cab": "navara", "np300 navara sc": "navara",
        "navara calibre my21": "navara", "navara sc": "navara",
        "new navara pro 4x and pro 2x": "navara",
        "kicks e power with stylish package": "kicks",
        "new kicks": "kicks", "kicks e-power": "kicks",
        "serena epower": "serena",
        "new leaf": "leaf",
        "mazda 6e": "mazda 6e",
        "mg3": "mg3", "mg4": "mg4", "mg5": "mg5",
        "s5 ev plus": "s5 ev plus",
    }
    norm_model = MODEL_NORM.get(model_l, model_l)

    # Try brand|model lookup
    bm_key = f"{brand_l}|{norm_model}"
    if bm_key in variants_map:
        vlist = variants_map[bm_key]
        if isinstance(vlist, list) and vlist:
            if variant in ("__MODEL_RANGE__", "__MODEL__", "__MODEL__"):
                return vlist[0]["id"]
            var_l = variant.lower().strip()
            for v in vlist:
                if var_l in v["slug"].lower() or var_l in v["name"].lower():
                    return v["id"]
            for v in vlist:
                v_words = set(v["slug"].lower().split("-"))
                var_words = set(re.split(r'[\s\-]+', var_l))
                if v_words & var_words:
                    return v["id"]
            return vlist[0]["id"]

    # Try original model name if normalized didn't match
    if norm_model != model_l:
        bm_key2 = f"{brand_l}|{model_l}"
        if bm_key2 in variants_map:
            vlist = variants_map[bm_key2]
            if isinstance(vlist, list) and vlist:
                return vlist[0]["id"]

    return None

def insert_price(variant_id, doc_id, amount, price_type, confidence=0.75):
    """Insert a Price record. Idempotent — expires existing current price first."""
    price_type_map = {
        "LIST_PRICE": "LIST_PRICE",
        "MSRP": "MSRP",
        "CAMPAIGN_PRICE": "PROMOTION",
        "AFTER_DISCOUNT": "AFTER_DISCOUNT",
    }
    pt = price_type_map.get(price_type, "LIST_PRICE")

    # Check if same price already exists
    existing = psql(f'''
        SELECT id FROM "Price"
        WHERE "variantId" = '{variant_id}' AND "sourceDocumentId" = '{doc_id}'
              AND "priceType" = '{pt}'::"PriceType" AND amount = {amount}
    ''')
    if existing:
        return None  # Already exists

    # Expire existing current price for this variant+priceType
    psql(f'''
        UPDATE "Price" SET "isCurrent" = false, "validTo" = NOW()
        WHERE "variantId" = '{variant_id}' AND "priceType" = '{pt}'::"PriceType"
              AND "isCurrent" = true
    ''', fetch=False)

    # Insert new price
    price_id = str(__import__("uuid").uuid4())
    psql(f'''
        INSERT INTO "Price" (id, "variantId", "sourceDocumentId", "priceType", amount,
              currency, "validFrom", "isCurrent", confidence)
        VALUES ('{price_id}', '{variant_id}', '{doc_id}', '{pt}'::"PriceType",
                {amount}, 'THB', NOW(), true, {confidence})
    ''', fetch=False)
    return price_id

def insert_spec(variant_id, doc_id, key, value, unit=None, numeric=None):
    """Insert a VariantSpec record. Idempotent via UNIQUE constraint."""
    spec_id = str(__import__("uuid").uuid4())
    safe_value = value.replace("'", "''")[:500] if isinstance(value, str) else str(value)
    safe_key = key.replace("'", "''")[:100]
    unit_val = f"'{unit}'" if unit else "NULL"
    numeric_val = str(numeric) if numeric is not None else "NULL"
    psql(f'''
        INSERT INTO "VariantSpec" (id, "variantId", "sourceDocumentId", key, "valueTh", "valueEn", "valueNumeric", unit, confidence)
        VALUES ('{spec_id}', '{variant_id}', '{doc_id}', '{safe_key}', '{safe_value}', '{safe_value}', {numeric_val}, {unit_val}, 0.75)
        ON CONFLICT ("variantId", key, "sourceDocumentId") DO NOTHING
    ''', fetch=False)
    return spec_id

# ── Spec key mapping: raw extraction key → normalized DB key ──
# Maps "Capacity (cc.)" → "engine.displacementCc", etc.
SPEC_KEY_MAP = {
    "Capacity (cc.)": "engine.displacementCc",
    "Capacity (kW-hr)": "battery.capacityKwh",
    "Max Output EEC net (kW(PS) / rpm)": "performance.powerKw",
    "Max. Output (kW(PS))": "performance.powerKw",
    "Max Output (kW(PS))": "performance.powerKw",
    "Max Torque EEC net (Nm / rpm)": "performance.torqueNm",
    "Max Torque EEC net (Nm)": "performance.torqueNm",
    "Max Torque (Nm)": "performance.torqueNm",
    "Wheelbase (mm.)": "dimensions.wheelbaseMm",
    "Min. Ground Clearance (mm.)": "dimensions.groundClearanceMm",
    "Overall Length x Width x Height (mm.)": "dimensions.lengthMm",  # special: multi-value
    "Seating Capacity": "capacity.seats",
    "Fuel Capacity (Liter)": "fuel.capacityLiter",
    "Fuel Tank Capacity (Liter)": "fuel.capacityLiter",
    "Min. Turning Radius (m.)": "handling.turningRadiusM",
    "Kerb Weight (kg.)": "dimensions.curbWeightKg",
    "Vehicle Weight (kg.)": "dimensions.curbWeightKg",
    "Gross Vehicle Weight (kg.)": "dimensions.grossWeightKg",
    "Max Voltage (V)": "battery.maxVoltageV",
    "Voltage (V)": "battery.voltageV",
    "Range (km.)": "performance.rangeKm",
    "Fuel Consumption (km/L)": "efficiency.fuelConsumptionKmL",
    "Energy Consumption (km/kWh)": "efficiency.energyConsumptionKmKwh",
    "Battery Type": "battery.type",
    "Charging Time - Normal (hours)": "charging.normalTimeHours",
    "Charging Time - DC Fast (minutes)": "charging.dcFastTimeMin",
    "DC Fast Charging Power (kW)": "charging.dcPowerKw",
    "Tire Size": "wheels.tireSize",
    "Wheel & Tires": "wheels.tireSize",
    "Bore x Stroke (mm.)": "engine.boreStrokeMm",
    "Compression Ratio": "engine.compressionRatio",
    "Model / Type": "engine.modelType",
    "Differential Final Gear Ratio": "drivetrain.finalGearRatio",
    "Emission Standard": "emissions.standard",
    "Warranty - Vehicle (years)": "warranty.vehicleYears",
    "Warranty - Vehicle (km.)": "warranty.vehicleDistanceKm",
    "Warranty - Battery (years)": "warranty.batteryYears",
    "Warranty - Battery (km.)": "warranty.batteryDistanceKm",
}

def map_spec_key(raw_key):
    """Map a raw spec key to a normalized DB key."""
    if raw_key in SPEC_KEY_MAP:
        return SPEC_KEY_MAP[raw_key]
    # Fallback: lowercase, strip, replace spaces/slashes with dots
    norm = raw_key.lower().strip()
    norm = re.sub(r'\s*\([^)]*\)', '', norm)  # remove (mm.), (cc.), etc.
    norm = re.sub(r'[\s/]+', '.', norm)
    return f"spec.{norm}"

def parse_numeric_value(raw_value):
    """Extract numeric value and unit from a raw spec string.
    Returns (numeric_float, unit_string_or_None).
    """
    if not raw_value:
        return None, None
    val = str(raw_value).strip().replace(",", "")
    # Pattern: number followed by optional unit
    m = re.match(r'^([0-9]+\.?[0-9]*)\s*(mm|cm|m|km|kg|kW|kWh|Nm|PS|hp|L|liter|cc|rpm|V|seat|seats|positions?|hour|hours|min|minutes)?$', val, re.IGNORECASE)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit:
            unit = unit.lower()
            if unit in ("liter",): unit = "L"
            if unit in ("seat", "seats"): unit = "seats"
            if unit in ("positions", "position"): unit = "positions"
        return num, unit
    # Pattern: "L x W x H" dimensions — extract first number
    m = re.match(r'^([0-9,]+)\s*x\s*([0-9,]+)\s*x\s*([0-9,]+)', val)
    if m:
        # For dimensions, return tuple of three numbers as separate specs
        return None, None  # caller handles
    # Pattern: number with comma separator
    m = re.match(r'^([0-9]+(?:\.[0-9]+)?)$', val)
    if m:
        return float(m.group(1)), None
    return None, None

def parse_dimensions(raw_value):
    """Parse 'L x W x H' format into (length, width, height) tuples.
    Returns list of (key_suffix, value_numeric).
    """
    m = re.match(r'^([0-9,]+)\s*x\s*([0-9,]+)\s*x\s*([0-9,]+)', str(raw_value).strip().replace(",", ""))
    if m:
        return [("length", float(m.group(1))), ("width", float(m.group(2))), ("height", float(m.group(3)))]
    return []

def normalize_observation(obs):
    """Normalize an observation from either old pipeline or new extraction format.
    Returns a list of normalized dicts ready for DB insertion.
    """
    results = []
    brand = obs.get("brand", "")
    model = obs.get("model", "")
    variant = obs.get("variant", "__MODEL_RANGE__")
    source_url = obs.get("source_url", "")
    source_class = obs.get("source_class", "SEARCH_LEAD")
    source_name = obs.get("source_name", "")
    content_hash = obs.get("content_hash", hashlib.sha256(source_url.encode()).hexdigest()[:16])
    extraction_method = obs.get("extraction_method", "unknown")
    article_title = obs.get("article_title", obs.get("model", ""))

    # Infer source_name from URL if not provided
    if not source_name:
        from urllib.parse import urlparse
        parsed = urlparse(source_url)
        domain = parsed.netloc.replace("www.", "")
        source_name = domain.split(".")[0].title() if domain else "Unknown"

    base = {
        "brand": brand, "model": model, "variant": variant,
        "source_url": source_url, "source_class": source_class,
        "source_name": source_name, "content_hash": content_hash,
        "extraction_method": extraction_method, "article_title": article_title,
    }

    # ── Old pipeline format: obs_field="price" or "spec_*" ──
    if "obs_field" in obs:
        obs_field = obs["obs_field"]
        if obs_field == "price":
            results.append({**base, "_type": "price",
                "amount": int(obs.get("normalized_value", 0)),
                "price_type": obs.get("price_type", "LIST_PRICE")})
        elif obs_field.startswith("spec_"):
            key = obs_field.replace("spec_", "")
            value = obs.get("normalized_value", obs.get("raw_value", ""))
            unit = obs.get("unit")
            numeric, parsed_unit = parse_numeric_value(value)
            if unit and not parsed_unit:
                parsed_unit = unit
            results.append({**base, "_type": "spec",
                "raw_key": key, "value": value,
                "unit": parsed_unit, "numeric": numeric})
        return results

    # ── New extraction format: price_thb + spec_key/spec_value ──
    if "price_thb" in obs:
        amount = int(obs.get("price_thb", 0))
        price_type = obs.get("price_type", "STARTING_PRICE")
        # Map new price types to DB types
        pt_map = {
            "STARTING_PRICE": "MSRP", "VARIANT_MSRP": "MSRP",
            "CAMPAIGN_PRICE": "PROMOTION", "LIST_PRICE": "LIST_PRICE",
        }
        results.append({**base, "_type": "price",
            "amount": amount, "price_type": pt_map.get(price_type, price_type)})

    if "spec_key" in obs and "spec_value" in obs:
        raw_key = obs["spec_key"]
        raw_value = obs["spec_value"]
        db_key = map_spec_key(raw_key)

        # Handle "L x W x H" dimensions specially
        if raw_key == "Overall Length x Width x Height (mm.)":
            dims = parse_dimensions(raw_value)
            for suffix, num_val in dims:
                dim_key = f"dimensions.{suffix}Mm"
                results.append({**base, "_type": "spec",
                    "raw_key": dim_key, "value": str(int(num_val)),
                    "unit": "mm", "numeric": num_val})
            return results

        numeric, unit = parse_numeric_value(raw_value)
        results.append({**base, "_type": "spec",
            "raw_key": db_key, "value": raw_value,
            "unit": unit, "numeric": numeric})

    return results


def load_extraction_artifacts(run_dir):
    """Load observations from extraction artifact directories.
    Handles: summary.json (specs+prices), summary.json (all_variant_prices_thb+specs_extracted),
    and hl.json (price-only lists).
    """
    observations = []
    if os.path.isfile(run_dir):
        # Single file path
        with open(run_dir) as f:
            data = json.load(f)
        if isinstance(data, list):
            observations.extend(data)
        elif isinstance(data, dict):
            observations.extend(data.get("prices", []))
            observations.extend(data.get("specs", []))
            observations.extend(data.get("all_variant_prices_thb", []))
            observations.extend(data.get("specs_extracted", []))
        return observations

    # Directory: scan brand subdirectories
    for brand_dir in sorted(os.listdir(run_dir)):
        brand_path = os.path.join(run_dir, brand_dir)
        if not os.path.isdir(brand_path):
            continue
        for fname in ("summary.json", "hl.json"):
            fpath = os.path.join(brand_path, fname)
            if not os.path.isfile(fpath):
                continue
            with open(fpath) as f:
                data = json.load(f)
            if isinstance(data, list):
                observations.extend(data)
            elif isinstance(data, dict):
                observations.extend(data.get("prices", []))
                observations.extend(data.get("specs", []))
                observations.extend(data.get("all_variant_prices_thb", []))
                observations.extend(data.get("specs_extracted", []))
    return observations


def run_integration(pipeline_output_path):
    """Main integration: read pipeline output/summary.json → normalize → DB."""
    # Load observations from file or directory
    if os.path.isfile(pipeline_output_path):
        with open(pipeline_output_path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict) and "accepted_observations" in data:
            observations = data["accepted_observations"]
        elif isinstance(data, dict):
            observations = data.get("prices", []) + data.get("specs", [])
        else:
            observations = data if isinstance(data, list) else []
    elif os.path.isdir(pipeline_output_path):
        observations = load_extraction_artifacts(pipeline_output_path)
    else:
        print(f"Path not found: {pipeline_output_path}"); sys.exit(1)

    print(f"Loaded {len(observations)} observations from {pipeline_output_path}")

    # Load existing DB state
    sources = get_existing_sources()
    variants_map = get_existing_variants()

    print(f"DB state: {len(sources)} sources, {len(variants_map)} variant keys")

    # Pre-resolve variant IDs for all unique (brand, model, variant) combos
    variant_cache = {}  # (brand, model, variant) -> variant_id or None
    for raw_obs in observations:
        brand = raw_obs.get("brand", "")
        model = raw_obs.get("model", "")
        variant = raw_obs.get("variant", "__MODEL_RANGE__")
        key = (brand, model, variant)
        if key not in variant_cache:
            variant_cache[key] = resolve_variant(brand, model, variant, variants_map)

    resolved_count = sum(1 for v in variant_cache.values() if v)
    unresolved_count = sum(1 for v in variant_cache.values() if not v)
    print(f"Variant resolution: {resolved_count} resolved, {unresolved_count} unresolved")

    # Pre-resolve source/doc IDs per URL to avoid repeated DB lookups
    source_doc_cache = {}  # url -> (source_id, doc_id)

    stats = {
        "prices_inserted": 0, "prices_skipped": 0, "prices_no_variant": 0,
        "specs_inserted": 0, "specs_skipped": 0,
        "sources_created": 0, "docs_created": 0,
        "models_resolved": 0, "models_unresolved": 0,
    }
    unresolved_models = set()

    # ── Phase 1: normalize all observations, resolve variants, build SQL batches ──
    spec_batch = []   # list of SQL INSERT strings for VariantSpec
    price_batch = []  # list of SQL INSERT strings for Price
    BATCH_SIZE = 200

    def flush_specs():
        nonlocal spec_batch
        if spec_batch:
            psql_batch(spec_batch)
            stats["specs_inserted"] += len(spec_batch)
            spec_batch = []

    def flush_prices():
        nonlocal price_batch
        if price_batch:
            psql_batch(price_batch)
            stats["prices_inserted"] += len(price_batch)
            price_batch = []

    for raw_obs in observations:
        for obs in normalize_observation(raw_obs):
            brand = obs["brand"]
            model = obs["model"]
            variant = obs["variant"]

            variant_id = variant_cache.get((brand, model, variant))
            if not variant_id:
                stats["prices_no_variant"] += 1
                unresolved_models.add(f"{brand}/{model}")
                continue
            stats["models_resolved"] += 1

            source_url = obs["source_url"]
            if source_url not in source_doc_cache:
                source_id = get_or_create_source(sources, obs["source_name"], obs["source_class"], source_url)
                doc_id = create_source_document(source_id, source_url, obs["content_hash"], obs["extraction_method"], obs.get("article_title", ""))
                source_doc_cache[source_url] = (source_id, doc_id)
            doc_id = source_doc_cache[source_url][1]

            if obs["_type"] == "price":
                amount = obs["amount"]
                if amount < 100000:
                    stats["prices_skipped"] += 1
                    continue
                pt_map = {"STARTING_PRICE": "MSRP", "VARIANT_MSRP": "MSRP",
                          "CAMPAIGN_PRICE": "PROMOTION", "LIST_PRICE": "LIST_PRICE"}
                pt = pt_map.get(obs["price_type"], obs["price_type"])
                price_id = str(__import__("uuid").uuid4())
                # Expire existing current price
                price_batch.append(
                    f'UPDATE "Price" SET "isCurrent" = false, "validTo" = NOW() '
                    f'WHERE "variantId" = \'{variant_id}\' AND "priceType" = \'{pt}\'::"PriceType" AND "isCurrent" = true'
                )
                price_batch.append(
                    f'INSERT INTO "Price" (id, "variantId", "sourceDocumentId", "priceType", amount, '
                    f'currency, "validFrom", "isCurrent", confidence) '
                    f'VALUES (\'{price_id}\', \'{variant_id}\', \'{doc_id}\', \'{pt}\'::"PriceType", '
                    f'{amount}, \'THB\', NOW(), true, 0.75)'
                )
                if len(price_batch) >= BATCH_SIZE * 2:
                    flush_prices()

            elif obs["_type"] == "spec":
                key = obs["raw_key"][:100].replace("'", "''")
                val = (obs["value"] or "")[:500].replace("'", "''")
                unit_val = f"'{obs['unit']}'" if obs["unit"] else "NULL"
                numeric_val = str(obs["numeric"]) if obs["numeric"] is not None else "NULL"
                spec_id = str(__import__("uuid").uuid4())
                spec_batch.append(
                    f'INSERT INTO "VariantSpec" (id, "variantId", "sourceDocumentId", key, '
                    f'"valueTh", "valueEn", "valueNumeric", unit, confidence) '
                    f'VALUES (\'{spec_id}\', \'{variant_id}\', \'{doc_id}\', \'{key}\', '
                    f'\'{val}\', \'{val}\', {numeric_val}, {unit_val}, 0.75) '
                    f'ON CONFLICT ("variantId", key, "sourceDocumentId") DO NOTHING'
                )
                if len(spec_batch) >= BATCH_SIZE:
                    flush_specs()

    # Flush remaining
    flush_specs()
    flush_prices()

    stats["models_unresolved"] = len(unresolved_models)

    print(f"\n=== Integration Complete ===")
    print(json.dumps(stats, indent=2))
    print(f"\nUnresolved models ({len(unresolved_models)}):")
    for m in sorted(unresolved_models):
        print(f"  {m}")

    return stats


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Try new extraction artifacts first, then old pipeline output
        search_paths = [
            "/home/ubuntu/Projects/thai-car-intelligence/storage/research/runs/run-20260920-mega-parallel",
            "/home/ubuntu/Projects/thai-car-intelligence/storage/research/runs/run-20260920-020658",
            "/tmp/thai-car-pipeline",
        ]
        path = None
        for sp in search_paths:
            if os.path.exists(sp):
                if os.path.isdir(sp):
                    # Check for summary.json files inside
                    for brand_dir in os.listdir(sp):
                        if os.path.isfile(os.path.join(sp, brand_dir, "summary.json")):
                            path = sp
                            break
                    if path:
                        break
                else:
                    path = sp
        if not path:
            print("No extraction artifacts found"); sys.exit(1)
    else:
        path = sys.argv[1]

    print(f"Integrating: {path}")
    run_integration(path)
