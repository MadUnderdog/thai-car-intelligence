import pg from "pg";
import crypto from "crypto";

function contentHash(text: string): string {
  return crypto.createHash("sha256").update(text).digest("hex").substring(0, 16);
}

function entityIdToChunkIndex(entityId: string): number {
  // Convert entity ID to a numeric chunk index using hex decoding
  const hash = crypto.createHash("md5").update(entityId).digest("hex");
  return parseInt(hash.substring(0, 8), 16) % 1000;
}

export type IndexedFact = {
  entityType: string;
  entityId: string;
  variantId: string;
  content: string;
  sourceUrl: string;
  sourceTier: string;
  verified: boolean;
};

/**
 * Index verified facts into pgvector embeddings table.
 * Uses entityId hash as unique chunk identifier.
 */
export async function indexVerifiedFacts(
  pool: pg.Pool,
  facts: IndexedFact[],
  embedFn: (text: string) => Promise<number[]>
): Promise<{ indexed: number; skipped: number; errors: number }> {
  let indexed = 0;
  let skipped = 0;
  let errors = 0;

  for (const fact of facts) {
    try {
      // Get or create source document
      const sourceResult = await pool.query(
        `SELECT id FROM "SourceDocument" WHERE url = $1 AND status = 'VERIFIED' LIMIT 1`,
        [fact.sourceUrl]
      );

      let sourceDocId: string;
      if (sourceResult.rows.length > 0) {
        sourceDocId = sourceResult.rows[0].id;
      } else {
        // Get any verified source
        const sourceId = await pool.query(`SELECT id FROM "Source" WHERE status = 'ACTIVE' LIMIT 1`);
        if (sourceId.rows.length === 0) {
          console.log(`  SKIP: No active sources`);
          skipped++;
          continue;
        }
        const newDoc = await pool.query(
          `INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
           VALUES (gen_random_uuid(), $1, $2, $2, $3, $3, 'text/html', 'th', $4, NOW(), 'verified_evidence', 'VERIFIED', 'UNKNOWN', 'SUCCEEDED', NOW(), NOW())
           RETURNING id`,
          [sourceId.rows[0].id, fact.sourceUrl, fact.entityId, contentHash(fact.content)]
        );
        sourceDocId = newDoc.rows[0].id;
      }

      // Use entityId hash as chunk index
      const chunkIndex = entityIdToChunkIndex(fact.entityId);

      // Check if embedding already exists with same content hash
      const factHash = contentHash(fact.content);
      const existing = await pool.query(
        `SELECT id, "contentHash" FROM "Embedding" WHERE "sourceDocumentId" = $1 AND "chunkIndex" = $2 AND model = 'pplx-embed-v1-0.6b'`,
        [sourceDocId, chunkIndex]
      );

      if (existing.rows.length > 0 && existing.rows[0].contentHash === factHash) {
        skipped++;
        continue;
      }

      // Generate embedding
      const vector = await embedFn(fact.content);

      // Insert or update embedding
      if (existing.rows.length > 0) {
        await pool.query(
          `UPDATE "Embedding" SET "content" = $1, "contentHash" = $2, "vector" = $3::vector, "entityType" = $4, "entityId" = $5 WHERE id = $6`,
          [fact.content, factHash, JSON.stringify(vector), fact.entityType, fact.entityId, existing.rows[0].id]
        );
      } else {
        await pool.query(
          `INSERT INTO "Embedding" ("id", "sourceDocumentId", "entityType", "entityId", "chunkIndex", "chunkType", "content", "contentHash", "model", "dimensions", "vector", "createdAt")
           VALUES (gen_random_uuid(), $1, $2, $3, $4, 'fact', $5, $6, 'pplx-embed-v1-0.6b', 1024, $7::vector, NOW())`,
          [sourceDocId, fact.entityType, fact.entityId, chunkIndex, fact.content, factHash, JSON.stringify(vector)]
        );
      }

      indexed++;
    } catch (e: any) {
      console.log(`  ERROR: ${fact.entityId}: ${e.message}`);
      errors++;
    }
  }

  return { indexed, skipped, errors };
}

/**
 * Collect all verified facts from canonical tables for indexing.
 */
export async function collectVerifiedFacts(pool: pg.Pool): Promise<IndexedFact[]> {
  const facts: IndexedFact[] = [];

  // 1. Verified prices
  const prices = await pool.query(`
    SELECT p.id as price_id, v.id as variant_id, v."nameEn" as variant_name,
           m."nameEn" as model_name, mf."nameEn" as manufacturer_name,
           p.amount, sd."canonicalUrl" as source_url
    FROM "Price" p
    JOIN "Variant" v ON v.id = p."variantId"
    JOIN "CarModel" m ON m.id = v."modelId"
    JOIN "Manufacturer" mf ON mf.id = m."manufacturerId"
    LEFT JOIN "SourceDocument" sd ON sd.id = p."sourceDocumentId"
    WHERE p."isCurrent" = true AND p."sourceDocumentId" IS NOT NULL
  `);

  for (const row of prices.rows) {
    facts.push({
      entityType: "price",
      entityId: `price:${row.price_id}`,
      variantId: row.variant_id,
      content: `${row.manufacturer_name} ${row.model_name} ${row.variant_name} ราคา ${row.amount.toLocaleString()} บาท`,
      sourceUrl: row.source_url || "",
      sourceTier: "verified",
      verified: true,
    });
  }

  // 2. PerformanceSpec
  const perfSpecs = await pool.query(`
    SELECT ps.id, ps."variantId", v."nameEn" as variant_name,
           m."nameEn" as model_name, mf."nameEn" as manufacturer_name,
           ps."powerKw", ps."torqueNm", ps."rangeKm", ps."sourceUrl"
    FROM "PerformanceSpec" ps
    JOIN "Variant" v ON v.id = ps."variantId"
    JOIN "CarModel" m ON m.id = v."modelId"
    JOIN "Manufacturer" mf ON mf.id = m."manufacturerId"
    WHERE ps."sourceUrl" IS NOT NULL
  `);

  for (const row of perfSpecs.rows) {
    const specs = [];
    if (row.powerKw) specs.push(`กำลัง ${row.powerKw} kW`);
    if (row.torqueNm) specs.push(`แรงบิด ${row.torqueNm} Nm`);
    if (row.rangeKm) specs.push(`ระยะทาง ${row.rangeKm} km`);
    if (specs.length > 0) {
      facts.push({
        entityType: "spec", entityId: `perf:${row.id}`, variantId: row.variantId,
        content: `${row.manufacturer_name} ${row.model_name} ${row.variant_name} ${specs.join(" ")}`,
        sourceUrl: row.sourceUrl || "", sourceTier: "verified", verified: true,
      });
    }
  }

  // 3. BatterySpec
  const battSpecs = await pool.query(`
    SELECT bs.id, bs."variantId", v."nameEn" as variant_name,
           m."nameEn" as model_name, mf."nameEn" as manufacturer_name,
           bs."capacityKwh", bs."chemistry", bs."sourceUrl"
    FROM "BatterySpec" bs
    JOIN "Variant" v ON v.id = bs."variantId"
    JOIN "CarModel" m ON m.id = v."modelId"
    JOIN "Manufacturer" mf ON mf.id = m."manufacturerId"
    WHERE bs."sourceUrl" IS NOT NULL
  `);

  for (const row of battSpecs.rows) {
    const specs = [];
    if (row.capacityKwh) specs.push(`แบตเตอรี่ ${row.capacityKwh} kWh`);
    if (row.chemistry) specs.push(`ประเภท ${row.chemistry}`);
    if (specs.length > 0) {
      facts.push({
        entityType: "spec", entityId: `batt:${row.id}`, variantId: row.variantId,
        content: `${row.manufacturer_name} ${row.model_name} ${row.variant_name} ${specs.join(" ")}`,
        sourceUrl: row.sourceUrl || "", sourceTier: "verified", verified: true,
      });
    }
  }

  // 4. DimensionsSpec
  const dimSpecs = await pool.query(`
    SELECT ds.id, ds."variantId", v."nameEn" as variant_name,
           m."nameEn" as model_name, mf."nameEn" as manufacturer_name,
           ds."lengthMm", ds."widthMm", ds."heightMm", ds."wheelbaseMm", ds."groundClearanceMm", ds."sourceUrl"
    FROM "DimensionsSpec" ds
    JOIN "Variant" v ON v.id = ds."variantId"
    JOIN "CarModel" m ON m.id = v."modelId"
    JOIN "Manufacturer" mf ON mf.id = m."manufacturerId"
    WHERE ds."sourceUrl" IS NOT NULL
  `);

  for (const row of dimSpecs.rows) {
    const specs = [];
    if (row.lengthMm && row.widthMm && row.heightMm) specs.push(`ขนาด ${row.lengthMm}x${row.widthMm}x${row.heightMm} mm`);
    if (row.wheelbaseMm) specs.push(`ฐานล้อ ${row.wheelbaseMm} mm`);
    if (row.groundClearanceMm) specs.push(`ระยะต่ำสุด ${row.groundClearanceMm} mm`);
    if (specs.length > 0) {
      facts.push({
        entityType: "spec", entityId: `dim:${row.id}`, variantId: row.variantId,
        content: `${row.manufacturer_name} ${row.model_name} ${row.variant_name} ${specs.join(" ")}`,
        sourceUrl: row.sourceUrl || "", sourceTier: "verified", verified: true,
      });
    }
  }

  // 5. WarrantySpec
  const warSpecs = await pool.query(`
    SELECT ws.id, ws."variantId", v."nameEn" as variant_name,
           m."nameEn" as model_name, mf."nameEn" as manufacturer_name,
           ws."vehicleYears", ws."vehicleDistanceKm", ws."sourceUrl"
    FROM "WarrantySpec" ws
    JOIN "Variant" v ON v.id = ws."variantId"
    JOIN "CarModel" m ON m.id = v."modelId"
    JOIN "Manufacturer" mf ON mf.id = m."manufacturerId"
    WHERE ws."sourceUrl" IS NOT NULL
  `);

  for (const row of warSpecs.rows) {
    const specs = [];
    if (row.vehicleYears) specs.push(`ประกัน ${row.vehicleYears} ปี`);
    if (row.vehicleDistanceKm) specs.push(`${row.vehicleDistanceKm.toLocaleString()} km`);
    if (specs.length > 0) {
      facts.push({
        entityType: "warranty", entityId: `warranty:${row.id}`, variantId: row.variantId,
        content: `${row.manufacturer_name} ${row.model_name} ${row.variant_name} ${specs.join(" ")}`,
        sourceUrl: row.sourceUrl || "", sourceTier: "verified", verified: true,
      });
    }
  }

  // 6. ChargingSpec
  const chgSpecs = await pool.query(`
    SELECT cs.id, cs."variantId", v."nameEn" as variant_name,
           m."nameEn" as model_name, mf."nameEn" as manufacturer_name,
           cs."dcPowerKw", cs."acPowerKw", cs."sourceUrl"
    FROM "ChargingSpec" cs
    JOIN "Variant" v ON v.id = cs."variantId"
    JOIN "CarModel" m ON m.id = v."modelId"
    JOIN "Manufacturer" mf ON mf.id = m."manufacturerId"
    WHERE cs."sourceUrl" IS NOT NULL
  `);

  for (const row of chgSpecs.rows) {
    const specs = [];
    if (row.dcPowerKw) specs.push(`ชาร์จ DC ${row.dcPowerKw} kW`);
    if (row.acPowerKw) specs.push(`ชาร์จ AC ${row.acPowerKw} kW`);
    if (specs.length > 0) {
      facts.push({
        entityType: "spec", entityId: `charge:${row.id}`, variantId: row.variantId,
        content: `${row.manufacturer_name} ${row.model_name} ${row.variant_name} ${specs.join(" ")}`,
        sourceUrl: row.sourceUrl || "", sourceTier: "verified", verified: true,
      });
    }
  }

  return facts;
}
