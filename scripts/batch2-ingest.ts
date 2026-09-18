/**
 * Batch #2 ingestion script — verifies additional prices with real evidence.
 */

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import pg from "pg";
import { ingestVerifiedPrice } from "../lib/catalog/evidence-ingestion";
import { BATCH2_EVIDENCE } from "../lib/catalog/batch2-evidence";

async function main() {
  console.log("Starting batch #2 ingestion...");

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
    "honda-civic-type-r-turbo-3990000-2026-verified": "c688fa9e-cbe2-4c4f-803f-20bb40c3e1ab",
    "mg-mg3-hybrid-plus-579900-2026-verified": "9b92adfc-1d51-4652-b04c-161fb07cf06a",
  };

  let verified = 0;
  let rejected = 0;

  for (const evidence of BATCH2_EVIDENCE) {
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
