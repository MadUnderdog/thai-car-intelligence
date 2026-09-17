import "dotenv/config";
import db from "../lib/db";

async function main() {
  console.log("=== Enrichment Worker - Wave 1 ===\n");

  // Get Wave 1 items (EVs with missing specs)
  const items = await db.$queryRaw<{ id: string; variant_id: string; variant_name: string; slug: string; brand: string; model_name: string; fuel_type: string; missing_required: string[] }[]>`
    SELECT eq.id, eq."variantId" as variant_id, v."nameEn" as variant_name, v.slug,
      m."nameEn" as brand, cm."nameEn" as model_name, v."fuelType" as fuel_type,
      eq."missingRequired" as missing_required
    FROM "EnrichmentQueue" eq
    JOIN "Variant" v ON v.id = eq."variantId"
    JOIN "CarModel" cm ON cm.id = v."modelId"
    JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
    WHERE eq.status = 'QUEUED' AND v."fuelType" = 'EV'
    ORDER BY eq.priority DESC LIMIT 6
  `;

  console.log(`Found ${items.length} Wave 1 EV items\n`);

  const results = { processed: 0, blocked: 0 };

  for (const item of items) {
    console.log(`  ${item.brand} ${item.model_name} ${item.variant_name}`);

    // Mark as RESEARCHING
    await db.$executeRaw`UPDATE "EnrichmentQueue" SET status = 'RESEARCHING', "lastAttemptAt" = NOW(), "attemptCount" = "attemptCount" + 1 WHERE id = ${item.id}`;

    // Browser unavailable → BLOCKED
    await db.$executeRaw`UPDATE "EnrichmentQueue" SET status = 'BLOCKED', "errorReason" = 'Browser unavailable for official spec extraction', "lastStep" = 'research' WHERE id = ${item.id}`;
    results.blocked++;
    results.processed++;
  }

  console.log(`\nProcessed: ${results.processed}, Blocked: ${results.blocked}`);

  const stats = await db.$queryRaw<{ status: string; cnt: number }[]>`SELECT status, count(*) as cnt FROM "EnrichmentQueue" GROUP BY status`;
  console.log("\nQueue status:");
  for (const s of stats) console.log(`  ${s.status}: ${s.cnt}`);
}

main().catch(console.error);
