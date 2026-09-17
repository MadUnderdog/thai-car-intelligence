import { NextResponse } from "next/server";
import db from "../../../../../lib/db";

export const dynamic = "force-dynamic";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function q(sql: string): Promise<any[]> {
  return db.$queryRawUnsafe(sql);
}

export async function GET() {
  try {
    const total = await q(`SELECT count(*) as cnt FROM "Variant" WHERE status = 'ACTIVE'`);
    const withPrice = await q(`SELECT count(*) as cnt FROM "Variant" v INNER JOIN "Price" p ON p."variantId" = v.id AND p."isCurrent" = true WHERE v.status = 'ACTIVE'`);
    const withSpecs = await q(`SELECT count(DISTINCT v.id) as cnt FROM "Variant" v INNER JOIN "PerformanceSpec" ps ON ps."variantId" = v.id WHERE v.status = 'ACTIVE'`);
    const withFeatures = await q(`SELECT count(DISTINCT "variantId") as cnt FROM "VariantFeature" WHERE available = true`);
    const withImages = await q(`SELECT count(DISTINCT "modelId") as cnt FROM "Media" WHERE type = 'IMAGE'`);
    const fuelTypes = await q(`SELECT "fuelType", "fuelTypeSource" as source, count(*) as cnt FROM "Variant" WHERE status = 'ACTIVE' GROUP BY "fuelType", "fuelTypeSource"`);

    // Record-level counts per spec table
    const perfSpecs = await q(`SELECT "sourceTier", count(*) as cnt FROM "PerformanceSpec" GROUP BY "sourceTier"`);
    const dimSpecs = await q(`SELECT "sourceTier", count(*) as cnt FROM "DimensionsSpec" GROUP BY "sourceTier"`);
    const battSpecs = await q(`SELECT "sourceTier", count(*) as cnt FROM "BatterySpec" GROUP BY "sourceTier"`);
    const chargeSpecs = await q(`SELECT "sourceTier", count(*) as cnt FROM "ChargingSpec" GROUP BY "sourceTier"`);

    const t = Number(total[0]?.cnt ?? 0);

    // Build record-level metrics
    const recordMetrics = (rows: { sourceTier: string; cnt: bigint }[]) => {
      const map: Record<string, number> = {};
      let total = 0;
      for (const r of rows) { map[r.sourceTier] = Number(r.cnt); total += Number(r.cnt); }
      return { total, official: map["official_verified"] ?? 0, secondary: map["secondary_verified"] ?? 0, reference: map["reference"] ?? 0, inferred: map["inferred"] ?? 0 };
    };

    return NextResponse.json({
      summary: {
        totalVariants: t,
        withPrice: Number(withPrice[0]?.cnt ?? 0),
        withSpecs: Number(withSpecs[0]?.cnt ?? 0),
        withFeatures: Number(withFeatures[0]?.cnt ?? 0),
        withImages: Number(withImages[0]?.cnt ?? 0),
      },
      records: {
        performance: recordMetrics(perfSpecs),
        dimensions: recordMetrics(dimSpecs),
        battery: recordMetrics(battSpecs),
        charging: recordMetrics(chargeSpecs),
        total: Number(perfSpecs.reduce((s: number, r: { cnt: bigint }) => s + Number(r.cnt), 0))
          + Number(dimSpecs.reduce((s: number, r: { cnt: bigint }) => s + Number(r.cnt), 0))
          + Number(battSpecs.reduce((s: number, r: { cnt: bigint }) => s + Number(r.cnt), 0))
          + Number(chargeSpecs.reduce((s: number, r: { cnt: bigint }) => s + Number(r.cnt), 0)),
      },
      priceCoverage: { verified: Number(withPrice[0]?.cnt ?? 0), percentage: t > 0 ? Math.round((Number(withPrice[0]?.cnt ?? 0) / t) * 100) : 0 },
      fuelCoverage: fuelTypes.map((f: { fuelType: string | null; source: string; cnt: bigint }) => ({ type: f.fuelType ?? "unknown", source: f.source, count: Number(f.cnt) })),
      featureCoverage: { variantsWithFeatures: Number(withFeatures[0]?.cnt ?? 0), percentage: t > 0 ? Math.round((Number(withFeatures[0]?.cnt ?? 0) / t) * 100) : 0 },
      imageCoverage: { modelsWithImages: Number(withImages[0]?.cnt ?? 0), percentage: Math.round((Number(withImages[0]?.cnt ?? 0) / 76) * 100) },
    });
  } catch (e) {
    console.error("API route error:", e);
    return NextResponse.json({ error: "database_unavailable" }, { status: 503 });
  }
}
