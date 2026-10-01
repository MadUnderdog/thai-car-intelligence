import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Quality variants endpoint — returns safe unavailable state.
 * The backing view/table (variant_completeness_matrix) does not exist
 * in the current database schema. This endpoint documents that the
 * completeness tracking is not yet implemented rather than crashing.
 */
export async function GET() {
  return NextResponse.json({
    summary: {
      totalVariants: 0,
      complete: 0,
      withSpecs: 0,
      withFeatures: 0,
      withImages: 0,
      completenessPercentage: 0,
    },
    sourceQuality: {},
    variants: [],
    _status: "not_implemented",
    _message: "Completeness matrix not yet created. This endpoint returns empty data.",
  });
}
