-- Discovery Registry & Extraction Engine tables
-- Non-destructive: only adds new tables, no drops, no alters to existing tables

CREATE TYPE "DiscoveryStatus" AS ENUM ('DISCOVERED', 'EXTRACTING', 'EXTRACTED', 'VERIFIED', 'FAILED', 'STALE');
CREATE TYPE "ExtractionJobStatus" AS ENUM ('QUEUED', 'RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED', 'CANCELLED', 'RETRY_SCHEDULED');
CREATE TYPE "CoverageGapState" AS ENUM ('NOT_DISCOVERED', 'FOUND_BUT_NO_PRICE', 'FOUND_BUT_NO_OFFICIAL_SOURCE', 'PRICE_ONLY', 'PARTIAL_SPECS', 'FULL_SPECS_UNVERIFIED', 'VERIFIED', 'STALE', 'CONFLICT', 'EXTRACTION_FAILED', 'NOT_APPLICABLE');
CREATE TYPE "DiscoveryJobStatus" AS ENUM ('QUEUED', 'RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED');

CREATE TABLE "DiscoverySource" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "manufacturerId" UUID,
    "nameTh" TEXT NOT NULL,
    "nameEn" TEXT NOT NULL,
    "baseUrl" TEXT NOT NULL,
    "catalogUrl" TEXT,
    "priceListUrl" TEXT,
    "brochureUrlPattern" TEXT,
    "domain" TEXT NOT NULL,
    "sourceType" "SourceType" NOT NULL,
    "discoveryMethod" TEXT,
    "priority" INTEGER NOT NULL DEFAULT 0,
    "enabled" BOOLEAN NOT NULL DEFAULT true,
    "lastDiscoveredAt" TIMESTAMP(3),
    "lastCheckedAt" TIMESTAMP(3),
    "contentHash" TEXT,
    "status" "DiscoveryStatus" NOT NULL DEFAULT 'DISCOVERED',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "DiscoverySource_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "DiscoverySource_baseUrl_key" UNIQUE ("baseUrl"),
    CONSTRAINT "DiscoverySource_manufacturerId_fkey" FOREIGN KEY ("manufacturerId") REFERENCES "Manufacturer"("id") ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE INDEX "DiscoverySource_manufacturerId_enabled_idx" ON "DiscoverySource"("manufacturerId", "enabled");

CREATE TABLE "VehicleUniverse" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "manufacturerId" UUID,
    "carModelId" UUID,
    "variantId" UUID,
    "nameTh" TEXT NOT NULL,
    "nameEn" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "brandSlug" TEXT NOT NULL,
    "generation" TEXT,
    "modelYear" INTEGER,
    "status" "RecordStatus" NOT NULL DEFAULT 'ACTIVE',
    "coverageState" "CoverageGapState" NOT NULL DEFAULT 'NOT_DISCOVERED',
    "discoverySourceId" UUID,
    "officialUrl" TEXT,
    "discoveryUrl" TEXT,
    "aliases" JSONB,
    "identityConfidence" DECIMAL(5,4),
    "discoveredAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "lastCheckedAt" TIMESTAMP(3),
    "lastExtractedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "VehicleUniverse_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "VehicleUniverse_brandSlug_slug_modelYear_key" UNIQUE ("brandSlug", "slug", "modelYear"),
    CONSTRAINT "VehicleUniverse_manufacturerId_fkey" FOREIGN KEY ("manufacturerId") REFERENCES "Manufacturer"("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "VehicleUniverse_carModelId_fkey" FOREIGN KEY ("carModelId") REFERENCES "CarModel"("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "VehicleUniverse_variantId_fkey" FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "VehicleUniverse_discoverySourceId_fkey" FOREIGN KEY ("discoverySourceId") REFERENCES "DiscoverySource"("id") ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE INDEX "VehicleUniverse_coverageState_idx" ON "VehicleUniverse"("coverageState");
CREATE INDEX "VehicleUniverse_brandSlug_idx" ON "VehicleUniverse"("brandSlug");
CREATE INDEX "VehicleUniverse_status_idx" ON "VehicleUniverse"("status");

CREATE TABLE "DiscoveryJob" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" TEXT NOT NULL,
    "status" "DiscoveryJobStatus" NOT NULL DEFAULT 'QUEUED',
    "brandSlug" TEXT,
    "targetsFound" INTEGER NOT NULL DEFAULT 0,
    "modelsFound" INTEGER NOT NULL DEFAULT 0,
    "variantsFound" INTEGER NOT NULL DEFAULT 0,
    "newDiscoveries" INTEGER NOT NULL DEFAULT 0,
    "error" TEXT,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "DiscoveryJob_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "DiscoveryJob_status_createdAt_idx" ON "DiscoveryJob"("status", "createdAt");

CREATE TABLE "ExtractionJob" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" TEXT NOT NULL,
    "status" "ExtractionJobStatus" NOT NULL DEFAULT 'QUEUED',
    "priority" INTEGER NOT NULL DEFAULT 0,
    "vehicleUniverseId" UUID,
    "sourceUrl" TEXT NOT NULL,
    "extractionMethod" TEXT,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "maxAttempts" INTEGER NOT NULL DEFAULT 3,
    "lastError" TEXT,
    "nextRetryAt" TIMESTAMP(3),
    "pricesFound" INTEGER NOT NULL DEFAULT 0,
    "specsFound" INTEGER NOT NULL DEFAULT 0,
    "contentHash" TEXT,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ExtractionJob_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "ExtractionJob_vehicleUniverseId_fkey" FOREIGN KEY ("vehicleUniverseId") REFERENCES "VehicleUniverse"("id") ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE INDEX "ExtractionJob_status_priority_idx" ON "ExtractionJob"("status", "priority");
CREATE INDEX "ExtractionJob_vehicleUniverseId_idx" ON "ExtractionJob"("vehicleUniverseId");
CREATE INDEX "ExtractionJob_nextRetryAt_idx" ON "ExtractionJob"("nextRetryAt");

CREATE TABLE "SourceFreshness" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "sourceDocumentId" UUID NOT NULL,
    "lastSeenAt" TIMESTAMP(3) NOT NULL,
    "lastSuccessfulExtractionAt" TIMESTAMP(3),
    "contentHash" TEXT,
    "previousHash" TEXT,
    "changed" BOOLEAN NOT NULL DEFAULT false,
    "parserVersion" TEXT,
    "extractorVersion" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SourceFreshness_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "SourceFreshness_sourceDocumentId_key" UNIQUE ("sourceDocumentId"),
    CONSTRAINT "SourceFreshness_sourceDocumentId_fkey" FOREIGN KEY ("sourceDocumentId") REFERENCES "SourceDocument"("id") ON DELETE CASCADE ON UPDATE CASCADE
);
