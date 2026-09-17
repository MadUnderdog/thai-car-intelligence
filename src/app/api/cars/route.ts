import { NextResponse } from "next/server";
import { listVariants } from "../../../../lib/catalog/queries";
import type { CatalogFilters } from "../../../../lib/catalog/types";

export const dynamic = "force-dynamic";

export function parseCarQuery(searchParams: URLSearchParams): CatalogFilters | null {
  const limitRaw = searchParams.get("limit");
  const pageRaw = searchParams.get("page");
  const maxPriceRaw = searchParams.get("maxPrice");

  const limit = limitRaw ? Number(limitRaw) : undefined;
  if (limit !== undefined && (!Number.isFinite(limit) || limit < 1 || limit > 100)) return null;

  const page = pageRaw ? Number(pageRaw) : undefined;
  if (page !== undefined && (!Number.isFinite(page) || page < 1)) return null;

  const maxPrice = maxPriceRaw ? Number(maxPriceRaw) : undefined;
  if (maxPrice !== undefined && (!Number.isFinite(maxPrice) || maxPrice < 0)) return null;

  return {
    manufacturer: searchParams.get("manufacturer") || undefined,
    fuelType: searchParams.get("fuelType") || undefined,
    maxPrice,
    limit,
    page,
  };
}

export async function GET(request: Request) {
  try {
    const filters = parseCarQuery(new URL(request.url).searchParams);
    if (filters === null) {
      return NextResponse.json({ error: "invalid_params", results: [], total: 0, page: 1, limit: 24, hasMore: false }, { status: 400 });
    }
    const result = await listVariants(filters);
    return NextResponse.json(result);
  } catch (error) {
    console.error("API /api/cars error:", error);
    return NextResponse.json({ error: "catalog_unavailable", results: [], total: 0, page: 1, limit: 24, hasMore: false }, { status: 503 });
  }
}
