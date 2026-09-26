"""
Observation persistence layer — append-only with canonical projection.

Architecture:
1. Observations write to Observation table (append-only, fingerprint unique)
2. Canonical projection (Price/VariantSpec) happens only for APPROVED observations
3. Current price comes from source semantics, not NOW()
4. Identity/scope decisions stored with observation
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
    """Get or create a Source record."""
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
    """Deterministic upsert of SourceDocument by URL + contentHash."""
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


def compute_fingerprint(obs: Observation) -> str:
    """Compute deterministic fingerprint for idempotency."""
    pt = obs.price_type.value if hasattr(obs.price_type, 'value') else str(obs.price_type)
    fp_raw = f"{obs.source_domain}|{obs.source_url}|{obs.brand}|{obs.model}|{obs.variant}|{obs.field}|{obs.normalized_value}|{pt}"
    return hashlib.sha256(fp_raw.encode()).hexdigest()


def resolve_variant_exact(brand: str, model: str, variant: str = "") -> Optional[str]:
    """
    Resolve brand+model+variant to a Variant ID.
    Exact match only. Returns None if no exact match or multiple variants without variant specified.
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
            return rows[0][0]
        else:
            # Multiple variants — return None (MODEL_LEVEL / NEEDS_REVIEW)
            return None

    return None


def persist_observations(observations: List[Observation],
                         dry_run: bool = False) -> Dict[str, int]:
    """
    Phase 1: Write observations to Observation table (append-only).
    Phase 2: Promote approved observations to canonical (Price/VariantSpec).

    FIXES:
    - Observation table enforces fingerprint uniqueness (idempotent reruns)
    - Current price determined from source semantics, not NOW()
    - Promotion/historical never become unconditional current MSRP
    - Identity/scope decisions stored with observation
    """
    stats = {
        "observations_inserted": 0,
        "observations_skipped": 0,
        "canonical_promoted": 0,
        "no_variant": 0,
        "errors": 0,
    }

    source_cache: Dict[str, str] = {}
    doc_cache: Dict[str, str] = {}

    for obs in observations:
        if obs.persisted:
            continue

        # Compute fingerprint
        fingerprint = compute_fingerprint(obs)

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

        # Get/create document
        if obs.source_url not in doc_cache:
            if dry_run:
                doc_cache[obs.source_url] = "dry-run-doc"
            else:
                doc_cache[obs.source_url] = get_or_create_source_document(
                    source_id, obs.source_url, obs.content_hash, obs.title
                )
        doc_id = doc_cache[obs.source_url]

        # Phase 1: Write to Observation table (append-only)
        obs_id = str(uuid.uuid4())
        source_class_str = obs.source_class.value if hasattr(obs.source_class, 'value') else str(obs.source_class)
        trust_str = obs.trust_state.value if hasattr(obs.trust_state, 'value') else str(obs.trust_state)
        pt = obs.price_type.value if hasattr(obs.price_type, 'value') else str(obs.price_type)
        excerpt_safe = obs.evidence_excerpt.replace("'", "''")[:500] if obs.evidence_excerpt else ""
        brand_safe = (obs.brand or "").replace("'", "''")
        model_safe = (obs.model or "").replace("'", "''")
        variant_safe = (obs.variant or "").replace("'", "''")

        obs_sql = f"""
            INSERT INTO "Observation" (
                id, "sourceDocumentId", "sourceUrl", "sourceDomain", "sourceClass",
                "trustState", "verificationState",
                "identityDecision", "identityReason",
                "scopeDecision", "scopeReason",
                field, "rawValue", "normalizedValue", unit, "priceType",
                brand, model, variant,
                "evidenceExcerpt", "contentHash", fingerprint,
                "observedAt", "publishedAt", confidence, "scopeState"
            ) VALUES (
                '{obs_id}', '{doc_id}', '{obs.source_url[:500].replace("'", "''")}',
                '{obs.source_domain}', '{source_class_str}',
                '{trust_str}', 'NOT_OFFICIAL',
                '{getattr(obs, "identity_decision", "UNRESOLVED")}',
                '{getattr(obs, "identity_reason", "")}',
                '{getattr(obs, "scope_decision", "UNRESOLVED")}',
                '{getattr(obs, "scope_reason", "")}',
                '{obs.field[:100].replace("'", "''")}',
                '{(obs.raw_value or "").replace("'", "''")[:500]}',
                '{(obs.normalized_value or "").replace("'", "''")[:500]}',
                '{(obs.unit or "")}',
                '{pt}',
                '{brand_safe}', '{model_safe}', '{variant_safe}',
                '{excerpt_safe}',
                '{obs.content_hash}',
                '{fingerprint}',
                '{obs.published_date or obs.observed_at or datetime.now(timezone.utc).isoformat()}',
                '{obs.published_date or ""}',
                {obs.confidence},
                '{obs.scope_state or "UNRESOLVED"}'
            ) ON CONFLICT (fingerprint) DO NOTHING
        """

        if not dry_run:
            try:
                _psql(obs_sql, fetch=False)
                stats["observations_inserted"] += 1
            except Exception as e:
                stats["errors"] += 1
                continue
        else:
            stats["observations_inserted"] += 1

        # Phase 2: Promote to canonical (only MSRP/LIST_PRICE for prices, all specs)
        variant_id = resolve_variant_exact(obs.brand, obs.model, obs.variant)
        if not variant_id:
            stats["no_variant"] += 1
            continue

        # Only promote approved price types
        if obs.field == "price":
            if pt not in ("MSRP", "LIST_PRICE"):
                continue  # Don't promote PROMOTION/MODEL_RANGE/HISTORICAL to current
            amount = int(obs.normalized_value)
            # FIX: isCurrent based on source semantics
            is_current = pt == "MSRP"  # Only MSRP is unconditionally current
            price_id = str(uuid.uuid4())
            valid_from = obs.published_date.replace("'", "") if obs.published_date else "NOW()"
            if not dry_run:
                try:
                    _psql(f"""
                        INSERT INTO "Price" (id, "variantId", "sourceDocumentId", "priceType",
                            amount, currency, "validFrom", "isCurrent", confidence, "sourceTier", "sourceUrl")
                        VALUES ('{price_id}', '{variant_id}', '{doc_id}', '{pt}'::"PriceType",
                            {amount}, 'THB', '{valid_from}', {is_current}, 0.7,
                            '{source_class_str}', '{obs.source_url[:500].replace("'", "")}')
                    """, fetch=False)
                    stats["canonical_promoted"] += 1
                except Exception:
                    stats["errors"] += 1
        else:
            key = obs.field[:100].replace("'", "''")
            val = (obs.normalized_value or "").replace("'", "''")[:500]
            unit_val = f"'{obs.unit}'" if obs.unit else "NULL"
            numeric_val = "NULL"
            try:
                numeric_val = str(float(obs.normalized_value))
            except (ValueError, TypeError):
                pass
            spec_id = str(uuid.uuid4())
            if not dry_run:
                try:
                    _psql(f"""
                        INSERT INTO "VariantSpec" (id, "variantId", "sourceDocumentId", key,
                            "valueTh", "valueEn", "valueNumeric", unit, confidence)
                        VALUES ('{spec_id}', '{variant_id}', '{doc_id}', '{key}',
                            '{val}', '{val}', {numeric_val}, {unit_val}, 0.7)
                        ON CONFLICT ("variantId", key, "sourceDocumentId") DO NOTHING
                    """, fetch=False)
                    stats["canonical_promoted"] += 1
                except Exception:
                    stats["errors"] += 1

    return stats
