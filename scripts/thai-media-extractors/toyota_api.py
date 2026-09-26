#!/usr/bin/env python3
"""
Toyota Thailand API extractor.
Source: POST https://www.toyota.co.th/component/api/tcoth/web-init
Returns JSON with car_series key — 34 models with start_price/max_price.
Source class: OFFICIAL_API, trustState: QUALIFIED.
"""
import json
import hashlib
import sys
import os
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(__file__))
from evidence_schema import Observation

TOYOTA_API = "https://www.toyota.co.th/component/api/tcoth/web-init"

def fetch_toyota_api():
    req = Request(TOYOTA_API, method="POST",
                  headers={"Content-Type": "application/json",
                           "User-Agent": "Mozilla/5.0 Chrome/131"})
    req.data = b"{}"
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def extract_toyota() -> list[dict]:
    data = fetch_toyota_api()
    series = data.get("car_series", data.get("data", {}))
    if isinstance(series, list):
        series = {s.get("code", str(i)): s for i, s in enumerate(series)}

    obs = []
    for code, info in series.items():
        title = info.get("title_en") or info.get("title", "")
        start = info.get("start_price", 0)
        maxp = info.get("max_price", 0)
        if not title or not start:
            continue

        excerpt = json.dumps({k: info[k] for k in ["code", "title_en", "start_price", "max_price", "model_code"] if k in info}, ensure_ascii=False)
        ch = hashlib.sha256(excerpt.encode()).hexdigest()[:16]

        obs.append({
            "brand": "toyota", "model": title,
            "variant": "__MODEL_RANGE__", "scope": "MODEL",
            "obs_field": "price", "raw_value": str(start),
            "normalized_value": str(start), "unit": "THB",
            "price_type": "LIST_PRICE",
            "source_url": TOYOTA_API, "source_class": "OFFICIAL_API",
            "extraction_method": "toyota_web_init_api",
            "evidence_excerpt": excerpt, "content_hash": ch,
            "trust_state": "QUALIFIED",
            "source_name": "Toyota Thailand API",
            "raw_json_path": f"car_series[{code}]",
        })
        if maxp and maxp != start:
            obs[-1]["price_max_thb"] = maxp
    return obs

def extract_toyota_detail(code: str) -> list[dict]:
    url = f"https://www.toyota.co.th/en/model/api/car/?series_code={code}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 Chrome/131"})
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    items = data.get("data", [])
    if not items:
        return []
    item = items[0]
    grades = item.get("grades", [])
    obs = []
    model_name = item.get("title_en", item.get("name", code))
    for g in grades:
        gname = g.get("name", "")
        price = g.get("price") or g.get("msrp", 0)
        if not price:
            continue
        excerpt = json.dumps({"grade": gname, "price": price}, ensure_ascii=False)
        ch = hashlib.sha256(excerpt.encode()).hexdigest()[:16]
        obs.append({
            "brand": "toyota", "model": model_name,
            "variant": gname or "__MODEL_RANGE__",
            "scope": "VARIANT" if gname else "MODEL",
            "obs_field": "price", "raw_value": str(price),
            "normalized_value": str(price), "unit": "THB",
            "price_type": "MSRP" if gname else "LIST_PRICE",
            "source_url": url, "source_class": "OFFICIAL_API",
            "extraction_method": "toyota_model_detail_api",
            "evidence_excerpt": excerpt, "content_hash": ch,
            "trust_state": "QUALIFIED",
            "source_name": "Toyota Thailand API",
        })
        # Specs
        specs = g.get("specifications", [])
        for group in specs:
            for item_spec in group.get("items", []):
                skey = item_spec.get("title_en", "")
                sval = item_spec.get("value_en", "")
                if skey and sval:
                    obs.append({
                        "brand": "toyota", "model": model_name,
                        "variant": gname or "__MODEL__",
                        "scope": "VARIANT" if gname else "MODEL",
                        "obs_field": f"spec_{skey.lower().replace(' ', '_')}",
                        "raw_value": sval, "normalized_value": sval,
                        "source_url": url, "source_class": "OFFICIAL_API",
                        "extraction_method": "toyota_model_detail_api",
                        "evidence_excerpt": f"{skey}: {sval}",
                        "content_hash": hashlib.sha256(f"{skey}:{sval}".encode()).hexdigest()[:16],
                        "trust_state": "QUALIFIED",
                        "source_name": "Toyota Thailand API",
                    })
    return obs

if __name__ == "__main__":
    print("Fetching Toyota API...")
    obs = extract_toyota()
    print(f"Models from list API: {len(obs)}")
    # Fetch detail for first few
    detail_obs = []
    for o in obs[:5]:
        code_guess = o.get("raw_json_path", "").strip("car_series[]")
        if code_guess:
            try:
                detail_obs.extend(extract_toyota_detail(code_guess))
            except Exception as e:
                print(f"  Detail fail for {code_guess}: {e}", file=sys.stderr)
    all_obs = obs + detail_obs
    print(f"Total observations: {len(all_obs)}")
    print(json.dumps(all_obs, indent=2, ensure_ascii=False))
