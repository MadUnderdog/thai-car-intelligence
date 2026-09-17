import { NextResponse } from "next/server";
import db from "../../../../../lib/db";

export const dynamic = "force-dynamic";

async function q(sql: string): Promise<any[]> {
  return db.$queryRawUnsafe(sql);
}

export async function GET() {
  try {
    // Catalog metrics
    const totalVariants = await q(`SELECT count(*) as cnt FROM "Variant" WHERE status = 'ACTIVE'`);
    const withSpecs = await q(`SELECT count(DISTINCT "variantId") as cnt FROM "PerformanceSpec"`);
    const withFeatures = await q(`SELECT count(DISTINCT "variantId") as cnt FROM "VariantFeature" WHERE available = true`);
    const withImages = await q(`SELECT count(DISTINCT "modelId") as cnt FROM "Media" WHERE type = 'IMAGE'`);

    // Source quality
    const perfSpecs = await q(`SELECT "sourceTier", count(*) as cnt FROM "PerformanceSpec" GROUP BY "sourceTier"`);
    const dimSpecs = await q(`SELECT "sourceTier", count(*) as cnt FROM "DimensionsSpec" GROUP BY "sourceTier"`);

    // Enrichment queue
    const queueStats = await q(`SELECT status, count(*) as cnt FROM "EnrichmentQueue" GROUP BY status`);

    // Research runs
    const recentRuns = await q(`SELECT status, count(*) as cnt FROM "RefreshRun" GROUP BY status`);

    const t = Number(totalVariants[0]?.cnt ?? 0);

    return NextResponse.json({
      catalog: {
        totalVariants: t,
        withSpecs: Number(withSpecs[0]?.cnt ?? 0),
        withFeatures: Number(withFeatures[0]?.cnt ?? 0),
        withImages: Number(withImages[0]?.cnt ?? 0),
        specCoverage: t > 0 ? Math.round((Number(withSpecs[0]?.cnt ?? 0) / t) * 100) : 0,
      },
      sourceQuality: {
        performance: Object.fromEntries(perfSpecs.map((s: any) => [s.sourceTier, Number(s.cnt)])),
        dimensions: Object.fromEntries(dimSpecs.map((s: any) => [s.sourceTier, Number(s.cnt)])),
      },
      enrichment: Object.fromEntries(queueStats.map((s: any) => [s.status, Number(s.cnt)])),
      research: Object.fromEntries(recentRuns.map((s: any) => [s.status, Number(s.cnt)])),
    });
  } catch (e) {
    return NextResponse.json({ error: "database_unavailable", detail: String(e) }, { status: 503 });
  }
}
