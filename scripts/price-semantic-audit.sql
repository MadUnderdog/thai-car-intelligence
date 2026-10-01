-- ============================================================================
-- COMPREHENSIVE PRICE SEMANTIC AUDIT
-- Thai Car Intelligence Database
-- Checks all active (non-quarantined) prices for semantic integrity issues
-- ============================================================================

-- ============================================================================
-- SECTION 0: Summary counts
-- ============================================================================
SELECT '=== SECTION 0: BASELINE COUNTS ===' as section;

SELECT
  (SELECT COUNT(*) FROM "Price" WHERE "quarantineStatus" IS NULL OR "quarantineStatus" != 'quarantined') as total_active_prices,
  (SELECT COUNT(*) FROM "Price" WHERE "isCurrent" = true AND ("quarantineStatus" IS NULL OR "quarantineStatus" != 'quarantined')) as total_current_prices,
  (SELECT COUNT(*) FROM "Price" WHERE "quarantineStatus" = 'quarantined') as already_quarantined;


-- ============================================================================
-- SECTION 1: Toyota URL series_code vs Model Name Mismatch
-- For Toyota prices from toyota.co.th URLs with series_code parameter,
-- check if the series_code in the URL matches the model name
-- ============================================================================
SELECT '=== SECTION 1: URL series_code vs MODEL NAME MISMATCH ===' as section;

WITH toyota_url_prices AS (
  SELECT
    p."id" as price_id,
    p."amount",
    p."isCurrent",
    p."quarantineStatus",
    sd."url",
    cm."nameEn" as model_name,
    m."nameEn" as brand,
    v."nameEn" as variant_name,
    -- Extract series_code from URL
    CASE
      WHEN sd."url" LIKE '%series_code=%' THEN
        regexp_replace(sd."url", '.*series_code=([^&]+).*', '\1')
      ELSE NULL
    END as series_code
  FROM "Price" p
  JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
  JOIN "Variant" v ON p."variantId" = v."id"
  JOIN "CarModel" cm ON v."modelId" = cm."id"
  JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
  WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
    AND sd."url" LIKE '%toyota.co.th%series_code=%'
),
series_code_mismatch AS (
  SELECT
    t.*,
    -- Normalize both for comparison: lowercase, remove spaces/hyphens/underscores
    lower(replace(replace(replace(t.series_code, ' ', ''), '-', ''), '_', '')) as normalized_code,
    lower(replace(replace(replace(replace(t.model_name, ' ', ''), '-', ''), '_', ''), '/', '')) as normalized_model
  FROM toyota_url_prices t
  WHERE t.series_code IS NOT NULL
)
SELECT
  price_id,
  brand,
  model_name,
  variant_name,
  amount,
  "isCurrent",
  "quarantineStatus",
  series_code,
  normalized_code,
  normalized_model,
  url,
  CASE
    WHEN normalized_model LIKE '%' || normalized_code || '%' THEN 'MATCH'
    WHEN normalized_code LIKE '%' || normalized_model || '%' THEN 'MATCH'
    ELSE 'MISMATCH'
  END as match_result
FROM series_code_mismatch
WHERE
  -- Check for mismatch: neither contains the other
  normalized_model NOT LIKE '%' || normalized_code || '%'
  AND normalized_code NOT LIKE '%' || normalized_model || '%'
ORDER BY brand, model_name, variant_name;


-- Also check non-Toyota brand URLs for brand/model consistency
SELECT '=== SECTION 1b: NON-TOYOTA URL-BRAND MISMATCH ===' as section;

SELECT
  p."id" as price_id,
  m."nameEn" as model_brand,
  cm."nameEn" as model_name,
  v."nameEn" as variant_name,
  sd."url",
  p."amount",
  CASE
    WHEN sd."url" LIKE '%toyota.co.th%' AND m."nameEn" != 'Toyota' THEN 'URL=Toyota but model_brand=' || m."nameEn"
    WHEN sd."url" LIKE '%honda.co.th%' AND m."nameEn" != 'Honda' THEN 'URL=Honda but model_brand=' || m."nameEn"
    WHEN sd."url" LIKE '%mazda%' AND m."nameEn" != 'Mazda' THEN 'URL=Mazda but model_brand=' || m."nameEn"
    WHEN sd."url" LIKE '%nissan.co.th%' AND m."nameEn" != 'Nissan' THEN 'URL=Nissan but model_brand=' || m."nameEn"
    WHEN sd."url" LIKE '%mitsubishi%' AND m."nameEn" != 'Mitsubishi' THEN 'URL=Mitsubishi but model_brand=' || m."nameEn"
    WHEN sd."url" LIKE '%isuzu%' AND m."nameEn" != 'Isuzu' THEN 'URL=Isuzu but model_brand=' || m."nameEn"
    WHEN sd."url" LIKE '%mgcars.com%' AND m."nameEn" != 'MG' THEN 'URL=MG but model_brand=' || m."nameEn"
    WHEN sd."url" LIKE '%byd%' AND m."nameEn" != 'BYD' THEN 'URL=BYD but model_brand=' || m."nameEn"
    WHEN sd."url" LIKE '%hyundai%' AND m."nameEn" != 'Hyundai' THEN 'URL=Hyundai but model_brand=' || m."nameEn"
    WHEN sd."url" LIKE '%kia%' AND m."nameEn" != 'Kia' THEN 'URL=Kia but model_brand=' || m."nameEn"
    ELSE 'OK'
  END as brand_check
FROM "Price" p
JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
JOIN "Variant" v ON p."variantId" = v."id"
JOIN "CarModel" cm ON v."modelId" = cm."id"
JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
  AND (
    (sd."url" LIKE '%toyota.co.th%' AND m."nameEn" != 'Toyota')
    OR (sd."url" LIKE '%honda.co.th%' AND m."nameEn" != 'Honda')
    OR (sd."url" LIKE '%mazda%' AND m."nameEn" != 'Mazda')
    OR (sd."url" LIKE '%nissan.co.th%' AND m."nameEn" != 'Nissan')
    OR (sd."url" LIKE '%mitsubishi%' AND m."nameEn" != 'Mitsubishi')
    OR (sd."url" LIKE '%isuzu%' AND m."nameEn" != 'Isuzu')
    OR (sd."url" LIKE '%mgcars.com%' AND m."nameEn" != 'MG')
    OR (sd."url" LIKE '%byd%' AND m."nameEn" != 'BYD')
    OR (sd."url" LIKE '%hyundai%' AND m."nameEn" != 'Hyundai')
    OR (sd."url" LIKE '%kia%' AND m."nameEn" != 'Kia')
  )
ORDER BY m."nameEn", cm."nameEn";


-- ============================================================================
-- SECTION 2: Suspiciously High Prices
-- Economy brands: >2M THB (Toyota, Honda, Mazda, Nissan, Mitsubishi, Isuzu, MG, BYD, Hyundai, Kia, Suzuki)
-- Luxury brands: >5M THB (Lexus, BMW, Mercedes, Audi, Porsche, Volvo, Jaguar, Land Rover)
-- ============================================================================
SELECT '=== SECTION 2: SUSPICIOUSLY HIGH PRICES ===' as section;

SELECT
  p."id" as price_id,
  m."nameEn" as brand,
  cm."nameEn" as model,
  v."nameEn" as variant,
  p."amount",
  p."currency",
  p."priceType",
  p."isCurrent",
  CASE
    WHEN m."nameEn" IN ('Toyota', 'Honda', 'Mazda', 'Nissan', 'Mitsubishi', 'Isuzu', 'MG', 'BYD', 'Hyundai', 'Kia', 'Suzuki', 'Subaru', 'Ford', 'Chevrolet') AND p."amount" > 2000000 THEN 'ECONOMY_THRESHOLD_EXCEEDED'
    WHEN m."nameEn" IN ('Lexus', 'BMW', 'Mercedes-Benz', 'Mercedes', 'Audi', 'Porsche', 'Volvo', 'Jaguar', 'Land Rover', 'Mini') AND p."amount" > 5000000 THEN 'LUXURY_THRESHOLD_EXCEEDED'
    WHEN p."amount" > 5000000 THEN 'GENERIC_THRESHOLD_EXCEEDED'
    ELSE 'OK'
  END as price_check,
  sd."url"
FROM "Price" p
JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
JOIN "Variant" v ON p."variantId" = v."id"
JOIN "CarModel" cm ON v."modelId" = cm."id"
JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
  AND (
    (m."nameEn" IN ('Toyota', 'Honda', 'Mazda', 'Nissan', 'Mitsubishi', 'Isuzu', 'MG', 'BYD', 'Hyundai', 'Kia', 'Suzuki', 'Subaru', 'Ford', 'Chevrolet') AND p."amount" > 2000000)
    OR (m."nameEn" IN ('Lexus', 'BMW', 'Mercedes-Benz', 'Mercedes', 'Audi', 'Porsche', 'Volvo', 'Jaguar', 'Land Rover', 'Mini') AND p."amount" > 5000000)
    OR (m."nameEn" NOT IN ('Toyota', 'Honda', 'Mazda', 'Nissan', 'Mitsubishi', 'Isuzu', 'MG', 'BYD', 'Hyundai', 'Kia', 'Suzuki', 'Subaru', 'Ford', 'Chevrolet', 'Lexus', 'BMW', 'Mercedes-Benz', 'Mercedes', 'Audi', 'Porsche', 'Volvo', 'Jaguar', 'Land Rover', 'Mini') AND p."amount" > 5000000)
  )
ORDER BY p."amount" DESC, m."nameEn", cm."nameEn";


-- ============================================================================
-- SECTION 3: Cross-Source Price Disagreement
-- Same variant with prices from 3+ different sources that disagree by >20%
-- ============================================================================
SELECT '=== SECTION 3: CROSS-SOURCE PRICE DISAGREEMENT (>20%) ===' as section;

WITH active_prices AS (
  SELECT
    p."id" as price_id,
    p."variantId",
    p."sourceDocumentId",
    p."amount",
    p."isCurrent",
    v."nameEn" as variant_name,
    cm."nameEn" as model_name,
    m."nameEn" as brand,
    sd."url"
  FROM "Price" p
  JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
  JOIN "Variant" v ON p."variantId" = v."id"
  JOIN "CarModel" cm ON v."modelId" = cm."id"
  JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
  WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
),
variant_source_stats AS (
  SELECT
    "variantId",
    variant_name,
    model_name,
    brand,
    COUNT(DISTINCT "sourceDocumentId") as source_count,
    MIN("amount") as min_price,
    MAX("amount") as max_price,
    AVG("amount") as avg_price,
    CASE
      WHEN MIN("amount") > 0 THEN (MAX("amount") - MIN("amount")) / MIN("amount") * 100
      ELSE 0
    END as price_spread_pct
  FROM active_prices
  GROUP BY "variantId", variant_name, model_name, brand
  HAVING COUNT(DISTINCT "sourceDocumentId") >= 3
)
SELECT
  s."variantId",
  s.brand,
  s.model_name,
  s.variant_name,
  s.source_count,
  s.min_price,
  s.max_price,
  s.avg_price,
  ROUND(s.price_spread_pct::numeric, 1) as spread_pct,
  'DISAGREEMENT_' || ROUND(s.price_spread_pct::numeric, 0) || 'PCT' as reason,
  STRING_AGG(DISTINCT ap.url, ' | ') as source_urls
FROM variant_source_stats s
JOIN active_prices ap ON s."variantId" = ap."variantId"
WHERE s.price_spread_pct > 20
GROUP BY s."variantId", s.brand, s.model_name, s.variant_name, s.source_count, s.min_price, s.max_price, s.avg_price, s.price_spread_pct
ORDER BY s.price_spread_pct DESC;


-- ============================================================================
-- SECTION 4: Stale Current Prices (fetched >6 months ago)
-- ============================================================================
SELECT '=== SECTION 4: STALE CURRENT PRICES (>6 months since fetch) ===' as section;

SELECT
  p."id" as price_id,
  m."nameEn" as brand,
  cm."nameEn" as model,
  v."nameEn" as variant,
  p."amount",
  sd."fetchedAt",
  p."observedAt",
  NOW() - sd."fetchedAt" as age,
  EXTRACT(DAY FROM NOW() - sd."fetchedAt") as days_since_fetch,
  sd."url"
FROM "Price" p
JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
JOIN "Variant" v ON p."variantId" = v."id"
JOIN "CarModel" cm ON v."modelId" = cm."id"
JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
WHERE p."isCurrent" = true
  AND (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
  AND sd."fetchedAt" < NOW() - INTERVAL '6 months'
ORDER BY sd."fetchedAt" ASC;


-- ============================================================================
-- SECTION 5: Variants Without VehicleUniverse Match
-- ============================================================================
SELECT '=== SECTION 5: VARIANTS WITHOUT VEHICLEUNIVERSE MATCH ===' as section;

SELECT
  p."id" as price_id,
  m."nameEn" as brand,
  cm."nameEn" as model,
  v."nameEn" as variant,
  v."slug" as variant_slug,
  cm."slug" as model_slug,
  p."amount",
  p."isCurrent",
  vu."id" as vu_id,
  vu."nameEn" as vu_name,
  'NO_VU_MATCH' as reason
FROM "Price" p
JOIN "Variant" v ON p."variantId" = v."id"
JOIN "CarModel" cm ON v."modelId" = cm."id"
JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
LEFT JOIN "VehicleUniverse" vu ON vu."variantId" = v."id"
WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
  AND vu."id" IS NULL
ORDER BY m."nameEn", cm."nameEn", v."nameEn";


-- ============================================================================
-- SECTION 6: QUARANTINE REPORT - Grouped by Brand, Model, Reason
-- ============================================================================
SELECT '=== SECTION 6: QUARANTINE REPORT ===' as section;

WITH suspicious_prices AS (
  -- Section 1: Toyota URL series_code mismatch
  SELECT
    p."id" as price_id,
    m."nameEn" as brand,
    cm."nameEn" as model,
    v."nameEn" as variant,
    p."amount",
    'URL_SERIES_CODE_MISMATCH' as reason,
    sd."url" as detail
  FROM "Price" p
  JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
  JOIN "Variant" v ON p."variantId" = v."id"
  JOIN "CarModel" cm ON v."modelId" = cm."id"
  JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
  WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
    AND sd."url" LIKE '%toyota.co.th%series_code=%'
    AND NOT (
      lower(replace(replace(replace(replace(cm."nameEn", ' ', ''), '-', ''), '_', ''), '/', '')) LIKE '%' ||
      lower(regexp_replace(regexp_replace(sd."url", '.*series_code=([^&]+).*', '\1'), '[ _-]', '', 'g')) || '%'
      OR lower(regexp_replace(regexp_replace(sd."url", '.*series_code=([^&]+).*', '\1'), '[ _-]', '', 'g')) LIKE '%' ||
      lower(replace(replace(replace(replace(cm."nameEn", ' ', ''), '-', ''), '_', ''), '/', '')) || '%'
    )

  UNION ALL

  -- Section 2: Suspiciously high prices
  SELECT
    p."id",
    m."nameEn",
    cm."nameEn",
    v."nameEn",
    p."amount",
    CASE
      WHEN m."nameEn" IN ('Toyota', 'Honda', 'Mazda', 'Nissan', 'Mitsubishi', 'Isuzu', 'MG', 'BYD', 'Hyundai', 'Kia', 'Suzuki', 'Subaru', 'Ford', 'Chevrolet')
        THEN 'ECONOMY_PRICE_EXCEEDED_' || ROUND(p."amount"/1000000, 1) || 'M'
      ELSE 'LUXURY_PRICE_EXCEEDED_' || ROUND(p."amount"/1000000, 1) || 'M'
    END,
    sd."url"
  FROM "Price" p
  JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
  JOIN "Variant" v ON p."variantId" = v."id"
  JOIN "CarModel" cm ON v."modelId" = cm."id"
  JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
  WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
    AND (
      (m."nameEn" IN ('Toyota', 'Honda', 'Mazda', 'Nissan', 'Mitsubishi', 'Isuzu', 'MG', 'BYD', 'Hyundai', 'Kia', 'Suzuki', 'Subaru', 'Ford', 'Chevrolet') AND p."amount" > 2000000)
      OR (m."nameEn" IN ('Lexus', 'BMW', 'Mercedes-Benz', 'Mercedes', 'Audi', 'Porsche', 'Volvo', 'Jaguar', 'Land Rover', 'Mini') AND p."amount" > 5000000)
      OR (m."nameEn" NOT IN ('Toyota', 'Honda', 'Mazda', 'Nissan', 'Mitsubishi', 'Isuzu', 'MG', 'BYD', 'Hyundai', 'Kia', 'Suzuki', 'Subaru', 'Ford', 'Chevrolet', 'Lexus', 'BMW', 'Mercedes-Benz', 'Mercedes', 'Audi', 'Porsche', 'Volvo', 'Jaguar', 'Land Rover', 'Mini') AND p."amount" > 5000000)
    )

  UNION ALL

  -- Section 3: Cross-source disagreement (flag all prices for that variant)
  SELECT
    p."id",
    m."nameEn",
    cm."nameEn",
    v."nameEn",
    p."amount",
    'CROSS_SOURCE_DISAGREEMENT_' ||
      ROUND(((MAX(p."amount") OVER (PARTITION BY p."variantId") - MIN(p."amount") OVER (PARTITION BY p."variantId")) /
             NULLIF(MIN(p."amount") OVER (PARTITION BY p."variantId"), 0)) * 100, 0) || 'PCT' as reason,
    sd."url"
  FROM "Price" p
  JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
  JOIN "Variant" v ON p."variantId" = v."id"
  JOIN "CarModel" cm ON v."modelId" = cm."id"
  JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
  WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
    AND p."variantId" IN (
      SELECT "variantId"
      FROM "Price" p2
      WHERE (p2."quarantineStatus" IS NULL OR p2."quarantineStatus" != 'quarantined')
      GROUP BY "variantId"
      HAVING COUNT(DISTINCT "sourceDocumentId") >= 3
        AND (MAX("amount") - MIN("amount")) / NULLIF(MIN("amount"), 0) * 100 > 20
    )

  UNION ALL

  -- Section 4: Stale current prices
  SELECT
    p."id",
    m."nameEn",
    cm."nameEn",
    v."nameEn",
    p."amount",
    'STALE_CURRENT_' || EXTRACT(DAY FROM NOW() - sd."fetchedAt")::int || 'DAYS',
    sd."url"
  FROM "Price" p
  JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
  JOIN "Variant" v ON p."variantId" = v."id"
  JOIN "CarModel" cm ON v."modelId" = cm."id"
  JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
  WHERE p."isCurrent" = true
    AND (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
    AND sd."fetchedAt" < NOW() - INTERVAL '6 months'

  UNION ALL

  -- Section 5: No VehicleUniverse match
  SELECT
    p."id",
    m."nameEn",
    cm."nameEn",
    v."nameEn",
    p."amount",
    'NO_VU_MATCH',
    sd."url"
  FROM "Price" p
  JOIN "Variant" v ON p."variantId" = v."id"
  JOIN "CarModel" cm ON v."modelId" = cm."id"
  JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
  JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
  LEFT JOIN "VehicleUniverse" vu ON vu."variantId" = v."id"
  WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
    AND vu."id" IS NULL
),

-- Deduplicate: one price_id can appear in multiple checks
deduplicated AS (
  SELECT DISTINCT ON (price_id)
    price_id, brand, model, variant, amount, reason, detail
  FROM suspicious_prices
  ORDER BY price_id, reason
)

-- Grouped summary
SELECT
  brand,
  model,
  COUNT(DISTINCT price_id) as suspicious_count,
  STRING_AGG(DISTINCT reason, ' | ') as reasons,
  ARRAY_AGG(DISTINCT variant) as affected_variants,
  MIN(amount) as min_amount,
  MAX(amount) as max_amount,
  SUM(CASE WHEN reason LIKE '%ECONOMY%' OR reason LIKE '%LUXURY%' THEN 1 ELSE 0 END) as high_price_count,
  SUM(CASE WHEN reason LIKE '%URL%' THEN 1 ELSE 0 END) as url_mismatch_count,
  SUM(CASE WHEN reason LIKE '%DISAGREEMENT%' THEN 1 ELSE 0 END) as disagreement_count,
  SUM(CASE WHEN reason LIKE '%STALE%' THEN 1 ELSE 0 END) as stale_count,
  SUM(CASE WHEN reason LIKE '%NO_VU%' THEN 1 ELSE 0 END) as vu_missing_count
FROM deduplicated
GROUP BY brand, model
ORDER BY suspicious_count DESC, brand, model;


-- ============================================================================
-- SECTION 7: TOTAL QUARANTINE SUMMARY
-- ============================================================================
SELECT '=== SECTION 7: QUARANTINE SUMMARY ===' as section;

WITH suspicious_prices AS (
  SELECT p."id" as price_id, 'URL_SERIES_CODE_MISMATCH' as reason
  FROM "Price" p
  JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
  JOIN "Variant" v ON p."variantId" = v."id"
  JOIN "CarModel" cm ON v."modelId" = cm."id"
  WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
    AND sd."url" LIKE '%toyota.co.th%series_code=%'
    AND NOT (
      lower(replace(replace(replace(replace(cm."nameEn", ' ', ''), '-', ''), '_', ''), '/', '')) LIKE '%' ||
      lower(regexp_replace(regexp_replace(sd."url", '.*series_code=([^&]+).*', '\1'), '[ _-]', '', 'g')) || '%'
      OR lower(regexp_replace(regexp_replace(sd."url", '.*series_code=([^&]+).*', '\1'), '[ _-]', '', 'g')) LIKE '%' ||
      lower(replace(replace(replace(replace(cm."nameEn", ' ', ''), '-', ''), '_', ''), '/', '')) || '%'
    )
  UNION ALL
  SELECT p."id", 'HIGH_PRICE'
  FROM "Price" p
  JOIN "Variant" v ON p."variantId" = v."id"
  JOIN "CarModel" cm ON v."modelId" = cm."id"
  JOIN "Manufacturer" m ON cm."manufacturerId" = m."id"
  WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
    AND (
      (m."nameEn" IN ('Toyota', 'Honda', 'Mazda', 'Nissan', 'Mitsubishi', 'Isuzu', 'MG', 'BYD', 'Hyundai', 'Kia', 'Suzuki', 'Subaru', 'Ford', 'Chevrolet') AND p."amount" > 2000000)
      OR (m."nameEn" IN ('Lexus', 'BMW', 'Mercedes-Benz', 'Mercedes', 'Audi', 'Porsche', 'Volvo', 'Jaguar', 'Land Rover', 'Mini') AND p."amount" > 5000000)
      OR (m."nameEn" NOT IN ('Toyota', 'Honda', 'Mazda', 'Nissan', 'Mitsubishi', 'Isuzu', 'MG', 'BYD', 'Hyundai', 'Kia', 'Suzuki', 'Subaru', 'Ford', 'Chevrolet', 'Lexus', 'BMW', 'Mercedes-Benz', 'Mercedes', 'Audi', 'Porsche', 'Volvo', 'Jaguar', 'Land Rover', 'Mini') AND p."amount" > 5000000)
    )
  UNION ALL
  SELECT p."id", 'DISAGREEMENT'
  FROM "Price" p
  WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
    AND p."variantId" IN (
      SELECT "variantId" FROM "Price"
      WHERE ("quarantineStatus" IS NULL OR "quarantineStatus" != 'quarantined')
      GROUP BY "variantId"
      HAVING COUNT(DISTINCT "sourceDocumentId") >= 3
        AND (MAX("amount") - MIN("amount")) / NULLIF(MIN("amount"), 0) * 100 > 20
    )
  UNION ALL
  SELECT p."id", 'STALE'
  FROM "Price" p
  JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd."id"
  WHERE p."isCurrent" = true
    AND (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
    AND sd."fetchedAt" < NOW() - INTERVAL '6 months'
  UNION ALL
  SELECT p."id", 'NO_VU'
  FROM "Price" p
  JOIN "Variant" v ON p."variantId" = v."id"
  LEFT JOIN "VehicleUniverse" vu ON vu."variantId" = v."id"
  WHERE (p."quarantineStatus" IS NULL OR p."quarantineStatus" != 'quarantined')
    AND vu."id" IS NULL
)
SELECT
  COUNT(DISTINCT price_id) as total_suspicious_prices,
  COUNT(*) as total_suspicious_records
FROM suspicious_prices;
