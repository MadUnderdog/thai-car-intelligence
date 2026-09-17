import type { AIProvider, ChatInput, ChatOutput } from "./types";

export type ErrorClass = "TRANSIENT_TIMEOUT" | "RATE_LIMIT" | "NETWORK_ERROR" | "AUTH_ERROR" | "INVALID_REQUEST" | "PROVIDER_ERROR" | "SUCCESS";

export type GatewayConfig = {
  primaryProvider: AIProvider;
  fallbackProvider?: AIProvider;
  requestTimeoutMs: number;
  maxAttempts: number;
  thaiRepairEnabled: boolean;
};

export type ProviderHealth = {
  successRate: number;
  timeoutRate: number;
  avgLatencyMs: number;
  lastFailureAt: Date | null;
  recentResults: boolean[];
};

export type GatewayMetrics = {
  llmRequests: number;
  llmSuccess: number;
  llmTimeout: number;
  llmRetry: number;
  llmFallback: number;
  thaiInitialPass: number;
  thaiFinalPass: number;
  thaiRepairTriggered: number;
  thaiRepairSuccess: number;
  thaiTemplateUsed: number;
  retrievalMs: number;
  llmMs: number;
  repairMs: number;
  totalMs: number;
  latencies: number[];
};

function classifyError(error: unknown): ErrorClass {
  const msg = String(error).toLowerCase();
  if (msg.includes("timeout") || msg.includes("deadline")) return "TRANSIENT_TIMEOUT";
  if (msg.includes("rate") || msg.includes("429") || msg.includes("too many")) return "RATE_LIMIT";
  if (msg.includes("network") || msg.includes("econnrefused") || msg.includes("fetch")) return "NETWORK_ERROR";
  if (msg.includes("auth") || msg.includes("401") || msg.includes("403")) return "AUTH_ERROR";
  if (msg.includes("invalid") || msg.includes("400") || msg.includes("bad request")) return "INVALID_REQUEST";
  return "PROVIDER_ERROR";
}

function isRetryable(errorClass: ErrorClass): boolean {
  return errorClass === "TRANSIENT_TIMEOUT" || errorClass === "RATE_LIMIT" || errorClass === "NETWORK_ERROR";
}

function isThai(text: string): boolean {
  if (!text || text.length === 0) return true;
  const thaiChars = (text.match(/[\u0E00-\u0E7F]/g) || []).length;
  return thaiChars / text.length > 0.3;
}

function buildThaiTemplate(evidence: ChatInput["evidence"]): string {
  if (evidence.length === 0) return "ไม่พบข้อมูลยืนยันในฐานข้อมูล";
  const lines = evidence.slice(0, 3).map((e) => {
    const match = e.content.match(/(.+?): price (.+)/);
    if (match) return `- ${match[1]}: ฿${Number(match[2]).toLocaleString()}`;
    return `- ${e.content.substring(0, 100)}`;
  });
  return `จากระบบฐานข้อมูล:\n${lines.join("\n")}\n\nข้อมูลนี้เป็นข้อมูลจากฐานข้อมูล ไม่ใช่คำตอบจาก AI`;
}

export class LLMGateway {
  private config: GatewayConfig;
  private metrics: GatewayMetrics;
  private providerHealth: Map<string, ProviderHealth> = new Map();

  constructor(config: GatewayConfig) {
    this.config = config;
    this.metrics = {
      llmRequests: 0, llmSuccess: 0, llmTimeout: 0, llmRetry: 0,
      llmFallback: 0, thaiInitialPass: 0, thaiFinalPass: 0,
      thaiRepairTriggered: 0, thaiRepairSuccess: 0, thaiTemplateUsed: 0,
      retrievalMs: 0, llmMs: 0, repairMs: 0, totalMs: 0, latencies: [],
    };
  }

  async chat(input: ChatInput): Promise<ChatOutput & { errorClass?: ErrorClass }> {
    const totalStart = Date.now();
    this.metrics.llmRequests++;
    let lastError: unknown;
    let lastErrorClass: ErrorClass = "PROVIDER_ERROR";

    // Try primary provider with retry
    for (let attempt = 1; attempt <= this.config.maxAttempts; attempt++) {
      try {
        const llmStart = Date.now();
        const result = await Promise.race([
          this.config.primaryProvider.chat(input),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error("timeout")), this.config.requestTimeoutMs)
          ),
        ]);
        const llmLatency = Date.now() - llmStart;
        this.recordLatency(llmLatency);
        this.updateHealth("primary", true, llmLatency);

        // Thai validation
        if (this.config.thaiRepairEnabled && !isThai(result.answer)) {
          this.metrics.thaiRepairTriggered++;
          const repaired = await this.tryThaiRepair(input, result);
          if (repaired) {
            this.metrics.thaiRepairSuccess++;
            this.metrics.thaiFinalPass++;
            this.metrics.llmSuccess++;
            this.metrics.repairMs = Date.now() - totalStart - llmLatency;
            this.metrics.totalMs = Date.now() - totalStart;
            return { ...repaired, errorClass: "SUCCESS" };
          }
        }

        this.metrics.thaiInitialPass++;
        this.metrics.thaiFinalPass++;
        this.metrics.llmSuccess++;
        this.metrics.llmMs = llmLatency;
        this.metrics.totalMs = Date.now() - totalStart;
        return { ...result, errorClass: "SUCCESS" };
      } catch (error) {
        lastError = error;
        lastErrorClass = classifyError(error);
        this.updateHealth("primary", false, 0);
        if (lastErrorClass === "TRANSIENT_TIMEOUT") this.metrics.llmTimeout++;

        if (attempt < this.config.maxAttempts && isRetryable(lastErrorClass)) {
          this.metrics.llmRetry++;
          await new Promise((r) => setTimeout(r, 1000 * attempt));
        }
      }
    }

    // Try fallback if configured
    if (this.config.fallbackProvider) {
      try {
        this.metrics.llmFallback++;
        const result = await this.config.fallbackProvider.chat(input);
        this.updateHealth("fallback", true, 0);
        this.metrics.llmSuccess++;
        this.metrics.totalMs = Date.now() - totalStart;

        if (this.config.thaiRepairEnabled && !isThai(result.answer)) {
          this.metrics.thaiRepairTriggered++;
          const repaired = await this.tryThaiRepair(input, result);
          if (repaired) {
            this.metrics.thaiRepairSuccess++;
            this.metrics.thaiFinalPass++;
            return { ...repaired, errorClass: "SUCCESS" };
          }
        }

        this.metrics.thaiFinalPass++;
        return { ...result, errorClass: "SUCCESS" };
      } catch (error) {
        lastError = error;
        lastErrorClass = classifyError(error);
        this.updateHealth("fallback", false, 0);
      }
    }

    // Thai template fallback
    this.metrics.thaiTemplateUsed++;
    this.metrics.totalMs = Date.now() - totalStart;
    return {
      answer: buildThaiTemplate(input.evidence),
      citations: [],
      status: "unavailable",
      errorClass: lastErrorClass,
    };
  }

  private async tryThaiRepair(input: ChatInput, original: ChatOutput): Promise<ChatOutput | null> {
    try {
      const result = await Promise.race([
        this.config.primaryProvider.chat({ ...input, question: `${input.question}\n\nตอบภาษาไทยเท่านั้น ห้ามตอบภาษาอังกฤษ` }),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("timeout")), this.config.requestTimeoutMs)
        ),
      ]);
      if (isThai((result as ChatOutput).answer)) return result as ChatOutput;
    } catch { /* ignore */ }
    return null;
  }

  private updateHealth(provider: string, success: boolean, latencyMs: number) {
    let health = this.providerHealth.get(provider);
    if (!health) {
      health = { successRate: 0, timeoutRate: 0, avgLatencyMs: 0, lastFailureAt: null, recentResults: [] };
      this.providerHealth.set(provider, health);
    }
    health.recentResults.push(success);
    if (health.recentResults.length > 20) health.recentResults.shift();
    const recent = health.recentResults;
    health.successRate = recent.filter(Boolean).length / recent.length;
    health.timeoutRate = recent.filter((r) => !r).length / recent.length;
    if (latencyMs > 0) health.avgLatencyMs = (health.avgLatencyMs + latencyMs) / 2;
    if (!success) health.lastFailureAt = new Date();
  }

  private recordLatency(ms: number) {
    this.metrics.latencies.push(ms);
    if (this.metrics.latencies.length > 1000) this.metrics.latencies.shift();
  }

  getMetrics(): GatewayMetrics & { providerHealth: Record<string, ProviderHealth> } {
    const sorted = [...this.metrics.latencies].sort((a, b) => a - b);
    return {
      ...this.metrics,
      latencies: [...this.metrics.latencies],
      providerHealth: Object.fromEntries(this.providerHealth),
    };
  }
}
