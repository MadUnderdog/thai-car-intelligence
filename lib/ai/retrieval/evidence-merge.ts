import { searchVectorEvidence, type VectorEvidence, type VectorSearchResult } from "../../search/vector-search";

export type EvidenceItem = {
  id: string;
  kind: "fact" | "opinion" | "analysis";
  content: string;
  official: boolean;
  metadata?: Record<string, unknown>;
};

export type MergedEvidence = {
  structured: EvidenceItem[];
  vector: VectorEvidence[];
  merged: EvidenceItem[];
  vectorAvailable: boolean;
};

/**
 * Merge structured catalog evidence with vector retrieval evidence.
 * Structured catalog results get priority; vector evidence is supplemental.
 */
export function mergeEvidence(
  structured: EvidenceItem[],
  vectorResult: VectorSearchResult
): MergedEvidence {
  const merged: EvidenceItem[] = [...structured];
  const vectorEvidence: VectorEvidence[] = [];

  if (!vectorResult.available || vectorResult.evidence.length === 0) {
    return { structured, vector: [], merged, vectorAvailable: false };
  }

  // Add vector evidence that doesn't duplicate structured evidence
  const structuredIds = new Set(structured.map((e) => e.metadata?.variantId));
  const seenContents = new Set(structured.map((e) => e.content.substring(0, 50)));

  for (const vec of vectorResult.evidence) {
    vectorEvidence.push(vec);

    // Skip if already in structured evidence
    if (structuredIds.has(vec.entityId)) continue;
    if (seenContents.has(vec.content.substring(0, 50))) continue;

    // Add as supplemental evidence
    merged.push({
      id: `vector:${vec.id}`,
      kind: "fact",
      content: vec.content,
      official: vec.source.sourceType === "OFFICIAL_MANUFACTURER",
      metadata: {
        entityId: vec.entityId,
        entityType: vec.entityType,
        sourceUrl: vec.source.url,
        distance: vec.distance,
      },
    });
    seenContents.add(vec.content.substring(0, 50));
  }

  return { structured, vector: vectorEvidence, merged, vectorAvailable: true };
}

/**
 * Get vector evidence for a query from the database.
 * Returns empty results if embedding is not configured.
 */
export async function getVectorEvidence(query: string): Promise<VectorSearchResult> {
  try {
    return await searchVectorEvidence(query, { limit: 5 });
  } catch (error) {
    console.error("Vector retrieval failed, falling back to structured only:", error);
    return { available: false, evidence: [] };
  }
}
