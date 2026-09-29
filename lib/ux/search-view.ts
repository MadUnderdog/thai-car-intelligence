/**
 * P116 — /api/search response → search UI view model (SearchClient).
 *
 * Consumes the REAL post-P115 contract: CatalogVariant rows are NESTED
 * (manufacturer/model objects + prices[] with source provenance) plus the
 * additive vectorAvailable/searchMode/evidence fields. The legacy flat fields
 * (manufacturerSlug/modelName/…) never existed in the response.
 */

export type SearchUiState = "loading" | "empty" | "error" | "ok";

export type SearchViewRow = {
  variantId: string;
  nameEn: string;
  nameTh: string;
  fuelType: string | null;
  manufacturerName: string;
  manufacturerSlug: string;
  modelName: string;
  modelSlug: string;
  link: string;
  priceAmount: number | null;
  priceType: string | null;
  priceSourceUrl: string | null;
  priceSourceName: string | null;
};

export type SearchView = {
  state: SearchUiState;
  rows: SearchViewRow[];
  searchMode: string | null;
  evidenceCount: number;
  total: number;
};

export function resolveSearchUiState(input: { loading: boolean; ok: boolean; results: unknown[] }): SearchUiState {
  if (input.loading) return "loading";
  if (!input.ok) return "error";
  return input.results.length > 0 ? "ok" : "empty";
}

export function mapSearchResponse(data: any, ok: boolean): SearchView {
  if (!ok || !data || !Array.isArray(data.results)) {
    return { state: "error", rows: [], searchMode: null, evidenceCount: 0, total: 0 };
  }
  const rows: SearchViewRow[] = data.results.map((r: any) => {
    const manufacturerSlug = r?.manufacturer?.slug ?? "";
    const modelSlug = r?.model?.slug ?? "";
    const price = Array.isArray(r?.prices) ? r.prices[0] : null;
    return {
      variantId: r?.id ?? "",
      nameEn: r?.nameEn ?? "",
      nameTh: r?.nameTh ?? "",
      fuelType: r?.fuelType ?? null,
      manufacturerName: r?.manufacturer?.nameEn ?? "",
      manufacturerSlug,
      modelName: r?.model?.nameEn ?? "",
      modelSlug,
      link: `/cars/${manufacturerSlug}/${modelSlug}`,
      priceAmount: price?.amount ?? null,
      priceType: price?.type ?? null,
      priceSourceUrl: price?.source?.url ?? null,
      priceSourceName: price?.source?.source?.nameEn ?? null,
    };
  });
  return {
    state: rows.length > 0 ? "ok" : "empty",
    rows,
    searchMode: typeof data.searchMode === "string" ? data.searchMode : null,
    evidenceCount: Array.isArray(data.evidence) ? data.evidence.length : 0,
    total: typeof data.total === "number" ? data.total : rows.length,
  };
}
