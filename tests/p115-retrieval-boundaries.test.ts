/**
 * P115 — Search / retrieval / RAG boundary regressions.
 *
 * Red-before: written against base 7c2fc2b (unmodified retrieval code),
 * run BEFORE the implementation pass — failures recorded per defect group
 * (G1..G7 in audit/coverage/p115_target_plan.json).
 *
 * Boundaries proven here:
 *  A. Structured catalog stays authoritative (vector can never widen results)
 *  C. Every returned vector evidence item passes the deterministic gates
 *  D. Ask route returns insufficient — never same-brand guessing
 *  E. Query normalization preserves exact entity specificity
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { PrismaClient } from "@prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";
import pg from "pg";

import { parseSearchQuery, GET as getSearch } from "../src/app/api/search/route";
import { searchCatalog } from "../lib/catalog/queries";
import { searchHybrid } from "../lib/search/hybrid-search";
import { searchVectorEvidence, type VectorEvidence } from "../lib/search/vector-search";
import { applyEvidenceThresholds } from "../lib/ai/retrieval/evidence-gate-policy";
import { searchQuestionCatalog } from "../lib/ai/retrieval/catalog-search";
import { smartCatalogSearch } from "../lib/discovery/exact-model-retrieval";
import { POST as ask } from "../src/app/api/ai/ask/route";
import * as catalogSearchModule from "../lib/ai/retrieval/catalog-search";
import * as vectorSearchModule from "../lib/search/vector-search";
import * as hybridModule from "../lib/search/hybrid-search";
import type { CatalogPage } from "../lib/catalog/types";

const emptyPage = (overrides: Partial<CatalogPage> = {}): CatalogPage => ({
  results: [], total: 0, page: 1, limit: 24, hasMore: false, ...overrides,
});

const vecRow = (over: Partial<VectorEvidence> = {}): VectorEvidence => ({
  id: "e1", sourceDocumentId: "d1", entityType: "SourceDocument", entityId: "v1",
  chunkIndex: 0, chunkType: "document", pageNumber: null,
  content: "Camry official evidence ราคา 1,000,000 บาท", distance: 0.1,
  source: { id: "s1", url: "https://example.test/camry", titleTh: null, titleEn: "Camry", sourceType: "OFFICIAL_MANUFACTURER" },
  ...over,
});

function filters(q: string): URLSearchParams {
  return new URLSearchParams({ q });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

/* ──────────────────────────────────────────────────────────────────────
 * 1+2. Exact explicit query: Honda City → city scope only, never the
 *      arbitrary same-brand set. Thai alias behaves the same.
 * ──────────────────────────────────────────────────────────────────── */
describe("T1/T2 explicit model scoping (structured authority)", () => {
  it("1: 'Honda City' resolves to city scope + honda brand (never brand-wide)", () => {
    const f = parseSearchQuery(filters("Honda City"));
    expect(f).not.toBeNull();
    expect(f!.q).toBe("city");
    expect(f!.manufacturer).toBe("honda");
    // brand-wide (q erased) is the defect — assert it stays gone
    expect(f!.q).not.toBeUndefined();
  });

  it("2: Thai alias 'ฮอนด้า ซิตี้' resolves identically", () => {
    const f = parseSearchQuery(filters("ฮอนด้า ซิตี้"));
    expect(f).toMatchObject({ q: "city", manufacturer: "honda" });
  });

  it("2b: substring-colliding Thai aliases keep the most specific entity ('ยาริส ครอส' → yaris cross, not 'yaris yaris cross')", () => {
    const f = parseSearchQuery(filters("ยาริส ครอส"));
    expect(f!.q).toBe("yaris cross");
    const ep = parseSearchQuery(filters("เอพี พลัส"));
    expect(ep!.q).toBe("ep plus");
  });

  it("guards: brand-only queries stay brand-scoped, non-brand queries keep original q", () => {
    expect(parseSearchQuery(filters("ฮอนด้า"))).toMatchObject({ manufacturer: "honda", q: undefined });
    expect(parseSearchQuery(filters("Honda"))).toMatchObject({ manufacturer: "honda", q: undefined });
    expect(parseSearchQuery(filters("City Hatchback"))).toMatchObject({ q: "City Hatchback" });
  });

  it("1b: live catalog — city scope returns real rows and never CR-V/Civic/Accord", async () => {
    const pool = new pg.Pool({
      user: process.env.DB_USER || "hermes",
      host: process.env.DB_HOST || "localhost",
      port: Number(process.env.DB_PORT) || 5432,
      database: process.env.DB_NAME || "thai_car_intelligence",
      max: 2,
    });
    const client = new PrismaClient({ adapter: new PrismaPg(pool) });
    try {
      const f = parseSearchQuery(filters("Honda City"))!;
      const page = await searchCatalog(f, client);
      expect(page.total).toBeGreaterThan(0); // non-vacuous: priced City-family row exists
      for (const r of page.results) {
        expect(r.model.slug.startsWith("city")).toBe(true);
        expect(/cr-v|civic|accord|hr-v|br-v/i.test(r.model.nameEn)).toBe(false);
      }
      // Thai alias → identical structured eligibility
      const thai = await searchCatalog(parseSearchQuery(filters("ฮอนด้า ซิตี้"))!, client);
      expect(thai.total).toBeGreaterThan(0);
      for (const r of thai.results) expect(r.model.slug.startsWith("city")).toBe(true);

      // G2: the erased phrase 'yaris yaris cross' finds nothing, the
      // specific entity 'yaris cross' does (Yaris Cross has a priced row).
      const erased = await searchCatalog({ q: "yaris yaris cross", limit: 50, page: 1 }, client);
      expect(erased.total).toBe(0);
      const specific = await searchCatalog(parseSearchQuery(filters("ยาริส ครอส"))!, client);
      expect(specific.total).toBeGreaterThan(0);
      for (const r of specific.results) expect(r.model.slug).toContain("yaris-cross");
    } finally {
      await client.$disconnect().catch(() => undefined);
      await pool.end().catch(() => undefined);
    }
  });
});

/* ──────────────────────────────────────────────────────────────────────
 * 3. Short-token collision: MG EP vs MG EP Plus stays separated
 *    across structured retrieval (slug collision mg-ep → EP Plus).
 * ──────────────────────────────────────────────────────────────────── */
describe("T3 MG EP vs MG EP Plus separation", () => {
  const variant = (name: string, model: string, manufacturer: string) => ({
    id: `v-${model}`, nameTh: name, nameEn: name, slug: name.toLowerCase(), modelYear: 2025,
    status: "ACTIVE", modelYearValue: null,
    model: {
      id: `m-${model}`, nameTh: model, nameEn: model, slug: model.toLowerCase().replace(/\s+/g, "-"),
      manufacturer: { id: "mfr", nameTh: manufacturer, nameEn: manufacturer, slug: manufacturer.toLowerCase() },
      status: "ACTIVE", modelYear: null,
    },
    aliases: [], fuelType: null,
    prices: [{
      id: "p1", amount: 999900, currency: "THB", priceType: "MSRP", isCurrent: true,
      validFrom: new Date("2026-01-01"), validTo: null, observedAt: new Date("2026-01-01"),
      sourceDocument: {
        id: "sd1", status: "VERIFIED", url: "https://mg.example/ep",
        canonicalUrl: "https://mg.example/ep", titleTh: null, titleEn: "MG EP",
        source: { id: "s1", nameTh: "MG", nameEn: "MG", sourceType: "OFFICIAL_MANUFACTURER", status: "ACTIVE", domain: "mg.example" },
        verifications: [{ status: "VERIFIED", verifiedAt: new Date("2026-01-02") }],
      },
    }],
    manufacturer: { id: "mfr", nameTh: manufacturer, nameEn: manufacturer, slug: manufacturer.toLowerCase() },
  });

  const fakePrisma = {
    carModel: {
      findFirst: async (args: { where: { slug?: string } }) => {
        const slug = args?.where?.slug;
        if (slug === "mg-ep") {
          // DB reality: slug 'mg-ep' belongs to model "EP Plus"
          return {
            id: "m-ep-plus", nameTh: "EP Plus", nameEn: "EP Plus", slug: "mg-ep", modelYear: null, status: "ACTIVE",
            variants: [variant("EV", "EP Plus", "MG")],
            manufacturer: { id: "mfr", nameEn: "MG", slug: "mg" },
            aliases: [],
          };
        }
        if (slug === "city") {
          return {
            id: "m-city", nameTh: "City", nameEn: "City", slug: "city", modelYear: null, status: "ACTIVE",
            variants: [variant("V", "City", "Honda")],
            manufacturer: { id: "mfr", nameEn: "Honda", slug: "honda" },
            aliases: [],
          };
        }
        return null;
      },
    },
    alias: { findFirst: async () => null },
    variant: { findFirst: async () => null },
  } as never;

  it("3a: structured query 'MG EP' is model-scoped (q='ep'), never brand-wide", () => {
    const f = parseSearchQuery(filters("MG EP"));
    expect(f).toMatchObject({ q: "ep", manufacturer: "mg" });
  });

  it("3b: exact retrieval must not resolve slug 'mg-ep' (EP Plus) for query 'MG EP' — and still resolves Honda City", async () => {
    const ep = await smartCatalogSearch(fakePrisma, "MG EP", 5);
    expect(ep.exactMatch).toBe(false);
    expect(ep.results).toEqual([]);

    const city = await smartCatalogSearch(fakePrisma, "Honda City", 5);
    expect(city.exactMatch).toBe(true);
    expect(city.results.map((v: { model?: { nameEn?: string } }) => v.model?.nameEn)).toEqual(["City"]);
  });

  it("3c: hybrid never returns EP Plus vector evidence for an 'MG EP' query", async () => {
    const out = await searchHybrid({ q: "MG EP", limit: 10, page: 1 }, {
      searchCatalog: vi.fn(async () => emptyPage()),
      vectorSearch: vi.fn(async () => ({
        available: true,
        evidence: [vecRow({ id: "ep-plus-row", content: "MG EP Plus sedan ราคา 999,000 บาท รุ่นปี 2024" })],
      })),
    });
    expect(out.evidence.map((e) => e.id)).toEqual([]);
    expect(out.vectorAvailable).toBe(true); // service ran; evidence just failed gates
    expect(out.results).toEqual([]);
  });
});

/* ──────────────────────────────────────────────────────────────────────
 * 4. /api/search uses hybrid; structured result set is NEVER widened
 *    by vector hits; structured contract fields unchanged.
 * ──────────────────────────────────────────────────────────────────── */
describe("T4 structured results not widened by vector evidence", () => {
  const structured = emptyPage({
    results: [{
      id: "v-city-hatch", nameTh: "City Hatchback", nameEn: "City Hatchback", slug: "city-hatchback-v",
      modelYear: 2025,
      manufacturer: { id: "mfr", nameTh: "ฮอนด้า", nameEn: "Honda", slug: "honda" },
      model: { id: "m-ch", nameTh: "City Hatchback", nameEn: "City Hatchback", slug: "city-hatchback", modelYear: 2025 },
      fuelType: "HEV", aliases: [], prices: [],
    }],
    total: 1, page: 1, limit: 24, hasMore: false,
  });

  it("4a: hybrid keeps the structured result set byte-identical while attaching gated evidence", async () => {
    const out = await searchHybrid({ q: "Honda City", limit: 24, page: 1 }, {
      searchCatalog: vi.fn(async () => structured),
      vectorSearch: vi.fn(async () => ({
        available: true,
        evidence: [
          vecRow({ id: "ok", content: "Honda City e:HEV ราคา 999,000 บาท" }),
          vecRow({ id: "crv", entityId: "v-crv", content: "Honda CR-V ราคา 1,500,000 บาท" }),
        ],
      })),
    });
    // structured contract untouched
    expect(out.results).toEqual(structured.results);
    expect(out.total).toBe(1);
    expect(out.page).toBe(1);
    expect(out.limit).toBe(24);
    expect(out.hasMore).toBe(false);
    // cross-model vector row gated out; accepted row keeps provenance
    expect(out.evidence.map((e) => e.id)).toEqual(["ok"]);
    expect(out.evidence[0].source.url).toBe("https://example.test/camry");
    // vector rows can never inject entities into the result set
    expect((out.results as Array<{ id: string }>).some((r) => r.id === "v-crv")).toBe(false);
  });

  it("4b: /api/search response reports hybrid mode from searchHybrid and preserves structured fields", async () => {
    const spy = vi.spyOn(hybridModule, "searchHybrid").mockResolvedValue({
      ...structured, vectorAvailable: true, searchMode: "hybrid", evidence: [vecRow()],
    });
    const res = await getSearch(new Request("http://localhost/api/search?q=Honda%20City"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0]?.[0]).toMatchObject({ q: "city", manufacturer: "honda" });
    expect(body.results).toEqual(structured.results);
    expect(body.total).toBe(1);
    expect(body.vectorAvailable).toBe(true);
    expect(body.searchMode).toBe("hybrid");
    expect(body.evidence).toHaveLength(1);
    expect(body.evidence[0].source.url).toBe("https://example.test/camry");
  });
});

/* ──────────────────────────────────────────────────────────────────────
 * 5+6. Vector-disabled / dimension-mismatch paths fail closed truthfully.
 * ──────────────────────────────────────────────────────────────────── */
describe("T5/T6 fail-closed vector fallbacks", () => {
  it("5: no embedding endpoint → truthful structured-fallback with results intact", async () => {
    vi.stubEnv("EMBEDDING_BASE_URL", "");
    const catalog = emptyPage({ total: 3 });
    const out = await searchHybrid({ q: "Camry", limit: 24, page: 1 }, {
      searchCatalog: vi.fn(async () => catalog),
    });
    expect(out).toMatchObject({ vectorAvailable: false, searchMode: "structured-fallback", evidence: [] });
    expect(out.total).toBe(3);
    expect(out.results).toEqual(catalog.results);
  });

  it("6: wrong-length query embedding fails closed before touching the database", async () => {
    const queryRaw = vi.fn();
    const bad = {
      provider: "local" as const, model: "test", dimensions: 1024,
      embed: vi.fn(async () => [Array.from({ length: 512 }, () => 0.1)]),
    };
    await expect(searchVectorEvidence("Camry", { embeddingClient: bad, queryRaw }))
      .rejects.toMatchObject({ code: "dimension_mismatch" });
    expect(queryRaw).not.toHaveBeenCalled();
  });
});

/* ──────────────────────────────────────────────────────────────────────
 * 7+8+9. Vector evidence guards: SQL predicates + deterministic gate.
 * ──────────────────────────────────────────────────────────────────── */
describe("T7/T8/T9 vector evidence gates", () => {
  const client1024 = {
    provider: "local" as const, model: "test", dimensions: 1024,
    embed: vi.fn(async () => [Array.from({ length: 1024 }, () => 0.01)]),
  };

  it("7+8: retrieval SQL keeps VERIFIED document / ACTIVE source / BrochureVerification predicates", async () => {
    const queryRaw = vi.fn(async () => []);
    await searchVectorEvidence("Camry", { embeddingClient: client1024, queryRaw, limit: 5 });
    expect(queryRaw).toHaveBeenCalledTimes(1);
    const sql = (queryRaw.mock.calls as unknown[][])[0]?.[0] as { sql: string };
    expect(sql.sql).toContain('sd."status"');
    expect(sql.sql).toContain("VERIFIED");
    expect(sql.sql).toContain('s."status"');
    expect(sql.sql).toContain("ACTIVE");
    expect(sql.sql).toContain('"BrochureVerification"');
    expect(sql.sql).toContain("dimensions");
  });

  it("7b: untrusted sourceType is rejected by the deterministic gate", () => {
    const gated = applyEvidenceThresholds("Camry ราคา", {
      available: true,
      evidence: [vecRow({ source: { id: "s9", url: "https://forum.test/x", titleTh: null, titleEn: null, sourceType: "COMMUNITY" } })],
    });
    expect(gated.evidence).toEqual([]);
  });

  it("9: cross-model vector evidence (CR-V for a Honda City query) is rejected", () => {
    const gated = applyEvidenceThresholds("Honda City ราคาเท่าไหร่", {
      available: true,
      evidence: [vecRow({ content: "Honda CR-V ราคา 1,500,000 บาท เครื่องยนต์ 1.5 เทอร์โบ" })],
    });
    expect(gated.evidence).toEqual([]);
  });

  it("11: deterministic + idempotent — same input, same ordered ids; gating twice changes nothing", () => {
    const input = {
      available: true,
      evidence: [
        vecRow({ id: "a", distance: 0.12, content: "Honda City ราคา 999,000 บาท" }),
        vecRow({ id: "b", distance: 0.28, content: "Honda City e:HEV ราคา 1,100,000 บาท" }),
      ],
    };
    const once = applyEvidenceThresholds("Honda City", input);
    const twice = applyEvidenceThresholds("Honda City", input);
    expect(once.evidence.map((e) => e.id)).toEqual(twice.evidence.map((e) => e.id));
    const again = applyEvidenceThresholds("Honda City", once);
    expect(again).toEqual(once);
  });
});

/* ──────────────────────────────────────────────────────────────────────
 * 10. Ask boundary: no structured exact hit + no qualified vector
 *     → insufficient; explicit-model fallback never same-brand guesses.
 * ──────────────────────────────────────────────────────────────────── */
describe("T10 ask route insufficient / no same-brand guessing", () => {
  const req = (question: string) =>
    new Request("http://localhost/api/ai/ask", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question }),
    });

  it("10a: structured empty + vector rows that fail gates → 200 insufficient, no citations", async () => {
    vi.spyOn(catalogSearchModule, "searchQuestionCatalog").mockResolvedValue([]);
    const vectorSpy = vi.spyOn(vectorSearchModule, "searchVectorEvidence").mockResolvedValue({
      available: true,
      evidence: [vecRow({ content: "บทความรีวิวรถยนต์ทั่วไปไม่เกี่ยวกับคำถามนี้", distance: 0.42 })],
    });
    const res = await ask(req("รถรุ่นที่ไม่มีในระบบเลยxyz"));
    expect(vectorSpy).toHaveBeenCalledTimes(1); // vector path really ran
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("insufficient_evidence");
    expect(body.whyThisAnswer).toEqual([]);
    expect(body.trust.confidence).toBe("INSUFFICIENT");
  });

  it("10b: explicit-model query never falls back to brand-wide search terms", async () => {
    const calls: string[] = [];
    const searcher = vi.fn(async (f: { q: string }) => {
      calls.push(f.q);
      return emptyPage();
    });
    const out = await searchQuestionCatalog(
      "ราคา MG EP มีรุ่นอะไร",
      searcher as never,
      { exactSearch: vi.fn(async () => ({ results: [], matchType: "none", exactMatch: false })) } as never,
    );
    expect(out).toEqual([]);
    expect(calls).toContain("ep");       // model-scoped term searched
    expect(calls).not.toContain("mg");   // brand-only term dropped (no same-brand guessing)
  });
});

/* ──────────────────────────────────────────────────────────────────────
 * 12. Ask structured prices come only from the official verified chain
 *     (G4): an isCurrent price from a non-official/unverified document
 *     must never be surfaced as structured price evidence.
 * ──────────────────────────────────────────────────────────────────── */
describe("T12 structured price eligibility in AI retrieval", () => {
  it("12: exact-branch prices failing the official chain are dropped, not claimed", async () => {
    const unofficialVariant = {
      id: "v-bad", nameTh: "City", nameEn: "City", slug: "v-bad", modelYear: 2025,
      manufacturer: { id: "mfr", nameTh: "ฮอนด้า", nameEn: "Honda", slug: "honda" },
      model: { id: "m-city", nameTh: "City", nameEn: "City", slug: "city", modelYear: 2025 },
      aliases: [], fuelType: null,
      prices: [{
        id: "p-bad", amount: 1234567, currency: "THB", priceType: "MSRP", isCurrent: true,
        validFrom: new Date("2026-01-01"), validTo: null, observedAt: new Date("2026-01-01"),
        sourceDocument: {
          id: "sd-bad", status: "DISCOVERED", url: "https://used.example/listing",
          canonicalUrl: null, titleTh: null, titleEn: null,
          source: { id: "s-bad", nameTh: "used", nameEn: "used", sourceType: "COMMUNITY", status: "INACTIVE", domain: "used.example" },
          verifications: [],
        },
      }],
    };
    const searcher = vi.fn(async () => emptyPage());
    const out = await searchQuestionCatalog(
      "honda city ราคาเท่าไหร่",
      searcher as never,
      { exactSearch: vi.fn(async () => ({ results: [unofficialVariant], matchType: "exact_model", exactMatch: true })) } as never,
    );
    // the unofficial current price must not be presented as structured evidence
    const surfaced = out.flatMap((v) => v.prices ?? []);
    expect(surfaced.map((p) => p.amount)).not.toContain(1234567);
    // variant itself also fails catalog eligibility (no official price) → not returned
    expect(out).toEqual([]);
    // non-vacuous: fallback structured search actually ran
    expect(searcher).toHaveBeenCalled();
  });
});
