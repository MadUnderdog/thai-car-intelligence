import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";

// We test the proxy function by importing it and calling it directly.
// The proxy reads process.env.ADMIN_API_TOKEN at call time.

// Save and restore env
const ORIGINAL_TOKEN = process.env.ADMIN_API_TOKEN;

function makeRequest(path: string, headers?: Record<string, string>): Request {
  return new Request(`http://localhost${path}`, { headers });
}

// Import the proxy function — it's a pure function we can test in isolation.
// We need to import it fresh to avoid module caching issues.
async function getProxy() {
  const mod = await import("../src/proxy");
  return mod.proxy;
}

describe("admin auth proxy", () => {
  afterEach(() => {
    // Restore original token state
    if (ORIGINAL_TOKEN === undefined) {
      delete process.env.ADMIN_API_TOKEN;
    } else {
      process.env.ADMIN_API_TOKEN = ORIGINAL_TOKEN;
    }
  });

  it("returns 401 when ADMIN_API_TOKEN is not configured (fail closed)", async () => {
    delete process.env.ADMIN_API_TOKEN;
    const proxy = await getProxy();
    const response = proxy(makeRequest("/api/admin/quality") as any);
    expect(response.status).toBe(401);
    const body = await response.json();
    expect(body.error).toBe("admin_auth_disabled");
  });

  it("returns 401 when Authorization header is missing", async () => {
    process.env.ADMIN_API_TOKEN = "test-secret-token";
    const proxy = await getProxy();
    const response = proxy(makeRequest("/api/admin/quality") as any);
    expect(response.status).toBe(401);
    const body = await response.json();
    expect(body.error).toBe("unauthorized");
  });

  it("returns 401 when Authorization header is not Bearer scheme", async () => {
    process.env.ADMIN_API_TOKEN = "test-secret-token";
    const proxy = await getProxy();
    const response = proxy(makeRequest("/api/admin/quality", { authorization: "Basic abc123" }) as any);
    expect(response.status).toBe(401);
    const body = await response.json();
    expect(body.error).toBe("unauthorized");
  });

  it("returns 401 when token is wrong", async () => {
    process.env.ADMIN_API_TOKEN = "test-secret-token";
    const proxy = await getProxy();
    const response = proxy(makeRequest("/api/admin/quality", { authorization: "Bearer wrong-token" }) as any);
    expect(response.status).toBe(401);
    const body = await response.json();
    expect(body.error).toBe("unauthorized");
  });

  it("passes through when token is valid", async () => {
    process.env.ADMIN_API_TOKEN = "test-secret-token";
    const proxy = await getProxy();
    const response = proxy(makeRequest("/api/admin/quality", { authorization: "Bearer test-secret-token" }) as any);
    // NextResponse.next() returns 200
    expect(response.status).toBe(200);
  });

  it("only matches /api/admin/* paths (config matcher)", async () => {
    const { config } = await import("../src/proxy");
    expect(config.matcher).toEqual(["/api/admin/:path*"]);
  });
});
