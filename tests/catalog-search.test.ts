import { describe, expect, it, vi } from "vitest";
import { GET as getCars, parseCarQuery } from "../src/app/api/cars/route";
import { GET as getSearch, parseSearchQuery } from "../src/app/api/search/route";
import { validateSourceBundle } from "../lib/catalog/importer";
import * as catalogQueries from "../lib/catalog/queries";
import { listVariants } from "../lib/catalog/queries";
import type { PrismaClient } from "@prisma/client";

const validPriceProvenance = { url: "https://example.com/price", evidence: "Official price page" };

function request(path: string): Request {
  return new Request(`http://localhost${path}`);
}

describe("catalog query parsing", () => {
  it("parses supported car filters with bounded pagination", () => {
    expect(parseCarQuery(new URLSearchParams("manufacturer=MG&maxPrice=800000&limit=100&page=2"))).toMatchObject({ maxPrice: 800000, limit: 100, page: 2 });
  });
  it("applies safe pagination defaults and rejects excessive limits", () => {
    expect(parseSearchQuery(new URLSearchParams())).toMatchObject({ limit: 24, page: 1 });
    expect(parseSearchQuery(new URLSearchParams("limit=101"))).toBeNull();
    expect(parseSearchQuery(new URLSearchParams("page=0"))).toBeNull();
  });
  it("rejects invalid numeric and too-long filters", () => {
    expect(parseCarQuery(new URLSearchParams("maxPrice=-1"))).toBeNull();
    expect(parseSearchQuery(new URLSearchParams("maxPrice=nope"))).toBeNull();
    expect(parseSearchQuery(new URLSearchParams(`q=${"x".repeat(121)}`))).toBeNull();
  });
});

describe("catalog API outage handling", () => {
  it("returns 503 instead of treating a database failure as an empty catalog", async () => {
    vi.spyOn(catalogQueries, "listVariants").mockRejectedValueOnce(new Error("database offline"));
    const response = await getCars(request("/api/cars"));
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ error: "catalog_unavailable", results: [], total: 0, page: 1, limit: 24 });
  });
  it("includes search metadata on database failure", async () => {
    vi.spyOn(catalogQueries, "searchCatalog").mockRejectedValueOnce(new Error("database offline"));
    const response = await getSearch(request("/api/search?q=MG&limit=10"));
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ error: "catalog_unavailable", results: [], page: 1, limit: 10, vectorAvailable: false });
  });
});

describe("catalog database filters", () => {
  it("requires active sources and verified documents in the database predicate", async () => {
    const count = vi.fn().mockResolvedValue(0);
    const findMany = vi.fn().mockResolvedValue([]);
    const client = { variant: { count, findMany } } as unknown as PrismaClient;
    await listVariants({ q: "MG" }, client);
    const where = JSON.stringify(count.mock.calls[0][0].where);
    expect(where).toContain('"status":"ACTIVE"');
    expect(where).toContain('"status":"VERIFIED"');
    expect(where).toContain('"sourceType":{"in":["OFFICIAL_MANUFACTURER"');
  });
});

describe("source bundle validation", () => {
  const identity = { nameTh: "ชื่อ", nameEn: "Name", slug: "name" };
  it("rejects important facts without provenance", () => {
    const result = validateSourceBundle({ records: [{ manufacturer: identity, model: identity, variant: identity, facts: [{ key: "fuelType", value: "EV" }] }] });
    expect(result.success).toBe(false);
  });
  it("rejects non-THB prices", () => {
    const result = validateSourceBundle({ records: [{ manufacturer: identity, model: identity, variant: identity, prices: [{ amount: 100, currency: "USD", provenance: validPriceProvenance }] }] });
    expect(result.success).toBe(false);
  });
  it("accepts a provenance-bearing THB bundle without writing data", () => {
    const provenance = { url: "https://example.com/spec", evidence: "Official specification page" };
    const result = validateSourceBundle({ records: [{ manufacturer: identity, model: identity, variant: identity, prices: [{ amount: 100, provenance }], facts: [{ key: "fuelType", value: "EV", provenance }] }] });
    expect(result.success).toBe(true);
  });
  it("accepts an explicitly empty bundle", () => {
    expect(validateSourceBundle({ records: [] }).success).toBe(true);
  });
});
