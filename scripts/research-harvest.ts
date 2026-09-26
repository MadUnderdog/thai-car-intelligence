/**
 * Research price discovery ingestion script.
 * Stores secondary-source price observations as research candidates.
 * Does NOT mark them as verified — they are REPORTED/UNVERIFIED.
 */

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import pg from "pg";
import { RESEARCH_OBSERVATIONS, type ResearchPriceObservation } from "../lib/catalog/research-observations";

async function main() {
  console.log("Starting research price discovery ingestion...");

  const pool = new pg.Pool({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
    max: 10,
  });
  const adapter = new PrismaPg(pool);
  const prisma = new PrismaClient({ adapter });

  let created = 0;
  let skipped = 0;

  for (const obs of RESEARCH_OBSERVATIONS) {
    // Find or create Source
    let source = await prisma.source.findFirst({
      where: { nameEn: obs.sourceName },
    });
    if (!source) {
      source = await prisma.source.create({
        data: {
          nameTh: obs.sourceName,
          nameEn: obs.sourceName,
          sourceType: "AUTOMOTIVE_MEDIA" as any,
          baseUrl: obs.sourceUrl.split("/").slice(0, 3).join("/"),
          domain: new URL(obs.sourceUrl).hostname,
          rightsStatus: "UNKNOWN",
          status: "ACTIVE",
        },
      });
    }

    // Find or create SourceDocument
    const contentHash = `research-${obs.sourceUrl}-${obs.model}-${obs.variant}-${obs.reportedPrice}`;
    let sourceDoc = await prisma.sourceDocument.findFirst({
      where: { sourceId: source.id, contentHash },
    });
    if (!sourceDoc) {
      sourceDoc = await prisma.sourceDocument.create({
        data: {
          sourceId: source.id,
          url: obs.sourceUrl,
          canonicalUrl: obs.sourceUrl,
          titleTh: obs.articleTitle,
          titleEn: obs.articleTitle,
          mimeType: "text/html",
          language: "th",
          contentHash,
          fetchedAt: new Date(obs.retrievalTimestamp),
          publishedAt: obs.publicationDate ? new Date(obs.publicationDate) : null,
          documentType: "price_article",
          status: "DISCOVERED", // NOT VERIFIED
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
