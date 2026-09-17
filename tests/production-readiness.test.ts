import { describe, it, expect, vi, beforeEach } from "vitest";
import { verifyChangeCandidate, publishVerifiedCandidate } from "../lib/research/verification";
import { rollbackPublishedChange } from "../lib/research/rollback";
import { detectPriceChange, batchDetectPriceChanges } from "../lib/research/price-change-detection";
import { createChangeCandidate, getCandidateStats } from "../lib/research/refresh-pipeline";

// Mock the database module
vi.mock("../lib/db", () => ({
  default: {
    $executeRaw: vi.fn(),
    $queryRaw: vi.fn(),
  },
}));

describe("publish safety", () => {
  beforeEach(() => vi.clearAllMocks());

  it("DISCOVERED cannot publish", async () => {
    const mockQuery = vi.fn().mockResolvedValue([{ id: "c1", status: "DISCOVERED" }]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await publishVerifiedCandidate("c1");
    expect(result.published).toBe(false);
    expect(result.reason).toContain("Cannot publish");
  });

  it("NEEDS_VERIFICATION cannot publish", async () => {
    const mockQuery = vi.fn().mockResolvedValue([{ id: "c1", status: "NEEDS_VERIFICATION" }]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await publishVerifiedCandidate("c1");
    expect(result.published).toBe(false);
  });

  it("REJECTED cannot publish", async () => {
    const mockQuery = vi.fn().mockResolvedValue([{ id: "c1", status: "REJECTED" }]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await publishVerifiedCandidate("c1");
    expect(result.published).toBe(false);
  });

  it("CONFLICT cannot publish", async () => {
    const mockQuery = vi.fn().mockResolvedValue([{ id: "c1", status: "CONFLICT" }]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await publishVerifiedCandidate("c1");
    expect(result.published).toBe(false);
  });

  it("VERIFIED can publish", async () => {
    const mockQuery = vi.fn()
      .mockResolvedValueOnce([{ id: "c1", entity_type: "price", entity_id: "v1", field_name: "amount", old_value: "100", new_value: "200", source_url: "https://example.com", source_tier: "official_verified", status: "VERIFIED" }])
      .mockResolvedValueOnce([{ cnt: 0 }]) // not yet published
      .mockResolvedValueOnce([{ id: "doc1" }]) // source doc
      .mockResolvedValueOnce([]); // insert price

    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await publishVerifiedCandidate("c1");
    expect(result.published).toBe(true);
  });
});

describe("rollback", () => {
  beforeEach(() => vi.clearAllMocks());

  it("cannot rollback non-existent candidate", async () => {
    const mockQuery = vi.fn().mockResolvedValue([]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await rollbackPublishedChange("nonexistent", "test");
    expect(result.success).toBe(false);
    expect(result.reason).toContain("not found");
  });

  it("cannot rollback un-published candidate", async () => {
    const mockQuery = vi.fn().mockResolvedValue([{ id: "c1", status: "VERIFIED", old_value: "100" }]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await rollbackPublishedChange("c1", "test");
    expect(result.success).toBe(false);
    expect(result.reason).toContain("Cannot rollback");
  });

  it("cannot rollback when no previous value", async () => {
    const mockQuery = vi.fn().mockResolvedValue([{ id: "c1", status: "PUBLISHED", old_value: null }]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await rollbackPublishedChange("c1", "test");
    expect(result.success).toBe(false);
    expect(result.reason).toContain("No previous value");
  });

  it("rollback is idempotent", async () => {
    const mockQuery = vi.fn()
      .mockResolvedValueOnce([{ id: "c1", entity_type: "price", entity_id: "v1", status: "PUBLISHED", old_value: "100", new_value: "200" }])
      .mockResolvedValueOnce([{ amount: "100" }]); // already rolled back

    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await rollbackPublishedChange("c1", "test");
    expect(result.success).toBe(true);
    expect(result.reason).toContain("Already rolled back");
  });
});

describe("idempotency", () => {
  beforeEach(() => vi.clearAllMocks());

  it("same source twice does not create duplicate candidate", async () => {
    // First call: no existing candidate
    const mockQuery = vi.fn()
      .mockResolvedValueOnce([{ amount: 749900 }]) // current price
      .mockResolvedValueOnce([{ nameEn: "ATTO 3", modelName: "ATTO 3", brandName: "BYD" }])
      .mockResolvedValueOnce([]) // no existing candidate
      .mockResolvedValueOnce([{ id: "c1" }]); // created

    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result1 = await detectPriceChange({ variantId: "v1", newPrice: 799900, sourceUrl: "https://example.com", sourceTier: "official_verified" });
    expect(result1).not.toBeNull();

    // Second call: existing candidate found → returns null (no duplicate)
    const mockQuery2 = vi.fn()
      .mockResolvedValueOnce([{ amount: 749900 }])
      .mockResolvedValueOnce([{ nameEn: "ATTO 3", modelName: "ATTO 3", brandName: "BYD" }])
      .mockResolvedValueOnce([{ id: "c1" }]); // existing candidate

    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery2 } as never);

    const result2 = await detectPriceChange({ variantId: "v1", newPrice: 799900, sourceUrl: "https://example.com", sourceTier: "official_verified" });
    expect(result2).toBeNull(); // No duplicate created
  });

  it("unchanged price creates no candidate", async () => {
    const mockQuery = vi.fn().mockResolvedValueOnce([{ amount: 749900 }]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await detectPriceChange({ variantId: "v1", newPrice: 749900, sourceUrl: "https://example.com", sourceTier: "official_verified" });
    expect(result).toBeNull();
  });

  it("batch detect handles multiple variants", async () => {
    const mockQuery = vi.fn()
      .mockResolvedValueOnce([{ amount: 749900 }])
      .mockResolvedValueOnce([{ nameEn: "ATTO 3", modelName: "ATTO 3", brandName: "BYD" }])
      .mockResolvedValueOnce([]) // no existing candidate
      .mockResolvedValueOnce([{ id: "c1" }])
      .mockResolvedValueOnce([{ amount: 599900 }])
      .mockResolvedValueOnce([{ nameEn: "Dolphin", modelName: "Dolphin", brandName: "BYD" }])
      .mockResolvedValueOnce([]) // no existing candidate
      .mockResolvedValueOnce([{ id: "c2" }]);

    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const results = await batchDetectPriceChanges([
      { variantId: "v1", newPrice: 799900, sourceUrl: "https://a.com", sourceTier: "official_verified" },
      { variantId: "v2", newPrice: 629900, sourceUrl: "https://b.com", sourceTier: "official_verified" },
    ]);

    expect(results).toHaveLength(2);
  });
});
