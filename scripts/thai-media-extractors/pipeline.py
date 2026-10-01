#!/usr/bin/env python3
"""
Thai Automotive Data Extraction Pipeline — main coordinator.

Orchestrates: OEM APIs, Thai media (9CARTHAI, Headlightmag).
Workers → artifacts → validation → dedup → identity resolve → DB.

Hard rules:
- Unknown model candidates stay unknown — NEVER persist
- Secondary media = RESEARCH_UNVERIFIED, never VERIFIED
- Rerun must be idempotent
- No mass-delete of existing valid records
"""
import json
import hashlib
import sys
import os
import time
from datetime import datetime
from typing import List, Dict, Set, Tuple
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(__file__))
from evidence_schema import Observation, RejectionRecord, ExtractionRun

PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(PIPELINE_DIR, "..", ".."))

# ─── Brand registry ──────────────────────────────────────────
BRANDS = {
    "toyota": {"name": "Toyota", "official_url": "https://www.toyota.co.th"},
    "honda": {"name": "Honda", "official_url": "https://www.honda.co.th"},
    "nissan": {"name": "Nissan", "official_url": "https://www.nissan.co.th/th"},
    "mazda": {"name": "Mazda", "official_url": "https://www.mazda.co.th"},
    "mg": {"name": "MG", "official_url": "https://www.mgcars.com/th"},
    "byd": {"name": "BYD", "official_url": "https://www.byd.com/th"},
    "gwm": {"name": "GWM", "official_url": "https://www.gwm.co.th"},
    "ford": {"name": "Ford", "official_url": "https://www.ford.co.th"},
    "isuzu": {"name": "Isuzu", "official_url": "https://www.isuzu-tis.com"},
    "bmw": {"name": "BMW", "official_url": "https://www.bmw.co.th"},
    "mercedes-benz": {"name": "Mercedes-Benz", "official_url": "https://www.mercedes-benz.co.th"},
    "volvo": {"name": "Volvo", "official_url": "https://www.volvo.co.th"},
    "chevrolet": {"name": "Chevrolet", "official_url": "https://www.chevrolet.co.th"},
    "chery": {"name": "Chery", "official_url": "https://www.chery.co.th"},
    "hyundai": {"name": "Hyundai", "official_url": "https://www.hyundai.co.th"},
    "kia": {"name": "Kia", "official_url": "https://www.kia.com/th"},
    "subaru": {"name": "Subaru", "official_url": "https://www.subaru.co.th"},
    "mitsubishi": {"name": "Mitsubishi", "official_url": "https://www.mitsubishi-motors.co.th/th"},
    "suzuki": {"name": "Suzuki", "official_url": "https://www.suzuki.co.th"},
    "porsche": {"name": "Porsche", "official_url": "https://www.porsche.com/thailand"},
    "mini": {"name": "Mini", "official_url": "https://www.mini.co.th"},
    "zeekr": {"name": "Zeekr", "official_url": "https://www.zeekrlife.com/th"},
    "changan": {"name": "Changan", "official_url": "https://www.changan.co.th"},
    "dongfeng": {"name": "Dongfeng", "official_url": "https://www.dongfeng.co.th"},
    "ldv": {"name": "LDV", "official_url": "https://www.ldvautomotive.co.th"},
    "jetour": {"name": "Jetour", "official_url": "https://www.jetour.co.th"},
    "baic": {"name": "BAIC", "official_url": "https://www.baicmotor.co.th"},
    "geely": {"name": "Geely", "official_url": "https://www.geely.com/th"},
    "kg-mobility": {"name": "KG Mobility", "official_url": "https://www.kgmobility.co.th"},
    "lexus": {"name": "Lexus", "official_url": "https://www.lexus.co.th"},
    "nio": {"name": "NIO", "official_url": "https://www.nio.com/th"},
    "avora": {"name": "Avora", "official_url": "https://www.avora.co.th"},
    "denza": {"name": "Denza", "official_url": "https://www.denza.co.th"},
}


def quarantine_generic_candidates(observations: List[dict]) -> Tuple[List[dict], List[dict]]:
    """Separate real observations from generic/unknown-model candidates."""
    accepted = []
    quarantined = []
    for obs in observations:
        model = obs.get("model", "")
        variant = obs.get("variant", "")
        # Quarantine rules
        if not model or model == "unknown":
            quarantined.append({**obs, "_quarantine_reason": "no_model_identity"})
        elif model.startswith("ราคา") or "headlight" in model.lower():
            quarantined.append({**obs, "_quarantine_reason": "model_is_article_title"})
        elif variant == "unknown" and obs.get("scope") == "VARIANT":
            quarantined.append({**obs, "_quarantine_reason": "variant_unknown"})
        else:
            accepted.append(obs)
    return accepted, quarantined


def dedup_observations(observations: List[dict]) -> List[dict]:
    """Deduplicate by (brand, model, variant, price, source_url)."""
    seen: Set[str] = set()
    deduped = []
    for obs in observations:
        key = f"{obs.get('brand')}|{obs.get('model')}|{obs.get('variant')}|{obs.get('normalized_value')}|{obs.get('source_url')}"
        h = hashlib.sha256(key.encode()).hexdigest()[:16]
        if h not in seen:
            seen.add(h)
            deduped.append(obs)
    return deduped


def run_oem_extraction() -> Tuple[List[dict], List[dict]]:
    """Run OEM-specific extractors."""
    all_obs = []
    all_rej = []

    # Toyota API
    try:
        from toyota_api import extract_toyota
        toyota_obs = extract_toyota()
        all_obs.extend(toyota_obs)
        print(f"  Toyota API: {len(toyota_obs)} observations")
    except Exception as e:
        print(f"  Toyota FAIL: {e}", file=sys.stderr)

    # Nissan iframe
    try:
        from nissan_iframe import extract_nissan
        nissan_obs, nissan_rej = extract_nissan()
        all_obs.extend(nissan_obs)
        all_rej.extend(nissan_rej)
        print(f"  Nissan iframe: {len(nissan_obs)} observations, {len(nissan_rej)} rejections")
    except Exception as e:
        print(f"  Nissan FAIL: {e}", file=sys.stderr)

    # Mitsubishi homepage
    try:
        from mitsubishi_homepage import extract_mitsubishi
        mits_obs, mits_rej = extract_mitsubishi(
            __import__("urllib.request", fromlist=["urlopen"]).urlopen(
                __import__("urllib.request", fromlist=["Request"]).Request(
                    "https://www.mitsubishi-motors.co.th/th",
                    headers={"User-Agent": "Mozilla/5.0 Chrome/131"}
                ), timeout=15
            ).read().decode("utf-8", errors="replace")
        )
        all_obs.extend(mits_obs)
        all_rej.extend(mits_rej)
        print(f"  Mitsubishi: {len(mits_obs)} observations")
    except Exception as e:
        print(f"  Mitsubishi FAIL: {e}", file=sys.stderr)

    return all_obs, all_rej


def run_media_extraction(max_hl_articles: int = 30) -> Tuple[List[dict], List[dict]]:
    """Run Thai media extractors (9CARTHAI + Headlightmag)."""
    all_obs = []
    all_rej = []

    # Headlightmag
    try:
        from headlightmag_extractor import run_headlightmag_extraction
        hl_obs, hl_rej, hl_stats = run_headlightmag_extraction(max_hl_articles)
        all_obs.extend([o.to_dict() for o in hl_obs])
        all_rej.extend([r.to_dict() for r in hl_rej])
        print(f"  Headlightmag: {len(hl_obs)} obs, {len(hl_rej)} rej, {hl_stats}")
    except Exception as e:
        print(f"  Headlightmag FAIL: {e}", file=sys.stderr)

    return all_obs, all_rej


def run_9carthai_extraction() -> Tuple[List[dict], List[dict]]:
    """Run 9CARTHAI brand page extraction."""
    # Import 9carthai parser (filename starts with digit, so use importlib)
    import importlib.util
    _9c_spec = importlib.util.spec_from_file_location("ninecarthai_parser",
        os.path.join(PIPELINE_DIR, "9carthai_parser.py"))
    _9c_mod = importlib.util.module_from_spec(_9c_spec)
    _9c_spec.loader.exec_module(_9c_mod)
    parse_brand_page = _9c_mod.parse_brand_page
    all_obs = []
    all_rej = []

    for brand_slug in list(BRANDS.keys())[:20]:  # Top 20 brands
        url = f"https://www.9carthai.com/{brand_slug}-price/"
        try:
            req = Request(url, headers={
                "User-Agent": "Mozilla/5.0 Chrome/131",
                "Accept-Language": "th,en;q=0.9",
            })
            with urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            obs, rej = parse_brand_page(html, brand_slug, url)
            all_obs.extend([o.to_dict() for o in obs])
            all_rej.extend([r.to_dict() for r in rej])
            print(f"  9CARTHAI {brand_slug}: {len(obs)} obs, {len(rej)} rej")
            time.sleep(1.0)
        except Exception as e:
            print(f"  9CARTHAI {brand_slug} FAIL: {e}", file=sys.stderr)
            all_rej.append({
                "brand": brand_slug, "model_hint": "unknown",
                "reason": f"fetch_failed: {e}",
                "source_url": url,
            })

    return all_obs, all_rej


def main():
    run_id = f"pipeline-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir = os.path.join("/tmp/thai-car-pipeline", run_id)
    os.makedirs(run_dir, exist_ok=True)

    print(f"=== Pipeline Run: {run_id} ===")
    run = ExtractionRun(run_id=run_id)

    # Phase 1: OEM extraction (parallel-safe, official sources)
    print("\n--- Phase 1: OEM Extraction ---")
    oem_obs, oem_rej = run_oem_extraction()
    run.raw_candidates += len(oem_obs) + len(oem_rej)

    # Phase 2: Thai media extraction
    print("\n--- Phase 2: Thai Media Extraction ---")
    media_obs, media_rej = run_media_extraction(max_hl_articles=30)
    run.raw_candidates += len(media_obs) + len(media_rej)

    # Phase 2b: 9CARTHAI
    print("\n--- Phase 2b: 9CARTHAI Extraction ---")
    nine_obs, nine_rej = run_9carthai_extraction()
    run.raw_candidates += len(nine_obs) + len(nine_rej)

    # Phase 3: Quarantine generic unknowns
    print("\n--- Phase 3: Quarantine ---")
    all_obs = oem_obs + media_obs + nine_obs
    all_rej = oem_rej + media_rej + nine_rej
    accepted, quarantined = quarantine_generic_candidates(all_obs)
    print(f"  Raw: {len(all_obs)}, Accepted: {len(accepted)}, Quarantined: {len(quarantined)}")

    # Phase 4: Dedup
    print("\n--- Phase 4: Dedup ---")
    deduped = dedup_observations(accepted)
    print(f"  Before dedup: {len(accepted)}, After: {len(deduped)}")

    # Phase 5: Write artifacts
    print("\n--- Phase 5: Write Artifacts ---")
    artifacts = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "accepted_observations": deduped,
        "quarantined_candidates": quarantined,
        "rejected_candidates": all_rej,
        "summary": {
            "raw_candidates": run.raw_candidates,
            "accepted": len(deduped),
            "quarantined": len(quarantined),
            "rejected": len(all_rej),
            "price_observations": len([o for o in deduped if o.get("obs_field") == "price"]),
            "spec_observations": len([o for o in deduped if o.get("obs_field", "").startswith("spec_")]),
            "brands_with_data": list(set(o.get("brand") for o in deduped)),
            "models_with_data": list(set(o.get("model") for o in deduped if o.get("obs_field") == "price")),
        },
    }

    output_path = os.path.join(run_dir, "pipeline-output.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(artifacts, f, indent=2, ensure_ascii=False)

    print(f"\n=== Pipeline Complete ===")
    print(f"  Output: {output_path}")
    print(f"  Summary: {json.dumps(artifacts['summary'], indent=2, ensure_ascii=False)}")

    return artifacts


if __name__ == "__main__":
    main()
