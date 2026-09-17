/* eslint-disable @typescript-eslint/no-explicit-any */
import { NextResponse } from "next/server";
import db from "../../../../../../lib/db";

export const dynamic = "force-dynamic";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function q(sql: string): Promise<any[]> {
  return db.$queryRawUnsafe(sql);
}

export async function GET() {
  try {
    // Get completeness matrix
    const variants = await q(`
      SELECT brand, model_name, variant_name, slug, powertrain_type,
        performance, perf_source, dimensions, dim_source,
        battery, batt_source, charging, charge_source,
        adas_features, image, brochure
      FROM variant_completeness_matrix
      ORDER BY brand, model_name, variant_name
    `);

    // Calculate enrichment priority scores
    const scored = variants.map((v: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      const required = v.powertrain_type === "EV"
        ? ["performance", "dimensions", "battery", "charging"]
        : ["performance", "dimensions"];
      const optional = ["adas_features", "image", "brochure"];

      const missingRequired = required.filter((f) => v[f] === "MISSING").length;
      const missingOptional = optional.filter((f) => v[f] === "MISSING").length;
      const totalRequired = required.length;
      const completeness = totalRequired > 0
        ? Math.round(((totalRequired - missingRequired) / totalRequired) * 100)
        : 0;

      // Priority: higher score = more enrichment needed
      const priority = missingRequired * 10 + missingOptional * 3;

      return {
        ...v,
        completeness,
        priority,
        missingFields: [...required, ...optional].filter((f) => v[f] === "MISSING"),
      };
    });

    // Summary stats
    const total = scored.length;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const complete = scored.filter((v: any) => v.completeness === 100).length;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const withSpecs = scored.filter((v: any) => v.performance === "PRESENT").length;
    const withFeatures = scored.filter((v: any) => v.adas_features === "PRESENT").length;
    const withImages = scored.filter((v: any) => v.image === "PRESENT").length;

    // Source quality summary
    const sourceCounts = await q(`
      SELECT 'PerformanceSpec' as tbl, \"sourceTier\", count(*) as cnt FROM \"PerformanceSpec\" GROUP BY \"sourceTier\"
      UNION ALL
      SELECT 'DimensionsSpec', \"sourceTier\", count(*) FROM \"DimensionsSpec\" GROUP BY \"sourceTier\"
    `);

    return NextResponse.json({
      summary: {
        totalVariants: total,
        complete,
        withSpecs,
        withFeatures,
        withImages,
        completenessPercentage: total > 0 ? Math.round((complete / total) * 100) : 0,
      },
      sourceQuality: Object.fromEntries(
        sourceCounts.map((s: { tbl: string; sourceTier: string; cnt: bigint }) => [`${s.tbl}:${s.sourceTier}`, Number(s.cnt)])
      ),
      variants: scored,
    });
  } catch (e) {
    return NextResponse.json({ error: "database_unavailable", detail: String(e) }, { status: 503 });
  }
}
