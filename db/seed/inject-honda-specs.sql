-- Honda City specs (2026 Thailand, from zigwheels.co.th + paultan.org)
-- Official Thai prices and specs

-- Honda City S (1.0L Turbo)
INSERT INTO "PerformanceSpec" (id,"variantId","powerKw","torqueNm","sourceTier","sourceType","sourceUrl","verifiedAt")
SELECT gen_random_uuid(), v.id, 88.0, 173.0, 'reference', 'media', 'https://www.zigwheels.co.th/en/new-cars/honda/city', NOW()
FROM "Variant" v JOIN "CarModel" cm ON cm.id=v."modelId" JOIN "Manufacturer" m ON m.id=cm."manufacturerId"
WHERE m.slug='honda' AND cm.slug='city' AND v."nameEn"='S' ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id,"variantId","lengthMm","widthMm","heightMm","wheelbaseMm","groundClearanceMm","sourceTier","sourceType","sourceUrl","verifiedAt")
SELECT gen_random_uuid(), v.id, 4589.0, 1748.0, 1467.0, 2589.0, 147.0, 'reference', 'media', 'https://www.zigwheels.co.th/en/new-cars/honda/city', NOW()
FROM "Variant" v JOIN "CarModel" cm ON cm.id=v."modelId" JOIN "Manufacturer" m ON m.id=cm."manufacturerId"
WHERE m.slug='honda' AND cm.slug='city' AND v."nameEn"='S' ON CONFLICT DO NOTHING;

-- Honda City e:HEV V
INSERT INTO "PerformanceSpec" (id,"variantId","powerKw","torqueNm","sourceTier","sourceType","sourceUrl","verifiedAt")
SELECT gen_random_uuid(), v.id, 72.0, 175.0, 'reference', 'media', 'https://www.zigwheels.co.th/en/new-cars/honda/city', NOW()
FROM "Variant" v JOIN "CarModel" cm ON cm.id=v."modelId" JOIN "Manufacturer" m ON m.id=cm."manufacturerId"
WHERE m.slug='honda' AND cm.slug='city' AND v."nameEn"='e:HEV V' ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id,"variantId","lengthMm","widthMm","heightMm","wheelbaseMm","groundClearanceMm","sourceTier","sourceType","sourceUrl","verifiedAt")
SELECT gen_random_uuid(), v.id, 4589.0, 1748.0, 1467.0, 2589.0, 147.0, 'reference', 'media', 'https://www.zigwheels.co.th/en/new-cars/honda/city', NOW()
FROM "Variant" v JOIN "CarModel" cm ON cm.id=v."modelId" JOIN "Manufacturer" m ON m.id=cm."manufacturerId"
WHERE m.slug='honda' AND cm.slug='city' AND v."nameEn"='e:HEV V' ON CONFLICT DO NOTHING;

-- Honda City e:HEV SV
INSERT INTO "PerformanceSpec" (id,"variantId","powerKw","torqueNm","sourceTier","sourceType","sourceUrl","verifiedAt")
SELECT gen_random_uuid(), v.id, 72.0, 175.0, 'reference', 'media', 'https://www.zigwheels.co.th/en/new-cars/honda/city', NOW()
FROM "Variant" v JOIN "CarModel" cm ON cm.id=v."modelId" JOIN "Manufacturer" m ON m.id=cm."manufacturerId"
WHERE m.slug='honda' AND cm.slug='city' AND v."nameEn"='e:HEV SV' ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id,"variantId","lengthMm","widthMm","heightMm","wheelbaseMm","groundClearanceMm","sourceTier","sourceType","sourceUrl","verifiedAt")
SELECT gen_random_uuid(), v.id, 4589.0, 1748.0, 1467.0, 2589.0, 147.0, 'reference', 'media', 'https://www.zigwheels.co.th/en/new-cars/honda/city', NOW()
FROM "Variant" v JOIN "CarModel" cm ON cm.id=v."modelId" JOIN "Manufacturer" m ON m.id=cm."manufacturerId"
WHERE m.slug='honda' AND cm.slug='city' AND v."nameEn"='e:HEV SV' ON CONFLICT DO NOTHING;

-- Honda City e:HEV RS
INSERT INTO "PerformanceSpec" (id,"variantId","powerKw","torqueNm","sourceTier","sourceType","sourceUrl","verifiedAt")
SELECT gen_random_uuid(), v.id, 72.0, 175.0, 'reference', 'media', 'https://www.zigwheels.co.th/en/new-cars/honda/city', NOW()
FROM "Variant" v JOIN "CarModel" cm ON cm.id=v."modelId" JOIN "Manufacturer" m ON m.id=cm."manufacturerId"
WHERE m.slug='honda' AND cm.slug='city' AND v."nameEn"='e:HEV RS' ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id,"variantId","lengthMm","widthMm","heightMm","wheelbaseMm","groundClearanceMm","sourceTier","sourceType","sourceUrl","verifiedAt")
SELECT gen_random_uuid(), v.id, 4589.0, 1748.0, 1467.0, 2589.0, 147.0, 'reference', 'media', 'https://www.zigwheels.co.th/en/new-cars/honda/city', NOW()
FROM "Variant" v JOIN "CarModel" cm ON cm.id=v."modelId" JOIN "Manufacturer" m ON m.id=cm."manufacturerId"
WHERE m.slug='honda' AND cm.slug='city' AND v."nameEn"='e:HEV RS' ON CONFLICT DO NOTHING;

-- Update fuel types for Honda City
UPDATE "Variant" SET "fuelType"='ICE', "fuelTypeSource"='reference' WHERE "modelId" IN (SELECT id FROM "CarModel" WHERE slug='city') AND "nameEn"='S';
UPDATE "Variant" SET "fuelType"='HEV', "fuelTypeSource"='reference' WHERE "modelId" IN (SELECT id FROM "CarModel" WHERE slug='city') AND "nameEn" LIKE 'e:HEV%';

SELECT 'Honda City done' as status;
