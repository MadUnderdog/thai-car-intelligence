import { afterEach, describe, expect, it, vi } from "vitest";
import { createLocalEmbeddingClient, getLocalEmbeddingClient, LOCAL_EMBEDDING_DIMENSIONS } from "../../lib/embeddings/local-service";

const vector = () => Array.from({ length: LOCAL_EMBEDDING_DIMENSIONS }, (_, index) => index / LOCAL_EMBEDDING_DIMENSIONS);
afterEach(() => vi.unstubAllGlobals());

describe("local embedding service", () => {
  it("batches texts and validates the real 1024d response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ embeddings: [vector(), vector()], dimensions: 1024 }), { status: 200 }));
    const client = createLocalEmbeddingClient({ baseUrl: "http://localhost:8080/", fetchImpl: fetchMock });
    await expect(client.embed(["one", "two"])).resolves.toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8080/embed", expect.objectContaining({ body: JSON.stringify({ texts: ["one", "two"] }) }));
  });

  it("rejects a dimension mismatch and does not assume a network endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ embeddings: [[1, 2]], dimensions: 2 }), { status: 200 }));
    await expect(createLocalEmbeddingClient({ baseUrl: "http://localhost:8080", fetchImpl: fetchMock }).embed(["x"])).rejects.toMatchObject({ code: "dimension_mismatch" });
    expect(getLocalEmbeddingClient({} as NodeJS.ProcessEnv)).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
