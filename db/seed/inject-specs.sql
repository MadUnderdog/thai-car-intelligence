-- MG S5 EV PLUS specs
-- Source: Wikipedia MGS5 EV + thaiautonews official review + mgcars.com/th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm", "topSpeedKph")
SELECT gen_random_uuid(), v.id, 180.0, 350.0, 160.0
FROM "Variant" v WHERE v."nameEn" = 'S5 EV PLUS' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "BatterySpec" (id, "variantId", "capacityKwh", "chemistry")
SELECT gen_random_uuid(), v.id, 62.2, 'LFP'
FROM "Variant" v WHERE v."nameEn" = 'S5 EV PLUS' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "ChargingSpec" (id, "variantId", "acPowerKw", "dcPowerKw")
SELECT gen_random_uuid(), v.id, 7.0, 150.0
FROM "Variant" v WHERE v."nameEn" = 'S5 EV PLUS' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4476.0, 1849.0, 1621.0, 2730.0, 139.0
FROM "Variant" v WHERE v."nameEn" = 'S5 EV PLUS' LIMIT 1
ON CONFLICT DO NOTHING;

-- BYD Atto 3 specs
-- Source: Wikipedia BYD Atto 3 + official Thai pricing page
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm", "topSpeedKph")
SELECT gen_random_uuid(), v.id, 150.0, 310.0, 160.0
FROM "Variant" v WHERE v."nameEn" = 'ATTO 3' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "BatterySpec" (id, "variantId", "capacityKwh", "chemistry")
SELECT gen_random_uuid(), v.id, 50.25, 'LFP Blade'
FROM "Variant" v WHERE v."nameEn" = 'ATTO 3' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "ChargingSpec" (id, "variantId", "acPowerKw", "dcPowerKw")
SELECT gen_random_uuid(), v.id, 7.0, 80.0
FROM "Variant" v WHERE v."nameEn" = 'ATTO 3' LIMIT 1
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm")
SELECT gen_random_uuid(), v.id, 4455.0, 1875.0, 1615.0, 2720.0, 175.0
FROM "Variant" v WHERE v."nameEn" = 'ATTO 3' LIMIT 1
ON CONFLICT DO NOTHING;

-- Toyota Camry HEV specs
-- Source: tustintoyota.com + toyota.co.th
INSERT INTO "PerformanceSpec" (id, "variantId", "powerKw", "torqueNm")
SELECT gen_random_uuid(), v.id, 168.0, 221.0
FROM "Variant" v WHERE v."nameEn" IN ('HEV Smart','HEV Premium','HEV Premium Luxury')
ON CONFLICT DO NOTHING;

INSERT INTO "DimensionsSpec" (id, "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm")
SELECT gen_random_uuid(), v.id, 4920.0, 1840.0, 1455.0, 2825.0
FROM "Variant" v WHERE v."nameEn" IN ('HEV Smart','HEV Premium','HEV Premium Luxury')
ON CONFLICT DO NOTHING;
