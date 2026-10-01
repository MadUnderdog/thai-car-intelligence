-- Quarantine Headlightmag Cross-Model Contamination
-- ==================================================
-- Root cause: The Headlightmag extractor's generic price/spec regex patterns
-- (Patterns 2, 4, and all spec patterns) matched text about ANY model in the
-- article without verifying the match was about the article's subject model.
-- Automotive articles frequently mention competitor models for comparison,
-- so a BYD Seal 6 article's specs got attributed to 43 different models.
--
-- This migration:
-- 1. Adds status/quarantineReason columns to VariantSpec
-- 2. Marks contaminated rows where the sourceDocument URL doesn't match
--    the variant's model name as QUARANTINED with reason
--    'cross-model contamination'

-- Step 1: Add quarantine columns to VariantSpec
ALTER TABLE "VariantSpec" ADD COLUMN IF NOT EXISTS "status" TEXT DEFAULT NULL;
ALTER TABLE "VariantSpec" ADD COLUMN IF NOT EXISTS "quarantineReason" TEXT DEFAULT NULL;

-- Step 2: Mark contaminated VariantSpec rows
-- A row is "contaminated" if:
--   - Its sourceDocument URL is from headlightmag.com
--   - The variant's model name (from CarModel.nameEn) does NOT appear
--     in the sourceDocument URL slug (case-insensitive)
-- This catches the cross-model contamination where specs from competitor
-- models mentioned in the article were incorrectly attributed.
WITH contaminated AS (
  SELECT vs.id AS vs_id
  FROM "VariantSpec" vs
  JOIN "Variant" v ON vs."variantId" = v.id
  JOIN "CarModel" cm ON v."modelId" = cm.id
  JOIN "SourceDocument" sd ON vs."sourceDocumentId" = sd.id
  WHERE sd.url LIKE '%headlightmag%'
    AND vs."status" IS NULL
    AND NOT (
      LOWER(cm."nameEn") IN (
        SELECT LOWER(word)
        FROM unnest(
          string_to_array(
            regexp_replace(
              regexp_replace(sd.url, 'https?://[^/]+/', ''),
              '[^a-z0-9 ]', ' ', 'gi'
            ),
            ' '
          )
        ) AS word
        WHERE length(word) > 2
      )
    )
)
UPDATE "VariantSpec"
SET "status" = 'QUARANTINED',
    "quarantineReason" = 'cross-model contamination'
WHERE id IN (SELECT vs_id FROM contaminated);

-- Step 3: Show summary of quarantined rows
SELECT
  cm."nameEn" AS model_name,
  m."nameEn" AS brand_name,
  sd.url AS source_url,
  COUNT(*) AS contaminated_spec_count
FROM "VariantSpec" vs
JOIN "Variant" v ON vs."variantId" = v.id
JOIN "CarModel" cm ON v."modelId" = cm.id
JOIN "Manufacturer" m ON cm."manufacturerId" = m.id
JOIN "SourceDocument" sd ON vs."sourceDocumentId" = sd.id
WHERE vs."status" = 'QUARANTINED'
  AND vs."quarantineReason" = 'cross-model contamination'
GROUP BY cm."nameEn", m."nameEn", sd.url
ORDER BY contaminated_spec_count DESC;

-- Step 4: Show total counts
SELECT
  COUNT(*) AS total_headlightmag_specs,
  COUNT(*) FILTER (WHERE vs."status" = 'QUARANTINED') AS quarantined_specs,
  COUNT(*) FILTER (WHERE vs."status" IS NULL) AS clean_specs
FROM "VariantSpec" vs
JOIN "SourceDocument" sd ON vs."sourceDocumentId" = sd.id
WHERE sd.url LIKE '%headlightmag%';
