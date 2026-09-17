import { NextResponse } from "next/server";
import pool from "@/lib/db-pg";

export const dynamic = "force-dynamic";

export function parseCarQuery(searchParams: URLSearchParams) {
  return Object.fromEntries(searchParams.entries());
}

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const limit = Math.min(parseInt(url.searchParams.get("limit") || "24"), 100);
    const page = Math.max(parseInt(url.searchParams.get("page") || "1"), 1);
    const offset = (page - 1) * limit;
    const fuelType = url.searchParams.get("fuelType");
    const manufacturer = url.searchParams.get("manufacturer");
    const maxPrice = url.searchParams.get("maxPrice");

    let whereClause = `WHERE v.status = 'ACTIVE' AND cm.status = 'ACTIVE' AND m.status = 'ACTIVE'`;
    const params: any[] = [];
    let paramIdx = 1;

    if (fuelType) {
      whereClause += ` AND v."fuelType" = $${paramIdx++}`;
      params.push(fuelType);
    }
    if (manufacturer) {
      whereClause += ` AND (m.slug = $${paramIdx++} OR m."nameEn" ILIKE $${paramIdx++})`;
      params.push(manufacturer, `%${manufacturer}%`);
    }
    if (maxPrice) {
      whereClause += ` AND EXISTS (SELECT 1 FROM "Price" p WHERE p."variantId" = v.id AND p."isCurrent" = true AND p.amount <= $${paramIdx++})`;
      params.push(parseInt(maxPrice));
    }

    const countResult: any = await pool.query(
      `SELECT COUNT(*) as total FROM "Variant" v JOIN "CarModel" cm ON cm.id = v."modelId" JOIN "Manufacturer" m ON m.id = cm."manufacturerId" ${whereClause}`,
      params
    );
    const total = parseInt(countResult.rows[0].total);

    const result: any = await pool.query(
      `SELECT v.id, v."nameTh", v."nameEn", v.slug, v."fuelType", v."modelYear",
        m."nameEn" as "manufacturerName", m.slug as "manufacturerSlug",
        m."nameTh" as "manufacturerTh",
        cm."nameEn" as "modelName", cm.slug as "modelSlug",
        cm."nameTh" as "modelTh"
      FROM "Variant" v
      JOIN "CarModel" cm ON cm.id = v."modelId"
      JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
      ${whereClause}
      ORDER BY m."nameEn", cm."nameEn", v."nameEn"
      LIMIT $${paramIdx++} OFFSET $${paramIdx++}`,
      [...params, limit, offset]
    );

    const stats: any = await pool.query(`
      SELECT 
        (SELECT COUNT(*) FROM "Manufacturer" WHERE status = 'ACTIVE')::int as "totalManufacturers",
        (SELECT COUNT(*) FROM "Variant" WHERE status = 'ACTIVE' AND "fuelType" = 'EV')::int as "evCount",
        (SELECT COUNT(*) FROM "Variant" WHERE status = 'ACTIVE' AND "fuelType" = 'HEV')::int as "hevCount"
    `);

    return NextResponse.json({
      results: result.rows.map((row: any) => ({
        ...row,
        prices: [],
        media: [],
      })),
      total,
      page,
      limit,
      hasMore: offset + limit < total,
      ...stats.rows[0],
    });
  } catch (error) {
    console.error("API /api/cars error:", error);
    return NextResponse.json({ error: "catalog_unavailable", results: [], total: 0, page: 1, limit: 24, hasMore: false, totalManufacturers: 0, evCount: 0, hevCount: 0 }, { status: 503 });
  }
}
