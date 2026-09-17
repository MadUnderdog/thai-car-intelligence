import type { AIProvider, ChatInput, ChatOutput, EmbeddingOutput } from "./types";
import { createOpenAICompatibleProvider, type OpenAICompatibleConfig } from "./providers/openai-compatible";

class UnavailableProvider implements AIProvider {
  readonly name = "unavailable";

  async chat(input: ChatInput): Promise<ChatOutput> {
    void input;
    return { answer: "ขณะนี้ยังไม่มีผู้ให้บริการ AI ที่พร้อมใช้งาน จึงไม่สามารถสรุปคำตอบแทนข้อมูลจริงได้", citations: [], status: "unavailable" };
  }

  async embed(text: string): Promise<EmbeddingOutput> {
    void text;
    throw new Error("AI provider unavailable");
  }
}

const unavailable = new UnavailableProvider();

function readConfig(env: NodeJS.ProcessEnv = process.env): OpenAICompatibleConfig | null {
  const provider = env.AI_PROVIDER?.trim().toLowerCase();
  if (provider !== "openai-compatible" && provider !== "openai") return null;
  const baseUrl = env.AI_BASE_URL?.trim();
  const apiKey = env.AI_API_KEY?.trim();
  const model = env.AI_MODEL?.trim();
  if (!baseUrl || !apiKey || !model) return null;

  const dimensionsText = env.EMBEDDING_DIMENSIONS?.trim();
  if (dimensionsText && (!Number.isInteger(Number(dimensionsText)) || Number(dimensionsText) <= 0)) return null;
  const embeddingProvider = env.EMBEDDING_PROVIDER?.trim().toLowerCase();
  if (embeddingProvider && embeddingProvider !== "openai-compatible" && embeddingProvider !== "openai") return null;
  return {
    baseUrl,
    apiKey,
    model,
    embeddingBaseUrl: env.EMBEDDING_BASE_URL?.trim() || undefined,
    embeddingApiKey: env.EMBEDDING_API_KEY?.trim() || undefined,
    embeddingModel: env.EMBEDDING_MODEL?.trim() || undefined,
    embeddingDimensions: dimensionsText ? Number(dimensionsText) : undefined,
  };
}

/** Selects only explicitly configured adapters; absent or unknown configuration stays unavailable. */
export function getAIProvider(): AIProvider {
  const config = readConfig();
  return config ? createOpenAICompatibleProvider(config) : unavailable;
}

export function createUnavailableProvider(): AIProvider {
  return unavailable;
}

export function getAIProviderConfig(env: NodeJS.ProcessEnv = process.env): OpenAICompatibleConfig | null {
  return readConfig(env);
}

/** Create a provider for a specific model using the same base URL and API key */
export function getAIProviderForModel(modelName: string): AIProvider {
  const config = readConfig();
  if (!config) return unavailable;
  return createOpenAICompatibleProvider({ ...config, model: modelName });
}

/** Get all configured model names from environment */
export function getConfiguredModels(): { simple: string; fastFallback: string; complex: string } {
  return {
    simple: process.env.AI_SIMPLE_MODEL || process.env.AI_MODEL || "mimo-v2.5",
    fastFallback: process.env.AI_FAST_FALLBACK_MODEL || "DeepSeek V4 Flash",
    complex: process.env.AI_COMPLEX_MODEL || "gpt-5.6-luna",
  };
}
