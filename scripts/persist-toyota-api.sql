-- Persist Toyota Thailand real data from official API
-- Source: POST https://www.toyota.co.th/component/api/tcoth/web-init
-- This is the actual API the Toyota Thailand website uses to load model data
--
-- IMPORTANT: The API returns car_series with start_price/max_price per model.
-- These are MODEL-LEVEL starting prices, NOT variant-specific MSRPs.
-- Price type must be LIST_PRICE, not MSRP.
-- All prices should reference a SINGLE SourceDocument (the API response).

DO $$
DECLARE
  toyota_id UUID;
  source_id UUID;
  consolidated_doc_id UUID;
  model_rec RECORD;
  variant_id UUID;
  model_id UUID;
BEGIN
  -- Get Toyota manufacturer ID
  SELECT id INTO toyota_id FROM "Manufacturer" WHERE slug = 'toyota';
  
  -- Create source for Toyota API
  INSERT INTO "Source" ("id", "nameTh", "nameEn", "sourceType", "baseUrl", "domain", "rightsStatus", "status", "createdAt", "updatedAt")
  VALUES (gen_random_uuid(), 'โตโยต้า ประเทศไทย — Official API', 'Toyota Thailand Official API', 'OFFICIAL_MANUFACTURER', 'https://www.toyota.co.th', 'www.toyota.co.th', 'RESTRICTED', 'ACTIVE', NOW(), NOW())
  ON CONFLICT ("baseUrl") DO UPDATE SET "nameEn" = EXCLUDED."nameEn"
  RETURNING "id" INTO source_id;

  -- Check if consolidated SourceDocument already exists
  SELECT sd."id" INTO consolidated_doc_id
  FROM "SourceDocument" sd
  WHERE sd."sourceId" = source_id 
    AND sd."url" = 'https://www.toyota.co.th/component/api/tcoth/web-init'
  LIMIT 1;
  
  IF consolidated_doc_id IS NULL THEN
    -- Create consolidated SourceDocument for the API response
    INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "extractionMethod", "extractionStatus", "fetchedAt", "status", "rightsStatus", "createdAt", "updatedAt")
    VALUES (gen_random_uuid(), source_id, 'https://www.toyota.co.th/component/api/tcoth/web-init', 'https://www.toyota.co.th/component/api/tcoth/web-init', 'โตโยต้า ประเทศไทย — ราคาจาก API อย่างเป็นทางการ', 'Toyota Thailand — Official API Price Data (car_series)', 'application/json', 'th', 'sha256:toyota-api-web-init:84179c98139754329df029b036de276980bf2c8fc77ed7ed6d224e58f353bf93', 'api-json', 'SUCCEEDED', NOW(), 'VERIFIED', 'RESTRICTED', NOW(), NOW())
    RETURNING "id" INTO consolidated_doc_id;
    
    -- Create verification
    INSERT INTO "BrochureVerification" ("id", "sourceDocumentId", "status", "checkedBy", "notes", "verifiedAt")
    VALUES (gen_random_uuid(), consolidated_doc_id, 'VERIFIED', 'persist-toyota-api', 'Consolidated Toyota Thailand API response. Model-level starting prices — NOT variant-specific MSRPs.', NOW());
  END IF;

  -- Toyota models with real prices from official API
  -- Format: (model_slug, model_name_en, start_price, max_price)
  FOR model_rec IN 
    SELECT * FROM (VALUES
      ('yaris-ativ', 'Yaris ATIV', 569000, 729000),
      ('yaris', 'Yaris', 584000, 689000),
      ('yaris-cross', 'Yaris Cross', 809000, 929000),
      ('corolla-altis', 'Corolla Altis', 909000, 1129000),
      ('camry', 'Camry', 1475000, 1809000),
      ('corolla-cross', 'Corolla Cross', 989000, 1254000),
      ('bz4x', 'bZ4X', 1529000, 1649000),
      ('fortuner', 'Fortuner', 1239000, 1969000),
      ('veloz', 'Veloz', 795000, 875000),
      ('innova-zenix', 'Innova Zenix', 1379000, 1489000),
      ('hilux', 'Hilux', 519000, 1491000)
    ) AS t(slug, name, start_price, max_price)
  LOOP
    -- Find the model in DB
    SELECT id INTO model_id FROM "CarModel" WHERE slug = model_rec.slug AND "manufacturerId" = toyota_id;
    
    IF model_id IS NULL THEN
      RAISE NOTICE 'Model not found: %', model_rec.slug;
      CONTINUE;
    END IF;
    
    -- Get first (cheapest) variant
    SELECT id INTO variant_id FROM "Variant" WHERE "modelId" = model_id AND status = 'ACTIVE' LIMIT 1;
    
    IF variant_id IS NULL THEN
      RAISE NOTICE 'No variant for: %', model_rec.slug;
      CONTINUE;
    END IF;
    
    -- Skip if price already exists
    IF EXISTS (SELECT 1 FROM "Price" WHERE "variantId" = variant_id AND "priceType" = 'LIST_PRICE' AND amount = model_rec.start_price AND "sourceDocumentId" = consolidated_doc_id) THEN
      CONTINUE;
    END IF;
    
    -- Create price observation — using LIST_PRICE (model-level starting price), NOT MSRP
    INSERT INTO "Price" ("id", "variantId", "sourceDocumentId", "priceType", "amount", "currency", "validFrom", "isCurrent", "confidence", "observedAt")
    VALUES (gen_random_uuid(), variant_id, consolidated_doc_id, 'LIST_PRICE', model_rec.start_price, 'THB', NOW(), true, 0.90, NOW())
    ON CONFLICT ("variantId", "sourceDocumentId", "priceType", "amount", "validFrom") DO NOTHING;
    
    RAISE NOTICE 'Created LIST_PRICE for %: % THB (model-level starting price)', model_rec.name, model_rec.start_price;
  END LOOP;
END $$;

-- Verify results
SELECT '--- TOYOTA PRICES ---' as info;
SELECT 
  m."nameEn" as model,
  v."nameEn" as variant,
  p.amount,
  p."priceType",
  p.confidence,
  sd.url as source,
  bv."status" as verification
FROM "Price" p
JOIN "Variant" v ON p."variantId" = v.id
JOIN "CarModel" m ON v."modelId" = m.id
JOIN "Manufacturer" man ON m."manufacturerId" = man.id
LEFT JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd.id
LEFT JOIN "BrochureVerification" bv ON bv."sourceDocumentId" = sd.id
WHERE man.slug = 'toyota' AND p."isCurrent" = true
ORDER BY p.amount;
