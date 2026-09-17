-- Add fuelType to Variant for attribute filtering.
-- Populated by inference from model/variant names. Nullable = unknown.
ALTER TABLE "Variant" ADD COLUMN "fuelType" TEXT;

-- Populate from known patterns
UPDATE "Variant" SET "fuelType" = 'EV'
WHERE "nameEn" ILIKE '%EV %' OR "nameEn" ILIKE '% EV' OR "nameEn" = 'EV'
   OR "nameEn" ILIKE '%EV PLUS%' OR "nameEn" ILIKE '%EV PLUS%'
   OR "nameEn" ILIKE '% Urban%' OR "nameEn" ILIKE '%Urban%'
   OR "nameEn" ILIKE '%MG4%' OR "nameEn" = 'MG4 MY2026'
   OR "nameEn" ILIKE '%Seal %' OR "nameEn" = 'Seal'
   OR "nameEn" ILIKE '%Atto%' OR "nameEn" ILIKE '%Atto%'
   OR "nameEn" ILIKE '%Dolphin%'
   OR "nameEn" ILIKE '%EV6%' OR "nameEn" ILIKE '%EV9%'
   OR "nameEn" ILIKE '%Ionic%' OR "nameEn" ILIKE '%Ioniq%'
   OR "nameEn" ILIKE '%e:NP1%' OR "nameEn" ILIKE '%e:N1%'
   OR "nameEn" ILIKE '%Model 3%' OR "nameEn" ILIKE '%Model Y%';

UPDATE "Variant" SET "fuelType" = 'HEV'
WHERE "nameEn" ILIKE '%HEV%' OR "nameEn" ILIKE '%hybrid%'
   OR "nameEn" ILIKE '%VS HEV%' OR "nameEn" ILIKE '%e:HEV%'
   OR "nameEn" ILIKE '%e-POWER%';

UPDATE "Variant" SET "fuelType" = 'PHEV'
WHERE "nameEn" ILIKE '%PHEV%' OR "nameEn" ILIKE '%DM-i%'
   OR "nameEn" ILIKE '%DM-i%';

-- BYD Sealion 5 DM-i is PHEV, not EV
UPDATE "Variant" SET "fuelType" = 'PHEV'
WHERE "nameEn" ILIKE '%Sealion 5%DM-i%' OR "nameEn" ILIKE '%Sealion 6%DM-i%';

-- BYD Atto/Dolphin/Seal/Sealion 7 are pure EV but names don't have "EV"
-- Fix: check if model name contains known EV indicators
UPDATE "Variant" SET "fuelType" = 'EV'
WHERE "modelId" IN (
  SELECT cm.id FROM "CarModel" cm
  WHERE cm."nameEn" ILIKE '%Atto%' OR cm."nameEn" ILIKE '%Dolphin%'
     OR cm."nameEn" ILIKE '%Seal %' OR cm."nameEn" = 'Seal'
     OR cm."nameEn" ILIKE '%Sealion 7%'
)
AND "fuelType" IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS "Variant_fuelType_idx" ON "Variant" ("fuelType") WHERE "fuelType" IS NOT NULL;
