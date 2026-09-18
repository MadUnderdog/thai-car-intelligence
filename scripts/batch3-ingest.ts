/**
 * Batch #3 ingestion script — verifies MG prices with rendered evidence.
 */

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import pg from "pg";
import { ingestVerifiedPrice } from "../lib/catalog/evidence-ingestion";
import { BATCH3_EVIDENCE } from "../lib/catalog/batch3-evidence";

async function main() {
  console.log("Starting batch #3 ingestion...");

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
    "mg-urban-ev-579900-2026-verified": "2c24f458-e6ae-4fab-ab2d-fff326f66a7c",
    "mg-im5-ev-1549900-2026-verified": "1f412205-461e-48cc-96f1-d2d570f4ff7e",
    "mg-maxus9-ev-1849900-2026-verified": "e59796a4-ebab-498d-8713-a2cbb08a0d36",
    "mg-mg4-standard-669900-2026-verified": "6f2a860c-5f09-456a-bb96-db7284b4c46c",
  };

  let verified = 0;
  let rejected = 0;

  for (const evidence of BATCH3_EVIDENCE) {
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
