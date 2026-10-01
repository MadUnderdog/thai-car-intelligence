#!/usr/bin/env python3
"""Generate a Thai alias catalog for all CarModel and Manufacturer records.

Queries the live DB, builds Thai brand/model aliases, generates search query
templates, and exports the catalog to storage/thai-alias-catalog.json.

Usage:
    python3 scripts/thai-alias-catalog.py
"""

import json
import os
import sys
from pathlib import Path

import psycopg2

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "thai_car_intelligence"),
    "user": os.getenv("DB_USER", "hermes"),
    "password": os.getenv("DB_PASSWORD", "hermes2026"),
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage"
OUTPUT_FILE = STORAGE_DIR / "thai-alias-catalog.json"

# Thai brand aliases: English name → known Thai transliterations
# The DB already stores nameTh on Manufacturer; this map adds *extra* aliases
# that Thai speakers commonly type (shorter forms, alternate spellings).
THAI_BRAND_ALIASES: dict[str, list[str]] = {
    "Toyota":        ["โตโยต้า"],
    "Honda":         ["ฮอนด้า"],
    "Nissan":        ["นิสสัน"],
    "Mazda":         ["มาสด้า"],
    "Mercedes-Benz": ["เมอร์เซเดส-เบนซ์", "เบนซ์", "Mercedes"],
    "BMW":           ["บีเอ็มดับเบิลยู", "บีเอ็มดับบลิว", "บีเอ็ม", "BMW"],
    "Volvo":         ["วอลโว่", "วอลโว"],
    "Tesla":         ["เทสลา"],
    "BYD":           ["บีวายดี"],
    "MG":            ["เอ็มจี", "MG"],
    "GWM":           ["เกรทวอลล์มอเตอร์", "เกรทวอลล์", "จีดับบลิวเอ็ม", "GWM"],
    "Chery":         ["เชอรี", "เชอรี่"],
    "Ford":          ["ฟอร์ด"],
    "Hyundai":       ["ฮุนได"],
    "Kia":           ["เกีย"],
    "Mitsubishi":    ["มิตซูบิชิ"],
    "Isuzu":         ["อีซูซุ"],
    "Suzuki":        ["ซูซูกิ"],
    "Subaru":        ["ซูบารุ"],
    "Porsche":       ["ปอร์เช่"],
    "MINI":          ["มินิ"],
    "Lexus":         ["เล็กซัส"],
}

# Search query template patterns
SEARCH_TEMPLATES = [
    "{brand} {model}",
    "{brand_th} {model}",
    "{brand_th} {model_th}",
    "{brand_th} ราคา",
    "{model_th} เปิดตัว",
    "{model_th} สเปก",
    "{model_th} รุ่นย่อย",
    "{model_th} 2026",
]


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_connection():
    """Return a psycopg2 connection using DB_CONFIG."""
    return psycopg2.connect(**DB_CONFIG)


def fetch_manufacturers_list(conn) -> list[dict]:
    """Return list of manufacturer dicts."""
    with conn.cursor() as cur:
        cur.execute(
            'SELECT id, "nameEn", "nameTh", slug FROM "Manufacturer" ORDER BY "nameEn"'
        )
        return [
            {"id": r[0], "nameEn": r[1], "nameTh": r[2], "slug": r[3]}
            for r in cur.fetchall()
        ]


def fetch_models_with_manufacturers(conn) -> list[dict]:
    """Return list of model dicts with joined manufacturer info."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cm."nameEn", cm."nameTh", cm.slug,
                   m."nameEn" AS brand_en, m."nameTh" AS brand_th, m.slug AS brand_slug
            FROM "CarModel" cm
            JOIN "Manufacturer" m ON cm."manufacturerId" = m.id
            ORDER BY m."nameEn", cm."nameEn"
            """
        )
        return [
            {
                "nameEn": r[0],
                "nameTh": r[1],
                "slug": r[2],
                "brandEn": r[3],
                "brandTh": r[4],
                "brandSlug": r[5],
            }
            for r in cur.fetchall()
        ]


# ---------------------------------------------------------------------------
# Catalog generation
# ---------------------------------------------------------------------------

def build_brand_aliases(manufacturers: list[dict]) -> dict[str, dict]:
    """Build brand alias mapping from DB manufacturers + hardcoded aliases."""
    brands = {}
    for m in manufacturers:
        en = m["nameEn"]
        th = m["nameTh"]
        slug = m["slug"]

        # All known Thai aliases for this brand
        aliases = set()
        if th:
            aliases.add(th)
        if en in THAI_BRAND_ALIASES:
            aliases.update(THAI_BRAND_ALIASES[en])

        brands[slug] = {
            "nameEn": en,
            "nameTh": th,
            "slug": slug,
            "aliases": sorted(aliases),
        }
    return brands


def build_model_aliases(models: list[dict]) -> dict[str, dict]:
    """Build model alias mapping with search query templates."""
    result = {}
    for m in models:
        slug = m["slug"]
        name_en = m["nameEn"]
        name_th = m["nameTh"]
        brand_en = m["brandEn"]
        brand_th = m["brandTh"]
        brand_slug = m["brandSlug"]

        # Collect all aliases: English name, Thai name, slug
        aliases = set()
        if name_en:
            aliases.add(name_en)
        if name_th:
            aliases.add(name_th)
        if slug:
            aliases.add(slug)

        # Generate search query templates
        queries = []
        for tpl in SEARCH_TEMPLATES:
            q = tpl.format(
                brand=brand_en,
                brand_th=brand_th or brand_en,
                model=name_en,
                model_th=name_th or name_en,
            )
            if q not in queries:
                queries.append(q)

        result[slug] = {
            "nameEn": name_en,
            "nameTh": name_th,
            "slug": slug,
            "brandEn": brand_en,
            "brandTh": brand_th,
            "brandSlug": brand_slug,
            "aliases": sorted(aliases),
            "searchQueries": queries,
        }
    return result


def generate_catalog(conn) -> dict:
    """Generate the full Thai alias catalog."""
    manufacturers = fetch_manufacturers_list(conn)
    models = fetch_models_with_manufacturers(conn)

    brands = build_brand_aliases(manufacturers)
    models_catalog = build_model_aliases(models)

    return {
        "version": "1.0",
        "generated_by": "thai-alias-catalog.py",
        "stats": {
            "brands_covered": len(brands),
            "models_covered": len(models_catalog),
            "total_aliases": sum(len(v["aliases"]) for v in brands.values())
            + sum(len(v["aliases"]) for v in models_catalog.values()),
            "total_search_queries": sum(
                len(v["searchQueries"]) for v in models_catalog.values()
            ),
        },
        "brands": brands,
        "models": models_catalog,
    }


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_catalog(catalog: dict, output_path: Path = OUTPUT_FILE):
    """Write the catalog JSON to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    print(f"✅ Catalog exported to {output_path}")
    print(f"   Brands: {catalog['stats']['brands_covered']}")
    print(f"   Models: {catalog['stats']['models_covered']}")
    print(f"   Total aliases: {catalog['stats']['total_aliases']}")
    print(f"   Total search queries: {catalog['stats']['total_search_queries']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Main entry point."""
    try:
        conn = get_connection()
        catalog = generate_catalog(conn)
        export_catalog(catalog)
        conn.close()
        return catalog
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
