import { describe, expect, it } from "vitest";

describe("error leakage regression", () => {
  // These tests verify that error responses do not leak internal details.
  // They test the error response format, not the actual error handling logic.

  it("admin dashboard error response has no detail field", async () => {
    // Import the route handler to check its error response format
    // We can't easily trigger a DB error in tests, so we verify the
    // catch block structure by reading the source.
    const fs = await import("fs");
    const path = await import("path");
    const routePath = path.resolve(__dirname, "../src/app/api/admin/dashboard/route.ts");
    const content = fs.readFileSync(routePath, "utf-8");

    // Should NOT contain String(e) in error responses
    expect(content).not.toMatch(/String\(e\)/);
    // Should have console.error for server-side logging
    expect(content).toContain("console.error");
    // Should return safe error message
    expect(content).toContain('"database_unavailable"');
    // Should NOT have detail field in error response
    expect(content).not.toMatch(/detail:\s*String/);
  });

  it("admin quality error response has no detail field", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const routePath = path.resolve(__dirname, "../src/app/api/admin/quality/route.ts");
    const content = fs.readFileSync(routePath, "utf-8");
    expect(content).not.toMatch(/String\(e\)/);
    expect(content).toContain("console.error");
    expect(content).toContain('"database_unavailable"');
  });

  it("admin quality variants error response has no detail field", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const routePath = path.resolve(__dirname, "../src/app/api/admin/quality/variants/route.ts");
    const content = fs.readFileSync(routePath, "utf-8");
    // Should NOT contain String(e) or detail leakage
    expect(content).not.toMatch(/String\(e\)/);
    expect(content).not.toMatch(/detail:\s*String/);
    // Route returns safe unavailable state (no try/catch needed for static response)
    expect(content).toContain('"not_implemented"');
  });

  it("admin research queue error response has no detail field", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const routePath = path.resolve(__dirname, "../src/app/api/admin/research/queue/route.ts");
    const content = fs.readFileSync(routePath, "utf-8");
    // Should NOT contain String(e) or detail leakage
    expect(content).not.toMatch(/String\(e\)/);
    expect(content).not.toMatch(/detail:\s*String/);
    // Route returns safe unavailable state (no try/catch needed for static response)
    expect(content).toContain('"not_implemented"');
  });

  it("proxy does not leak token in error responses", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const proxyPath = path.resolve(__dirname, "../src/proxy.ts");
    const content = fs.readFileSync(proxyPath, "utf-8");

    // Should not include the token value in any response
    expect(content).not.toMatch(/ADMIN_API_TOKEN.*"/);
    // Error messages should be generic
    expect(content).toContain('"unauthorized"');
    expect(content).toContain('"admin_auth_disabled"');
    expect(content).toContain('"rate_limited"');
  });
});
