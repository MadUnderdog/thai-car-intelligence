/**
 * P116 — live read-only contract tests (real DB, no writes).
 *
 * These prove the price-eligibility and ID contracts against actual data:
 *   A2  /api/models price parity with an INDEPENDENTLY written full-chain reference
 *   D2  /api/models returns compareVariantId (ACTIVE variant of the same model)
 *   D3  two compareVariantIds flow into /api/compare with order preserved
 *   H2  /api/compare carries price provenance URL for full-chain priced variants
 *   K2  deterministic repeated compare responses
 *   B4  secondary-tier spec data exists → official flags must not claim it
 */
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import pg from "pg";
import { GET as getModels } from "../src/app/api/models/route";
import { GET as getCompare } from "../src/app/api/compare/route";

const client = new pg.Client({
  user: process.env.DB_USER || "hermes",
  host: process.env.DB_HOST || "localhost",
  port: Number(process.env.DB_PORT) || 5432,
  database: process.env.DB_NAME || "thai_car_intelligence",
});

const REFERENCE_FULL_CHAIN = `
  SELECT cm.id::text AS model_id,
         min(p.amount)::text AS min_amount,
         max(p.amount)::text AS max_amount
  FROM "CarModel" cm
  JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
  JOIN "Variant" v ON v."modelId" = cm.id AND v.status = 'ACTIVE'
  JOIN "Price" p ON p."variantId" = v.id AND p."isCurrent" = true
  JOIN "SourceDocument" sd ON sd.id = p."sourceDocumentId"
  JOIN "Source" s ON s.id = sd."sourceId"
  WHERE cm.status = 'ACTIVE' AND m.status = 'ACTIVE'
    AND sd.status = 'VERIFIED'
    AND s.status = 'ACTIVE'
    AND s."sourceType"::text IN ('OFFICIAL_MANUFACTURER','OFFICIAL_MANUFACTURER_BROCHURE','OFFICIAL_MANUFACTURER_PRICE_LIST','OFFICIAL_MANUFACTURER_PRESS_RELEASE')
    AND EXISTS (SELECT 1 FROM "BrochureVerification" bv
                WHERE bv."sourceDocumentId" = sd.id AND bv.status = 'VERIFIED')
  GROUP BY cm.id`;

beforeAll(async () => {
  await client.connect();
});
afterAll(async () => {
  await client.end();
});

describe("A2. /api/models price parity with independent currentOfficialPrice reference", () => {
  it("every listed model's min/max equals the full-chain reference (no secondary/loose price leak)", async () => {
    const res = await getModels(new Request("http://localhost/api/models?limit=100"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.results.length).toBeGreaterThan(0);

    const ref = new Map<string, { min: string; max: string }>();
    const refRows = await client.query(REFERENCE_FULL_CHAIN);
    for (const r of refRows.rows) ref.set(r.model_id, { min: r.min_amount, max: r.max_amount });

    const mismatches: any[] = [];
    for (const row of body.results) {
      const expected = ref.get(row.id);
      const expectedMin = expected ? Number(expected.min) : null;
      const expectedMax = expected ? Number(expected.max) : null;
      if (row.minPrice !== expectedMin || row.maxPrice !== expectedMax) {
        mismatches.push({ model: `${row.manufacturer.slug}/${row.slug}`, got: [row.minPrice, row.maxPrice], expected: [expectedMin, expectedMax] });
      }
    }
    expect(mismatches, `route prices must equal the full-chain reference; leaks: ${JSON.stringify(mismatches.slice(0, 5))}`).toEqual([]);
  });
});

describe("D. compareVariantId contract", () => {
  let ids: string[] = [];

  it("D2: models rows carry compareVariantId pointing at an ACTIVE variant of the SAME model", async () => {
    const res = await getModels(new Request("http://localhost/api/models?limit=100"));
    const body = await res.json();
    expect(body.results.length).toBeGreaterThan(0);
    expect(body.results[0]).toHaveProperty("compareVariantId");

    for (const row of body.results) {
      if (!row.compareVariantId) continue;
      const check = await client.query(
        `SELECT v.id FROM "Variant" v WHERE v.id = $1 AND v."modelId" = $2 AND v.status = 'ACTIVE'`,
        [row.compareVariantId, row.id],
      );
      expect(check.rows.length, `compareVariantId must be an ACTIVE variant of ${row.slug}`).toBe(1);
    }
    ids = body.results.filter((r: any) => r.compareVariantId).slice(0, 2).map((r: any) => r.compareVariantId);
    expect(ids.length, "need at least 2 models exposing a compareVariantId").toBeGreaterThanOrEqual(2);
  });

  it("D3+K2: /api/compare accepts those ids, preserves requested order, deterministic across runs", async () => {
    const reversed = [...ids].reverse();
    const first = await (await getCompare(new Request(`http://localhost/api/compare?ids=${reversed.join(",")}`))).json();
    expect(first.comparison.map((c: any) => c.id)).toEqual(reversed);

    const second = await (await getCompare(new Request(`http://localhost/api/compare?ids=${reversed.join(",")}`))).json();
    expect(second).toEqual(first); // K2 deterministic
  });
});

describe("H2. compare price provenance URL (full-chain priced variants)", () => {
  it("returns price.sourceUrl + sourceName for variants with currentOfficialPrice", async () => {
    const priced = await client.query(`
      SELECT v.id::text
      FROM "Price" p
      JOIN "SourceDocument" sd ON sd.id = p."sourceDocumentId"
      JOIN "Source" s ON s.id = sd."sourceId"
      JOIN "Variant" v ON v.id = p."variantId"
      WHERE p."isCurrent" = true AND sd.status = 'VERIFIED' AND s.status = 'ACTIVE'
        AND s."sourceType"::text IN ('OFFICIAL_MANUFACTURER','OFFICIAL_MANUFACTURER_BROCHURE','OFFICIAL_MANUFACTURER_PRICE_LIST','OFFICIAL_MANUFACTURER_PRESS_RELEASE')
        AND v.status = 'ACTIVE'
        AND EXISTS (SELECT 1 FROM "BrochureVerification" bv WHERE bv."sourceDocumentId" = sd.id AND bv.status = 'VERIFIED')
      LIMIT 2`);
    expect(priced.rows.length, "expected >=2 full-chain priced active variants in DB").toBeGreaterThanOrEqual(2);
    const [a, b] = priced.rows.map((r: any) => r.id);
    const res = await getCompare(new Request(`http://localhost/api/compare?ids=${a},${b}`));
    expect(res.status).toBe(200);
    const body = await res.json();
    const pricedHits = body.comparison.filter((c: any) => c.price !== null);
    expect(pricedHits.length).toBeGreaterThan(0);
    for (const hit of pricedHits) {
      expect(hit.price.sourceUrl, "price provenance URL must survive into the response").toBeTruthy();
      expect(hit.price.sourceName).toBeTruthy();
    }
  });
});

describe("B4. secondary-tier spec data must never be flagged official", () => {
  it("active variants exist whose PerformanceSpec row is secondary-tier only", async () => {
    const rows = await client.query(`
      SELECT ps."sourceTier"::text AS tier FROM "PerformanceSpec" ps
      JOIN "Variant" v ON v.id = ps."variantId" WHERE v.status = 'ACTIVE'`);
    const tiers = new Set(rows.rows.map((r: any) => r.tier));
    expect(tiers.has("secondary_automotive_media"), "data precondition for the tier-honest evidence flag").toBe(true);

    const m = await import("../lib/ux/detail-view").catch(() => null);
    expect(m, "lib/ux/detail-view must exist").not.toBeNull();
    expect(m!.specEvidenceFlags([{ sourceTier: "secondary_automotive_media" }])).toBe(false);
    expect(m!.specEvidenceFlags([{ sourceTier: "primary_official" }])).toBe(true);
  });
});
