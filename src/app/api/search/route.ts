import { NextResponse } from "next/server";
import { searchHybrid } from "../../../../lib/search/hybrid-search";
import type { CatalogFilters } from "../../../../lib/catalog/types";
import { validateFuelType, validateLimit, validatePage, validateMaxPrice, MAX_QUERY_LENGTH } from "../../../../lib/validation/api-params";
import { normalizeThaiQuery } from "../../../../lib/search/thai-normalize";
import { parseBrandModelQuery } from "../../../../lib/discovery/exact-model-retrieval";

export const dynamic = "force-dynamic";

const DEFAULT_LIMIT = 24;
const DEFAULT_PAGE = 1;

export function parseSearchQuery(searchParams: URLSearchParams): CatalogFilters | null {
  const q = searchParams.get("q")?.trim() || undefined;
  if (q && q.length > MAX_QUERY_LENGTH) return null;

  const limit = validateLimit(searchParams.get("limit"), DEFAULT_LIMIT);
  if (limit === null) return null;

  const page = validatePage(searchParams.get("page"), DEFAULT_PAGE);
  if (page === null) return null;

  const maxPrice = validateMaxPrice(searchParams.get("maxPrice"));
  if (searchParams.has("maxPrice") && maxPrice === null) return null;

  const fuelType = validateFuelType(searchParams.get("fuelType"));

  // Thai alias normalization: resolve Thai model/brand names to English
  // Use resolved aliases for manufacturer/model filtering, not query string modification
  let resolvedManufacturer = searchParams.get("manufacturer") || undefined;
  let resolvedQ = q;
  if (q) {
    const { resolvedBrands, resolvedModels } = normalizeThaiQuery(q);
    if (resolvedBrands.length > 0 && !resolvedManufacturer) {
      resolvedManufacturer = resolvedBrands[0];
    }
    // Keep only the most specific model phrase: identical values deduped,
    // and a value that is a substring of another resolved value is dropped
    // ("ep" ⊂ "ep plus", "yaris" ⊂ "yaris cross") so the joined phrase can
    // still match — never erase exact entity specificity.
    const uniqueModels = [...new Set(resolvedModels)];
    const maximalModels = uniqueModels.filter(
      (m) => !uniqueModels.some((o) => o.length > m.length && o.includes(m)),
    );
    if (maximalModels.length > 0) {
      resolvedQ = maximalModels.join(" ");
    } else if (resolvedBrands.length > 0) {
      // P115 (G1): explicit model queries must stay model-scoped. English
      // queries don't hit the Thai model map, and the old "brand resolved →
      // q = undefined" branch searched the WHOLE brand (Honda City → CR-V,
      // Civic, Accord…). Scope to the model words via the repo's own
      // brand/model parser. Brand-only queries (no model words) keep the
      // original brand-scoped behavior. Four-digit years map to modelYear,
      // never to name matching, so they don't belong in the phrase.
      const parsed = parseBrandModelQuery(q);
      const modelPhrase = (parsed.model ?? "")
        .split(/\s+/)
        .filter((token) => token && !/^\d{4}$/.test(token))
        .join(" ");
      resolvedQ = modelPhrase || undefined;
    }
  }

  return {
    q: resolvedQ,
    manufacturer: resolvedManufacturer || undefined,
    fuelType: fuelType || undefined,
    maxPrice: maxPrice ?? undefined,
    limit,
    page,
  };
}

export async function GET(request: Request) {
  try {
    const filters = parseSearchQuery(new URL(request.url).searchParams);
    if (filters === null) {
      return NextResponse.json({ error: "invalid_params", results: [], total: 0, page: 1, limit: 24, hasMore: false, vectorAvailable: false }, { status: 400 });
    }
    // P115: structured catalog results come from the same authoritative
    // searchCatalog; vector evidence rides along separately, already gated —
    // it can never add rows to `results`.
    const result = await searchHybrid(filters);
    return NextResponse.json({ ...result });
  } catch (error) {
    console.error("API /api/search error:", error);
    const url = new URL(request.url);
    const limit = validateLimit(url.searchParams.get("limit"), DEFAULT_LIMIT) ?? DEFAULT_LIMIT;
    return NextResponse.json({ error: "catalog_unavailable", results: [], total: 0, page: 1, limit, hasMore: false, vectorAvailable: false }, { status: 503 });
  }
}
