import { NextRequest, NextResponse } from "next/server";
import { Prisma } from "@prisma/client";
import db from "../../../../../../lib/db";
import { requireAdmin } from "@/lib/community/admin-auth";
import { checkRateLimit } from "../../../../../../lib/security/rate-limit";

export const dynamic = "force-dynamic";

// POST /api/admin/community/research-lead
// Body: { commentId, fieldName, proposedValue, evidence?, confidence? }
// Handoff the community observation into the existing ResearchCandidate table
// so research leads can verify it via the normal research-run pipeline.
// Steps:
//   1. find or create a COMMUNITY_LEAD ResearchRun
//   2. create ResearchCandidate(status=PENDING, confidence default 0.0)
//   3. link CommunityComment researchCandidateId + isResearchLead=true
export async function POST(req: NextRequest) {
  const ip = req.headers.get("x-forwarded-for") || "none";
  const denied = requireAdmin(req);
  if (denied) return denied;
  const rl = checkRateLimit(`lead:${ip}`, 30, 60_000);
  if (!rl.allowed) return NextResponse.json({ error: "เรียกใช้บ่อยเกินไป" }, { status: 429 });

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "รูปแบบข้อมูลไม่ถูกต้อง" }, { status: 400 });
  }

  const { commentId, fieldName, proposedValue, evidence } = payload ?? {};
  const confidence = payload?.confidence !== undefined ? Number(payload.confidence) : 0;

  if (!commentId || !fieldName || typeof fieldName !== "string" || fieldName.trim().length === 0) {
    return NextResponse.json({ error: "กรุณาระบุ commentId และ fieldName" }, { status: 400 });
  }
  if (proposedValue === undefined || proposedValue === null || (typeof proposedValue === "object" && Object.keys(proposedValue).length === 0)) {
    return NextResponse.json({ error: "กรุณาระบุ proposedValue" }, { status: 400 });
  }
  if (Number.isNaN(confidence) || confidence < 0 || confidence > 1) {
    return NextResponse.json({ error: "confidence ต้องอยู่ในช่วง 0-1" }, { status: 400 });
  }

  const comment = await db.communityComment.findUnique({
    where: { id: commentId },
    select: { id: true, status: true, deletedAt: true, variantId: true, isResearchLead: true, researchCandidateId: true },
  });
  if (!comment || comment.deletedAt) {
    return NextResponse.json({ error: "ไม่พบความคิดเห็นนี้" }, { status: 404 });
  }
  if (comment.isResearchLead && comment.researchCandidateId) {
    return NextResponse.json(
      { ok: true, alreadyLinked: true, researchCandidateId: comment.researchCandidateId },
      { status: 200 },
    );
  }

  const result = await db.$transaction(async (tx) => {
    // 1. find or create the community-lead research run
    let run = await tx.researchRun.findFirst({
      where: { name: "COMMUNITY_LEADS" },
      select: { id: true },
    });
    if (!run) {
      run = await tx.researchRun.create({
        data: {
          name: "COMMUNITY_LEADS",
          status: "SUCCEEDED",
          entityType: "CommunityComment",
          factsChanged: 0,
        },
        select: { id: true },
      });
    }

    // 2. create the ResearchCandidate (status PENDING by default)
    const candidate = await tx.researchCandidate.create({
      data: {
        researchRunId: run.id,
        variantId: comment.variantId,
        fieldName: fieldName.trim(),
        proposedValue: proposedValue as Prisma.InputJsonValue,
        evidence: typeof evidence === "string" && evidence.trim().length > 0 ? evidence.trim() : null,
        confidence: new Prisma.Decimal(confidence),
        status: "PENDING",
      },
      select: { id: true, fieldName: true, status: true, confidence: true },
    });

    // 3. link back to the comment (research-lead flag)
    await tx.communityComment.update({
      where: { id: commentId },
      data: { isResearchLead: true, researchCandidateId: candidate.id },
    });

    return candidate;
  });

  return NextResponse.json({ ok: true, researchCandidate: result }, { status: 201 });
}
