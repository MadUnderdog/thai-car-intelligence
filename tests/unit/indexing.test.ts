import { createHash } from "node:crypto";
import { describe, expect, it, vi } from "vitest";
import { createLocalEmbeddingClient } from "../../lib/embeddings/local-service";
import { indexDocument } from "../../workers/indexing/embed-document";

const id = "00000000-0000-0000-0000-000000000001";
const embedding = { provider: "local" as const, model: "bge-test", dimensions: 1024, embed: vi.fn(async (texts: string[]) => texts.map(() => Array(1024).fill(0.1))) };
function store(rows: Array<{ id: string; chunkIndex: number; contentHash: string; model: string; dimensions: number }>) {
  return { embedding: { findMany: vi.fn(async () => rows) }, $executeRaw: vi.fn(async () => 1) };
}

describe("incremental document indexing", () => {
  it("sends changed chunks in batches and persists parameterized SQL", async () => {
    const db = store([]);
    const result = await indexDocument({ sourceDocumentId: id, extractedText: "page one\fpage two", chunkOptions: { maxCharacters: 100 }, batchSize: 2 }, { store: db, embeddings: embedding });
    expect(result).toMatchObject({ chunks: 2, unchanged: 0, embedded: 2 });
    expect(embedding.embed).toHaveBeenCalledWith(["page one", "page two"]);
    expect(db.$executeRaw).toHaveBeenCalledTimes(2);
  });

  it("does not call the service for unchanged chunks", async () => {
    const first = store([]);
    await indexDocument({ sourceDocumentId: id, extractedText: "same" }, { store: first, embeddings: embedding });
    embedding.embed.mockClear();
    const sameHash = createHash("sha256").update("same").digest("hex");
        const second = store([{ id: "row", chunkIndex: 0, contentHash: sameHash, model: "bge-test", dimensions: 1024 }]);
        const dry = await indexDocument({ sourceDocumentId: id, extractedText: "same", dryRun: true }, { store: second, embeddings: embedding });
        expect(dry).toMatchObject({ dryRun: true, unchanged: 1, embedded: 0 });
    expect(embedding.embed).not.toHaveBeenCalled();
  });

  it("local response rejects non-1024 vectors", async () => {
    const client = createLocalEmbeddingClient({ baseUrl: "http://example.test", fetchImpl: vi.fn(async () => new Response(JSON.stringify({ embeddings: [[1]], dimensions: 1 }), { status: 200 })) });
    await expect(client.embed(["x"])).rejects.toMatchObject({ code: "dimension_mismatch" });
  });
});
