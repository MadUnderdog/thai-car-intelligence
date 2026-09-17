-- Vehicle Data Completeness Score
-- Computes per-model completeness from verified data only.

CREATE OR REPLACE VIEW vehicle_completeness AS
WITH model_stats AS (
  SELECT
    cm.id AS model_id,
    m.id AS manufacturer_id,
    m."nameEn" AS brand,
    cm."nameEn" AS model_name,
    -- identity
    CASE WHEN cm."nameEn" IS NOT NULL AND cm."nameTh" IS NOT NULL THEN 100 ELSE 50 END AS identity_score,
    -- variant coverage: how many variants have at least one current price
    ROUND(
      100.0 * COUNT(DISTINCT CASE WHEN p."isCurrent" = true THEN v.id END) /
      GREATEST(COUNT(DISTINCT v.id), 1)
    ) AS variant_price_coverage,
    -- spec coverage
    ROUND(
      100.0 * COUNT(DISTINCT vs."variantId") /
      GREATEST(COUNT(DISTINCT v.id), 1)
    ) AS spec_coverage,
    -- image coverage
    ROUND(
      100.0 * COUNT(DISTINCT med."variantId") /
      GREATEST(COUNT(DISTINCT v.id), 1)
    ) AS image_coverage,
    -- feature coverage
    ROUND(
      100.0 * COUNT(DISTINCT vf."variantId") /
      GREATEST(COUNT(DISTINCT v.id), 1)
    ) AS feature_coverage,
    -- source docs
    (SELECT count(*) FROM "SourceDocument" sd
     JOIN "Source" s ON s.id = sd."sourceId"
     WHERE s."manufacturerId" = m.id) AS source_docs,
    -- embeddings
    (SELECT count(*) FROM "Embedding" e
     JOIN "SourceDocument" sd ON sd.id = e."sourceDocumentId"
     JOIN "Source" s ON s.id = sd."sourceId"
     WHERE s."manufacturerId" = m.id) AS embedding_chunks,
    -- counts
    COUNT(DISTINCT v.id) AS variant_count,
    COUNT(DISTINCT CASE WHEN p."isCurrent" = true THEN p.id END) AS price_count
  FROM "CarModel" cm
  JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
  LEFT JOIN "Variant" v ON v."modelId" = cm.id
  LEFT JOIN "Price" p ON p."variantId" = v.id
  LEFT JOIN "VariantSpec" vs ON vs."variantId" = v.id
  LEFT JOIN "Media" med ON med."variantId" = v.id
  LEFT JOIN "VariantFeature" vf ON vf."variantId" = v.id
  GROUP BY cm.id, m.id, m."nameEn", cm."nameEn"
)
SELECT
  brand,
  model_name,
  variant_count,
  price_count,
  identity_score,
  variant_price_coverage AS price_pct,
  spec_coverage AS spec_pct,
  image_coverage AS image_pct,
  feature_coverage AS feature_pct,
  source_docs,
  embedding_chunks,
  ROUND((identity_score + variant_price_coverage + spec_coverage + image_coverage + feature_coverage) / 5.0) AS overall_pct
FROM model_stats
ORDER BY overall_pct DESC, brand, model_name;
