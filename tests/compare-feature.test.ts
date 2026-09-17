import { describe, expect, it } from "vitest";
import { onlyDifferentFields } from "../lib/compare/differences";
import { mapCatalogToCompareOptions } from "../lib/compare/selector";

const price = { amount: 1475000, currency: "THB", type: "LIST_PRICE", validFrom: "2025-01-01", validTo: null, observedAt: "2025-01-01", source: {} as never };
const variant = {
  id: "v1", nameTh: "HEV Smart", nameEn: "HEV Smart", slug: "hev-smart", modelYear: 2025,
  manufacturer: { id: "m", nameTh: "โตโยต้า", nameEn: "Toyota", slug: "toyota" },
  model: { id: "model", nameTh: "คัมรี", nameEn: "Camry", slug: "camry", modelYear: 2025 },
  fuelType: "Hybrid", prices: [price],
};

describe("compare selector and rows", () => {
  it("maps only API catalog data into selectable options", () => {
    expect(mapCatalogToCompareOptions({ results: [variant], total: 1, page: 1, limit: 100, hasMore: false })).toEqual([{ id: "v1", label: "HEV Smart", detail: "โตโยต้า · คัมรี · 2025", price: 1475000 }]);
  });

  it("removes only rows with identical values", () => {
    const fields = [{ key: "fuelType", label: "เชื้อเพลิง", values: ["Hybrid", "Hybrid"] }, { key: "price", label: "ราคา", values: [100, 200] }, { key: "range", label: "ระยะทาง", values: [null, null] }];
    expect(onlyDifferentFields(fields)).toEqual([fields[1]]);
  });
});
