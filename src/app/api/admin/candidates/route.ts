import { NextResponse } from "next/server";
import db from "../../../../../lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    // Get candidate stats
    const stats = await db.$queryRaw<{ status: string; cnt: number }[]>`SELECT status, count(*) as cnt FROM "ChangeCandidate" GROUP BY status`;
    const statMap = Object.fromEntries(stats.map((s) => [s.status, Number(s.cnt)]));

    // Get recent candidates
    const candidates = await db.$queryRaw<{
      id: string; entity_type: string; entity_id: string; field_name: string;
      old_value: string | null; new_value: string; source_url: string; source_tier: string;
      status: string; detected_at: Date; review_notes: string | null;
    }[]>`SELECT id, entity_type, entity_id, field_name, old_value, new_value, source_url, source_tier, status, detected_at, review_notes FROM "ChangeCandidate" ORDER BY detected_at DESC LIMIT 20`;

    // Get recent refresh runs
    const runs = await db.$queryRaw<{
      id: string; status: string; started_at: Date | null; completed_at: Date | null;
      sources_checked: number; changes_detected: number; candidates_created: number; errors: number;
    }[]>`SELECT id, status, started_at, completed_at, sources_checked, changes_detected, candidates_created, errors FROM "RefreshRun" ORDER BY created_at DESC LIMIT 10`;

    // Get source health
    const sourceHealth = await db.$queryRaw<{
      domain: string; last_success_at: Date | null; consecutive_failures: number; last_error: string | null;
    }[]>`SELECT domain, last_success_at, consecutive_failures, last_error FROM "SourceHealth" ORDER BY consecutive_failures DESC, domain LIMIT 20`;

    return NextResponse.json({
      stats: {
        total: Object.values(statMap).reduce((a, b) => a + b, 0),
        discovered: statMap["DISCOVERED"] ?? 0,
        needsVerification: statMap["NEEDS_VERIFICATION"] ?? 0,
        verified: statMap["VERIFIED"] ?? 0,
        published: statMap["PUBLISHED"] ?? 0,
        rejected: statMap["REJECTED"] ?? 0,
        conflict: statMap["CONFLICT"] ?? 0,
      },
      candidates,
      runs,
      sourceHealth,
    });
  } catch {
    return NextResponse.json({ error: "database_unavailable" }, { status: 503 });
  }
}
