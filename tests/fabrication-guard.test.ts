import { describe, expect, it, vi } from "vitest";
import { evaluateEvidenceGate, buildInsufficientEvidenceResponse } from "../lib/ai/evidence-gate";
import { buildThaiRagPrompt } from "../lib/ai/prompts/rag-th";
import { POST as ask } from "../src/app/api/ai/ask/route";
import * as catalogSearch from "../lib/ai/retrieval/catalog-search";

describe("fabrication guard", () => {
  it("returns verified when price and variant evidence exist", () => {
    const evidence = [
      { id: "variant:1", kind: "fact" as const, content: "โตโยต้า คัมรี HEV Premium", metadata: {} },
      { id: "price:1:0", kind: "fact" as const, content: "ราคา 1659000 THB", sourcePageUrl: "https://toyota.co.th", official: true, metadata: {} },
    ];
    const gate = evaluateEvidenceGate(evidence);
    expect(gate.confidence).toBe("verified");
    expect(gate.hasPriceEvidence).toBe(true);
    expect(gate.hasVariantEvidence).toBe(true);
  });

  it("returns insufficient when no variant or price evidence", () => {
    const evidence = [
      { id: "embedding:1", kind: "fact" as const, content: "some random text", sourcePageUrl: "https://example.com", official: false, metadata: {} },
    ];
    const gate = evaluateEvidenceGate(evidence);
    expect(gate.confidence).toBe("insufficient");
    expect(gate.missingDataDescription.length).toBeGreaterThan(0);
  });

  it("returns partial when variant exists but no price", () => {
    const evidence = [
      { id: "variant:1", kind: "fact" as const, content: "โตโยต้า คัมรี", metadata: {} },
    ];
    const gate = evaluateEvidenceGate(evidence);
    expect(gate.confidence).toBe("partial");
  });

  it("builds Thai insufficient response with suggestion", () => {
    const gate = { confidence: "insufficient" as const, hasPriceEvidence: false, hasSpecEvidence: false, hasVariantEvidence: false, officialSourceCount: 0, totalEvidenceCount: 0, missingDataDescription: ["ไม่พบรุ่นรถที่ตรงกับคำถาม"] };
    const result = buildInsufficientEvidenceResponse("รถอะไร", gate);
    expect(result.answer).toContain("ไม่พบข้อมูลยืนยัน");
    expect(result.answer).toContain("ไม่พบรุ่นรถที่ตรงกับคำถาม");
    expect(result.confidence).toBe("insufficient");
  });

  it("prompt enforces Thai language", () => {
    const prompt = buildThaiRagPrompt("test");
    expect(prompt).toContain("ภาษาไทยเท่านั้น");
    expect(prompt).toContain("ห้ามแต่งข้อเท็จจริง");
  });
});

describe("fabrication guard integration", () => {
  it("blocks fabrication when no evidence found", async () => {
    vi.spyOn(catalogSearch, "searchQuestionCatalog").mockResolvedValueOnce([]);
    const response = await ask(new Request("http://localhost/api/ai/ask", { method: "POST", body: JSON.stringify({ question: "Ferrari Roma ราคาเท่าไหร่" }), headers: { "content-type": "application/json" } }));
    const data = await response.json();
    expect(data.status).toBe("insufficient_evidence");
    expect(data.answer).toContain("ไม่พบข้อมูล");
  });

  it.skip("allows answer when variant+price evidence exist", async () => {
    const variant = { id: "camry-premium", nameTh: "HEV Premium", nameEn: "HEV Premium", slug: "hev-premium", modelYear: null,
      manufacturer: { id: "toyota", nameTh: "โตโยต้า", nameEn: "Toyota", slug: "toyota" },
      model: { id: "camry", nameTh: "คัมรี", nameEn: "Camry", slug: "camry", modelYear: null },
      aliases: [], fuelType: null,
      prices: [{ amount: 1659000, currency: "THB", type: "LIST_PRICE", validFrom: new Date().toISOString(), validTo: null, observedAt: new Date().toISOString(),
        source: { id: "s1", url: "https://toyota.co.th/model/camry", titleTh: null, titleEn: "Toyota Camry", documentStatus: "VERIFIED", verificationStatus: "VERIFIED", verifiedAt: new Date().toISOString(),
          source: { id: "src1", nameTh: "แหล่งข้อมูลทางการ", nameEn: "Toyota", type: "OFFICIAL_MANUFACTURER", domain: "toyota.co.th" } } }],
    };
    vi.spyOn(catalogSearch, "searchQuestionCatalog").mockResolvedValueOnce([variant]);
    const response = await ask(new Request("http://localhost/api/ai/ask", { method: "POST", body: JSON.stringify({ question: "Toyota Camry HEV Premium ราคาเท่าไหร่" }), headers: { "content-type": "application/json" } }));
    const data = await response.json();
    // Should NOT be insufficient_evidence since variant+price exist
    expect(data.status).not.toBe("insufficient_evidence");
    expect(data.confidence).toBeDefined();
  });
});
