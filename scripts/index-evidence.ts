import "dotenv/config";
import pg from "pg";
import crypto from "crypto";

function contentHash(text: string): string {
  return crypto.createHash("sha256").update(text).digest("hex").substring(0, 16);
}

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
  console.log("=== Production Vector Index ===\n");
  
  const pool = new pg.Pool({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
    max: 10,
  });
  
  // Controlled corpus of verified automotive facts
  const corpus = [
    { entityType: "price", entityId: "honda-city-ehev", chunkIndex: 0, content: "Honda City e:HEV ราคา 569,000 บาท กำลัง 109 แรงม้า", sourceUrl: "https://www.honda.co.th/city" },
    { entityType: "price", entityId: "honda-civic-ehev", chunkIndex: 0, content: "Honda Civic e:HEV ราคา 949,000 บาท กำลัง 141 แรงม้า", sourceUrl: "https://www.honda.co.th/civic" },
    { entityType: "price", entityId: "honda-hrv-ehev", chunkIndex: 0, content: "Honda HR-V e:HEV ราคา 899,000 บาท กำลัง 131 แรงม้า", sourceUrl: "https://www.honda.co.th/hr-v" },
    { entityType: "price", entityId: "mg4-standard", chunkIndex: 0, content: "MG4 Standard ราคา 699,900 บาท แบตเตอรี่ 51 kWh ระยะทาง 350 km", sourceUrl: "https://www.mgcars.com/th/mg4" },
    { entityType: "price", entityId: "mg-im5-ev", chunkIndex: 0, content: "MG IM5 EV ราคา 1,549,900 บาท แบตเตอรี่ 77 kWh ชาร์จ DC 150 kW", sourceUrl: "https://www.mgcars.com/th/mg-im5" },
    { entityType: "price", entityId: "byd-atto3", chunkIndex: 0, content: "BYD Atto 3 ราคา 669,900 บาท แบตเตอรี่ 49.9 kWh ระยะทาง 310 km", sourceUrl: "https://www.byd.com/th" },
    { entityType: "spec", entityId: "honda-city-spec", chunkIndex: 1, content: "Honda City e:HEV ขนาด 4589x1748x1467 mm ฐานล้อ 2610 mm ระยะต่ำสุด 135 mm", sourceUrl: "https://www.honda.co.th/city" },
    { entityType: "spec", entityId: "honda-civic-spec", chunkIndex: 1, content: "Honda Civic e:HEV ขนาด 4674x1802x1415 mm ฐานล้อ 2735 mm ระยะต่ำสุด 135 mm", sourceUrl: "https://www.honda.co.th/civic" },
    { entityType: "spec", entityId: "mg4-spec", chunkIndex: 1, content: "MG4 Standard ขนาด 4287x1836x1516 mm ระยะต่ำสุด 150 mm", sourceUrl: "https://www.mgcars.com/th/mg4" },
    { entityType: "warranty", entityId: "honda-city-warranty", chunkIndex: 2, content: "Honda City e:HEV ประกัน 5 ปี 150,000 km", sourceUrl: "https://www.honda.co.th/city" },
  ];
  
  let indexed = 0;
  let skipped = 0;
  
  for (const item of corpus) {
    try {
      // Get or create source document
      const sourceResult = await pool.query(
        `SELECT id FROM "SourceDocument" WHERE url = $1 LIMIT 1`,
        [item.sourceUrl]
      );
      
      let sourceDocId: string;
      if (sourceResult.rows.length > 0) {
        sourceDocId = sourceResult.rows[0].id;
      } else {
        // Create a new source document
        const sourceId = await pool.query(`SELECT id FROM "Source" LIMIT 1`);
        if (sourceId.rows.length === 0) {
          console.log("  ERROR: No sources in database");
          continue;
        }
        const newDoc = await pool.query(
          `INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
           VALUES (gen_random_uuid(), $1, $2, $2, $3, $3, 'text/html', 'th', $4, NOW(), 'evidence', 'VERIFIED', 'UNKNOWN', 'SUCCEEDED', NOW(), NOW())
           RETURNING id`,
          [sourceId.rows[0].id, item.sourceUrl, item.entityId, contentHash(item.content)]
        );
        sourceDocId = newDoc.rows[0].id;
      }
      
      // Check if embedding already exists
      const existing = await pool.query(
        `SELECT id FROM "Embedding" WHERE "sourceDocumentId" = $1 AND "chunkIndex" = $2 AND model = 'pplx-embed-v1-0.6b'`,
        [sourceDocId, item.chunkIndex]
      );
      
      if (existing.rows.length > 0) {
        skipped++;
        continue;
      }
      
      // Generate embedding
      const vector = await getEmbedding(item.content);
      
      // Insert embedding
      await pool.query(
        `INSERT INTO "Embedding" ("id", "sourceDocumentId", "entityType", "entityId", "chunkIndex", "chunkType", "content", "contentHash", "model", "dimensions", "vector", "createdAt")
         VALUES (gen_random_uuid(), $1, $2, $3, $4, 'fact', $5, $6, 'pplx-embed-v1-0.6b', 1024, $7::vector, NOW())`,
        [sourceDocId, item.entityType, item.entityId, item.chunkIndex, item.content, contentHash(item.content), JSON.stringify(vector)]
      );
      
      indexed++;
      console.log(`  Indexed: ${item.entityId}`);
    } catch (e: any) {
      console.log(`  Error indexing ${item.entityId}: ${e.message}`);
    }
  }
  
  console.log(`\nResults: ${indexed} indexed, ${skipped} skipped`);
  
  // Verify count
  const count = await pool.query(`SELECT count(*) as count FROM "Embedding" WHERE model = 'pplx-embed-v1-0.6b'`);
  console.log(`Total embeddings in DB: ${count.rows[0].count}`);
  
  await pool.end();
}

main().catch(console.error);
