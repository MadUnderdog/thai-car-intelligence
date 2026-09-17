import type { AIProvider, ChatInput, ChatOutput } from "./types";

export type RouteClass = "FAST_PATH" | "SIMPLE_FACTUAL" | "COMPARISON" | "COMPLEX_REASONING" | "ADVISORY";
export type ProviderEntry = { name: string; provider: AIProvider; model: string; costPer1kTokens: number };
export type CircuitState = "CLOSED" | "OPEN" | "HALF_OPEN";
export type HealthRecord = { successes: number; failures: number; latencies: number[]; circuitState: CircuitState; lastFailureAt: number; consecutiveFailures: number };
export type RoutingDecision = { routeClass: RouteClass; selectedProvider: string; selectedModel: string; circuitState: CircuitState; reason: string; costEstimate: number; cacheHit: boolean; escalated: boolean };
export type RoutingMetrics = { totalRequests: number; requestsByModel: Record<string, number>; fallbackCount: number; templateCount: number; totalCostEstimate: number; avgLatencyByModel: Record<string, number>; cacheHits: number; cacheMisses: number; escalations: number; llmRequestsAvoided: number };
export type CacheEntry = { answer: string; citations: any[]; timestamp: number; evidenceHash: string; confidence: "high" | "medium" | "low" };

const FAILURE_THRESHOLD = 5;
const RECOVERY_TIMEOUT_MS = 60_000;
const CACHE_TTL_MS = 3600_000;
const UNSAFE_PATTERNS = /แนะนำ|ควร|เลือก|ซื้อ|ดีไหม|คุ้ม|ส่วนตัว|偏好|recommend|should buy|personal/i;

function isCacheable(query: string): boolean { return !UNSAFE_PATTERNS.test(query); }
function classifyRoute(input: ChatInput): RouteClass {
  const q = input.question.toLowerCase();
  if (input.evidence.length === 0) return "FAST_PATH";
  if (/เปรียบเทียบ|เทียบ|compare|vs/.test(q)) return "COMPARISON";
  if (/แนะนำ| advice|ควร|suggest|เลือก/.test(q)) return "ADVISORY";
  if (/ทำไม|เหตุผล|วิเคราะห์|analyze/.test(q)) return "COMPLEX_REASONING";
  return "SIMPLE_FACTUAL";
}
function hashEvidence(evidence: any[]): string { return evidence.map((e) => e.content).sort().join("|").substring(0, 100); }
function normalizeQuery(q: string): string { return q.toLowerCase().replace(/\s+/g, "").replace(/[?!.,]/g, ""); }
function evidenceConfidence(evidence: any[]): "high" | "medium" | "low" {
  if (evidence.length === 0) return "low";
  if (evidence.some((e) => e.content.includes("official") || e.content.includes("verified"))) return "high";
  if (evidence.length >= 3) return "medium";
  return "low";
}
function shouldEscalate(routeClass: RouteClass, confidence: string): boolean {
  if (routeClass === "COMPLEX_REASONING" || routeClass === "ADVISORY") return confidence !== "high";
  if (routeClass === "COMPARISON") return confidence === "low";
  return false;
}
function healthScore(h: HealthRecord): number {
  const total = h.successes + h.failures;
  const sr = total > 0 ? h.successes / total : 0.5;
  const al = h.latencies.length > 0 ? h.latencies.reduce((a, b) => a + b, 0) / h.latencies.length : 5000;
  return sr * 0.7 + Math.max(0, 1 - al / 20000) * 0.3;
}
function isThai(text: string): boolean { if (!text || text.length === 0) return true; return (text.match(/[\u0E00-\u0E7F]/g) || []).length / text.length > 0.3; }

type ChatResult = ChatOutput & { routing: RoutingDecision; errorClass?: string; traceId: string };

export class ModelRouter {
  private routes = new Map<RouteClass, ProviderEntry[]>();
  private health = new Map<string, HealthRecord>();
  private cache = new Map<string, CacheEntry>();
  private metrics: RoutingMetrics;
  private premiumProvider?: ProviderEntry;

  constructor(providers: { simple: AIProvider; complex: AIProvider; premium?: AIProvider; simpleModel: string; complexModel: string; premiumModel?: string }) {
    const s: ProviderEntry = { name: "simple", provider: providers.simple, model: providers.simpleModel, costPer1kTokens: providers.simpleModel.includes("mimo") ? 0.001 : 0.002 };
    const c: ProviderEntry = { name: "complex", provider: providers.complex, model: providers.complexModel, costPer1kTokens: providers.complexModel.includes("deepseek") ? 0.003 : 0.01 };
    if (providers.premium && providers.premiumModel) this.premiumProvider = { name: "premium", provider: providers.premium, model: providers.premiumModel, costPer1kTokens: 0.01 };
    this.routes.set("FAST_PATH", []);
    this.routes.set("SIMPLE_FACTUAL", [s]);
    this.routes.set("COMPARISON", [s, c]);
    this.routes.set("COMPLEX_REASONING", [c]);
    this.routes.set("ADVISORY", [c]);
    this.metrics = { totalRequests: 0, requestsByModel: {}, fallbackCount: 0, templateCount: 0, totalCostEstimate: 0, avgLatencyByModel: {}, cacheHits: 0, cacheMisses: 0, escalations: 0, llmRequestsAvoided: 0 };
  }

  private getCircuitState(name: string): CircuitState {
    const h = this.health.get(name);
    if (!h) return "CLOSED";
    if (h.circuitState === "OPEN" && Date.now() - h.lastFailureAt > RECOVERY_TIMEOUT_MS) { h.circuitState = "HALF_OPEN"; return "HALF_OPEN"; }
    return h.circuitState;
  }
  private recordSuccess(name: string, ms: number) {
    let h = this.health.get(name);
    if (!h) { h = { successes: 0, failures: 0, latencies: [], circuitState: "CLOSED", lastFailureAt: 0, consecutiveFailures: 0 }; this.health.set(name, h); }
    h.successes++; h.consecutiveFailures = 0; h.latencies.push(ms);
    if (h.latencies.length > 50) h.latencies.shift();
    if (h.circuitState === "HALF_OPEN") h.circuitState = "CLOSED";
  }
  private recordFailure(name: string) {
    let h = this.health.get(name);
    if (!h) { h = { successes: 0, failures: 0, latencies: [], circuitState: "CLOSED", lastFailureAt: 0, consecutiveFailures: 0 }; this.health.set(name, h); }
    h.failures++; h.consecutiveFailures++; h.lastFailureAt = Date.now();
    if (h.consecutiveFailures >= FAILURE_THRESHOLD) h.circuitState = "OPEN";
  }
  private updateMetrics(model: string, ms: number, cost: number) {
    this.metrics.totalRequests++;
    this.metrics.requestsByModel[model] = (this.metrics.requestsByModel[model] || 0) + 1;
    this.metrics.totalCostEstimate += cost;
    const prev = this.metrics.avgLatencyByModel[model] || 0;
    const cnt = this.metrics.requestsByModel[model];
    this.metrics.avgLatencyByModel[model] = Math.round((prev * (cnt - 1) + ms) / cnt);
  }
  private getCached(q: string, ev: any[]): CacheEntry | null {
    const e = this.cache.get(`${normalizeQuery(q)}:${hashEvidence(ev)}`);
    if (!e || Date.now() - e.timestamp > CACHE_TTL_MS) { if (e) this.cache.delete(`${normalizeQuery(q)}:${hashEvidence(ev)}`); return null; }
    return e;
  }
  private setCache(q: string, ev: any[], ans: string, cit: any[], conf: "high" | "medium" | "low") {
    if (!isCacheable(q) || conf === "low") return;
    this.cache.set(`${normalizeQuery(q)}:${hashEvidence(ev)}`, { answer: ans, citations: cit, timestamp: Date.now(), evidenceHash: hashEvidence(ev), confidence: conf });
  }
  private selectProvider(providers: ProviderEntry[]): ProviderEntry | null {
    const avail = providers.filter((p) => this.getCircuitState(p.name) !== "OPEN");
    return avail.length > 0 ? avail.sort((a, b) => a.costPer1kTokens - b.costPer1kTokens)[0] : null;
  }

  async chat(input: ChatInput): Promise<ChatResult> {
    const traceId = `tr-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
    const routeClass = classifyRoute(input);
    const providers = this.routes.get(routeClass) || [];
    const confidence = evidenceConfidence(input.evidence);
    const mk = (ans: string, cit: any[], stat: string, route: RoutingDecision, ec?: string): ChatResult => ({ answer: ans, citations: cit, status: stat as any, routing: route, errorClass: ec, traceId });

    if (routeClass === "FAST_PATH") {
      const ans = input.evidence.length > 0 ? `จากระบบฐานข้อมูล:\n${input.evidence.slice(0, 3).map((e) => `- ${e.content.substring(0, 100)}`).join("\n")}` : "ไม่พบข้อมูลยืนยันในฐานข้อมูล";
      return mk(ans, [], "ok", { routeClass: "FAST_PATH", selectedProvider: "none", selectedModel: "template", circuitState: "CLOSED", reason: "fast_path_no_llm", costEstimate: 0, cacheHit: false, escalated: false });
    }

    const cached = this.getCached(input.question, input.evidence);
    if (cached) { this.metrics.cacheHits++; this.metrics.llmRequestsAvoided++; return mk(cached.answer, cached.citations, "ok", { routeClass, selectedProvider: "cache", selectedModel: "cache", circuitState: "CLOSED", reason: `cache_hit_${cached.confidence}`, costEstimate: 0, cacheHit: true, escalated: false }); }
    this.metrics.cacheMisses++;

    let escalated = false;
    let selProviders = providers;
    if (shouldEscalate(routeClass, confidence) && this.premiumProvider && this.getCircuitState("premium") !== "OPEN") { selProviders = [this.premiumProvider, ...providers]; escalated = true; this.metrics.escalations++; }

    const provider = this.selectProvider(selProviders);
    if (!provider) { this.metrics.templateCount++; return mk(input.evidence.length > 0 ? `จากระบบฐานข้อมูล:\n${input.evidence.slice(0, 3).map((e) => `- ${e.content.substring(0, 100)}`).join("\n")}` : "ไม่พบข้อมูลยืนยันในฐานข้อมูล", [], "unavailable", { routeClass, selectedProvider: "template", selectedModel: "evidence_template", circuitState: "CLOSED", reason: "all_circuits_open", costEstimate: 0, cacheHit: false, escalated: false }, "PROVIDER_ERROR"); }

    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        const start = Date.now();
        const result = await Promise.race([provider.provider.chat(input), new Promise<never>((_, rej) => setTimeout(() => rej(new Error("timeout")), 15000))]);
        const ms = Date.now() - start;
        this.recordSuccess(provider.name, ms); this.updateMetrics(provider.model, ms, provider.costPer1kTokens);
        this.setCache(input.question, input.evidence, (result as ChatOutput).answer, (result as ChatOutput).citations, confidence);
        return mk((result as ChatOutput).answer, (result as ChatOutput).citations, "ok", { routeClass, selectedProvider: provider.name, selectedModel: provider.model, circuitState: this.getCircuitState(provider.name), reason: `attempt_${attempt}`, costEstimate: provider.costPer1kTokens, cacheHit: false, escalated });
      } catch { this.recordFailure(provider.name); if (attempt < 2) await new Promise((r) => setTimeout(r, 1000 * attempt)); }
    }

    const fb = providers.find((p) => p.name !== provider.name && this.getCircuitState(p.name) !== "OPEN");
    if (fb) { this.metrics.fallbackCount++; try { const start = Date.now(); const result = await fb.provider.chat(input); const ms = Date.now() - start; this.recordSuccess(fb.name, ms); this.updateMetrics(fb.model, ms, fb.costPer1kTokens); this.setCache(input.question, input.evidence, (result as ChatOutput).answer, (result as ChatOutput).citations, confidence); return mk((result as ChatOutput).answer, (result as ChatOutput).citations, "ok", { routeClass, selectedProvider: fb.name, selectedModel: fb.model, circuitState: this.getCircuitState(fb.name), reason: "fallback", costEstimate: fb.costPer1kTokens, cacheHit: false, escalated }); } catch { this.recordFailure(fb.name); } }

    this.metrics.templateCount++;
    return mk(input.evidence.length > 0 ? `จากระบบฐานข้อมูล:\n${input.evidence.slice(0, 3).map((e) => `- ${e.content.substring(0, 100)}`).join("\n")}` : "ไม่พบข้อมูลยืนยันในฐานข้อมูล", [], "unavailable", { routeClass, selectedProvider: "template", selectedModel: "evidence_template", circuitState: "CLOSED", reason: `${provider.name}_failed`, costEstimate: 0, cacheHit: false, escalated: false }, "PROVIDER_ERROR");
  }

  getHealth(): Record<string, { score: number; state: CircuitState; successes: number; failures: number; avgLatency: number }> {
    const r: Record<string, any> = {};
    for (const [n, h] of this.health) r[n] = { score: healthScore(h), state: this.getCircuitState(n), successes: h.successes, failures: h.failures, avgLatency: h.latencies.length > 0 ? Math.round(h.latencies.reduce((a, b) => a + b, 0) / h.latencies.length) : 0 };
    return r;
  }
  getMetrics(): RoutingMetrics { return { ...this.metrics }; }
  getCacheStats(): { size: number; hitRate: number } { const t = this.metrics.cacheHits + this.metrics.cacheMisses; return { size: this.cache.size, hitRate: t > 0 ? this.metrics.cacheHits / t : 0 }; }
}
