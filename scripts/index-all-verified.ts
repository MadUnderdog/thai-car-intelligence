import "dotenv/config";
import pg from "pg";
import { collectVerifiedFacts, indexVerifiedFacts } from "../lib/catalog/verified-evidence-indexer";

async function getEmbedding(text: string): Promise<number[]> {
  const baseUrl = process.env.EMBEDDING_BASE_URL?.trim()!;
  const apiKey = process.env.EMBEDDING_API_KEY?.trim()!;
  const model = process.env.EMBEDDING_MODEL?.trim()!;
  
  const response = await fetch(`${baseUrl}/embeddings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ model, input: text }),
  });
  
  const data = await response.json();
  return data.data?.[0]?.embedding || [];
}

async function main() {
  console.log("=== Production Evidence Index Expansion ===\n");
  
  const pool = new pg.Pool({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
    max: 10,
  });
  
  // Snapshot current state
  const before = await pool.query(`SELECT count(*) as count FROM "Embedding" WHERE model = 'pplx-embed-v1-0.6b'`);
  console.log(`Current embeddings: ${before.rows[0].count}`);
  
  // Collect all verified facts
  console.log("\nCollecting verified facts...");
  const facts = await collectVerifiedFacts(pool);
  console.log(`Found ${facts.length} verified facts to index`);
  
  // Breakdown by type
  const byType: Record<string, number> = {};
  for (const f of facts) {
    byType[f.entityType] = (byType[f.entityType] || 0) + 1;
  }
  console.log("By type:", byType);
  
  // Index facts
  console.log("\nIndexing facts...");
  const result = await indexVerifiedFacts(pool, facts, getEmbedding);
  
  console.log(`\nResults:`);
  console.log(`  Indexed: ${result.indexed}`);
  console.log(`  Skipped: ${result.skipped}`);
  console.log(`  Errors: ${result.errors}`);
  
  // Verify final state
  const after = await pool.query(`SELECT count(*) as count FROM "Embedding" WHERE model = 'pplx-embed-v1-0.6b'`);
  console.log(`\nFinal embeddings: ${after.rows[0].count}`);
  
  // Test idempotency
  console.log("\nTesting idempotency (re-run)...");
  const result2 = await indexVerifiedFacts(pool, facts, getEmbedding);
  console.log(`  Indexed: ${result2.indexed} (should be 0)`);
  console.log(`  Skipped: ${result2.skipped} (should be ${facts.length})`);
  
  await pool.end();
}

main().catch(console.error);
