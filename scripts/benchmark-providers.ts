import "dotenv/config";
import { readFileSync, writeFileSync } from "fs";

function isThai(text: string): boolean {
  if (!text || text.length === 0) return true;
  const thaiChars = (text.match(/[\u0E00-\u0E7F]/g) || []).length;
  return thaiChars / text.length > 0.3;
}

async function callModel(model: string, question: string, useResponses = false): Promise<{ answer: string; latencyMs: number; success: boolean }> {
  const key = process.env.AI_API_KEY;
  const start = Date.now();
  try {
    if (useResponses) {
      const res = await fetch("https://opencode.ai/zen/go/v1/responses", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
        body: JSON.stringify({ model, input: `ตอบภาษาไทยเท่านั้น\n\n${question}`, max_output_tokens: 500 }),
      });
      const data = await res.json() as any;
      const text = data.output?.find((o: any) => o.type === "message")?.content?.[0]?.text || "";
      return { answer: text, latencyMs: Date.now() - start, success: data.status === "completed" && text.length > 0 };
    } else {
      const res = await fetch("https://opencode.ai/zen/go/v1/chat/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
        body: JSON.stringify({ model, messages: [{ role: "user", content: `ตอบภาษาไทยเท่านั้น\n\n${question}` }], max_tokens: 500, temperature: 0.1 }),
      });
      const data = await res.json() as any;
      const text = data.choices?.[0]?.message?.content || "";
      return { answer: text, latencyMs: Date.now() - start, success: res.status === 200 && text.length > 0 };
    }
  } catch {
    return { answer: "", latencyMs: Date.now() - start, success: false };
  }
}

const CATEGORIES = {
  SIMPLE_FACTUAL: [
    { q: "Camry HEV Premium ราคาเท่าไหร่", expect: ["1,659,000", "1659000"] },
    { q: "BYD Dolphin มีกำลังกี่ kW", expect: ["70"] },
    { q: "MG S5 EV PLUS มีแรงบิดเท่าไหร่", expect: ["250"] },
    { q: "Ford Everest ราคาเท่าไหร่", expect: [] },
    { q: "Tesla Model 3 มี range เท่าไหร่", expect: [] },
  ],
  COMPARISON: [
    { q: "BYD ATTO 3 เทียบ MG S5 EV PLUS เรื่องราคา", expect: [] },
    { q: "Camry เทียบ Accord เรื่องราคา", expect: [] },
    { q: "EV vs HEV ต่างกันยังไง", expect: [] },
  ],
  COMPLEX_REASONING: [
    { q: "งบ 1 ล้าน ซื้อ EV รุ่นไหนดี", expect: [] },
    { q: "ครอบครัว 4 คน ควรเลือก SUV หรือ MPV", expect: [] },
    { q: "รถ Eco Car คุ้มค่าไหมสำหรับใช้ในเมือง", expect: [] },
  ],
  ADVISORY: [
    { q: "แนะนำรถ EV สำหรับวิ่งในกรุงเทพ", expect: [] },
    { q: "ควรซื้อรถใหม่หรือรถมือสอง", expect: [] },
    { q: "เลือกประกันชั้น 1 หรือ 2 ดี", expect: [] },
  ],
};

async function main() {
  console.log(`=== gpt-5.6-luna Benchmark ===\n`);

  const models = [
    { name: "mimo-v2.5", useResponses: false },
    { name: "deepseek-v4-flash", useResponses: false },
    { name: "gpt-5.6-luna", useResponses: true },
  ];

  const allResults: any[] = [];

  for (const model of models) {
    console.log(`--- ${model.name} ---`);
    for (const [cat, tests] of Object.entries(CATEGORIES)) {
      const results = [];
      for (const test of tests) {
        const r = await callModel(model.name, test.q, model.useResponses);
        const correct = test.expect.length === 0 || test.expect.some((e: string) => r.answer.includes(e));
        results.push({ ...r, thai: isThai(r.answer), correct });
      }
      const success = results.filter((r) => r.success).length;
      const thai = results.filter((r) => r.thai).length;
      const correct = results.filter((r) => r.correct).length;
      const latencies = results.map((r) => r.latencyMs).sort((a, b) => a - b);
      const avg = Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length || 0);
      allResults.push({ model: model.name, category: cat, success, total: tests.length, thai, correct, avgLatency: avg });
      console.log(`  ${cat}: ${success}/${tests.length} success, ${thai} thai, ${correct} correct, avg ${avg}ms`);
    }
    console.log();
  }

  // Summary
  console.log(`=== SUMMARY ===`);
  console.log(`Model            Avg Success  Thai%  Correct%  Avg Latency`);
  for (const model of models) {
    const modelResults = allResults.filter((r) => r.model === model.name);
    const totalSuccess = modelResults.reduce((s, r) => s + r.success, 0);
    const totalThai = modelResults.reduce((s, r) => s + r.thai, 0);
    const totalCorrect = modelResults.reduce((s, r) => s + r.correct, 0);
    const totalTests = modelResults.reduce((s, r) => s + r.total, 0);
    const totalSuccessCount = modelResults.reduce((s, r) => s + r.success, 0);
    const avgLatency = Math.round(modelResults.reduce((s, r) => s + r.avgLatency * r.total, 0) / totalTests);
    console.log(`${model.name.padEnd(16)} ${(totalSuccess/totalTests*100).toFixed(0)}%      ${(totalThai/(totalSuccessCount||1)*100).toFixed(0)}%   ${(totalCorrect/(totalSuccessCount||1)*100).toFixed(0)}%     ${avgLatency}ms`);
  }

  writeFileSync("docs/gpt56luna-benchmark.json", JSON.stringify(allResults, null, 2));
  console.log(`\nReport saved: docs/gpt56luna-benchmark.json`);
}

main().catch(console.error);
