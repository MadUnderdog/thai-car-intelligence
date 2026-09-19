import { NextResponse } from "next/server";
import pool from "@/lib/db-pg";
import { validateFuelType, validateLimit } from "../../../../lib/validation/api-params";
import { KNOWN_BODY_TYPES } from "../../../../lib/ai/retrieval/body-type-intent";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const manufacturer = url.searchParams.get("manufacturer");
    const fuelType = validateFuelType(url.searchParams.get("fuelType"));
    const bodyTypeParam = url.searchParams.get("bodyType");
    const minPrice = url.searchParams.get("minPrice");
    const maxPrice = url.searchParams.get("maxPrice");
    const sortBy = url.searchParams.get("sortBy") || "name_asc";
    const q = url.searchParams.get("q");
    const limit = validateLimit(url.searchParams.get("limit"), 50);

    if (limit === null) {
      return NextResponse.json({ error: "invalid_params", results: [], total: 0 }, { status: 400 });
    }

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
    if (q) {
      whereClause += ` AND (cm."nameEn" ILIKE $${paramIdx++} OR cm."nameTh" ILIKE $${paramIdx} OR m."nameEn" ILIKE $${paramIdx++})`;
      params.push(`%${q}%`);
    }
    // Price range filter on verified prices only
    if (minPrice) {
      const minP = parseFloat(minPrice);
      if (!isNaN(minP) && minP >= 0) {
        whereClause += ` AND EXISTS (SELECT 1 FROM "Variant" v2 JOIN "Price" p2 ON p2."variantId" = v2.id WHERE v2."modelId" = cm.id AND p2."isCurrent" = true AND p2."sourceDocumentId" IS NOT NULL AND EXISTS (SELECT 1 FROM "SourceDocument" sd WHERE sd.id = p2."sourceDocumentId" AND sd.status = 'VERIFIED') AND p2.amount >= $${paramIdx++})`;
        params.push(minP);
      }
    }
    if (maxPrice) {
      const maxP = parseFloat(maxPrice);
      if (!isNaN(maxP) && maxP > 0) {
        whereClause += ` AND EXISTS (SELECT 1 FROM "Variant" v3 JOIN "Price" p3 ON p3."variantId" = v3.id WHERE v3."modelId" = cm.id AND p3."isCurrent" = true AND p3."sourceDocumentId" IS NOT NULL AND EXISTS (SELECT 1 FROM "SourceDocument" sd WHERE sd.id = p3."sourceDocumentId" AND sd.status = 'VERIFIED') AND p3.amount <= $${paramIdx++})`;
        params.push(maxP);
      }
    }

    let orderBy = `m."nameEn", cm."nameEn"`;
    if (sortBy === "price_asc") orderBy = `MIN(p.amount) ASC NULLS LAST, m."nameEn"`;
    if (sortBy === "price_desc") orderBy = `MIN(p.amount) DESC NULLS LAST, m."nameEn"`;

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
         AND p."sourceDocumentId" IS NOT NULL
         AND EXISTS (SELECT 1 FROM "SourceDocument" sd WHERE sd.id = p."sourceDocumentId" AND sd.status = 'VERIFIED')
       ${whereClause}
       GROUP BY cm.id, m.id
       ORDER BY ${orderBy}
       LIMIT $${paramIdx++}`,
      [...params, limit]
    );

    let rows = result.rows.map((row: any) => ({
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
    }));

    // Body-type filter (server-side via slug mapping)
    if (bodyTypeParam) {
      rows = rows.filter((r: any) => KNOWN_BODY_TYPES[r.slug] === bodyTypeParam);
    }

    return NextResponse.json({ results: rows, total: rows.length });
  } catch (error) {
    console.error("API /api/models error:", error);
    return NextResponse.json({ error: "catalog_unavailable", results: [], total: 0 }, { status: 503 });
  }
}
