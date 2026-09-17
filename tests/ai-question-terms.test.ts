import { describe, expect, it } from "vitest";
import { extractQuestionTerms } from "../lib/ai/retrieval/question-terms";
import { searchQuestionCatalog } from "../lib/ai/retrieval/catalog-search";

describe("AI question entity extraction", () => {
  it("extracts Toyota Camry from a Thai price question", () => {
    expect(extractQuestionTerms("Toyota Camry มีราคาเท่าไหร่")).toEqual(["toyota", "camry"]);
  });

  it("extracts MG S5 EV X+ model tokens", () => {
    expect(extractQuestionTerms("MG S5 EV X+ ราคาเท่าไหร่")).toEqual(["mg", "s5", "ev", "x"]);
  });

  it("does not treat an unknown natural-language question as one entity", () => {
    const terms = extractQuestionTerms("รถรุ่นที่ไม่มีในระบบ มีราคาเท่าไหร่");
    expect(terms).not.toContain("รถรุ่นที่ไม่มีในระบบ มีราคาเท่าไหร่");
    expect(terms).not.toContain("มี");
    expect(terms).not.toContain("ราคา");
    expect(terms).not.toContain("เท่าไหร่");
  });

  it("returns no candidates for stop-word-only questions", () => {
    expect(extractQuestionTerms("มี ราคา เท่าไหร่ how much is the car")).toEqual([]);
  });

  it("falls back from the full question and deduplicates structured results", async () => {
    const variant = { id: "camry-1" } as never;
    const queries: string[] = [];
    const results = await searchQuestionCatalog("Toyota Camry มีราคาเท่าไหร่", async ({ q }) => {
      queries.push(q);
      return { results: q === "camry" || q === "toyota" ? [variant] : [], total: q ? 1 : 0, page: 1, limit: 8, hasMore: false };
    });
    expect(queries.some((q) => q.includes("toyota") || q.includes("camry"))).toBe(true);
    expect(results).toEqual([variant]);
  });
});
