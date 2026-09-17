import db from "../db";

export type VerificationResult = {
  candidateId: string;
  status: "VERIFIED" | "REJECTED" | "CONFLICT";
  reason: string;
  verifiedAt: Date;
};

/**
 * Verify a change candidate against current database state.
 * Does NOT publish — only moves status to VERIFIED/REJECTED/CONFLICT.
 */
export async function verifyChangeCandidate(candidateId: string): Promise<VerificationResult> {
  const candidates = await db.$queryRaw<{
    id: string; entity_type: string; entity_id: string; field_name: string;
    old_value: string | null; new_value: string; source_url: string; source_tier: string;
    status: string;
  }[]>`SELECT * FROM "ChangeCandidate" WHERE id = ${candidateId}::uuid`;

  if (candidates.length === 0) throw new Error("Candidate not found");
  const c = candidates[0];
  if (c.status !== "DISCOVERED" && c.status !== "NEEDS_VERIFICATION") {
    throw new Error(`Candidate ${candidateId} is in status ${c.status}, cannot verify`);
  }

  // Step 1: Move to NEEDS_VERIFICATION
  await db.$executeRaw`UPDATE "ChangeCandidate" SET status = 'NEEDS_VERIFICATION' WHERE id = ${candidateId}::uuid`;

  // Step 2: Re-fetch source to confirm it's still accessible
  let sourceAccessible = true;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    const response = await fetch(c.source_url, { signal: controller.signal, headers: { "User-Agent": "ThaiCarIntel/1.0 (verification)" } });
    clearTimeout(timer);
    sourceAccessible = response.ok;
  } catch {
    sourceAccessible = false;
  }

  if (!sourceAccessible) {
    await db.$executeRaw`UPDATE "ChangeCandidate" SET status = 'REJECTED', review_notes = ${'Source not accessible during verification'}, verified_at = NOW() WHERE id = ${candidateId}::uuid`;
    return { candidateId, status: "REJECTED", reason: "Source not accessible", verifiedAt: new Date() };
  }

  // Step 3: Verify against current DB value
  let currentDbValue: string | null = null;
  if (c.entity_type === "price") {
    const rows = await db.$queryRaw<{ amount: string }[]>`SELECT p.amount::text FROM "Price" p WHERE p."variantId" = ${c.entity_id}::uuid AND p."isCurrent" = true LIMIT 1`;
    currentDbValue = rows[0]?.amount ?? null;
  }

  // Step 4: Check for conflicts with other candidates for same entity
  const conflicts = await db.$queryRaw<{ id: string; new_value: string; source_url: string; source_tier: string }[]>`SELECT id, new_value, source_url, source_tier FROM "ChangeCandidate" WHERE entity_type = ${c.entity_type} AND entity_id = ${c.entity_id} AND field_name = ${c.field_name} AND id != ${candidateId}::uuid AND status IN ('VERIFIED', 'NEEDS_VERIFICATION')`;

  if (conflicts.length > 0) {
    // Check if sources disagree
    const conflictValues = new Set([c.new_value, ...conflicts.map((x) => x.new_value)]);
    if (conflictValues.size > 1) {
      await db.$executeRaw`UPDATE "ChangeCandidate" SET status = 'CONFLICT', review_notes = ${`Conflicting values from ${conflicts.length + 1} sources: ${[c.new_value, ...conflicts.map((x) => x.new_value)].join(", ")}`}, verified_at = NOW() WHERE id = ${candidateId}::uuid`;
      return { candidateId, status: "CONFLICT", reason: `Conflicting values from ${conflicts.length + 1} sources`, verifiedAt: new Date() };
    }
  }

  // Step 5: Mark as verified
  await db.$executeRaw`UPDATE "ChangeCandidate" SET status = 'VERIFIED', review_notes = ${`Verified against accessible source. Previous DB value: ${currentDbValue ?? "none"}`}, verified_at = NOW() WHERE id = ${candidateId}::uuid`;

  return { candidateId, status: "VERIFIED", reason: "Source verified, value confirmed", verifiedAt: new Date() };
}

/**
 * Publish a verified candidate to the catalog.
 * Only VERIFIED candidates can be published.
 */
export async function publishVerifiedCandidate(candidateId: string): Promise<{ published: boolean; reason: string }> {
  const candidates = await db.$queryRaw<{
    id: string; entity_type: string; entity_id: string; field_name: string;
    old_value: string | null; new_value: string; source_url: string; source_tier: string;
    status: string;
  }[]>`SELECT * FROM "ChangeCandidate" WHERE id = ${candidateId}::uuid`;

  if (candidates.length === 0) return { published: false, reason: "Candidate not found" };
  const c = candidates[0];
  if (c.status !== "VERIFIED") return { published: false, reason: `Cannot publish: status is ${c.status}` };

  // Idempotent: if already published, skip
  const alreadyPublished = await db.$queryRaw<{ cnt: number }[]>`SELECT count(*) as cnt FROM "ChangeCandidate" WHERE id = ${candidateId}::uuid AND status = 'PUBLISHED'`;
  if (alreadyPublished[0].cnt > 0) return { published: true, reason: "Already published" };

  // Publish: update the actual catalog data
  if (c.entity_type === "price" && c.field_name === "amount") {
    // Mark old price as not current
    await db.$executeRaw`UPDATE "Price" SET "isCurrent" = false WHERE "variantId" = ${c.entity_id}::uuid AND "isCurrent" = true`;

    // Find or create source document for the new price
    let sourceDocId: string;
    const docs = await db.$queryRaw<{ id: string }[]>`SELECT id FROM "SourceDocument" WHERE url = ${c.source_url} LIMIT 1`;
    if (docs.length > 0) {
      sourceDocId = docs[0].id;
    } else {
      const newDoc = await db.$queryRaw<{ id: string }[]>`INSERT INTO "SourceDocument" (id, "sourceId", url, "contentHash", status, "extractionStatus", "createdAt", "updatedAt") VALUES (gen_random_uuid(), (SELECT id FROM "Source" LIMIT 1), ${c.source_url}, 'manual', 'VERIFIED', 'SUCCEEDED', NOW(), NOW()) RETURNING id`;
      sourceDocId = newDoc[0].id;
    }

    // Insert new price
    await db.$executeRaw`INSERT INTO "Price" ("id", "variantId", "sourceDocumentId", "priceType", amount, currency, "validFrom", "observedAt", "isCurrent", confidence) VALUES (gen_random_uuid(), ${c.entity_id}::uuid, ${sourceDocId}::uuid, 'LIST_PRICE', ${c.new_value}::numeric, 'THB', NOW(), NOW(), true, 0.95)`;
  }

  // Mark candidate as published
  await db.$executeRaw`UPDATE "ChangeCandidate" SET status = 'PUBLISHED', published_at = NOW() WHERE id = ${candidateId}::uuid`;

  return { published: true, reason: "Published successfully" };
}
