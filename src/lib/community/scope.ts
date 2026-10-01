/**
 * P117 — shared, fail-closed scope validation for community content.
 *
 * One predicate for every community entry point:
 *   - UUID format checked first (malformed input → 400, never a Prisma throw)
 *   - entity must EXIST and be ACTIVE (nonexistent/inactive → 404, no orphans)
 *   - modelId + variantId together must agree (mismatch → 400)
 *   - replies never take scope from the client — only from the parent
 */
import db from "../../../lib/db";
import { isValidUuid } from "../../../lib/validation/api-params";

export type ScopeOk = { ok: true; modelId: string | null; variantId: string | null };
export type ScopeErr = { ok: false; status: 400 | 404; error: string };
export type ScopeResult = ScopeOk | ScopeErr;

const bad = (error: string): ScopeErr => ({ ok: false, status: 400, error });
const missing = (error: string): ScopeErr => ({ ok: false, status: 404, error });

/** Top-level comment scope: modelId and/or variantId, validated end-to-end. */
export async function resolveTopLevelScope(input: {
  modelId?: unknown;
  variantId?: unknown;
}): Promise<ScopeResult> {
  const { modelId, variantId } = input;
  if (!modelId && !variantId) {
    return bad("ต้องระบุ modelId หรือ variantId");
  }
  if (modelId !== undefined && modelId !== null) {
    if (typeof modelId !== "string" || !isValidUuid(modelId)) return bad("modelId ไม่ถูกต้อง");
  }
  if (variantId !== undefined && variantId !== null) {
    if (typeof variantId !== "string" || !isValidUuid(variantId)) return bad("variantId ไม่ถูกต้อง");
  }

  let variantModelId: string | null = null;
  if (variantId) {
    const variant = await db.variant.findFirst({
      where: { id: variantId as string, status: "ACTIVE" },
      select: { modelId: true },
    });
    if (!variant) return missing("ไม่พบ variant ที่ระบุหรือถูกปิดการใช้งาน");
    variantModelId = variant.modelId;
  }
  if (modelId) {
    const model = await db.carModel.findFirst({
      where: { id: modelId as string, status: "ACTIVE" },
      select: { id: true },
    });
    if (!model) return missing("ไม่พบ model ที่ระบุหรือถูกปิดการใช้งาน");
    if (variantModelId && variantModelId !== modelId) {
      return bad("variant ที่ระบุไม่ได้อยู่ใน model ที่ระบุ");
    }
  }
  // variant-only comment: allowed — modelId column stays null (exact-column scoping)

  return { ok: true, modelId: (modelId as string) ?? null, variantId: (variantId as string) ?? null };
}

export type ReplyParent = { id: string; modelId: string | null; variantId: string | null };

/** Reply scope comes ONLY from the parent (client scope fields are ignored). */
export async function resolveReplyParent(parentId: unknown): Promise<
  { ok: true; parent: ReplyParent } | ScopeErr
> {
  if (typeof parentId !== "string" || !isValidUuid(parentId)) {
    return bad("parentId ไม่ถูกต้อง");
  }
  const parent = await db.communityComment.findUnique({
    where: { id: parentId },
    select: { id: true, status: true, deletedAt: true, modelId: true, variantId: true },
  });
  if (!parent || parent.status !== "VISIBLE" || parent.deletedAt) {
    return missing("ไม่พบความคิดเห็นต้นทางหรือถูกปิดการแสดงผล");
  }
  return {
    ok: true,
    parent: { id: parent.id, modelId: parent.modelId, variantId: parent.variantId },
  };
}

/** GET-side entity check: malformed id → 400, missing/inactive → 404. */
export async function assertActiveEntityForRead(
  kind: "model" | "variant",
  rawId: string,
): Promise<{ ok: true } | ScopeErr> {
  if (!isValidUuid(rawId)) return bad(kind === "model" ? "modelId ไม่ถูกต้อง" : "variantId ไม่ถูกต้อง");
  if (kind === "model") {
    const model = await db.carModel.findFirst({ where: { id: rawId, status: "ACTIVE" }, select: { id: true } });
    if (!model) return missing("ไม่พบ model ที่ระบุหรือถูกปิดการใช้งาน");
  } else {
    const variant = await db.variant.findFirst({ where: { id: rawId, status: "ACTIVE" }, select: { id: true } });
    if (!variant) return missing("ไม่พบ variant ที่ระบุหรือถูกปิดการใช้งาน");
  }
  return { ok: true };
}

export function parsePagination(
  pageRaw: string | null,
  limitRaw: string | null,
): { ok: true; page: number; limit: number } | ScopeErr {
  const page = pageRaw === null ? 1 : Number(pageRaw);
  const limit = limitRaw === null ? 20 : Number(limitRaw);
  if (!Number.isInteger(page) || page < 1) return bad("page ไม่ถูกต้อง");
  if (!Number.isInteger(limit) || limit < 1 || limit > 50) return bad("limit ไม่ถูกต้อง");
  return { ok: true, page, limit };
}
