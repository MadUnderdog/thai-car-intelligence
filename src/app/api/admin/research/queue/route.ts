/* eslint-disable @typescript-eslint/no-explicit-any */
import { NextResponse } from "next/server";
import db from "../../../../../../lib/db";

export const dynamic = "force-dynamic";

async function q(sql: string): Promise<any[]> {
  return db.$queryRawUnsafe(sql);
}

export async function GET() {
  try {
    const queue = await q(`
      SELECT eq.id, eq.status, eq.priority, eq."missingRequired", eq."missingOptional",
        eq."lastAttemptAt", eq."completedAt", eq."researchNotes",
        v."nameEn" as variant_name, v.slug, v."fuelType",
        cm."nameEn" as model_name, m."nameEn" as brand,
        CASE WHEN v."fuelType" = 'EV' THEN 'EV'
             WHEN v."fuelType" IN ('HEV','PHEV') THEN 'HEV'
             WHEN v."fuelType" = 'Diesel' THEN 'DIESEL'
             ELSE 'ICE' END as powertrain_type,
        (SELECT count(*) FROM \"PerformanceSpec\" WHERE \"variantId\"=v.id) as has_perf,
        (SELECT count(*) FROM \"DimensionsSpec\" WHERE \"variantId\"=v.id) as has_dims
      FROM \"EnrichmentQueue\" eq
      JOIN \"Variant\" v ON v.id=eq."variantId"
      JOIN \"CarModel\" cm ON cm.id=v."modelId"
      JOIN \"Manufacturer\" m ON m.id=cm."manufacturerId"
      ORDER BY eq.priority DESC, eq."createdAt" ASC
      LIMIT 50
    `);

    const stats = await q(`
      SELECT status, count(*) as cnt FROM \"EnrichmentQueue\" GROUP BY status
    `);

    const completedToday = await q(`
      SELECT count(*) as cnt FROM \"EnrichmentQueue\" 
      WHERE status = 'COMPLETED' AND \"completedAt\" > CURRENT_DATE
    `);

    return NextResponse.json({
      queue: queue.map((item: any) => ({
        id: item.id,
        status: item.status,
        priority: item.priority,
        brand: item.brand,
        model: item.model_name,
        variant: item.variant_name,
        slug: item.slug,
        fuelType: item.fuelType,
        powertrainType: item.powertrain_type,
        missingRequired: item.missingRequired || [],
        missingOptional: item.missingOptional || [],
        lastAttempt: item.lastAttemptAt,
        completedAt: item.completedAt,
        notes: item.researchNotes,
      })),
      stats: Object.fromEntries(stats.map((s: any) => [s.status, Number(s.cnt)])),
      completedToday: Number(completedToday[0]?.cnt ?? 0),
    });
  } catch (e) {
    return NextResponse.json({ error: "database_unavailable", detail: String(e) }, { status: 503 });
  }
}
