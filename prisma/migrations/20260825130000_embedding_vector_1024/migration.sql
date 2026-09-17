-- Align Embedding vector dimension with the configured external embedding provider (1024).
-- Pre-check: Embedding has only 1 row from local 768d testing; re-index after migration.
DELETE FROM "Embedding";
DROP INDEX IF EXISTS "Embedding_vector_hnsw_idx";
ALTER TABLE "Embedding" ALTER COLUMN "vector" SET DATA TYPE vector(1024);
CREATE INDEX "Embedding_vector_hnsw_idx" ON "Embedding" USING hnsw ("vector" vector_cosine_ops) WITH (m = 16, ef_construction = 64) WHERE "vector" IS NOT NULL;
