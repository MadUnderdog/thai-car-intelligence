import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const token = process.env.ADMIN_API_TOKEN;

  // Fail closed: if no token is configured, block all admin access
  if (!token) {
    return NextResponse.json(
      { error: "admin_auth_disabled", message: "Admin API token not configured" },
      { status: 401 },
    );
  }

  // Accept only Authorization: Bearer header
  const authHeader = request.headers.get("authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return NextResponse.json(
      { error: "unauthorized", message: "Missing or malformed Authorization header" },
      { status: 401 },
    );
  }

  const providedToken = authHeader.slice(7); // "Bearer ".length === 7
  if (providedToken !== token) {
    return NextResponse.json(
      { error: "unauthorized", message: "Invalid admin token" },
      { status: 401 },
    );
  }

  // Token valid — pass through to the route handler
  return NextResponse.next();
}

export const config = {
  matcher: ["/api/admin/:path*"],
};
