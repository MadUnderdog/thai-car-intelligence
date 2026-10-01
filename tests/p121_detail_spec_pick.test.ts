/**
 * P121 — detail page spec-representative selection (red-before).
 *
 * Red-before: written against HEAD 8fda850 BEFORE implementation.
 * Evidenced defect (real browser + curl against /cars/mg/mg-s5):
 *   the detail "สเปคหลัก" section binds EVERY spec row to variants[0],
 *   which is ordered by verified price ASC NULLS LAST — so a model whose
 *   first variant has a verified price but NO typed spec rows renders
 *   "ยังไม่มีข้อมูลยืนยัน" for every spec even though a SIBLING variant of
 *   the same model has full PerformanceSpec/DimensionsSpec/BatterySpec/
 *   ChargingSpec rows (mg-s5: long-range price-only first, s5-ev typed
 *   specs second). A truthful unavailable state must not be shown while
 *   real verified-tier data exists for the model.
 *
 * Contract: pickSpecVariant() selects the variant with the MOST non-null
 * typed-spec fields; ties keep the incoming (price-first) order; empty
 * input returns null.
 */
import { describe, it, expect } from "vitest";
import { pickSpecVariant } from "../src/lib/catalog/spec-variant";

type V = {
  name: string;
  powerKw: number | null;
  torqueNm: number | null;
  rangeKm: number | null;
  batteryKwh: number | null;
  dimensionsMm: string | null;
  warrantyYears: number | null;
};

const longRange: V = {
  name: "long-range",
  powerKw: null,
  torqueNm: null,
  rangeKm: null,
  batteryKwh: null,
  dimensionsMm: null,
  warrantyYears: null,
};
const s5Ev: V = {
  name: "s5-ev",
  powerKw: 130,
  torqueNm: 280,
  rangeKm: 420,
  batteryKwh: 61.1,
  dimensionsMm: "4325x1815x1530",
  warrantyYears: null,
};

describe("P121 pickSpecVariant", () => {
  it("picks the sibling variant that actually has typed specs", () => {
    const picked = pickSpecVariant([longRange, s5Ev]);
    expect(picked?.name).toBe("s5-ev");
  });

  it("keeps incoming order on ties (price-first representative preserved)", () => {
    const a = { ...s5Ev, name: "a" };
    const b = { ...s5Ev, name: "b" };
    expect(pickSpecVariant([a, b])?.name).toBe("a");
  });

  it("returns the only variant when it has no specs (honest fallback)", () => {
    expect(pickSpecVariant([longRange])?.name).toBe("long-range");
  });

  it("returns null for an empty variant list", () => {
    expect(pickSpecVariant([])).toBeNull();
  });
});
