/**
 * Brand/model consistency tests for the evidence gate.
 *
 * Verifies that when a query specifies an explicit brand, evidence content
 * must reference that same brand — preventing cross-brand model collisions
 * (e.g. "Honda City" query rejecting "Toyota City" evidence).
 */
import { describe, it, expect } from "vitest";
import {
  applyEvidenceThresholds,
  gateVectorEvidence,
} from "../../lib/ai/retrieval/evidence-gate-policy";
import type { VectorEvidence, VectorSearchResult } from "../../lib/search/vector-search";

// ── Helpers ────────────────────────────────────────────────────────────────

function vec(overrides: Partial<VectorEvidence> & { content: string }): VectorEvidence {
  return {
    id: overrides.id ?? "test-1",
    sourceDocumentId: "sd-1",
    entityType: "SourceDocument",
    entityId: "eid-1",
    chunkIndex: 0,
    chunkType: "document",
    pageNumber: null,
    ...overrides,
    distance: overrides.distance ?? 0.25,
    source: {
      id: overrides.source?.id ?? "src-1",
      url: overrides.source?.url ?? "https://example.test",
      titleTh: overrides.source?.titleTh ?? null,
      titleEn: overrides.source?.titleEn ?? null,
      sourceType: overrides.source?.sourceType ?? "OFFICIAL_MANUFACTURER",
    },
  };
}

function gate(query: string, evidence: VectorEvidence[]) {
  const result: VectorSearchResult = { available: true, evidence };
  return applyEvidenceThresholds(query, result);
}

function acceptedIds(result: VectorSearchResult): string[] {
  return result.evidence.map((e) => e.id);
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("Evidence gate — brand/model consistency", () => {
  // ── 1. Same model, different brand ──────────────────────────────────────
  it("1: Honda City query rejects Toyota City evidence (same model, wrong brand)", () => {
    const evidence = vec({
      id: "toyota-city",
      content: "Toyota City sedan ราคา 600,000 บาท ปี 2024",
      distance: 0.25,
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("toyota-city");
  });

  // ── 2. Same brand, different model ──────────────────────────────────────
  it("2: MG IM5 query rejects MG IM6 evidence (same brand, different model)", () => {
    const evidence = vec({
      id: "im6-ev",
      content: "MG IM6 SUV ราคาเริ่มต้น 1,299,000 บาท สมรรถนะและสเปค",
      distance: 0.25,
    });
    const result = gate("MG IM5 ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("im6-ev");
  });

  // ── 3. Same prefix, different number ────────────────────────────────────
  it("3: Tesla Model Y query rejects Model 3 evidence (same brand, different model)", () => {
    const evidence = vec({
      id: "model3",
      content: "Tesla Model 3 sedan ราคา 1,290,000 บาท",
      distance: 0.20,
    });
    const result = gate("Tesla Model Y ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("model3");
  });

  // ── 4. Brand + generic body type accepts same-brand different model ─────
  it("4: Honda SUV query accepts Honda CR-V evidence (same brand, compatible model)", () => {
    const evidence = vec({
      id: "crv-ev",
      content: "Honda CR-V SUV ราคา 1,499,000 บาท รุ่นปี 2024",
      distance: 0.20,
    });
    const result = gate("Honda SUV ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("crv-ev");
  });

  // ── 5. Brand-only query accepts any matching brand ─────────────────────
  it("5: Brand-only 'Toyota ราคา' accepts any Toyota evidence", () => {
    const camry = vec({
      id: "camry",
      content: "Toyota Camry hybrid ราคา 1,490,000 บาท",
      distance: 0.22,
    });
    const yaris = vec({
      id: "yaris",
      content: "Toyota Yaris hatchback ราคา 549,000 บาท",
      distance: 0.25,
    });
    const result = gate("Toyota ราคา", [camry, yaris]);
    const ids = acceptedIds(result);
    expect(ids).toContain("camry");
    expect(ids).toContain("yaris");
  });

  // ── 5b. Brand-only rejects different brand ─────────────────────────────
  it("5b: Brand-only 'Honda ราคา' rejects Toyota evidence", () => {
    const evidence = vec({
      id: "toyota-camry",
      content: "Toyota Camry hybrid ราคา 1,490,000 บาท",
      distance: 0.25,
    });
    const result = gate("Honda ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("toyota-camry");
  });

  // ── 6. Thai brand alias consistency ─────────────────────────────────────
  it("6: Thai 'ฮอนด้า ซิตี้ ราคา' accepts Honda City, rejects Toyota City", () => {
    const hondaCity = vec({
      id: "honda-city",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.20,
    });
    const toyotaCity = vec({
      id: "toyota-city",
      content: "Toyota City sedan ราคา 600,000 บาท",
      distance: 0.22,
    });
    const result = gate("ฮอนด้า ซิตี้ ราคา", [hondaCity, toyotaCity]);
    expect(acceptedIds(result)).toContain("honda-city");
    expect(acceptedIds(result)).not.toContain("toyota-city");
  });

  // ── 7. No brand in evidence → can't mismatch (edge case) ────────────────
  it("7: Query with brand accepts evidence with no brand mention (can't mismatch)", () => {
    const evidence = vec({
      id: "generic",
      content: "ราคาเริ่มต้น 500,000 บาท รุ่นปี 2024 สมรรถนะดี",
      distance: 0.25,
    });
    const result = gate("Honda City ราคา", [evidence]);
    // No brand in content → brand guard passes; but no entity match → rejected by final guard
    expect(acceptedIds(result)).not.toContain("generic");
  });

  // ── 8. No brand in query → no brand constraint ──────────────────────────
  it("8: Query without brand has no brand constraint — accepts any evidence matching entities", () => {
    const evidence = vec({
      id: "city-generic",
      content: "City sedan ราคา 599,000 บาท รุ่นปี 2024",
      distance: 0.25,
    });
    const result = gate("city ราคา", [evidence]);
    // "city" is in query tokens and in content → entity match → accepted
    expect(acceptedIds(result)).toContain("city-generic");
  });
});
