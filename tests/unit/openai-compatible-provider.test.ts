import { afterEach, describe, expect, it, vi } from "vitest";
import { AIProviderError, OpenAICompatibleProvider } from "../../lib/ai/providers/openai-compatible";

afterEach(() => vi.unstubAllGlobals());

const config = {
  baseUrl: "https://api.example.test/v1",
  apiKey: "test-key",
  model: "test-chat",
  embeddingBaseUrl: "https://embed.example.test/v1",
  embeddingApiKey: "embed-key",
  embeddingModel: "test-embed",
  embeddingDimensions: 3,
  timeoutMs: 100,
};

const input = { question: "ราคาเท่าไร", evidence: [{ id: "e1", kind: "fact" as const, content: "ราคา 1 บาท", sourcePageUrl: "https://example.test" }], language: "th" as const };

describe("OpenAI-compatible provider", () => {
  it("returns validated chat output", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ choices: [{ message: { content: "ราคา 1 บาท" } }] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await new OpenAICompatibleProvider(config).chat(input);
    expect(result).toEqual({ answer: "ราคา 1 บาท", citations: [], status: "ok" });
    expect(fetchMock.mock.calls[0][0]).toBe("https://api.example.test/v1/chat/completions");
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer test-key");
  });

  it("reports upstream provider errors without exposing secrets", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("bad", { status: 502 })));
    const error = await new OpenAICompatibleProvider(config).chat(input).catch((value) => value);
    expect(error).toBeInstanceOf(AIProviderError);
    expect(error.code).toBe("provider_error");
    expect(error.message).not.toContain("test-key");
  });

  it("rejects malformed chat responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ choices: [] }), { status: 200 })));
    await expect(new OpenAICompatibleProvider(config).chat(input)).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("reports timeout/abort as unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn((_url: string, options: { signal: AbortSignal }) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })));
    })));
    await expect(new OpenAICompatibleProvider({ ...config, timeoutMs: 1 }).chat(input)).rejects.toMatchObject({ code: "timeout" });
  });

  it("rejects missing API keys as misconfigured", async () => {
    await expect(new OpenAICompatibleProvider({ ...config, apiKey: "" }).chat(input)).rejects.toMatchObject({ code: "misconfigured" });
  });

  it("validates embedding dimensions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: [{ embedding: [1, 2] }] }), { status: 200 })));
    await expect(new OpenAICompatibleProvider(config).embed("hello")).rejects.toMatchObject({ code: "dimension_mismatch" });
  });
});
