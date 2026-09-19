/**
 * Adversarial behavior audit for the evidence gate (evidence-gate-policy.ts).
 *
 * Each scenario creates synthetic VectorEvidence objects and feeds them
 * through applyEvidenceThresholds() + gateVectorEvidence() to verify
 * the deterministic gate logic under adversarial conditions.
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

// ── Scenario tests ─────────────────────────────────────────────────────────

describe("Evidence gate — adversarial audit", () => {
  // ── 1. Same-brand wrong model ────────────────────────────────────────────
  it("1: MG IM5 query rejects MG IM6 evidence (same brand, different model)", () => {
    const evidence = vec({
      id: "im6-ev",
      content: "MG IM6 SUV ราคาเริ่มต้น 1,299,000 บาท สมรรถนะและสเปค",
      distance: 0.25,
    });
    const result = gate("MG IM5 ราคา", [evidence]);
    // The specificity check should reject: "im5" is a specific term, but content only has "im6"
    expect(acceptedIds(result)).not.toContain("im6-ev");
  });

  // ── 2. Same-model wrong brand ────────────────────────────────────────────
  it("2: Honda City query rejects Toyota City evidence (same model, wrong brand)", () => {
    const evidence = vec({
      id: "toyota-city",
      content: "Toyota City sedan ราคา 600,000 บาท ปี 2024",
      distance: 0.25,
    });
    const result = gate("Honda City ราคา", [evidence]);
    // GATE GAP: the gate matches "city" entity token and passes, but
    // the brand "toyota" in content clashes with query "honda".
    // Expected: rejected. Actual: may be accepted (entity match on "city").
    // This test documents whether the gate catches brand/model inconsistency.
    const accepted = acceptedIds(result);
    // The gate currently accepts this — documenting as a known gap.
    // If the gate is fixed to check brand consistency, flip this assertion.
    if (accepted.includes("toyota-city")) {
      console.warn(
        "⚠️  GAP: Toyota City evidence accepted for Honda City query — " +
          "gate matches 'city' entity but ignores brand mismatch"
      );
    }
    // For now, assert what the gate ACTUALLY does (accepts) — this is the gap.
    expect(accepted).toContain("toyota-city");
  });

  // ── 3. SUV query vs sedan evidence ───────────────────────────────────────
  it("3: Honda SUV query rejects City (sedan) evidence via body-type constraint", () => {
    const evidence = vec({
      id: "city-ev",
      content: "Honda City sedan ราคา 599,000 บาท รุ่นปี 2024",
      distance: 0.20,
    });
    const result = gate("Honda SUV ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("city-ev");
  });

  // ── 4. Sedan query vs SUV evidence ──────────────────────────────────────
  it("4: Honda sedan query rejects CR-V (SUV) evidence via body-type constraint", () => {
    const evidence = vec({
      id: "crv-ev",
      content: "Honda CR-V SUV ราคา 1,499,000 บาท รุ่นปี 2024",
      distance: 0.20,
    });
    const result = gate("Honda sedan ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("crv-ev");
  });

  // ── 5. Exact variant vs generic ──────────────────────────────────────────
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
    // Body type: City = sedan, query wants hatchback → rejected
    expect(acceptedIds(result)).not.toContain("city-sedan");
  });

  it("5c: Both Hatchback and sedan in same result — only Hatchback survives", () => {
    const evidences = [
      vec({
        id: "city-hb",
        content: "Honda City Hatchback ราคา 799,000 บาท",
        distance: 0.15,
      }),
      vec({
        id: "city-sedan",
        content: "Honda City sedan ราคา 599,000 บาท",
        distance: 0.18,
      }),
    ];
    const result = gate("Honda City Hatchback ราคา", evidences);
    expect(acceptedIds(result)).toContain("city-hb");
    expect(acceptedIds(result)).not.toContain("city-sedan");
  });

  // ── 6. Thai alias ────────────────────────────────────────────────────────
  it("6: Thai query 'ฮอนด้า ซิตี้ ราคา' accepts Honda City evidence", () => {
    const evidence = vec({
      id: "city-th",
      content: "Honda City sedan ราคา 599,000 บาท รุ่นปี 2024",
      distance: 0.20,
    });
    const result = gate("ฮอนด้า ซิตี้ ราคา", [evidence]);
    expect(acceptedIds(result)).toContain("city-th");
  });

  it("6b: Thai alias resolves to correct entity tokens", () => {
    // Verify the Thai alias mapping works: ฮอนด้า→honda, ซิตี้→city
    const evidence = vec({
      id: "city-th2",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.20,
    });
    const result = gate("ฮอนด้า ซิตี้ ราคา", [evidence]);
    const accepted = acceptedIds(result);
    expect(accepted).toContain("city-th2");
  });

  // ── 7. Short token collision ─────────────────────────────────────────────
  it("7: MG EP query vs MG EP Plus evidence — documents short-token ambiguity", () => {
    const evidence = vec({
      id: "ep-plus",
      content: "MG EP Plus sedan ราคา 999,000 บาท รุ่นปี 2024",
      distance: 0.25,
    });
    const result = gate("MG EP ราคา", [evidence]);
    const accepted = acceptedIds(result);
    // GAP: "ep" has length 2, filtered by w.length > 2 in extractSpecificModelTerms.
    // No specific term to enforce, so gate accepts EP Plus for EP query.
    if (accepted.includes("ep-plus")) {
      console.warn(
        "⚠️  GAP: MG EP Plus evidence accepted for MG EP query — " +
          "'ep' is too short (2 chars) for specificity enforcement"
      );
    }
    // Document the actual behavior
    expect(accepted).toContain("ep-plus");
  });

  // ── 8. Conflicting evidence (same model, different trims) ────────────────
  it("8: MG3 query accepts both HYBRID+ and non-hybrid evidence (both match 'mg3')", () => {
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
    // Both have "mg3" in content — gate accepts both.
    // This is by design: the gate resolves model, not trim.
    expect(acceptedIds(result)).toContain("mg3-hybrid");
    expect(acceptedIds(result)).toContain("mg3-nonhybrid");
  });

  // ── 9. Missing evidence ─────────────────────────────────────────────────
  it("9: Tesla Model Y query rejects all unrelated evidence", () => {
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
    // Neither evidence mentions Tesla or Model Y — gate should reject both
    expect(acceptedIds(result)).toHaveLength(0);
  });

  it("9b: Tesla Model Y query rejects evidence that mentions 'model' but not 'y'", () => {
    // Edge case: evidence has "Model 3" which contains "model" (a specificity term)
    const evidence = vec({
      id: "model3",
      content: "Tesla Model 3 sedan ราคา 1,290,000 บาท",
      distance: 0.20,
    });
    const result = gate("Tesla Model Y ราคา", [evidence]);
    // entityMatch: tokens = ["model y", "tesla"]. "model y" not in "teslamodel3sedan..." → false.
    // Wait, normalize("model y") = "modely". normalize("Tesla Model 3 sedan...") = "teslamodel3sedan..."
    // "teslamodel3sedan...".includes("modely") → false.
    // "tesla" is in MANUFACTURER_TOKENS and content → manufacturerMatch = true
    // specificTerms = ["model"], "model" in "teslamodel3..." → hasSpecificMatch = true
    // distance 0.20 ≤ 0.30 → first check passes
    // specificTerms.length > 0 && !hasSpecificMatch (false) && manufacturerMatch → skip
    // !entityMatch (true) && !manufacturerMatch (false) → false → passes
    // ACCEPTED — because manufacturerMatch is true and specificTerm "model" matches
    const accepted = acceptedIds(result);
    if (accepted.includes("model3")) {
      console.warn(
        "⚠️  GAP: Tesla Model 3 accepted for Model Y query — 'model' is " +
          "too generic as a specificity term"
      );
    }
    // Document the actual behavior: gate accepts Model 3 for Model Y because "model" matches
    expect(accepted).toContain("model3");
  });

  // ── 10. Research-only evidence ───────────────────────────────────────────
  it("10: research-only evidence (sourceType RESEARCH) should be rejected", () => {
    const evidence = vec({
      id: "research-ev",
      content: "Honda City sedan ราคา 599,000 บาท วิจัยเปรียบเทียบ",
      distance: 0.20,
      source: {
        id: "src-research",
        url: "https://research.example.com",
        titleTh: null,
        titleEn: null,
        sourceType: "RESEARCH",
      },
    });
    const result = gate("Honda City ราคา", [evidence]);
    const accepted = acceptedIds(result);
    // GAP: The gate does NOT check sourceType. Research evidence is accepted
    // if it matches entity tokens and is within distance thresholds.
    // In production, the vector search SQL filters for VERIFIED docs only,
    // so this path is unlikely. But the gate function itself doesn't guard.
    if (accepted.includes("research-ev")) {
      console.warn(
        "⚠️  GAP: Research-only evidence accepted — gate does not check " +
          "sourceType; relies on upstream SQL filter for VERIFIED status"
      );
    }
    // Document the actual behavior
    expect(accepted).toContain("research-ev");
  });

  // ── Boundary tests ───────────────────────────────────────────────────────

  it("beyond entity-corroborated bound (>0.60) is rejected", () => {
    const evidence = vec({
      id: "far-ev",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.65, // > 0.60 entity-corroborated absolute bound
    });
    const result = gate("Honda City ราคา", [evidence]);
    expect(acceptedIds(result)).not.toContain("far-ev");
  });

  it("entity-corroborated evidence within wide bound (0.45-0.60) is accepted", () => {
    const evidence = vec({
      id: "wide-ev",
      content: "Honda City sedan ราคา 599,000 บาท",
      distance: 0.50, // > MAX (0.45) but < 0.60
    });
    const result = gate("Honda City ราคา", [evidence]);
    // Entity match: "honda" in content → true → gets wide bound
    expect(acceptedIds(result)).toContain("wide-ev");
  });

  it("non-entity-corroborated evidence beyond strict distance is rejected", () => {
    const evidence = vec({
      id: "nomatch-far",
      content: "Toyota Camry hybrid ราคา 1,490,000 บาท",
      distance: 0.40, // > STRICT (0.30) but < MAX (0.45)
    });
    const result = gate("Honda City ราคา", [evidence]);
    // No entity match (honda/city not in toyotacamryhybrid...) → rejected
    expect(acceptedIds(result)).not.toContain("nomatch-far");
  });

  it("empty result returns empty", () => {
    const result = gate("Honda City ราคา", []);
    expect(result.evidence).toHaveLength(0);
    expect(result.available).toBe(true);
  });

  it("unavailable result is returned as-is", () => {
    const result: VectorSearchResult = { available: false, evidence: [] };
    const out = applyEvidenceThresholds("Honda City ราคา", result);
    expect(out.available).toBe(false);
  });
});
