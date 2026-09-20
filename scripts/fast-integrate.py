#!/usr/bin/env python3
"""Fast batch integration — reads pipeline-output and inserts to DB via batch SQL."""
import json, hashlib, sys, os, re, subprocess, uuid
from collections import defaultdict

def psql(sql, fetch=True):
    cmd = ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence",
           "-t", "-A", "-F", "|", "-c", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return []
    if not fetch:
        return r.stdout.strip()
    return [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]

def load_variants():
    rows = psql('''SELECT v.id, v.slug, v."nameEn", cm."nameEn", m."nameEn"
        FROM "Variant" v JOIN "CarModel" cm ON v."modelId"=cm.id
        JOIN "Manufacturer" m ON cm."manufacturerId"=m.id''')
    variants = {}
    for row in rows:
        parts = row.split("|")
        if len(parts) >= 5:
            key = f"{parts[4].lower()}|{parts[3].lower()}|{parts[1].lower()}"
            variants[key] = parts[0]
            bm = f"{parts[4].lower()}|{parts[3].lower()}"
            if bm not in variants:
                variants[bm] = []
            variants[bm].append({"id": parts[0], "slug": parts[1], "name": parts[2]})
    return variants

def load_sources():
    rows = psql('SELECT id, "nameEn", "baseUrl", "domain" FROM "Source"')
    sources = {}
    for row in rows:
        parts = row.split("|")
        if len(parts) >= 4:
            sources[parts[3]] = {"id": parts[0], "name": parts[1], "url": parts[2]}
    return sources

MODEL_NORM = {
    "hilux revo": "hilux", "innova": "innova zenix",
    "corolla altis gr sport": "corolla altis",
    "corolla cross gr sport": "corolla cross",
    "fortuner gr sport": "fortuner", "fortuner legender": "fortuner",
    "yaris ativ gr sport": "yaris ativ", "yaris cross nightshade": "yaris cross",
    "new almera": "almera", "kicks e-power": "kicks", "serena epower": "serena",
    "mg3": "mg3", "mg4": "mg4", "mg5": "mg5",
    "s5 ev plus": "s5 ev plus", "mazda 6e": "mazda 6e",
}

def resolve_variant(brand, model, variant, vm):
    bl = brand.lower().strip()
    ml = model.lower().strip()
    ml = MODEL_NORM.get(ml, ml)
    bm = f"{bl}|{ml}"
    if bm in vm and isinstance(vm[bm], list) and vm[bm]:
        if variant in ("__MODEL_RANGE__", "__MODEL__"):
            return vm[bm][0]["id"]
        vl = variant.lower().strip()
        for v in vm[bm]:
            if vl in v["slug"].lower() or vl in v["name"].lower():
                return v["id"]
        for v in vm[bm]:
            if set(v["slug"].lower().split("-")) & set(re.split(r'[\s\-]+', vl)):
                return v["id"]
        return vm[bm][0]["id"]
    return None

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/Projects/thai-car-intelligence/storage/research/runs/2026-09-20/combined-pipeline-output.json"
    with open(path) as f:
        data = json.load(f)
    obs_list = data.get("accepted_observations", [])
    print(f"Loaded {len(obs_list)} observations")
    
    vm = load_variants()
    sources = load_sources()
    print(f"DB: {len(vm)} variant keys, {len(sources)} sources")
    
    stats = {"prices_inserted": 0, "prices_skipped": 0, "no_variant": 0,
             "specs_inserted": 0, "specs_skipped": 0, "resolved": 0}
    unresolved = set()
    
    for obs in obs_list:
        brand = obs.get("brand", "")
        model = obs.get("model", "")
        variant = obs.get("variant", "__MODEL_RANGE__")
        obs_field = obs.get("obs_field", "")
        
        vid = resolve_variant(brand, model, variant, vm)
        if not vid:
            stats["no_variant"] += 1
            unresolved.add(f"{brand}/{model}")
            continue
        stats["resolved"] += 1
        
        # Get/create source
        src_url = obs.get("source_url", "")
        src_class = obs.get("source_class", "SEARCH_LEAD")
        src_name = obs.get("source_name", "Unknown")
        from urllib.parse import urlparse
        parsed = urlparse(src_url)
        domain = parsed.netloc.replace("www.", "")
        src_key = f"{domain}{parsed.path.rstrip('/')}"
        
        if src_key not in sources and domain not in sources:
            sid = str(uuid.uuid4())
            type_map = {"OFFICIAL_API": "OFFICIAL_MANUFACTURER", "OFFICIAL_WEB": "OFFICIAL_MANUFACTURER",
                        "AUTO_MEDIA": "AUTOMOTIVE_MEDIA", "REFERENCE_MEDIA": "AUTOMOTIVE_MEDIA"}
            stype = type_map.get(src_class, "AUTOMOTIVE_MEDIA")
            psql(f'''INSERT INTO "Source" (id,"nameTh","nameEn","sourceType","baseUrl","domain","status","createdAt","updatedAt")
                VALUES ('{sid}','{src_name}','{src_name}','{stype}'::"SourceType",
                '{src_url}','{domain}','ACTIVE'::"RecordStatus",NOW(),NOW())''', fetch=False)
            sources[src_key] = {"id": sid, "name": src_name, "url": src_url}
            sources[domain] = {"id": sid, "name": src_name, "url": src_url}
        
        sid = sources.get(src_key, sources.get(domain, {})).get("id", "")
        if not sid:
            continue
        
        # Create source document
        chash = obs.get("content_hash", hashlib.sha256(src_url.encode()).hexdigest()[:16])
        method = obs.get("extraction_method", "unknown")
        title = obs.get("article_title", "")[:200].replace("'", "''")
        existing = psql(f'''SELECT id FROM "SourceDocument" WHERE "sourceId"='{sid}' AND "contentHash"='{chash}' ''')
        if existing:
            doc_id = existing[0]
        else:
            doc_id = str(uuid.uuid4())
            psql(f'''INSERT INTO "SourceDocument" (id,"sourceId",url,"contentHash","extractionMethod",titleEn,status,"createdAt","updatedAt")
                VALUES ('{doc_id}','{sid}','{src_url}','{chash}','{method}','{title}','VERIFIED'::"DocumentStatus",NOW(),NOW())''', fetch=False)
        
        if obs_field == "price":
            try:
                amount = int(float(obs.get("normalized_value", 0)))
            except:
                stats["prices_skipped"] += 1
                continue
            if amount < 100000:
                stats["prices_skipped"] += 1
                continue
            pt = obs.get("price_type", "LIST_PRICE")
            if pt not in ("LIST_PRICE", "MSRP"):
                pt = "LIST_PRICE"
            dup = psql(f'''SELECT id FROM "Price" WHERE "variantId"='{vid}' AND "sourceDocumentId"='{doc_id}'
                AND "priceType"='{pt}'::"PriceType" AND amount={amount}''')
            if dup:
                stats["prices_skipped"] += 1
                continue
            psql(f'''UPDATE "Price" SET "isCurrent"=false,"validTo"=NOW()
                WHERE "variantId"='{vid}' AND "priceType"='{pt}'::"PriceType" AND "isCurrent"=true''', fetch=False)
            pid = str(uuid.uuid4())
            psql(f'''INSERT INTO "Price" (id,"variantId","sourceDocumentId","priceType",amount,currency,"validFrom","isCurrent",confidence)
                VALUES ('{pid}','{vid}','{doc_id}','{pt}'::"PriceType",{amount},'THB',NOW(),true,0.75)''', fetch=False)
            stats["prices_inserted"] += 1
        elif obs_field.startswith("spec_"):
            key = obs_field.replace("spec_", "")
            value = obs.get("normalized_value", obs.get("raw_value", ""))[:500]
            value = value.replace("'", "''")
            key = key.replace("'", "''")[:100]
            psql(f'''INSERT INTO "VariantSpec" (id,"variantId","sourceDocumentId",key,"valueTh","valueEn",confidence)
                VALUES ('{str(uuid.uuid4())}','{vid}','{doc_id}','{key}','{value}','{value}',0.75)
                ON CONFLICT ("variantId",key,"sourceDocumentId") DO NOTHING''', fetch=False)
            stats["specs_inserted"] += 1
    
    print(f"\n=== Integration Complete ===")
    print(json.dumps(stats, indent=2))
    print(f"Unresolved: {len(unresolved)}")
    for m in sorted(unresolved)[:20]:
        print(f"  {m}")

if __name__ == "__main__":
    main()
