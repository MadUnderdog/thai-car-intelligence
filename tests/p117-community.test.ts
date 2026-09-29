/**
 * P117 — community + moderation contract tests (real DB, community tables only).
 *
 * Red-before: written against base 2a30e39 BEFORE any implementation change.
 * Fixtures are marked '[p117-fixture]' and removed in afterAll (community
 * tables only — no catalog/price/spec writes anywhere in this file).
 * Unique x-forwarded-for IP per case + _resetRateLimitStore() keep the
 * in-memory rate limits from cross-contaminating tests.
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";
import db from "../lib/db";
import { _resetRateLimitStore } from "../lib/security/rate-limit";

import { GET as commentsGET, POST as commentsPOST } from "../src/app/api/community/comments/route";
import { POST as votePOST } from "../src/app/api/community/comments/[id]/vote/route";
import { POST as reportPOST } from "../src/app/api/community/comments/[id]/report/route";
import { GET as queueGET, PATCH as queuePATCH } from "../src/app/api/admin/community/moderation/route";
import { POST as leadPOST } from "../src/app/api/admin/community/research-lead/route";

const ADMIN_TOKEN = "p117-test-token";
process.env.ADMIN_API_TOKEN = ADMIN_TOKEN;

const MARK = "[p117-fixture]";
let modelA = "";
let modelB = "";
let variantA = "";
let variantB = "";
let ipSeq = 0;

function nextIp(tag: string): string {
  ipSeq += 1;
  return `10.${(ipSeq >> 8) & 255}.${ipSeq & 255}.${(tag.length % 250) + 1}`;
}

function req(
  url: string,
  opts: { method?: string; body?: unknown; ip?: string; headers?: Record<string, string> } = {},
): NextRequest {
  const headers: Record<string, string> = { "content-type": "application/json", ...(opts.headers || {}) };
  if (opts.ip) headers["x-forwarded-for"] = opts.ip;
  return new NextRequest(url, {
    method: opts.method || "GET",
    headers,
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  });
}

async function createComment(data: Record<string, unknown>, ip: string) {
  const res = await commentsPOST(
    req("http://localhost/api/community/comments", { method: "POST", body: data, ip }),
  );
  const json = await res.json().catch(() => null);
  return { status: res.status, json };
}

async function adminHeaders(extra: Record<string, string> = {}) {
  return { authorization: `Bearer ${ADMIN_TOKEN}`, ...extra };
}

/** Next dynamic-route context: handlers read the id from { params }, not the URL. */
const P = (id: string) => ({ params: Promise.resolve({ id }) });

beforeAll(async () => {
  // two real ACTIVE models each with an ACTIVE variant
  const rows = await db.$queryRaw<
    { model_id: string; variant_id: string }[]
  >`SELECT DISTINCT ON (m.id) m.id::text AS model_id, v.id::text AS variant_id
     FROM "Variant" v JOIN "CarModel" m ON m.id = v."modelId"
     WHERE v.status = 'ACTIVE' AND m.status = 'ACTIVE'
     ORDER BY m.id LIMIT 2`;
  expect(rows.length, "need 2 active model+variant fixtures").toBe(2);
  modelA = rows[0].model_id; variantA = rows[0].variant_id;
  modelB = rows[1].model_id; variantB = rows[1].variant_id;
});

afterAll(async () => {
  // community tables only — fixtures + their votes/reports (cascade) + any
  // research candidate created by the admin-path test.
  await db.communityComment.deleteMany({ where: { body: { startsWith: MARK } } });
  await db.$executeRawUnsafe(
    `DELETE FROM "ResearchCandidate" WHERE "fieldName" = 'p117_test_field'`,
  );
  vi.restoreAllMocks();
});

beforeEach(() => {
  _resetRateLimitStore();
});

// ── A / B: scope persistence ────────────────────────────────────────────────
describe("P117-A/B scope persistence", () => {
  it("P117-A: model comment persists with correct modelId and GET returns it", async () => {
    const body = `${MARK} A model comment`;
    const { status, json } = await createComment({ modelId: modelA, authorName: "tester-a", body }, nextIp("a"));
    expect(status).toBe(201);
    expect(json.comment.modelId).toBe(modelA);
    expect(json.comment.variantId).toBeNull();

    const res = await commentsGET(req(`http://localhost/api/community/comments?modelId=${modelA}`));
    const list = await res.json();
    expect(list.comments.some((c: any) => c.id === json.comment.id)).toBe(true);
  });

  it("P117-B: variant comment persists with variantId; another model's scope does not include it", async () => {
    const body = `${MARK} B variant comment`;
    const { status, json } = await createComment({ variantId: variantB, authorName: "tester-b", body }, nextIp("b"));
    expect(status).toBe(201);
    expect(json.comment.variantId).toBe(variantB);

    const vRes = await commentsGET(req(`http://localhost/api/community/comments?variantId=${variantB}`));
    const vList = await vRes.json();
    expect(vList.comments.some((c: any) => c.id === json.comment.id)).toBe(true);

    // model A (a DIFFERENT model) must never receive this variant's comment
    const mRes = await commentsGET(req(`http://localhost/api/community/comments?modelId=${modelA}`));
    const mList = await mRes.json();
    expect(mList.comments.some((c: any) => c.id === json.comment.id)).toBe(false);
  });
});

// ── C: reply scope inheritance ──────────────────────────────────────────────
describe("P117-C reply cannot change scope", () => {
  it("P117-C: malicious reply payload (foreign modelId/variantId) still inherits the parent scope", async () => {
    const parent = await createComment(
      { modelId: modelA, authorName: "tester-c", body: `${MARK} C parent` },
      nextIp("c1"),
    );
    expect(parent.status).toBe(201);

    const reply = await createComment(
      {
        parentId: parent.json.comment.id,
        modelId: modelB, // attacker tries to move the reply to another model
        variantId: variantB, // …and onto another model's variant
        authorName: "tester-c2",
        body: `${MARK} C reply`,
      },
      nextIp("c2"),
    );
    expect(reply.status).toBe(201);
    expect(reply.json.comment.modelId).toBe(modelA); // parent scope, NOT modelB
    expect(reply.json.comment.variantId).toBeNull(); // parent scope, NOT variantB
    expect(reply.json.comment.parentId).toBe(parent.json.comment.id);
  });
});

// ── D: entity validation / consistency ──────────────────────────────────────
describe("P117-D entity scope validation fails closed", () => {
  it("P117-D1: malformed modelId on POST → 400 (no Prisma throw)", async () => {
    const r = await createComment({ modelId: "not-a-uuid", authorName: "t", body: `${MARK} D1` }, nextIp("d1"));
    expect(r.status).toBe(400);
  });

  it("P117-D2: nonexistent modelId → 404, no orphan row persisted", async () => {
    const ghost = "00000000-0000-4000-8000-000000000000";
    const r = await createComment({ modelId: ghost, authorName: "t", body: `${MARK} D2` }, nextIp("d2"));
    expect(r.status).toBe(404);
    const rows = await db.communityComment.count({ where: { body: `${MARK} D2` } });
    expect(rows, "nonexistent entity must not persist an orphan").toBe(0);
  });

  it("P117-D3: nonexistent variantId → 404, no orphan row persisted", async () => {
    const ghost = "00000000-0000-4000-8000-000000000001";
    const r = await createComment({ variantId: ghost, authorName: "t", body: `${MARK} D3` }, nextIp("d3"));
    expect(r.status).toBe(404);
    const rows = await db.communityComment.count({ where: { body: `${MARK} D3` } });
    expect(rows).toBe(0);
  });

  it("P117-D4: modelId+variantId mismatch (different models) → 400, nothing persisted", async () => {
    const r = await createComment(
      { modelId: modelA, variantId: variantB, authorName: "t", body: `${MARK} D4` },
      nextIp("d4"),
    );
    expect(r.status).toBe(400);
    const rows = await db.communityComment.count({ where: { body: `${MARK} D4` } });
    expect(rows).toBe(0);
  });

  it("P117-D5: existence checks filter status='ACTIVE' (inactive entities are rejected by the same path)", async () => {
    const spy = vi.spyOn(db.carModel, "findFirst");
    await createComment({ modelId: "00000000-0000-4000-8000-000000000002", authorName: "t", body: `${MARK} D5` }, nextIp("d5"));
    const modelCall = spy.mock.calls.find((c: any) => c[0]?.where?.status !== undefined);
    expect(modelCall, "model lookup must include status='ACTIVE'").toBeTruthy();
    expect((modelCall as any)[0].where.status).toBe("ACTIVE");
    spy.mockRestore();
  });

  it("P117-D6: malformed modelId on GET → 400 safe JSON; nonexistent model on GET → 404", async () => {
    const bad = await commentsGET(req("http://localhost/api/community/comments?modelId=zzz"));
    expect(bad.status).toBe(400);
    const missing = await commentsGET(
      req("http://localhost/api/community/comments?modelId=00000000-0000-4000-8000-000000000003"),
    );
    expect(missing.status).toBe(404);
  });

  it("P117-D7: malformed parentId → 400 (no Prisma throw)", async () => {
    const r = await createComment(
      { modelId: modelA, parentId: "nope", authorName: "t", body: `${MARK} D7` },
      nextIp("d7"),
    );
    expect(r.status).toBe(400);
  });
});

// ── E: research-lead privilege ──────────────────────────────────────────────
describe("P117-E research-lead cannot be self-granted", () => {
  it("P117-E1: client-supplied isResearchLead=true is stripped → persisted false", async () => {
    const r = await createComment(
      { modelId: modelA, authorName: "t", body: `${MARK} E self-lead`, isResearchLead: true },
      nextIp("e1"),
    );
    expect(r.status).toBe(201);
    expect(r.json.comment.isResearchLead, "client must not grant the badge").toBe(false);
    const row = await db.communityComment.findUnique({ where: { id: r.json.comment.id } });
    expect(row!.isResearchLead).toBe(false);
  });

  it("P117-E2: ONLY the admin research-lead route sets the badge", async () => {
    const c = await createComment(
      { modelId: modelA, authorName: "t", body: `${MARK} E admin-lead` },
      nextIp("e2"),
    );
    expect(c.status).toBe(201);
    const res = await leadPOST(
      req("http://localhost/api/admin/community/research-lead", {
        method: "POST",
        body: { commentId: c.json.comment.id, fieldName: "p117_test_field", proposedValue: "x", evidence: MARK },
        headers: await adminHeaders(),
        ip: nextIp("e2admin"),
      }),
    );
    expect(res.status).toBe(201);
    const row = await db.communityComment.findUnique({ where: { id: c.json.comment.id } });
    expect(row!.isResearchLead, "admin path must grant the badge").toBe(true);

    // unauthenticated caller cannot reach the setter
    const anon = await leadPOST(
      req("http://localhost/api/admin/community/research-lead", {
        method: "POST",
        body: { commentId: c.json.comment.id, fieldName: "p117_test_field", proposedValue: "x" },
        ip: nextIp("e2anon"),
      }),
    );
    expect(anon.status).toBe(401);
  });
});

// ── F: visibility ───────────────────────────────────────────────────────────
describe("P117-F hidden content never appears in public GET", () => {
  it("P117-F: HIDDEN parent hides parent+reply+count; DELETED reply disappears; RESTORE brings back", async () => {
    const parent = await createComment(
      { modelId: modelA, authorName: "t", body: `${MARK} F parent` },
      nextIp("f1"),
    );
    const reply = await createComment(
      { parentId: parent.json.comment.id, authorName: "t", body: `${MARK} F reply` },
      nextIp("f2"),
    );
    expect(parent.status).toBe(201);
    expect(reply.status).toBe(201);

    const url = `http://localhost/api/community/comments?modelId=${modelA}`;
    const before = await (await commentsGET(req(url))).json();
    const beforeIds = before.comments.map((c: any) => c.id);
    expect(beforeIds).toContain(parent.json.comment.id);

    // HIDE parent → parent AND its reply leave the list and the count
    const hide = await queuePATCH(
      req("http://localhost/api/admin/community/moderation", {
        method: "PATCH",
        body: { commentId: parent.json.comment.id, action: "HIDE" },
        headers: await adminHeaders(),
        ip: nextIp("f3"),
      }),
    );
    expect(hide.status).toBe(200);
    const afterHide = await (await commentsGET(req(url))).json();
    expect(afterHide.comments.map((c: any) => c.id)).not.toContain(parent.json.comment.id);
    expect(afterHide.comments.flatMap((c: any) => c.replies || []).map((r: any) => r.id)).not.toContain(
      reply.json.comment.id,
    );
    expect(afterHide.total).toBe(before.total - 1);

    // DELETE the reply directly → gone while parent restored below
    await queuePATCH(
      req("http://localhost/api/admin/community/moderation", {
        method: "PATCH",
        body: { commentId: reply.json.comment.id, action: "DELETE" },
        headers: await adminHeaders(),
        ip: nextIp("f4"),
      }),
    );
    // RESTORE parent → visible again, deleted reply stays out
    await queuePATCH(
      req("http://localhost/api/admin/community/moderation", {
        method: "PATCH",
        body: { commentId: parent.json.comment.id, action: "RESTORE" },
        headers: await adminHeaders(),
        ip: nextIp("f5"),
      }),
    );
    const final = await (await commentsGET(req(url))).json();
    expect(final.comments.map((c: any) => c.id)).toContain(parent.json.comment.id);
    expect(final.comments.flatMap((c: any) => c.replies || []).map((r: any) => r.id)).not.toContain(
      reply.json.comment.id,
    );
  });
});

// ── G + K: reports, auto-hide, moderation queue ─────────────────────────────
describe("P117-G/K reports, auto-hide, queue", () => {
  it("P117-G1: one report per comment per IP even with rotated cookies (idempotent)", async () => {
    const c = await createComment(
      { modelId: modelA, authorName: "t", body: `${MARK} G1 target` },
      nextIp("g1"),
    );
    const ip = nextIp("g1reporter");
    const firstRes = await reportPOST(
      req(`http://localhost/api/community/comments/${c.json.comment.id}/report`, {
        method: "POST", body: { reason: "SPAM" }, ip,
        headers: { cookie: "tci_token=attacker-token-aaaa" },
      }),
      P(c.json.comment.id),
    );
    expect(firstRes.status).toBe(200);
    const first = await firstRes.json();
    expect(first.ok).toBe(true);
    expect(first.autoHidden).toBe(false);

    const secondRes = await reportPOST(
      req(`http://localhost/api/community/comments/${c.json.comment.id}/report`, {
        method: "POST", body: { reason: "ABUSE" }, ip, // SAME IP, rotated/absent cookie
      }),
      P(c.json.comment.id),
    );
    expect(secondRes.status).toBe(200);
    const second = await secondRes.json();
    expect(second.message, "second report must be idempotent").toMatch(/ไปแล้ว|อยู่แล้ว/);
    const rows = await db.commentReport.count({ where: { commentId: c.json.comment.id } });
    expect(rows, "same IP must not mint a second reporter identity").toBe(1);
  });

  it("P117-G2+K: 3 distinct reporters → FLAGGED with report rows preserved; queue lists it; HIDE reflected on public GET", async () => {
    const c = await createComment(
      { modelId: modelA, authorName: "t", body: `${MARK} G2 target` },
      nextIp("g2"),
    );
    const reasons = ["SPAM", "ABUSE", "INACCURATE"] as const;
    let last: any = null;
    for (let i = 0; i < 3; i++) {
      const res = await reportPOST(
        req(`http://localhost/api/community/comments/${c.json.comment.id}/report`, {
          method: "POST", body: { reason: reasons[i] }, ip: nextIp(`g2r${i}`),
        }),
        P(c.json.comment.id),
      );
      last = await res.json();
      expect(res.status).toBe(200);
    }
    expect(last.autoHidden).toBe(true);
    expect(last.status).toBe("FLAGGED");
    const reportRows = await db.commentReport.count({ where: { commentId: c.json.comment.id } });
    expect(reportRows, "auto-hide must keep every report as evidence").toBe(3);
    const flagged = await db.communityComment.findUnique({ where: { id: c.json.comment.id } });
    expect(flagged!.status).toBe("FLAGGED");

    // queue shows it with its reports
    const queue = await queueGET(
      req(`http://localhost/api/admin/community/moderation?status=FLAGGED`, {
        headers: await adminHeaders(), ip: nextIp("g2admin"),
      }),
    );
    expect(queue.status).toBe(200);
    const q = await queue.json();
    const item = q.comments.find((x: any) => x.commentId === c.json.comment.id);
    expect(item, "flagged comment must appear in the moderation queue").toBeTruthy();
    expect(item.reports.length).toBe(3);
    expect(item.briefByReason).toMatchObject({ SPAM: 1, ABUSE: 1, INACCURATE: 1 });

    // queue requires auth
    const anon = await queueGET(req(`http://localhost/api/admin/community/moderation`, { ip: nextIp("g2anon") }));
    expect(anon.status).toBe(401);

    // HIDE → public GET excludes; RESTORE → back
    const url = `http://localhost/api/community/comments?modelId=${modelA}`;
    await queuePATCH(
      req("http://localhost/api/admin/community/moderation", {
        method: "PATCH", body: { commentId: c.json.comment.id, action: "HIDE" },
        headers: await adminHeaders(), ip: nextIp("g2hide"),
      }),
    );
    const hidden = await (await commentsGET(req(url))).json();
    expect(hidden.comments.map((x: any) => x.id)).not.toContain(c.json.comment.id);
    await queuePATCH(
      req("http://localhost/api/admin/community/moderation", {
        method: "PATCH", body: { commentId: c.json.comment.id, action: "RESTORE" },
        headers: await adminHeaders(), ip: nextIp("g2restore"),
      }),
    );
    const back = await (await commentsGET(req(url))).json();
    expect(back.comments.map((x: any) => x.id)).toContain(c.json.comment.id);
  });
});

// ── H: voting ───────────────────────────────────────────────────────────────
describe("P117-H voting is deterministic per identity", () => {
  it("P117-H: duplicate same-value idempotent, switch deterministic, counters == vote rows", async () => {
    const c = await createComment(
      { modelId: modelA, authorName: "t", body: `${MARK} H target` },
      nextIp("h1"),
    );
    const id = c.json.comment.id;
    const ip = nextIp("hvoter");
    const vote = (value: number) =>
      votePOST(
        req(`http://localhost/api/community/comments/${id}/vote`, { method: "POST", body: { value }, ip }),
        P(id),
      ).then((r) => r.json());

    expect(await vote(1)).toMatchObject({ ok: true, upvotes: 1, downvotes: 0 });
    expect(await vote(1)).toMatchObject({ ok: true, upvotes: 1, downvotes: 0 }); // idempotent
    expect(await vote(-1)).toMatchObject({ ok: true, upvotes: 0, downvotes: 1 }); // switch
    expect(await vote(1)).toMatchObject({ ok: true, upvotes: 1, downvotes: 0 }); // switch back

    const rows = await db.commentVote.findMany({ where: { commentId: id } });
    expect(rows.length, "one identity → one vote row").toBe(1);
    expect(rows[0].value).toBe(1);
    const fresh = await db.communityComment.findUnique({ where: { id } });
    const up = rows.filter((r) => r.value === 1).length;
    const down = rows.filter((r) => r.value === -1).length;
    expect(fresh!.upvotes).toBe(up);
    expect(fresh!.downvotes).toBe(down);
  });
});

// ── I: input validation / safe errors ───────────────────────────────────────
describe("P117-I validation and safe client responses", () => {
  it("P117-I1: malformed vote/report/comment ids → 400 safe JSON (no throw)", async () => {
    const v = await votePOST(
      req("http://localhost/api/community/comments/not-a-uuid/vote", {
        method: "POST", body: { value: 1 }, ip: nextIp("i1"),
      }),
      P("not-a-uuid"),
    );
    expect(v.status).toBe(400);
    const rp = await reportPOST(
      req("http://localhost/api/community/comments/not-a-uuid/report", {
        method: "POST", body: { reason: "SPAM" }, ip: nextIp("i2"),
      }),
      P("not-a-uuid"),
    );
    expect(rp.status).toBe(400);
  });

  it("P117-I2: page=abc → 400 (no NaN query into Prisma); limit out of range → 400", async () => {
    const bad = await commentsGET(req(`http://localhost/api/community/comments?modelId=${modelA}&page=abc`));
    expect(bad.status).toBe(400);
    const badLimit = await commentsGET(req(`http://localhost/api/community/comments?modelId=${modelA}&limit=9999`));
    expect(badLimit.status).toBe(400);
  });

  it("P117-I3: invalid vote value, invalid report reason, oversized body → 400", async () => {
    const c = await createComment({ modelId: modelA, authorName: "t", body: `${MARK} I3` }, nextIp("i3"));
    const v = await votePOST(
      req(`http://localhost/api/community/comments/${c.json.comment.id}/vote`, {
        method: "POST", body: { value: 5 }, ip: nextIp("i4"),
      }),
      P(c.json.comment.id),
    );
    expect(v.status).toBe(400);
    const rp = await reportPOST(
      req(`http://localhost/api/community/comments/${c.json.comment.id}/report`, {
        method: "POST", body: { reason: "NOT_A_REASON" }, ip: nextIp("i5"),
      }),
      P(c.json.comment.id),
    );
    expect(rp.status).toBe(400);
    const over = await createComment(
      { modelId: modelA, authorName: "t", body: `${MARK} ${"x".repeat(2001)}` },
      nextIp("i6"),
    );
    expect(over.status).toBe(400);
  });

  it("P117-I4: admin PATCH with malformed commentId → 400 (no Prisma throw)", async () => {
    const res = await queuePATCH(
      req("http://localhost/api/admin/community/moderation", {
        method: "PATCH", body: { commentId: "garbage", action: "HIDE" },
        headers: await adminHeaders(), ip: nextIp("i7"),
      }),
    );
    expect(res.status).toBe(400);
  });
});

// ── J: blocked words ────────────────────────────────────────────────────────
describe("P117-J blocked-word detection is deterministic and never persists", () => {
  it("P117-J: spam body → 400, NO row persisted, same input always rejected", async () => {
    const spamBody = `${MARK} คลิกเลย คาสิโนออนไลน์ เครดิตฟรี ไม่ต้องฝาก`;
    const first = await createComment({ modelId: modelA, authorName: "t", body: spamBody }, nextIp("j1"));
    expect(first.status).toBe(400);
    const rows = await db.communityComment.count({ where: { body: spamBody } });
    expect(rows, "blocked content must not persist as anything").toBe(0);
    // deterministic on the same fixture input
    const second = await createComment({ modelId: modelA, authorName: "t", body: spamBody }, nextIp("j2"));
    expect(second.status).toBe(400);

    // a normal comment still passes (no over-blocking of the marker itself)
    const ok = await createComment(
      { modelId: modelA, authorName: "t", body: `${MARK} J benign driving impression` },
      nextIp("j3"),
    );
    expect(ok.status).toBe(201);
  });
});

// ── L: community never becomes official fact ────────────────────────────────
describe("P117-L anecdotal boundary", () => {
  it("P117-L1: catalog/evidence sources contain ZERO references to community tables", async () => {
    const { readFileSync } = await import("node:fs");
    const files = [
      "lib/catalog/queries.ts",
      "lib/catalog/price-sql.ts",
      "lib/catalog/detail-queries.ts",
      "lib/ai/evidence-gate.ts",
      "lib/ai/retrieval/catalog-search.ts",
      "src/app/cars/[manufacturer]/[model]/page.tsx",
    ];
    for (const f of files) {
      const src = readFileSync(`${process.cwd()}/${f}`, "utf8");
      for (const token of ["CommunityComment", "CommentVote", "CommentReport", "communityComment"]) {
        expect(src.includes(token), `${f} must not reference ${token}`).toBe(false);
      }
    }
  });

  it("P117-L2: CommunitySection keeps the anecdotal label + disclaimer", async () => {
    const { readFileSync } = await import("node:fs");
    const src = readFileSync(`${process.cwd()}/src/components/community/CommunitySection.tsx`, "utf8");
    expect(src).toContain("ความคิดเห็นจากชุมชน");
    expect(src).toContain("ไม่ใช่ข้อมูลที่ได้รับการตรวจสอบจากแหล่งทางการ");
  });
});

// ── M: deterministic ordering ───────────────────────────────────────────────
describe("P117-M deterministic GET", () => {
  it("P117-M: orderBy carries a final id tiebreak; repeated GET returns identical order", async () => {
    const spy = vi.spyOn(db.communityComment, "findMany");
    const url = `http://localhost/api/community/comments?modelId=${modelA}`;
    const r1 = await (await commentsGET(req(url))).json();
    const r2 = await (await commentsGET(req(url))).json();

    const orderBy = spy.mock.calls[0][0]?.orderBy as any[];
    expect(Array.isArray(orderBy)).toBe(true);
    const last = orderBy[orderBy.length - 1];
    expect(last, "orderBy must end with a deterministic tiebreak").toMatchObject({ id: "asc" });
    spy.mockRestore();

    expect(r1.comments.map((c: any) => c.id)).toEqual(r2.comments.map((c: any) => c.id));
    expect(r1.comments.map((c: any) => c.createdAt)).toEqual(r2.comments.map((c: any) => c.createdAt));
  });
});
