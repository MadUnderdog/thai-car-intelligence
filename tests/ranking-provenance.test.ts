import { describe, expect, it, vi, beforeEach } from "vitest";

/**
 * Ranking query provenance bypass tests — verify that:
 * 1. getCheapestVariant / getMostExpensiveVariant apply verified-current-official filter
 * 2. Unverified prices cannot win cheapest/most-expensive
 * 3. Provenance comes from the DB, not fabricated
 * 4. Returns null when no verified prices exist
 */

// ── Mock helpers ──────────────────────────────────────────────────────────

const officialSourceTypes = [
  "OFFICIAL_MANUFACTURER",
  "OFFICIAL_MANUFACTURER_BROCHURE",
  "OFFICIAL_MANUFACTURER_PRICE_LIST",
  "OFFICIAL_MANUFACTURER_PRESS_RELEASE",
];

/** The canonical currentOfficialPrice filter used by the module. */
const currentOfficialPrice = {
  isCurrent: true,
  sourceDocument: {
    AND: [
      { status: "VERIFIED", source: { status: "ACTIVE" }, verifications: { some: { status: "VERIFIED" } } },
      { source: { sourceType: { in: [...officialSourceTypes] }, status: "ACTIVE" } },
    ],
  },
};

/** Build a fake Prisma client whose price.findFirst captures its args. */
function mockPrisma(firstResult: any | null) {
  const findFirst = vi.fn().mockResolvedValue(firstResult);
  const variantWhere = vi.fn().mockResolvedValue([]);
  const count = vi.fn().mockResolvedValue(0);
  return {
    price: { findFirst },
    variant: { count, findMany: variantWhere },
    // Expose captured args for assertions
    get capturedPriceWhere() { return findFirst.mock.calls[0]?.[0]; },
  } as any;
}

// ── Tests ─────────────────────────────────────────────────────────────────

describe("ranking query provenance bypass fix", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getCheapestVariant", () => {
    it("returns null when no verified prices exist", async () => {
      const mock = mockPrisma(null);
      const { getCheapestVariant } = await import("../lib/catalog/queries");
      const result = await getCheapestVariant(mock);
      expect(result).toBeNull();
      // The Prisma query must use currentOfficialPrice
      expect(mock.price.findFirst).toHaveBeenCalledTimes(1);
      const args = mock.price.findFirst.mock.calls[0][0];
      expect(args.where).toEqual(currentOfficialPrice);
      expect(args.orderBy).toEqual({ amount: "asc" });
    });

    it("returns null when variant is not ACTIVE", async () => {
      const mock = mockPrisma({ variant: null });
      const { getCheapestVariant } = await import("../lib/catalog/queries");
      const result = await getCheapestVariant(mock);
      expect(result).toBeNull();
    });

    it("applies currentOfficialPrice filter (not just isCurrent=true)", async () => {
      const mock = mockPrisma(null);
      const { getCheapestVariant } = await import("../lib/catalog/queries");
      await getCheapestVariant(mock);
      const args = mock.price.findFirst.mock.calls[0][0];

      // Must require VERIFIED source document
      expect(args.where).toEqual(currentOfficialPrice);

      // Variant include must filter ACTIVE only
      const variantInclude = args.include.variant;
      expect(variantInclude.where).toEqual({
        status: "ACTIVE",
        model: { status: "ACTIVE", manufacturer: { status: "ACTIVE" } },
      });
    });

    it("returns variant with real provenance from the DB (not fabricated)", async () => {
      const now = new Date().toISOString();
      const mockResult = {
        variant: {
          id: "v1",
          nameTh: "COROLLA ALTIS",
          nameEn: "COROLLA ALTIS",
          slug: "corolla-altis",
          modelYear: 2025,
          fuelType: "Petrol",
          aliases: [],
          specs: [],
          prices: [
            {
              amount: 899000,
              currency: "THB",
              priceType: "official",
              validFrom: new Date("2025-01-01"),
              validTo: null,
              observedAt: new Date(),
              sourceDocument: {
                id: "sd1",
                url: "https://toyota.co.th/brochure",
                canonicalUrl: "https://toyota.co.th/brochure",
                titleTh: "Toyota Brochure 2025",
                titleEn: "Toyota Brochure 2025",
                status: "VERIFIED",
                source: {
                  id: "s1",
                  nameTh: "Toyota Thailand",
                  nameEn: "Toyota Thailand",
                  sourceType: "OFFICIAL_MANUFACTURER_BROCHURE",
                  domain: "toyota.co.th",
                },
                verifications: [
                  { status: "VERIFIED", verifiedAt: new Date() },
                ],
              },
            },
          ],
          model: {
            id: "m1",
            nameTh: "COROLLA ALTIS",
            nameEn: "COROLLA ALTIS",
            slug: "corolla-altis",
            modelYear: 2025,
            manufacturer: {
              id: "man1",
              nameTh: "โตโยต้า",
              nameEn: "Toyota",
              slug: "toyota",
            },
          },
        },
      };
      const mock = mockPrisma(mockResult);
      const { getCheapestVariant } = await import("../lib/catalog/queries");
      const result = await getCheapestVariant(mock);

      expect(result).not.toBeNull();
      expect(result!.id).toBe("v1");

      // Provenance must come from real DB data, not fabricated
      const price = result!.prices[0];
      expect(price.source.id).toBe("sd1");
      expect(price.source.url).toContain("toyota.co.th");
      expect(price.source.documentStatus).toBe("VERIFIED");
      expect(price.source.verificationStatus).toBe("VERIFIED");
      expect(price.source.source.type).toBe("OFFICIAL_MANUFACTURER_BROCHURE");
      expect(price.source.source.domain).toBe("toyota.co.th");

      // Must NOT have fabricated values
      expect(price.source.source.type).not.toBe("database");
      expect(price.source.documentStatus).not.toBe("active");
    });
  });

  describe("getMostExpensiveVariant", () => {
    it("returns null when no verified prices exist", async () => {
      const mock = mockPrisma(null);
      const { getMostExpensiveVariant } = await import("../lib/catalog/queries");
      const result = await getMostExpensiveVariant(mock);
      expect(result).toBeNull();
      // Must use currentOfficialPrice filter with desc order
      const args = mock.price.findFirst.mock.calls[0][0];
      expect(args.where).toEqual(currentOfficialPrice);
      expect(args.orderBy).toEqual({ amount: "desc" });
    });

    it("applies currentOfficialPrice filter (not just isCurrent=true)", async () => {
      const mock = mockPrisma(null);
      const { getMostExpensiveVariant } = await import("../lib/catalog/queries");
      await getMostExpensiveVariant(mock);
      const args = mock.price.findFirst.mock.calls[0][0];

      // Must require VERIFIED source document + VERIFIED brochure + official source type
      expect(args.where).toEqual(currentOfficialPrice);
    });

    it("returns variant with real provenance from the DB", async () => {
      const mockResult = {
        variant: {
          id: "v2",
          nameTh: "CAMRY",
          nameEn: "CAMRY",
          slug: "camry",
          modelYear: 2025,
          fuelType: "Hybrid",
          aliases: [],
          specs: [],
          prices: [
            {
              amount: 1799000,
              currency: "THB",
              priceType: "official",
              validFrom: new Date("2025-01-01"),
              validTo: null,
              observedAt: new Date(),
              sourceDocument: {
                id: "sd2",
                url: "https://toyota.co.th/price-list",
                canonicalUrl: "https://toyota.co.th/price-list",
                titleTh: "Toyota Price List",
                titleEn: "Toyota Price List",
                status: "VERIFIED",
                source: {
                  id: "s2",
                  nameTh: "Toyota Thailand",
                  nameEn: "Toyota Thailand",
                  sourceType: "OFFICIAL_MANUFACTURER_PRICE_LIST",
                  domain: "toyota.co.th",
                },
                verifications: [
                  { status: "VERIFIED", verifiedAt: new Date() },
                ],
              },
            },
          ],
          model: {
            id: "m2",
            nameTh: "CAMRY",
            nameEn: "CAMRY",
            slug: "camry",
            modelYear: 2025,
            manufacturer: {
              id: "man1",
              nameTh: "โตโยต้า",
              nameEn: "Toyota",
              slug: "toyota",
            },
          },
        },
      };
      const mock = mockPrisma(mockResult);
      const { getMostExpensiveVariant } = await import("../lib/catalog/queries");
      const result = await getMostExpensiveVariant(mock);

      expect(result).not.toBeNull();
      expect(result!.id).toBe("v2");

      // Provenance must be real
      const price = result!.prices[0];
      expect(price.source.id).toBe("sd2");
      expect(price.source.documentStatus).toBe("VERIFIED");
      expect(price.source.verificationStatus).toBe("VERIFIED");
      expect(price.source.source.type).toBe("OFFICIAL_MANUFACTURER_PRICE_LIST");
    });
  });

  describe("mapRow is removed", () => {
    it("queries.ts no longer exports mapRow", async () => {
      const mod = await import("../lib/catalog/queries");
      expect((mod as any).mapRow).toBeUndefined();
    });
  });

  describe("unverified prices are excluded from ranking", () => {
    it("getCheapestVariant ignores prices without VERIFIED sourceDocument", async () => {
      // Simulate: findFirst returns null (no verified-official prices pass the filter)
      const mock = mockPrisma(null);
      const { getCheapestVariant } = await import("../lib/catalog/queries");
      const result = await getCheapestVariant(mock);

      // Even if the DB has prices, none pass the currentOfficialPrice filter
      expect(result).toBeNull();
      // The filter must be currentOfficialPrice (which requires VERIFIED + official)
      const args = mock.price.findFirst.mock.calls[0][0];
      expect(args.where).toEqual(currentOfficialPrice);
    });

    it("getMostExpensiveVariant ignores prices without VERIFIED sourceDocument", async () => {
      const mock = mockPrisma(null);
      const { getMostExpensiveVariant } = await import("../lib/catalog/queries");
      const result = await getMostExpensiveVariant(mock);
      expect(result).toBeNull();
      const args = mock.price.findFirst.mock.calls[0][0];
      expect(args.where).toEqual(currentOfficialPrice);
    });
  });
});
