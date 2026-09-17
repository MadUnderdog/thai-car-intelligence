import type { CatalogVariant } from "../../catalog/types";
import type { VectorEvidence } from "../../search/vector-search";
import type { EvidenceContext } from "../types";

export function buildEvidenceContext(variants: CatalogVariant[], vectorEvidence: VectorEvidence[] = []): EvidenceContext[] {
  const catalogFacts = variants.flatMap((variant) => {
    const base = `${variant.manufacturer.nameTh} ${variant.model.nameTh} ${variant.nameTh}`;
    const facts: EvidenceContext[] = [{ id: `variant:${variant.id}`, kind: "fact", content: base, metadata: { variantId: variant.id } }];
    if (variant.fuelType) facts.push({ id: `fuel:${variant.id}`, kind: "fact", content: `เชื้อเพลิง: ${variant.fuelType}`, metadata: { variantId: variant.id } });
    for (const [index, price] of variant.prices.entries()) {
      facts.push({ id: `price:${variant.id}:${index}`, kind: "fact", content: `ราคา ${price.amount} ${price.currency}`, sourcePageUrl: price.source.url, sourceTitle: price.source.titleTh ?? price.source.titleEn ?? undefined, official: price.source.source.type.startsWith("OFFICIAL"), metadata: { variantId: variant.id, observedAt: price.observedAt } });
    }
    return facts;
  });
  const retrieved = vectorEvidence.map((row): EvidenceContext => ({
    id: `embedding:${row.id}`,
    kind: "fact",
    content: row.content,
    sourcePageUrl: row.source.url,
    sourceTitle: row.source.titleTh ?? row.source.titleEn ?? undefined,
    official: row.source.sourceType.startsWith("OFFICIAL"),
    metadata: { sourceDocumentId: row.sourceDocumentId, pageNumber: row.pageNumber, entityType: row.entityType, entityId: row.entityId, distance: row.distance },
  }));
  return [...catalogFacts, ...retrieved];
}
