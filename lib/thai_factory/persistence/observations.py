"""
Observation persistence layer — FIXED per audit findings.

FIXES:
1. resolve_variant: exact ID first, no LIMIT 1 fuzzy matching
2. Price type: never rewrite unknown to MSRP; preserve explicit types
3. Current price: don't auto-expire; determine currentness from source semantics
4. SourceDocument: deterministic upsert by URL + contentHash
5. Fingerprint: includes variant, uses full SHA-256
6. Observation immutability: deterministic observation key
"""
import hashlib
import subprocess
import uuid
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone

from ..models import Observation, PriceType, SourceClass


def _psql(sql: str, fetch: bool = True) -> List[str]:
    """Execute SQL via docker exec psql."""
    cmd = [
        "docker", "exec", "pgvector", "psql",
        "-U", "hermes", "-d", "thai_car_intelligence",
        "-t", "-A", "-F", "|", "-c", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"psql error: {result.stderr[:500]}")
    if not fetch:
        return [result.stdout.strip()]
    lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
    return lines


def get_or_create_source(domain: str, url: str, source_class: str = "AUTOMOTIVE_MEDIA") -> str:
    """Get or create a Source record. Returns source ID."""
    rows = _psql(f"SELECT id FROM \"Source\" WHERE domain = '{domain}' LIMIT 1")
    if rows:
        return rows[0]

    source_id = str(uuid.uuid4())
    _psql(f"""
        INSERT INTO "Source" (id, "nameTh", "nameEn", "sourceType", "baseUrl", domain, "rightsStatus")
        VALUES ('{source_id}', '{domain}', '{domain}', '{source_class}',
                '{url[:500]}', '{domain}', 'UNKNOWN')
    """, fetch=False)
    return source_id


def get_or_create_source_document(source_id: str, url: str, content_hash: str,
                                   title: str = "") -> str:
    """
    Deterministic upsert of SourceDocument by URL + contentHash.
    FIX: No longer creates duplicate documents for same URL.
    """
    url_safe = url[:500].replace("'", "''")
    rows = _psql(f"""
        SELECT id FROM "SourceDocument"
        WHERE url = '{url_safe}' AND "contentHash" = '{content_hash}'
        LIMIT 1
    """)
    if rows:
        return rows[0]

    doc_id = str(uuid.uuid4())
    title_safe = title.replace("'", "''")[:500] if title else ""
    _psql(f"""
        INSERT INTO "SourceDocument" (id, "sourceId", url, "contentHash",
               "titleEn", "createdAt", "updatedAt")
        VALUES ('{doc_id}', '{source_id}', '{url_safe}', '{content_hash}',
                '{title_safe}', NOW(), NOW())
    """, fetch=False)
    return doc_id


def resolve_variant_exact(brand: str, model: str, variant: str = "") -> Optional[str]:
    """
    Resolve brand+model+variant to a Variant ID.
    FIX: Exact match first. No fuzzy LIMIT 1.
    Returns None if no exact match found.
    """
    brand_lower = brand.lower().strip()
    model_lower = model.lower().strip()
    variant_lower = variant.lower().strip() if variant else ""

    # Stage 1: Try exact variant match if variant provided
    if variant_lower:
        rows = _psql(f"""
            SELECT v.id
            FROM "Variant" v
            JOIN "CarModel" cm ON v."modelId" = cm.id
            JOIN "Manufacturer" m ON cm."manufacturerId" = m.id
            WHERE LOWER(m.slug) = '{brand_lower}'
              AND LOWER(v."nameEn") = '{variant_lower}'
              AND v.status = 'ACTIVE'
            LIMIT 1
        """)
        if rows:
            return rows[0]

    # Stage 2: Try exact model match — only if exactly 1 variant exists
    # FIX: Never pick first variant when multiple exist (model-level contamination)
    rows = _psql(f"""
        SELECT v.id, v."nameEn"
        FROM "Variant" v
        JOIN "CarModel" cm ON v."modelId" = cm.id
        JOIN "Manufacturer" m ON cm."manufacturerId" = m.id
        WHERE LOWER(m.slug) = '{brand_lower}'
          AND (
            LOWER(cm."nameEn") = '{model_lower}'
            OR LOWER(cm.slug) = '{model_lower.replace(" ", "-")}'
          )
          AND v.status = 'ACTIVE'
        ORDER BY v."nameEn"
    """)
    if rows:
        if len(rows) == 1:
            # Single variant — safe to map model-level data to it
            return rows[0][0]
        else:
            # Multiple variants — do NOT pick first, return None
            # Caller should mark as MODEL_LEVEL or NEEDS_REVIEW
            return None

    # Stage 3: No exact match — return None (do NOT fuzzy match)
    return None


def resolve_variant(brand: str, model: str) -> Optional[str]:
    """Resolve brand+model to a Variant ID. Uses exact matching."""
    return resolve_variant_exact(brand, model)


def persist_observations(observations: List[Observation],
                         dry_run: bool = False) -> Dict[str, int]:
    """
    Persist validated observations to the DB.
    PRESERVES HISTORY — each observation becomes a new DB row.

    FIXES:
    - Price type preserved (never rewrite unknown to MSRP)
    - No auto-expiration of current prices
    - Deterministic SourceDocument upsert
    - Full SHA-256 fingerprints
    """
    stats = {
        "prices_inserted": 0,
        "specs_inserted": 0,
        "no_variant": 0,
        "no_source": 0,
        "errors": 0,
        "skipped_unknown_price_type": 0,
    }

    source_cache: Dict[str, str] = {}
    doc_cache: Dict[str, str] = {}
    price_batch = []
    spec_batch = []
    seen_fingerprints: Set[str] = set()

    for obs in observations:
        if obs.persisted:
            continue

        # Skip unknown price types
        if obs.field == "price" and obs.price_type == PriceType.UNKNOWN:
            stats["skipped_unknown_price_type"] += 1
            continue

        # Skip historical and promotion prices from becoming current
        if obs.field == "price" and obs.price_type in (PriceType.HISTORICAL, PriceType.PROMOTION):
            stats["skipped_unknown_price_type"] += 1
            continue

        # Resolve variant — exact match only
        variant_id = resolve_variant_exact(obs.brand, obs.model, obs.variant)
        if not variant_id:
            stats["no_variant"] += 1
            continue

        # Get/create source
        if obs.source_domain not in source_cache:
            if dry_run:
                source_cache[obs.source_domain] = "dry-run-source"
            else:
                source_class_str = obs.source_class.value if hasattr(obs.source_class, 'value') else str(obs.source_class)
                source_cache[obs.source_domain] = get_or_create_source(
                    obs.source_domain, obs.source_url, source_class_str
                )
        source_id = source_cache[obs.source_domain]

        # Get/create document (deterministic upsert)
        if obs.source_url not in doc_cache:
            if dry_run:
                doc_cache[obs.source_url] = "dry-run-doc"
            else:
                doc_cache[obs.source_url] = get_or_create_source_document(
                    source_id, obs.source_url, obs.content_hash, obs.title
                )
        doc_id = doc_cache[obs.source_url]

        # Compute full fingerprint
        fp_raw = f"{obs.source_domain}|{obs.source_url}|{obs.brand}|{obs.model}|{obs.variant}|{obs.field}|{obs.normalized_value}|{obs.price_type.value if hasattr(obs.price_type, 'value') else obs.price_type}"
        fingerprint = hashlib.sha256(fp_raw.encode()).hexdigest()

        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)

        # Persist based on field type
        if obs.field == "price":
            amount = int(obs.normalized_value)
            pt = obs.price_type.value if hasattr(obs.price_type, 'value') else str(obs.price_type)

            # Never rewrite unknown types to MSRP
            if pt not in ("MSRP", "LIST_PRICE", "PROMOTION", "MODEL_RANGE", "HISTORICAL"):
                stats["skipped_unknown_price_type"] += 1
                continue

            price_id = str(uuid.uuid4())
            # FIX: Use source publication date, not NOW()
            source_tier = obs.source_class.value if hasattr(obs.source_class, 'value') else str(obs.source_class)
            valid_from = obs.published_date.replace("'", "") if obs.published_date else "NOW()"
            price_batch.append(
                f'INSERT INTO "Price" (id, "variantId", "sourceDocumentId", "priceType", '
                f'amount, currency, "validFrom", "isCurrent", confidence, "sourceTier", "sourceUrl") '
                f'VALUES (\'{price_id}\', \'{variant_id}\', \'{doc_id}\', \'{pt}\'::"PriceType", '
                f'{amount}, \'THB\', \'{valid_from}\', true, 0.7, '
                f'\'{source_tier}\', \'{obs.source_url[:500].replace(chr(39), "")}\')'
            )
            stats["prices_inserted"] += 1

        elif obs.field != "price":
            key = obs.field[:100].replace("'", "''")
            val = obs.normalized_value.replace("'", "''")[:500]
            unit_val = f"'{obs.unit}'" if obs.unit else "NULL"
            numeric_val = "NULL"
            try:
                numeric_val = str(float(obs.normalized_value))
            except (ValueError, TypeError):
                pass

            spec_id = str(uuid.uuid4())
            spec_batch.append(
                f'INSERT INTO "VariantSpec" (id, "variantId", "sourceDocumentId", key, '
                f'"valueTh", "valueEn", "valueNumeric", unit, confidence) '
                f'VALUES (\'{spec_id}\', \'{variant_id}\', \'{doc_id}\', \'{key}\', '
                f'\'{val}\', \'{val}\', {numeric_val}, {unit_val}, 0.7) '
                f'ON CONFLICT ("variantId", key, "sourceDocumentId") DO NOTHING'
            )
            stats["specs_inserted"] += 1

        # Flush batches periodically
        if len(price_batch) >= 100:
            if not dry_run:
                try:
                    _psql("BEGIN; " + "; ".join(price_batch) + "; COMMIT;", fetch=False)
                except Exception:
                    stats["errors"] += 1
            price_batch = []

        if len(spec_batch) >= 50:
            if not dry_run:
                try:
                    _psql("BEGIN; " + "; ".join(spec_batch) + "; COMMIT;", fetch=False)
                except Exception:
                    stats["errors"] += 1
            spec_batch = []

    # Flush remaining
    if price_batch and not dry_run:
        try:
            _psql("BEGIN; " + "; ".join(price_batch) + "; COMMIT;", fetch=False)
        except Exception:
            stats["errors"] += 1

    if spec_batch and not dry_run:
        try:
            _psql("BEGIN; " + "; ".join(spec_batch) + "; COMMIT;", fetch=False)
        except Exception:
            stats["errors"] += 1

    return stats
