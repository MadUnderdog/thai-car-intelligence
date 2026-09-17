import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { checkRateLimit } from "../lib/security/rate-limit";

const ADMIN_RATE_LIMIT_MAX = 60; // requests per window
const ADMIN_RATE_LIMIT_WINDOW_MS = 60_000; // 1 minute

function getClientIp(request: NextRequest): string {
  return request.headers.get("x-forwarded-for")?.split(",")[0]?.trim()
    || request.headers.get("x-real-ip")
    || "unknown";
}

export function proxy(request: NextRequest) {
  const token = process.env.ADMIN_API_TOKEN;

  // Fail closed: if no token is configured, block all admin access
  if (!token) {
    return NextResponse.json(
      { error: "admin_auth_disabled" },
      { status: 401 },
    );
  }

  // Rate limit admin endpoints
  const ip = getClientIp(request);
  const rateLimit = checkRateLimit(`admin:${ip}`, ADMIN_RATE_LIMIT_MAX, ADMIN_RATE_LIMIT_WINDOW_MS);
  if (!rateLimit.allowed) {
    return NextResponse.json(
      { error: "rate_limited" },
      {
        status: 429,
        headers: {
          "Retry-After": String(Math.ceil(rateLimit.retryAfterMs / 1000)),
          "X-RateLimit-Limit": String(ADMIN_RATE_LIMIT_MAX),
          "X-RateLimit-Remaining": "0",
        },
      },
    );
  }

  // Accept only Authorization: Bearer header
  const authHeader = request.headers.get("authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return NextResponse.json(
      { error: "unauthorized" },
      { status: 401 },
    );
  }

  const providedToken = authHeader.slice(7); // "Bearer ".length === 7
  if (providedToken !== token) {
    return NextResponse.json(
      { error: "unauthorized" },
      { status: 401 },
    );
  }

  // Token valid — pass through to the route handler
  return NextResponse.next();
}

export const config = {
  matcher: ["/api/admin/:path*"],
};
