/**
 * Adversarial behavior audit for the evidence gate (evidence-gate-policy.ts).
 * P12.6 — Hardened with canonical model identity, source-type defense-in-depth,
 * and 30+ safe regression assertions.
 *
 * Every test asserts the SAFE result. No test documents known-unsafe behavior.
 */
import { describe, it, expect } from "vitest";
import {
  applyEvidenceThresholds,
  gateVectorEvidence,
  VECTOR_STRICT_DISTANCE,
  VECTOR_MAX_DISTANCE,
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

// ── Source types ────────────────────────────────────────────────────────────
const VERIFIED_OFFICIAL = "OFFICIAL_MANUFACTURER";
const VERIFIED_BROCHURE = "OFFICIAL_BROCHURE";
const VERIFIED_SECONDARY = "VERIFIED_AUTOMOTIVE_REFERENCE";
const RESEARCH = "RESEARCH";
const UNVERIFIED = "UNVERIFIED";

// ── Tests ───────────────────────────────────────────────────────────────────

describe("Evidence gate — adversarial audit (P12.6)", () => {

  // ══════════════════════════════════════════════════════════════════════════
  // 1-4: Same-brand / wrong-model / wrong-brand / body-type mismatches
  // ══════════════════════════════════════════════════════════════════════════

  it("1: MG IM5 query rejects MG IM6 evidence (same brand, different model)", () => {
    const evidence = vec({
      id: "im6-ev",
      content: "MG IM6 SUV ราคาเริ่มต้น 1,299,000 บาท สมรรถนะและสเปค",
      distance: 0.25,
    });
    const result = gate("MG IM5 ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("im6-ev");
  });

  it("2: Honda City query rejects Toyota City evidence (same model, wrong brand)", () => {
    const evidence = vec({
      id: "toyota-city",
      content: "Toyota City sedan ราคา 600,000 บาท ปี 2024",
      distance: 0.25,
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("toyota-city");
  });

  it("3: Honda SUV query rejects City (sedan) evidence via body-type constraint", () => {
    const evidence = vec({
      id: "city-ev",
      content: "Honda City sedan ราคา 599,000 บาท รุ่นปี 2024",
      distance: 0.20,
    });
    const result = gate("Honda SUV ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("city-ev");
  });

  it("4: Honda sedan query rejects CR-V (SUV) evidence via body-type constraint", () => {
    const evidence = vec({
      id: "crv-ev",
      content: "Honda CR-V SUV ราคา 1,499,000 บาท รุ่นปี 2024",
      distance: 0.20,
    });
    const result = gate("Honda sedan ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("crv-ev");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 5: Exact variant and trim
  // ══════════════════════════════════════════════════════════════════════════

  it("5a: City Hatchback query accepts City Hatchback evidence (exact variant match)", () => {
    const evidence = vec({
      id: "city-hb",
      content: "Honda City Hatchback ราคา 799,000 บาท รุ่น RS",
      distance: 0.20,
    });
    const result = gate("Honda City Hatchback ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("city-hb");
  });

  it("5b: City Hatchback query rejects City sedan evidence (wrong body type)", () => {
    const evidence = vec({
      id: "city-sedan",
      content: "Honda City sedan ราคา 599,000 บาท รุ่น V",
      distance: 0.20,
    });
    const result = gate("Honda City Hatchback ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("city-sedan");
  });

  it("5c: Both Hatchback and sedan in same result — only Hatchback survives", () => {
    const evidences = [
      vec({ id: "city-hb", content: "Honda City Hatchback ราคา 799,000 บาท", distance: 0.15 }),
      vec({ id: "city-sedan", content: "Honda City sedan ราคา 599,000 บาท", distance: 0.18 }),
    ];
    const result = gate("Honda City Hatchback ราคา", evidences);
    expect(acceptedIds(result)).toContain("city-hb");
    expect(acceptedIds(result)).not.toContain("city-sedan");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 6: Thai aliases
  // ══════════════════════════════════════════════════════════════════════════

  it("6a: Thai query 'ฮอนด้า ซิตี้ ราคา' accepts Honda City evidence", () => {
    const evidence = vec({
      id: "city-th",
      content: "Honda City sedan ราคา 599,000 บาท รุ่นปี 2024",
      distance: 0.20,
    });
    const result = gate("ฮอนด้า ซิตี้ ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("city-th");
  });

  it("6b: Thai alias 'เอ็มจี โฟร์' accepts MG4 evidence", () => {
    const evidence = vec({
      id: "mg4-th",
      content: "MG4 hatchback ราคา 799,000 บาท",
      distance: 0.20,
    });
    const result = gate("เอ็มจี โฟร์ ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("mg4-th");
  });

  it("6c: Mixed Thai+English 'ฮอนด้า City ราคา' accepts Honda City evidence", () => {
    const evidence = vec({
      id: "city-mixed",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.20,
    });
    const result = gate("ฮอนด้า City ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("city-mixed");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 7: Short token collision — MG EP vs EP Plus
  // ══════════════════════════════════════════════════════════════════════════

  it("7a: MG EP query rejects MG EP Plus evidence (canonical identity mismatch)", () => {
    const evidence = vec({
      id: "ep-plus",
      content: "MG EP Plus sedan ราคา 999,000 บาท รุ่นปี 2024",
      distance: 0.25,
    });
    const result = gate("MG EP ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("ep-plus");
  });

  it("7b: MG EP Plus query rejects MG EP evidence (reverse direction)", () => {
    const evidence = vec({
      id: "ep-base",
      content: "MG EP sedan ราคา 799,000 บาท รุ่นปี 2024",
      distance: 0.25,
    });
    const result = gate("MG EP Plus ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("ep-base");
  });

  it("7c: MG EP query accepts MG EP evidence (exact match)", () => {
    const evidence = vec({
      id: "ep-exact",
      content: "MG EP sedan ราคา 799,000 บาท รุ่นปี 2024",
      distance: 0.25,
    });
    const result = gate("MG EP ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("ep-exact");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 8: Tesla Model Y vs Model 3
  // ══════════════════════════════════════════════════════════════════════════

  it("8a: Tesla Model Y query rejects Model 3 evidence (canonical identity mismatch)", () => {
    const evidence = vec({
      id: "model3-ev",
      content: "Tesla Model 3 sedan ราคา 1,290,000 บาท",
      distance: 0.20,
    });
    const result = gate("Tesla Model Y ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("model3-ev");
  });

  it("8b: Tesla Model 3 query rejects Model Y evidence (reverse direction)", () => {
    const evidence = vec({
      id: "modely-ev",
      content: "Tesla Model Y SUV ราคา 1,490,000 บาท",
      distance: 0.20,
    });
    const result = gate("Tesla Model 3 ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("modely-ev");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 9: MG IM5 vs IM6
  // ══════════════════════════════════════════════════════════════════════════

  it("9a: MG IM5 query rejects MG IM6 evidence", () => {
    const evidence = vec({
      id: "im6-for-im5",
      content: "MG IM6 SUV ราคา 1,299,000 บาท",
      distance: 0.25,
    });
    const result = gate("MG IM5 ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("im6-for-im5");
  });

  it("9b: MG IM6 query rejects MG IM5 evidence (reverse direction)", () => {
    const evidence = vec({
      id: "im5-for-im6",
      content: "MG IM5 sedan ราคา 1,099,000 บาท",
      distance: 0.25,
    });
    const result = gate("MG IM6 ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("im5-for-im6");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 10: Source type defense-in-depth
  // ══════════════════════════════════════════════════════════════════════════

  it("10a: RESEARCH evidence is rejected at the gate", () => {
    const evidence = vec({
      id: "research-ev",
      content: "Honda City sedan ราคา 599,000 บาท วิจัยเปรียบเทียบ",
      distance: 0.20,
      source: {
        id: "src-research",
        url: "https://research.example.com",
        titleTh: null,
        titleEn: null,
        sourceType: RESEARCH,
      },
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("research-ev");
  });

  it("10b: UNVERIFIED evidence is rejected at the gate", () => {
    const evidence = vec({
      id: "unverified-ev",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.20,
      source: {
        id: "src-unverified",
        url: "https://unverified.example.com",
        titleTh: null,
        titleEn: null,
        sourceType: UNVERIFIED,
      },
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("unverified-ev");
  });

  it("10c: VERIFIED official evidence is accepted when entity matches", () => {
    const evidence = vec({
      id: "official-ev",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.20,
      source: {
        id: "src-official",
        url: "https://honda.co.th",
        titleTh: null,
        titleEn: null,
        sourceType: VERIFIED_OFFICIAL,
      },
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("official-ev");
  });

  it("10d: VERIFIED secondary evidence is accepted when entity matches", () => {
    const evidence = vec({
      id: "secondary-ev",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.20,
      source: {
        id: "src-secondary",
        url: "https://headlight.in.th",
        titleTh: null,
        titleEn: null,
        sourceType: VERIFIED_SECONDARY,
      },
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("secondary-ev");
  });

  it("10e: VERIFIED brochure evidence is accepted", () => {
    const evidence = vec({
      id: "brochure-ev",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.20,
      source: {
        id: "src-brochure",
        url: "https://brochure.honda.co.th",
        titleTh: null,
        titleEn: null,
        sourceType: VERIFIED_BROCHURE,
      },
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("brochure-ev");
  });

  it("10f: missing/unknown source type is NOT silently treated as verified (fail-closed)", () => {
    const evidence = vec({
      id: "unknown-src",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.20,
      source: {
        id: "src-unknown",
        url: "https://unknown.example.com",
        titleTh: null,
        titleEn: null,
        sourceType: "SOME_NEW_TYPE",
      },
    });
    const result = gate("Honda City ราคา", [evidence]);
    // Unknown source type → fail-closed → rejected
    expect(acceptedIds(result)).not.toContain("unknown-src");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 11: Conflicting evidence (same model, different trims)
  // ══════════════════════════════════════════════════════════════════════════

  it("11: MG3 query accepts both HYBRID+ and non-hybrid evidence (both match 'mg3')", () => {
    const hybrid = vec({
      id: "mg3-hybrid",
      content: "MG3 HYBRID+ hatchback ราคา 799,000 บาท",
      distance: 0.20,
    });
    const nonHybrid = vec({
      id: "mg3-nonhybrid",
      content: "MG3 non-hybrid hatchback ราคา 599,000 บาท",
      distance: 0.22,
    });
    const result = gate("MG3 ราคา", [hybrid, nonHybrid]);
    expect(acceptedIds(result)).toContain("mg3-hybrid");
    expect(acceptedIds(result)).toContain("mg3-nonhybrid");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 12-13: Missing evidence / unrelated evidence
  // ══════════════════════════════════════════════════════════════════════════

  it("12: Tesla Model Y query rejects all unrelated evidence", () => {
    const evidences = [
      vec({
        id: "honda-city",
        content: "Honda City sedan ราคา 599,000 บาท ปี 2024",
        distance: 0.30,
      }),
      vec({
        id: "toyota-camry",
        content: "Toyota Camry hybrid ราคา 1,490,000 บาท",
        distance: 0.35,
      }),
    ];
    const result = gate("Tesla Model Y ราคา", evidences);
    expect(acceptedIds(result)).toHaveLength(0);
  });

  it("13: evidence with no brand in content is rejected when query has specific model", () => {
    const evidence = vec({
      id: "no-brand",
      content: " автомобил ราคา 599,000 บาท",
      distance: 0.20,
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("no-brand");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 14: Punctuation/spacing variants
  // ══════════════════════════════════════════════════════════════════════════

  it("14: query 'MG IM-5 ราคา' (with dash) accepts MG IM5 evidence", () => {
    const evidence = vec({
      id: "im5-dash",
      content: "MG IM5 sedan ราคา 1,099,000 บาท",
      distance: 0.20,
    });
    const result = gate("MG IM-5 ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("im5-dash");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 15: Generic "model" keyword
  // ══════════════════════════════════════════════════════════════════════════

  it("15: generic 'model' keyword does not match specific model evidence", () => {
    const evidence = vec({
      id: "generic-model",
      content: "Tesla Model 3 sedan ราคา 1,290,000 บาท",
      distance: 0.20,
    });
    // "model" is in THAI_QUERY_WORDS, so entitySpecificTerms may be empty.
    // But 'tesla' is NOT in the query tokens, so the brand consistency guard
    // must reject — a generic query must not accept brand-specific evidence.
    const result = gate("รถ model ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("generic-model");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 16: Brand-only queries
  // ══════════════════════════════════════════════════════════════════════════

  it("16: brand-only query 'Honda ราคา' accepts Honda City evidence", () => {
    const evidence = vec({
      id: "honda-city",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.20,
    });
    const result = gate("Honda ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("honda-city");
  });

  it("16b: brand-only query 'MG ราคา' accepts MG4 evidence", () => {
    const evidence = vec({
      id: "mg4-ev",
      content: "MG4 hatchback ราคา 799,000 บาท",
      distance: 0.20,
    });
    const result = gate("MG ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("mg4-ev");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 17: High-similarity wrong entity
  // ══════════════════════════════════════════════════════════════════════════

  it("17: Honda City Hatchback query rejects Honda City sedan (not just model match, wrong variant)", () => {
    const evidence = vec({
      id: "city-sedan-for-hb",
      content: "Honda City sedan ราคา 599,000 บาท รุ่น V",
      distance: 0.15,
    });
    const result = gate("Honda City Hatchback ราคา", [evidence]);
    // Canonical identity: "city" vs "city hatchback" — different identities
    // Body-type: sedan vs hatchback — conflicting
    expect(acceptedIds(result)).not.toContain("city-sedan-for-hb");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 18: Research-only → never promoted to verified factual answer
  // ══════════════════════════════════════════════════════════════════════════

  it("18: RESEARCH evidence for MG IM6 is rejected even with perfect entity match", () => {
    const evidence = vec({
      id: "research-im6",
      content: "MG IM6 SUV ราคา 1,299,000 บาท",
      distance: 0.20,
      source: {
        id: "src-research-im6",
        url: "https://research.example.com",
        titleTh: null,
        titleEn: null,
        sourceType: RESEARCH,
      },
    });
    const result = gate("MG IM6 ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("research-im6");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 19: Brand+body-type queries
  // ══════════════════════════════════════════════════════════════════════════

  it("19: brand+body-type query 'MG SUV ราคา' accepts MG IM6 evidence (SUV)", () => {
    const evidence = vec({
      id: "im6-suv",
      content: "MG IM6 SUV ราคา 1,299,000 บาท",
      distance: 0.20,
    });
    const result = gate("MG SUV ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("im6-suv");
  });

  it("19b: brand+body-type 'MG sedan ราคา' rejects MG IM6 evidence (SUV)", () => {
    const evidence = vec({
      id: "im6-sedan-q",
      content: "MG IM6 SUV ราคา 1,299,000 บาท",
      distance: 0.20,
    });
    const result = gate("MG sedan ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("im6-sedan-q");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 20: Entity missing from content
  // ══════════════════════════════════════════════════════════════════════════

  it("20: query 'Honda City ราคา' rejects evidence about Toyota Camry (no Honda/City in content)", () => {
    const evidence = vec({
      id: "camry-ev",
      content: "Toyota Camry hybrid ราคา 1,490,000 บาท",
      distance: 0.40,
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("camry-ev");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 21: Manufacturer mismatch embedded in prose
  // ══════════════════════════════════════════════════════════════════════════

  it("21: Honda City query rejects evidence mentioning 'Toyota City' in prose", () => {
    const evidence = vec({
      id: "prose-toyota",
      content: "เปรียบเทียบ Toyota City กับ Honda City ราคา 600,000 บาท",
      distance: 0.20,
    });
    const result = gate("Honda City ราคา", [evidence]);
    // Evidence mentions both Honda and Toyota — mixed-entity evidence must be
    // rejected for a single-entity query to prevent cross-brand contamination.
    // The canonical identity matcher finds Honda City in the evidence, but the
    // evidence also references Toyota City (wrong brand). The brand consistency
    // guard detects multiple brands in content when query specifies only one.
    expect(acceptedIds(result)).not.toContain("prose-toyota");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 22: BYD Atto 2 vs Atto 3
  // ══════════════════════════════════════════════════════════════════════════

  it("22a: BYD Atto 2 query rejects Atto 3 evidence", () => {
    const evidence = vec({
      id: "atto3-for-atto2",
      content: "BYD Atto 3 SUV ราคา 1,099,000 บาท",
      distance: 0.25,
    });
    const result = gate("BYD Atto 2 ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("atto3-for-atto2");
  });

  it("22b: BYD Atto 3 query rejects Atto 2 evidence (reverse)", () => {
    const evidence = vec({
      id: "atto2-for-atto3",
      content: "BYD Atto 2 SUV ราคา 799,000 บาท",
      distance: 0.25,
    });
    const result = gate("BYD Atto 3 ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("atto2-for-atto3");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 23: Toyota Yaris vs Yaris Cross
  // ══════════════════════════════════════════════════════════════════════════

  it("23a: Toyota Yaris query rejects Yaris Cross evidence", () => {
    const evidence = vec({
      id: "yaris-cross-for-yaris",
      content: "Toyota Yaris Cross SUV ราคา 899,000 บาท",
      distance: 0.25,
    });
    const result = gate("Toyota Yaris ราคา", [evidence]);
    // Yaris cross should be excluded from Yaris identity
    const accepted = acceptedIds(result);
    expect(accepted).not.toContain("yaris-cross-for-yaris");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 24: Broad compare intent
  // ══════════════════════════════════════════════════════════════════════════

  it("24: broad compare 'Honda vs Toyota ราคา' accepts evidence from both brands", () => {
    const hondaEv = vec({
      id: "honda-city",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.25,
    });
    const toyotaEv = vec({
      id: "toyota-camry",
      content: "Toyota Camry sedan ราคา 1,490,000 บาท",
      distance: 0.25,
    });
    const result = gate("Honda vs Toyota ราคา", [hondaEv, toyotaEv]);
    expect(acceptedIds(result)).toContain("honda-city");
    expect(acceptedIds(result)).toContain("toyota-camry");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 25: Unsupported / unknown
  // ══════════════════════════════════════════════════════════════════════════

  it("25: completely unrelated query 'Tesla Roadster ราคา' rejects Honda City evidence", () => {
    const evidence = vec({
      id: "city-ev",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.30,
    });
    const result = gate("Tesla Roadster ราคา", [evidence]);
    // Roadster not in canonical models, but Honda City is different brand
    expect(acceptedIds(result)).not.toContain("city-ev");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 26: Honda Civic Type R vs regular Civic
  // ══════════════════════════════════════════════════════════════════════════

  it("26: Honda Civic query accepts Civic evidence", () => {
    const evidence = vec({
      id: "civic-ev",
      content: "Honda Civic sedan ราคา 999,000 บาท",
      distance: 0.20,
    });
    const result = gate("Honda Civic ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("civic-ev");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 27: Distance boundary tests
  // ══════════════════════════════════════════════════════════════════════════

  it("27a: beyond entity-corroborated bound (>0.60) is rejected", () => {
    const evidence = vec({
      id: "far-ev",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.65,
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("far-ev");
  });

  it("27b: entity-corroborated evidence within wide bound (0.45-0.60) is accepted", () => {
    const evidence = vec({
      id: "wide-ev",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.50,
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("wide-ev");
  });

  it("27c: non-entity-corroborated evidence beyond strict distance is rejected", () => {
    const evidence = vec({
      id: "nomatch-far",
      content: "Toyota Camry hybrid ราคา 1,490,000 บาท",
      distance: 0.40,
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("nomatch-far");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 28-29: Empty/unavailable results
  // ══════════════════════════════════════════════════════════════════════════

  it("28: empty result returns empty", () => {
    const result = gate("Honda City ราคา", []);
    expect(result.evidence).toHaveLength(0);
    expect(result.available).toBe(true);
  });

  it("29: unavailable result is returned as-is", () => {
    const result: VectorSearchResult = { available: false, evidence: [] };
    const out = applyEvidenceThresholds("Honda City ราคา", result);
    expect(out.available).toBe(false);
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 30: Multiple evidence items — mixed accepted/rejected
  // ══════════════════════════════════════════════════════════════════════════

  it("30: mixed evidence — only matching verified evidence survives", () => {
    const evidences = [
      vec({ id: "city-ok", content: "Honda City sedan ราคา 599,000 บาท", distance: 0.20 }),
      vec({
        id: "city-research",
        content: "Honda City sedan ราคา 599,000 บาท",
        distance: 0.20,
        source: { id: "src-r", url: "https://r.example.com", titleTh: null, titleEn: null, sourceType: RESEARCH },
      }),
      vec({ id: "camry-far", content: "Toyota Camry sedan ราคา 1,490,000 บาท", distance: 0.40 }),
    ];
    const result = gate("Honda City ราคา", evidences);
    expect(acceptedIds(result)).toContain("city-ok");
    expect(acceptedIds(result)).not.toContain("city-research");
    expect(acceptedIds(result)).not.toContain("camry-far");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 31: Honda HR-V vs CR-V (same brand, different model)
  // ══════════════════════════════════════════════════════════════════════════

  it("31: Honda HR-V query rejects CR-V evidence", () => {
    const evidence = vec({
      id: "crv-for-hrv",
      content: "Honda CR-V SUV ราคา 1,499,000 บาท",
      distance: 0.25,
    });
    const result = gate("Honda HR-V ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("crv-for-hrv");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 32: Thai alias with brand consistency
  // ══════════════════════════════════════════════════════════════════════════

  it("32: 'ฮอนด้า ซิตี้ ราคา' rejects Toyota City evidence", () => {
    const evidence = vec({
      id: "toyota-city-th",
      content: "Toyota City sedan ราคา 600,000 บาท",
      distance: 0.20,
    });
    const result = gate("ฮอนด้า ซิตี้ ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("toyota-city-th");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 33: Evidence content has NO brand but matches model name
  // ══════════════════════════════════════════════════════════════════════════

  it("33: explicit brand+model query rejects evidence with NO brand (fail-closed contract)", () => {
    const evidence = vec({
      id: "no-brand-city",
      content: "City sedan ราคา 599,000 บาท รุ่นปี 2024",
      distance: 0.25,
    });
    const result = gate("Honda City ราคา", [evidence]);
    // Contract: explicit brand+model query + evidence with no brand identity → reject.
    // Evidence mentions "city" but has NO Honda/manufacturer identifier.
    // The gate must not silently weaken brand+model to model-only.
    expect(acceptedIds(result)).not.toContain("no-brand-city");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // 34: MG MG4 query vs MG IM5 evidence
  // ══════════════════════════════════════════════════════════════════════════

  it("34: MG MG4 query rejects MG IM5 evidence (different canonical models)", () => {
    const evidence = vec({
      id: "im5-for-mg4",
      content: "MG IM5 sedan ราคา 1,099,000 บาท",
      distance: 0.25,
    });
    const result = gate("MG4 ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("im5-for-mg4");
  });

});
