// @ts-nocheck
import { NextResponse } from "next/server";
import pool from "@/lib/db-pg";
import { isValidUuid } from "../../../../lib/validation/api-params";
import { currentOfficialPriceWhere } from "../../../../lib/catalog/price-sql";

export const dynamic = "force-dynamic";

/**
 * P116 compare contract (hardened):
 *  - price rows use the FULL currentOfficialPrice chain (never secondary /
 *    inactive / unverified documents as official)
 *  - response preserves the SELECTED id order (deduped, valid UUIDs only)
 *  - features keep their `available` flag → ✓ / ✗ / ไม่มีข้อมูล three-state
 *  - price carries provenance (sourceUrl + sourceName) for the UI
 */
export async function GET(request: Request) {
  try {
    const params = new URL(request.url).searchParams;
    const ids = params.get("ids");
    if (!ids) return NextResponse.json({ error: "invalid_ids" }, { status: 400 });

    const rawList = ids.split(",").filter(Boolean).slice(0, 4);
    if (rawList.length < 2) return NextResponse.json({ error: "need_at_least_2" }, { status: 400 });

    // Validate UUID format for all IDs
    const idList = [...new Set(rawList.filter((id) => isValidUuid(id)))];
    if (idList.length < 2) return NextResponse.json({ error: "invalid_ids" }, { status: 400 });

    const variants = await pool.query(
      `SELECT v.id, v."nameEn", v."nameTh", v.slug,
              cm."nameEn" as "modelName", cm."nameTh" as "modelTh",
              m."nameEn" as "brand", m."nameTh" as "brandTh"
       FROM "Variant" v
       JOIN "CarModel" cm ON v."modelId" = cm.id
       JOIN "Manufacturer" m ON cm."manufacturerId" = m.id
       WHERE v.id = ANY($1::uuid[]) AND v.status = 'ACTIVE'`,
      [idList]
    );

    if (variants.rows.length < 2) return NextResponse.json({ error: "variants_not_found" }, { status: 404 });

    // P116: preserve the SELECTED order — map DB rows back onto idList
    // (WHERE ANY() returns no guaranteed order).
    const byId = new Map(variants.rows.map((r) => [r.id, r]));
    const orderedRows = idList.map((id) => byId.get(id)).filter(Boolean);

    const variantIds = orderedRows.map((r) => r.id);
    const [prices, perf, dims, batt, charge, features] = await Promise.all([
      pool.query(
        `SELECT p."variantId", p.amount, p."priceType",
                sd."canonicalUrl", sd.url, s."nameEn" as "sourceName"
         FROM "Price" p
         JOIN "SourceDocument" sd ON sd.id = p."sourceDocumentId"
         JOIN "Source" s ON s.id = sd."sourceId"
         WHERE p."variantId" = ANY($1::uuid[]) AND ${currentOfficialPriceWhere("p")}
         ORDER BY p.amount ASC`,
        [variantIds]
      ),
      pool.query(
        `SELECT "variantId", "powerKw", "torqueNm", "rangeKm" FROM "PerformanceSpec" WHERE "variantId" = ANY($1::uuid[])`,
        [variantIds]
      ),
      pool.query(
        `SELECT "variantId", "lengthMm", "widthMm", "heightMm", "wheelbaseMm", "groundClearanceMm" FROM "DimensionsSpec" WHERE "variantId" = ANY($1::uuid[])`,
        [variantIds]
      ),
      pool.query(
        `SELECT "variantId", "capacityKwh", chemistry FROM "BatterySpec" WHERE "variantId" = ANY($1::uuid[])`,
        [variantIds]
      ),
      pool.query(
        `SELECT "variantId", "dcPowerKw", "acPowerKw" FROM "ChargingSpec" WHERE "variantId" = ANY($1::uuid[])`,
        [variantIds]
      ),
      // P116: keep `available` (installed / explicitly not installed); a
      // missing row = unknown — the client renders ไม่มีข้อมูล, never ไม่ติดตั้ง
      pool.query(
        `SELECT vf."variantId", f.slug, f."nameEn", f."nameTh", vf.standard, vf."sourceTier", vf.available
         FROM "VariantFeature" vf
         JOIN "Feature" f ON vf."featureId" = f.id
         WHERE vf."variantId" = ANY($1::uuid[])
         ORDER BY f.slug`,
        [variantIds]
      ),
    ]);

    const priceMap = new Map();
    for (const p of prices.rows) {
      if (!priceMap.has(p.variantId)) {
        priceMap.set(p.variantId, {
          amount: Number(p.amount),
          type: p.priceType,
          sourceUrl: p.canonicalUrl || p.url || null,
          sourceName: p.sourceName || null,
        });
      }
    }

    const perfMap = new Map(perf.rows.map((r) => [r.variantId, r]));
    const dimsMap = new Map(dims.rows.map((r) => [r.variantId, r]));
    const battMap = new Map(batt.rows.map((r) => [r.variantId, r]));
    const chargeMap = new Map(charge.rows.map((r) => [r.variantId, r]));
    const featureMap = new Map();
    for (const f of features.rows) {
      if (!featureMap.has(f.variantId)) featureMap.set(f.variantId, []);
      featureMap.get(f.variantId).push({
        slug: f.slug,
        nameEn: f.nameEn,
        nameTh: f.nameTh,
        standard: f.standard,
        available: f.available,
        sourceTier: f.sourceTier,
      });
    }

    // NOTE: response shape is the BASE client contract (name/model/specs) —
    // CompareClient reads v.specs.power etc. Additive only: price.sourceUrl /
    // sourceName (provenance) and features[].available (three-state).
    const comparison = orderedRows.map((row) => {
      const perf = perfMap.get(row.id);
      const dim = dimsMap.get(row.id);
      const batt = battMap.get(row.id);
      const charge = chargeMap.get(row.id);
      const price = priceMap.get(row.id) || null;
      return {
        id: row.id,
        name: row.nameEn,
        nameTh: row.nameTh,
        model: row.modelName,
        modelTh: row.modelTh,
        brand: row.brand,
        brandTh: row.brandTh,
        price,
        specs: {
          power: perf?.powerKw != null ? Number(perf.powerKw) : null,
          torque: perf?.torqueNm != null ? Number(perf.torqueNm) : null,
          range: perf?.rangeKm != null ? Number(perf.rangeKm) : null,
          length: dim?.lengthMm != null ? Number(dim.lengthMm) : null,
          width: dim?.widthMm != null ? Number(dim.widthMm) : null,
          height: dim?.heightMm != null ? Number(dim.heightMm) : null,
          wheelbase: dim?.wheelbaseMm != null ? Number(dim.wheelbaseMm) : null,
          battery: batt?.capacityKwh != null ? Number(batt.capacityKwh) : null,
          chemistry: batt?.chemistry || null,
          acCharge: charge?.acPowerKw != null ? Number(charge.acPowerKw) : null,
          dcCharge: charge?.dcPowerKw != null ? Number(charge.dcPowerKw) : null,
        },
        features: featureMap.get(row.id) || [],
      };
    });

    return NextResponse.json({ comparison, totalVariants: comparison.length });
  } catch (error) {
    console.error("API /api/compare error:", error);
    return NextResponse.json({ error: "database_unavailable" }, { status: 503 });
  }
}
