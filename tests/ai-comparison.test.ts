import { describe, expect, it, vi } from "vitest";
import { buildThaiRagPrompt } from "../lib/ai/prompts/rag-th";
import { validateCitations } from "../lib/ai/citations";
import { createUnavailableProvider } from "../lib/ai/provider-factory";
import { compareVariants } from "../lib/compare/compare";
import { POST as ask } from "../src/app/api/ai/ask/route";
import * as catalogSearch from "../lib/ai/retrieval/catalog-search";

describe("honest AI/RAG", () => {
  it("prompt forbids invention and requires ไม่พบข้อมูล", () => { const p = buildThaiRagPrompt("ราคาเท่าไร"); expect(p).toContain("ห้ามแต่ง"); expect(p).toContain("ไม่พบข้อมูล"); });
  it("rejects citations with unknown evidence or mismatched URL", () => { const evidence = [{ id: "e1", kind: "fact" as const, content: "x", sourcePageUrl: "https://example.com/a" }]; expect(validateCitations([{ evidenceId: "e1", sourcePageUrl: "https://example.com/b" }, { evidenceId: "e2", sourcePageUrl: "https://example.com/a" }], evidence)).toEqual([]); });
  it("is deterministic and unavailable without a key", async () => { const result = await createUnavailableProvider().chat({ question: "x", evidence: [] }); expect(result.status).toBe("unavailable"); expect(result.citations).toEqual([]); });
  it("returns 400 for missing or oversized Thai questions", async () => {
    const missing = await ask(new Request("http://localhost/api/ai/ask", { method: "POST", body: "{}", headers: { "content-type": "application/json" } }));
    expect(missing.status).toBe(400);
    const oversized = await ask(new Request("http://localhost/api/ai/ask", { method: "POST", body: JSON.stringify({ question: "ก".repeat(501) }), headers: { "content-type": "application/json" } }));
    expect(oversized.status).toBe(400);
  });
  it("returns an explicit insufficient-evidence response", async () => {
    vi.spyOn(catalogSearch, "searchQuestionCatalog").mockResolvedValueOnce([]);
    const response = await ask(new Request("http://localhost/api/ai/ask", { method: "POST", body: JSON.stringify({ question: "รถรุ่นที่ไม่มีในระบบ" }), headers: { "content-type": "application/json" } }));
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ status: "insufficient_evidence", answer: "ไม่พบข้อมูลที่ตรวจสอบได้สำหรับคำถามนี้", whyThisAnswer: [] });
  });
  it.skip("reports unavailable provider separately when structured evidence exists", async () => {
    const variant = {
      id: "camry-1", nameTh: "คัมรี่", nameEn: "Camry", slug: "camry", modelYear: 2025,
      manufacturer: { id: "toyota", nameTh: "โตโยต้า", nameEn: "Toyota", slug: "toyota" },
      model: { id: "camry", nameTh: "คัมรี่", nameEn: "Camry", slug: "camry", modelYear: 2025 },
      aliases: [], fuelType: null, prices: [],
    };
    vi.spyOn(catalogSearch, "searchQuestionCatalog").mockImplementation(async (q) => q.includes("Camry") || q.includes("camry") ? [variant] : []);
    const response = await ask(new Request("http://localhost/api/ai/ask", { method: "POST", body: JSON.stringify({ question: "Toyota Camry มีราคาเท่าไหร่" }), headers: { "content-type": "application/json" } }));
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ status: "unavailable", whyThisAnswer: [{ id: "variant:camry-1" }] });
  }, 15000);
});

describe("structured comparison", () => {
  it("keeps missing values null", async () => { const client = { variant: { findMany: async () => [{ id: "a", nameTh: "A", model: { nameTh: "M", manufacturer: { nameTh: "ค่าย" } }, specs: [], prices: [], battery: null, performance: null, warranty: null }] } } as never; const result = await compareVariants(["a", "b"], client); expect(result.variants[0].fields.rangeKm).toBeNull(); expect(result.fields.find((f) => f.key === "rangeKm")?.values).toEqual([null]); });
});
