import { describe, expect, it } from "vitest";
import { parseAutomotiveQuery } from "../lib/ai/retrieval/query-parser";

describe("automotive query parser", () => {
  it("parses EV budget filter", () => {
    const result = parseAutomotiveQuery("EV ราคาไม่เกิน 800,000 มีรุ่นไหนบ้าง");
    expect(result.type).toBe("search");
    const search = result as Extract<typeof result, { type: "search" }>;
    expect(search.filters.fuelType).toBe("EV");
    expect(search.filters.maxPrice).toBe(800000);
  });

  it("parses Thai brand name", () => {
    const result = parseAutomotiveQuery("โตโยต้า มีกี่รุ่น");
    expect(result.type).toBe("count");
    const count = result as Extract<typeof result, { type: "count" }>;
    expect(count.brand).toBe("toyota");
  });

  it("parses comparison intent", () => {
    const result = parseAutomotiveQuery("Camry เทียบ Sealion 5");
    expect(result.type).toBe("compare");
    const compare = result as Extract<typeof result, { type: "compare" }>;
    expect(compare.entities.length).toBeGreaterThan(0);
  });

  it("parses cheapest query", () => {
    const result = parseAutomotiveQuery("รถถูกที่สุดราคาเท่าไหร่");
    expect(result.type).toBe("cheapest");
  });

  it("parses HEV filter", () => {
    const result = parseAutomotiveQuery("ไฮบริด ราคาไม่เกิน 1,000,000");
    expect(result.type).toBe("search");
    const search = result as Extract<typeof result, { type: "search" }>;
    expect(search.filters.fuelType).toBe("HEV");
    expect(search.filters.maxPrice).toBe(1000000);
  });

  it("parses brand + max price", () => {
    const result = parseAutomotiveQuery("MG ราคาไม่เกิน 800,000");
    expect(result.type).toBe("search");
    const search = result as Extract<typeof result, { type: "search" }>;
    expect(search.filters.brand).toBe("mg");
    expect(search.filters.maxPrice).toBe(800000);
  });

  it("extracts entities from model names", () => {
    const result = parseAutomotiveQuery("MG S5 EV PLUS ราคาเท่าไหร่");
    expect(result.type).toBe("search");
    const search = result as Extract<typeof result, { type: "search" }>;
    expect(search.entities.some((e) => e.includes("s5"))).toBe(true);
  });

  it("handles empty/unknown query", () => {
    const result = parseAutomotiveQuery("a b c");
    expect(result.type).toBe("search");
    const search = result as Extract<typeof result, { type: "search" }>;
    expect(search.filters.fuelType).toBeUndefined();
    expect(search.filters.maxPrice).toBeUndefined();
  });
});
