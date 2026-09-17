/**
 * Pilot ingestion script — verifies 3 Honda prices with real evidence.
 * Safe to run multiple times (idempotent).
 */

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import pg from "pg";
import { ingestVerifiedPrice } from "../lib/catalog/evidence-ingestion";
import { PILOT_EVIDENCE } from "../lib/catalog/pilot-evidence";

async function main() {
  console.log("Starting pilot ingestion...");

  // Create Prisma client with driver adapter
  const pool = new pg.Pool({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
    max: 10,
  });
  const adapter = new PrismaPg(pool);
  const prisma = new PrismaClient({ adapter });

  // Map evidence to price IDs
  const priceMap: Record<string, string> = {
    "honda-city-ehev-569000-2026-verified": "90c93ea1-0c5f-4555-ad7b-2fd7e0c1794c", // Honda City e:HEV
    "honda-civic-ehev-949000-2026-verified": "65b27d8e-f708-4587-ab87-16245de930eb", // Honda Civic e:HEV
    "honda-hrv-ehev-949000-2026-verified": "61b46c36-6937-417d-8b1e-c0c60eec05f3", // Honda HR-V e:HEV
  };

  let verified = 0;
  let rejected = 0;

  for (const evidence of PILOT_EVIDENCE) {
    const priceId = priceMap[evidence.contentHash];
    if (!priceId) {
      console.log(`SKIP: No price ID for ${evidence.contentHash}`);
      continue;
    }

    const result = await ingestVerifiedPrice(prisma, priceId, evidence);
    if (result.success) {
      console.log(`✓ VERIFIED: ${evidence.modelNameInSource} ${evidence.variantNameInSource} — ${evidence.priceText} THB`);
      verified++;
    } else {
      console.log(`✗ REJECTED: ${evidence.modelNameInSource} ${evidence.variantNameInSource} — ${result.reason}`);
      rejected++;
    }
  }

  // Report final state
  const stats = await prisma.$queryRaw<{ verified: bigint; unverified: bigint }[]>`
    SELECT 
      (SELECT count(*) FROM "Price" WHERE "isCurrent" = true AND "sourceDocumentId" IS NOT NULL) as verified,
      (SELECT count(*) FROM "Price" WHERE "isCurrent" = true AND "sourceDocumentId" IS NULL) as unverified
  `;

  console.log(`\nFinal state:`);
  console.log(`  Verified prices: ${stats[0].verified}`);
  console.log(`  Unverified prices: ${stats[0].unverified}`);
  console.log(`  This run: ${verified} verified, ${rejected} rejected`);

  await prisma.$disconnect();
  await pool.end();
}

main().catch(console.error);
