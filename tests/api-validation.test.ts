import { describe, expect, it } from "vitest";
import { parseCarQuery } from "../src/app/api/cars/route";
import { parseSearchQuery } from "../src/app/api/search/route";
import { isValidUuid, validateFuelType, validateLimit, validatePage } from "../lib/validation/api-params";

describe("api-params validation", () => {
  describe("validateFuelType", () => {
    it("accepts valid fuel types", () => {
      expect(validateFuelType("BEV")).toBe("BEV");
      expect(validateFuelType("hev")).toBe("HEV");
      expect(validateFuelType("ICE")).toBe("ICE");
      expect(validateFuelType("PHEV")).toBe("PHEV");
    });

    it("returns undefined for invalid fuel types", () => {
      expect(validateFuelType("diesel")).toBeUndefined();
      expect(validateFuelType("petrol")).toBeUndefined();
      expect(validateFuelType("")).toBeUndefined();
      expect(validateFuelType(null)).toBeUndefined();
    });
  });

  describe("isValidUuid", () => {
    it("accepts valid UUIDs", () => {
      expect(isValidUuid("550e8400-e29b-41d4-a716-446655440000")).toBe(true);
      expect(isValidUuid("550E8400-E29B-41D4-A716-446655440000")).toBe(true);
    });

    it("rejects invalid UUIDs", () => {
      expect(isValidUuid("not-a-uuid")).toBe(false);
      expect(isValidUuid("550e8400-e29b-41d4-a716")).toBe(false);
      expect(isValidUuid("")).toBe(false);
      expect(isValidUuid("550e8400e29b41d4a716446655440000")).toBe(false); // no dashes
    });
  });

  describe("validateLimit", () => {
    it("returns parsed limit within bounds", () => {
      expect(validateLimit("10")).toBe(10);
      expect(validateLimit("1")).toBe(1);
      expect(validateLimit("100")).toBe(100);
    });

    it("returns default when not provided", () => {
      expect(validateLimit(null, 24)).toBe(24);
      expect(validateLimit(null)).toBeNull();
    });

    it("returns null for invalid values", () => {
      expect(validateLimit("0")).toBeNull();
      expect(validateLimit("-1")).toBeNull();
      expect(validateLimit("101")).toBeNull();
      expect(validateLimit("abc")).toBeNull();
    });
  });

  describe("validatePage", () => {
    it("returns parsed page", () => {
      expect(validatePage("1")).toBe(1);
      expect(validatePage("100")).toBe(100);
    });

    it("returns null for invalid values", () => {
      expect(validatePage("0")).toBeNull();
      expect(validatePage("-1")).toBeNull();
      expect(validatePage("abc")).toBeNull();
    });
  });
});

describe("parseCarQuery validation", () => {
  it("returns null for invalid limit", () => {
    expect(parseCarQuery(new URLSearchParams("limit=0"))).toBeNull();
    expect(parseCarQuery(new URLSearchParams("limit=101"))).toBeNull();
    expect(parseCarQuery(new URLSearchParams("limit=abc"))).toBeNull();
  });

  it("returns null for invalid page", () => {
    expect(parseCarQuery(new URLSearchParams("page=0"))).toBeNull();
    expect(parseCarQuery(new URLSearchParams("page=-1"))).toBeNull();
  });

  it("returns null for invalid maxPrice", () => {
    expect(parseCarQuery(new URLSearchParams("maxPrice=-1"))).toBeNull();
    expect(parseCarQuery(new URLSearchParams("maxPrice=abc"))).toBeNull();
  });

  it("filters out invalid fuelType", () => {
    const result = parseCarQuery(new URLSearchParams("fuelType=diesel"));
    expect(result).not.toBeNull();
    expect(result!.fuelType).toBeUndefined();
  });

  it("passes through valid fuelType", () => {
    const result = parseCarQuery(new URLSearchParams("fuelType=BEV"));
    expect(result!.fuelType).toBe("BEV");
  });

  it("accepts valid params", () => {
    const result = parseCarQuery(new URLSearchParams("manufacturer=MG&maxPrice=800000&limit=100&page=2"));
    expect(result).toMatchObject({ maxPrice: 800000, limit: 100, page: 2, manufacturer: "MG" });
  });
});

describe("parseSearchQuery validation", () => {
  it("returns null for query exceeding max length", () => {
    expect(parseSearchQuery(new URLSearchParams(`q=${"x".repeat(121)}`))).toBeNull();
  });

  it("returns null for invalid limit", () => {
    expect(parseSearchQuery(new URLSearchParams("limit=0"))).toBeNull();
    expect(parseSearchQuery(new URLSearchParams("limit=101"))).toBeNull();
  });

  it("applies defaults when params missing", () => {
    const result = parseSearchQuery(new URLSearchParams());
    expect(result).toMatchObject({ limit: 24, page: 1 });
  });

  it("filters out invalid fuelType", () => {
    const result = parseSearchQuery(new URLSearchParams("fuelType=petrol"));
    expect(result).not.toBeNull();
    expect(result!.fuelType).toBeUndefined();
  });
});
