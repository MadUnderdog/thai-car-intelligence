import { NextRequest, NextResponse } from "next/server";
import db from "../../../../../../../lib/db";
import { hashIp, extractIp, getTokenCookieName } from "@/lib/community/identity";
import { checkRateLimit } from "../../../../../../../lib/security/rate-limit";

export const dynamic = "force-dynamic";

const ALLOWED_REASONS = new Set(["SPAM", "ABUSE", "INACCURATE", "OTHER"]);

// POST /api/community/comments/[id]/report
// Body: { reason: "SPAM" | "ABUSE" | "INACCURATE" | "OTHER", detail?: string }
// One report per (comment, reporterToken). Auto-hides the comment after 3 flags.
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const ip = extractIp(req.headers);
  const rl = checkRateLimit(`report:${ip || "none"}`, 10, 60_000);
  if (!rl.allowed) {
    return NextResponse.json({ error: "รายงานบ่อยเกินไป กรุณารอสักครู่" }, { status: 429 });
  }

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "รูปแบบข้อมูลไม่ถูกต้อง" }, { status: 400 });
  }
  const reason = String(payload?.reason || "").toUpperCase();
  if (!ALLOWED_REASONS.has(reason)) {
    return NextResponse.json(
      { error: "เหตุผลการรายงานไม่ถูกต้อง (SPAM / ABUSE / INACCURATE / OTHER)" },
      { status: 400 },
    );
  }

  const comment = await db.communityComment.findUnique({
    where: { id },
    select: { id: true, status: true, deletedAt: true },
  });
  if (!comment || comment.deletedAt) {
    return NextResponse.json({ error: "ไม่พบความคิดเห็นนี้" }, { status: 404 });
  }
  if (comment.status !== "VISIBLE") {
    return NextResponse.json({ ok: true, message: "ความคิดเห็นนี้ถูกปิดการแสดงผลอยู่แล้ว" });
  }

  const reporterToken =
    req.cookies.get(getTokenCookieName())?.value || hashIp(ip);
  const duplicate = await db.commentReport.findUnique({
    where: { commentId_reporterToken: { commentId: id, reporterToken } },
  });
  if (duplicate) {
    return NextResponse.json({ ok: true, message: "คุณได้รายงานความคิดเห็นนี้ไปแล้ว" });
  }

  const AUTO_HIDE_THRESHOLD = 3;
  const result = await db.$transaction(async (tx) => {
    await tx.commentReport.create({
      data: { commentId: id, reporterToken, reason },
    });
    const updated = await tx.communityComment.update({
      where: { id },
      data: { flaggedCount: { increment: 1 } },
      select: { flaggedCount: true, status: true },
    });
    if (updated.flaggedCount >= AUTO_HIDE_THRESHOLD && updated.status === "VISIBLE") {
      const hidden = await tx.communityComment.update({
        where: { id },
        data: { status: "FLAGGED" },
        select: { status: true },
      });
      return { flaggedCount: updated.flaggedCount, status: hidden.status, autoHidden: true };
    }
    return { flaggedCount: updated.flaggedCount, status: updated.status, autoHidden: false };
  });

  return NextResponse.json({ ok: true, ...result });
}
