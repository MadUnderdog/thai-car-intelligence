-- Database foundation hardening for catalog ingestion.
-- This migration is additive; it intentionally does not drop or reset data.

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TYPE "SourceType" ADD VALUE IF NOT EXISTS 'OFFICIAL_MANUFACTURER_BROCHURE';
ALTER TYPE "SourceType" ADD VALUE IF NOT EXISTS 'OFFICIAL_MANUFACTURER_PRICE_LIST';
ALTER TYPE "SourceType" ADD VALUE IF NOT EXISTS 'OFFICIAL_MANUFACTURER_PRESS_RELEASE';
ALTER TYPE "SourceType" ADD VALUE IF NOT EXISTS 'AUTHORIZED_DEALER';
ALTER TYPE "SourceType" ADD VALUE IF NOT EXISTS 'AUTOMOTIVE_MEDIA';
ALTER TYPE "SourceType" ADD VALUE IF NOT EXISTS 'SOCIAL';
ALTER TYPE "SourceType" ADD VALUE IF NOT EXISTS 'COMMUNITY';
ALTER TYPE "SourceType" ADD VALUE IF NOT EXISTS 'USER_SUBMISSION';
ALTER TYPE "CrawlJobStatus" ADD VALUE IF NOT EXISTS 'PARTIAL_SUCCESS';

CREATE TYPE "ExtractionStatus" AS ENUM ('PENDING', 'RUNNING', 'SUCCEEDED', 'PARTIAL_SUCCESS', 'FAILED');

ALTER TABLE "SourceDocument"
  ADD COLUMN "documentType" TEXT,
  ADD COLUMN "localPath" TEXT,
  ADD COLUMN "objectKey" TEXT,
  ADD COLUMN "extractedText" TEXT,
  ADD COLUMN "extractionMethod" TEXT,
  ADD COLUMN "extractionStatus" "ExtractionStatus" NOT NULL DEFAULT 'PENDING';

ALTER TABLE "Price"
  ADD COLUMN "isCurrent" BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE "Media"
  ADD COLUMN "sourcePageUrl" TEXT,
  ADD COLUMN "role" TEXT,
  ADD COLUMN "perceptualHash" TEXT,
  ADD COLUMN "width" INTEGER,
  ADD COLUMN "height" INTEGER,
  ADD COLUMN "sourceMetadata" JSONB;

ALTER TABLE "ResearchRun"
  ADD COLUMN "entityType" TEXT,
  ADD COLUMN "entityId" TEXT,
  ADD COLUMN "queries" JSONB,
  ADD COLUMN "domainsChecked" JSONB,
  ADD COLUMN "pagesChecked" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN "documentsFound" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN "imagesFound" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN "factsChanged" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN "error" TEXT;

ALTER TABLE "DataChangeLog"
  ADD COLUMN "evidenceExcerpt" TEXT,
  ADD COLUMN "evidence" JSONB,
  ADD COLUMN "proposed" BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN "applied" BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN "reviewStatus" "ReviewStatus" NOT NULL DEFAULT 'OPEN',
  ADD COLUMN "reviewerId" TEXT;

ALTER TABLE "Embedding"
  ADD COLUMN "entityType" TEXT,
  ADD COLUMN "entityId" TEXT,
  ADD COLUMN "chunkType" TEXT,
  ADD COLUMN "pageNumber" INTEGER;

-- Existing rows are preserved and receive explicit metadata defaults before tightening.
UPDATE "Embedding" SET "entityType" = 'SourceDocument', "entityId" = "sourceDocumentId"::text, "chunkType" = 'document'
WHERE "entityType" IS NULL OR "entityId" IS NULL OR "chunkType" IS NULL;
ALTER TABLE "Embedding"
  ALTER COLUMN "entityType" SET NOT NULL,
  ALTER COLUMN "entityId" SET NOT NULL,
  ALTER COLUMN "chunkType" SET NOT NULL;

CREATE TABLE "VariantSpecExtra" (
  "id" UUID NOT NULL,
  "variantId" UUID NOT NULL,
  "data" JSONB NOT NULL,
  CONSTRAINT "VariantSpecExtra_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "VariantSpecExtra_variantId_key" ON "VariantSpecExtra"("variantId");
ALTER TABLE "VariantSpecExtra" ADD CONSTRAINT "VariantSpecExtra_variantId_fkey"
  FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE "DimensionsSpec" (
  "id" UUID NOT NULL, "variantId" UUID NOT NULL,
  "lengthMm" DECIMAL(12,2), "widthMm" DECIMAL(12,2), "heightMm" DECIMAL(12,2),
  "wheelbaseMm" DECIMAL(12,2), "groundClearanceMm" DECIMAL(12,2), "curbWeightKg" DECIMAL(12,2),
  CONSTRAINT "DimensionsSpec_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "DimensionsSpec_variantId_key" ON "DimensionsSpec"("variantId");
ALTER TABLE "DimensionsSpec" ADD CONSTRAINT "DimensionsSpec_variantId_fkey"
  FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE "PerformanceSpec" (
  "id" UUID NOT NULL, "variantId" UUID NOT NULL,
  "powerKw" DECIMAL(12,2), "torqueNm" DECIMAL(12,2), "acceleration0To100S" DECIMAL(8,3),
  "topSpeedKph" DECIMAL(8,2), "rangeKm" DECIMAL(10,2),
  CONSTRAINT "PerformanceSpec_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "PerformanceSpec_variantId_key" ON "PerformanceSpec"("variantId");
ALTER TABLE "PerformanceSpec" ADD CONSTRAINT "PerformanceSpec_variantId_fkey"
  FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE "BatterySpec" (
  "id" UUID NOT NULL, "variantId" UUID NOT NULL,
  "capacityKwh" DECIMAL(10,3), "usableCapacityKwh" DECIMAL(10,3), "chemistry" TEXT, "voltageV" DECIMAL(10,2),
  CONSTRAINT "BatterySpec_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "BatterySpec_variantId_key" ON "BatterySpec"("variantId");
ALTER TABLE "BatterySpec" ADD CONSTRAINT "BatterySpec_variantId_fkey"
  FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE "ChargingSpec" (
  "id" UUID NOT NULL, "variantId" UUID NOT NULL,
  "acPowerKw" DECIMAL(10,2), "dcPowerKw" DECIMAL(10,2), "acTimeMinutes" INTEGER, "dcTimeMinutes" INTEGER, "connectorType" TEXT,
  CONSTRAINT "ChargingSpec_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "ChargingSpec_variantId_key" ON "ChargingSpec"("variantId");
ALTER TABLE "ChargingSpec" ADD CONSTRAINT "ChargingSpec_variantId_fkey"
  FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE "WarrantySpec" (
  "id" UUID NOT NULL, "variantId" UUID NOT NULL,
  "vehicleYears" INTEGER, "vehicleDistanceKm" INTEGER, "batteryYears" INTEGER, "batteryDistanceKm" INTEGER, "terms" JSONB,
  CONSTRAINT "WarrantySpec_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "WarrantySpec_variantId_key" ON "WarrantySpec"("variantId");
ALTER TABLE "WarrantySpec" ADD CONSTRAINT "WarrantySpec_variantId_fkey"
  FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE "SafetySpec" (
  "id" UUID NOT NULL, "variantId" UUID NOT NULL,
  "airbags" INTEGER, "abs" BOOLEAN, "esc" BOOLEAN, "adas" JSONB, "rating" TEXT,
  CONSTRAINT "SafetySpec_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "SafetySpec_variantId_key" ON "SafetySpec"("variantId");
ALTER TABLE "SafetySpec" ADD CONSTRAINT "SafetySpec_variantId_fkey"
  FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "Price"
  ADD CONSTRAINT "Price_amount_positive" CHECK ("amount" > 0),
  ADD CONSTRAINT "Price_currency_thb" CHECK ("currency" = 'THB'),
  ADD CONSTRAINT "Price_valid_interval" CHECK ("validTo" IS NULL OR "validTo" > "validFrom"),
  ADD CONSTRAINT "Price_confidence_range" CHECK ("confidence" >= 0 AND "confidence" <= 1);

-- Current price intervals cannot overlap for a variant and price type.
ALTER TABLE "Price" ADD CONSTRAINT "Price_current_interval_exclusion"
  EXCLUDE USING gist (
    "variantId" WITH =,
    "priceType" WITH =,
    tsrange("validFrom", "validTo", '[)') WITH &&
  ) WHERE ("isCurrent" = true);

CREATE INDEX "Embedding_entity_idx" ON "Embedding"("entityType", "entityId");
CREATE INDEX "Embedding_vector_hnsw_idx" ON "Embedding" USING hnsw ("vector" vector_cosine_ops)
  WITH (m = 16, ef_construction = 64) WHERE "vector" IS NOT NULL;
