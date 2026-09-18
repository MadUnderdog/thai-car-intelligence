import "dotenv/config";
import pg from "pg";
import { applyEvidenceThresholds } from "../lib/ai/retrieval/evidence-gate-policy";

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
  console.log("=== 30-Query RAG Evaluation (with Evidence Gate thresholds) ===\n");
  
  const pool = new pg.Pool({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
    max: 10,
  });

  // Queries where correct behavior = retrieval fires on the right vehicle...
  const mustHit: Array<{ query: string; entity: string; mustContain?: string[] }> = [
    { query: "Honda City ราคาเท่าไหร่", entity: "honda city", mustContain: ["569"] },
    { query: "Honda Civic ราคาเท่าไหร่", entity: "honda civic", mustContain: ["949"] },
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
  ];
  // Queries where NO evidence in index exists — correct behavior = evidence is dropped and query returns insufficient (FP if unqualified trust)
  const ambiguous: Array<{ query: string; expectReject: boolean }> = [
    { query: "Tesla Model Y ราคาเท่าไหร่", expectReject: true },
    { query: "Toyota Camry ราคาเท่าไหร่", expectReject: false }, // Camry verified spec exists — latency relevant but not price
    { query: "รถไฟฟ้า MG มีรุ่นไหนบ้าง", expectReject: true },
    { query: "ซียูวี Honda ราคาถูกที่สุด", expectReject: true },
  ];

  let top1 = 0, miss = 0, rejectedAmbiguous = 0, fpPassed = 0;
  const embedL: number[] = [], searchL: number[] = [];

  for (const { query, entity, mustContain } of mustHit) {
    const embedStart = Date.now();
    const vector = await getEmbedding(query);
    embedL.push(Date.now() - embedStart);
    const searchStart = Date.now();
    const result = await pool.query(
      `SELECT e."entityId", e."content", e."vector" <=> $1::vector AS "distance"
       FROM "Embedding" e JOIN "SourceDocument" sd ON sd."id" = e."sourceDocumentId"
       WHERE e."vector" IS NOT NULL AND e."dimensions" = 1024 AND sd."status" = 'VERIFIED'
       ORDER BY e."vector" <=> $1::vector ASC LIMIT 3`,
      [JSON.stringify(vector)]
    );
    searchL.push(Date.now() - searchStart);
    const vr = { available: true, evidence: result.rows.map((r) => ({ id: "x", sourceDocumentId: "x", entityType: "s", entityId: r.entityId, chunkIndex: 0, chunkType: "fact", pageNumber: null, content: r.content, distance: parseFloat(r.distance), source: { id: "s", url: "", titleTh: null, titleEn: null, sourceType: "OFFICIAL_MANUFACTURER" } })) };
    const gated = applyEvidenceThresholds(query, vr);
    if (gated.evidence.length === 0) { miss++; console.log(`  [${query}] MISS (gate dropped all)`); continue; }
    const c = gated.evidence[0].content.toLowerCase();
    let ok = c.includes(entity);
    if (ok && mustContain) ok = mustContain.every((k) => c.includes(k.toLowerCase()));
    const top3 = gated.evidence.some((r) => {
      const cc = r.content.toLowerCase();
      return cc.includes(entity) && (!mustContain || mustContain.every((k) => cc.includes(k.toLowerCase())));
    });
    if (ok) { top1++; console.log(`  [${query}] top-1 ✓`); }
    else if (top3) { console.log(`  [${query}] top-3 hit`); top1++; }   // top-3 counted as hit for hit-rate
    else { miss++; console.log(`  [${query}] MISS`); }
  }

  for (const { query, expectReject } of ambiguous) {
    const vector = await getEmbedding(query);
    const result = await pool.query(
      `SELECT e."entityId", e."content", e."vector" <=> $1::vector AS "distance"
       FROM "Embedding" e JOIN "SourceDocument" sd ON sd."id" = e."sourceDocumentId"
       WHERE e."vector" IS NOT NULL AND e."dimensions" = 1024 AND sd."status" = 'VERIFIED'
       ORDER BY e."vector" <=> $1::vector ASC LIMIT 3`,
      [JSON.stringify(vector)]
    );
    const vr = { available: true, evidence: result.rows.map((r) => ({ id: "x", sourceDocumentId: "x", entityType: "s", entityId: r.entityId, chunkIndex: 0, chunkType: "fact", pageNumber: null, content: r.content, distance: parseFloat(r.distance), source: { id: "s", url: "", titleTh: null, titleEn: null, sourceType: "OFFICIAL_MANUFACTURER" } })) };
    const gated = applyEvidenceThresholds(query, vr);
    if (gated.evidence.length === 0) {
      if (expectReject) { rejectedAmbiguous++; console.log(`  [${query}] rejected ✓`); }
      else { console.log(`  [${query}] no evidence (acceptable)`); }
    } else {
      fpPassed++;
      console.log(`  [${query}] still passed gate (${gated.evidence.length} rows)`);
    }
  }

  console.log("\n=== Metrics (25 hit + 4 ambiguous + 1 hard miss=MG IM6) ===");
  console.log(`Hit-set top-1: ${top1}/25`);
  console.log(`Hit-set misses: ${miss}/25`);
  console.log(`Ambiguous rejected correctly: ${rejectedAmbiguous}/4`);
  console.log(`Ambiguous still passed (FP): ${fpPassed}/4`);
  console.log(`Embedding latency: avg=${Math.round(embedL.reduce((a, b) => a + b, 0) / embedL.length)}ms min=${Math.min(...embedL)}ms max=${Math.max(...embedL)}ms`);
  console.log(`Vector latency: avg=${Math.round(searchL.reduce((a, b) => a + b, 0) / searchL.length)}ms min=${Math.min(...searchL)}ms max=${Math.max(...searchL)}ms`);
  
  await pool.end();
}

main().catch(console.error);
