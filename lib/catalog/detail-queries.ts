/**
 * P116 — SQL builders for the public vehicle detail page.
 *
 * Extracted from src/app/cars/[manufacturer]/[model]/page.tsx so the price
 * eligibility chain (lib/catalog/price-sql → currentOfficialPrice) and the
 * research/official separation are testable and shared, not copy-pasted.
 */
import { currentOfficialPriceWhere, OFFICIAL_SOURCE_TYPES_SQL } from "./price-sql";

/** Model lookup: BOTH slugs + ACTIVE on model AND manufacturer → 404 otherwise. */
export const detailModelLookupSql = `
  SELECT cm.id, cm."nameEn", cm."nameTh",
         m.id as "mfrId", m."nameEn" as "mfrNameEn", m."nameTh" as "mfrTh", m.slug as "mfrSlug",
         (SELECT s."baseUrl" FROM "Source" s
          WHERE s."manufacturerId" = m.id AND s.status = 'ACTIVE'
            AND s."sourceType" IN ${OFFICIAL_SOURCE_TYPES_SQL}
            AND s."baseUrl" IS NOT NULL
          ORDER BY s."domain" LIMIT 1) as "officialUrl"
  FROM "CarModel" cm
  JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
  WHERE cm.slug = $1 AND m.slug = $2
    AND cm.status = 'ACTIVE' AND m.status = 'ACTIVE'`;

/**
 * Variant rows: price join uses the FULL currentOfficialPrice chain; spec
 * tiers come along so "verified" marks can be tier-honest; price provenance
 * (source url/name + verification date) rides into the view.
 */
export const variantRowsSql = `
  SELECT v.id, v."nameEn", v."nameTh", v.slug, v."fuelType",
    p.amount as price,
    p."sourceDocumentId" IS NOT NULL as "priceVerified",
    sd.url as "priceSourceUrl",
    sd."canonicalUrl" as "priceSourceCanonical",
    psrc."nameEn" as "priceSourceName",
    (SELECT bv."verifiedAt" FROM "BrochureVerification" bv
      WHERE bv."sourceDocumentId" = p."sourceDocumentId" AND bv.status = 'VERIFIED' LIMIT 1) as "lastVerifiedAt",
    ps."powerKw", ps."torqueNm", ps."rangeKm", ps."sourceTier" as "perfTier",
    bs."capacityKwh", bs.chemistry, bs."sourceTier" as "battTier",
    cs."dcPowerKw", cs."acPowerKw", cs."sourceTier" as "chargeTier",
    ds."lengthMm", ds."widthMm", ds."heightMm", ds."wheelbaseMm", ds."groundClearanceMm", ds."sourceTier" as "dimsTier",
    ws."vehicleYears", ws."vehicleDistanceKm", ws."batteryYears", ws."sourceTier" as "warrantyTier"
  FROM "Variant" v
  LEFT JOIN "Price" p ON p."variantId" = v.id AND ${currentOfficialPriceWhere("p")}
  LEFT JOIN "SourceDocument" sd ON sd.id = p."sourceDocumentId"
  LEFT JOIN "Source" psrc ON psrc.id = sd."sourceId"
  LEFT JOIN "PerformanceSpec" ps ON ps."variantId" = v.id
  LEFT JOIN "BatterySpec" bs ON bs."variantId" = v.id
  LEFT JOIN "ChargingSpec" cs ON cs."variantId" = v.id
  LEFT JOIN "DimensionsSpec" ds ON ds."variantId" = v.id
  LEFT JOIN "WarrantySpec" ws ON ws."variantId" = v.id
  WHERE v."modelId" = $1 AND v.status = 'ACTIVE'
  ORDER BY p.amount ASC NULLS LAST`;

/** Research-only observations: ONLY non-VERIFIED documents, never official. */
export const researchRowsSql = `
  SELECT vs."variantId", vs.key, COALESCE(vs."valueTh", vs."valueEn") as value, vs.unit, vs."valueNumeric"
  FROM "VariantSpec" vs JOIN "SourceDocument" sd ON sd.id = vs."sourceDocumentId"
  WHERE vs."variantId" = ANY($1::uuid[]) AND sd.status <> 'VERIFIED'
  ORDER BY vs.key LIMIT 60`;

/** Official brochure/price-list PDF for the brand — verified docs only. */
export const brochureSql = `
  SELECT sd."titleEn", sd."titleTh", sd.url, sd."canonicalUrl", sd."publishedAt",
         s."nameEn" as "sourceName", sd.status::text as "documentStatus",
         (SELECT bv."verifiedAt" FROM "BrochureVerification" bv
          WHERE bv."sourceDocumentId" = sd.id AND bv.status = 'VERIFIED' LIMIT 1) as "verifiedAt"
  FROM "SourceDocument" sd
  JOIN "Source" s ON s.id = sd."sourceId"
  WHERE s."manufacturerId" = $1 AND s.status = 'ACTIVE'
    AND s."sourceType" IN ${OFFICIAL_SOURCE_TYPES_SQL}
    AND sd.status = 'VERIFIED'
    AND (sd."mimeType" = 'application/pdf' OR lower(coalesce(sd."documentType", '')) LIKE '%brochure%')
  ORDER BY sd."publishedAt" DESC NULLS LAST, sd."fetchedAt" DESC NULLS LAST
  LIMIT 1`;
