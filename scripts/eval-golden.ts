import "dotenv/config";
import { readFileSync } from "fs";
import { getAIProvider } from "../lib/ai/provider-factory";
import { searchQuestionCatalog } from "../lib/ai/retrieval/catalog-search";
import { searchCatalog } from "../lib/catalog/queries";
import { buildEvidenceContext } from "../lib/ai/retrieval/context-builder";

interface GoldenTest {
  id: string;
  question: string;
  expectedEntities: string[];
  expectedFacts: string[];
  acceptableAnswerCriteria: string;
  category: string;
}

async function runTest(test: GoldenTest): Promise<{ id: string; passed: boolean; answer: string; details: string }> {
  try {
    // 1. Retrieve evidence
    const variants = await searchQuestionCatalog(test.question, searchCatalog);
    const evidence = buildEvidenceContext(variants);

    // 2. Check entity retrieval
    const retrievedEntities = evidence.map((e) => e.content.toLowerCase());
    const entityMatch = test.expectedEntities.length === 0 || test.expectedEntities.some((ent) =>
      retrievedEntities.some((e) => e.includes(ent.toLowerCase()))
    );

    // 3. Generate answer via AI
    const provider = getAIProvider();
    const output = await provider.chat({ question: test.question, evidence, language: "th" });
    const answer = output.answer;

    // 4. Check no-data case
    if (test.category === "no-data") {
      const saysNoData = /ไม่พบ|ไม่มีข้อมูล|ไม่ทราบ/i.test(answer);
      return { id: test.id, passed: saysNoData, answer, details: saysNoData ? "OK: stated no data" : "FAIL: fabricated answer" };
    }

    // 5. Basic answer quality check
    const hasNumbers = /\d/.test(answer);
    const hasAnswer = answer.length > 10;
    const passed = entityMatch && hasAnswer;

    return {
      id: test.id,
      passed,
      answer: answer.slice(0, 200),
      details: `entities=${test.expectedEntities.length > 0 ? (entityMatch ? "match" : "miss") : "n/a"}, hasAnswer=${hasAnswer}, hasNumbers=${hasNumbers}`,
    };
  } catch (e: unknown) {
    return { id: test.id, passed: false, answer: "", details: `error: ${e instanceof Error ? e.message : String(e)}` };
  }
}

async function main() {
  const dataset = JSON.parse(readFileSync("fixtures/eval/golden-test-dataset.json", "utf8"));
  const tests: GoldenTest[] = dataset.tests;

  console.log(`Running ${tests.length} golden tests...\n`);
  let passed = 0, failed = 0;

  for (const test of tests) {
    const result = await runTest(test);
    const icon = result.passed ? "✅" : "❌";
    console.log(`${icon} ${test.id} [${test.category}]`);
    console.log(`   Q: ${test.question}`);
    console.log(`   A: ${result.answer.slice(0, 150)}`);
    console.log(`   ${result.details}`);
    console.log();
    if (result.passed) passed++; else failed++;
  }

  console.log(`\nResults: ${passed}/${tests.length} passed, ${failed} failed`);
  process.exitCode = failed > 0 ? 1 : 0;
}

main();
