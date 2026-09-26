import { NextRequest, NextResponse } from "next/server";
import db from "../../../../../../../lib/db";
import { hashIp, extractIp } from "@/lib/community/identity";
import { checkRateLimit } from "../../../../../../../lib/security/rate-limit";

export const dynamic = "force-dynamic";

// POST /api/community/comments/[id]/vote
// Body: { value: 1 | -1 }. One vote per (comment, voterToken); re-voting with
// the opposite value switches the vote, repeat same-value calls are idempotent.
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const ip = extractIp(req.headers);
  const rl = checkRateLimit(`vote:${ip || "none"}`, 20, 60_000);
  if (!rl.allowed) {
    return NextResponse.json({ error: "โหวตบ่อยเกินไป กรุณารอสักครู่" }, { status: 429 });
  }

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "รูปแบบข้อมูลไม่ถูกต้อง" }, { status: 400 });
  }
  const value = Number(payload?.value);
  if (value !== 1 && value !== -1) {
    return NextResponse.json({ error: "ค่าโหวตต้องเป็น 1 หรือ -1" }, { status: 400 });
  }

  const comment = await db.communityComment.findUnique({
    where: { id },
    select: { id: true, status: true, deletedAt: true },
  });
  if (!comment || comment.status !== "VISIBLE" || comment.deletedAt) {
    return NextResponse.json({ error: "ไม่พบความคิดเห็นนี้" }, { status: 404 });
  }

  const voterToken = hashIp(ip);
  const existing = await db.commentVote.findUnique({
    where: { commentId_voterToken: { commentId: id, voterToken } },
  });

  await db.$transaction(async (tx) => {
    if (!existing) {
      await tx.commentVote.create({ data: { commentId: id, voterToken, value } });
      if (value === 1) await tx.communityComment.update({ where: { id }, data: { upvotes: { increment: 1 } } });
      else await tx.communityComment.update({ where: { id }, data: { downvotes: { increment: 1 } } });
    } else if (existing.value !== value) {
      // switch vote
      await tx.commentVote.update({ where: { id: existing.id }, data: { value } });
      await tx.communityComment.update({
        where: { id },
        data: value === 1 ? { upvotes: { increment: 1 }, downvotes: { decrement: 1 } } : { upvotes: { decrement: 1 }, downvotes: { increment: 1 } },
      });
    }
    // else: same-value repeat → idempotent no-op
  });

  const fresh = await db.communityComment.findUnique({
    where: { id },
    select: { id: true, upvotes: true, downvotes: true },
  });
  return NextResponse.json({ ok: true, vote: value, ...fresh });
}
