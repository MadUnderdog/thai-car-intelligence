#!/usr/bin/env python3
"""Ultra-fast batch spec integration — groups by variant+source, uses multi-row INSERT."""
import json, hashlib, sys, os, re, subprocess, uuid
from collections import defaultdict

def psql(sql, fetch=True):
    cmd = ["docker", "exec", "pgvector", "psql", "-U", "hermes", "-d", "thai_car_intelligence",
           "-t", "-A", "-F", "|", "-c", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return []
    if not fetch:
        return r.stdout.strip()
    return [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]

def load_variants():
    rows = psql('''SELECT v.id, v.slug, cm."nameEn", m."nameEn"
        FROM "Variant" v JOIN "CarModel" cm ON v."modelId"=cm.id
        JOIN "Manufacturer" m ON cm."manufacturerId"=m.id''')
    vm = {}
    for row in rows:
        p = row.split("|")
        if len(p) >= 4:
            bm = f"{p[3].lower()}|{p[2].lower()}"
            if bm not in vm:
                vm[bm] = []
            vm[bm].append(p[0])
    return vm

MODEL_NORM = {
    "hilux revo": "hilux", "innova": "innova zenix",
    "corolla altis gr sport": "corolla altis",
    "fortuner gr sport": "fortuner", "fortuner legender": "fortuner",
    "yaris ativ gr sport": "yaris ativ",
}

def resolve_vid(brand, model, vm):
    bl = brand.lower().strip()
    ml = model.lower().strip()
    ml = MODEL_NORM.get(ml, ml)
    bm = f"{bl}|{ml}"
    if bm in vm and vm[bm]:
        return vm[bm][0]
    return None

def main():
    path = sys.argv[1]
    with open(path) as f:
        data = json.load(f)
    obs_list = data.get("accepted_observations", [])
    
    # Only process specs
    spec_obs = [o for o in obs_list if o.get("obs_field", "").startswith("spec_")]
    print(f"Processing {len(spec_obs)} spec observations")
    
    vm = load_variants()
    
    # Group by (brand, model, source_url, content_hash)
    groups = defaultdict(list)
    for obs in spec_obs:
        key = (obs.get("brand",""), obs.get("model",""), obs.get("source_url",""), obs.get("content_hash",""))
        groups[key].append(obs)
    
    inserted = 0
    skipped = 0
    for (brand, model, src_url, chash), obss in groups.items():
        vid = resolve_vid(brand, model, vm)
        if not vid:
            skipped += len(obss)
            continue
        
        # Get or create source doc
        from urllib.parse import urlparse
        parsed = urlparse(src_url)
        domain = parsed.netloc.replace("www.", "")
        
        existing = psql(f'''SELECT id FROM "SourceDocument" WHERE "contentHash"='{chash}' LIMIT 1''')
        if existing:
            doc_id = existing[0]
        else:
            # Find source
            src_rows = psql(f'''SELECT id FROM "Source" WHERE "domain"='{domain}' LIMIT 1''')
            sid = src_rows[0] if src_rows else None
            if not sid:
                sid = str(uuid.uuid4())
                psql(f'''INSERT INTO "Source" (id,"nameTh","nameEn","sourceType","baseUrl","domain","status","createdAt","updatedAt")
                    VALUES ('{sid}','API','API','OFFICIAL_MANUFACTURER'::"SourceType",
                    '{src_url}','{domain}','ACTIVE'::"RecordStatus",NOW(),NOW())''', fetch=False)
            doc_id = str(uuid.uuid4())
            psql(f'''INSERT INTO "SourceDocument" (id,"sourceId",url,"contentHash","extractionMethod",status,"createdAt","updatedAt")
                VALUES ('{doc_id}','{sid}','{src_url}','{chash}','toyota_car_api','VERIFIED'::"DocumentStatus",NOW(),NOW())''', fetch=False)
        
        # Batch insert specs
        values = []
        for obs in obss:
            key = obs.get("obs_field","").replace("spec_","").replace("'","''")[:100]
            val = obs.get("normalized_value", obs.get("raw_value",""))[:500].replace("'","''")
            sid2 = str(uuid.uuid4())
            values.append(f"('{sid2}','{vid}','{doc_id}','{key}','{val}','{val}',0.75)")
        
        if values:
            # Insert in batches of 50
            for i in range(0, len(values), 50):
                batch = values[i:i+50]
                sql = f'''INSERT INTO "VariantSpec" (id,"variantId","sourceDocumentId",key,"valueTh","valueEn",confidence)
                    VALUES {",".join(batch)} ON CONFLICT ("variantId",key,"sourceDocumentId") DO NOTHING'''
                psql(sql, fetch=False)
                inserted += len(batch)
    
    print(f"Inserted: {inserted}, Skipped: {skipped}")

if __name__ == "__main__":
    main()
