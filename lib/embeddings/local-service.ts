export const LOCAL_EMBEDDING_DIMENSIONS = 1024;

export type LocalEmbeddingClient = {
  readonly provider: "local";
  readonly model: string;
  readonly dimensions: number;
  embed(texts: string[]): Promise<number[][]>;
};

export type LocalEmbeddingOptions = {
  baseUrl: string;
  model?: string;
  timeoutMs?: number;
  expectedDimensions?: number;
  fetchImpl?: typeof fetch;
};

export class LocalEmbeddingError extends Error {
  constructor(readonly code: "misconfigured" | "timeout" | "provider_error" | "malformed_response" | "dimension_mismatch", message: string) {
    super(message);
    this.name = "LocalEmbeddingError";
  }
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function createLocalEmbeddingClient(options: LocalEmbeddingOptions): LocalEmbeddingClient {
  const baseUrl = options.baseUrl.trim().replace(/\/+$/, "");
  const timeoutMs = options.timeoutMs ?? 15_000;
  const expected = options.expectedDimensions ?? LOCAL_EMBEDDING_DIMENSIONS;
  if (!baseUrl) throw new LocalEmbeddingError("misconfigured", "EMBEDDING_BASE_URL is required");
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 120_000) {
    throw new LocalEmbeddingError("misconfigured", "timeoutMs must be between 1 and 120000");
  }
  if (!Number.isInteger(expected) || expected < 1) throw new LocalEmbeddingError("misconfigured", "expectedDimensions must be positive");
  const fetchImpl = options.fetchImpl ?? fetch;
  const model = options.model?.trim() || "local-bge-base";

  return {
    provider: "local",
    model,
    dimensions: expected,
    async embed(texts) {
      if (texts.length === 0) return [];
      if (texts.some((text) => typeof text !== "string" || !text.trim())) throw new LocalEmbeddingError("malformed_response", "Embedding input texts must be non-empty strings");
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      let response: Response;
      try {
        try {
          response = await fetchImpl(`${baseUrl}/embed`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ texts }),
            signal: controller.signal,
          });
        } catch (error) {
          if (controller.signal.aborted || (error instanceof Error && error.name === "AbortError")) throw new LocalEmbeddingError("timeout", "Local embedding request timed out");
          throw new LocalEmbeddingError("provider_error", "Local embedding request failed");
        }
        if (!response.ok) throw new LocalEmbeddingError("provider_error", `Local embedding service returned HTTP ${response.status}`);
        let json: unknown;
        try { json = await response.json(); } catch { throw new LocalEmbeddingError("malformed_response", "Local embedding service returned invalid JSON"); }
        const embeddings = record(json) ? json.embeddings : undefined;
        const dimensions = record(json) ? json.dimensions : undefined;
        if (!Array.isArray(embeddings) || embeddings.length !== texts.length) {
          throw new LocalEmbeddingError("malformed_response", "Local embedding response must contain one embeddings array per input");
        }
        if (dimensions !== expected) {
          throw new LocalEmbeddingError("dimension_mismatch", `Local embedding service reported dimension ${String(dimensions)}, expected ${expected}`);
        }
        for (const embedding of embeddings) {
          if (!Array.isArray(embedding) || embedding.length !== expected || embedding.some((value) => typeof value !== "number" || !Number.isFinite(value))) {
            throw new LocalEmbeddingError("dimension_mismatch", `Local embedding must contain finite vectors of dimension ${expected}`);
          }
        }
        return embeddings as number[][];
      } finally { clearTimeout(timer); }
    },
  };
}

/** Returns null unless EMBEDDING_BASE_URL is explicitly configured; never assumes localhost. */
export function getLocalEmbeddingClient(env: NodeJS.ProcessEnv = process.env, fetchImpl?: typeof fetch): LocalEmbeddingClient | null {
  const baseUrl = env.EMBEDDING_BASE_URL?.trim();
  if (!baseUrl) return null;
  const dimensions = Number(env.EMBEDDING_DIMENSIONS?.trim() || String(LOCAL_EMBEDDING_DIMENSIONS));
  if (!Number.isInteger(dimensions) || dimensions < 1) throw new LocalEmbeddingError("misconfigured", "EMBEDDING_DIMENSIONS must be a positive integer");
  return createLocalEmbeddingClient({ baseUrl, model: env.EMBEDDING_MODEL, expectedDimensions: dimensions, fetchImpl });
}
