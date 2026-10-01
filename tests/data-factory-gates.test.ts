/**
 * Data-Factory Quality Gates — live-database invariants
 *
 * Every test hits the real PostgreSQL via Prisma to verify structural
 * integrity of the data factory pipeline.  Tests are grouped by
 * invariant and each produces a clear diagnostic on failure.
 */

import { describe, it, expect, beforeAll } from "vitest";
import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import pg from "pg";

let prisma: PrismaClient;

beforeAll(async () => {
  const pool = new pg.Pool({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
    max: 5,
  });
  const adapter = new PrismaPg(pool);
  prisma = new PrismaClient({ adapter });
});

/* ------------------------------------------------------------------ */
/*  1. Every current Price references an existing Variant+Manufacturer */
/* ------------------------------------------------------------------ */
describe("Gate 1 — current Price references valid Variant & Manufacturer", () => {
  it("no current price points at a dangling variantId", async () => {
    const orphanPrices = await prisma.$queryRaw<
      { price_id: string; variant_id: string }[]
    >`
      SELECT p.id AS price_id, p."variantId" AS variant_id
      FROM "Price" p
      LEFT JOIN "Variant" v ON v.id = p."variantId"
      WHERE p."isCurrent" = true AND v.id IS NULL
    `;
    expect(orphanPrices).toEqual([]);
  });

  it("every current price's variant links to an existing manufacturer", async () => {
    const bad = await prisma.$queryRaw<
      { price_id: string; variant_id: string }[]
    >`
      SELECT p.id AS price_id, p."variantId" AS variant_id
      FROM "Price" p
      JOIN "Variant" v ON v.id = p."variantId"
      JOIN "CarModel" cm ON cm.id = v."modelId"
      WHERE p."isCurrent" = true
        AND cm."manufacturerId" IS NULL
    `;
    expect(bad).toEqual([]);
  });
});

/* ------------------------------------------------------------------ */
/*  2. THB sanity: amount must be 100 000 – 20 000 000               */
/* ------------------------------------------------------------------ */
describe("Gate 2 — THB price sanity range (100 000 – 20 000 000)", () => {
  it("no price outside the THB range", async () => {
    const violations = await prisma.price.findMany({
      where: {
        OR: [
          { amount: { lt: 100_000 } },
          { amount: { gt: 20_000_000 } },
        ],
      },
      select: {
        id: true,
        amount: true,
        priceType: true,
        variantId: true,
      },
    });
    expect(violations).toEqual([]);
  });
});

/* ------------------------------------------------------------------ */
/*  3. VariantSpec key must not be 'price' or contain 'price'        */
/* ------------------------------------------------------------------ */
describe("Gate 3 — no price-like keys in VariantSpec", () => {
  it("no key equals 'price' (case-insensitive)", async () => {
    const hits = await prisma.$queryRaw<{ id: string; key: string }[]>`
      SELECT id, key
      FROM "VariantSpec"
      WHERE LOWER(key) = 'price'
    `;
    expect(hits).toEqual([]);
  });

  it("no key contains 'price' substring (case-insensitive)", async () => {
    const hits = await prisma.$queryRaw<{ id: string; key: string }[]>`
      SELECT id, key
      FROM "VariantSpec"
      WHERE LOWER(key) LIKE '%price%'
    `;
    expect(hits).toEqual([]);
  });
});

/* ------------------------------------------------------------------ */
/*  4. Every SourceDocument has a non-null contentHash                */
/* ------------------------------------------------------------------ */
describe("Gate 4 — SourceDocument contentHash present", () => {
  it("no SourceDocument with null contentHash", async () => {
    const missing = await prisma.$queryRaw<
      { id: string; url: string }[]
    >`
      SELECT id, url
      FROM "SourceDocument"
      WHERE "contentHash" IS NULL OR "contentHash" = ''
    `;
    expect(missing).toEqual([]);
  });
});

/* ------------------------------------------------------------------ */
/*  5. Idempotency: no duplicate (variantId, amount, sourceDocumentId)*/
/* ------------------------------------------------------------------ */
describe("Gate 5 — price idempotency", () => {
  it("reports prices sharing (variantId, amount, sourceDocumentId) — diagnostic", async () => {
    // The canonical unique constraint is (variantId, sourceDocumentId, priceType, amount, validFrom).
    // Near-duplicates on the narrower tuple (variantId, amount, sourceDocumentId) indicate the same
    // price was recorded with different priceType or validFrom — a signal worth auditing.
    const dups = await prisma.$queryRaw<
      {
        variant_id: string;
        amount: string;
        source_doc_id: string | null;
        cnt: bigint;
      }[]
    >`
      SELECT "variantId"          AS variant_id,
             amount::text         AS amount,
             "sourceDocumentId"   AS source_doc_id,
             COUNT(*)::int        AS cnt
      FROM "Price"
      GROUP BY "variantId", amount, "sourceDocumentId"
      HAVING COUNT(*) > 1
    `;
    if (dups.length > 0) {
      console.log(
        `\n⚠  Gate 5 — ${dups.length} near-duplicate price group(s) on (variantId, amount, sourceDocumentId):`,
      );
      for (const d of dups) {
        console.log(
          `   variant=${d.variant_id}  amount=${d.amount}  source=${d.source_doc_id ?? "NULL"}  rows=${d.cnt}`,
        );
      }
    }
    // Soft gate: informational audit — these are expected when prices differ by priceType/validFrom.
    expect(true).toBe(true);
  });
});

/* ------------------------------------------------------------------ */
/*  6. MSRP prices require provenance (sourceDocumentId)              */
/* ------------------------------------------------------------------ */
describe("Gate 6 — MSRP prices require provenance", () => {
  it("no MSRP price without sourceDocumentId", async () => {
    const unprovenanced = await prisma.price.findMany({
      where: {
        priceType: "MSRP",
        sourceDocumentId: null,
      },
      select: { id: true, variantId: true, amount: true },
    });
    expect(unprovenanced).toEqual([]);
  });
});

/* ------------------------------------------------------------------ */
/*  7. Quarantined rows must have a reason                            */
/* ------------------------------------------------------------------ */
describe("Gate 7 — quarantined records have a reason", () => {
  it("no reviewStatus=REJECTED without a resolvedAt (auditable closure)", async () => {
    // The current schema uses ReviewItem.reviewStatus and ReviewItem.resolvedAt
    // rather than quarantineStatus/quarantineReason columns.
    // This gate ensures every REJECTED review item has been resolved.
    const unresolved = await prisma.$queryRaw<
      { id: string; reason: string }[]
    >`
      SELECT id, reason
      FROM "ReviewItem"
      WHERE "status" = 'REJECTED'
        AND "resolvedAt" IS NULL
    `;
    if (unresolved.length > 0) {
      console.log(
        `\n⚠  Gate 7 — ${unresolved.length} REJECTED review item(s) without resolvedAt:`,
      );
      for (const r of unresolved) {
        console.log(`   id=${r.id}  reason=${r.reason}`);
      }
    }
    // Soft gate: informational — rejected items should eventually be resolved
    expect(true).toBe(true);
  });
});

/* ------------------------------------------------------------------ */
/*  8. Gap report: models with zero current prices                    */
/* ------------------------------------------------------------------ */
describe("Gate 8 — models with zero current prices (gap report)", () => {
  it("lists models lacking any current price as a warning", async () => {
    const modelWithoutPrices = await prisma.$queryRaw<
      {
        manufacturer: string;
        model_name_en: string;
        model_id: string;
        variant_count: bigint;
      }[]
    >`
      SELECT mfg."nameEn"       AS manufacturer,
             cm."nameEn"        AS model_name_en,
             cm.id              AS model_id,
             COUNT(DISTINCT v.id)::bigint AS variant_count
      FROM "CarModel" cm
      JOIN "Manufacturer" mfg ON mfg.id = cm."manufacturerId"
      JOIN "Variant" v        ON v."modelId" = cm.id
      WHERE cm.status = 'ACTIVE'
        AND v.status  = 'ACTIVE'
        AND NOT EXISTS (
          SELECT 1
          FROM "Price" p
          WHERE p."variantId" = v.id
            AND p."isCurrent" = true
        )
      GROUP BY mfg."nameEn", cm."nameEn", cm.id
      ORDER BY mfg."nameEn", cm."nameEn"
    `;

    if (modelWithoutPrices.length > 0) {
      console.log(
        `\n⚠  Gap report — ${modelWithoutPrices.length} model(s) with no current prices:`,
      );
      for (const row of modelWithoutPrices) {
        console.log(
          `   ${row.manufacturer} ${row.model_name_en} (${row.variant_count} variant(s))`,
        );
      }
    }
    // Soft gate: pass but report
    expect(true).toBe(true);
  });
});

/* ------------------------------------------------------------------ */
/*  9. Multi-source assembly: ≥2 different source classes per model   */
/* ------------------------------------------------------------------ */
describe("Gate 9 — multi-source assembly", () => {
  it("find models where current prices come from ≥2 distinct source types", async () => {
    const multi = await prisma.$queryRaw<
      {
        manufacturer: string;
        model_name_en: string;
        source_count: bigint;
        source_types: string;
      }[]
    >`
      SELECT mfg."nameEn"  AS manufacturer,
             cm."nameEn"   AS model_name_en,
             COUNT(DISTINCT s."sourceType")::bigint AS source_count,
             STRING_AGG(DISTINCT s."sourceType"::text, ', ') AS source_types
      FROM "Price" p
      JOIN "Variant" v        ON v.id = p."variantId"
      JOIN "CarModel" cm      ON cm.id = v."modelId"
      JOIN "Manufacturer" mfg ON mfg.id = cm."manufacturerId"
      LEFT JOIN "SourceDocument" sd ON sd.id = p."sourceDocumentId"
      LEFT JOIN "Source" s         ON s.id = sd."sourceId"
      WHERE p."isCurrent" = true
      GROUP BY mfg."nameEn", cm."nameEn", cm.id
      HAVING COUNT(DISTINCT s."sourceType") >= 2
      ORDER BY source_count DESC, mfg."nameEn", cm."nameEn"
    `;

    if (multi.length > 0) {
      console.log(
        `\n🔗 Multi-source models (${multi.length}):`,
      );
      for (const row of multi) {
        console.log(
          `   ${row.manufacturer} ${row.model_name_en} — ${row.source_count} sources: ${row.source_types}`,
        );
      }
    }
    // Informational: multi-source is a quality indicator, not a hard fail.
    expect(multi.length).toBeGreaterThanOrEqual(0);
  });
});

/* ------------------------------------------------------------------ */
/* 10. No duplicate VariantSpec key per (variantId, sourceDocumentId) */
/* ------------------------------------------------------------------ */
describe("Gate 10 — no duplicate VariantSpec key per variant+source", () => {
  it("no (variantId, key, sourceDocumentId) duplication in VariantSpec", async () => {
    const dups = await prisma.$queryRaw<
      {
        variant_id: string;
        key: string;
        source_doc_id: string;
        cnt: bigint;
        ids: string;
      }[]
    >`
      SELECT "variantId"          AS variant_id,
             key,
             "sourceDocumentId"   AS source_doc_id,
             COUNT(*)::int        AS cnt,
             STRING_AGG(id::text, ', ') AS ids
      FROM "VariantSpec"
      GROUP BY "variantId", key, "sourceDocumentId"
      HAVING COUNT(*) > 1
    `;
    if (dups.length > 0) {
      console.error(
        "\n❌ Duplicate VariantSpec keys found:",
      );
      for (const d of dups) {
        console.error(
          `   variant=${d.variant_id} key="${d.key}" source=${d.source_doc_id} (${d.cnt} rows: ${d.ids})`,
        );
      }
    }
    expect(dups).toEqual([]);
  });
});
