// @ts-nocheck
import pool from "@/lib/db-pg";
import { isValidUuid } from "../../../../lib/validation/api-params";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const ids = params.get("ids");
  if (!ids) return NextResponse.json({ error: "invalid_ids" }, { status: 400 });

  const rawList = ids.split(",").filter(Boolean).slice(0, 4);
  if (rawList.length < 2) return NextResponse.json({ error: "need_at_least_2" }, { status: 400 });

  // Validate UUID format for all IDs
  const idList = rawList.filter((id) => isValidUuid(id));
  if (idList.length < 2) return NextResponse.json({ error: "invalid_ids" }, { status: 400 });

  try {
    const variants: any = await pool.query(
      `SELECT v.id, v."nameEn", v."nameTh", v.slug,
        cm."nameEn" as "modelName", cm."nameTh" as "modelTh",
        m."nameEn" as "brand", m."nameTh" as "brandTh"
      FROM "Variant" v
      JOIN "CarModel" cm ON cm.id = v."modelId"
      JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
      WHERE v.id = ANY($1) AND v.status = 'ACTIVE'`,
      [idList]
    );

    if (variants.rows.length < 2) return NextResponse.json({ error: "variants_not_found" }, { status: 404 });

    const variantIds = variants.rows.map((v: any) => v.id);

    const prices: any = await pool.query(
      `SELECT "variantId", amount, "priceType" FROM "Price" WHERE "variantId" = ANY($1) AND "isCurrent" = true ORDER BY amount ASC`,
      [variantIds]
    );

    const perfSpecs: any = await pool.query(
      `SELECT "variantId", "powerKw", "torqueNm", "rangeKm" FROM "PerformanceSpec" WHERE "variantId" = ANY($1)`,
      [variantIds]
    );

    const dimSpecs: any = await pool.query(
      `SELECT "variantId", "lengthMm" as "lengthMm", "widthMm" as "widthMm", "heightMm" as "heightMm", "wheelbaseMm" as "wheelbaseMm" FROM "DimensionsSpec" WHERE "variantId" = ANY($1)`,
      [variantIds]
    );

    const battSpecs: any = await pool.query(
      `SELECT "variantId", "capacityKwh", chemistry FROM "BatterySpec" WHERE "variantId" = ANY($1)`,
      [variantIds]
    );

    const chargeSpecs: any = await pool.query(
      `SELECT "variantId", "acPowerKw", "dcPowerKw" FROM "ChargingSpec" WHERE "variantId" = ANY($1)`,
      [variantIds]
    );

    const features: any = await pool.query(
      `SELECT vf."variantId", f.slug, f."nameEn", f."nameTh", vf.standard, vf."sourceTier"
      FROM "VariantFeature" vf
      JOIN "Feature" f ON f.id = vf."featureId"
      WHERE vf."variantId" = ANY($1) AND vf.available = true`,
      [variantIds]
    );

    const priceMap = new Map(prices.rows.map((p: any) => [p.variantId, p]));
    const perfMap = new Map(perfSpecs.rows.map((s: any) => [s.variantId, s]));
    const dimMap = new Map(dimSpecs.rows.map((s: any) => [s.variantId, s]));
    const battMap = new Map(battSpecs.rows.map((s: any) => [s.variantId, s]));
    const chargeMap = new Map(chargeSpecs.rows.map((s: any) => [s.variantId, s]));
    const featMap = new Map<string, any[]>();
    for (const f of features.rows) {
      const arr = featMap.get(f.variantId) || [];
      arr.push(f);
      featMap.set(f.variantId, arr);
    }

    const comparison = variants.rows.map((v: any) => {
      const p = priceMap.get(v.id);
      const perf = perfMap.get(v.id);
      const dim = dimMap.get(v.id);
      const batt = battMap.get(v.id);
      const charge = chargeMap.get(v.id);
      const feats = featMap.get(v.id) || [];

      return {
        id: v.id,
        name: v.nameEn,
        nameTh: v.nameTh,
        model: v.modelName,
        modelTh: v.modelTh,
        brand: v.brand,
        brandTh: v.brandTh,
        price: p ? { amount: Number(p.amount), type: p.priceType } : null,
        specs: {
          power: perf?.powerKw ? Number(perf.powerKw) : null,
          torque: perf?.torqueNm ? Number(perf.torqueNm) : null,
          range: perf?.rangeKm ? Number(perf.rangeKm) : null,
          length: dim ? Number((dim as any).lengthMm) : null,
          width: dim ? Number((dim as any).widthMm) : null,
          height: dim ? Number((dim as any).heightMm) : null,
          wheelbase: dim ? Number((dim as any).wheelbaseMm) : null,
          battery: batt ? Number((batt as any).capacityKwh) : null,
          chemistry: (batt as any)?.chemistry || null,
          acCharge: charge ? Number((charge as any).acPowerKw) : null,
          dcCharge: charge ? Number((charge as any).dcPowerKw) : null,
        },
        features: feats.map((f: any) => ({ slug: f.slug, nameEn: f.nameEn, nameTh: f.nameTh, standard: f.standard })),
      };
    });

    return NextResponse.json({ comparison, totalVariants: comparison.length });
  } catch (error) {
    console.error("API /api/compare error:", error);
    return NextResponse.json({ error: "database_unavailable" }, { status: 503 });
  }
}
