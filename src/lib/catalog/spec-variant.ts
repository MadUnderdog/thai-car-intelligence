/**
 * P121 — pick the detail page's spec representative variant.
 *
 * The "สเปคหลัก" section previously bound every row to variants[0]
 * (ordered by verified price ASC NULLS LAST), so a model whose first
 * variant had a price but no typed spec rows rendered
 * "ยังไม่มีข้อมูลยืนยัน" everywhere while a sibling variant of the SAME
 * model carried full PerformanceSpec/DimensionsSpec/BatterySpec/
 * ChargingSpec data. Selection: most non-null typed-spec fields; ties
 * keep the incoming order; empty input → null. Pure function, no JSX.
 */

type SpecBearing = {
  powerKw?: number | null;
  torqueNm?: number | null;
  rangeKm?: number | null;
  batteryKwh?: number | null;
  batteryChemistry?: string | null;
  chargeDcKw?: number | null;
  chargeAcKw?: number | null;
  dimensionsMm?: string | null;
  wheelbaseMm?: number | null;
  groundClearanceMm?: number | null;
  warrantyYears?: number | null;
  warrantyKm?: number | null;
};

export function pickSpecVariant<T extends SpecBearing>(variants: T[]): T | null {
  if (!variants || variants.length === 0) return null;
  let best: T | null = null;
  let bestScore = -1;
  for (const v of variants) {
    const score =
      (v.powerKw != null ? 1 : 0) +
      (v.torqueNm != null ? 1 : 0) +
      (v.rangeKm != null ? 1 : 0) +
      (v.batteryKwh != null ? 1 : 0) +
      (v.batteryChemistry != null ? 1 : 0) +
      (v.chargeDcKw != null ? 1 : 0) +
      (v.chargeAcKw != null ? 1 : 0) +
      (v.dimensionsMm != null ? 1 : 0) +
      (v.wheelbaseMm != null ? 1 : 0) +
      (v.groundClearanceMm != null ? 1 : 0) +
      (v.warrantyYears != null ? 1 : 0) +
      (v.warrantyKm != null ? 1 : 0);
    // strictly greater → ties keep the FIRST (incoming price-first) order
    if (score > bestScore) {
      bestScore = score;
      best = v;
    }
  }
  return best;
}
