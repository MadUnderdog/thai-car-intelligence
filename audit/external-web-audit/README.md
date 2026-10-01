# External Web Audit — thai-car-intelligence

## Audit Method

This audit captures a **point-in-time snapshot** of the live PostgreSQL database backing the Thai Car Intelligence platform. All data is queried directly from the running `pgvector` container via `docker exec psql`, ensuring no stale or cached representations.

### What is audited

- **Price observations** — real MSRP, LIST_PRICE, and PROMOTION prices from automotive media sources and OEM references
- **Variant specifications** — structured spec key/value pairs with confidence scores, covering Toyota and non-Toyota brands
- **Database totals** — independent counts across all major tables to enable stage reconciliation
- **Pipeline stage flow** — raw candidates → parsed → identity resolved → scope valid → quality passed → deduped → persisted → promoted → quarantined → unresolved

### Sampling methodology

- Price samples: 30 rows, randomly sampled (`ORDER BY RANDOM() LIMIT 30`) from `Price` where `isCurrent=true`
- Spec samples: 30 rows randomly sampled; initial query pulls from all ACTIVE quarantineStatus records, with non-Toyota brands explicitly included to verify cross-brand coverage
- All samples are real persisted data — no synthetic or fabricated records

### Known limitations

1. **Point-in-time only** — data may have changed between this audit timestamp and any subsequent read
2. **Random sampling bias** — `RANDOM()` is PostgreSQL uniform; with small populations, some brands may be over/under-represented
3. **No network verification** — `sourceUrl` values are recorded but not re-fetched; source availability is not re-verified
4. **Quarantine status snapshot** — quarantined specs reflect the state at audit time; re-processing may change status
5. **No cross-table join validation** — referential integrity is assumed via Prisma schema; FK violations are not re-checked here

## Timestamp

- **Audit generated**: 2026-09-21T10:47:31+07:00
- **DB timestamp**: 2026-09-21T03:47:31.330609+00 (UTC)
- **Branch**: `fix/p1-provenance-gate`
- **Commit SHA**: `276afda`

## Database / Schema Version

- **PostgreSQL**: 16.14 (Debian 16.14-1.pgdg124+1)
- **Prisma migrations applied**: 6
- **Last migration**: 2026-09-17T11:30:46.058618+00

## Reproduction Commands

```bash
# 1. Verify DB is running
docker exec pgvector psql -U hermes -d thai_car_intelligence -c "SELECT current_timestamp;"

# 2. Query price samples
docker exec pgvector psql -U hermes -d thai_car_intelligence -A -c \
  'SELECT p.id, p."variantId", p."priceType", p.amount, p."isCurrent", p."sourceTier", p."sourceUrl", v."nameEn" as variant_name, cm."nameEn" as model_name, m."nameEn" as brand_name FROM "Price" p JOIN "Variant" v ON p."variantId"=v.id JOIN "CarModel" cm ON v."modelId"=cm.id JOIN "Manufacturer" m ON cm."manufacturerId"=m.id WHERE p."isCurrent"=true ORDER BY RANDOM() LIMIT 30;'

# 3. Query spec samples
docker exec pgvector psql -U hermes -d thai_car_intelligence -A -c \
  'SELECT vs.id, vs.key, vs."valueEn", vs."valueNumeric", vs.unit, vs.confidence, v."nameEn" as variant_name, cm."nameEn" as model_name, m."nameEn" as brand_name FROM "VariantSpec" vs JOIN "Variant" v ON vs."variantId"=v.id JOIN "CarModel" cm ON v."modelId"=cm.id JOIN "Manufacturer" m ON cm."manufacturerId"=m.id WHERE vs."quarantineStatus"='"'"'ACTIVE'"'"' ORDER BY RANDOM() LIMIT 30;'

# 4. Full table counts
docker exec pgvector psql -U hermes -d thai_car_intelligence -A -c \
  'SELECT (SELECT count(*) FROM "Manufacturer") as manufacturers, (SELECT count(*) FROM "CarModel") as models, (SELECT count(*) FROM "Variant") as variants, (SELECT count(*) FROM "VariantSpec") as variant_specs, (SELECT count(*) FROM "VariantSpec" WHERE "quarantineStatus"='"'"'ACTIVE'"'"') as active_specs, (SELECT count(*) FROM "VariantSpec" WHERE "quarantineStatus"='"'"'QUARANTINED'"'"') as quarantined_specs, (SELECT count(*) FROM "Price" WHERE "isCurrent"=true) as current_prices, (SELECT count(*) FROM "Price") as all_prices, (SELECT count(*) FROM "Source") as sources, (SELECT count(*) FROM "DiscoverySource") as discovery_sources, (SELECT count(*) FROM "ResearchCandidate") as research_candidates, (SELECT count(*) FROM "SourceDocument") as source_documents, (SELECT count(*) FROM "VehicleUniverse") as vehicle_universe, (SELECT count(*) FROM "VariantFeature") as variant_features;'

# 5. Run local invariant checks (no network required)
python3 audit/external-web-audit/reproduce_audit.py
```
