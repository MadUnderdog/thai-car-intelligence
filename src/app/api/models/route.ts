import { NextResponse } from "next/server";
import pool from "@/lib/db-pg";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const manufacturer = url.searchParams.get("manufacturer");
    const fuelType = url.searchParams.get("fuelType");
    const limit = Math.min(parseInt(url.searchParams.get("limit") || "50"), 100);

    let whereClause = `WHERE cm.status = 'ACTIVE' AND m.status = 'ACTIVE'`;
    const params: any[] = [];
    let paramIdx = 1;

    if (manufacturer) {
      whereClause += ` AND (m.slug = $${paramIdx++} OR m."nameEn" ILIKE $${paramIdx++})`;
      params.push(manufacturer, `%${manufacturer}%`);
    }
    if (fuelType) {
      whereClause += ` AND EXISTS (SELECT 1 FROM "Variant" v WHERE v."modelId" = cm.id AND v."fuelType" = $${paramIdx++} AND v.status = 'ACTIVE')`;
      params.push(fuelType);
    }

    const result: any = await pool.query(
      `SELECT 
        cm.id, cm."nameEn", cm."nameTh", cm.slug,
        m."nameEn" as "mfrName", m."nameTh" as "mfrTh", m.slug as "mfrSlug",
        MIN(p.amount) as "minPrice",
        MAX(p.amount) as "maxPrice",
        COUNT(DISTINCT v.id) as "variantCount",
        MODE() WITHIN GROUP (ORDER BY v."fuelType") as "primaryFuelType",
        (SELECT med.url FROM "Media" med WHERE med."modelId" = cm.id AND med.role = 'hero' LIMIT 1) as "heroImage"
       FROM "CarModel" cm
       JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
       LEFT JOIN "Variant" v ON v."modelId" = cm.id AND v.status = 'ACTIVE'
       LEFT JOIN "Price" p ON p."variantId" = v.id AND p."isCurrent" = true
       ${whereClause}
       GROUP BY cm.id, m.id
       ORDER BY m."nameEn", cm."nameEn"
       LIMIT $${paramIdx++}`,
      [...params, limit]
    );

    return NextResponse.json({
      results: result.rows.map((row: any) => ({
        id: row.id,
        nameEn: row.nameEn,
        nameTh: row.nameTh,
        slug: row.slug,
        manufacturer: { nameEn: row.mfrName, nameTh: row.mfrTh, slug: row.mfrSlug },
        minPrice: row.minPrice ? Number(row.minPrice) : null,
        maxPrice: row.maxPrice ? Number(row.maxPrice) : null,
        variantCount: Number(row.variantCount),
        primaryFuelType: row.primaryFuelType,
        heroImage: row.heroImage,
      })),
      total: result.rows.length,
    });
  } catch (error) {
    console.error("API /api/models error:", error);
    return NextResponse.json({ error: "catalog_unavailable", results: [], total: 0 }, { status: 503 });
  }
}
