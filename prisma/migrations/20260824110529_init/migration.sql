CREATE EXTENSION IF NOT EXISTS "vector";

-- CreateEnum
CREATE TYPE "RecordStatus" AS ENUM ('DRAFT', 'ACTIVE', 'ARCHIVED');

-- CreateEnum
CREATE TYPE "SourceType" AS ENUM ('OFFICIAL_MANUFACTURER', 'OFFICIAL_DEALER', 'GOVERNMENT', 'NEWS', 'REVIEW', 'MARKETPLACE', 'OTHER');

-- CreateEnum
CREATE TYPE "RightsStatus" AS ENUM ('UNKNOWN', 'PUBLIC_DOMAIN', 'LICENSED', 'FAIR_USE', 'RESTRICTED');

-- CreateEnum
CREATE TYPE "DocumentStatus" AS ENUM ('DISCOVERED', 'FETCHED', 'PARSED', 'VERIFIED', 'REJECTED');

-- CreateEnum
CREATE TYPE "PriceType" AS ENUM ('MSRP', 'LIST_PRICE', 'PROMOTION', 'FINANCE', 'LEASE', 'USED_PRICE', 'OTHER');

-- CreateEnum
CREATE TYPE "CandidateStatus" AS ENUM ('PENDING', 'ACCEPTED', 'REJECTED', 'DUPLICATE');

-- CreateEnum
CREATE TYPE "VerificationStatus" AS ENUM ('PENDING', 'VERIFIED', 'FAILED');

-- CreateEnum
CREATE TYPE "ReviewStatus" AS ENUM ('OPEN', 'IN_REVIEW', 'APPROVED', 'REJECTED');

-- CreateEnum
CREATE TYPE "CrawlJobStatus" AS ENUM ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "CrawlEventLevel" AS ENUM ('INFO', 'WARNING', 'ERROR');

-- CreateEnum
CREATE TYPE "MediaType" AS ENUM ('IMAGE', 'VIDEO', 'DOCUMENT', 'OTHER');

-- CreateEnum
CREATE TYPE "ChangeType" AS ENUM ('CREATED', 'UPDATED', 'DELETED', 'CORRECTED');

-- CreateTable
CREATE TABLE "Manufacturer" (
    "id" UUID NOT NULL,
    "nameTh" TEXT NOT NULL,
    "nameEn" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "status" "RecordStatus" NOT NULL DEFAULT 'ACTIVE',
    "websiteUrl" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Manufacturer_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CarModel" (
    "id" UUID NOT NULL,
    "manufacturerId" UUID NOT NULL,
    "nameTh" TEXT NOT NULL,
    "nameEn" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "modelYear" INTEGER,
    "status" "RecordStatus" NOT NULL DEFAULT 'ACTIVE',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CarModel_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Variant" (
    "id" UUID NOT NULL,
    "modelId" UUID NOT NULL,
    "nameTh" TEXT NOT NULL,
    "nameEn" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "modelYear" INTEGER,
    "status" "RecordStatus" NOT NULL DEFAULT 'ACTIVE',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Variant_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Source" (
    "id" UUID NOT NULL,
    "manufacturerId" UUID,
    "nameTh" TEXT NOT NULL,
    "nameEn" TEXT NOT NULL,
    "sourceType" "SourceType" NOT NULL,
    "baseUrl" TEXT NOT NULL,
    "domain" TEXT NOT NULL,
    "authority" DECIMAL(5,4),
    "rightsStatus" "RightsStatus" NOT NULL DEFAULT 'UNKNOWN',
    "status" "RecordStatus" NOT NULL DEFAULT 'ACTIVE',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Source_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SourceDocument" (
    "id" UUID NOT NULL,
    "sourceId" UUID NOT NULL,
    "url" TEXT NOT NULL,
    "canonicalUrl" TEXT,
    "titleTh" TEXT,
    "titleEn" TEXT,
    "mimeType" TEXT,
    "language" TEXT,
    "contentHash" TEXT NOT NULL,
    "fetchedAt" TIMESTAMP(3),
    "publishedAt" TIMESTAMP(3),
    "pageCount" INTEGER,
    "status" "DocumentStatus" NOT NULL DEFAULT 'DISCOVERED',
    "rightsStatus" "RightsStatus" NOT NULL DEFAULT 'UNKNOWN',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SourceDocument_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Price" (
    "id" UUID NOT NULL,
    "variantId" UUID NOT NULL,
    "sourceDocumentId" UUID NOT NULL,
    "priceType" "PriceType" NOT NULL,
    "amount" DECIMAL(15,2) NOT NULL,
    "currency" TEXT NOT NULL DEFAULT 'THB',
    "validFrom" TIMESTAMP(3) NOT NULL,
    "validTo" TIMESTAMP(3),
    "observedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "pageNumber" INTEGER,
    "confidence" DECIMAL(5,4) NOT NULL DEFAULT 0,

    CONSTRAINT "Price_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "VariantSpec" (
    "id" UUID NOT NULL,
    "variantId" UUID NOT NULL,
    "sourceDocumentId" UUID NOT NULL,
    "key" TEXT NOT NULL,
    "valueTh" TEXT,
    "valueEn" TEXT,
    "valueNumeric" DECIMAL(20,6),
    "unit" TEXT,
    "pageNumber" INTEGER,
    "confidence" DECIMAL(5,4) NOT NULL DEFAULT 0,

    CONSTRAINT "VariantSpec_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Feature" (
    "id" UUID NOT NULL,
    "nameTh" TEXT NOT NULL,
    "nameEn" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "category" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Feature_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "VariantFeature" (
    "variantId" UUID NOT NULL,
    "featureId" UUID NOT NULL,
    "sourceDocumentId" UUID,
    "available" BOOLEAN NOT NULL,
    "standard" BOOLEAN NOT NULL DEFAULT false,
    "pageNumber" INTEGER,
    "confidence" DECIMAL(5,4) NOT NULL DEFAULT 0,

    CONSTRAINT "VariantFeature_pkey" PRIMARY KEY ("variantId","featureId")
);

-- CreateTable
CREATE TABLE "Alias" (
    "id" UUID NOT NULL,
    "value" TEXT NOT NULL,
    "language" TEXT NOT NULL,
    "manufacturerId" UUID,
    "modelId" UUID,
    "variantId" UUID,
    "featureId" UUID,

    CONSTRAINT "Alias_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Media" (
    "id" UUID NOT NULL,
    "type" "MediaType" NOT NULL,
    "url" TEXT NOT NULL,
    "contentHash" TEXT,
    "rightsStatus" "RightsStatus" NOT NULL DEFAULT 'UNKNOWN',
    "sourceDocumentId" UUID,
    "modelId" UUID,
    "variantId" UUID,
    "captionTh" TEXT,
    "captionEn" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Media_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ResearchRun" (
    "id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "status" "CrawlJobStatus" NOT NULL DEFAULT 'QUEUED',
    "provider" TEXT,
    "prompt" TEXT,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ResearchRun_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ResearchCandidate" (
    "id" UUID NOT NULL,
    "researchRunId" UUID NOT NULL,
    "variantId" UUID,
    "sourceDocumentId" UUID,
    "fieldName" TEXT NOT NULL,
    "proposedValue" JSONB NOT NULL,
    "evidence" TEXT,
    "pageNumber" INTEGER,
    "confidence" DECIMAL(5,4) NOT NULL DEFAULT 0,
    "status" "CandidateStatus" NOT NULL DEFAULT 'PENDING',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ResearchCandidate_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "BrochureVerification" (
    "id" UUID NOT NULL,
    "sourceDocumentId" UUID NOT NULL,
    "status" "VerificationStatus" NOT NULL DEFAULT 'PENDING',
    "checkedBy" TEXT,
    "notes" TEXT,
    "verifiedAt" TIMESTAMP(3),

    CONSTRAINT "BrochureVerification_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "DataChangeLog" (
    "id" UUID NOT NULL,
    "sourceDocumentId" UUID,
    "researchRunId" UUID,
    "entityType" TEXT NOT NULL,
    "entityId" UUID NOT NULL,
    "fieldName" TEXT,
    "changeType" "ChangeType" NOT NULL,
    "beforeValue" JSONB,
    "afterValue" JSONB,
    "reason" TEXT,
    "confidence" DECIMAL(5,4),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "DataChangeLog_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ReviewItem" (
    "id" UUID NOT NULL,
    "researchRunId" UUID,
    "sourceDocumentId" UUID,
    "entityType" TEXT NOT NULL,
    "entityId" UUID NOT NULL,
    "reason" TEXT NOT NULL,
    "status" "ReviewStatus" NOT NULL DEFAULT 'OPEN',
    "assignedTo" TEXT,
    "resolvedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ReviewItem_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SourceHint" (
    "id" UUID NOT NULL,
    "sourceId" UUID NOT NULL,
    "pattern" TEXT NOT NULL,
    "description" TEXT,
    "priority" INTEGER NOT NULL DEFAULT 0,
    "enabled" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SourceHint_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CrawlJob" (
    "id" UUID NOT NULL,
    "sourceId" UUID NOT NULL,
    "status" "CrawlJobStatus" NOT NULL DEFAULT 'QUEUED',
    "requestedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "startedAt" TIMESTAMP(3),
    "finishedAt" TIMESTAMP(3),
    "error" TEXT,

    CONSTRAINT "CrawlJob_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CrawlEvent" (
    "id" UUID NOT NULL,
    "crawlJobId" UUID NOT NULL,
    "sourceDocumentId" UUID,
    "level" "CrawlEventLevel" NOT NULL DEFAULT 'INFO',
    "message" TEXT NOT NULL,
    "metadata" JSONB,
    "occurredAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CrawlEvent_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Embedding" (
    "id" UUID NOT NULL,
    "sourceDocumentId" UUID NOT NULL,
    "chunkIndex" INTEGER NOT NULL,
    "content" TEXT NOT NULL,
    "contentHash" TEXT NOT NULL,
    "model" TEXT NOT NULL,
    "dimensions" INTEGER NOT NULL DEFAULT 1536,
    "vector" vector(1536),
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Embedding_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Manufacturer_slug_key" ON "Manufacturer"("slug");

-- CreateIndex
CREATE INDEX "Manufacturer_nameTh_idx" ON "Manufacturer"("nameTh");

-- CreateIndex
CREATE INDEX "Manufacturer_nameEn_idx" ON "Manufacturer"("nameEn");

-- CreateIndex
CREATE INDEX "CarModel_nameTh_idx" ON "CarModel"("nameTh");

-- CreateIndex
CREATE INDEX "CarModel_nameEn_idx" ON "CarModel"("nameEn");

-- CreateIndex
CREATE UNIQUE INDEX "CarModel_manufacturerId_slug_modelYear_key" ON "CarModel"("manufacturerId", "slug", "modelYear");

-- CreateIndex
CREATE INDEX "Variant_nameTh_idx" ON "Variant"("nameTh");

-- CreateIndex
CREATE INDEX "Variant_nameEn_idx" ON "Variant"("nameEn");

-- CreateIndex
CREATE UNIQUE INDEX "Variant_modelId_slug_modelYear_key" ON "Variant"("modelId", "slug", "modelYear");

-- CreateIndex
CREATE INDEX "Source_sourceType_status_idx" ON "Source"("sourceType", "status");

-- CreateIndex
CREATE UNIQUE INDEX "Source_baseUrl_key" ON "Source"("baseUrl");

-- CreateIndex
CREATE INDEX "SourceDocument_canonicalUrl_idx" ON "SourceDocument"("canonicalUrl");

-- CreateIndex
CREATE INDEX "SourceDocument_status_fetchedAt_idx" ON "SourceDocument"("status", "fetchedAt");

-- CreateIndex
CREATE UNIQUE INDEX "SourceDocument_sourceId_contentHash_key" ON "SourceDocument"("sourceId", "contentHash");

-- CreateIndex
CREATE INDEX "Price_variantId_priceType_validFrom_idx" ON "Price"("variantId", "priceType", "validFrom");

-- CreateIndex
CREATE INDEX "Price_sourceDocumentId_pageNumber_idx" ON "Price"("sourceDocumentId", "pageNumber");

-- CreateIndex
CREATE UNIQUE INDEX "Price_variantId_sourceDocumentId_priceType_amount_validFrom_key" ON "Price"("variantId", "sourceDocumentId", "priceType", "amount", "validFrom");

-- CreateIndex
CREATE INDEX "VariantSpec_key_idx" ON "VariantSpec"("key");

-- CreateIndex
CREATE UNIQUE INDEX "VariantSpec_variantId_key_sourceDocumentId_key" ON "VariantSpec"("variantId", "key", "sourceDocumentId");

-- CreateIndex
CREATE UNIQUE INDEX "Feature_slug_key" ON "Feature"("slug");

-- CreateIndex
CREATE INDEX "Alias_value_idx" ON "Alias"("value");

-- CreateIndex
CREATE UNIQUE INDEX "Alias_value_language_key" ON "Alias"("value", "language");

-- CreateIndex
CREATE INDEX "Media_modelId_variantId_idx" ON "Media"("modelId", "variantId");

-- CreateIndex
CREATE INDEX "ResearchCandidate_researchRunId_status_idx" ON "ResearchCandidate"("researchRunId", "status");

-- CreateIndex
CREATE UNIQUE INDEX "BrochureVerification_sourceDocumentId_key" ON "BrochureVerification"("sourceDocumentId");

-- CreateIndex
CREATE INDEX "DataChangeLog_entityType_entityId_createdAt_idx" ON "DataChangeLog"("entityType", "entityId", "createdAt");

-- CreateIndex
CREATE INDEX "ReviewItem_status_createdAt_idx" ON "ReviewItem"("status", "createdAt");

-- CreateIndex
CREATE INDEX "SourceHint_sourceId_enabled_priority_idx" ON "SourceHint"("sourceId", "enabled", "priority");

-- CreateIndex
CREATE INDEX "CrawlJob_status_requestedAt_idx" ON "CrawlJob"("status", "requestedAt");

-- CreateIndex
CREATE INDEX "CrawlEvent_crawlJobId_occurredAt_idx" ON "CrawlEvent"("crawlJobId", "occurredAt");

-- CreateIndex
CREATE INDEX "Embedding_sourceDocumentId_idx" ON "Embedding"("sourceDocumentId");

-- CreateIndex
CREATE UNIQUE INDEX "Embedding_sourceDocumentId_chunkIndex_model_key" ON "Embedding"("sourceDocumentId", "chunkIndex", "model");

-- AddForeignKey
ALTER TABLE "CarModel" ADD CONSTRAINT "CarModel_manufacturerId_fkey" FOREIGN KEY ("manufacturerId") REFERENCES "Manufacturer"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Variant" ADD CONSTRAINT "Variant_modelId_fkey" FOREIGN KEY ("modelId") REFERENCES "CarModel"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Source" ADD CONSTRAINT "Source_manufacturerId_fkey" FOREIGN KEY ("manufacturerId") REFERENCES "Manufacturer"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SourceDocument" ADD CONSTRAINT "SourceDocument_sourceId_fkey" FOREIGN KEY ("sourceId") REFERENCES "Source"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Price" ADD CONSTRAINT "Price_variantId_fkey" FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Price" ADD CONSTRAINT "Price_sourceDocumentId_fkey" FOREIGN KEY ("sourceDocumentId") REFERENCES "SourceDocument"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "VariantSpec" ADD CONSTRAINT "VariantSpec_variantId_fkey" FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "VariantSpec" ADD CONSTRAINT "VariantSpec_sourceDocumentId_fkey" FOREIGN KEY ("sourceDocumentId") REFERENCES "SourceDocument"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "VariantFeature" ADD CONSTRAINT "VariantFeature_variantId_fkey" FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "VariantFeature" ADD CONSTRAINT "VariantFeature_featureId_fkey" FOREIGN KEY ("featureId") REFERENCES "Feature"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "VariantFeature" ADD CONSTRAINT "VariantFeature_sourceDocumentId_fkey" FOREIGN KEY ("sourceDocumentId") REFERENCES "SourceDocument"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Alias" ADD CONSTRAINT "Alias_manufacturerId_fkey" FOREIGN KEY ("manufacturerId") REFERENCES "Manufacturer"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Alias" ADD CONSTRAINT "Alias_modelId_fkey" FOREIGN KEY ("modelId") REFERENCES "CarModel"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Alias" ADD CONSTRAINT "Alias_variantId_fkey" FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Alias" ADD CONSTRAINT "Alias_featureId_fkey" FOREIGN KEY ("featureId") REFERENCES "Feature"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Media" ADD CONSTRAINT "Media_sourceDocumentId_fkey" FOREIGN KEY ("sourceDocumentId") REFERENCES "SourceDocument"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Media" ADD CONSTRAINT "Media_modelId_fkey" FOREIGN KEY ("modelId") REFERENCES "CarModel"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Media" ADD CONSTRAINT "Media_variantId_fkey" FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ResearchCandidate" ADD CONSTRAINT "ResearchCandidate_researchRunId_fkey" FOREIGN KEY ("researchRunId") REFERENCES "ResearchRun"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ResearchCandidate" ADD CONSTRAINT "ResearchCandidate_variantId_fkey" FOREIGN KEY ("variantId") REFERENCES "Variant"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ResearchCandidate" ADD CONSTRAINT "ResearchCandidate_sourceDocumentId_fkey" FOREIGN KEY ("sourceDocumentId") REFERENCES "SourceDocument"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "BrochureVerification" ADD CONSTRAINT "BrochureVerification_sourceDocumentId_fkey" FOREIGN KEY ("sourceDocumentId") REFERENCES "SourceDocument"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "DataChangeLog" ADD CONSTRAINT "DataChangeLog_sourceDocumentId_fkey" FOREIGN KEY ("sourceDocumentId") REFERENCES "SourceDocument"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "DataChangeLog" ADD CONSTRAINT "DataChangeLog_researchRunId_fkey" FOREIGN KEY ("researchRunId") REFERENCES "ResearchRun"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ReviewItem" ADD CONSTRAINT "ReviewItem_researchRunId_fkey" FOREIGN KEY ("researchRunId") REFERENCES "ResearchRun"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ReviewItem" ADD CONSTRAINT "ReviewItem_sourceDocumentId_fkey" FOREIGN KEY ("sourceDocumentId") REFERENCES "SourceDocument"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SourceHint" ADD CONSTRAINT "SourceHint_sourceId_fkey" FOREIGN KEY ("sourceId") REFERENCES "Source"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CrawlJob" ADD CONSTRAINT "CrawlJob_sourceId_fkey" FOREIGN KEY ("sourceId") REFERENCES "Source"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CrawlEvent" ADD CONSTRAINT "CrawlEvent_crawlJobId_fkey" FOREIGN KEY ("crawlJobId") REFERENCES "CrawlJob"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CrawlEvent" ADD CONSTRAINT "CrawlEvent_sourceDocumentId_fkey" FOREIGN KEY ("sourceDocumentId") REFERENCES "SourceDocument"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Embedding" ADD CONSTRAINT "Embedding_sourceDocumentId_fkey" FOREIGN KEY ("sourceDocumentId") REFERENCES "SourceDocument"("id") ON DELETE CASCADE ON UPDATE CASCADE;
