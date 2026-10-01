/**
 * P116 — Public car / compare / search UX contract tests (non-DOM layer).
 *
 * Red-before: written against base 3590131 BEFORE any implementation change.
 * Helper modules under lib/ux and lib/catalog/detail-queries do not exist yet —
 * they are loaded via dynamic import so each test fails individually.
 * Route tests use a fake @/lib/db-pg pool that captures SQL for assertions.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// ── fake pool ───────────────────────────────────────────────────────────────
const captured: { sql: string; params: any[] }[] = [];
const fakeRows: Record<string, any[]> = {};

vi.mock("@/lib/db-pg", () => ({
  default: {
    query: vi.fn(async (sql: string, params?: any[]) => {
      captured.push({ sql, params: params ?? [] });
      if (sql.includes(`FROM "CarModel" cm`)) return { rows: fakeRows.models ?? [] };
      if (sql.includes(`FROM "Variant" v`) && sql.includes(`JOIN "CarModel"`)) return { rows: fakeRows.variants ?? [] };
      if (sql.includes(`FROM "Price" p`)) return { rows: fakeRows.prices ?? [] };
      if (sql.includes(`"PerformanceSpec"`)) return { rows: fakeRows.perf ?? [] };
      if (sql.includes(`"DimensionsSpec"`)) return { rows: fakeRows.dims ?? [] };
      if (sql.includes(`"BatterySpec"`)) return { rows: fakeRows.batt ?? [] };
      if (sql.includes(`"ChargingSpec"`)) return { rows: fakeRows.charge ?? [] };
      if (sql.includes(`"VariantFeature"`)) return { rows: fakeRows.features ?? [] };
      return { rows: [] };
    }),
  },
}));

import { GET as getModels } from "../src/app/api/models/route";
import { GET as getCompare } from "../src/app/api/compare/route";

const UUID_A = "11111111-1111-4111-8111-111111111111";
const UUID_B = "22222222-2222-4222-8222-222222222222";
const UUID_C = "33333333-3333-4333-8333-333333333333";

/** The five conditions of lib/catalog/queries currentOfficialPrice, in SQL. */
const CHAIN_TOKENS = [
  `opsd.status = 'VERIFIED'`,
  `ops.status = 'ACTIVE'`,
  `ops."sourceType" IN`,
  `opbv.status = 'VERIFIED'`,
];

function pricesSql(calls: { sql: string }[]): string {
  const hit = calls.find((c) => c.sql.includes(`FROM "Price" p`));
  expect(hit, "expected the route to query Price rows").toBeTruthy();
  return hit!.sql;
}

async function loadHelper<T>(path: string): Promise<T | null> {
  try {
    return (await import(path)) as T;
  } catch {
    return null;
  }
}

beforeEach(() => {
  captured.length = 0;
  for (const key of Object.keys(fakeRows)) delete fakeRows[key];
});

// ── A. /api/models price eligibility ────────────────────────────────────────
describe("A. /api/models official price semantics (G1)", () => {
  it("A1: models SQL uses the full currentOfficialPrice chain (not sd-only)", async () => {
    fakeRows.models = [];
    await getModels(new Request("http://localhost/api/models?minPrice=100000&maxPrice=2000000"));
    const sql = captured.map((c) => c.sql).join("\n");
    for (const token of CHAIN_TOKENS) expect(sql).toContain(token);
    expect(sql).toContain(`p."isCurrent"`);
    // the loose legacy predicate alone must not be the only guard
    expect(sql).toContain(`FROM "SourceDocument" opsd`);
  });

  it("A3: q filter binds every referenced parameter (base LIMIT $N+2 had none → 503)", async () => {
    fakeRows.models = [];
    await getModels(new Request("http://localhost/api/models?q=city"));
    const call = captured[captured.length - 1];
    const maxIdx = Math.max(...[...call.sql.matchAll(/\$(\d+)/g)].map((m) => Number(m[1])));
    expect(maxIdx, `q-binding must reference only bound params (max $${maxIdx}, params ${call.params.length})`).toBeLessThanOrEqual(call.params.length);
  });

  it("D1: response rows carry compareVariantId for the compare contract", async () => {
    fakeRows.models = [
      { id: "m1", nameEn: "City", nameTh: "ซิตี้", slug: "city", mfrName: "Honda", mfrTh: "ฮอนด้า", mfrSlug: "honda", minPrice: 999000, maxPrice: 999000, variantCount: 2, primaryFuelType: "HEV", heroImage: null, compareVariantId: UUID_A },
    ];
    const res = await getModels(new Request("http://localhost/api/models"));
    const body = await res.json();
    expect(body.results[0]).toHaveProperty("compareVariantId", UUID_A);
  });
});

// ── C. /api/compare ─────────────────────────────────────────────────────────
describe("C. /api/compare contract (G2, G4, G12)", () => {
  const variantRow = (id: string, name: string) => ({
    id, nameEn: name, nameTh: name, slug: name.toLowerCase(),
    modelName: "Model", modelTh: "โมเดล", brand: "Brand", brandTh: "แบรนด์",
  });

  it("C1: compare price query uses the full currentOfficialPrice chain", async () => {
    fakeRows.variants = [variantRow(UUID_A, "Base"), variantRow(UUID_B, "Plus")];
    fakeRows.prices = [];
    await getCompare(new Request(`http://localhost/api/compare?ids=${UUID_A},${UUID_B}`));
    const sql = pricesSql(captured);
    for (const token of CHAIN_TOKENS) expect(sql).toContain(token);
    expect(sql).toContain(`p."isCurrent"`);
  });

  it("C2: response preserves the SELECTED id order even when the DB returns another order", async () => {
    fakeRows.variants = [variantRow(UUID_B, "Plus"), variantRow(UUID_A, "Base")]; // DB order ≠ request order
    fakeRows.prices = [];
    const res = await getCompare(new Request(`http://localhost/api/compare?ids=${UUID_A},${UUID_B}`));
    const body = await res.json();
    expect(body.comparison.map((c: any) => c.id)).toEqual([UUID_A, UUID_B]);
  });

  it("C6: exactly 2–4 id semantics — 1 id → 400, non-UUID rejected, >4 capped at 4", async () => {
    fakeRows.variants = [];
    const one = await getCompare(new Request(`http://localhost/api/compare?ids=${UUID_A}`));
    expect(one.status).toBe(400);
    const junk = await getCompare(new Request("http://localhost/api/compare?ids=abc,def"));
    expect(junk.status).toBe(400);
    const manyIds = [UUID_A, UUID_B, UUID_C, "44444444-4444-4444-8444-444444444444", "55555555-5555-4555-8555-555555555555"];
    fakeRows.variants = manyIds.slice(0, 4).map((id, i) => variantRow(id, `V${i}`));
    fakeRows.prices = [];
    await getCompare(new Request(`http://localhost/api/compare?ids=${manyIds.join(",")}`));
    const variantCall = captured.find((c) => c.sql.includes(`FROM "Variant" v`));
    expect(variantCall!.params[0]).toHaveLength(4);
  });

  it("C5: features rows keep their available flag (installed / not installed / unknown)", async () => {
    fakeRows.variants = [variantRow(UUID_A, "Base"), variantRow(UUID_B, "Plus")];
    fakeRows.prices = [];
    fakeRows.features = [
      { variantId: UUID_A, slug: "sunroof", nameEn: "Sunroof", nameTh: "ซันรูฟ", standard: true, available: true, sourceTier: "primary_official" },
      { variantId: UUID_A, slug: "hud", nameEn: "HUD", nameTh: "HUD", standard: false, available: false, sourceTier: "secondary_automotive_media" },
      { variantId: UUID_B, slug: "sunroof", nameEn: "Sunroof", nameTh: "ซันรูฟ", standard: false, available: true, sourceTier: "primary_official" },
    ];
    const res = await getCompare(new Request(`http://localhost/api/compare?ids=${UUID_A},${UUID_B}`));
    const body = await res.json();
    const a = body.comparison.find((c: any) => c.id === UUID_A);
    const b = body.comparison.find((c: any) => c.id === UUID_B);
    expect(a.features.find((f: any) => f.slug === "sunroof")).toMatchObject({ available: true });
    expect(a.features.find((f: any) => f.slug === "hud")).toMatchObject({ available: false });
    // variant B has no hud row → unknown (not "not installed")
    expect(b.features.find((f: any) => f.slug === "hud")).toBeUndefined();

    const cv = await loadHelper<{ featureCellText: (features: any[], slug: string) => string }>("../lib/ux/compare-view");
    expect(cv, "lib/ux/compare-view must exist").not.toBeNull();
    expect(cv!.featureCellText(a.features, "sunroof")).toBe("✓");
    expect(cv!.featureCellText(a.features, "hud")).toBe("✗");
    expect(cv!.featureCellText(b.features, "hud")).toBe("ไม่มีข้อมูล");
  });
});

// ── F/E/G/H/I helpers (dynamic import → red-before = module missing) ────────
describe("F. search UI states are truthful", () => {
  it("F1/F2/F3: resolveSearchUiState distinguishes loading / empty / error / ok", async () => {
    const m = await loadHelper<{ resolveSearchUiState: (input: { loading: boolean; ok: boolean; results: unknown[] }) => string }>("../lib/ux/search-view");
    expect(m, "lib/ux/search-view must exist").not.toBeNull();
    expect(m!.resolveSearchUiState({ loading: true, ok: true, results: [] })).toBe("loading");
    expect(m!.resolveSearchUiState({ loading: false, ok: false, results: [] })).toBe("error");
    expect(m!.resolveSearchUiState({ loading: false, ok: true, results: [] })).toBe("empty");
    expect(m!.resolveSearchUiState({ loading: false, ok: true, results: [{}] })).toBe("ok");
  });

  it("F4: compare error mapping tells the truth for need_at_least_2", async () => {
    const m = await loadHelper<{ compareErrorMessage: (code: string) => string }>("../lib/ux/compare-view");
    expect(m, "lib/ux/compare-view must exist").not.toBeNull();
    expect(m!.compareErrorMessage("need_at_least_2")).toBe("กรุณาเลือกรถอย่างน้อย 2 รุ่น");
    expect(m!.compareErrorMessage("variants_not_found")).toBe("ไม่พบรถที่เลือก");
  });
});

describe("E. SearchClient consumes the REAL P115 response", () => {
  // Exact shape of an /api/search hit post-P115 (CatalogVariant nested).
  const apiResponse = {
    results: [
      {
        id: UUID_A, nameEn: "e:HEV RS", nameTh: "อีเฮฟ รเอส", slug: "e-hev-rs", modelYear: 2026,
        manufacturer: { id: "mf1", nameTh: "ฮอนด้า", nameEn: "Honda", slug: "honda", status: "ACTIVE" },
        model: { id: "m1", nameTh: "ซิตี้ แฮทช์แบ็ก", nameEn: "City Hatchback", slug: "city-hatchback", modelYear: null },
        aliases: [], fuelType: "HEV",
        prices: [{ amount: 999000, currency: "THB", type: "EXACT_CURRENT_MSRP_VERIFIED", validFrom: "2026-01-01T00:00:00.000Z", validTo: null, observedAt: "2026-09-01T00:00:00.000Z",
          source: { id: "sd1", url: "https://www.honda.co.th/price", titleTh: null, titleEn: "Honda price", documentStatus: "VERIFIED", verificationStatus: "VERIFIED", verifiedAt: "2026-09-01T00:00:00.000Z",
            source: { id: "s1", nameTh: "ฮอนด้า", nameEn: "Honda", type: "OFFICIAL_MANUFACTURER", domain: "honda.co.th" } } }],
      },
    ],
    total: 1, page: 1, limit: 24, hasMore: false,
    vectorAvailable: true, searchMode: "hybrid",
    evidence: [{ id: "v1", entityType: "Variant", entityId: UUID_A, sourceType: "OFFICIAL_MANUFACTURER", distance: 0.12, content: "…", source: { id: "s1", url: "https://www.honda.co.th", name: "Honda", domain: "honda.co.th" } }],
  };

  it("E1: live-shaped response has NESTED manufacturer/model and NO flat legacy fields", async () => {
    // documents why the old client (r.manufacturerSlug / r.modelName / r.fuelType…) broke
    const row: any = apiResponse.results[0];
    expect(row.manufacturer.slug).toBe("honda");
    expect(row.model.slug).toBe("city-hatchback");
    expect(Object.keys(row)).not.toContain("manufacturerSlug");
    expect(Object.keys(row)).not.toContain("modelName");
  });

  it("E2+E3: mapSearchResponse builds correct links, keeps exact model name, price, mode", async () => {
    const m = await loadHelper<{
      mapSearchResponse: (data: any, ok: boolean) => { state: string; rows: any[]; searchMode: string | null; evidenceCount: number };
    }>("../lib/ux/search-view");
    expect(m, "lib/ux/search-view must exist").not.toBeNull();
    const view = m!.mapSearchResponse(apiResponse, true);
    expect(view.state).toBe("ok");
    expect(view.searchMode).toBe("hybrid");
    expect(view.evidenceCount).toBe(1);
    const row = view.rows[0];
    expect(row.nameEn).toBe("e:HEV RS"); // exact model result not lost
    expect(row.link).toBe("/cars/honda/city-hatchback"); // never /cars/undefined/undefined
    expect(row.manufacturerName).toBe("Honda");
    expect(row.priceAmount).toBe(999000);
    expect(view.rows.every((r) => !r.link.includes("undefined"))).toBe(true);
    // deterministic (K1)
    expect(m!.mapSearchResponse(apiResponse, true)).toEqual(view);
  });

  it("H3: price provenance URL survives into the search view", async () => {
    const m = await loadHelper<{ mapSearchResponse: (data: any, ok: boolean) => any }>("../lib/ux/search-view");
    expect(m, "lib/ux/search-view must exist").not.toBeNull();
    const view = m!.mapSearchResponse(apiResponse, true);
    expect(view.rows[0].priceSourceUrl).toBe("https://www.honda.co.th/price");
    expect(view.rows[0].priceSourceName).toBe("Honda");
  });
});

// ── B/G/H/I: detail page builders + view helpers ────────────────────────────
describe("B/G. vehicle detail query builders + evidence flags", () => {
  it("G1: detail model lookup enforces BOTH slugs + ACTIVE on model and manufacturer", async () => {
    const m = await loadHelper<{ detailModelLookupSql: string }>("../lib/catalog/detail-queries");
    expect(m, "lib/catalog/detail-queries must exist").not.toBeNull();
    const sql = m!.detailModelLookupSql;
    expect(sql).toContain(`cm.slug = $1`);
    expect(sql).toContain(`m.slug = $2`);
    expect(sql).toContain(`cm.status = 'ACTIVE'`);
    expect(sql).toContain(`m.status = 'ACTIVE'`);
  });

  it("B2: research rows come only from sd.status <> 'VERIFIED' documents", async () => {
    const m = await loadHelper<{ researchRowsSql: string }>("../lib/catalog/detail-queries");
    expect(m, "lib/catalog/detail-queries must exist").not.toBeNull();
    expect(m!.researchRowsSql).toContain(`sd.status <> 'VERIFIED'`);
  });

  it("B1: detail variant price join uses the full currentOfficialPrice chain", async () => {
    const m = await loadHelper<{ variantRowsSql: string }>("../lib/catalog/detail-queries");
    expect(m, "lib/catalog/detail-queries must exist").not.toBeNull();
    const sql = m!.variantRowsSql;
    for (const token of CHAIN_TOKENS) expect(sql).toContain(token);
    expect(sql).toContain(`p."isCurrent"`);
  });

  it("B3: specEvidenceFlags marks official only for primary_official rows", async () => {
    const m = await loadHelper<{ specEvidenceFlags: (rows: { sourceTier?: string | null }[]) => boolean }>("../lib/ux/detail-view");
    expect(m, "lib/ux/detail-view must exist").not.toBeNull();
    expect(m!.specEvidenceFlags([{ sourceTier: "primary_official" }])).toBe(true);
    expect(m!.specEvidenceFlags([{ sourceTier: "secondary_automotive_media" }])).toBe(false);
    expect(m!.specEvidenceFlags([{ sourceTier: null }])).toBe(false);
    expect(m!.specEvidenceFlags([])).toBe(false);
    expect(m!.specEvidenceFlags([{ sourceTier: "primary_official" }, { sourceTier: "secondary_automotive_media" }])).toBe(true);
  });
});

// ── I. image / brochure fallback (Blueprint 86/87) ──────────────────────────
describe("I. image and brochure fallback never invent assets", () => {
  it("I1: no image → placeholder with official-site link when known, else no link", async () => {
    const m = await loadHelper<{ imageBlock: (images: any[], officialUrl: string | null) => { kind: string; href: string | null } }>("../lib/ux/detail-view");
    expect(m, "lib/ux/detail-view must exist").not.toBeNull();
    expect(m!.imageBlock([], "https://www.toyota.co.th")).toEqual({ kind: "fallback", href: "https://www.toyota.co.th" });
    expect(m!.imageBlock([], null)).toEqual({ kind: "placeholder", href: null });
    expect(m!.imageBlock([{ url: "https://img/x.jpg", role: "hero" }], null).kind).toBe("image");
  });

  it("I2: no brochure + no official source → plain fallback text, no invented href", async () => {
    const m = await loadHelper<{ brochureBlock: (doc: any, officialUrl: string | null) => any }>("../lib/ux/detail-view");
    expect(m, "lib/ux/detail-view must exist").not.toBeNull();
    expect(m!.brochureBlock(null, null)).toMatchObject({ title: "โบรชัวร์จากผู้ผลิต", href: null });
    expect(m!.brochureBlock(null, "https://www.mg.co.th")).toMatchObject({ title: "โบรชัวร์จากผู้ผลิต", href: "https://www.mg.co.th" });
  });

  it("I3: verified brochure doc keeps title/url/source/date/verified", async () => {
    const m = await loadHelper<{ brochureBlock: (doc: any, officialUrl: string | null) => any }>("../lib/ux/detail-view");
    expect(m, "lib/ux/detail-view must exist").not.toBeNull();
    const block = m!.brochureBlock(
      { title: "Price List 2026", url: "https://www.honda.co.th/p.pdf", sourceName: "Honda", verifiedAt: "2026-08-01T00:00:00.000Z", documentStatus: "VERIFIED" },
      null,
    );
    expect(block).toMatchObject({ title: "Price List 2026", href: "https://www.honda.co.th/p.pdf", sourceName: "Honda", verified: true });
  });
});

// ── D. CarsPage ↔ /api/compare end-to-end contract (fake pool) ──────────────
describe("D. compare entry from /cars", () => {
  it("D-1: two compareVariantIds from /api/models are accepted by /api/compare", async () => {
    fakeRows.models = [
      { id: "m1", nameEn: "City", nameTh: "ซิตี้", slug: "city", mfrName: "Honda", mfrTh: "ฮอนด้า", mfrSlug: "honda", minPrice: 999000, maxPrice: 999000, variantCount: 2, primaryFuelType: "HEV", heroImage: null, compareVariantId: UUID_A },
      { id: "m2", nameEn: "Yaris", nameTh: "ยาริส", slug: "yaris", mfrName: "Toyota", mfrTh: "โตโยต้า", mfrSlug: "toyota", minPrice: 559000, maxPrice: 559000, variantCount: 1, primaryFuelType: "Petrol", heroImage: null, compareVariantId: UUID_B },
    ];
    const modelsRes = await getModels(new Request("http://localhost/api/models"));
    const modelsBody = await modelsRes.json();
    const ids = modelsBody.results.map((r: any) => r.compareVariantId);
    expect(new Set(ids).size).toBe(2);
    expect(ids.every((id: any) => typeof id === "string" && id.includes("-"))).toBe(true);

    captured.length = 0;
    fakeRows.variants = [
      { id: UUID_A, nameEn: "e:HEV", nameTh: "อีเฮฟ", slug: "e-hev", modelName: "City", modelTh: "ซิตี้", brand: "Honda", brandTh: "ฮอนด้า" },
      { id: UUID_B, nameEn: "1.5 G", nameTh: "1.5 จี", slug: "15-g", modelName: "Yaris", modelTh: "ยาริส", brand: "Toyota", brandTh: "โตโยต้า" },
    ];
    fakeRows.prices = [];
    const compareRes = await getCompare(new Request(`http://localhost/api/compare?ids=${ids.join(",")}`));
    expect(compareRes.status).toBe(200);
    const compareBody = await compareRes.json();
    expect(compareBody.comparison.map((c: any) => c.id)).toEqual(ids);
  });
});
