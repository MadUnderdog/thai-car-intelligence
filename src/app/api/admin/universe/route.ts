/**
 * Coverage Matrix API — Returns machine-readable data completeness report.
 */

import { NextResponse } from "next/server";
import { db } from "../../../../../lib/db";
import { computeCoverageMatrix } from "../../../../../lib/discovery/coverage-matrix";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const matrix = await computeCoverageMatrix(db);
    return NextResponse.json(matrix);
  } catch (error) {
    return NextResponse.json(
      { error: "coverage_unavailable", message: String(error) },
      { status: 503 },
    );
  }
}
