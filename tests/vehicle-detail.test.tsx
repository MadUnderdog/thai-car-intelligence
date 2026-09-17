import { describe, it, expect, vi, afterEach } from "vitest";
import * as dbModule from "../lib/db";

describe("vehicle detail", () => {
  afterEach(() => vi.restoreAllMocks());

  it("page component exports correctly", async () => {
    const mod = await import("../src/app/cars/[manufacturer]/[model]/page");
    expect(mod.default).toBeDefined();
    expect(typeof mod.generateMetadata).toBe("function");
  });

  it("generateMetadata returns not-found title for unknown vehicle", async () => {
    vi.spyOn(dbModule, "default", "get").mockReturnValue({
      carModel: { findFirst: vi.fn().mockResolvedValue(null) },
    } as never);

    const { generateMetadata } = await import("../src/app/cars/[manufacturer]/[model]/page");
    const result = await generateMetadata({ params: Promise.resolve({ manufacturer: "nonexistent", model: "nonexistent" }) });
    expect(result.title).toContain("ไม่พบ");
  });
});
