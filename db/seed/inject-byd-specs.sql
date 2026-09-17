-- BYD Dolphin specs (Thailand: Standard 44.9kWh, Extended 60.4kWh)
-- Source: Wikipedia BYD Dolphin + reverautomotive.com
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm", "topSpeedKph")
SELECT gen_random_uuid(), v.id, 70.0, 180.0, 150.0
FROM "Variant" v WHERE v."nameEn" = 'Dolphin' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='dolphin') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "BatterySpec" (id, "variantId", "capacityKwh", "chemistry")
SELECT gen_random_uuid(), v.id, 44.9, 'LFP'
FROM "Variant" v WHERE v."nameEn" = 'Dolphin' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='dolphin') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "ChargingSpec" (id, "variantId", "acPowerKw", "dcPowerKw")
SELECT gen_random_uuid(), v.id, 6.6, 65.0
FROM "Variant" v WHERE v."nameEn" = 'Dolphin' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='dolphin') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4290.0, 1770.0, 1570.0, 2700.0, 130.0
FROM "Variant" v WHERE v."nameEn" = 'Dolphin' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='dolphin') LIMIT 1
ON CONFLICT DO NOTHING;

-- BYD Seal specs (Thailand: 82.5 kWh AWD)
-- Source: Wikipedia BYD Seal
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm", "topSpeedKph", "acceleration0To100S")
SELECT gen_random_uuid(), v.id, 390.0, 670.0, 180.0, 3.8
FROM "Variant" v WHERE v."nameEn" = 'Seal' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='seal') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "BatterySpec" (id, "variantId", "capacityKwh", "chemistry")
SELECT gen_random_uuid(), v.id, 82.5, 'LFP Blade'
FROM "Variant" v WHERE v."nameEn" = 'Seal' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='seal') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "ChargingSpec" (id, "variantId", "acPowerKw", "dcPowerKw")
SELECT gen_random_uuid(), v.id, 11.0, 150.0
FROM "Variant" v WHERE v."nameEn" = 'Seal' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='seal') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4800.0, 1875.0, 1460.0, 2920.0, 120.0
FROM "Variant" v WHERE v."nameEn" = 'Seal' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='seal') LIMIT 1
ON CONFLICT DO NOTHING;

-- BYD Atto 2 specs
-- Source: Wikipedia BYD Yuan Up / reverautomotive.com
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm", "topSpeedKph")
SELECT gen_random_uuid(), v.id, 70.0, 180.0, 150.0
FROM "Variant" v WHERE v."nameEn" = 'ATTO 2' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='atto-2') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "BatterySpec" (id, "variantId", "capacityKwh", "chemistry")
SELECT gen_random_uuid(), v.id, 45.1, 'LFP Blade'
FROM "Variant" v WHERE v."nameEn" = 'ATTO 2' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='atto-2') LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm")
SELECT gen_random_uuid(), v.id, 4390.0, 1790.0, 1595.0, 2620.0
FROM "Variant" v WHERE v."nameEn" = 'ATTO 2' AND v."modelId" IN (SELECT id FROM "CarModel" WHERE slug='atto-2') LIMIT 1
ON CONFLICT DO NOTHING;

-- BYD Sealion 5 DM-i specs (PHEV)
-- Source: Wikipedia BYD Seal 05 DM-i
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm", "topSpeedKph")
SELECT gen_random_uuid(), v.id, 145.0, 325.0, 170.0
FROM "Variant" v WHERE v."nameEn" = 'Sealion 5 DM-i' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "BatterySpec" (id, "variantId", "capacityKwh", "chemistry")
SELECT gen_random_uuid(), v.id, 18.3, 'LFP'
FROM "Variant" v WHERE v."nameEn" = 'Sealion 5 DM-i' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm")
SELECT gen_random_uuid(), v.id, 4785.0, 1890.0, 1660.0, 2765.0
FROM "Variant" v WHERE v."nameEn" = 'Sealion 5 DM-i' LIMIT 1
ON CONFLICT DO NOTHING;

-- BYD Sealion 6 DM-i specs (PHEV)
-- Source: Wikipedia BYD Seal 06 DM-i
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm", "topSpeedKph")
SELECT gen_random_uuid(), v.id, 160.0, 350.0, 180.0
FROM "Variant" v WHERE v."nameEn" = 'Sealion 6 DM-i' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "BatterySpec" (id, "variantId", "capacityKwh", "chemistry")
SELECT gen_random_uuid(), v.id, 18.3, 'LFP'
FROM "Variant" v WHERE v."nameEn" = 'Sealion 6 DM-i' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm")
SELECT gen_random_uuid(), v.id, 4785.0, 1890.0, 1660.0, 2765.0
FROM "Variant" v WHERE v."nameEn" = 'Sealion 6 DM-i' LIMIT 1
ON CONFLICT DO NOTHING;

-- BYD Sealion 7 specs (EV)
-- Source: Wikipedia BYD Sealion 7
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm", "topSpeedKph", "acceleration0To100S")
SELECT gen_random_uuid(), v.id, 230.0, 380.0, 200.0, 6.7
FROM "Variant" v WHERE v."nameEn" = 'Sealion 7' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "BatterySpec" (id, "variantId", "capacityKwh", "chemistry")
SELECT gen_random_uuid(), v.id, 91.3, 'LFP Blade'
FROM "Variant" v WHERE v."nameEn" = 'Sealion 7' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "ChargingSpec" (id, "variantId", "acPowerKw", "dcPowerKw")
SELECT gen_random_uuid(), v.id, 11.0, 150.0
FROM "Variant" v WHERE v."nameEn" = 'Sealion 7' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4830.0, 1925.0, 1620.0, 2930.0, 190.0
FROM "Variant" v WHERE v."nameEn" = 'Sealion 7' LIMIT 1
ON CONFLICT DO NOTHING;
