import { describe, expect, it, vi } from "vitest";
import { searchVectorEvidence } from "../../lib/search/vector-search";
import { searchHybrid } from "../../lib/search/hybrid-search";
import type { LocalEmbeddingClient } from "../../lib/embeddings/local-service";

const embedding = (values: number[] = [1, 0]) => ({
  provider: "local" as const,
  model: "test",
  dimensions: 1024,
  embed: vi.fn(async () => [Array.from({ length: 1024 }, (_, i) => values[i] ?? 0)]),
}) satisfies LocalEmbeddingClient;

const evidence = { id: "e1", sourceDocumentId: "d1", entityType: "SourceDocument", entityId: "d1", chunkIndex: 0, chunkType: "document", pageNumber: 2, content: "Camry official evidence", distance: 0.1, source: { id: "s1", url: "https://example.test/camry", titleTh: "คัมรี่", titleEn: "Camry", sourceType: "OFFICIAL_MANUFACTURER" } };

describe("vector retrieval", () => {
  it("uses a parameterized cosine-distance query and bounded rows", async () => {
    const query = vi.fn(async () => [evidence]);
    const result = await searchVectorEvidence("Camry", { embeddingClient: embedding(), queryRaw: query, limit: 5 });
    expect(result.available).toBe(true);
    expect(result.evidence).toEqual([evidence]);
    expect(query).toHaveBeenCalledOnce();
    const sql = (query.mock.calls as unknown[][])[0]?.[0] as { sql: string; values: unknown[] };
    expect(sql.sql).toContain("<=>");
    expect(sql.sql).toContain("LIMIT");
    expect(sql.values.some((value) => String(value).includes("["))).toBe(true);
    expect(sql.values).not.toContain("Camry");
  });

  it("does not make a network or database call by default when the endpoint is unset", async () => {
    vi.stubEnv("EMBEDDING_BASE_URL", "");
    const queryRaw = vi.fn();
    await expect(searchVectorEvidence("Camry", { queryRaw })).resolves.toEqual({ available: false, evidence: [] });
    expect(queryRaw).not.toHaveBeenCalled();
  });

  it("fails closed when the embedding client dimension is not 1024", async () => {
    const bad = { ...embedding(), dimensions: 767 };
    await expect(searchVectorEvidence("Camry", { embeddingClient: bad, queryRaw: vi.fn() })).rejects.toMatchObject({ code: "dimension_mismatch" });
  });
});

describe("hybrid retrieval", () => {
  it("reports hybrid mode only after vector retrieval succeeds", async () => {
    const catalog = { results: [{ id: "v1" }], total: 1, page: 1, limit: 10, hasMore: false };
    const result = await searchHybrid({ q: "Camry", limit: 10, page: 1 }, {
      searchCatalog: vi.fn(async () => catalog as never),
      vectorSearch: vi.fn(async () => ({ available: true, evidence: [evidence] })),
    });
    expect(result.searchMode).toBe("hybrid");
    expect(result.vectorAvailable).toBe(true);
    expect(result.evidence).toEqual([evidence]);
  });

  it("falls back without calling vectors when no query is present or no endpoint is configured", async () => {
    const vectorSearch = vi.fn();
    const searchCatalog = vi.fn(async () => ({ results: [], total: 0, page: 1, limit: 10, hasMore: false }));
    await expect(searchHybrid({ limit: 10, page: 1 }, { searchCatalog, vectorSearch })).resolves.toMatchObject({ searchMode: "structured-fallback", vectorAvailable: false, evidence: [] });
    expect(vectorSearch).not.toHaveBeenCalled();
  });

  it("does not claim vector mode when the provider is unavailable", async () => {
    const result = await searchHybrid({ q: "Camry", limit: 10, page: 1 }, {
      searchCatalog: vi.fn(async () => ({ results: [], total: 0, page: 1, limit: 10, hasMore: false })),
      vectorSearch: vi.fn(async () => { throw new Error("embedding offline"); }),
    });
    expect(result).toMatchObject({ searchMode: "structured-fallback", vectorAvailable: false, evidence: [] });
  });
});
