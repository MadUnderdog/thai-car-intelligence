import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Candidates endpoint — returns safe unavailable state.
 * The backing tables (ChangeCandidate, RefreshRun, SourceHealth) do not exist
 * in the current database schema. This endpoint documents that these features
 * are not yet implemented rather than crashing with SQL errors.
 */
export async function GET() {
  return NextResponse.json({
    stats: { total: 0, discovered: 0, needsVerification: 0, verified: 0, published: 0, rejected: 0, conflict: 0 },
    candidates: [],
    runs: [],
    sourceHealth: [],
    _status: "not_implemented",
    _message: "Change tracking tables not yet created. This endpoint returns empty data.",
  });
}
