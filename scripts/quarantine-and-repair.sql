-- ============================================================================
-- Quarantine & Repair Migration
-- Thai Car Intelligence — 2026-09-20
--
-- Strategy: quarantine only, never delete. Each block is idempotent.
-- NOTE: Price.sourceUrl is always NULL; URL lives on SourceDocument.url.
--       All URL checks on Price must join through sourceDocumentId.
-- ============================================================================

BEGIN;

-- ==========================================================================
-- 1. SCHEMA CHANGES
-- ==========================================================================

-- 1a. Add quarantine columns to Price
ALTER TABLE "Price"
  ADD COLUMN IF NOT EXISTS "quarantineReason" text DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS "quarantineStatus"  text DEFAULT 'ACTIVE';

COMMENT ON COLUMN "Price"."quarantineReason" IS 'Free-text reason why this price row is quarantined. NULL = not quarantined.';
COMMENT ON COLUMN "Price"."quarantineStatus"  IS 'ACTIVE = row is usable. QUARANTINED = row is excluded from queries.';

-- 1b. Add quarantine columns to VariantSpec
ALTER TABLE "VariantSpec"
  ADD COLUMN IF NOT EXISTS "quarantineReason" text DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS "quarantineStatus"  text DEFAULT 'ACTIVE';

COMMENT ON COLUMN "VariantSpec"."quarantineReason" IS 'Free-text reason why this spec row is quarantined.';
COMMENT ON COLUMN "VariantSpec"."quarantineStatus"  IS 'ACTIVE = row is usable. QUARANTINED = row is excluded from queries.';

-- 1c. Create ModelAlias table for canonical <-> alias mapping
CREATE TABLE IF NOT EXISTS "ModelAlias" (
  "id"          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  "canonicalId" uuid NOT NULL REFERENCES "CarModel"(id) ON DELETE CASCADE,
  "aliasId"     uuid NOT NULL REFERENCES "CarModel"(id) ON DELETE CASCADE,
  "reason"      text,
  "createdAt"   timestamptz NOT NULL DEFAULT now(),
  "updatedAt"   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT "ModelAlias_no_self_ref" CHECK ("canonicalId" <> "aliasId"),
  CONSTRAINT "ModelAlias_unique_pair" UNIQUE ("canonicalId", "aliasId")
);

COMMENT ON TABLE  "ModelAlias"  IS 'Maps duplicate CarModel rows: canonicalId is the survivor with more variants, aliasId is the deprecated twin.';
COMMENT ON COLUMN "ModelAlias"."canonicalId" IS 'CarModel with more variants — the canonical/primary record.';
COMMENT ON COLUMN "ModelAlias"."aliasId"     IS 'CarModel with fewer variants — to be migrated away from.';

CREATE INDEX IF NOT EXISTS "ModelAlias_canonicalId_idx" ON "ModelAlias" ("canonicalId");
CREATE INDEX IF NOT EXISTS "ModelAlias_aliasId_idx"     ON "ModelAlias" ("aliasId");


-- ==========================================================================
-- 2. QUARANTINE KNOWN-BAD PRICES
-- ==========================================================================

-- 2a. GR Corolla misattribution
--     Price sourced from toyota.co.th API with series_code=grcorolla
--     but assigned to Corolla Altis HEV variant.
--     URL is on SourceDocument, NOT on Price.sourceUrl.
UPDATE "Price" p
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'GR Corolla misattribution: sourceDocument URL series_code=grcorolla but price assigned to Corolla Altis HEV variant. GR Corolla (E210 GR) is a distinct performance model from Corolla Altis.'
FROM "SourceDocument" sd
JOIN "Variant" v ON v.id = p."variantId"
JOIN "CarModel" cm ON cm.id = v."modelId"
WHERE p."sourceDocumentId" = sd.id
  AND sd.url LIKE '%series_code=grcorolla%'
  AND cm."nameEn" = 'Corolla Altis'
  AND p."quarantineStatus" = 'ACTIVE';

-- 2b. Quarantine TCO calculator prices of 4,199,000 THB for Corolla Altis
--     The Toyota TCO API returned GR Corolla pricing embedded in the
--     Corolla Altis model response. These 4 rows (amount=4199000 from
--     toyota.co.th/component/api/tcoth/web-init for Corolla Altis) are
--     GR Corolla MSRP contamination.
UPDATE "Price" p
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'TCO API contamination: 4,199,000 THB TCO calculator price for Corolla Altis HEV matches GR Corolla MSRP. Toyota TCO API returned cross-model pricing.'
FROM "Variant" v
JOIN "CarModel" cm ON cm.id = v."modelId"
WHERE p."variantId" = v.id
  AND p.amount = 4199000
  AND cm."nameEn" = 'Corolla Altis'
  AND p."quarantineStatus" = 'ACTIVE';

-- 2c. Generic series_code -> model mismatch quarantine
--     Quarantine any Price whose sourceDocument URL has series_code=X
--     but the assigned model's slug does not contain X (case-insensitive).
--     Catches future misattributions from the Toyota API.
UPDATE "Price" p
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'series_code mismatch: sourceDocument URL contains series_code='
      || (regexp_match(sd.url, 'series_code=([^&]+)'))[1]
      || ' but model slug is ' || cm.slug || ' — cross-model attribution error.'
FROM "SourceDocument" sd
JOIN "Variant" v ON v.id = p."variantId"
JOIN "CarModel" cm ON cm.id = v."modelId"
WHERE p."sourceDocumentId" = sd.id
  AND sd.url ~ 'series_code=[^&]+'
  AND p."quarantineStatus" = 'ACTIVE'
  AND LOWER(cm.slug) NOT LIKE '%'
       || LOWER(REPLACE((regexp_match(sd.url, 'series_code=([^&]+)'))[1], '_', '%'))
       || '%';


-- ==========================================================================
-- 3. QUARANTINE CROSS-BRAND / CROSS-MODEL VARIANTSPECS
-- ==========================================================================

-- 3a. headlightmag BYD Seal 6 document specs assigned to non-BYD models
--     Article: "official-price-byd-seal-6-2026" compares BYD Seal 6 against
--     competitors. Specs were mistakenly ingested into 43 models across
--     Honda, MG, Toyota, BYD. Only BYD Seal variants should retain specs.
UPDATE "VariantSpec" vs
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'Cross-brand contamination: specs sourced from BYD Seal 6 article (headlightmag.com/official-price-byd-seal-6-2026) but applied to '
      || m."nameEn" || ' ' || cm."nameEn"
      || '. Article is BYD Seal 6-specific; competitor data is comparison context, not spec provenance.'
FROM "SourceDocument" sd
JOIN "Variant" v ON v.id = vs."variantId"
JOIN "CarModel" cm ON cm.id = v."modelId"
JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
WHERE vs."sourceDocumentId" = sd.id
  AND sd.url = 'https://www.headlightmag.com/official-price-byd-seal-6-2026/'
  AND m."nameEn" != 'BYD';

-- 3b. headlightmag MG4 document specs assigned to non-MG4 models
--     Article: "official-price-mg4-my2026-2" cross-references BYD ATTO 2.
--     Only MG4 variants should retain specs from this MG4-focused document.
UPDATE "VariantSpec" vs
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'Cross-brand contamination: specs sourced from MG4 article (headlightmag.com/official-price-mg4-my2026-2) but applied to '
      || m."nameEn" || ' ' || cm."nameEn"
      || '. Article is MG4-specific.'
FROM "SourceDocument" sd
JOIN "Variant" v ON v.id = vs."variantId"
JOIN "CarModel" cm ON cm.id = v."modelId"
JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
WHERE vs."sourceDocumentId" = sd.id
  AND sd.url = 'https://www.headlightmag.com/official-price-mg4-my2026-2/'
  AND cm."nameEn" != 'MG4'
  AND vs."quarantineStatus" = 'ACTIVE';

-- 3c. Generic cross-manufacturer spec contamination
--     Quarantine VariantSpecs where the SourceDocument URL contains a
--     manufacturer brand indicator that doesn't match the model's manufacturer.
--     Example: Honda specs sourced from a BYD page URL, BYD specs from Zeekr.
--     Skips the two known comparison articles handled above.
UPDATE "VariantSpec" vs
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'Cross-brand URL mismatch: sourceDocument URL contains brand indicator for '
      || detected_brand || ' but model belongs to manufacturer '
      || m."nameEn" || ' (' || cm."nameEn" || '). Likely cross-brand spec contamination.'
FROM "SourceDocument" sd
JOIN "Variant" v ON v.id = vs."variantId"
JOIN "CarModel" cm ON cm.id = v."modelId"
JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
CROSS JOIN LATERAL (
  SELECT CASE
    WHEN sd.url ~* '(^|[-_/])honda([-_/]|$)' THEN 'Honda'
    WHEN sd.url ~* '(^|[-_/])toyota([-_/]|$)' THEN 'Toyota'
    WHEN sd.url ~* '(^|[-_/])byd([-_/]|$)' THEN 'BYD'
    WHEN sd.url ~* '(^|[-_/])mg[-_]([-_/]|$)' THEN 'MG'
    WHEN sd.url ~* '(^|[-_/])zeekr([-_/]|$)' THEN 'Zeekr'
    WHEN sd.url ~* '(^|[-_/])hyundai([-_/]|$)' THEN 'Hyundai'
    WHEN sd.url ~* '(^|[-_/])nissan([-_/]|$)' THEN 'Nissan'
    WHEN sd.url ~* '(^|[-_/])mazda([-_/]|$)' THEN 'Mazda'
    WHEN sd.url ~* '(^|[-_/])subaru([-_/]|$)' THEN 'Subaru'
    WHEN sd.url ~* '(^|[-_/])tesla([-_/]|$)' THEN 'Tesla'
    WHEN sd.url ~* '(^|[-_/])geely([-_/]|$)' THEN 'Geely'
    WHEN sd.url ~* '(^|[-_/])gwm([-_/]|$)' THEN 'GWM'
    WHEN sd.url ~* '(^|[-_/])denza([-_/]|$)' THEN 'Denza'
    WHEN sd.url ~* '(^|[-_/])xpeng([-_/]|$)' THEN 'Xpeng'
    WHEN sd.url ~* '(^|[-_/])nio([-_/]|$)' THEN 'NIO'
    WHEN sd.url ~* '(^|[-_/])avatr([-_/]|$)' THEN 'Avatr'
    WHEN sd.url ~* '(^|[-_/])changan([-_/]|$)' THEN 'Changan'
    WHEN sd.url ~* '(^|[-_/])suzuki([-_/]|$)' THEN 'Suzuki'
    WHEN sd.url ~* '(^|[-_/])mg([-_/]|$)' THEN 'MG'
    ELSE NULL
  END AS detected_brand
) AS brand
WHERE vs."sourceDocumentId" = sd.id
  AND brand.detected_brand IS NOT NULL
  AND brand.detected_brand != m."nameEn"
  AND vs."quarantineStatus" = 'ACTIVE'
  -- Skip the two known cross-brand comparison articles above
  AND sd.url NOT LIKE '%official-price-byd-seal-6-2026%'
  AND sd.url NOT LIKE '%official-price-mg4-my2026-2%';


-- ==========================================================================
-- 4. CANONICAL MODEL ALIAS MIGRATION
-- ==========================================================================
-- For each pair of duplicate CarModel rows (same nameEn + same manufacturerId),
-- designate the one with more variants as canonical. When tied, prefer the
-- slug without a brand prefix (e.g. 'yaris' over 'toyota-yaris').

INSERT INTO "ModelAlias" ("canonicalId", "aliasId", "reason")
SELECT
  canonical.id AS "canonicalId",
  alias.id     AS "aliasId",
  'Duplicate model: both named ''' || canonical."nameEn" || ''' under '
    || m."nameEn" || '. Canonical chosen by variant count ('
    || canonical.variant_count || ' vs ' || alias.variant_count || ').'
    || CASE WHEN canonical.variant_count = alias.variant_count
            THEN ' Tied — canonical preferred by shorter slug (no brand prefix).'
            ELSE ''
       END
  AS reason
FROM (
  -- Rank models within each (nameEn, manufacturerId) group
  SELECT cm.id, cm."nameEn", cm."manufacturerId", cm.slug,
    COUNT(DISTINCT v.id) AS variant_count,
    ROW_NUMBER() OVER (
      PARTITION BY cm."nameEn", cm."manufacturerId"
      ORDER BY COUNT(DISTINCT v.id) DESC,   -- more variants = higher rank
               LENGTH(cm.slug) ASC,          -- shorter slug preferred when tied
               cm.slug ASC                   -- lexicographic tiebreak
    ) AS rank
  FROM "CarModel" cm
  LEFT JOIN "Variant" v ON v."modelId" = cm.id
  GROUP BY cm.id, cm."nameEn", cm."manufacturerId", cm.slug
) AS canonical
JOIN (
  SELECT cm.id, cm."nameEn", cm."manufacturerId", cm.slug,
    COUNT(DISTINCT v.id) AS variant_count,
    ROW_NUMBER() OVER (
      PARTITION BY cm."nameEn", cm."manufacturerId"
      ORDER BY COUNT(DISTINCT v.id) DESC,
               LENGTH(cm.slug) ASC,
               cm.slug ASC
    ) AS rank
  FROM "CarModel" cm
  LEFT JOIN "Variant" v ON v."modelId" = cm.id
  GROUP BY cm.id, cm."nameEn", cm."manufacturerId", cm.slug
) AS alias
  ON alias."nameEn" = canonical."nameEn"
  AND alias."manufacturerId" = canonical."manufacturerId"
  AND alias.rank = canonical.rank + 1
JOIN "Manufacturer" m ON m.id = canonical."manufacturerId"
WHERE canonical.rank = 1  -- Only the top-ranked (canonical) row
  -- Only create entries for actual duplicates (groups with >1 row)
  AND EXISTS (
    SELECT 1 FROM "CarModel" cm2
    WHERE cm2."nameEn" = canonical."nameEn"
      AND cm2."manufacturerId" = canonical."manufacturerId"
    GROUP BY cm2."nameEn", cm2."manufacturerId"
    HAVING COUNT(*) > 1
  )
ON CONFLICT ("canonicalId", "aliasId") DO NOTHING;


-- ==========================================================================
-- 5. VERIFICATION QUERIES
-- ==========================================================================

-- Summary counts
SELECT 'prices_quarantined' AS metric, COUNT(*) AS val
FROM "Price" WHERE "quarantineStatus" = 'QUARANTINED'
UNION ALL
SELECT 'prices_active', COUNT(*) FROM "Price" WHERE "quarantineStatus" = 'ACTIVE'
UNION ALL
SELECT 'specs_quarantined', COUNT(*) FROM "VariantSpec" WHERE "quarantineStatus" = 'QUARANTINED'
UNION ALL
SELECT 'specs_active', COUNT(*) FROM "VariantSpec" WHERE "quarantineStatus" = 'ACTIVE'
UNION ALL
SELECT 'model_aliases_created', COUNT(*) FROM "ModelAlias"
ORDER BY metric;

-- Detailed view: quarantined prices
-- SELECT p.id, p.amount, p."priceType", p."quarantineReason",
--        v."nameEn" AS variant, cm."nameEn" AS model, sd.url AS source_url
-- FROM "Price" p
-- JOIN "Variant" v ON v.id = p."variantId"
-- JOIN "CarModel" cm ON cm.id = v."modelId"
-- LEFT JOIN "SourceDocument" sd ON sd.id = p."sourceDocumentId"
-- WHERE p."quarantineStatus" = 'QUARANTINED';

-- Detailed view: quarantined specs
-- SELECT vs.id, vs.key, vs."quarantineReason",
--        v."nameEn" AS variant, cm."nameEn" AS model, sd.url AS source_url
-- FROM "VariantSpec" vs
-- JOIN "Variant" v ON v.id = vs."variantId"
-- JOIN "CarModel" cm ON cm.id = v."modelId"
-- LEFT JOIN "SourceDocument" sd ON sd.id = vs."sourceDocumentId"
-- WHERE vs."quarantineStatus" = 'QUARANTINED';

-- Detailed view: model aliases
-- SELECT ma."canonicalId", cm_c."nameEn" AS canonical, cm_c.slug AS canonical_slug,
--        ma."aliasId", cm_a."nameEn" AS alias, cm_a.slug AS alias_slug, ma.reason
-- FROM "ModelAlias" ma
-- JOIN "CarModel" cm_c ON cm_c.id = ma."canonicalId"
-- JOIN "CarModel" cm_a ON cm_a.id = ma."aliasId"
-- ORDER BY cm_c."nameEn";

COMMIT;
