import type { CatalogFilters, CatalogPage } from "../catalog/types";
import { searchCatalog } from "../catalog/queries";
import { searchVectorEvidence, type VectorEvidence, type VectorSearchResult } from "./vector-search";
import { applyEvidenceThresholds, type GatedEvidence } from "../ai/retrieval/evidence-gate-policy";

export type SearchMode = "hybrid" | "structured-fallback";
export type HybridSearchResult = CatalogPage & { vectorAvailable: boolean; searchMode: SearchMode; evidence: VectorEvidence[] };

type HybridDependencies = {
  searchCatalog?: (filters: CatalogFilters) => Promise<CatalogPage>;
  vectorSearch?: (query: string, options?: { limit?: number }) => Promise<VectorSearchResult>;
};

/** Structured catalog remains authoritative; vectors only add discoverable evidence. */
export async function searchHybrid(filters: CatalogFilters, dependencies: HybridDependencies = {}): Promise<HybridSearchResult> {
  const catalog = await (dependencies.searchCatalog ?? ((input) => searchCatalog(input)))(filters);
  if (!filters.q?.trim()) return { ...catalog, vectorAvailable: false, searchMode: "structured-fallback", evidence: [] };
  try {
    const vector = await (dependencies.vectorSearch ?? searchVectorEvidence)(filters.q, { limit: filters.limit });
    if (!vector.available) return { ...catalog, vectorAvailable: false, searchMode: "structured-fallback", evidence: [] };
    // P115: every returned row must survive the deterministic retrieval
    // gates (source/entity/distance/identity) — raw hits never surface.
    const gated = applyEvidenceThresholds(filters.q, vector);
    const evidence: VectorEvidence[] = gated.evidence.map((row) => {
      const { qualified, ...rest } = row as GatedEvidence;
      void qualified; // qualification is an internal gate marker, not response shape
      return rest;
    });
    return { ...catalog, vectorAvailable: true, searchMode: "hybrid", evidence };
  } catch {
    return { ...catalog, vectorAvailable: false, searchMode: "structured-fallback", evidence: [] };
  }
}
