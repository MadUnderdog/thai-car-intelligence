import { Prisma } from "@prisma/client";
import { randomUUID } from "node:crypto";
import { chunkExtractedText } from "./chunker";
import type { LocalEmbeddingClient } from "../../lib/embeddings/local-service";

export type ExistingEmbedding = { id: string; chunkIndex: number; contentHash: string; model: string; dimensions: number };
export type IndexingStore = {
  embedding: { findMany(args: unknown): Promise<ExistingEmbedding[]> };
  $executeRaw(query: ReturnType<typeof Prisma.sql>): Promise<number>;
};

export type IndexDocumentOptions = {
  sourceDocumentId: string;
  extractedText: string;
  entityType?: string;
  entityId?: string;
  chunkOptions?: { maxCharacters?: number };
  batchSize?: number;
  dryRun?: boolean;
};

export type IndexDocumentResult = {
  sourceDocumentId: string;
  chunks: number;
  unchanged: number;
  embedded: number;
  deleted: number;
  dryRun: boolean;
};

function vectorLiteral(values: number[]): string { return JSON.stringify(values); }

/** Indexes only changed chunks. Existing rows are updated by id; stale chunks are removed after success. */
export async function indexDocument(options: IndexDocumentOptions, deps: { store: IndexingStore; embeddings: LocalEmbeddingClient }): Promise<IndexDocumentResult> {
  const { sourceDocumentId } = options;
  if (!/^[0-9a-f-]{36}$/i.test(sourceDocumentId)) throw new Error("sourceDocumentId must be a UUID");
  const chunks = chunkExtractedText(options.extractedText, options.chunkOptions);
  const model = deps.embeddings.model;
  const existing = await deps.store.embedding.findMany({ where: { sourceDocumentId, model }, select: { id: true, chunkIndex: true, contentHash: true, model: true, dimensions: true } });
  const byIndex = new Map(existing.map((row) => [row.chunkIndex, row]));
  const changed = chunks.filter((chunk) => byIndex.get(chunk.index)?.contentHash !== chunk.contentHash);
  const unchanged = chunks.length - changed.length;
  if (options.dryRun) return { sourceDocumentId, chunks: chunks.length, unchanged, embedded: changed.length, deleted: existing.filter((row) => !chunks.some((chunk) => chunk.index === row.chunkIndex)).length, dryRun: true };

  const batchSize = options.batchSize ?? 32;
  if (!Number.isInteger(batchSize) || batchSize < 1) throw new Error("batchSize must be a positive integer");
  let embedded = 0;
  for (let offset = 0; offset < changed.length; offset += batchSize) {
    const batch = changed.slice(offset, offset + batchSize);
    const vectors = await deps.embeddings.embed(batch.map((chunk) => chunk.text));
    if (vectors.length !== batch.length) throw new Error("Embedding service returned an unexpected batch size");
    for (let i = 0; i < batch.length; i += 1) {
      const chunk = batch[i];
      const vector = vectors[i];
      const prior = byIndex.get(chunk.index);
      const metadata = { provider: deps.embeddings.provider, dimensions: deps.embeddings.dimensions };
      if (prior) {
        await deps.store.$executeRaw(Prisma.sql`UPDATE "Embedding" SET "content" = ${chunk.text}, "contentHash" = ${chunk.contentHash}, "vector" = ${vectorLiteral(vector)}::vector, "dimensions" = ${deps.embeddings.dimensions}, "entityType" = ${options.entityType ?? "SourceDocument"}, "entityId" = ${options.entityId ?? sourceDocumentId}, "chunkType" = ${chunk.chunkType}, "pageNumber" = ${chunk.pageNumber ?? null}, "metadata" = ${JSON.stringify(metadata)}::jsonb WHERE "id" = ${prior.id}`);
      } else {
        await deps.store.$executeRaw(Prisma.sql`INSERT INTO "Embedding" ("id", "sourceDocumentId", "entityType", "entityId", "chunkIndex", "chunkType", "pageNumber", "content", "contentHash", "model", "dimensions", "vector", "metadata") VALUES (${randomUUID()}, ${sourceDocumentId}, ${options.entityType ?? "SourceDocument"}, ${options.entityId ?? sourceDocumentId}, ${chunk.index}, ${chunk.chunkType}, ${chunk.pageNumber ?? null}, ${chunk.text}, ${chunk.contentHash}, ${model}, ${deps.embeddings.dimensions}, ${vectorLiteral(vector)}::vector, ${JSON.stringify(metadata)}::jsonb)`);
      }
      embedded += 1;
    }
  }
  const stale = existing.filter((row) => !chunks.some((chunk) => chunk.index === row.chunkIndex));
  for (const row of stale) await deps.store.$executeRaw(Prisma.sql`DELETE FROM "Embedding" WHERE "id" = ${row.id}`);
  return { sourceDocumentId, chunks: chunks.length, unchanged, embedded, deleted: stale.length, dryRun: false };
}

export type SourceDocumentStore = { sourceDocument: { findUnique(args: unknown): Promise<{ extractedText: string | null } | null> } };
export async function indexSourceDocument(sourceDocumentId: string, deps: { db: SourceDocumentStore & IndexingStore; embeddings: LocalEmbeddingClient }, options: Omit<IndexDocumentOptions, "sourceDocumentId" | "extractedText"> = {}): Promise<IndexDocumentResult> {
  const document = await deps.db.sourceDocument.findUnique({ where: { id: sourceDocumentId }, select: { extractedText: true } });
  if (!document) throw new Error("Source document not found");
  if (!document.extractedText?.trim()) throw new Error("Source document has no extractedText");
  return indexDocument({ ...options, sourceDocumentId, extractedText: document.extractedText }, { store: deps.db, embeddings: deps.embeddings });
}
