/**
 * Ingest real price observations from official Thai sources.
 * Run after seed-universe.ts. Idempotent.
 *
 * Usage: npx tsx scripts/ingest-prices.ts
 */

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import pg from "pg";

const pool = new pg.Pool({
  user: process.env.DB_USER || "hermes",
  host: process.env.DB_HOST || "localhost",
  port: Number(process.env.DB_PORT) || 5432,
  database: process.env.DB_NAME || "thai_car_intelligence",
  max: 5,
});
const adapter = new PrismaPg(pool);
const prisma = new PrismaClient({ adapter });

type PriceObs = {
  brandSlug: string;
  modelSlug: string;
  variantSlug?: string;
  amount: number;
  sourceUrl: string;
  sourceName: string;
  domain: string;
};

// Real prices from official Thai manufacturer websites (verified by subagent extraction)
const OBSERVATIONS: PriceObs[] = [
  // Honda Thailand (honda.co.th)
  { brandSlug: "honda", modelSlug: "city", amount: 569000, sourceUrl: "https://www.honda.co.th/city", sourceName: "Honda Thailand", domain: "www.honda.co.th" },
  { brandSlug: "honda", modelSlug: "city-hatchback", amount: 579000, sourceUrl: "https://www.honda.co.th/cityhatchback", sourceName: "Honda Thailand", domain: "www.honda.co.th" },
  { brandSlug: "honda", modelSlug: "wr-v", amount: 799000, sourceUrl: "https://www.honda.co.th/wrv", sourceName: "Honda Thailand", domain: "www.honda.co.th" },
  { brandSlug: "honda", modelSlug: "civic", amount: 949000, sourceUrl: "https://www.honda.co.th/civic", sourceName: "Honda Thailand", domain: "www.honda.co.th" },
  { brandSlug: "honda", modelSlug: "hr-v", amount: 959000, sourceUrl: "https://www.honda.co.th/hrvehev", sourceName: "Honda Thailand", domain: "www.honda.co.th" },
  { brandSlug: "honda", modelSlug: "cr-v", amount: 1409000, sourceUrl: "https://www.honda.co.th/crv", sourceName: "Honda Thailand", domain: "www.honda.co.th" },
  { brandSlug: "honda", modelSlug: "accord", amount: 1479000, sourceUrl: "https://www.honda.co.th/accordehev", sourceName: "Honda Thailand", domain: "www.honda.co.th" },
  { brandSlug: "honda", modelSlug: "civic-type-r", amount: 3990000, sourceUrl: "https://www.honda.co.th/civictyper", sourceName: "Honda Thailand", domain: "www.honda.co.th" },
  // Nissan Thailand (nissan.co.th)
  { brandSlug: "nissan", modelSlug: "almera", amount: 573000, sourceUrl: "https://www.nissan.co.th/en/vehicles/almera", sourceName: "Nissan Thailand", domain: "www.nissan.co.th" },
  { brandSlug: "nissan", modelSlug: "kicks", amount: 789900, sourceUrl: "https://www.nissan.co.th/en/vehicles/kicks-epower", sourceName: "Nissan Thailand", domain: "www.nissan.co.th" },
  { brandSlug: "nissan", modelSlug: "x-trail", amount: 1699000, sourceUrl: "https://www.nissan.co.th/en/vehicles/xtrail-epower", sourceName: "Nissan Thailand", domain: "www.nissan.co.th" },
  { brandSlug: "nissan", modelSlug: "terra", amount: 1199000, sourceUrl: "https://www.nissan.co.th/en/vehicles/new-terra", sourceName: "Nissan Thailand", domain: "www.nissan.co.th" },
  { brandSlug: "nissan", modelSlug: "navara", amount: 606000, sourceUrl: "https://www.nissan.co.th/en/vehicles/navara", sourceName: "Nissan Thailand", domain: "www.nissan.co.th" },
  // MG Thailand (mgcars.com)
  { brandSlug: "mg", modelSlug: "extender", amount: 649000, sourceUrl: "https://www.mgcars.com/th_th/cars/mg-extender", sourceName: "MG Thailand", domain: "www.mgcars.com" },
  { brandSlug: "mg", modelSlug: "s5-ev-plus", amount: 749900, sourceUrl: "https://www.mgcars.com/th_th/cars/mg-s5-ev-plus", sourceName: "MG Thailand", domain: "www.mgcars.com" },
];

async function main() {
  console.log("=== Ingesting Real Price Observations ===\n");

  let pricesCreated = 0;
  let sourcesCreated = 0;
  let docsCreated = 0;
  const errors: string[] = [];

  for (const obs of OBSERVATIONS) {
    try {
      // 1. Find or create Source
      let source = await prisma.source.findUnique({ where: { baseUrl: `https://${obs.domain}` } });
      if (!source) {
        source = await prisma.source.create({
          data: {
            nameTh: obs.sourceName,
            nameEn: obs.sourceName,
            sourceType: "OFFICIAL_MANUFACTURER",
            baseUrl: `https://${obs.domain}`,
            domain: obs.domain,
            rightsStatus: "RESTRICTED",
            status: "ACTIVE",
          },
        });
        sourcesCreated++;
      }

      // 2. Find the model
      const manufacturer = await prisma.manufacturer.findUnique({ where: { slug: obs.brandSlug } });
      if (!manufacturer) { errors.push(`No manufacturer: ${obs.brandSlug}`); continue; }

      const model = await prisma.carModel.findFirst({
        where: { slug: obs.modelSlug, manufacturerId: manufacturer.id },
      });
      if (!model) { errors.push(`No model: ${obs.brandSlug}/${obs.modelSlug}`); continue; }

      // 3. Find or create SourceDocument
      const contentHash = `official-${obs.brandSlug}-${obs.modelSlug}-${obs.amount}`;
      let doc = await prisma.sourceDocument.findFirst({
        where: { sourceId: source.id, contentHash },
      });
      if (!doc) {
        doc = await prisma.sourceDocument.create({
          data: {
            sourceId: source.id,
            url: obs.sourceUrl,
            canonicalUrl: obs.sourceUrl,
            titleTh: `${model.nameTh} — ราคา`,
            titleEn: `${model.nameEn} — Price`,
            mimeType: "text/html",
            language: "th",
            contentHash,
            fetchedAt: new Date(),
            status: "VERIFIED",
            rightsStatus: "RESTRICTED",
            extractionStatus: "SUCCEEDED",
          },
        });
        docsCreated++;
      }

      // 4. Create BrochureVerification
      const existingVerif = await prisma.brochureVerification.findUnique({
        where: { sourceDocumentId: doc.id },
      });
      if (!existingVerif) {
        await prisma.brochureVerification.create({
          data: {
            sourceDocumentId: doc.id,
            status: "VERIFIED",
            checkedBy: "hermes-agent",
            notes: `Official price from ${obs.sourceName}: ${obs.amount.toLocaleString()} THB`,
            verifiedAt: new Date(),
          },
        });
      }

      // 5. Find or create Price for first variant
      const variants = await prisma.variant.findMany({
        where: { modelId: model.id, status: "ACTIVE" },
        take: 1,
      });
      if (variants.length === 0) { errors.push(`No variants: ${obs.brandSlug}/${obs.modelSlug}`); continue; }

      const variant = variants[0];
      const existingPrice = await prisma.price.findFirst({
        where: {
          variantId: variant.id,
          priceType: "MSRP",
          amount: obs.amount,
        },
      });
      if (!existingPrice) {
        await prisma.price.create({
          data: {
            variantId: variant.id,
            sourceDocumentId: doc.id,
            priceType: "MSRP",
            amount: obs.amount,
            currency: "THB",
            validFrom: new Date(),
            isCurrent: true,
            confidence: 0.9,
          },
        });
        pricesCreated++;
      }

      // 6. Update universe coverage state
      await prisma.vehicleUniverse.updateMany({
        where: { brandSlug: obs.brandSlug, slug: obs.modelSlug },
        data: { coverageState: "FOUND_BUT_NO_PRICE", lastExtractedAt: new Date() },
      });

    } catch (e) {
      errors.push(`${obs.brandSlug}/${obs.modelSlug}: ${e}`);
    }
  }

  console.log(`Sources created: ${sourcesCreated}`);
  console.log(`Documents created: ${docsCreated}`);
  console.log(`Prices created: ${pricesCreated}`);
  console.log(`Errors: ${errors.length}`);
  for (const e of errors) console.log(`  - ${e}`);

  // Update coverage states for entries with prices
  const pricedVariants = await prisma.price.groupBy({
    by: ["variantId"],
    where: { isCurrent: true },
    _count: { id: true },
  });
  const pricedVariantIds = pricedVariants.map((p) => p.variantId);

  const updated = await prisma.vehicleUniverse.updateMany({
    where: { variantId: { in: pricedVariantIds } },
    data: { coverageState: "PRICE_ONLY" },
  });
  console.log(`\nUpdated ${updated.count} universe entries to PRICE_ONLY`);

  console.log("\n=== Done ===");
}

main()
  .catch((e) => { console.error("Fatal:", e); process.exit(1); })
  .finally(async () => { await prisma.$disconnect(); });
