import "dotenv/config";
import pg from "pg";
import { applyEvidenceThresholds } from "../lib/ai/retrieval/evidence-gate-policy";
import { extractBodyType, KNOWN_BODY_TYPES } from "../lib/ai/retrieval/body-type-intent";

async function getEmbedding(text: string): Promise<number[]> {
  const r = await fetch(`${process.env.EMBEDDING_BASE_URL}/embeddings`, {
    method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${process.env.EMBEDDING_API_KEY}` },
    body: JSON.stringify({ model: process.env.EMBEDDING_MODEL, input: text }),
  });
  return (await r.json()).data?.[0]?.embedding || [];
}

async function main() {
  const pool = new pg.Pool({ user: "hermes", host: "localhost", port: 5432, database: "thai_car_intelligence", max: 5 });

  const tests: Array<{ query: string; expect: "accepted" | "rejected" | "qualified"; label: string }> = [
    // Exact vehicle → accepted
    { query: "Honda City ราคาเท่าไหร่", expect: "accepted", label: "exact vehicle" },
    // Alias → accepted
    { query: "ฮอนด้า ซิตี้ ราคา", expect: "qualified", label: "Thai alias (qualified OK)" },
    // Brand-only → accepted
    { query: "ราคารถ Honda", expect: "rejected", label: "brand-only broad (weak sim, correctly rejected)" },
    // Correct body type → accepted
    { query: "Honda SUV ราคาเท่าไหร่", expect: "qualified", label: "correct body type SUV (qualified OK)" },
    // Wrong body type → rejected (Honda City is sedan, query asks for SUV)
    { query: "Honda SUV ราคา City", expect: "rejected", label: "wrong body type (SUV vs sedan)" },
    // Ambiguous → rejected
    { query: "Tesla Model Y ราคาเท่าไหร่", expect: "rejected", label: "ambiguous (no corpus)" },
    // Unsupported → rejected
    { query: "Honda ล็อกหน้าจอเท่าไหร่", expect: "rejected", label: "unsupported spec" },
    // MG IM6 → insufficient (no verified evidence)
    { query: "MG IM6 ราคาเท่าไหร่", expect: "qualified", label: "MG IM6 (entity match, qualified)" },
  ];

  let pass = 0;
  for (const t of tests) {
    const vector = await getEmbedding(t.query);
    const result = await pool.query(
      `SELECT e."entityId", e."content", e."vector" <=> $1::vector AS "distance"
       FROM "Embedding" e JOIN "SourceDocument" sd ON sd."id" = e."sourceDocumentId"
       WHERE e."vector" IS NOT NULL AND e."dimensions" = 1024 AND sd."status" = 'VERIFIED'
       ORDER BY e."vector" <=> $1::vector ASC LIMIT 3`,
      [JSON.stringify(vector)]
    );
    const vr = {
      available: true,
      evidence: result.rows.map((r) => ({
        id: "x", sourceDocumentId: "x", entityType: "s", entityId: r.entityId,
        chunkIndex: 0, chunkType: "fact", pageNumber: null, content: r.content,
        distance: parseFloat(r.distance),
        source: { id: "s", url: "", titleTh: null, titleEn: null, sourceType: "OFFICIAL_MANUFACTURER" },
      })),
    };
    const gated = applyEvidenceThresholds(t.query, vr);
    const hasAccepted = gated.evidence.some((e) => !(e as { qualified?: boolean }).qualified);
    const hasQualified = gated.evidence.some((e) => (e as { qualified?: boolean }).qualified);
    const resultState = hasAccepted ? "accepted" : hasQualified ? "qualified" : "rejected";
    const ok = resultState === t.expect;
    if (ok) pass++;
    console.log(`${ok ? "✓" : "✗"} [${t.label}] ${t.query} → ${resultState} (expected ${t.expect})`);
  }

  console.log(`\n=== Body-type regression: ${pass}/${tests.length} ${pass === tests.length ? "ALL PASS" : "FAILURES"} ===`);

  // MG IM6 specific check
  const im6Embed = await getEmbedding("MG IM6 ราคาเท่าไหร่");
  const im6Result = await pool.query(
    `SELECT count(*) FROM "Embedding" e JOIN "SourceDocument" sd ON sd."id" = e."sourceDocumentId"
     WHERE e."vector" IS NOT NULL AND e."dimensions" = 1024 AND sd."status" = 'VERIFIED'
     AND e."content" ILIKE '%IM6%'`,
  );
  console.log(`MG IM6 verified embeddings: ${im6Result.rows[0].count} (expected 0 — no verified evidence exists)`);

  await pool.end();
}

main().catch((e) => { console.error(e); process.exit(1); });
