import { describe, expect, it, beforeEach } from "vitest";
import { checkRateLimit, _resetRateLimitStore } from "../lib/security/rate-limit";

describe("rate limiter", () => {
  beforeEach(() => {
    _resetRateLimitStore();
  });

  it("allows requests within the limit", () => {
    const result = checkRateLimit("test-key", 5, 60_000);
    expect(result.allowed).toBe(true);
    expect(result.remaining).toBe(4);
  });

  it("blocks requests exceeding the limit", () => {
    for (let i = 0; i < 5; i++) {
      checkRateLimit("test-key", 5, 60_000);
    }
    const result = checkRateLimit("test-key", 5, 60_000);
    expect(result.allowed).toBe(false);
    expect(result.remaining).toBe(0);
    expect(result.retryAfterMs).toBeGreaterThan(0);
  });

  it("resets after the window expires", () => {
    // Use a very short window for testing
    const result1 = checkRateLimit("test-key", 2, 1); // 1ms window
    expect(result1.allowed).toBe(true);

    // Exhaust the limit
    checkRateLimit("test-key", 2, 1);
    const blocked = checkRateLimit("test-key", 2, 1);
    expect(blocked.allowed).toBe(false);

    // Wait for window to expire (artificial delay)
    const start = Date.now();
    while (Date.now() - start < 5) {
      // busy wait
    }

    const result2 = checkRateLimit("test-key", 2, 1);
    expect(result2.allowed).toBe(true);
    expect(result2.remaining).toBe(1);
  });

  it("tracks different keys independently", () => {
    checkRateLimit("key-a", 2, 60_000);
    checkRateLimit("key-a", 2, 60_000);
    const blocked = checkRateLimit("key-a", 2, 60_000);
    expect(blocked.allowed).toBe(false);

    const otherKey = checkRateLimit("key-b", 2, 60_000);
    expect(otherKey.allowed).toBe(true);
  });

  it("resets store correctly", () => {
    checkRateLimit("test-key", 1, 60_000);
    const blocked = checkRateLimit("test-key", 1, 60_000);
    expect(blocked.allowed).toBe(false);

    _resetRateLimitStore();

    const afterReset = checkRateLimit("test-key", 1, 60_000);
    expect(afterReset.allowed).toBe(true);
  });
});
