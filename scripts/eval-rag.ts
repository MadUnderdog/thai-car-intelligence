import "dotenv/config";
import { readFileSync, writeFileSync } from "fs";
import { parseAutomotiveQuery } from "../lib/ai/retrieval/query-parser";
import { searchQuestionCatalog } from "../lib/ai/retrieval/catalog-search";
import { ModelRouter } from "../lib/ai/router";
import { getAIProvider } from "../lib/ai/provider-factory";

type EvalResult = {
  id: string;
  routeClass: string;
  parserCorrect: boolean;
  retrievalSuccess: boolean;
  isFastPath: boolean;
  providerSuccess: boolean;
  thaiResponse: boolean;
  noFabrication: boolean;
  selectedProvider: string;
  latencyMs: number;
  status: string;
};

function isThai(text: string): boolean {
  if (!text || text.length === 0) return true;
  const thaiChars = (text.match(/[\u0E00-\u0E7F]/g) || []).length;
  return thaiChars / text.length > 0.3;
}

function classifyRouteClass(q: string): string {
  if (/เปรียบเทียบ|เทียบ|compare|vs/.test(q)) return "COMPARISON";
  if (/แนะนำ| advice|ควร|suggest|เลือก/.test(q)) return "ADVISORY";
  if (/ทำไม|เหตุผล|วิเคราะห์/.test(q)) return "COMPLEX_REASONING";
  return "SIMPLE_FACTUAL";
}

async function main() {
  const dataset = JSON.parse(readFileSync("fixtures/eval/rag-evaluation-v2.json", "utf-8"));
  const provider = getAIProvider();
  const router = new ModelRouter({ simple: provider, complex: provider, simpleModel: "mimo-v2.5", complexModel: "deepseek-v4-flash" });

  console.log(`=== RAG Evaluation v5 (Model Routing) ===`);
  console.log(`Tests: ${dataset.tests.length}\n`);

  const results: EvalResult[] = [];

  for (const test of dataset.tests) {
    // 1. Parser evaluation
    const intent = parseAutomotiveQuery(test.question);
    let parserCorrect = true;
    if (test.expectedParser.fuelType && intent.type === "search") parserCorrect = intent.filters.fuelType === test.expectedParser.fuelType;
    if (test.expectedParser.brand && intent.type === "search") parserCorrect = parserCorrect && intent.filters.brand === test.expectedParser.brand;
    if (test.expectedParser.entities && "entities" in intent) {
      parserCorrect = parserCorrect && test.expectedParser.entities.every((e: string) =>
        intent.entities.some((ie: string) => ie.includes(e) || e.includes(ie))
      );
    }

    // 2. Retrieval evaluation
    let retrievalResults: any[] = [];
    let retrievalSuccess = false;
    try {
      retrievalResults = await searchQuestionCatalog(test.question);
      retrievalSuccess = retrievalResults.length >= (test.expectedRetrieval.minResults ?? 0);
      if (test.expectedRetrieval.brands) {
        const brands = retrievalResults.map((r: any) => r.manufacturer?.nameEn?.toLowerCase());
        retrievalSuccess = retrievalSuccess && test.expectedRetrieval.brands.every((b: string) => brands.includes(b.toLowerCase()));
      }
    } catch { retrievalSuccess = false; }

    const isFastPath = intent.type === "cheapest" || intent.type === "most_expensive" || intent.type === "count";
    const routeClass = isFastPath ? "FAST_PATH" : classifyRouteClass(test.question);

    // 3. Provider evaluation (skip fast path)
    let providerSuccess = false;
    let thaiResponse = isFastPath;
    let noFabrication = true;
    let selectedProvider = "none";
    let latencyMs = 0;

    if (!isFastPath) {
      const evidence = retrievalResults.slice(0, 5).map((v: any) => ({
        id: v.id, kind: "fact" as const, content: `${v.manufacturer?.nameEn} ${v.nameEn}: price ${v.prices?.[0]?.amount ?? "unknown"}`,
      }));
      const start = Date.now();
      const response = await router.chat({ question: test.question, evidence, language: "th" });
      latencyMs = Date.now() - start;
      providerSuccess = response.status !== "unavailable";
      thaiResponse = isThai(response.answer);
      noFabrication = !(test.expectedAnswer.mustNotClaim ?? []).some((c: string) =>
        (response.answer || "").toLowerCase().includes(c.toLowerCase())
      );
      selectedProvider = response.routing.selectedProvider;
    }

    let status = "PASS";
    if (isFastPath && parserCorrect && retrievalSuccess) status = "FAST_PATH_PASS";
    else if (!providerSuccess) status = "PROVIDER_ERROR";
    else if (!parserCorrect) status = "FAIL";
    else if (!retrievalSuccess) status = "FAIL";
    else if (!noFabrication) status = "FAIL";
    else if (!thaiResponse) status = "FAIL";

    results.push({
      id: test.id, routeClass, parserCorrect, retrievalSuccess, isFastPath,
      providerSuccess, thaiResponse, noFabrication, selectedProvider, latencyMs, status,
    });
    process.stdout.write(`  ${test.id}: ${status} route=${routeClass} provider=${selectedProvider}\n`);
  }

  // Report
  const appCorrect = results.filter((r) => r.parserCorrect).length;
  const appRetrieved = results.filter((r) => r.retrievalSuccess).length;
  const fastPaths = results.filter((r) => r.isFastPath).length;
  const llmResults = results.filter((r) => !r.isFastPath);
  const provSuccess = llmResults.filter((r) => r.providerSuccess).length;

  console.log(`\n=== APPLICATION BENCHMARK ===`);
  console.log(`Parser: ${appCorrect}/${results.length} (${(appCorrect/results.length*100).toFixed(0)}%)`);
  console.log(`Retrieval: ${appRetrieved}/${results.length} (${(appRetrieved/results.length*100).toFixed(0)}%)`);
  console.log(`Fast paths: ${fastPaths}`);

  console.log(`\n=== PROVIDER BENCHMARK ===`);
  console.log(`LLM requests: ${llmResults.length}`);
  console.log(`Success: ${provSuccess}/${llmResults.length} (${llmResults.length > 0 ? (provSuccess/llmResults.length*100).toFixed(0) : 0}%)`);

  // Per-route breakdown
  const byRoute = new Map<string, EvalResult[]>();
  for (const r of results) {
    const arr = byRoute.get(r.routeClass) || [];
    arr.push(r);
    byRoute.set(r.routeClass, arr);
  }
  console.log(`\n=== PER-ROUTE BREAKDOWN ===`);
  for (const [route, routeResults] of byRoute) {
    const prov = routeResults.filter((r) => !r.isFastPath);
    const succ = prov.filter((r) => r.providerSuccess).length;
    console.log(`  ${route}: ${routeResults.length} tests, provider success: ${succ}/${prov.length}`);
  }

  const thaiFinal = results.filter((r) => r.thaiResponse || r.isFastPath).length;
  const passed = results.filter((r) => r.status === "PASS" || r.status === "FAST_PATH_PASS").length;

  console.log(`\n=== LANGUAGE (request-level) ===`);
  console.log(`Thai final: ${thaiFinal}/${results.length}`);
  console.log(`Non-Thai: ${results.length - thaiFinal}`);

  console.log(`\n=== END-TO-END ===`);
  console.log(`Pass: ${passed}/${results.length}`);

  const healthScores = router.getHealth();
  console.log(`\n=== ROUTER HEALTH ===`);
  for (const [name, score] of Object.entries(healthScores as Record<string, any>)) {
    console.log(`  ${name}: ${score.toFixed(2)}`);
  }

  writeFileSync("docs/eval-v5.json", JSON.stringify({ results, healthScores }, null, 2));
  console.log(`\nReport saved: docs/eval-v5.json`);
}

main().catch(console.error);
