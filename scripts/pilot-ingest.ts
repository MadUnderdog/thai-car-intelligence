/**
 * Pilot ingestion script — verifies Honda prices with real evidence.
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
    "honda-city-ehev-569000-2026-verified": "90c93ea1-0c5f-4555-ad7b-2fd7e0c1794c",
    "honda-civic-ehev-949000-2026-verified": "65b27d8e-f708-4587-ab87-16245de930eb",
    "honda-city-hatchback-ehev-579000-2026-verified": "12139065-ac64-4883-9969-5be421b800c7",
    "honda-crv-ehev-1409000-2026-verified": "b8252194-3739-4d8a-9367-4fade37fb67f",
    "honda-brv-915000-2026-verified": "0018ee8a-5bb2-48e6-a6c0-fcb393100c6e",
    "honda-wrv-799000-2026-verified": "06ef60bf-ef77-4033-a212-0708815b04a8",
    "honda-accord-ehev-1479000-2026-verified": "89066132-45ac-4575-af1c-16a867820553",
    "honda-en2-ev-1429000-2026-verified": "3da122fa-679d-451c-a4ac-fa6a351abe47",
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
