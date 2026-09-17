import { createHash } from "node:crypto";
import { z } from "zod";
import type { PrismaClient } from "@prisma/client";
import db from "../db";

const officialSourceTypes = [
  "OFFICIAL_MANUFACTURER",
  "OFFICIAL_MANUFACTURER_PRICE_LIST",
  "OFFICIAL_MANUFACTURER_PRESS_RELEASE",
] as const;
const priceTypes = ["MSRP", "LIST_PRICE", "PROMOTION", "FINANCE", "LEASE", "USED_PRICE", "OTHER"] as const;

const provenanceSchema = z.object({
  url: z.string().url(),
  evidence: z.string().trim().min(1),
  pageNumber: z.number().int().positive().optional(),
  title: z.string().trim().min(1).optional(),
});

const priceSchema = z.object({
  amount: z.number().finite().positive(),
  currency: z.literal("THB").default("THB"),
  type: z.enum(priceTypes).default("LIST_PRICE"),
  provenance: provenanceSchema,
});

const identitySchema = z.object({
  nameTh: z.string().trim().min(1),
  nameEn: z.string().trim().min(1),
  slug: z.string().trim().min(1).regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
});

/** The strict contract used by the verified importer and its CLI. */
export const verifiedBundleSchema = z.object({
  version: z.string().trim().min(1),
  source: z.object({
    url: z.string().url(),
    title: z.string().trim().min(1),
    sourceType: z.enum(officialSourceTypes),
    retrievedAt: z.coerce.date(),
    evidenceExcerpt: z.string().trim().min(1),
    contentHash: z.string().trim().regex(/^[a-f0-9]{64}$/i),
    verification: z.object({
      type: z.literal("MODEL_PAGE"),
      status: z.literal("VERIFIED"),
      notes: z.string().trim().min(1),
    }),
  }),
  records: z.array(z.object({
    manufacturer: identitySchema,
    model: identitySchema.extend({ modelYear: z.number().int().positive().optional() }),
    variant: identitySchema,
    prices: z.array(priceSchema).min(1),
  })).min(1),
}).superRefine((bundle, ctx) => {
  const sourceUrl = new URL(bundle.source.url);
  if (!/^(?:www\.)?toyota\.co\.th$/i.test(sourceUrl.hostname) && bundle.records.some((r) => r.manufacturer.slug === "toyota")) {
    ctx.addIssue({ code: "custom", path: ["source", "url"], message: "Toyota records must use an official Toyota source" });
  }
  if (bundle.source.verification.notes.toLowerCase().includes("brochure") && bundle.source.verification.notes.toLowerCase().includes("verified")) {
    ctx.addIssue({ code: "custom", path: ["source", "verification", "notes"], message: "A model page must not be labelled as brochure-verified" });
  }
});

export type VerifiedBundle = z.infer<typeof verifiedBundleSchema>;
export type VerifiedImportResult = { dryRun: boolean; sourceUrl: string; records: number; prices: number };

// Retained for callers of the original validation-only API. New imports must use verifiedBundleSchema.
const legacyPriceSchema = z.object({ amount: z.number().finite().positive(), currency: z.literal("THB").default("THB"), type: z.enum(priceTypes).default("LIST_PRICE"), provenance: provenanceSchema.optional() });
const factSchema = z.object({ key: z.string().trim().min(1), value: z.unknown(), provenance: provenanceSchema.optional() });
const legacyIdentity = z.object({ nameTh: z.string().trim().min(1), nameEn: z.string().trim().min(1), slug: z.string().trim().min(1) });
export const sourceBundleSchema = z.object({ version: z.string().optional(), records: z.array(z.object({ manufacturer: legacyIdentity, model: legacyIdentity.extend({ modelYear: z.number().int().optional() }), variant: legacyIdentity, prices: z.array(legacyPriceSchema).default([]), facts: z.array(factSchema).default([]), provenance: provenanceSchema.optional() }).superRefine((record, ctx) => { if (record.prices.some((p) => !p.provenance && !record.provenance) || record.facts.some((f) => !f.provenance && !record.provenance)) ctx.addIssue({ code: "custom", path: ["provenance"], message: "Important facts require source URL and evidence" }); })) });
export type SourceBundle = z.infer<typeof sourceBundleSchema>;
export function parseSourceBundle(input: unknown): SourceBundle { return sourceBundleSchema.parse(input); }
export function validateSourceBundle(input: unknown) { return sourceBundleSchema.safeParse(input); }
export function parseVerifiedBundle(input: unknown): VerifiedBundle { return verifiedBundleSchema.parse(input); }
export function validateVerifiedBundle(input: unknown) { return verifiedBundleSchema.safeParse(input); }

function sourceBaseUrl(url: string): string { const parsed = new URL(url); return `${parsed.protocol}//${parsed.host}`; }
function domain(url: string): string { return new URL(url).hostname; }
function slugHash(value: string): string { return createHash("sha256").update(value).digest("hex"); }

/** Import only an already-verified, manually curated bundle. It never fetches the source URL. */
export async function importVerifiedBundle(input: unknown, client: PrismaClient = db, options: { dryRun?: boolean } = {}): Promise<VerifiedImportResult> {
  const bundle = parseVerifiedBundle(input);
  const prices = bundle.records.reduce((sum, record) => sum + record.prices.length, 0);
  const result = { dryRun: options.dryRun === true, sourceUrl: bundle.source.url, records: bundle.records.length, prices };
  if (options.dryRun) return result;

  await client.$transaction(async (tx) => {
    const firstManufacturer = bundle.records[0].manufacturer;
    const sourceManufacturer = await tx.manufacturer.upsert({
      where: { slug: firstManufacturer.slug },
      create: { ...firstManufacturer },
      update: { nameTh: firstManufacturer.nameTh, nameEn: firstManufacturer.nameEn, status: "ACTIVE" },
    });
    const source = await tx.source.upsert({
      where: { baseUrl: sourceBaseUrl(bundle.source.url) },
      create: { baseUrl: sourceBaseUrl(bundle.source.url), domain: domain(bundle.source.url), nameTh: "แหล่งข้อมูลทางการ", nameEn: bundle.source.title, sourceType: bundle.source.sourceType, manufacturerId: sourceManufacturer.id, authority: 1, status: "ACTIVE" },
      update: { domain: domain(bundle.source.url), nameEn: bundle.source.title, sourceType: bundle.source.sourceType, manufacturerId: sourceManufacturer.id, authority: 1, status: "ACTIVE" },
    });
    const document = await tx.sourceDocument.upsert({
      where: { sourceId_contentHash: { sourceId: source.id, contentHash: bundle.source.contentHash } },
      create: { sourceId: source.id, url: bundle.source.url, canonicalUrl: bundle.source.url, titleEn: bundle.source.title, mimeType: "text/html", language: "th", contentHash: bundle.source.contentHash, fetchedAt: bundle.source.retrievedAt, extractedText: bundle.source.evidenceExcerpt, extractionMethod: "manual-verified-excerpt", extractionStatus: "SUCCEEDED", documentType: "model-page", status: "VERIFIED" },
      update: { url: bundle.source.url, canonicalUrl: bundle.source.url, titleEn: bundle.source.title, fetchedAt: bundle.source.retrievedAt, extractedText: bundle.source.evidenceExcerpt, extractionMethod: "manual-verified-excerpt", extractionStatus: "SUCCEEDED", documentType: "model-page", status: "VERIFIED" },
    });
    // Compatibility with the existing schema: this VERIFIED row certifies page evidence only.
    // It is explicitly MODEL_PAGE and must never be interpreted as brochure verification.
    await tx.brochureVerification.upsert({
      where: { sourceDocumentId: document.id },
      create: { sourceDocumentId: document.id, status: "VERIFIED", checkedBy: "verified-bundle-import", verifiedAt: bundle.source.retrievedAt, notes: `${bundle.source.verification.notes} This verifies official model-page evidence only; brochure contents remain NEEDS_REVIEW.` },
      update: { status: "VERIFIED", checkedBy: "verified-bundle-import", verifiedAt: bundle.source.retrievedAt, notes: `${bundle.source.verification.notes} This verifies official model-page evidence only; brochure contents remain NEEDS_REVIEW.` },
    });
    for (const record of bundle.records) {
      const manufacturer = await tx.manufacturer.upsert({ where: { slug: record.manufacturer.slug }, create: { ...record.manufacturer }, update: { nameTh: record.manufacturer.nameTh, nameEn: record.manufacturer.nameEn, status: "ACTIVE" } });
      const model = await tx.carModel.findFirst({ where: { manufacturerId: manufacturer.id, slug: record.model.slug, modelYear: record.model.modelYear ?? null } }) ?? await tx.carModel.create({ data: { manufacturerId: manufacturer.id, ...record.model, status: "ACTIVE" } });
      const updatedModel = await tx.carModel.update({ where: { id: model.id }, data: { nameTh: record.model.nameTh, nameEn: record.model.nameEn, status: "ACTIVE" } });
      const variant = await tx.variant.findFirst({ where: { modelId: updatedModel.id, slug: record.variant.slug, modelYear: record.model.modelYear ?? null } }) ?? await tx.variant.create({ data: { modelId: updatedModel.id, ...record.variant, modelYear: record.model.modelYear ?? null, status: "ACTIVE" } });
      await tx.variant.update({ where: { id: variant.id }, data: { nameTh: record.variant.nameTh, nameEn: record.variant.nameEn, status: "ACTIVE" } });
      await tx.price.updateMany({ where: { variantId: variant.id, isCurrent: true }, data: { isCurrent: false } });
      for (const item of record.prices) {
        await tx.price.upsert({
          where: { variantId_sourceDocumentId_priceType_amount_validFrom: { variantId: variant.id, sourceDocumentId: document.id, priceType: item.type, amount: item.amount, validFrom: bundle.source.retrievedAt } },
          create: { variantId: variant.id, sourceDocumentId: document.id, priceType: item.type, amount: item.amount, currency: "THB", validFrom: bundle.source.retrievedAt, observedAt: bundle.source.retrievedAt, pageNumber: item.provenance.pageNumber, confidence: 1, isCurrent: true },
          update: { currency: "THB", observedAt: bundle.source.retrievedAt, pageNumber: item.provenance.pageNumber, confidence: 1, isCurrent: true },
        });
      }
    }
  });
  return result;
}

export { slugHash };
