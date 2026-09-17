-- Alter the sourceDocumentId column from text to uuid
-- This fixes the Prisma type mismatch that caused "operator does not exist: uuid = text"

-- First, drop the foreign key constraint if it exists
ALTER TABLE "Price" DROP CONSTRAINT IF EXISTS "Price_sourceDocumentId_fkey";

-- Change the column type from text to uuid
ALTER TABLE "Price" ALTER COLUMN "sourceDocumentId" TYPE uuid USING "sourceDocumentId"::uuid;

-- Re-add the foreign key constraint
ALTER TABLE "Price" ADD CONSTRAINT "Price_sourceDocumentId_fkey" FOREIGN KEY ("sourceDocumentId") REFERENCES "SourceDocument"("id") ON DELETE SET NULL;
