-- Toyota Yaris (Thailand: 1.2L, 92 PS)
-- Source: toyota.co.th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm")
SELECT gen_random_uuid(), v.id, 67.0, 109.0
FROM "Variant" v WHERE v."nameEn" = 'Yaris' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='yaris') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4145.0, 1730.0, 1500.0, 2560.0, 140.0
FROM "Variant" v WHERE v."nameEn" = 'Yaris' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='yaris') LIMIT 1
ON CONFLICT DO NOTHING;

-- Toyota Yaris ATIV (Thailand: 1.2L, 92 PS)
-- Source: toyota.co.th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm")
SELECT gen_random_uuid(), v.id, 67.0, 109.0
FROM "Variant" v WHERE v."nameEn" = 'Yaris ATIV' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='yaris-ativ') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4425.0, 1740.0, 1480.0, 2620.0, 135.0
FROM "Variant" v WHERE v."nameEn" = 'Yaris ATIV' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='yaris-ativ') LIMIT 1
ON CONFLICT DO NOTHING;

-- Toyota Corolla Cross (Thailand: 1.8L Petrol / 1.8L HEV)
-- Source: toyota.co.th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm")
SELECT gen_random_uuid(), v.id, 103.0, 142.0
FROM "Variant" v WHERE v."nameEn" = 'Corolla Cross' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='corolla-cross') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4460.0, 1825.0, 1620.0, 2640.0, 161.0
FROM "Variant" v WHERE v."nameEn" = 'Corolla Cross' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='corolla-cross') LIMIT 1
ON CONFLICT DO NOTHING;

-- Toyota Hilux Revo (Thailand: 2.4L Diesel, 150 PS)
-- Source: toyota.co.th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm")
SELECT gen_random_uuid(), v.id, 110.0, 400.0
FROM "Variant" v WHERE v."nameEn" = 'Hilux Revo' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='hilux-revo') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 5325.0, 1855.0, 1815.0, 3085.0, 310.0
FROM "Variant" v WHERE v."nameEn" = 'Hilux Revo' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='hilux-revo') LIMIT 1
ON CONFLICT DO NOTHING;

-- Toyota Fortuner (Thailand: 2.4L Diesel, 150 PS)
-- Source: toyota.co.th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm")
SELECT gen_random_uuid(), v.id, 110.0, 400.0
FROM "Variant" v WHERE v."nameEn" = 'Fortuner' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='fortuner') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4795.0, 1855.0, 1835.0, 2750.0, 279.0
FROM "Variant" v WHERE v."nameEn" = 'Fortuner' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='fortuner') LIMIT 1
ON CONFLICT DO NOTHING;

-- Toyota Corolla Altis (Thailand: 1.8L Petrol, 140 PS)
-- Source: toyota.co.th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm")
SELECT gen_random_uuid(), v.id, 103.0, 177.0
FROM "Variant" v WHERE v."nameEn" = 'Corolla Altis' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='corolla-altis') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4630.0, 1780.0, 1435.0, 2700.0, 135.0
FROM "Variant" v WHERE v."nameEn" = 'Corolla Altis' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='corolla-altis') LIMIT 1
ON CONFLICT DO NOTHING;

-- Toyota Yaris Cross (Thailand: 1.5L Hybrid, 116 PS)
-- Source: toyota.co.th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm")
SELECT gen_random_uuid(), v.id, 85.0, 148.0
FROM "Variant" v WHERE v."nameEn" = 'Yaris Cross' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='yaris-cross') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4370.0, 1770.0, 1615.0, 2560.0, 165.0
FROM "Variant" v WHERE v."nameEn" = 'Yaris Cross' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='yaris-cross') LIMIT 1
ON CONFLICT DO NOTHING;

-- Toyota Veloz (Thailand: 1.5L, 106 PS)
-- Source: toyota.co.th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm")
SELECT gen_random_uuid(), v.id, 78.0, 138.0
FROM "Variant" v WHERE v."nameEn" = 'Veloz' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='veloz') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4475.0, 1750.0, 1695.0, 2750.0, 195.0
FROM "Variant" v WHERE v."nameEn" = 'Veloz' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='veloz') LIMIT 1
ON CONFLICT DO NOTHING;

-- Toyota Avanza (Thailand: 1.5L, 106 PS)
-- Source: toyota.co.th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm")
SELECT gen_random_uuid(), v.id, 78.0, 138.0
FROM "Variant" v WHERE v."nameEn" = 'Avanza' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='avanza') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4395.0, 1730.0, 1690.0, 2750.0, 195.0
FROM "Variant" v WHERE v."nameEn" = 'Avanza' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='avanza') LIMIT 1
ON CONFLICT DO NOTHING;

-- Toyota Hilux Champ (Thailand: 2.4L Diesel, 150 PS)
-- Source: toyota.co.th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm")
SELECT gen_random_uuid(), v.id, 110.0, 400.0
FROM "Variant" v WHERE v."nameEn" = 'Hilux Champ' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='hilux-champ') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4860.0, 1795.0, 1740.0, 2750.0, 286.0
FROM "Variant" v WHERE v."nameEn" = 'Hilux Champ' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='hilux-champ') LIMIT 1
ON CONFLICT DO NOTHING;

-- Toyota Innova (Thailand: 2.0L, 139 PS)
-- Source: toyota.co.th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm")
SELECT gen_random_uuid(), v.id, 102.0, 183.0
FROM "Variant" v WHERE v."nameEn" = 'Innova' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='innova') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4735.0, 1795.0, 1750.0, 2750.0, 185.0
FROM "Variant" v WHERE v."nameEn" = 'Innova' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='innova') LIMIT 1
ON CONFLICT DO NOTHING;
