import { NextResponse } from "next/server";
import { listVariants } from "../../../../lib/catalog/queries";
import type { CatalogFilters } from "../../../../lib/catalog/types";
import { validateFuelType, validateLimit, validatePage, validateMaxPrice } from "../../../../lib/validation/api-params";

export const dynamic = "force-dynamic";

export function parseCarQuery(searchParams: URLSearchParams): CatalogFilters | null {
  const limit = validateLimit(searchParams.get("limit"));
  if (searchParams.has("limit") && limit === null) return null;

  const page = validatePage(searchParams.get("page"));
  if (searchParams.has("page") && page === null) return null;

  const maxPrice = validateMaxPrice(searchParams.get("maxPrice"));
  if (searchParams.has("maxPrice") && maxPrice === null) return null;

  const fuelType = validateFuelType(searchParams.get("fuelType"));

  return {
    manufacturer: searchParams.get("manufacturer") || undefined,
    fuelType: fuelType || undefined,
    maxPrice: maxPrice ?? undefined,
    limit: limit ?? undefined,
    page: page ?? undefined,
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
