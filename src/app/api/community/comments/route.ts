import { NextRequest, NextResponse } from "next/server";
import db from "../../../../../lib/db";
import {
  getTokenCookieName,
  hashIp,
  extractIp,
  newToken,
} from "@/lib/community/identity";
import { checkRateLimit } from "../../../../../lib/security/rate-limit";
import {
  resolveTopLevelScope,
  resolveReplyParent,
  assertActiveEntityForRead,
  parsePagination,
} from "@/lib/community/scope";
import { findBlockedTerm } from "@/lib/community/blocked-words";

export const dynamic = "force-dynamic";

const MAX_BODY_LEN = 2000;
const MAX_NAME_LEN = 60;

/** Generic failure — never echoes SQL / stack / Prisma internals to clients. */
function serverError(): NextResponse {
  return NextResponse.json({ error: "เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง" }, { status: 500 });
}

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
// P117: malformed ids / pagination → 400, unknown or inactive entity → 404,
// ordering carries a final `id asc` tiebreak for deterministic reads.
export async function GET(req: NextRequest) {
  try {
    const url = new URL(req.url);
    const modelId = url.searchParams.get("modelId");
    const variantId = url.searchParams.get("variantId");

    if (modelId && variantId) {
      return NextResponse.json({ error: "ระบุ modelId หรือ variantId อย่างใดอย่างเดียว" }, { status: 400 });
    }
    if (!modelId && !variantId) {
      return NextResponse.json({ error: "ต้องระบุ modelId หรือ variantId" }, { status: 400 });
    }

    const pagination = parsePagination(url.searchParams.get("page"), url.searchParams.get("limit"));
    if (!pagination.ok) return NextResponse.json({ error: pagination.error }, { status: pagination.status });

    const entity = await assertActiveEntityForRead(modelId ? "model" : "variant", (modelId || variantId)!);
    if (!entity.ok) return NextResponse.json({ error: entity.error }, { status: entity.status });

    const { page, limit } = pagination;
    const where = {
      status: "VISIBLE" as const,
      deletedAt: null,
      parentId: null,
      ...(variantId ? { variantId } : { modelId }),
    };

    const [comments, total] = await Promise.all([
      db.communityComment.findMany({
        where,
        orderBy: [{ upvotes: "desc" }, { createdAt: "desc" }, { id: "asc" }],
        skip: (page - 1) * limit,
        take: limit,
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
      }),
      db.communityComment.count({ where }),
    ]);

    return NextResponse.json({ comments, total, page, limit, hasMore: (page - 1) * limit + comments.length < total });
  } catch (err) {
    console.error("[community/comments GET]", err);
    return serverError();
  }
}

// POST /api/community/comments — create comment or reply
// Body: { modelId?, variantId?, authorName, body, parentId? }
// P117 contract:
//   - replies inherit the parent's scope verbatim (client scope fields ignored)
//   - top-level scope is validated: UUID → existence+ACTIVE → model/variant agreement
//   - isResearchLead is NEVER read from the client (only the admin research-lead
//     route may set it)
//   - blocked words rejected BEFORE any persistence
export async function POST(req: NextRequest) {
  try {
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

    const { modelId, variantId, authorName, body, parentId } = payload ?? {};
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

    const blocked = findBlockedTerm(`${name} ${text}`);
    if (blocked) {
      return NextResponse.json(
        { error: "โพสต์นี้มีคำที่ไม่ได้รับอนุญาต กรุณาแก้ไขเนื้อหา" },
        { status: 400 },
      );
    }

    const ipHash = hashIp(ip);

    if (parentId) {
      // Reply: scope comes ONLY from the parent — client modelId/variantId
      // are ignored, so a malicious payload can never move the reply.
      const parentResult = await resolveReplyParent(parentId);
      if (!parentResult.ok) {
        return NextResponse.json({ error: parentResult.error }, { status: parentResult.status });
      }
      const parent = parentResult.parent;
      const comment = await db.communityComment.create({
        data: {
          modelId: parent.modelId,
          variantId: parent.variantId,
          authorName: name,
          authorToken: ipHash,
          body: text,
          parentId: parent.id,
          ipAddressHash: ipHash,
          isResearchLead: false,
        },
      });
      return withCookie(NextResponse.json({ comment }, { status: 201 }), ensureToken(req).setCookie);
    }

    // Top-level: full scope validation (fail closed)
    const scope = await resolveTopLevelScope({ modelId, variantId });
    if (!scope.ok) {
      return NextResponse.json({ error: scope.error }, { status: scope.status });
    }

    const dup = await db.communityComment.findFirst({
      where: { authorToken: ipHash, body: text, createdAt: { gte: new Date(Date.now() - 5 * 60_000) } },
      select: { id: true },
    });
    if (dup) {
      return NextResponse.json({ error: "คุณได้โพสต์เนื้อหานี้ไปแล้วเมื่อไม่นานมานี้" }, { status: 409 });
    }

    // isResearchLead from the payload is deliberately discarded (P117-E).
    const comment = await db.communityComment.create({
      data: {
        modelId: scope.modelId,
        variantId: scope.variantId,
        authorName: name,
        authorToken: ipHash,
        body: text,
        ipAddressHash: ipHash,
        isResearchLead: false,
      },
    });
    return withCookie(NextResponse.json({ comment }, { status: 201 }), ensureToken(req).setCookie);
  } catch (err) {
    console.error("[community/comments POST]", err);
    return serverError();
  }
}
