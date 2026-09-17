import { describe, it, expect } from "vitest";
import { parseAutomotiveQuery } from "../lib/ai/retrieval/query-parser";

describe("search query parsing", () => {
  it("parses EV + price filter", () => {
    const q = parseAutomotiveQuery("EV ไม่เกิน 800,000");
    expect(q.type).toBe("search");
    if (q.type === "search") {
      expect(q.filters.fuelType).toBe("EV");
      expect(q.filters.maxPrice).toBe(800000);
    }
  });

  it("parses brand + price", () => {
    const q = parseAutomotiveQuery("BYD ราคาไม่เกิน 900,000");
    expect(q.type).toBe("search");
    if (q.type === "search") {
      expect(q.filters.brand).toBe("byd");
      expect(q.filters.maxPrice).toBe(900000);
    }
  });

  it("parses HEV filter", () => {
    const q = parseAutomotiveQuery("ไฮบริด ราคาไม่เกิน 1,500,000");
    expect(q.type).toBe("search");
    if (q.type === "search") {
      expect(q.filters.fuelType).toBe("HEV");
      expect(q.filters.maxPrice).toBe(1500000);
    }
  });

  it("parses comparison intent", () => {
    const q = parseAutomotiveQuery("Camry เทียบ Corolla Cross");
    expect(q.type).toBe("compare");
  });

  it("parses model name search", () => {
    const q = parseAutomotiveQuery("MG4");
    expect(q.type).toBe("search");
    if (q.type === "search") {
      expect(q.entities.length).toBeGreaterThan(0);
    }
  });

  it("parses count intent", () => {
    const q = parseAutomotiveQuery("MG มีกี่รุ่น");
    expect(q.type).toBe("count");
  });

  it("handles empty query", () => {
    const q = parseAutomotiveQuery("");
    expect(q.type).toBe("search");
  });
});
