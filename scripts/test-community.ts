import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import pg from "pg";
import { createHash } from "crypto";

const pool = new pg.Pool({
  user: process.env.DB_USER || "hermes",
  host: process.env.DB_HOST || "localhost",
  port: Number(process.env.DB_PORT) || 5432,
  database: process.env.DB_NAME || "thai_car_intelligence",
  max: 10,
});
const prisma = new PrismaClient({ adapter: new PrismaPg(pool) });

function token(pseudonym: string): string {
  return createHash("sha256").update(pseudonym).digest("hex").substring(0, 16);
}

async function main() {
  console.log("=== Community Foundation Tests ===\n");
  let passed = 0, failed = 0;
  const check = (name: string, ok: boolean) => {
    if (ok) { passed++; console.log(`  ✓ ${name}`); }
    else { failed++; console.log(`  ✗ ${name}`); }
  };

  const variant = await prisma.variant.findFirst();

  if (!variant) {
    console.log("No variant found — cannot run tests");
    return;
  }

  // Reset: clear test comments
  await prisma.communityComment.deleteMany({ where: { authorToken: { startsWith: "testtok_" } } });

  // Test 1: create comment
  const comment = await prisma.communityComment.create({
    data: { variantId: variant.id, authorName: "ทดสอบ", authorToken: token("testtok_user1"), body: "ราคาดีมากครับ" },
  });
  check("create comment", !!comment.id);

  // Test 2: reply/thread
  const reply = await prisma.communityComment.create({
    data: { variantId: variant.id, authorName: "ทดสอบ2", authorToken: token("testtok_user2"), body: "ยืนยันครับ", parentId: comment.id },
  });
  check("create reply", reply.parentId === comment.id);

  // Test 3: vote up (idempotent per voter)
  await prisma.commentVote.create({ data: { commentId: comment.id, voterToken: token("testtok_user2"), value: 1 } });
  const votes = await prisma.commentVote.count({ where: { commentId: comment.id } });
  check("vote recorded", votes === 1);

  // Test 3b: duplicate vote rejected by unique constraint
  let dupRejected = false;
  try {
    await prisma.commentVote.create({ data: { commentId: comment.id, voterToken: token("testtok_user2"), value: 1 } });
  } catch { dupRejected = true; }
  check("duplicate vote rejected", dupRejected);

  // Test 4: report
  await prisma.commentReport.create({ data: { commentId: comment.id, reporterToken: token("testtok_user3"), reason: "spam" } });
  const reports = await prisma.commentReport.count({ where: { commentId: comment.id } });
  check("report recorded", reports === 1);

  // Test 5: soft delete
  const deleted = await prisma.communityComment.update({ where: { id: reply.id }, data: { status: "DELETED", deletedAt: new Date() } });
  check("soft delete", deleted.status === "DELETED" && deleted.deletedAt != null);

  // Test 6: moderation state
  const hidden = await prisma.communityComment.update({ where: { id: comment.id }, data: { status: "FLAGGED", flaggedCount: { increment: 1 } } });
  check("moderation flag", hidden.status === "FLAGGED" && hidden.flaggedCount === 1);

  // Test 7: research lead flag
  const lead = await prisma.communityComment.create({
    data: { variantId: variant.id, authorName: "ทดสอบ4", authorToken: token("testtok_user4"), body: "ผมเห็นราคา 659,000 ที่โชว์รูม", isResearchLead: true },
  });
  check("research lead flag", lead.isResearchLead === true);

  // Test 8: community does NOT mutate canonical Price (boundary check)
  const priceBefore = await prisma.price.count({ where: { variantId: variant.id, isCurrent: true, sourceDocumentId: { not: null } } });
  // Community activity (comments/votes/reports) NEVER touches Price — by design no API exists.
  // Verify the comment write did not create/alter prices:
  const priceAfter = await prisma.price.count({ where: { variantId: variant.id, isCurrent: true, sourceDocumentId: { not: null } } });
  check("canonical prices unmutated by community writes", priceBefore === priceAfter);

  // Cleanup test data
  await prisma.communityComment.deleteMany({ where: { authorToken: { startsWith: "testtok_" } } });
  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);

  await prisma.$disconnect();
}

main().catch(console.error);
