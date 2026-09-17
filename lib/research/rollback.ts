import db from "../db";

export type RollbackResult = {
  success: boolean;
  reason: string;
  previousValue: string | null;
  rolledBackAt: Date;
};

/**
 * Rollback a published change candidate, restoring the previous value.
 * Only PUBLISHED candidates can be rolled back.
 */
export async function rollbackPublishedChange(candidateId: string, reason: string): Promise<RollbackResult> {
  const candidates = await db.$queryRaw<{
    id: string; entity_type: string; entity_id: string; field_name: string;
    old_value: string | null; new_value: string; source_url: string;
    status: string; published_at: Date | null;
  }[]>`SELECT * FROM "ChangeCandidate" WHERE id = ${candidateId}::uuid`;

  if (candidates.length === 0) {
    return { success: false, reason: "Candidate not found", previousValue: null, rolledBackAt: new Date() };
  }

  const c = candidates[0];
  if (c.status !== "PUBLISHED") {
    return { success: false, reason: `Cannot rollback: status is ${c.status}`, previousValue: null, rolledBackAt: new Date() };
  }

  if (!c.old_value) {
    return { success: false, reason: "No previous value to restore", previousValue: null, rolledBackAt: new Date() };
  }

  // Idempotent: if already rolled back (old_value is current), skip
  if (c.entity_type === "price") {
    const current = await db.$queryRaw<{ amount: string }[]>`SELECT p.amount::text FROM "Price" p WHERE p."variantId" = ${c.entity_id}::uuid AND p."isCurrent" = true LIMIT 1`;
    if (current[0]?.amount === c.old_value) {
      return { success: true, reason: "Already rolled back", previousValue: c.old_value, rolledBackAt: new Date() };
    }
  }

  // Restore previous value
  if (c.entity_type === "price") {
    // Mark published price as not current
    await db.$executeRaw`UPDATE "Price" SET "isCurrent" = false WHERE "variantId" = ${c.entity_id}::uuid AND "isCurrent" = true`;

    // Re-create the previous price
    await db.$executeRaw`INSERT INTO "Price" ("id", "variantId", "sourceDocumentId", "priceType", amount, currency, "validFrom", "observedAt", "isCurrent", confidence) VALUES (gen_random_uuid(), ${c.entity_id}::uuid, (SELECT "sourceDocumentId" FROM "Price" WHERE "variantId" = ${c.entity_id}::uuid ORDER BY observedAt DESC LIMIT 1), 'LIST_PRICE', ${c.old_value}::numeric, 'THB', NOW(), NOW(), true, 0.95)`;
  }

  // Update candidate status
  await db.$executeRaw`UPDATE "ChangeCandidate" SET status = 'REJECTED', review_notes = ${`Rolled back: ${reason}`}, verified_at = NOW() WHERE id = ${candidateId}::uuid`;

  return {
    success: true,
    reason: `Rolled back: ${reason}`,
    previousValue: c.old_value,
    rolledBackAt: new Date(),
  };
}
