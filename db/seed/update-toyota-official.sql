-- Toyota Camry HEV: CORRECTED from official toyota.co.th browser extraction
-- Old inferred: 168 kW, 221 Nm, 4920x1840x1455mm, WB 2825mm
-- Official: 137 kW (186 PS), 221 Nm, 4920x1840x1445mm, WB 2825mm
UPDATE "PerformanceSpec" SET 
  "powerKw"=137.0, "torqueNm"=221.0,
  "sourceTier"='official_verified', "sourceType"='browser_extracted',
  "sourceUrl"='https://www.toyota.co.th/en/model/camry/specification',
  "verifiedAt"=NOW()
WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "nameEn" IN ('HEV Smart','HEV Premium','HEV Premium Luxury'));

UPDATE "DimensionsSpec" SET 
  "lengthMm"=4920.0, "widthMm"=1840.0, "heightMm"=1445.0, "wheelbaseMm"=2825.0,
  "sourceTier"='official_verified', "sourceType"='browser_extracted',
  "sourceUrl"='https://www.toyota.co.th/en/model/camry/specification',
  "verifiedAt"=NOW()
WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "nameEn" IN ('HEV Smart','HEV Premium','HEV Premium Luxury'));

-- Toyota Yaris Cross: CORRECTED from browser extraction
-- Old inferred: 85 kW, 148 Nm, 4370x1770x1615mm, WB 2560mm
-- Official: 67 kW (91 PS), 121 Nm, 4310x1770x1615mm, WB 2620mm
UPDATE "PerformanceSpec" SET 
  "powerKw"=67.0, "torqueNm"=121.0,
  "sourceTier"='official_verified', "sourceType"='browser_extracted',
  "sourceUrl"='https://www.toyota.co.th/en/model/yariscross/specification',
  "verifiedAt"=NOW()
WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "nameEn"='yaris-cross');

UPDATE "DimensionsSpec" SET 
  "lengthMm"=4310.0, "widthMm"=1770.0, "heightMm"=1615.0, "wheelbaseMm"=2620.0, "groundClearanceMm"=210.0,
  "sourceTier"='official_verified', "sourceType"='browser_extracted',
  "sourceUrl"='https://www.toyota.co.th/en/model/yariscross/specification',
  "verifiedAt"=NOW()
WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "nameEn"='yaris-cross');

-- Toyota Yaris: CORRECTED from browser extraction
-- Old inferred: 67 kW, 109 Nm, 4145x1730x1500mm, WB 2560mm
-- Official: 68 kW (92 PS), 109 Nm, 4160x1730x1500mm, WB 2550mm
UPDATE "PerformanceSpec" SET 
  "powerKw"=68.0, "torqueNm"=109.0,
  "sourceTier"='official_verified', "sourceType"='browser_extracted',
  "sourceUrl"='https://www.toyota.co.th/en/model/yaris/specification',
  "verifiedAt"=NOW()
WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "nameEn"='yaris');

UPDATE "DimensionsSpec" SET 
  "lengthMm"=4160.0, "widthMm"=1730.0, "heightMm"=1500.0, "wheelbaseMm"=2550.0,
  "sourceTier"='official_verified', "sourceType"='browser_extracted',
  "sourceUrl"='https://www.toyota.co.th/en/model/yaris/specification',
  "verifiedAt"=NOW()
WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "nameEn"='yaris');

-- Toyota Corolla Cross: CORRECTED from browser extraction
-- Old inferred: 103 kW, 142 Nm, 4460x1825x1620mm, WB 2640mm
-- Official: 72 kW (98 PS), 142 Nm, 4460x1825x1620mm, WB 2640mm
UPDATE "PerformanceSpec" SET 
  "powerKw"=72.0, "torqueNm"=142.0,
  "sourceTier"='official_verified', "sourceType"='browser_extracted',
  "sourceUrl"='https://www.toyota.co.th/en/model/corollacross/specification',
  "verifiedAt"=NOW()
WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "nameEn"='corolla-cross');

UPDATE "DimensionsSpec" SET 
  "lengthMm"=4460.0, "widthMm"=1825.0, "heightMm"=1620.0, "wheelbaseMm"=2640.0, "groundClearanceMm"=161.0,
  "sourceTier"='official_verified', "sourceType"='browser_extracted',
  "sourceUrl"='https://www.toyota.co.th/en/model/corollacross/specification',
  "verifiedAt"=NOW()
WHERE "variantId" IN (SELECT id FROM "Variant" WHERE "nameEn"='corolla-cross');
