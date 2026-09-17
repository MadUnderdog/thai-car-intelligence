import { describe, it, expect, vi, beforeEach } from "vitest";
import * as refreshPipeline from "../lib/research/refresh-pipeline";
import * as priceDetection from "../lib/research/price-change-detection";

// Mock the database module
vi.mock("../lib/db", () => ({
  default: {
    $executeRaw: vi.fn(),
    $queryRaw: vi.fn(),
  },
}));

describe("refresh pipeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates a refresh run", async () => {
    const mockQuery = vi.fn().mockResolvedValue([{ id: "run-123" }]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const runId = await refreshPipeline.createRefreshRun();
    expect(runId).toBe("run-123");
  });

  it("creates a change candidate", async () => {
    const mockQuery = vi.fn().mockResolvedValue([{ id: "candidate-456" }]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const id = await refreshPipeline.createChangeCandidate({
      entityType: "price",
      entityId: "variant-123",
      fieldName: "amount",
      oldValue: "749900",
      newValue: "799900",
      sourceUrl: "https://example.com",
      sourceTier: "official_verified",
    });
    expect(id).toBe("candidate-456");
  });

  it("gets candidate stats", async () => {
    const mockQuery = vi.fn().mockResolvedValue([
      { status: "DISCOVERED", cnt: 5 },
      { status: "VERIFIED", cnt: 3 },
      { status: "PUBLISHED", cnt: 2 },
    ]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const stats = await refreshPipeline.getCandidateStats();
    expect(stats.total).toBe(10);
    expect(stats.discovered).toBe(5);
    expect(stats.verified).toBe(3);
    expect(stats.published).toBe(2);
  });

  it("gets recent runs", async () => {
    const mockQuery = vi.fn().mockResolvedValue([
      { id: "run-1", status: "COMPLETED", startedAt: new Date(), completedAt: new Date(), sourcesChecked: 5, changesDetected: 2, candidatesCreated: 2, errors: 0 },
    ]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const runs = await refreshPipeline.getRecentRuns();
    expect(runs).toHaveLength(1);
    expect(runs[0].status).toBe("COMPLETED");
  });
});

describe("price change detection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("detects price change when new price differs", async () => {
    const mockQuery = vi.fn()
      .mockResolvedValueOnce([{ amount: 749900 }]) // current price
      .mockResolvedValueOnce([{ nameEn: "ATTO 3", modelName: "ATTO 3", brandName: "BYD" }]) // variant info
      .mockResolvedValueOnce([]) // no existing candidate (idempotency check)
      .mockResolvedValueOnce([{ id: "candidate-1" }]); // created candidate

    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await priceDetection.detectPriceChange({
      variantId: "variant-123",
      newPrice: 799900,
      sourceUrl: "https://example.com",
      sourceTier: "official_verified",
    });

    expect(result).not.toBeNull();
    expect(result!.oldPrice).toBe(749900);
    expect(result!.newPrice).toBe(799900);
  });

  it("returns null when price is unchanged", async () => {
    const mockQuery = vi.fn().mockResolvedValueOnce([{ amount: 749900 }]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await priceDetection.detectPriceChange({
      variantId: "variant-123",
      newPrice: 749900,
      sourceUrl: "https://example.com",
      sourceTier: "official_verified",
    });

    expect(result).toBeNull();
  });

  it("returns null when no current price exists", async () => {
    const mockQuery = vi.fn().mockResolvedValueOnce([]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await priceDetection.detectPriceChange({
      variantId: "variant-123",
      newPrice: 799900,
      sourceUrl: "https://example.com",
      sourceTier: "official_verified",
    });

    expect(result).toBeNull();
  });

  it("batch detects multiple price changes", async () => {
    const mockQuery = vi.fn()
      .mockResolvedValueOnce([{ amount: 749900 }]) // variant 1 current
      .mockResolvedValueOnce([{ nameEn: "ATTO 3", modelName: "ATTO 3", brandName: "BYD" }])
      .mockResolvedValueOnce([]) // no existing candidate
      .mockResolvedValueOnce([{ id: "c1" }])
      .mockResolvedValueOnce([{ amount: 599900 }]) // variant 2 current
      .mockResolvedValueOnce([{ nameEn: "Dolphin", modelName: "Dolphin", brandName: "BYD" }])
      .mockResolvedValueOnce([]) // no existing candidate
      .mockResolvedValueOnce([{ id: "c2" }]);

    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const results = await priceDetection.batchDetectPriceChanges([
      { variantId: "v1", newPrice: 799900, sourceUrl: "https://a.com", sourceTier: "official_verified" },
      { variantId: "v2", newPrice: 629900, sourceUrl: "https://b.com", sourceTier: "official_verified" },
    ]);

    expect(results).toHaveLength(2);
  });
});
