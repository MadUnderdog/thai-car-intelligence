-- MG URBAN specs (EV, Thailand)
-- Source: mgcars.com/th + Wikipedia MG4/MG URBAN
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm", "topSpeedKph")
SELECT gen_random_uuid(), v.id, 120.0, 250.0, 160.0
FROM "Variant" v WHERE v."nameEn" = 'URBAN' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='urban') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "BatterySpec" (id, "variantId", "capacityKwh", "chemistry")
SELECT gen_random_uuid(), v.id, 49.1, 'LFP'
FROM "Variant" v WHERE v."nameEn" = 'URBAN' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='urban') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "ChargingSpec" (id, "variantId", "acPowerKw", "dcPowerKw")
SELECT gen_random_uuid(), v.id, 7.0, 88.0
FROM "Variant" v WHERE v."nameEn" = 'URBAN' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='urban') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4376.0, 1804.0, 1545.0, 2650.0, 150.0
FROM "Variant" v WHERE v."nameEn" = 'URBAN' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='urban') LIMIT 1
ON CONFLICT DO NOTHING;

-- MG ZS EV specs (EV, Thailand)
-- Source: mgcars.com/th + Wikipedia MG ZS EV
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm", "topSpeedKph")
SELECT gen_random_uuid(), v.id, 130.0, 280.0, 140.0
FROM "Variant" v WHERE v."nameEn" = 'ZS EV' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='zs-ev') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "BatterySpec" (id, "variantId", "capacityKwh", "chemistry")
SELECT gen_random_uuid(), v.id, 51.1, 'LFP'
FROM "Variant" v WHERE v."nameEn" = 'ZS EV' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='zs-ev') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "ChargingSpec" (id, "variantId", "acPowerKw", "dcPowerKw")
SELECT gen_random_uuid(), v.id, 6.6, 87.0
FROM "Variant" v WHERE v."nameEn" = 'ZS EV' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='zs-ev') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4314.0, 1809.0, 1620.0, 2560.0, 155.0
FROM "Variant" v WHERE v."nameEn" = 'ZS EV' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='zs-ev') LIMIT 1
ON CONFLICT DO NOTHING;

-- MG MG4 MY2026 specs (EV, Thailand)
-- Source: mgcars.com/th + Wikipedia MG4 EV
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm", "topSpeedKph")
SELECT gen_random_uuid(), v.id, 125.0, 250.0, 160.0
FROM "Variant" v WHERE v."nameEn" = 'MG4 MY2026' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='mg4-my2026') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "BatterySpec" (id, "variantId", "capacityKwh", "chemistry")
SELECT gen_random_uuid(), v.id, 49.1, 'LFP'
FROM "Variant" v WHERE v."nameEn" = 'MG4 MY2026' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='mg4-my2026') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "ChargingSpec" (id, "variantId", "acPowerKw", "dcPowerKw")
SELECT gen_random_uuid(), v.id, 7.0, 88.0
FROM "Variant" v WHERE v."nameEn" = 'MG4 MY2026' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='mg4-my2026') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4287.0, 1836.0, 1516.0, 2705.0, 150.0
FROM "Variant" v WHERE v."nameEn" = 'MG4 MY2026' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='mg4-my2026') LIMIT 1
ON CONFLICT DO NOTHING;

-- MG VS HEV specs (Hybrid, Thailand)
-- Source: mgcars.com/th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm", "topSpeedKph")
SELECT gen_random_uuid(), v.id, 145.0, 300.0, 175.0
FROM "Variant" v WHERE v."nameEn" = 'VS HEV' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='vs-hev') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4570.0, 1860.0, 1670.0, 2700.0, 185.0
FROM "Variant" v WHERE v."nameEn" = 'VS HEV' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='vs-hev') LIMIT 1
ON CONFLICT DO NOTHING;
