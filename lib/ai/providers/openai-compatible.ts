import type { AIProvider, ChatInput, ChatOutput, EmbeddingOutput } from "../types";

export type OpenAICompatibleConfig = {
  baseUrl: string;
  apiKey: string;
  model: string;
  embeddingBaseUrl?: string;
  embeddingApiKey?: string;
  embeddingModel?: string;
  embeddingDimensions?: number;
  timeoutMs?: number;
};

export type AIProviderErrorCode = "misconfigured" | "provider_error" | "malformed_response" | "timeout" | "dimension_mismatch";

type ChatResponse = { choices?: Array<{ message?: { content?: unknown } }> };
type EmbeddingResponse = { data?: Array<{ embedding?: unknown }> };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export class AIProviderError extends Error {
  constructor(readonly code: AIProviderErrorCode, message: string) {
    super(message);
    this.name = "AIProviderError";
  }
}

function required(value: string | undefined, field: string): string {
  if (!value?.trim()) throw new AIProviderError("misconfigured", `${field} is required`);
  return value.trim();
}

function endpoint(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/+$/, "")}/${path}`;
}

function providerMessage(status: number): string {
  return `AI provider request failed with HTTP ${status}`;
}

export class OpenAICompatibleProvider implements AIProvider {
  readonly name = "openai-compatible";
  private readonly timeoutMs: number;

  constructor(private readonly config: OpenAICompatibleConfig) {
    this.timeoutMs = config.timeoutMs ?? 15_000;
    if (!Number.isInteger(this.timeoutMs) || this.timeoutMs < 1 || this.timeoutMs > 120_000) {
      throw new AIProviderError("misconfigured", "timeoutMs must be between 1 and 120000");
    }
  }

  async chat(input: ChatInput): Promise<ChatOutput> {
    const baseUrl = required(this.config.baseUrl, "AI_BASE_URL");
    const apiKey = required(this.config.apiKey, "AI_API_KEY");
    const model = required(this.config.model, "AI_MODEL");
    const evidence = input.evidence.map((item) => `[${item.id}] ${item.content}`).join("\n");
    const body = {
      model,
      messages: [
        { role: "system", content: "Answer only from the supplied evidence. If evidence is insufficient, say so. Do not invent citations." },
        { role: "user", content: `Question: ${input.question}\nEvidence:\n${evidence}` },
      ],
    };
    const json = await this.request(endpoint(baseUrl, "chat/completions"), apiKey, body);
    if (!isRecord(json)) throw new AIProviderError("malformed_response", "AI provider returned an invalid chat response");
    const content = (json as ChatResponse).choices?.[0]?.message?.content;
    if (typeof content !== "string" || !content.trim()) throw new AIProviderError("malformed_response", "AI provider returned no chat content");
    return { answer: content.trim(), citations: [], status: "ok" };
  }

  async embed(text: string): Promise<EmbeddingOutput> {
    const baseUrl = required(this.config.embeddingBaseUrl, "EMBEDDING_BASE_URL");
    const apiKey = required(this.config.embeddingApiKey, "EMBEDDING_API_KEY");
    const model = required(this.config.embeddingModel, "EMBEDDING_MODEL");
    const json = await this.request(endpoint(baseUrl, "embeddings"), apiKey, { model, input: text });
    if (!isRecord(json)) throw new AIProviderError("malformed_response", "AI provider returned an invalid embedding response");
    const embedding = (json as EmbeddingResponse).data?.[0]?.embedding;
    if (!Array.isArray(embedding) || embedding.some((value: unknown) => typeof value !== "number" || !Number.isFinite(value))) {
      throw new AIProviderError("malformed_response", "AI provider returned an invalid embedding");
    }
    if (this.config.embeddingDimensions !== undefined && embedding.length !== this.config.embeddingDimensions) {
      throw new AIProviderError("dimension_mismatch", `Embedding dimension ${embedding.length} does not match configured dimension ${this.config.embeddingDimensions}`);
    }
    return { embedding, model };
  }

  private async request(url: string, apiKey: string, body: Record<string, unknown>): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const headers: Record<string, string> = {
        "content-type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      };
      // OpenCode requires session ID header
      if (this.config.baseUrl?.includes("opencode.ai")) {
        headers["x-opencode-session"] = `session-${Date.now()}`;
      }
      let response: Response;
      try {
        response = await fetch(url, {
          method: "POST",
          headers,
          body: JSON.stringify(body),
          signal: controller.signal,
        });
      } catch (error) {
        if (controller.signal.aborted || (error instanceof Error && error.name === "AbortError")) {
          throw new AIProviderError("timeout", "AI provider request timed out");
        }
        throw new AIProviderError("provider_error", "AI provider request failed");
      }
      if (!response.ok) throw new AIProviderError("provider_error", providerMessage(response.status));
      try {
        return await response.json() as unknown;
      } catch {
        throw new AIProviderError("malformed_response", "AI provider returned invalid JSON");
      }
    } finally {
      clearTimeout(timer);
    }
  }
}

export function createOpenAICompatibleProvider(config: OpenAICompatibleConfig): AIProvider {
  return new OpenAICompatibleProvider(config);
}
