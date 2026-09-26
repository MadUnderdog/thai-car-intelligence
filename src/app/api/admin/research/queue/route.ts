import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Research queue endpoint — returns safe unavailable state.
 * The backing table (EnrichmentQueue) does not exist in the current
 * database schema. This endpoint documents that the enrichment pipeline
 * is not yet implemented rather than crashing with SQL errors.
 */
export async function GET() {
  return NextResponse.json({
    queue: [],
    stats: {},
    completedToday: 0,
    _status: "not_implemented",
    _message: "Enrichment queue table not yet created. This endpoint returns empty data.",
  });
}
