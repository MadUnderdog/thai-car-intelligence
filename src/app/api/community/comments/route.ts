import { NextRequest, NextResponse } from "next/server";
import db from "../../../../../lib/db";
import {
  getTokenCookieName,
  hashIp,
  extractIp,
  newToken,
} from "@/lib/community/identity";
import { checkRateLimit } from "../../../../../lib/security/rate-limit";

export const dynamic = "force-dynamic";

const MAX_BODY_LEN = 2000;
const MAX_NAME_LEN = 60;

function ensureToken(req: NextRequest): { token: string; setCookie: string } {
  const existing = req.cookies.get(getTokenCookieName())?.value;
  if (existing) return { token: existing, setCookie: "" };
  const token = newToken();
  return {
    token,
    setCookie: `${getTokenCookieName()}=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000`,
  };
}

function withCookie(res: NextResponse, setCookie: string): NextResponse {
  if (setCookie) res.headers.append("Set-Cookie", setCookie);
  return res;
}

// GET /api/community/comments?modelId=... or ?variantId=...
// Returns VISIBLE top-level comments with one level of replies (threading).
export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const modelId = url.searchParams.get("modelId");
  const variantId = url.searchParams.get("variantId");
  if (!modelId && !variantId) {
    return NextResponse.json({ error: "ต้องระบุ modelId หรือ variantId" }, { status: 400 });
  }

  const where = {
    status: "VISIBLE" as const,
    deletedAt: null,
    parentId: null,
    ...(variantId ? { variantId } : { modelId }),
  };

  const comments = await db.communityComment.findMany({
    where,
    orderBy: [{ upvotes: "desc" }, { createdAt: "desc" }],
    take: 100,
    select: {
      id: true, authorName: true, body: true, upvotes: true, downvotes: true,
      isResearchLead: true, createdAt: true,
      replies: {
        where: { status: "VISIBLE", deletedAt: null },
        orderBy: { createdAt: "asc" },
        select: {
          id: true, authorName: true, body: true, upvotes: true, downvotes: true,
          isResearchLead: true, createdAt: true, parentId: true,
        },
      },
    },
  });

  return NextResponse.json({ comments, total: comments.length });
}

// POST /api/community/comments — create comment or reply
// Body: { modelId?, variantId?, authorName, body, parentId?, isResearchLead? }
export async function POST(req: NextRequest) {
  const ip = extractIp(req.headers);
  const rl = checkRateLimit(`comment:${ip || "none"}`, 5, 60_000);
  if (!rl.allowed) {
    return NextResponse.json(
      { error: "ส่งความคิดเห็นบ่อยเกินไป กรุณารอสักครู่" },
      { status: 429, headers: { "Retry-After": String(Math.ceil(rl.retryAfterMs / 1000)) } },
    );
  }

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "รูปแบบข้อมูลไม่ถูกต้อง" }, { status: 400 });
  }

  const { modelId, variantId, authorName, body, parentId, isResearchLead } = payload ?? {};
  const name = typeof authorName === "string" ? authorName.trim() : "";
  const text = typeof body === "string" ? body.trim() : "";

  if (!name || name.length > MAX_NAME_LEN) {
    return NextResponse.json({ error: "กรุณาระบุชื่อเล่น (ไม่เกิน 60 ตัวอักษร)" }, { status: 400 });
  }
  if (!text || text.length > MAX_BODY_LEN) {
    return NextResponse.json(
      { error: `กรุณาระบุเนื้อหาความคิดเห็น (ไม่เกิน ${MAX_BODY_LEN} ตัวอักษร)` },
      { status: 400 },
    );
  }
  if (!modelId && !variantId) {
    return NextResponse.json({ error: "ต้องระบุ modelId หรือ variantId" }, { status: 400 });
  }

  const ipHash = hashIp(ip);
  const dup = await db.communityComment.findFirst({
    where: { authorToken: ipHash, body: text, createdAt: { gte: new Date(Date.now() - 5 * 60_000) } },
    select: { id: true },
  });
  if (dup) {
    return NextResponse.json({ error: "คุณได้โพสต์เนื้อหานี้ไปแล้วเมื่อไม่นานมานี้" }, { status: 409 });
  }

  if (parentId) {
    const parent = await db.communityComment.findUnique({
      where: { id: parentId },
      select: { status: true, deletedAt: true, modelId: true, variantId: true },
    });
    if (!parent || parent.status !== "VISIBLE" || parent.deletedAt) {
      return NextResponse.json({ error: "ไม่พบความคิดเห็นต้นทางหรือถูกปิดการแสดงผล" }, { status: 404 });
    }
    // reply inherits the thread's scope
    const comment = await db.communityComment.create({
      data: {
        modelId: modelId ?? parent.modelId,
        variantId: variantId ?? parent.variantId,
        authorName: name,
        authorToken: ipHash,
        body: text,
        parentId,
        ipAddressHash: ipHash,
        isResearchLead: false,
      },
    });
    return withCookie(NextResponse.json({ comment }, { status: 201 }), ensureToken(req).setCookie);
  }

  const comment = await db.communityComment.create({
    data: {
      modelId: modelId ?? null,
      variantId: variantId ?? null,
      authorName: name,
      authorToken: ipHash,
      body: text,
      ipAddressHash: ipHash,
      isResearchLead: Boolean(isResearchLead),
    },
  });
  return withCookie(NextResponse.json({ comment }, { status: 201 }), ensureToken(req).setCookie);
}
