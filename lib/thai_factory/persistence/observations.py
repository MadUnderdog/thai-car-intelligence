"""
Observation persistence layer.

Stores validated observations to the DB with full provenance.
Preserves history — never overwrites, always appends new observations.
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


def get_or_create_source(domain: str, url: str) -> str:
    """Get or create a Source record. Returns source ID."""
    rows = _psql(f"SELECT id FROM \"Source\" WHERE domain = '{domain}' LIMIT 1")
    if rows:
        return rows[0]

    source_id = str(uuid.uuid4())
    _psql(f"""
        INSERT INTO "Source" (id, "nameTh", "nameEn", "sourceType", "baseUrl", domain, "rightsStatus")
        VALUES ('{source_id}', '{domain}', '{domain}', 'AUTOMOTIVE_MEDIA',
                '{url[:500]}', '{domain}', 'UNKNOWN')
    """, fetch=False)
    return source_id


def create_source_document(source_id: str, url: str, content_hash: str,
                           title: str = "") -> str:
    """Create a SourceDocument record. Returns document ID."""
    doc_id = str(uuid.uuid4())
    title_safe = title.replace("'", "''")[:500] if title else ""
    _psql(f"""
        INSERT INTO "SourceDocument" (id, "sourceId", url, "contentHash",
               "titleEn", "createdAt", "updatedAt")
        VALUES ('{doc_id}', '{source_id}', '{url[:500]}', '{content_hash}',
                '{title_safe}', NOW(), NOW())
    """, fetch=False)
    return doc_id


def resolve_variant(brand: str, model: str) -> Optional[str]:
    """Resolve brand+model to a Variant ID."""
    rows = _psql(f"""
        SELECT v.id
        FROM "Variant" v
        JOIN "CarModel" cm ON v."modelId" = cm.id
        JOIN "Manufacturer" m ON cm."manufacturerId" = m.id
        WHERE LOWER(m.slug) = LOWER('{brand}')
          AND (
            LOWER(cm."nameEn") LIKE '%{model.lower()}%'
            OR LOWER(cm.slug) LIKE '%{model.lower().replace(" ", "-")}%'
            OR LOWER(v."nameEn") LIKE '%{model.lower()}%'
          )
          AND v.status = 'ACTIVE'
        LIMIT 1
    """)
    return rows[0] if rows else None


def persist_observations(observations: List[Observation],
                         dry_run: bool = False) -> Dict[str, int]:
    """
    Persist validated observations to the DB.
    Preserves history — each observation becomes a new DB row.
    Returns persistence stats.
    """
    stats = {
        "prices_inserted": 0,
        "specs_inserted": 0,
        "no_variant": 0,
        "no_source": 0,
        "errors": 0,
    }

    source_cache: Dict[str, str] = {}  # domain -> source_id
    doc_cache: Dict[str, str] = {}  # url -> doc_id
    price_batch = []
    spec_batch = []
    seen_prices: Set[str] = set()  # variantId|amount|sourceDocId

    for obs in observations:
        if obs.persisted:
            continue

        # Resolve variant
        variant_id = resolve_variant(obs.brand, obs.model)
        if not variant_id:
            stats["no_variant"] += 1
            continue

        # Get/create source
        if obs.source_domain not in source_cache:
            if dry_run:
                source_cache[obs.source_domain] = "dry-run-source"
            else:
                source_cache[obs.source_domain] = get_or_create_source(
                    obs.source_domain, obs.source_url
                )
        source_id = source_cache[obs.source_domain]

        # Get/create document
        if obs.source_url not in doc_cache:
            if dry_run:
                doc_cache[obs.source_url] = "dry-run-doc"
            else:
                doc_cache[obs.source_url] = create_source_document(
                    source_id, obs.source_url, obs.content_hash, obs.title
                )
        doc_id = doc_cache[obs.source_url]

        # Persist based on field type
        if obs.field == "price":
            amount = int(obs.normalized_value)
            pt = obs.price_type.value if hasattr(obs.price_type, 'value') else str(obs.price_type)
            if pt not in ("MSRP", "LIST_PRICE", "PROMOTION"):
                pt = "MSRP"

            price_key = f"{variant_id}|{amount}|{doc_id}"
            if price_key in seen_prices:
                continue
            seen_prices.add(price_key)

            price_id = str(uuid.uuid4())
            # Expire existing current price of same type for this variant
            price_batch.append(
                f'UPDATE "Price" SET "isCurrent" = false, "validTo" = NOW() '
                f'WHERE "variantId" = \'{variant_id}\' AND "priceType" = \'{pt}\'::"PriceType" '
                f'AND "isCurrent" = true'
            )
            price_batch.append(
                f'INSERT INTO "Price" (id, "variantId", "sourceDocumentId", "priceType", '
                f'amount, currency, "validFrom", "isCurrent", confidence, "sourceTier", "sourceUrl") '
                f'VALUES (\'{price_id}\', \'{variant_id}\', \'{doc_id}\', \'{pt}\'::"PriceType", '
                f'{amount}, \'THB\', NOW(), true, 0.7, '
                f'\'{obs.source_class.value}\', \'{obs.source_url[:500].replace(chr(39), "")}\')'
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
                except Exception as e:
                    stats["errors"] += 1
            price_batch = []

        if len(spec_batch) >= 50:
            if not dry_run:
                try:
                    _psql("BEGIN; " + "; ".join(spec_batch) + "; COMMIT;", fetch=False)
                except Exception as e:
                    stats["errors"] += 1
            spec_batch = []

    # Flush remaining
    if price_batch and not dry_run:
        try:
            _psql("BEGIN; " + "; ".join(price_batch) + "; COMMIT;", fetch=False)
        except Exception as e:
            stats["errors"] += 1

    if spec_batch and not dry_run:
        try:
            _psql("BEGIN; " + "; ".join(spec_batch) + "; COMMIT;", fetch=False)
        except Exception as e:
            stats["errors"] += 1

    return stats
