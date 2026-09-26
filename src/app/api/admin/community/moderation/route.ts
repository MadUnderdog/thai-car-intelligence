import { NextRequest, NextResponse } from "next/server";
import db from "../../../../../../lib/db";
import { checkRateLimit } from "../../../../../../lib/security/rate-limit";
import { requireAdmin } from "@/lib/community/admin-auth";

export const dynamic = "force-dynamic";

// GET /api/admin/community/moderation?status=FLAGGED — list reported / flagged comments (visible moderation queue)
export async function GET(req: NextRequest) {
  const denied = requireAdmin(req);
  if (denied) return denied;

  const url = new URL(req.url);
  const statusFilter = url.searchParams.get("status");
  const where: Record<string, unknown> = {};
  if (statusFilter && ["VISIBLE", "HIDDEN", "FLAGGED", "DELETED"].includes(statusFilter)) {
    where.status = statusFilter;
  } else {
    where.status = { in: ["FLAGGED", "HIDDEN"] };
  }

  const comments = await db.commentReport.findMany({
    where: { resolved: false, comment: { status: { in: ["FLAGGED", "HIDDEN", "VISIBLE"] } } },
    include: {
      comment: {
        select: {
          id: true, authorName: true, body: true, status: true, flaggedCount: true,
          upvotes: true, downvotes: true,
          isResearchLead: true, createdAt: true,
          modelId: true, variantId: true, parentId: true, deletedAt: true,
        },
      },
    },
    orderBy: { createdAt: "desc" },
    take: 100,
  });

  // group reports per comment into a moderation brief
  const map = new Map<string, { comment: Record<string, unknown>; reports: { id: string; reason: string; createdAt: Date }[] }>();
  for (const rpt of comments) {
    if (rpt.comment && statusFilter && rpt.comment.status !== statusFilter) continue;
    const key = rpt.commentId;
    if (!map.has(key)) {
      map.set(key, { comment: { ...rpt.comment } as Record<string, unknown>, reports: [] });
    }
    map.get(key)!.reports.push({ id: rpt.id, reason: rpt.reason, createdAt: rpt.createdAt });
  }

  const queue = Array.from(map.entries()).map(([commentId, v]) => ({
    commentId,
    ...v.comment,
    reports: v.reports.map((r) => ({ id: r.id, reason: r.reason, createdAt: r.createdAt })),
    briefByReason: v.reports.reduce<Record<string, number>>((acc, r) => {
      acc[r.reason] = (acc[r.reason] || 0) + 1;
      return acc;
    }, {}),
  }));

  return NextResponse.json({ comments: queue, total: queue.length });
}

// PATCH /api/admin/community/moderation — moderation action on a comment
// Body: { commentId, action: "HIDE" | "DELETE" | "RESTORE", note? }
//   HIDE    → status=HIDDEN (still present, hidden from UI)
//   DELETE  → soft delete: status=DELETED + deletedAt set
//   RESTORE → back to VISIBLE, clear deletedAt
export async function PATCH(req: NextRequest) {
  const denied = requireAdmin(req);
  if (denied) return denied;

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "รูปแบบข้อมูลไม่ถูกต้อง" }, { status: 400 });
  }
  const { commentId, action } = payload ?? {};
  if (!commentId || !["HIDE", "DELETE", "RESTORE"].includes(action)) {
    return NextResponse.json(
      { error: "กรุณาระบุ commentId และ action (HIDE / DELETE / RESTORE)" },
      { status: 400 },
    );
  }

  const target = await db.communityComment.findUnique({ where: { id: commentId }, select: { id: true } });
  if (!target) return NextResponse.json({ error: "ไม่พบความคิดเห็นนี้" }, { status: 404 });

  let data: Record<string, unknown>;
  if (action === "HIDE") data = { status: "HIDDEN" };
  else if (action === "DELETE") data = { status: "DELETED", deletedAt: new Date() };
  else data = { status: "VISIBLE", deletedAt: null };

  const updated = await db.communityComment.update({
    where: { id: commentId },
    data,
    select: { id: true, status: true, deletedAt: true },
  });

  // mark related open reports as resolved
  if (action !== "RESTORE") {
    await db.commentReport.updateMany({
      where: { commentId, resolved: false },
      data: { resolved: true, resolvedAt: new Date() },
    });
  }

  return NextResponse.json({ ok: true, comment: updated });
}
