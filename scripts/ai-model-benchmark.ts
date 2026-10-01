import "dotenv/config";

const BASE_URL = process.env.AI_BASE_URL?.trim() || "";
const API_KEY = process.env.AI_API_KEY?.trim() || "";

interface BenchmarkCase {
  id: string;
  category: string;
  question: string;
  evidence: string[];
  expectedContains?: string[];
  mustNotInvent?: string;
}

// Fixed 24-case Thai automotive golden set
const GOLDEN_SET: BenchmarkCase[] = [
  // 5 verified price questions
  { id: "p1", category: "price", evidence: ["Honda City e:HEV ราคา 569,000 บาท"], expectedContains: ["569,000"], mustNotInvent: "Honda City e:HEV", question: "Honda City e:HEV ราคาเท่าไหร่?" },
  { id: "p2", category: "price", evidence: ["Honda Civic e:HEV ราคา 949,000 บาท"], expectedContains: ["949,000"], mustNotInvent: "Honda Civic", question: "Honda Civic e:HEV ราคาเท่าไหร่?" },
  { id: "p3", category: "price", evidence: ["MG4 Standard ราคา 699,900 บาท แบตเตอรี่ 51 kWh"], expectedContains: ["699,900"], mustNotInvent: "MG4", question: "MG4 Standard ราคาเท่าไหร่?" },
  { id: "p4", category: "price", evidence: ["BYD Atto 3 ราคา 669,900 บาท"], expectedContains: ["669,900"], mustNotInvent: "Atto 3", question: "BYD Atto 3 ราคาเท่าไหร่?" },
  { id: "p5", category: "price", evidence: ["Honda CR-V e:HEV ราคา 1,409,000 บาท"], expectedContains: ["1,409,000"], mustNotInvent: "CR-V", question: "Honda CR-V e:HEV ราคาเท่าไหร่?" },
  // 5 verified spec questions
  { id: "s1", category: "spec", evidence: ["MG4 Standard แบตเตอรี่ 51 kWh"], expectedContains: ["51"], question: "MG4 Standard แบตเตอรี่กี่ kWh?" },
  { id: "s2", category: "spec", evidence: ["MG IM5 แบตเตอรี่ 77 kWh ชาร์จ DC 150 kW"], expectedContains: ["77", "150"], question: "MG IM5 แบตเตอรี่กี่ kWh และชาร์จ DC กี่ kW?" },
  { id: "s3", category: "spec", evidence: ["Honda City e:HEV ขนาด 4589x1748x1467 mm"], expectedContains: ["4589"], question: "Honda City e:HEV ขนาดเท่าไหร่?" },
  { id: "s4", category: "spec", evidence: ["Honda Civic e:HEV กำลัง 141 แรงม้า"], expectedContains: ["141"], question: "Honda Civic e:HEV กำลังกี่แรงม้า?" },
  { id: "s5", category: "spec", evidence: ["BYD Atto 3 ระยะทาง 310 km แบตเตอรี่ 49.9 kWh"], expectedContains: ["49.9"], question: "BYD Atto 3 แบตเตอรี่กี่ kWh?" },
  // 4 variant-specific questions
  { id: "v1", category: "variant", evidence: ["Honda City e:HEV ราคา 569,000 บาท", "Honda City Hatchback e:HEV ราคา 579,000 บาท"], expectedContains: ["569,000"], question: "Honda City e:HEV (ซีดัน) ราคาเท่าไหร่?" },
  { id: "v2", category: "variant", evidence: ["MG4 Standard ราคา 699,900 บาท", "MG4 Extended ราคา 799,900 บาท"], expectedContains: ["699,900"], question: "MG4 Standard ราคาเท่าไหร่?" },
  { id: "v3", category: "variant", evidence: ["BYD Seal Dynamic ราคา 1,325,000 บาท", "BYD Seal Performance AWD ราคา 1,599,000 บาท"], expectedContains: ["1,325,000"], question: "BYD Seal Dynamic ราคาเท่าไหร่?" },
  { id: "v4", category: "variant", evidence: ["Honda WR-V SV ราคา 799,000 บาท", "Honda WR-V RS ราคา 869,000 บาท"], expectedContains: ["799,000"], question: "Honda WR-V SV ราคาเท่าไหร่?" },
  // 3 comparison/reasoning questions
  { id: "c1", category: "comparison", evidence: ["Honda City e:HEV ราคา 569,000 บาท", "Honda Civic e:HEV ราคา 949,000 บาท"], expectedContains: ["569,000", "949,000"], question: "เปรียบเทียบราคา Honda City e:HEV และ Honda Civic e:HEV" },
  { id: "c2", category: "comparison", evidence: ["MG4 Standard แบตเตอรี่ 51 kWh ราคา 699,900", "MG IM5 แบตเตอรี่ 77 kWh ราคา 1,549,900"], expectedContains: ["51", "77"], question: "เปรียบเทียบแบตเตอรี่ MG4 Standard และ MG IM5" },
  { id: "c3", category: "comparison", evidence: ["BYD Atto 3 ระยะทาง 310 km", "MG4 Standard ระยะทาง 350 km"], expectedContains: ["310", "350"], question: "เปรียบเทียบระยะทาง BYD Atto 3 และ MG4 Standard" },
  // 2 Thai synonym/alias questions
  { id: "a1", category: "alias", evidence: ["Honda City e:HEV ราคา 569,000 บาท"], expectedContains: ["569,000"], question: "ฮอนด้า ซิตี้ ราคาเท่าไหร่?" },
  { id: "a2", category: "alias", evidence: ["MG4 Standard แบตเตอรี่ 51 kWh"], expectedContains: ["51"], question: "เอ็มจี โฟร์ แบตเตอรี่กี่ kWh?" },
  // 2 ambiguous queries
  { id: "am1", category: "ambiguous", evidence: ["Honda e:HEV ราคา 569,000", "Honda e:HEV ราคา 949,000", "Honda e:HEV ราคา 1,409,000"], expectedContains: ["หลาย"], question: "Honda e:HEV ราคาเท่าไหร่?" },
  { id: "am2", category: "ambiguous", evidence: ["BYD Seal ราคา 1,325,000 DM-i 599,900"], expectedContains: ["หลาย"], question: "BYD Seal ราคาเท่าไหร่?" },
  // 2 unsupported/missing-fact queries
  { id: "u1", category: "unsupported", evidence: [], mustNotInvent: "Tesla Model Y ราคา", question: "Tesla Model Y ราคาเท่าไหร่?" },
  { id: "u2", category: "unsupported", evidence: [], mustNotInvent: "ToyotaAlphard ความเร็วสูงสุด", question: "Toyota Alphard ความเร็วสูงสุดเท่าไหร่?" },
  // 1 evidence-conflict question
  { id: "x1", category: "conflict", evidence: ["ข้อมูลแหล่งที่ 1: Honda HR-V e:HEV ราคา 949,000 บาท", "ข้อมูลแหล่งที่ 2: Honda HR-V e:HEV ราคา 959,000 บาท"], expectedContains: ["949,000", "959,000"], question: "Honda HR-V e:HEV ราคาเท่าไหร่?" },
];

async function chatWithModel(model: string, question: string, evidence: string[], timeoutMs = 30000) {
  const start = Date.now();
  try {
    const evidenceText = evidence.length > 0 ? `\nหลักฐาน:\n${evidence.join("\n")}` : "";
    const response = await fetch(`${BASE_URL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${API_KEY}`,
        "x-opencode-session": `bench-${Date.now()}`,
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: "คุณเป็นผู้ช่วยด้านข้อมูลรถยนต์ไทย ตอบเฉพาะจากหลักฐานที่ให้มาเท่านั้น ถ้าหลักฐานไม่พอ ให้บอกว่าไม่มีข้อมูลเพียงพอ ห้ามแต่งข้อมูล ถ้าหลักฐานขัดแย้งกัน ให้แสดงทั้งสองค่าพร้อมระบุว่าขัดแย้งกัน" },
          { role: "user", content: `${question}${evidenceText}` },
        ],
        max_tokens: 300,
      }),
    });
    const latency = Date.now() - start;
    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;
    const usage = data.usage;
    return {
      success: response.ok && !!content,
      content: content || "",
      latency,
      inputTokens: usage?.prompt_tokens || 0,
      outputTokens: usage?.completion_tokens || 0,
      error: response.ok ? null : `HTTP ${response.status}`,
    };
  } catch (e: any) {
    return { success: false, content: "", latency: Date.now() - start, inputTokens: 0, outputTokens: 0, error: e.message };
  }
}

function evaluateAnswer(content: string, expected?: string[]): boolean {
  if (!expected) return true;
  return expected.every((k) => content.includes(k));
}

function isUnsupportedClaimHandled(content: string): boolean {
  const refusalPatterns = ["ไม่มีข้อมูล", "ไม่พบ", "ไม่เพียงพอ", "ไม่สามารถยืนยัน", "ไม่มีหลักฐาน"];
  return refusalPatterns.some((p) => content.includes(p));
}

async function main() {
  console.log("=== GLM-5.3-Flash vs mimo-v2.5 Benchmark ===\n");
  console.log(`Total cases: ${GOLDEN_SET.length}\n`);

  const results: Record<string, any[]> = { "glm-5.3-flash": [], "mimo-v2.5": [] };

  for (const model of ["glm-5.3-flash", "mimo-v2.5"]) {
    console.log(`--- Benchmarking ${model} ---`);
    for (const testCase of GOLDEN_SET) {
      const result = await chatWithModel(model, testCase.id.replace(/^[a-z]+\d+$/, "คำถาม"), testCase.evidence);
      const grounded = testCase.evidence.length > 0 ?
        result.content.split("").filter((c: string) => testCase.evidence.join("").includes(c)).length > 0 : true;
      const unsupportedHandled = testCase.category === "unsupported" ? isUnsupportedClaimHandled(result.content) : null;
      const correctness = testCase.expectedContains ?
        testCase.expectedContains.every((k) => result.content.includes(k)) : (unsupportedHandled || result.success);

      results[model].push({
        id: testCase.id,
        category: testCase.category,
        success: result.success,
        correct: correctness,
        grounded: grounded,
        latency: result.latency,
        inputTokens: result.inputTokens,
        outputTokens: result.outputTokens,
        error: result.error,
      });
      console.log(`  [${testCase.id}] ${result.success ? "✓" : "✗"} correct=${correctness} ${result.latency}ms`);
    }
  }

  // Summary per model
  console.log("\n=== SUMMARY ===\n");
  for (const [model, cases] of Object.entries(results)) {
    const successful = cases.filter((c: any) => c.success);
    const correct = cases.filter((c: any) => c.correct);
    const latencies = cases.filter((c: any) => c.success).map((c: any) => c.latency);
    const totalTokens = cases.reduce((sum: number, c: any) => sum + c.inputTokens + c.outputTokens, 0);
    
    console.log(`\nModel: ${model}`);
    console.log(`  Successful: ${successful.length}/${cases.length}`);
    console.log(`  Correct: ${correct.length}/${cases.length}`);
    console.log(`  Latency: min=${Math.min(...latencies)}ms max=${Math.max(...latencies)}ms avg=${Math.round(latencies.reduce((a: number, b: number) => a + b, 0) / Math.max(1, latencies.length))}ms`);
    console.log(`  Total tokens: ${totalTokens}`);
    console.log(`  Cost per successful case: ${(totalTokens * 0.000001).toFixed(4)} THB`);
  }

  // Per-category comparison
  console.log("\n=== Per-Category Comparison ===\n");
  const categories = [...new Set(GOLDEN_SET.map((c) => c.category))];
  for (const cat of categories) {
    console.log(`\nCategory: ${cat}`);
    for (const [model, cases] of Object.entries(results)) {
      const inCat = cases.filter((c: any) => c.category === cat);
      const correctInCat = inCat.filter((c: any) => c.correct);
      console.log(`  ${model}: ${correctInCatCount(inCat)}/${inCat.length}`);
    }
  }
  
  function correctInCatCount(cases: any[]): number {
    return cases.filter((c: any) => c.correct).length;
  }

  // Save results
  const report = {
    timestamp: new Date().toISOString(),
    models: Object.fromEntries(Object.entries(results).map(([model, cases]) => [
      model,
      {
        cases: cases.length,
        successful: cases.filter((c: any) => c.success).length,
        correct: cases.filter((c: any) => c.correct).length,
        avgLatency: Math.round(cases.filter((c: any) => c.success).reduce((s: number, c: any) => s + c.latency, 0) / Math.max(1, cases.filter((c: any) => c.success).length)),
        totalTokens: cases.reduce((sum: number, c: any) => sum + c.inputTokens + c.outputTokens, 0),
        byCategory: Object.fromEntries([...new Set(cases.map((c: any) => c.category))].map((cat) => [
          cat,
          {
            total: cases.filter((c: any) => c.category === cat).length,
            correct: cases.filter((c: any) => c.category === cat && c.correct).length,
          }
        ])),
      },
    ])),
    cases: results,
  };
  
  await import("fs").then((fs) => {
    fs.writeFileSync(
      "/home/ubuntu/Projects/thai-car-intelligence/scripts/benchmark-results.json",
      JSON.stringify(report, null, 2)
    );
  });

  console.log("\nResults saved to scripts/benchmark-results.json");
}

main().catch(console.error);
