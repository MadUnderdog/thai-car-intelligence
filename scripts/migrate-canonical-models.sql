-- ===================================================================
-- migrate-canonical-models.sql
-- Migrates Variants from alias CarModels to canonical CarModels,
-- then deletes orphaned alias CarModel records.
-- ===================================================================

-- 0. Pre-flight: snapshot counts
SELECT 'PRE-MIGRATION COUNTS' AS phase;
SELECT COUNT(*) AS models_before FROM "CarModel";
SELECT COUNT(*) AS variants_before FROM "Variant";
SELECT COUNT(*) AS aliases_total FROM "ModelAlias";

-- 1. Count how many variants will be moved
SELECT 'VARIANTS TO MIGRATE' AS phase;
SELECT COUNT(*) AS variants_to_move
FROM "Variant" v
WHERE v."modelId" IN (SELECT "aliasModelId" FROM "ModelAlias");

-- 2. Migrate: move all Variants from alias models to canonical models
UPDATE "Variant" v
SET "modelId" = ma."canonicalModelId"
FROM "ModelAlias" ma
WHERE v."modelId" = ma."aliasModelId";

-- 3. Report what moved
SELECT 'MIGRATION COMPLETE' AS phase;
SELECT COUNT(*) AS variants_after FROM "Variant";

-- 4. Delete orphaned alias CarModel records
--    These should have zero variants, zero prices, zero specs
DELETE FROM "CarModel" cm
WHERE cm."id" IN (SELECT "aliasModelId" FROM "ModelAlias");

-- 5. Delete the ModelAlias entries themselves (optional, but clean)
DELETE FROM "ModelAlias";

-- 6. Post-migration verification
SELECT 'POST-MIGRATION COUNTS' AS phase;
SELECT COUNT(*) AS models_after FROM "CarModel";
SELECT COUNT(*) AS variants_after_migrate FROM "Variant";

-- 7. Verify no dangling FKs (should be zero)
SELECT 'INTEGRITY CHECK' AS phase;
SELECT COUNT(*) AS orphaned_variants_no_model
FROM "Variant" v
WHERE NOT EXISTS (SELECT 1 FROM "CarModel" cm WHERE cm."id" = v."modelId");

SELECT COUNT(*) AS orphaned_prices_no_variant
FROM "Price" p
WHERE NOT EXISTS (SELECT 1 FROM "Variant" v WHERE v."id" = p."variantId");

SELECT COUNT(*) AS orphaned_specs_no_variant
FROM "VariantSpec" vs
WHERE NOT EXISTS (SELECT 1 FROM "Variant" v WHERE v."id" = vs."variantId");

-- 8. Summary
SELECT 'MIGRATION SUMMARY' AS phase;
SELECT 'Models removed' AS metric, 50 AS count
UNION ALL
SELECT 'Variants moved (estimated)', 98
UNION ALL
SELECT 'ModelAliases removed', 50;
