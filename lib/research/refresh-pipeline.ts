import db from "../db";


export type ChangeCandidateStatus = "DISCOVERED" | "NEEDS_VERIFICATION" | "VERIFIED" | "PUBLISHED" | "REJECTED";

export type RefreshRunStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "PARTIAL_SUCCESS" | "FAILED";

export async function createRefreshRun(): Promise<string> {
  await db.$executeRaw`INSERT INTO "RefreshRun" (id, status, started_at) VALUES (gen_random_uuid(), 'RUNNING', NOW()) RETURNING id`;
  const result = await db.$queryRaw<{ id: string }[]>`SELECT id FROM "RefreshRun" ORDER BY created_at DESC LIMIT 1`;
  return result[0].id;
}

export async function completeRefreshRun(
  runId: string,
  stats: { sources_checked: number; changes_detected: number; candidates_created: number; verified_changes: number; conflicts: number; errors: number; error_log?: string }
): Promise<void> {
  const status = stats.errors > 0 && stats.verified_changes === 0 ? "FAILED" : stats.errors > 0 ? "PARTIAL_SUCCESS" : "COMPLETED";
  await db.$executeRaw`UPDATE "RefreshRun" SET status = ${status}, completed_at = NOW(), sources_checked = ${stats.sources_checked}, changes_detected = ${stats.changes_detected}, candidates_created = ${stats.candidates_created}, verified_changes = ${stats.verified_changes}, conflicts = ${stats.conflicts}, errors = ${stats.errors}, error_log = ${stats.error_log ?? null} WHERE id = ${runId}`;
}

export async function createChangeCandidate(params: {
  entityType: string;
  entityId: string;
  fieldName: string;
  oldValue: string | null;
  newValue: string;
  sourceUrl: string;
  sourceTier: string;
}): Promise<string> {
  const result = await db.$queryRaw<{ id: string }[]>`INSERT INTO "ChangeCandidate" (entity_type, entity_id, field_name, old_value, new_value, source_url, source_tier) VALUES (${params.entityType}, ${params.entityId}::uuid, ${params.fieldName}, ${params.oldValue}, ${params.newValue}, ${params.sourceUrl}, ${params.sourceTier}) RETURNING id`;
  return result[0].id;
}

export async function getCandidateStats(): Promise<{ total: number; discovered: number; verified: number; published: number }> {
  const rows = await db.$queryRaw<{ status: string; cnt: number }[]>`SELECT status, count(*) as cnt FROM "ChangeCandidate" GROUP BY status`;
  const map = Object.fromEntries(rows.map((r) => [r.status, Number(r.cnt)]));
  return { total: Object.values(map).reduce((a, b) => a + b, 0), discovered: map["DISCOVERED"] ?? 0, verified: map["VERIFIED"] ?? 0, published: map["PUBLISHED"] ?? 0 };
}

export async function getRecentRuns(limit = 10): Promise<{ id: string; status: string; started_at: Date | null; completed_at: Date | null; sources_checked: number; changes_detected: number; candidates_created: number; errors: number }[]> {
  return db.$queryRaw`SELECT id, status, started_at, completed_at, sources_checked, changes_detected, candidates_created, errors FROM "RefreshRun" ORDER BY created_at DESC LIMIT ${limit}`;
}

export async function updateSourceHealth(url: string, domain: string, success: boolean, http_status?: number, response_time_ms?: number, error?: string): Promise<void> {
  await db.$executeRaw`INSERT INTO "SourceHealth" (source_url, domain, last_checked_at, last_success_at, http_status, response_time_ms, last_error, consecutive_failures) VALUES (${url}, ${domain}, NOW(), ${success ? new Date() : null}, ${http_status ?? null}, ${response_time_ms ?? null}, ${error ?? null}, ${success ? 0 : 1}) ON CONFLICT (source_url) DO UPDATE SET last_checked_at = NOW(), last_success_at = ${success ? new Date() : db.$queryRaw`"SourceHealth"."last_success_at"`}, http_status = ${http_status ?? null}, response_time_ms = ${response_time_ms ?? null}, last_error = ${error ?? null}, consecutive_failures = ${success ? 0 : db.$queryRaw`"SourceHealth"."consecutive_failures" + 1`}, updated_at = NOW()`;
}

export async function getSourceHealth(): Promise<{ domain: string; last_success_at: Date | null; consecutive_failures: number; last_error: string | null }[]> {
  return db.$queryRaw`SELECT domain, last_success_at, consecutive_failures, last_error FROM "SourceHealth" ORDER BY consecutive_failures DESC, domain`;
}
