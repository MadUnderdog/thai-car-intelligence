import "dotenv/config";
import pg from "pg";

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
  console.log("=== DB Vector Search Test ===\n");
  
  const pool = new pg.Pool({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
    max: 10,
  });
  
  const queries = [
    { query: "Honda City ราคาเท่าไหร่", expected: "honda-city-ehev" },
    { query: "MG4 แบตเตอรี่กี่ kWh", expected: "mg4-standard" },
    { query: "Honda Civic กำลังกี่แรงม้า", expected: "honda-civic-ehev" },
    { query: "BYD Atto 3 ระยะทางวิ่งได้เท่าไหร่", expected: "byd-atto3" },
    { query: "MG IM5 ชาร์จเร็วกี่ kW", expected: "mg-im5-ev" },
  ];
  
  let passed = 0;
  let failed = 0;
  
  for (const { query, expected } of queries) {
    console.log(`Query: "${query}"`);
    
    // Get query embedding
    const vector = await getEmbedding(query);
    
    // Search in database
    const result = await pool.query(
      `SELECT e."entityId", e."content", e."vector" <=> $1::vector AS "distance"
       FROM "Embedding" e
       JOIN "SourceDocument" sd ON sd."id" = e."sourceDocumentId"
       WHERE e."vector" IS NOT NULL AND e."dimensions" = 1024
         AND sd."status" = 'VERIFIED'
       ORDER BY e."vector" <=> $1::vector ASC
       LIMIT 3`,
      [JSON.stringify(vector)]
    );
    
    if (result.rows.length > 0) {
      const top = result.rows[0];
      console.log(`  Top result: ${top.entityId} (distance: ${parseFloat(top.distance).toFixed(4)})`);
      console.log(`  Content: ${top.content.substring(0, 80)}...`);
      console.log(`  Expected: ${expected}`);
      
      if (top.entityId === expected) {
        console.log("  PASS\n");
        passed++;
      } else {
        console.log("  FAIL\n");
        failed++;
      }
    } else {
      console.log("  No results\n");
      failed++;
    }
  }
  
  console.log(`Results: ${passed}/${passed + failed} passed`);
  
  await pool.end();
}

main().catch(console.error);
