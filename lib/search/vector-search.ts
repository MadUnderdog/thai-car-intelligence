import { Prisma } from "@prisma/client";
import db from "../db";
import { getLocalEmbeddingClient, LocalEmbeddingError, type LocalEmbeddingClient } from "../embeddings/local-service";

export const VECTOR_DIMENSIONS = Number(process.env.EMBEDDING_DIMENSIONS || "1024");
export const DEFAULT_VECTOR_LIMIT = 8;
export const MAX_VECTOR_LIMIT = 20;

export type VectorEvidence = {
  id: string;
  sourceDocumentId: string;
  entityType: string;
  entityId: string;
  chunkIndex: number;
  chunkType: string;
  pageNumber: number | null;
  content: string;
  distance: number;
  source: {
    id: string;
    url: string;
    titleTh: string | null;
    titleEn: string | null;
    sourceType: string;
  };
};

export type VectorSearchResult = { available: boolean; evidence: VectorEvidence[] };
type QueryRaw = (query: Prisma.Sql) => Promise<unknown>;

type VectorSearchOptions = {
  embeddingClient?: LocalEmbeddingClient | null;
  queryRaw?: QueryRaw;
  limit?: number;
};

function boundedLimit(limit: number | undefined): number {
  return Math.min(MAX_VECTOR_LIMIT, Math.max(1, Math.floor(limit ?? DEFAULT_VECTOR_LIMIT)));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function mapEvidence(row: unknown): VectorEvidence {
  if (!isRecord(row) || typeof row.id !== "string" || typeof row.sourceDocumentId !== "string" || typeof row.content !== "string" || !isRecord(row.source)) {
    throw new Error("Malformed vector evidence row");
  }
  const source = row.source;
  if (typeof source.id !== "string" || typeof source.url !== "string" || typeof source.sourceType !== "string") throw new Error("Malformed vector source metadata");
  return {
    id: row.id,
    sourceDocumentId: row.sourceDocumentId,
    entityType: String(row.entityType),
    entityId: String(row.entityId),
    chunkIndex: Number(row.chunkIndex),
    chunkType: String(row.chunkType),
    pageNumber: row.pageNumber == null ? null : Number(row.pageNumber),
    content: row.content,
    distance: Number(row.distance),
    source: { id: source.id, url: source.url, titleTh: typeof source.titleTh === "string" ? source.titleTh : null, titleEn: typeof source.titleEn === "string" ? source.titleEn : null, sourceType: source.sourceType },
  };
}

/** Retrieves verified document chunks. It is deliberately inert unless EMBEDDING_BASE_URL is configured. */
export async function searchVectorEvidence(query: string, options: VectorSearchOptions = {}): Promise<VectorSearchResult> {
  const text = query.trim();
  if (!text) return { available: false, evidence: [] };
  const embeddingClient = options.embeddingClient === undefined ? getLocalEmbeddingClient() : options.embeddingClient;
  if (!embeddingClient) return { available: false, evidence: [] };
  if (embeddingClient.dimensions !== VECTOR_DIMENSIONS) throw new LocalEmbeddingError("dimension_mismatch", `Vector retrieval requires ${VECTOR_DIMENSIONS} dimensions`);
  const [vector] = await embeddingClient.embed([text]);
  if (!vector || vector.length !== VECTOR_DIMENSIONS) throw new LocalEmbeddingError("dimension_mismatch", `Query embedding must have ${VECTOR_DIMENSIONS} dimensions`);
  const queryRaw = options.queryRaw ?? ((sql: Prisma.Sql) => db.$queryRaw(sql));
  const rows = await queryRaw(Prisma.sql`
    SELECT e."id", e."sourceDocumentId", e."entityType", e."entityId", e."chunkIndex", e."chunkType", e."pageNumber", e."content",
           e."vector" <=> ${JSON.stringify(vector)}::vector AS "distance",
           json_build_object('id', sd."id", 'url', COALESCE(sd."canonicalUrl", sd."url"), 'titleTh', sd."titleTh", 'titleEn', sd."titleEn", 'sourceType', s."sourceType") AS "source"
    FROM "Embedding" e
    JOIN "SourceDocument" sd ON sd."id" = e."sourceDocumentId"
    JOIN "Source" s ON s."id" = sd."sourceId"
    WHERE e."vector" IS NOT NULL AND e."dimensions" = ${VECTOR_DIMENSIONS}
      AND sd."status" = 'VERIFIED' AND s."status" = 'ACTIVE'
      AND EXISTS (SELECT 1 FROM "BrochureVerification" v WHERE v."sourceDocumentId" = sd."id" AND v."status" = 'VERIFIED')
    ORDER BY e."vector" <=> ${JSON.stringify(vector)}::vector ASC
    LIMIT ${boundedLimit(options.limit)}
  `);
  if (!Array.isArray(rows)) throw new Error("Malformed vector retrieval response");
  return { available: true, evidence: rows.map(mapEvidence) };
}
