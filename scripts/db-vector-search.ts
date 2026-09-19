import "dotenv/config";
import pg from "pg";

async function getEmbedding(text: string): Promise<number[]> {
  const baseUrl = process.env.EMBEDDING_BASE_URL?.trim()!;
  const apiKey = process.env.EMBEDDING_API_KEY?.trim()!;
  const model = process.env.EMBEDDING_MODEL?.trim()!;
  const response = await fetch(`${baseUrl}/embeddings`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${apiKey}` },
    body: JSON.stringify({ model, input: text }),
  });
  const data = await response.json();
  return data.data?.[0]?.embedding || [];
}

async function main() {
  console.log("=== DB Vector Search Evaluation (30 queries) ===\n");
  
  const pool = new pg.Pool({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
    max: 10,
  });
  
  const researchCheck = await pool.query(`
    SELECT count(*) as count FROM "Embedding" e
    WHERE e.model = 'pplx-embed-v1-0.6b'
      AND NOT EXISTS (SELECT 1 FROM "SourceDocument" sd WHERE sd.id = e."sourceDocumentId" AND sd.status = 'VERIFIED')
  `);
  console.log(`Unverified embeddings in production index: ${researchCheck.rows[0].count} (should be 0)\n`);
  
  // 30 Thai evaluation queries. expect = entity keyword that correct evidence must contain; null = should stay unresolved (FP if resolved by wrong vehicle, ok if "no exact evidence" is qualified).
  const queries: Array<{ query: string; entity: string | null; mustContain?: string[] }> = [
    { query: "Honda City ราคาเท่าไหร่", entity: "honda city" },
    { query: "Honda Civic ราคาเท่าไหร่", entity: "honda civic" },
    { query: "MG4 Standard ราคาเท่าไหร่", entity: "mg4" },
    { query: "BYD Atto 3 ราคาเท่าไหร่", entity: "atto 3" },
    { query: "MG IM5 ราคาเท่าไหร่", entity: "mg im5" },
    { query: "Honda HR-V ราคาเท่าไหร่", entity: "honda hr-v" },
    { query: "MG4 แบตเตอรี่กี่ kWh", entity: "mg4", mustContain: ["51"] },
    { query: "MG IM5 แบตเตอรี่กี่ kWh", entity: "mg im5", mustContain: ["77"] },
    { query: "MG IM5 ชาร์จเร็วกี่ kW", entity: "mg im5", mustContain: ["150"] },
    { query: "MG4 ชาร์จ DC กี่ kW", entity: "mg4", mustContain: ["ชาร์จ"] },
    { query: "Honda Civic กำลังกี่แรงม้า", entity: "honda civic", mustContain: ["กำลัง"] },
    { query: "BYD Atto 3 ระยะทางวิ่งได้เท่าไหร่", entity: "atto 3", mustContain: ["310"] },
    { query: "Honda City ขนาดเท่าไหร่", entity: "honda city", mustContain: ["4589"] },
    { query: "Honda Civic ขนาดกี่mm", entity: "honda civic", mustContain: ["4674"] },
    { query: "MG4 ขนาดกี่mm", entity: "mg4", mustContain: ["4287"] },
    { query: "Honda City ประกันกี่ปี", entity: "honda city", mustContain: ["ประกัน"] },
    { query: "BYD Atto 3 ประกันกี่ปี", entity: "atto 3", mustContain: ["ประกัน", "8"] },
    { query: "ฮอนด้า ซิตี้ ราคา", entity: "honda city" },
    { query: "เอ็มจี โฟร์ แบตเตอรี่", entity: "mg4" },
    { query: "ราคารถไฟฟ้า Honda", entity: "honda" },
    { query: "เปรียบเทียบ Honda City กับ Civic", entity: "honda" },
    { query: "MG ZS EV ระยะทางวิ่งกี่ km", entity: "zs" },
    { query: "BYD Seal ประกันกี่ปี", entity: "seal" },
    { query: "MG S5 EV PLUS ราคาเท่าไหร่", entity: "s5" },
    { query: "Honda City Hatchback ราคาเท่าไหร่", entity: "hatchback" },
    { query: "Tesla Model Y ราคาเท่าไหร่", entity: null },          // no verified fact — retrieval may return wrong vehicle; acceptable only if qualified
    { query: "Toyota Camry ราคาเท่าไหร่", entity: null },
    { query: "รถไฟฟ้า MG มีรุ่นไหนบ้าง", entity: null },
    { query: "ซียูวี Honda ราคาถูกที่สุด", entity: null },
    { query: "MG IM6 แบตเตอรี่กี่ kWh", entity: "mg im6" },
  ];
  
  let top1 = 0, top3 = 0, noEvOk = 0, fp = 0, miss = 0;
  const embedL: number[] = [], searchL: number[] = [];
  
  for (const { query, entity, mustContain } of queries) {
    const embedStart = Date.now();
    const vector = await getEmbedding(query);
    embedL.push(Date.now() - embedStart);
    
    const searchStart = Date.now();
    const result = await pool.query(
      `SELECT e."entityId", e."content", e."vector" <=> $1::vector AS "distance"
       FROM "Embedding" e
       JOIN "SourceDocument" sd ON sd."id" = e."sourceDocumentId"
       WHERE e."vector" IS NOT NULL AND e."dimensions" = 1024 AND sd."status" = 'VERIFIED'
       ORDER BY e."vector" <=> $1::vector ASC LIMIT 3`,
      [JSON.stringify(vector)]
    );
    searchL.push(Date.now() - searchStart);
    
    if (result.rows.length === 0) {
      if (entity === null) { noEvOk++; console.log(`  [${query}] no evidence — OK`); }
      else { miss++; console.log(`  [${query}] MISS (no evidence)`); }
      continue;
    }
    
    // check top-1
    const top = result.rows[0].content.toLowerCase();
    let correct = entity ? top.includes(entity.toLowerCase()) : false;
    if (correct && mustContain) correct = mustContain.every((k) => top.includes(k.toLowerCase()));
    
    if (entity === null) {
      // Expected no exact evidence; returning some vehicle fact is a false positive unless flagged by gate
      fp++;
      console.log(`  [${query}] FP: retrieved "${result.rows[0].content.substring(0, 50)}" — should be qualified/no-exact-evidence`);
      continue;
    }
    if (correct) { top1++; console.log(`  [${query}] top-1 ✓`); continue; }
    const top3Ok = result.rows.some((r) => {
      const c = r.content.toLowerCase();
      return c.includes(entity.toLowerCase()) && (!mustContain || mustContain.every((k) => c.includes(k.toLowerCase())));
    });
    if (top3Ok) { top3++; console.log(`  [${query}] top-3 hit`); }
    else { miss++; console.log(`  [${query}] MISS`); }
  }
  
  console.log("\n=== Metrics ===");
  console.log(`Top-1 correct: ${top1}/30`);
  console.log(`Top-3 additional hits: ${top3}/30`);
  console.log(`Retrieval misses: ${miss}`);
  console.log(`False positives (should be qualified): ${fp}`);
  console.log(`No-evidence correct: ${noEvOk}`);
  console.log(`Embedding latency: avg=${Math.round(embedL.reduce((a, b) => a + b, 0) / embedL.length)}ms min=${Math.min(...embedL)}ms max=${Math.max(...embedL)}ms`);
  console.log(`Vector search latency: avg=${Math.round(searchL.reduce((a, b) => a + b, 0) / searchL.length)}ms min=${Math.min(...searchL)}ms max=${Math.max(...searchL)}ms`);
  
  await pool.end();
}

main().catch(console.error);
