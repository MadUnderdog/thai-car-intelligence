import { describe, it, expect } from "vitest";
import { normalizeThaiQuery } from "../../lib/search/thai-normalize";

/**
 * Focused tests for Thai→English normalizer consistency with evidence-gate-policy.
 *
 * Every Thai alias in THAI_MODEL_MAP must resolve to a value that matches
 * a CANONICAL_MODELS canonicalName (or alias) in evidence-gate-policy.ts.
 * This prevents the cross-file mismatch class of bugs.
 */

describe("Thai normalizer → canonical model consistency", () => {
  // ── MG ──

  it("เอส 5 → s5 ev (not s5)", () => {
    const result = normalizeThaiQuery("เอส 5");
    expect(result.resolvedModels).toContain("s5 ev");
    expect(result.resolvedModels).not.toContain("s5");
  });

  it("วีเอส → vs hev (not vs)", () => {
    const result = normalizeThaiQuery("วีเอส");
    expect(result.resolvedModels).toContain("vs hev");
    expect(result.resolvedModels).not.toContain("vs");
  });

  it("สิงโต → sealion 7 (not sealion)", () => {
    const result = normalizeThaiQuery("สิงโต");
    expect(result.resolvedModels).toContain("sealion 7");
    expect(result.resolvedModels).not.toContain("sealion");
  });

  it("สิงโต (alone) → model sealion 7", () => {
    const result = normalizeThaiQuery("สิงโต");
    expect(result.resolvedModels).toContain("sealion 7");
  });

  it("เอ็มจี สิงโต → normalizer resolves Thai→English independently (brand mg + model sealion 7)", () => {
    const result = normalizeThaiQuery("เอ็มจี สิงโต");
    expect(result.resolvedBrands).toContain("mg");
    // Normalizer resolves Thai→English independently of brand context.
    // Sealion 7 is actually a BYD model — the gate handles cross-brand rejection.
    expect(result.resolvedModels).toContain("sealion 7");
  });

  it("บีวายดี สิงโต → correct pairing: brand byd + model sealion 7", () => {
    const result = normalizeThaiQuery("บีวายดี สิงโต");
    expect(result.resolvedBrands).toContain("byd");
    expect(result.resolvedModels).toContain("sealion 7");
  });

  it("ไอเอ็ม 5 → im5", () => {
    const result = normalizeThaiQuery("ไอเอ็ม 5");
    expect(result.resolvedModels).toContain("im5");
  });

  it("ไอเอ็ม 6 → im6", () => {
    const result = normalizeThaiQuery("ไอเอ็ม 6");
    expect(result.resolvedModels).toContain("im6");
  });

  it("ซีเอส → zs", () => {
    const result = normalizeThaiQuery("ซีเอส");
    expect(result.resolvedModels).toContain("zs");
  });

  it("เอชเอส → hs", () => {
    const result = normalizeThaiQuery("เอชเอส");
    expect(result.resolvedModels).toContain("hs");
  });

  it("เอ็มจี 4 → mg4", () => {
    const result = normalizeThaiQuery("เอ็มจี 4");
    expect(result.resolvedModels).toContain("mg4");
  });

  it("เอพี → ep", () => {
    const result = normalizeThaiQuery("เอพี");
    expect(result.resolvedModels).toContain("ep");
  });

  it("เอพี พลัส → ep plus", () => {
    const result = normalizeThaiQuery("เอพี พลัส");
    expect(result.resolvedModels).toContain("ep plus");
  });

  it("เอพี+ → ep plus", () => {
    const result = normalizeThaiQuery("เอพี+");
    expect(result.resolvedModels).toContain("ep plus");
  });

  // ── Toyota ──

  it("โคโรลล่า → corolla altis (not corolla)", () => {
    const result = normalizeThaiQuery("โคโรลล่า");
    expect(result.resolvedModels).toContain("corolla altis");
    expect(result.resolvedModels).not.toContain("corolla");
  });

  it("ยาริส ครอส → yaris cross", () => {
    const result = normalizeThaiQuery("ยาริส ครอส");
    expect(result.resolvedModels).toContain("yaris cross");
  });

  it("ยาริสครอส (no space) → yaris cross", () => {
    const result = normalizeThaiQuery("ยาริสครอส");
    expect(result.resolvedModels).toContain("yaris cross");
  });

  it("คัมรี → camry", () => {
    const result = normalizeThaiQuery("คัมรี");
    expect(result.resolvedModels).toContain("camry");
  });

  it("ฟอร์จูนเนอร์ → fortuner", () => {
    const result = normalizeThaiQuery("ฟอร์จูนเนอร์");
    expect(result.resolvedModels).toContain("fortuner");
  });

  it("ไฮลักซ์ → hilux", () => {
    const result = normalizeThaiQuery("ไฮลักซ์");
    expect(result.resolvedModels).toContain("hilux");
  });

  // ── Honda ──

  it("ซูเปอร์วัน → super-one (ป variant)", () => {
    const result = normalizeThaiQuery("ฮอนด้า ซูเปอร์วัน");
    expect(result.resolvedModels).toContain("super-one");
  });

  it("ซุปเปอร์วัน → super-one (บ variant)", () => {
    const result = normalizeThaiQuery("ฮอนด้า ซุปเปอร์วัน");
    expect(result.resolvedModels).toContain("super-one");
  });

  it("ซิตี้ → city", () => {
    const result = normalizeThaiQuery("ฮอนด้า ซิตี้");
    expect(result.resolvedModels).toContain("city");
  });

  it("ซีวิค → civic", () => {
    const result = normalizeThaiQuery("ซีวิค");
    expect(result.resolvedModels).toContain("civic");
  });

  it("แอคคอร์ด → accord", () => {
    const result = normalizeThaiQuery("แอคคอร์ด");
    expect(result.resolvedModels).toContain("accord");
  });

  // ── BYD ──

  it("โดลฟิน → dolphin", () => {
    const result = normalizeThaiQuery("โดลฟิน");
    expect(result.resolvedModels).toContain("dolphin");
  });

  it("ซีล → seal", () => {
    const result = normalizeThaiQuery("ซีล");
    expect(result.resolvedModels).toContain("seal");
  });

  it("แอทโต 3 → atto-3", () => {
    const result = normalizeThaiQuery("แอทโต 3");
    expect(result.resolvedModels).toContain("atto-3");
  });

  // ── Tesla ──

  it("โมเดล 3 → model-3", () => {
    const result = normalizeThaiQuery("โมเดล 3");
    expect(result.resolvedModels).toContain("model-3");
  });

  it("โมเดล วาย → model-y", () => {
    const result = normalizeThaiQuery("โมเดล วาย");
    expect(result.resolvedModels).toContain("model-y");
  });

  // ── Mixed Thai + English queries ──

  it("MG สิงโต → normalizer resolves independently (brand mg + model sealion 7, cross-brand)", () => {
    const result = normalizeThaiQuery("MG สิงโต");
    expect(result.resolvedBrands).toContain("mg");
    // Sealion 7 is BYD; normalizer resolves Thai→English without brand validation.
    expect(result.resolvedModels).toContain("sealion 7");
  });

  it("โตโยต้า โคโรลล่า → brand toyota + model corolla altis", () => {
    const result = normalizeThaiQuery("โตโยต้า โคโรลล่า");
    expect(result.resolvedBrands).toContain("toyota");
    expect(result.resolvedModels).toContain("corolla altis");
  });

  it("ฮอนด้า ซุปเปอร์วัน → brand honda + model super-one", () => {
    const result = normalizeThaiQuery("ฮอนด้า ซุปเปอร์วัน");
    expect(result.resolvedBrands).toContain("honda");
    expect(result.resolvedModels).toContain("super-one");
  });

  it("เอ็มจี เอส 5 → brand mg + model s5 ev", () => {
    const result = normalizeThaiQuery("เอ็มจี เอส 5");
    expect(result.resolvedBrands).toContain("mg");
    expect(result.resolvedModels).toContain("s5 ev");
  });

  // ── Spacing / punctuation edge cases ──

  it("handles Thai with standard spacing: เอส 5", () => {
    const result = normalizeThaiQuery("เอส 5");
    expect(result.resolvedModels).toContain("s5 ev");
  });

  it("brand-only query resolves brand", () => {
    const result = normalizeThaiQuery("โตโยต้า");
    expect(result.resolvedBrands).toContain("toyota");
  });

  it("returns original query unchanged", () => {
    const q = "โคโรลล่า ราคาเท่าไหร่";
    const result = normalizeThaiQuery(q);
    expect(result.original).toBe(q);
  });

  it("additionalTerms are deduplicated", () => {
    const result = normalizeThaiQuery("โตโยต้า คัมรี");
    const unique = [...new Set(result.additionalTerms)];
    expect(result.additionalTerms).toEqual(unique);
  });
});
