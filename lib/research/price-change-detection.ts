import db from "../db";
import { createChangeCandidate } from "./refresh-pipeline";

export type PriceChangeCandidate = {
  variantId: string;
  variantName: string;
  modelName: string;
  brandName: string;
  oldPrice: number;
  newPrice: number;
  sourceUrl: string;
  sourceTier: string;
  detectedAt: Date;
};

/**
 * Compare a newly discovered price against the current database price.
 * If different, create a change candidate.
 */
export async function detectPriceChange(params: {
  variantId: string;
  newPrice: number;
  sourceUrl: string;
  sourceTier: string;
}): Promise<PriceChangeCandidate | null> {
  const current = await db.$queryRaw<{ amount: number }[]>`SELECT p.amount FROM "Price" p WHERE p."variantId" = ${params.variantId}::uuid AND p."isCurrent" = true ORDER BY p.amount ASC LIMIT 1`;

  if (current.length === 0) return null;

  const currentPrice = Number(current[0].amount);
  if (currentPrice === params.newPrice) return null;

  // Get variant info for the candidate
  const variant = await db.$queryRaw<{ nameEn: string; modelName: string; brandName: string }[]>`SELECT v."nameEn", cm."nameEn" as "modelName", m."nameEn" as "brandName" FROM "Variant" v JOIN "CarModel" cm ON cm.id = v."modelId" JOIN "Manufacturer" m ON m.id = cm."manufacturerId" WHERE v.id = ${params.variantId}::uuid`;

  if (variant.length === 0) return null;

  const v = variant[0];

  // Idempotency: check if candidate already exists for same entity/field/value
  const existing = await db.$queryRaw<{ id: string }[]>`SELECT id FROM "ChangeCandidate" WHERE entity_type = 'price' AND entity_id = ${params.variantId}::uuid AND field_name = 'amount' AND new_value = ${String(params.newPrice)} AND status NOT IN ('REJECTED') LIMIT 1`;
  if (existing.length > 0) return null;

  await createChangeCandidate({
    entityType: "price",
    entityId: params.variantId,
    fieldName: "amount",
    oldValue: String(currentPrice),
    newValue: String(params.newPrice),
    sourceUrl: params.sourceUrl,
    sourceTier: params.sourceTier,
  });

  return {
    variantId: params.variantId,
    variantName: v.nameEn,
    modelName: v.modelName,
    brandName: v.brandName,
    oldPrice: currentPrice,
    newPrice: params.newPrice,
    sourceUrl: params.sourceUrl,
    sourceTier: params.sourceTier,
    detectedAt: new Date(),
  };
}

/**
 * Batch check multiple prices against current database values.
 */
export async function batchDetectPriceChanges(
  prices: { variantId: string; newPrice: number; sourceUrl: string; sourceTier: string }[]
): Promise<PriceChangeCandidate[]> {
  const candidates: PriceChangeCandidate[] = [];
  for (const p of prices) {
    const candidate = await detectPriceChange(p);
    if (candidate) candidates.push(candidate);
  }
  return candidates;
}
