import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("database schema", () => {
  const schema = readFileSync(resolve(process.cwd(), "prisma/schema.prisma"), "utf8");
  const migration = readFileSync(
    resolve(process.cwd(), "prisma/migrations/20260824123000_schema_review_gaps/migration.sql"),
    "utf8",
  );

  it("defines the core intelligence models", () => {
    for (const model of [
      "Manufacturer", "CarModel", "Variant", "Source", "SourceDocument", "Price",
      "VariantSpec", "VariantSpecExtra", "DimensionsSpec", "PerformanceSpec", "BatterySpec",
      "ChargingSpec", "WarrantySpec", "SafetySpec", "Feature", "VariantFeature", "Alias",
      "Media", "ResearchRun", "ResearchCandidate", "BrochureVerification", "DataChangeLog",
      "ReviewItem", "SourceHint", "CrawlJob", "CrawlEvent", "Embedding",
    ]) {
      expect(schema).toMatch(new RegExp(`model\\s+${model}\\s*\\{`));
    }
  });

  it("defines normalized one-to-one variant specifications", () => {
    for (const model of ["VariantSpecExtra", "DimensionsSpec", "PerformanceSpec", "BatterySpec", "ChargingSpec", "WarrantySpec", "SafetySpec"]) {
      expect(schema).toMatch(new RegExp(`model\\s+${model}[\\s\\S]*?variantId\\s+String\\s+@unique`));
    }
    expect(schema).toMatch(/specExtra\s+VariantSpecExtra\?/);
  });

  it("keeps provenance, media metadata, and a documented vector dimension", () => {
    for (const field of ["sourceDocumentId", "confidence", "sourcePageUrl", "perceptualHash", "sourceMetadata", "documentType", "extractedText", "extractionStatus", "entityType", "entityId", "chunkType", "pageNumber"]) {
      expect(schema).toContain(field);
    }
    expect(schema).toContain('Unsupported("vector(1024)")');
  });

  it("enforces price integrity and current interval exclusion in SQL", () => {
    for (const sql of ["Price_amount_positive", "Price_currency_thb", "Price_valid_interval", "Price_confidence_range", "Price_current_interval_exclusion", "btree_gist", "tsrange", "isCurrent"]) {
      expect(migration).toContain(sql);
    }
  });

  it("records research outcomes and auditable change review", () => {
    for (const field of ["queries", "domainsChecked", "pagesChecked", "documentsFound", "imagesFound", "factsChanged", "error", "evidenceExcerpt", "proposed", "applied", "reviewStatus", "reviewerId"]) {
      expect(schema).toContain(field);
      expect(migration).toContain(`"${field}"`);
    }
    expect(schema).toContain("PARTIAL_SUCCESS");
  });

  it("distinguishes source categories explicitly", () => {
    for (const sourceType of ["OFFICIAL_MANUFACTURER_BROCHURE", "OFFICIAL_MANUFACTURER_PRICE_LIST", "OFFICIAL_MANUFACTURER_PRESS_RELEASE", "AUTHORIZED_DEALER", "AUTOMOTIVE_MEDIA", "NEWS", "SOCIAL", "COMMUNITY", "USER_SUBMISSION"]) {
      expect(schema).toContain(sourceType);
      if (!["NEWS"].includes(sourceType)) expect(migration).toContain(sourceType);
    }
  });
});
