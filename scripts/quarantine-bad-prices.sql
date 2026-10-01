-- =============================================================================
-- Quarantine Bad Prices Migration
-- =============================================================================
-- Purpose: Add quarantine columns to Price table and mark contaminated/stale rows
-- Date: 2026-09-20
-- Database: thai_car_intelligence (pgvector)
-- =============================================================================

-- 1. ADD QUARANTINE COLUMNS
-- =============================================================================
ALTER TABLE "Price" ADD COLUMN IF NOT EXISTS "quarantineReason" TEXT DEFAULT NULL;
ALTER TABLE "Price" ADD COLUMN IF NOT EXISTS "quarantineStatus" TEXT DEFAULT 'ACTIVE';

-- 2. QUARANTINE: GR Corolla → Corolla Altis contamination
-- =============================================================================
-- The GR Corolla (GR Yaris/Corolla sport model) price was incorrectly linked to
-- Corolla Altis. Source document URL contains series_code=grcorolla but the price
-- is associated with Corolla Altis model variants.
--
-- Confirmed bad rows: 5 rows with amount=4199000 THB, variant HEV, model Corolla Altis
-- where sourceDocument URL = 'https://www.toyota.co.th/en/model/api/car/?series_code=grcorolla'
UPDATE "Price"
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'Cross-model contamination: GR Corolla (series_code=grcorolla) incorrectly linked to Corolla Altis model. Amount 4199000 THB is GR Corolla GR Sport pricing, not Corolla Altis.'
FROM "Variant" v
JOIN "CarModel" cm ON v."modelId" = cm.id
JOIN "SourceDocument" sd ON "Price"."sourceDocumentId" = sd.id
WHERE "Price"."variantId" = v.id
  AND cm."nameEn" = 'Corolla Altis'
  AND v."nameEn" = 'HEV'
  AND "Price".amount = 4199000
  AND sd.url LIKE '%series_code=grcorolla%';

-- 3. QUARANTINE: Cross-model contamination (series_code ≠ model name)
-- =============================================================================
-- Mark any prices where the Toyota API source URL series_code doesn't match
-- the associated CarModel name. This catches ingestion errors where prices
-- from one model's API endpoint were incorrectly linked to a different model.
--
-- Mapping logic:
--   series_code=gryaris      → should map to GR Yaris (not regular Yaris)
--   series_code=grcorolla    → should map to GR Corolla (not Corolla Altis)
--   series_code=yarisativ    → should map to Yaris ATIV/Ativ variants
--   series_code=yaris        → should map to Yaris (not Yaris Ativ/ATIV/Cross)
--   series_code=yariscross   → should map to Yaris Cross
--   series_code=corollacross → should map to Corolla Cross
--   series_code=altis        → should map to Corolla Altis
--   series_code=camry        → should map to Camry
--   series_code=fortuner_*   → should map to Fortuner
--   series_code=hilux_*      → should map to Hilux
--   series_code=innovazenix  → should map to Innova Zenix
--   series_code=veloz        → should map to Veloz
--   series_code=bz4x         → should map to bZ4X

UPDATE "Price"
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'Cross-model contamination: series_code='
      || regexp_replace(sd.url, '.*series_code=([^&]+).*', '\1')
      || ' does not match model ' || cm."nameEn"
      || ' (variant: ' || v."nameEn" || ', amount: ' || "Price".amount || ' THB)'
FROM "Variant" v
JOIN "CarModel" cm ON v."modelId" = cm.id
JOIN "SourceDocument" sd ON "Price"."sourceDocumentId" = sd.id
WHERE "Price"."variantId" = v.id
  AND sd.url LIKE '%toyota.co.th/en/model/api/car/?series_code=%'
  AND "Price"."quarantineStatus" IS NULL  -- Only process unquarantined rows
  AND (
    -- gryaris series_code should NOT match regular Yaris model
    (sd.url LIKE '%series_code=gryaris%' AND cm."nameEn" NOT ILIKE '%gr%yaris%')
    -- grcorolla series_code should NOT match Corolla Altis model
    OR (sd.url LIKE '%series_code=grcorolla%' AND cm."nameEn" NOT ILIKE '%gr%corolla%')
    -- yarisativ should only match Yaris Ativ/ATIV variants
    OR (sd.url LIKE '%series_code=yarisativ[_]%'  -- sub-variants like yarisativ_grsport
        AND cm."nameEn" NOT ILIKE '%yaris%')
    OR (sd.url LIKE '%series_code=yarisativ'  -- exact yarisativ (ends at ? or &)
        AND cm."nameEn" NOT ILIKE '%yaris%')
    -- yaris series_code should match Yaris but not Yaris Ativ/ATIV/Cross
    OR (sd.url LIKE '%series_code=yaris[_]%'  -- ends with yaris_ or yaris&
        AND cm."nameEn" NOT ILIKE '%yaris%')
    OR (sd.url LIKE '%series_code=yaris'  -- exact yaris
        AND cm."nameEn" NOT ILIKE '%yaris%')
    -- yariscross should match Yaris Cross
    OR (sd.url LIKE '%series_code=yariscross%'
        AND cm."nameEn" NOT ILIKE '%yaris%cross%')
    -- corollacross should match Corolla Cross
    OR (sd.url LIKE '%series_code=corollacross%'
        AND cm."nameEn" NOT ILIKE '%corolla%cross%')
    -- altis should match Corolla Altis
    OR (sd.url LIKE '%series_code=altis%'
        AND cm."nameEn" NOT ILIKE '%corolla%altis%')
    -- camry should match Camry
    OR (sd.url LIKE '%series_code=camry%'
        AND cm."nameEn" NOT ILIKE '%camry%')
    -- fortuner variants should match Fortuner
    OR (sd.url LIKE '%series_code=fortuner%'
        AND cm."nameEn" NOT ILIKE '%fortuner%')
    -- hilux variants should match Hilux
    OR (sd.url LIKE '%series_code=hilux%'
        AND cm."nameEn" NOT ILIKE '%hilux%')
    -- innovazenix should match Innova Zenix
    OR (sd.url LIKE '%series_code=innovazenix%'
        AND cm."nameEn" NOT ILIKE '%innova%zenix%')
    -- veloz should match Veloz
    OR (sd.url LIKE '%series_code=veloz%'
        AND cm."nameEn" NOT ILIKE '%veloz%')
    -- bz4x should match bZ4X
    OR (sd.url LIKE '%series_code=bz4x%'
        AND cm."nameEn" NOT ILIKE '%bz4x%')
  );

-- 4. QUARANTINE: Stale current prices
-- =============================================================================
-- Mark prices where isCurrent=true but validTo is not null and validTo < now().
-- These are prices that were marked as current but have an expiry date in the
-- past, indicating they should have been superseded by newer prices.
UPDATE "Price"
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'Stale current price: isCurrent=true but validTo='
      || "Price"."validTo" || ' (expired '
      || EXTRACT(DAY FROM now() - "Price"."validTo") || ' days ago)'
WHERE "Price"."isCurrent" = true
  AND "Price"."validTo" IS NOT NULL
  AND "Price"."validTo" < now()
  AND "Price"."quarantineStatus" IS NULL;

-- 5. LOG CHANGES TO DataChangeLog
-- =============================================================================
-- Record all quarantine actions in the DataChangeLog for audit trail
INSERT INTO "DataChangeLog" (
  "entityType",
  "entityId",
  "fieldName",
  "changeType",
  "beforeValue",
  "afterValue",
  "reason",
  "confidence",
  "proposed",
  "applied"
)
SELECT
  'Price',
  p.id,
  'quarantineStatus',
  'UPDATED',
  jsonb_build_object('quarantineStatus', NULL, 'quarantineReason', NULL),
  jsonb_build_object('quarantineStatus', p."quarantineStatus", 'quarantineReason', p."quarantineReason"),
  'Automated quarantine: ' || p."quarantineReason",
  0.95,
  false,
  true
FROM "Price" p
WHERE p."quarantineStatus" = 'QUARANTINED'
  AND p."quarantineReason" IS NOT NULL;

-- 6. VERIFICATION QUERIES (read-only, for manual review)
-- =============================================================================

-- 6a. Summary of quarantined prices
SELECT
  "quarantineReason",
  COUNT(*) as row_count,
  SUM(amount) as total_amount_thb
FROM "Price"
WHERE "quarantineStatus" = 'QUARANTINED'
GROUP BY "quarantineReason"
ORDER BY row_count DESC;

-- 6b. All quarantined prices with details
SELECT
  p.id,
  p.amount,
  p."isCurrent",
  p."validTo",
  v."nameEn" as variant_name,
  cm."nameEn" as model_name,
  sd.url as source_url,
  p."quarantineStatus",
  p."quarantineReason"
FROM "Price" p
JOIN "Variant" v ON p."variantId" = v.id
JOIN "CarModel" cm ON v."modelId" = cm.id
LEFT JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd.id
WHERE p."quarantineStatus" = 'QUARANTINED'
ORDER BY p.amount DESC;

-- 6c. Count of active vs quarantined prices
SELECT
  "quarantineStatus",
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM "Price"
GROUP BY "quarantineStatus"
ORDER BY "quarantineStatus";
