import { NextResponse } from "next/server";
import pool from "@/lib/db-pg";
import { validateFuelType, validateLimit } from "../../../../lib/validation/api-params";
import { KNOWN_BODY_TYPES } from "../../../../lib/ai/retrieval/body-type-intent";
import { currentOfficialPriceWhere } from "../../../../lib/catalog/price-sql";

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
      // P116: one value, three consistent placeholders (the old binding used
      // $N / $N+1 / $N+1 with a single pushed value AND skipped an index →
      // LIMIT $N+2 had no parameter → /api/models?q= returned 503).
      whereClause += ` AND (cm."nameEn" ILIKE $${paramIdx} OR cm."nameTh" ILIKE $${paramIdx} OR m."nameEn" ILIKE $${paramIdx})`;
      params.push(`%${q}%`);
      paramIdx++;
    }
    // Price range filter on FULL currentOfficialPrice chain only
    // (isCurrent + VERIFIED doc + ACTIVE official source + VERIFIED brochure
    //  verification — same predicate as lib/catalog/queries.currentOfficialPrice)
    if (minPrice) {
      const minP = parseFloat(minPrice);
      if (!isNaN(minP) && minP >= 0) {
        whereClause += ` AND EXISTS (SELECT 1 FROM "Variant" v2 JOIN "Price" p2 ON p2."variantId" = v2.id WHERE v2."modelId" = cm.id AND ${currentOfficialPriceWhere("p2")} AND p2.amount >= $${paramIdx++})`;
        params.push(minP);
      }
    }
    if (maxPrice) {
      const maxP = parseFloat(maxPrice);
      if (!isNaN(maxP) && maxP > 0) {
        whereClause += ` AND EXISTS (SELECT 1 FROM "Variant" v3 JOIN "Price" p3 ON p3."variantId" = v3.id WHERE v3."modelId" = cm.id AND ${currentOfficialPriceWhere("p3")} AND p3.amount <= $${paramIdx++})`;
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
        (SELECT med.url FROM "Media" med WHERE med."modelId" = cm.id AND med.role = 'hero' LIMIT 1) as "heroImage",
        (SELECT v0.id FROM "Variant" v0
          LEFT JOIN "Price" p0 ON p0."variantId" = v0.id AND ${currentOfficialPriceWhere("p0")}
          WHERE v0."modelId" = cm.id AND v0.status = 'ACTIVE'
          ORDER BY (p0.amount IS NULL) ASC, p0.amount ASC NULLS LAST, v0."nameEn" ASC, v0.id ASC
          LIMIT 1) as "compareVariantId"
       FROM "CarModel" cm
       JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
       LEFT JOIN "Variant" v ON v."modelId" = cm.id AND v.status = 'ACTIVE'
       LEFT JOIN "Price" p ON p."variantId" = v.id AND ${currentOfficialPriceWhere("p")}
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
      minPrice: row.minPrice !== null && row.minPrice !== undefined ? Number(row.minPrice) : null,
      maxPrice: row.maxPrice !== null && row.maxPrice !== undefined ? Number(row.maxPrice) : null,
      variantCount: Number(row.variantCount),
      primaryFuelType: row.primaryFuelType,
      heroImage: row.heroImage,
      // P116: representative ACTIVE variant for /compare (variant UUID, same
      // kind the /api/compare route accepts — never a model UUID).
      compareVariantId: row.compareVariantId || null,
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
