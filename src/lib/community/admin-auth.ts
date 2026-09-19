import { NextRequest, NextResponse } from "next/server";

/**
 * Shared admin bearer-token gate for /api/admin/community/* routes.
 * Returns a NextResponse when the caller is NOT authorized (caller should
 * return it directly); returns null when authorized.
 */
export function requireAdmin(req: NextRequest): NextResponse | null {
  const header = req.headers.get("authorization") || "";
  const token = header.replace(/^Bearer\s+/i, "");
  const expected = process.env.ADMIN_API_TOKEN || "";
  if (!expected) {
    return NextResponse.json({ error: "ไม่ได้ตั้งค่า ADMIN_API_TOKEN" }, { status: 500 });
  }
  if (token !== expected) {
    return NextResponse.json({ error: "ไม่ได้รับอนุญาต" }, { status: 401 });
  }
  return null;
}
