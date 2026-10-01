-- Persist real Toyota specs from official API
-- Source: GET /en/model/api/car/?series_code={code}
-- These are REAL specs from Toyota Thailand official website

DO $$
DECLARE
  model_rec RECORD;
  spec_data JSONB;
BEGIN
  -- Camry
  SELECT id INTO model_rec FROM "CarModel" WHERE slug = 'camry' AND "manufacturerId" = (SELECT id FROM "Manufacturer" WHERE slug = 'toyota');
  IF model_rec IS NOT NULL THEN
    UPDATE "DimensionsSpec" SET 
      "lengthMm" = 4920, "widthMm" = 1840, "heightMm" = 1445, 
      "wheelbaseMm" = 2825, "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=camry',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    UPDATE "PerformanceSpec" SET
      "powerKw" = 137, "torqueNm" = 221,
      "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=camry',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    UPDATE "BatterySpec" SET
      "chemistry" = 'Lithium-ion',
      "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=camry',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    RAISE NOTICE 'Camry specs updated';
  END IF;

  -- Fortuner
  SELECT id INTO model_rec FROM "CarModel" WHERE slug = 'fortuner' AND "manufacturerId" = (SELECT id FROM "Manufacturer" WHERE slug = 'toyota');
  IF model_rec IS NOT NULL THEN
    UPDATE "DimensionsSpec" SET
      "lengthMm" = 4795, "widthMm" = 1855, "heightMm" = 1835,
      "wheelbaseMm" = 2750, "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=fortuner_legender',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    UPDATE "PerformanceSpec" SET
      "powerKw" = 150, "torqueNm" = 500,
      "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=fortuner_legender',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    RAISE NOTICE 'Fortuner specs updated';
  END IF;

  -- bZ4X
  SELECT id INTO model_rec FROM "CarModel" WHERE slug = 'bz4x' AND "manufacturerId" = (SELECT id FROM "Manufacturer" WHERE slug = 'toyota');
  IF model_rec IS NOT NULL THEN
    UPDATE "DimensionsSpec" SET
      "lengthMm" = 4690, "widthMm" = 1860, "heightMm" = 1650,
      "wheelbaseMm" = 2850, "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=bz4x',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    UPDATE "BatterySpec" SET
      "chemistry" = 'Lithium-ion',
      "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=bz4x',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    RAISE NOTICE 'bZ4X specs updated';
  END IF;

  -- Innova Zenix
  SELECT id INTO model_rec FROM "CarModel" WHERE slug = 'innova-zenix' AND "manufacturerId" = (SELECT id FROM "Manufacturer" WHERE slug = 'toyota');
  IF model_rec IS NOT NULL THEN
    UPDATE "DimensionsSpec" SET
      "lengthMm" = 4799, "widthMm" = 1850, "heightMm" = 1790,
      "wheelbaseMm" = 2850, "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=innovazenix',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    UPDATE "PerformanceSpec" SET
      "powerKw" = 140, "torqueNm" = 188,
      "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=innovazenix',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    UPDATE "BatterySpec" SET
      "chemistry" = 'Nickel-metal hydride (NiMH)',
      "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=innovazenix',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    RAISE NOTICE 'Innova Zenix specs updated';
  END IF;

  -- Veloz
  SELECT id INTO model_rec FROM "CarModel" WHERE slug = 'veloz' AND "manufacturerId" = (SELECT id FROM "Manufacturer" WHERE slug = 'toyota');
  IF model_rec IS NOT NULL THEN
    UPDATE "DimensionsSpec" SET
      "lengthMm" = 4475, "widthMm" = 1750, "heightMm" = 1700,
      "wheelbaseMm" = 2750, "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=veloz',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    UPDATE "PerformanceSpec" SET
      "torqueNm" = 138,
      "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=veloz',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    RAISE NOTICE 'Veloz specs updated';
  END IF;

  -- Hilux
  SELECT id INTO model_rec FROM "CarModel" WHERE slug = 'hilux' AND "manufacturerId" = (SELECT id FROM "Manufacturer" WHERE slug = 'toyota');
  IF model_rec IS NOT NULL THEN
    UPDATE "PerformanceSpec" SET
      "torqueNm" = 400,
      "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=hilux_revo_zedition',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    RAISE NOTICE 'Hilux specs updated';
  END IF;

  -- Yaris ATIV
  SELECT id INTO model_rec FROM "CarModel" WHERE slug = 'yaris-ativ' AND "manufacturerId" = (SELECT id FROM "Manufacturer" WHERE slug = 'toyota');
  IF model_rec IS NOT NULL THEN
    UPDATE "DimensionsSpec" SET
      "lengthMm" = 4425, "widthMm" = 1740, "heightMm" = 1480,
      "wheelbaseMm" = 2620, "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=yarisativ',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    UPDATE "PerformanceSpec" SET
      "torqueNm" = 121,
      "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=yarisativ',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    UPDATE "BatterySpec" SET
      "chemistry" = 'Lithium-Ion',
      "sourceTier" = 'primary_official',
      "sourceUrl" = 'https://www.toyota.co.th/en/model/api/car/?series_code=yarisativ',
      "verifiedAt" = NOW()
    WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "modelId" = model_rec.id);
    
    RAISE NOTICE 'Yaris ATIV specs updated';
  END IF;
END $$;

-- Verify spec counts
SELECT '--- SPEC COUNTS ---' as section;
SELECT 'dimensions' as tbl, count(*) as cnt FROM "DimensionsSpec" WHERE "sourceTier" = 'primary_official'
UNION ALL SELECT 'performance', count(*) FROM "PerformanceSpec" WHERE "sourceTier" = 'primary_official'
UNION ALL SELECT 'battery', count(*) FROM "BatterySpec" WHERE "sourceTier" = 'primary_official';
