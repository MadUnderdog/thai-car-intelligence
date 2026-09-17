import { NextResponse } from "next/server";
import { searchCatalog } from "../../../../lib/catalog/queries";
import type { CatalogFilters } from "../../../../lib/catalog/types";

export const dynamic = "force-dynamic";

const DEFAULT_LIMIT = 24;
const DEFAULT_PAGE = 1;
const MAX_QUERY_LENGTH = 120;

export function parseSearchQuery(searchParams: URLSearchParams): CatalogFilters | null {
  const limitRaw = searchParams.get("limit");
  const pageRaw = searchParams.get("page");
  const maxPriceRaw = searchParams.get("maxPrice");
  const q = searchParams.get("q")?.trim() || undefined;

  if (q && q.length > MAX_QUERY_LENGTH) return null;

  const limit = limitRaw ? Number(limitRaw) : DEFAULT_LIMIT;
  if (!Number.isFinite(limit) || limit < 1 || limit > 100) return null;

  const page = pageRaw ? Number(pageRaw) : DEFAULT_PAGE;
  if (!Number.isFinite(page) || page < 1) return null;

  const maxPrice = maxPriceRaw ? Number(maxPriceRaw) : undefined;
  if (maxPrice !== undefined && (!Number.isFinite(maxPrice) || maxPrice < 0)) return null;

  return {
    q,
    manufacturer: searchParams.get("manufacturer") || undefined,
    fuelType: searchParams.get("fuelType") || undefined,
    maxPrice,
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
    const limit = Math.min(parseInt(url.searchParams.get("limit") || String(DEFAULT_LIMIT)), 100);
    return NextResponse.json({ error: "catalog_unavailable", results: [], total: 0, page: 1, limit, hasMore: false, vectorAvailable: false }, { status: 503 });
  }
}
