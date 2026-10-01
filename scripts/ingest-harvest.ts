/**
 * Batch4 ingestion — loads deduped observations from JSON into database.
 */

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import pg from "pg";
import * as fs from "fs";

interface HarvestedObservation {
  source_name: string;
  source_tier: string;
  source_url: string;
  article_title: string | null;
  publication_date: string | null;
  manufacturer: string;
  model: string;
  variant: string;
  reported_price: number;
  price_text: string;
  price_type: string;
  market: string;
  model_year: string | null;
  source_excerpt: string;
  retrieval_timestamp: string;
  content_hash: string;
}

async function main() {
  console.log("Starting batch4 mass harvest ingestion...");

  const pool = new pg.Pool({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
    max: 10,
  });
  const adapter = new PrismaPg(pool);
  const prisma = new PrismaClient({ adapter });

  // Load observations
  const raw = fs.readFileSync("/home/ubuntu/Projects/thai-car-intelligence/scripts/deduped-observations.json", "utf-8");
  const observations: HarvestedObservation[] = JSON.parse(raw);
  console.log(`Loaded ${observations.length} observations`);

  let created = 0;
  let skipped = 0;

  for (const obs of observations) {
    // Find or create Source
    let source = await prisma.source.findFirst({
      where: { nameEn: obs.source_name },
    });
    if (!source) {
      const baseUrl = `https://${new URL(obs.source_url).hostname}`;
      source = await prisma.source.create({
        data: {
          nameTh: obs.source_name,
          nameEn: obs.source_name,
          sourceType: "AUTOMOTIVE_MEDIA" as any,
          baseUrl,
          domain: new URL(obs.source_url).hostname,
          rightsStatus: "UNKNOWN",
          status: "ACTIVE",
        },
      });
    }

    // Find or create SourceDocument
    const contentHash = obs.content_hash;
    let sourceDoc = await prisma.sourceDocument.findFirst({
      where: { sourceId: source.id, contentHash },
    });
    if (!sourceDoc) {
      sourceDoc = await prisma.sourceDocument.create({
        data: {
          sourceId: source.id,
          url: obs.source_url,
          canonicalUrl: obs.source_url,
          titleTh: obs.article_title || "Unknown",
          titleEn: obs.article_title || "Unknown",
          mimeType: "text/html",
          language: "th",
          contentHash,
          fetchedAt: new Date(obs.retrieval_timestamp),
          publishedAt: obs.publication_date ? new Date(obs.publication_date) : null,
          documentType: "price_article",
          status: "DISCOVERED",
          rightsStatus: "UNKNOWN",
          extractionStatus: "SUCCEEDED",
        },
      });
      created++;
    } else {
      skipped++;
    }
  }

  // Report final state
  const stats = await prisma.$queryRaw<{ sources: bigint; documents: bigint; verified_prices: bigint }[]>`
    SELECT 
      (SELECT count(*) FROM "Source") as sources,
      (SELECT count(*) FROM "SourceDocument") as documents,
      (SELECT count(*) FROM "Price" WHERE "isCurrent" = true AND "sourceDocumentId" IS NOT NULL) as verified_prices
  `;

  console.log(`\nFinal state:`);
  console.log(`  Sources: ${stats[0].sources}`);
  console.log(`  SourceDocuments: ${stats[0].documents}`);
  console.log(`  Verified prices: ${stats[0].verified_prices}`);
  console.log(`  This run: ${created} created, ${skipped} skipped`);

  await prisma.$disconnect();
  await pool.end();
}

main().catch(console.error);
