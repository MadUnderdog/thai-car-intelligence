/**
 * Ingest harvested spec observations into database via Prisma.
 */

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import pg from "pg";
import * as fs from "fs";

interface SpecObs {
  source_name: string;
  source_tier: string;
  source_url: string;
  article_title: string | null;
  manufacturer: string;
  model: string;
  variant: string;
  spec_class: string;
  spec_key: string;
  raw_value: string;
  normalized_value: number | null;
  unit: string | null;
  source_excerpt: string;
  retrieval_timestamp: string;
  content_hash: string;
  model_year: string | null;
  market: string;
}

async function main() {
  console.log("Starting spec observation ingestion...");

  const pool = new pg.Pool({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
    max: 10,
  });
  const adapter = new PrismaPg(pool);
  const prisma = new PrismaClient({ adapter });

  const raw = fs.readFileSync("/home/ubuntu/Projects/thai-car-intelligence/scripts/harvested-specs.json", "utf-8");
  const specs: SpecObs[] = JSON.parse(raw);

  // Add manually extracted specs
  const manual: SpecObs[] = [
    { source_name: "HeadLight Magazine", source_tier: "secondary_automotive_media",
      source_url: "https://www.headlightmag.com/xpeng-l03-standard-long-range-thailand-specs/",
      article_title: "Xpeng L03 Specs", manufacturer: "Xpeng", model: "L03", variant: "Standard",
      spec_class: "battery", spec_key: "capacityKwh", raw_value: "58.3 kWh",
      normalized_value: 58.3, unit: "kWh", source_excerpt: "แบตฯ LFP 58.3 kWh",
      retrieval_timestamp: "2026-09-18T15:00:00Z", content_hash: "xpeng-l03-bat-58", model_year: "2026", market: "Thailand" },
    { source_name: "HeadLight Magazine", source_tier: "secondary_automotive_media",
      source_url: "https://www.headlightmag.com/xpeng-l03-standard-long-range-thailand-specs/",
      article_title: "Xpeng L03 Specs", manufacturer: "Xpeng", model: "L03", variant: "Long Range",
      spec_class: "battery", spec_key: "capacityKwh", raw_value: "71.2 kWh",
      normalized_value: 71.2, unit: "kWh", source_excerpt: "แบตฯ LFP 71.2 kWh",
      retrieval_timestamp: "2026-09-18T15:00:00Z", content_hash: "xpeng-l03-bat-71", model_year: "2026", market: "Thailand" },
    { source_name: "HeadLight Magazine", source_tier: "secondary_automotive_media",
      source_url: "https://www.headlightmag.com/xpeng-l03-standard-long-range-thailand-specs/",
      article_title: "Xpeng L03 Specs", manufacturer: "Xpeng", model: "L03", variant: "Long Range",
      spec_class: "performance", spec_key: "rangeKm", raw_value: "600 km",
      normalized_value: 600, unit: "km", source_excerpt: "วิ่งไกลสุด 600 km (NEDC)",
      retrieval_timestamp: "2026-09-18T15:00:00Z", content_hash: "xpeng-l03-range-600", model_year: "2026", market: "Thailand" },
    { source_name: "HeadLight Magazine", source_tier: "secondary_automotive_media",
      source_url: "https://www.headlightmag.com/specification-gwm-tank-500-diesel-3000-turbo-my2026/",
      article_title: "GWM Tank 500 Specs", manufacturer: "GWM", model: "Tank 500", variant: "Diesel",
      spec_class: "performance", spec_key: "powerKw", raw_value: "231 แรงม้า",
      normalized_value: 231, unit: "hp", source_excerpt: "231 แรงม้า",
      retrieval_timestamp: "2026-09-18T15:00:00Z", content_hash: "gwm-tank500-pwr-231", model_year: "2026", market: "Thailand" },
    { source_name: "HeadLight Magazine", source_tier: "secondary_automotive_media",
      source_url: "https://www.headlightmag.com/specification-gwm-tank-500-diesel-3000-turbo-my2026/",
      article_title: "GWM Tank 500 Specs", manufacturer: "GWM", model: "Tank 500", variant: "Diesel",
      spec_class: "performance", spec_key: "torqueNm", raw_value: "620 นิวตันเมตร",
      normalized_value: 620, unit: "Nm", source_excerpt: "620 นิวตันเมตร",
      retrieval_timestamp: "2026-09-18T15:00:00Z", content_hash: "gwm-tank500-trq-620", model_year: "2026", market: "Thailand" },
  ];

  const allSpecs = [...specs, ...manual];
  console.log(`Total specs to ingest: ${allSpecs.length}`);

  let created = 0;
  let skipped = 0;

  for (const spec of allSpecs) {
    // Find or create Source
    const baseUrl = `https://${new URL(spec.source_url).hostname}`;
    let source = await prisma.source.findFirst({ where: { baseUrl } });
    if (!source) {
      source = await prisma.source.create({
        data: {
          nameTh: spec.source_name,
          nameEn: spec.source_name,
          sourceType: "AUTOMOTIVE_MEDIA" as any,
          baseUrl,
          domain: new URL(spec.source_url).hostname,
          rightsStatus: "UNKNOWN",
          status: "ACTIVE",
        },
      });
    }

    // Find or create SourceDocument
    let sourceDoc = await prisma.sourceDocument.findFirst({
      where: { sourceId: source.id, contentHash: spec.content_hash },
    });
    if (!sourceDoc) {
      sourceDoc = await prisma.sourceDocument.create({
        data: {
          sourceId: source.id,
          url: spec.source_url,
          canonicalUrl: spec.source_url,
          titleTh: spec.article_title || "Spec Article",
          titleEn: spec.article_title || "Spec Article",
          mimeType: "text/html",
          language: "th",
          contentHash: spec.content_hash,
          fetchedAt: new Date(spec.retrieval_timestamp),
          documentType: "spec_article",
          status: "DISCOVERED",
          rightsStatus: "UNKNOWN",
          extractionStatus: "SUCCEEDED",
        },
      });
    }

    // Find variant
    const slug = spec.model.toLowerCase().replace(/\s+/g, "-");
    const variant = await prisma.variant.findFirst({
      where: { slug: { contains: slug } },
    });

    if (!variant) {
      console.log(`  SKIP: No variant found for ${spec.model}`);
      skipped++;
      continue;
    }

    // Insert VariantSpec observation
    try {
      await prisma.variantSpec.create({
        data: {
          variantId: variant.id,
          sourceDocumentId: sourceDoc.id,
          key: spec.spec_key,
          valueTh: spec.raw_value,
          valueEn: spec.raw_value,
          valueNumeric: spec.normalized_value,
          unit: spec.unit,
          confidence: 0.7,
        },
      });
      created++;
    } catch (e: any) {
      if (e?.code === "P2002") {
        skipped++; // Duplicate
      } else {
        console.log(`  ERROR: ${spec.model} ${spec.spec_key}: ${e.message}`);
      }
    }
  }

  // Report final state
  const stats = await prisma.$queryRaw<{ specs: bigint; sources: bigint; docs: bigint; verified: bigint }[]>`
    SELECT 
      (SELECT count(*) FROM "VariantSpec") as specs,
      (SELECT count(*) FROM "Source") as sources,
      (SELECT count(*) FROM "SourceDocument") as docs,
      (SELECT count(*) FROM "Price" WHERE "isCurrent" = true AND "sourceDocumentId" IS NOT NULL) as verified
  `;

  console.log(`\nFinal state:`);
  console.log(`  VariantSpec observations: ${stats[0].specs}`);
  console.log(`  Sources: ${stats[0].sources}`);
  console.log(`  SourceDocuments: ${stats[0].docs}`);
  console.log(`  Verified prices: ${stats[0].verified}`);
  console.log(`  This run: ${created} created, ${skipped} skipped`);

  await prisma.$disconnect();
  await pool.end();
}

main().catch(console.error);
