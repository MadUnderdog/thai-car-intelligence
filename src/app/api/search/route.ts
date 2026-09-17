import { NextResponse } from "next/server";
import { searchCatalog } from "../../../../lib/catalog/queries";
import type { CatalogFilters } from "../../../../lib/catalog/types";
import { validateFuelType, validateLimit, validatePage, validateMaxPrice, MAX_QUERY_LENGTH } from "../../../../lib/validation/api-params";

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

  return {
    q,
    manufacturer: searchParams.get("manufacturer") || undefined,
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
    const result = await searchCatalog(filters);
    return NextResponse.json({ ...result, vectorAvailable: false });
  } catch (error) {
    console.error("API /api/search error:", error);
    const url = new URL(request.url);
    const limit = validateLimit(url.searchParams.get("limit"), DEFAULT_LIMIT) ?? DEFAULT_LIMIT;
    return NextResponse.json({ error: "catalog_unavailable", results: [], total: 0, page: 1, limit, hasMore: false, vectorAvailable: false }, { status: 503 });
  }
}
