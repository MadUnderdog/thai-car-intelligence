/**
 * P117-I6 — internal DB failures must surface as SAFE client-facing JSON:
 * HTTP 500 with a generic message, no SQL text, no Prisma internals, no stack.
 *
 * Red-before: on base 2a30e39 the community routes have no try/catch, so a
 * DB error propagates as a thrown exception (no response object at all).
 * The lib/db module is mocked here ONLY in this file (separate module graph)
 * to raise an error that deliberately contains SQL text.
 */
import { describe, it, expect, beforeAll, vi } from "vitest";
import { NextRequest } from "next/server";

vi.mock("../lib/db", () => {
  const boom = () => {
    throw new Error('simulated DB failure while running: SELECT * FROM "CommunityComment" WHERE "modelId" = $1');
  };
  const exploding: any = new Proxy(
    {},
    {
      get: () => boom,
    },
  );
  return {
    default: {
      communityComment: exploding,
      commentVote: exploding,
      commentReport: exploding,
      researchRun: exploding,
      researchCandidate: exploding,
      carModel: exploding,
      variant: exploding,
      $transaction: boom,
    },
  };
});

import { GET as commentsGET, POST as commentsPOST } from "../src/app/api/community/comments/route";
import { POST as votePOST } from "../src/app/api/community/comments/[id]/vote/route";
import { POST as reportPOST } from "../src/app/api/community/comments/[id]/report/route";
import { GET as queueGET, PATCH as queuePATCH } from "../src/app/api/admin/community/moderation/route";
import { POST as leadPOST } from "../src/app/api/admin/community/research-lead/route";

const VALID_UUID = "11111111-2222-4333-8444-555555555555";
process.env.ADMIN_API_TOKEN = "p117-test-token";
let ipSeq = 0;

function req(
  url: string,
  opts: { method?: string; body?: unknown; ip?: string; headers?: Record<string, string> } = {},
): NextRequest {
  ipSeq += 1;
  const headers: Record<string, string> = { "content-type": "application/json", ...(opts.headers || {}) };
  headers["x-forwarded-for"] = opts.ip || `10.9.${(ipSeq >> 8) & 255}.${ipSeq & 255}`;
  if (!opts.headers?.authorization && opts.headers?.["with-auth"] === undefined) {
    // default: authorized admin unless the test opts out
  }
  return new NextRequest(url, {
    method: opts.method || "GET",
    headers,
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  });
}

function assertSafe(res: Response, label: string) {
  expect(res.status, `${label}: expected 500 on internal DB failure`).toBe(500);
  return res.json().then((body) => {
    const raw = JSON.stringify(body);
    expect(raw, `${label}: body must be JSON with an error field`).toMatch(/"error"/);
    for (const leak of ["SELECT", "CommunityComment", "prisma", "Prisma", "node_modules", "at Object."]) {
      expect(raw.includes(leak), `${label}: response leaks internal detail "${leak}"`).toBe(false);
    }
  });
}

beforeAll(() => {
  process.env.ADMIN_API_TOKEN = "p117-test-token";
});

describe("P117-I6: DB failures are client-safe on every community route", () => {
  it("P117-I6a: comments GET → safe 500", async () => {
    const res = await commentsGET(req(`http://localhost/api/community/comments?modelId=${VALID_UUID}`));
    await assertSafe(res, "commentsGET");
  });

  it("P117-I6b: comments POST → safe 500", async () => {
    const res = await commentsPOST(
      req("http://localhost/api/community/comments", {
        method: "POST",
        body: { modelId: VALID_UUID, authorName: "t", body: "hello from the error-safety fixture" },
      }),
    );
    await assertSafe(res, "commentsPOST");
  });

  it("P117-I6c: vote POST → safe 500", async () => {
    const res = await votePOST(
      req(`http://localhost/api/community/comments/${VALID_UUID}/vote`, { method: "POST", body: { value: 1 } }),
      { params: Promise.resolve({ id: VALID_UUID }) },
    );
    await assertSafe(res, "votePOST");
  });

  it("P117-I6d: report POST → safe 500", async () => {
    const res = await reportPOST(
      req(`http://localhost/api/community/comments/${VALID_UUID}/report`, {
        method: "POST",
        body: { reason: "SPAM" },
      }),
      { params: Promise.resolve({ id: VALID_UUID }) },
    );
    await assertSafe(res, "reportPOST");
  });

  it("P117-I6e: moderation queue GET → safe 500", async () => {
    const res = await queueGET(
      req("http://localhost/api/admin/community/moderation", {
        headers: { authorization: "Bearer p117-test-token" },
      }),
    );
    await assertSafe(res, "queueGET");
  });

  it("P117-I6f: moderation PATCH → safe 500", async () => {
    const res = await queuePATCH(
      req("http://localhost/api/admin/community/moderation", {
        method: "PATCH",
        body: { commentId: VALID_UUID, action: "HIDE" },
        headers: { authorization: "Bearer p117-test-token" },
      }),
    );
    await assertSafe(res, "queuePATCH");
  });

  it("P117-I6g: research-lead POST → safe 500 (auth still checked first)", async () => {
    const res = await leadPOST(
      req("http://localhost/api/admin/community/research-lead", {
        method: "POST",
        body: { commentId: VALID_UUID, fieldName: "power", proposedValue: "100" },
        headers: { authorization: "Bearer p117-test-token" },
      }),
    );
    await assertSafe(res, "leadPOST");

    const anon = await leadPOST(
      req("http://localhost/api/admin/community/research-lead", {
        method: "POST",
        body: { commentId: VALID_UUID, fieldName: "power", proposedValue: "100" },
        headers: { authorization: "Bearer wrong-token" },
      }),
    );
    expect(anon.status, "auth gate must run BEFORE any DB access").toBe(401);
  });
});
