import "dotenv/config";
import pg from "pg";
import { applyEvidenceThresholds, VECTOR_STRICT_DISTANCE } from "../lib/ai/retrieval/evidence-gate-policy";

async function getEmbedding(text: string): Promise<number[]> {
  const baseUrl = process.env.EMBEDDING_BASE_URL?.trim()!;
  const apiKey = process.env.EMBEDDING_API_KEY?.trim()!;
  const model = process.env.EMBEDDING_MODEL?.trim()!;
  const response = await fetch(`${baseUrl}/embeddings`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({ model, input: text }),
  });
  const data = await response.json();
  return data.data?.[0]?.embedding || [];
}

function makeEvidence(rows: Array<{ content: string; distance: number; entityId: string }>) {
  return {
    available: true,
    evidence: rows.map((r) => ({
      id: "x", sourceDocumentId: "x", entityType: "s", entityId: r.entityId,
      chunkIndex: 0, chunkType: "fact", pageNumber: null, content: r.content, distance: r.distance,
      source: { id: "s", url: "", titleTh: null, titleEn: null, sourceType: "OFFICIAL_MANUFACTURER" },
    })),
  };
}

/** Full gate + qualification decision for a query against live DB, deterministic. */
async function gateQuery(pool: pg.Pool, query: string) {
  const vector = await getEmbedding(query);
  const result = await pool.query(
    `SELECT e."entityId", e."content", e."vector" <=> $1::vector AS "distance"
     FROM "Embedding" e JOIN "SourceDocument" sd ON sd."id" = e."sourceDocumentId"
     WHERE e."vector" IS NOT NULL AND e."dimensions" = 1024 AND sd."status" = 'VERIFIED'
     ORDER BY e."vector" <=> $1::vector ASC LIMIT 3`,
    [JSON.stringify(vector)]
  );
  const vr = makeEvidence(result.rows.map((r) => ({ content: r.content, distance: parseFloat(r.distance), entityId: r.entityId })));
  const gated = applyEvidenceThresholds(query, vr);
  const confident = gated.evidence.filter((e) => !(e as { qualified?: boolean }).qualified);
  return { gated, confident };
}

async function main() {
  const pool = new pg.Pool({ user: "hermes", host: "localhost", port: 5432, database: "thai_car_intelligence", max: 5 });
  console.log(`vector strict threshold: ${VECTOR_STRICT_DISTANCE}\n`);

  // CASE 1: ambiguous query → explicit no/insufficient evidence
  const t1 = await gateQuery(pool, "Tesla Model Y ราคาเท่าไหร่");
  console.log(`CASE 1 ambiguous (Tesla Model Y ราคา): confident=${t1.confident.length} → ${t1.confident.length === 0 ? "PASS: insufficient-evidence path" : "FAIL"}`);

  // CASE 2: wrong vehicle nearest neighbor → rejected
  const t2 = await gateQuery(pool, "Nissan Leaf ราคาเท่าไหร่");
  console.log(`CASE 2 wrong-vehicle NN (Nissan Leaf ราคา): confident=${t2.confident.length} → ${t2.confident.length === 0 ? "PASS: rejected" : "FAIL"}`);

  // CASE 3: exact vehicle → accepted
  const t3 = await gateQuery(pool, "Honda City ราคาเท่าไหร่");
  const t3ok = t3.confident.some((e) => e.content.includes("City") && e.content.includes("569"));
  console.log(`CASE 3 exact vehicle (Honda City ราคา): confident=${t3.confident.length}, correct content=${t3ok} → ${t3ok ? "PASS: accepted" : "FAIL"}`);

  // CASE 4: alias → accepted (entity-corroborated; may be qualified, never dropped)
  const t4 = await gateQuery(pool, "ฮอนด้า ซิตี้ ราคา");
  const t4ok = t4.gated.evidence.some((e) => e.content.includes("City"));
  console.log(`CASE 4 alias (ฮอนด้า ซิตี้ ราคา): gated=${t4.gated.evidence.length}, correct content=${t4ok} → ${t4ok ? "PASS: accepted (alias corroborated)" : "FAIL"}`);

  // CASE 5: unsupported spec → blocked
  const t5 = await gateQuery(pool, "Honda City ล็อกหน้าจอเท่าไหร่");
  console.log(`CASE 5 unsupported spec (Honda City ล็อกหน้าจอ): confident=${t5.confident.length} → ${t5.confident.length === 0 ? "PASS: blocked" : "FAIL"}`);

  // CASE 6: conflict evidence → qualified answer (both rows exist, gate passes both)
  const t6 = await gateQuery(pool, "MG3 ราคาเท่าไหร่");
  console.log(`CASE 6 conflict (MG3 ราคา): confident=${t6.confident.length} → ${t6.confident.length > 0 ? "PASS: evidence routed to qualified answer" : "FAIL (over-blocked)"}`);

  const results = { t1: t1.confident.length === 0, t2: t2.confident.length === 0, t3: t3ok, t4: t4ok, t5: t5.confident.length === 0, t6: t6.confident.length > 0 };  const passCount = Object.values(results).filter(Boolean).length;
  console.log(`\n=== Gate regression: ${passCount}/6 ${passCount === 6 ? "ALL PASS" : "FAILURES PRESENT"} ===`);
  await pool.end();
}

main().catch((e) => { console.error(e); process.exit(1); });
