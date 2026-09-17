-- Align the local /embed service (768 dimensions) without resetting the database.
-- This migration is intentionally fail-closed: vectors must be empty before changing type.
DO $$
BEGIN
  IF (SELECT COUNT(*) FROM "Embedding") <> 0 THEN
    RAISE EXCEPTION 'Refusing vector dimension migration: Embedding is not empty';
  END IF;
END $$;

DROP INDEX IF EXISTS "Embedding_vector_hnsw_idx";
ALTER TABLE "Embedding" ALTER COLUMN "vector" TYPE vector(768);
ALTER TABLE "Embedding" ALTER COLUMN "dimensions" SET DEFAULT 768;
CREATE INDEX "Embedding_vector_hnsw_idx" ON "Embedding" USING hnsw ("vector" vector_cosine_ops)
  WITH (m = 16, ef_construction = 64) WHERE "vector" IS NOT NULL;
