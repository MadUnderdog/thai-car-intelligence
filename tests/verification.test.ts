import { describe, it, expect, vi, beforeEach } from "vitest";
import { verifyChangeCandidate, publishVerifiedCandidate } from "../lib/research/verification";

// Mock the database module
vi.mock("../lib/db", () => ({
  default: {
    $executeRaw: vi.fn(),
    $queryRaw: vi.fn(),
  },
}));

describe("verification", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("throws for non-existent candidate", async () => {
    const mockQuery = vi.fn().mockResolvedValue([]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    await expect(verifyChangeCandidate("nonexistent")).rejects.toThrow("Candidate not found");
  });

  it("throws for candidate in wrong status", async () => {
    const mockQuery = vi.fn().mockResolvedValue([{ id: "c1", status: "PUBLISHED" }]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    await expect(verifyChangeCandidate("c1")).rejects.toThrow("cannot verify");
  });

  it("marks candidate as REJECTED when source inaccessible", async () => {
    const mockQuery = vi.fn()
      .mockResolvedValueOnce([{ id: "c1", entity_type: "price", entity_id: "v1", field_name: "amount", old_value: "100", new_value: "200", source_url: "https://invalid.example.test", source_tier: "official_verified", status: "DISCOVERED" }])
      .mockResolvedValueOnce([{ amount: "100" }]) // current price
      .mockResolvedValueOnce([]); // no conflicts

    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    // Mock fetch to fail
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network error")));

    const result = await verifyChangeCandidate("c1");
    expect(result.status).toBe("REJECTED");
    expect(result.reason).toContain("not accessible");

    vi.unstubAllGlobals();
  });

  it("marks as VERIFIED when source accessible and no conflicts", async () => {
    const mockQuery = vi.fn()
      .mockResolvedValueOnce([{ id: "c1", entity_type: "price", entity_id: "v1", field_name: "amount", old_value: "100", new_value: "200", source_url: "https://example.com", source_tier: "official_verified", status: "DISCOVERED" }])
      .mockResolvedValueOnce([{ amount: "100" }]) // current price
      .mockResolvedValueOnce([]); // no conflicts

    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    // Mock fetch to succeed
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));

    const result = await verifyChangeCandidate("c1");
    expect(result.status).toBe("VERIFIED");
    expect(result.reason).toContain("verified");

    vi.unstubAllGlobals();
  });

  it("detects conflicts when sources disagree", async () => {
    const mockQuery = vi.fn()
      .mockResolvedValueOnce([{ id: "c1", entity_type: "price", entity_id: "v1", field_name: "amount", old_value: "100", new_value: "200", source_url: "https://a.com", source_tier: "official_verified", status: "DISCOVERED" }])
      .mockResolvedValueOnce([{ amount: "100" }]) // current price
      .mockResolvedValueOnce([{ id: "c2", new_value: "300", source_url: "https://b.com", source_tier: "official_verified" }]); // conflict

    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));

    const result = await verifyChangeCandidate("c1");
    expect(result.status).toBe("CONFLICT");
    expect(result.reason).toContain("Conflicting");

    vi.unstubAllGlobals();
  });
});

describe("publishing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("cannot publish non-existent candidate", async () => {
    const mockQuery = vi.fn().mockResolvedValue([]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await publishVerifiedCandidate("nonexistent");
    expect(result.published).toBe(false);
  });

  it("cannot publish unverified candidate", async () => {
    const mockQuery = vi.fn().mockResolvedValue([{ id: "c1", status: "DISCOVERED" }]);
    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await publishVerifiedCandidate("c1");
    expect(result.published).toBe(false);
    expect(result.reason).toContain("Cannot publish");
  });

  it("is idempotent - publishing twice returns same result", async () => {
    const mockQuery = vi.fn()
      .mockResolvedValueOnce([{ id: "c1", entity_type: "price", entity_id: "v1", field_name: "amount", old_value: "100", new_value: "200", source_url: "https://example.com", source_tier: "official_verified", status: "VERIFIED" }])
      .mockResolvedValueOnce([{ cnt: 1 }]); // already published

    vi.spyOn(await import("../lib/db"), "default", "get").mockReturnValue({ $executeRaw: vi.fn(), $queryRaw: mockQuery } as never);

    const result = await publishVerifiedCandidate("c1");
    expect(result.published).toBe(true);
    expect(result.reason).toContain("Already published");
  });
});
