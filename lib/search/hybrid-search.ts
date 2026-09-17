import type { CatalogFilters, CatalogPage } from "../catalog/types";
import { searchCatalog } from "../catalog/queries";
import { searchVectorEvidence, type VectorEvidence, type VectorSearchResult } from "./vector-search";

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
    return { ...catalog, vectorAvailable: vector.available, searchMode: vector.available ? "hybrid" : "structured-fallback", evidence: vector.available ? vector.evidence : [] };
  } catch {
    return { ...catalog, vectorAvailable: false, searchMode: "structured-fallback", evidence: [] };
  }
}
