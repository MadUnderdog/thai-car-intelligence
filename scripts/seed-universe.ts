/**
 * Universe Discovery Script — Seeds the master Thailand vehicle universe.
 *
 * Usage: npx tsx scripts/seed-universe.ts
 *
 * Idempotent: safe to re-run.
 */

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import pg from "pg";
import { seedUniverse, getUniverseDBStats } from "../lib/discovery/universe-seeder";
import { createExtractionQueue } from "../lib/discovery/extraction-pipeline";

const pool = new pg.Pool({
  user: process.env.DB_USER || "hermes",
  host: process.env.DB_HOST || "localhost",
  port: Number(process.env.DB_PORT) || 5432,
  database: process.env.DB_NAME || "thai_car_intelligence",
  max: 5,
});
const adapter = new PrismaPg(pool);
const prisma = new PrismaClient({ adapter });

async function main() {
  console.log("=== Thailand Vehicle Universe Discovery ===\n");

  // 1. Seed universe
  console.log("Step 1: Seeding universe registry...");
  const seedResult = await seedUniverse(prisma);
  console.log(`  Brands processed: ${seedResult.brandsProcessed}`);
  console.log(`  Brands created: ${seedResult.brandsCreated}`);
  console.log(`  Models processed: ${seedResult.modelsProcessed}`);
  console.log(`  Models created: ${seedResult.modelsCreated}`);
  console.log(`  Variants processed: ${seedResult.variantsProcessed}`);
  console.log(`  Variants created: ${seedResult.variantsCreated}`);
  console.log(`  Universe entries created: ${seedResult.universeEntriesCreated}`);
  console.log(`  Discovery sources created: ${seedResult.discoverySourcesCreated}`);
  if (seedResult.errors.length > 0) {
    console.log(`  Errors: ${seedResult.errors.length}`);
    for (const e of seedResult.errors.slice(0, 5)) console.log(`    - ${e}`);
  }

  // 2. Create extraction queue
  console.log("\nStep 2: Creating extraction queue...");
  const queueResult = await createExtractionQueue(prisma);
  console.log(`  Jobs created: ${queueResult.created}`);
  console.log(`  Jobs skipped: ${queueResult.skipped}`);
  if (queueResult.errors.length > 0) {
    console.log(`  Errors: ${queueResult.errors.length}`);
  }

  // 3. DB stats
  console.log("\nStep 3: Database statistics...");
  const stats = await getUniverseDBStats(prisma);
  console.log(`  DB: ${JSON.stringify(stats.db, null, 2)}`);
  console.log(`  File universe: ${JSON.stringify(stats.fileStats, null, 2)}`);
  console.log(`  Coverage states: ${JSON.stringify(stats.coverageStates, null, 2)}`);

  console.log("\n=== Universe discovery complete ===");
}

main()
  .catch((e) => {
    console.error("Fatal error:", e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
