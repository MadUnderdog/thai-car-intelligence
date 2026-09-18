"use client";

import { useState, useEffect } from "react";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

type CommunityComment = {
  id: string;
  authorName: string;
  body: string;
  upvotes: number;
  downvotes: number;
  isResearchLead: boolean;
  createdAt: string;
  parentId?: string | null;
  replies?: CommunityComment[];
};

const REPORT_REASONS: { value: string; label: string }[] = [
  { value: "SPAM", label: "สแปม" },
  { value: "ABUSE", label: "ไม่เหมาะสม" },
  { value: "INACCURATE", label: "ข้อมูลไม่ถูกต้อง" },
  { value: "OTHER", label: "อื่น ๆ" },
];

function timeAgoTh(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "เมื่อสักครู่";
  if (mins < 60) return `${mins} นาทีที่แล้ว`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} ชั่วโมงที่แล้ว`;
  const days = Math.floor(hours / 24);
  return `${days} วันที่แล้ว`;
}

export function CommunitySection({ modelId }: { modelId: string }) {
  const [comments, setComments] = useState<CommunityComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [authorName, setAuthorName] = useState("");
  const [body, setBody] = useState("");
  const [replyTo, setReplyTo] = useState<{ id: string; name: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [votes, setVotes] = useState<Record<string, number>>({});
  const [reports, setReports] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/community/comments?modelId=${encodeURIComponent(modelId)}`);
        const data = await res.json();
        if (!cancelled) setComments(Array.isArray(data.comments) ? data.comments : []);
      } catch {
        if (!cancelled) setComments([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [modelId]);

  async function submit(parentId?: string) {
    setError(null);
    setNotice(null);
    const text = body.trim();
    const name = authorName.trim();
    if (!name) return setError("กรุณาระบุชื่อเล่น");
    if (!text) return setError("กรุณาพิมพ์ความคิดเห็น");
    if (text.length > 2000) return setError("เนื้อหายาวเกิน 2,000 ตัวอักษร");
    setSubmitting(true);
    try {
      const res = await fetch("/api/community/comments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          modelId,
          authorName: name,
          body: text,
          parentId: parentId || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.error || "ไม่สามารถโพสต์ความคิดเห็นได้");
        return;
      }
      const created: CommunityComment = data.comment;
      setBody("");
      setReplyTo(null);
      if (parentId) {
        setComments((prev) =>
          prev.map((c) => ({
            ...c,
            replies: c.id === parentId ? [...(c.replies || []), { ...created, replies: [] }] : c.replies,
          })),
        );
        setNotice("ตอบกลับสำเร็จแล้ว");
      } else {
        setComments((prev) => [{ ...created, replies: [] }, ...prev]);
        setNotice("โพสต์ความคิดเห็นสำเร็จแล้ว");
      }
    } catch {
      setError("เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง");
    } finally {
      setSubmitting(false);
    }
  }

  async function vote(commentId: string, value: 1 | -1) {
    setError(null);
    try {
      const res = await fetch(`/api/community/comments/${commentId}/vote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.error || "ไม่สามารถโหวตได้");
        return;
      }
      setVotes((prev) => ({ ...prev, [commentId]: value }));
      applyCounts(commentId, data.upvotes ?? undefined, data.downvotes ?? undefined);
    } catch {
      setError("เกิดข้อผิดพลาดในการโหวต");
    }
  }

  async function report(commentId: string, reason: string) {
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(`/api/community/comments/${commentId}/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.error || "ไม่สามารถรายงานได้");
        return;
      }
      setReports((prev) => ({ ...prev, [commentId]: reason }));
      setNotice(data?.autoHidden ? "ขอบคุณสำหรับการรายงาน — ความคิดเห็นนี้ถูกระงับการแสดงผลแล้ว" : "รับรายงานเรียบร้อยแล้ว ขอบคุณ");
    } catch {
      setError("เกิดข้อผิดพลาดในการรายงาน");
    }
  }

  function applyCounts(commentId: string, up?: number, down?: number) {
    setComments((prev) =>
      prev.map((c) => {
        if (c.id === commentId && up !== undefined) return { ...c, upvotes: up, downvotes: down ?? c.downvotes };
        return {
          ...c,
          replies: (c.replies || []).map((r) =>
            r.id === commentId && up !== undefined ? { ...r, upvotes: up, downvotes: down ?? r.downvotes } : r,
          ),
        };
      }),
    );
  }

  function CommentItem({ c, depth }: { c: CommunityComment; depth: number }) {
    const voted = votes[c.id];
    const reported = reports[c.id];
    return (
      <div className={depth > 0 ? "ml-6 border-l border-[var(--color-gray-200)] pl-4" : ""}>
        <div className="py-3 border-b border-[var(--color-gray-100)] last:border-0">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium text-[var(--color-gray-900)]">{c.authorName}</span>
            {c.isResearchLead && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-primary-50)] text-[var(--color-primary-700)]">
                กำลังตรวจสอบข้อมูล
              </span>
            )}
            <span className="text-[var(--color-gray-400)] text-xs">{timeAgoTh(c.createdAt)}</span>
          </div>
          <p className="text-[var(--color-gray-700)] mt-1 whitespace-pre-wrap break-words">{c.body}</p>
          <div className="flex items-center gap-3 mt-2 text-sm">
            <button
              onClick={() => vote(c.id, 1)}
              className={`flex items-center gap-1 hover:text-[var(--color-primary-600)] ${voted === 1 ? "text-[var(--color-primary-600)] font-semibold" : "text-[var(--color-gray-500)]"}`}
              aria-label="โหวตขึ้น"
            >
              👍 {c.upvotes}
            </button>
            <button
              onClick={() => vote(c.id, -1)}
              className={`flex items-center gap-1 hover:text-[var(--color-danger-500)] ${voted === -1 ? "text-[var(--color-danger-500)] font-semibold" : "text-[var(--color-gray-500)]"}`}
              aria-label="โหวตลง"
            >
              👎 {c.downvotes}
            </button>
            {depth === 0 && (
              <button
                onClick={() => setReplyTo({ id: c.id, name: c.authorName })}
                className="text-[var(--color-gray-500)] hover:text-[var(--color-primary-600)]"
              >
                ตอบกลับ
              </button>
            )}
            {!reported && (
              <details className="relative">
                <summary className="text-[var(--color-gray-400)] text-xs cursor-pointer hover:text-[var(--color-danger-500)] list-none">
                  รายงาน
                </summary>
                <div className="absolute z-10 mt-1 bg-white border border-[var(--color-gray-200)] rounded-[var(--radius-md)] shadow-sm p-2 flex flex-col gap-1">
                  {REPORT_REASONS.map((r) => (
                    <button
                      key={r.value}
                      onClick={() => report(c.id, r.value)}
                      className="text-left text-xs px-3 py-1.5 rounded hover:bg-[var(--color-gray-50)] text-[var(--color-gray-700)]"
                    >
                      {r.label}
                    </button>
                  ))}
                </div>
              </details>
            )}
            {reported && <span className="text-xs text-[var(--color-gray-400)]">รายงานแล้ว</span>}
          </div>
        </div>
        {(c.replies || []).map((r) => (
          <CommentItem key={r.id} c={r} depth={depth + 1} />
        ))}
      </div>
    );
  }

  return (
    <Card>
      <CardBody>
        <h2 className="text-lg font-semibold text-[var(--color-gray-900)] mb-4">
          ความคิดเห็นจากชุมชน{comments.length > 0 ? ` (${comments.length})` : ""}
        </h2>
        {error && (
          <div className="mb-3 text-sm text-[var(--color-danger-600)] bg-[var(--color-danger-50)] rounded-[var(--radius-md)] px-3 py-2">
            {error}
          </div>
        )}
        {notice && (
          <div className="mb-3 text-sm text-[var(--color-primary-600)] bg-[var(--color-primary-50)] rounded-[var(--radius-md)] px-3 py-2">
            {notice}
          </div>
        )}

        <div className="space-y-2 mb-6">
          {replyTo && (
            <div className="text-sm text-[var(--color-gray-500)]">
              กำลังตอบกลับ {replyTo.name}{" "}
              <button className="underline hover:text-[var(--color-danger-500)]" onClick={() => setReplyTo(null)}>
                ยกเลิก
              </button>
            </div>
          )}
          <input
            className="w-full border border-[var(--color-gray-300)] rounded-[var(--radius-md)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-500)]"
            placeholder="ชื่อเล่น"
            maxLength={60}
            value={authorName}
            onChange={(e) => setAuthorName(e.target.value)}
          />
          <textarea
            className="w-full border border-[var(--color-gray-300)] rounded-[var(--radius-md)] px-3 py-2 text-sm min-h-[80px] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-500)]"
            placeholder={replyTo ? "พิมพ์ข้อความตอบกลับ..." : "แบ่งปันประสบการณ์หรือข้อมูลเกี่ยวกับรุ่นนี้"}
            maxLength={2000}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <Button
            size="sm"
            variant="primary"
            disabled={submitting}
            isLoading={submitting}
            onClick={() => submit(replyTo?.id)}
          >
            {replyTo ? "ส่งคำตอบ" : "โพสต์ความคิดเห็น"}
          </Button>
          <p className="text-xs text-[var(--color-gray-400)]">
            ความคิดเห็นเป็นของผู้ใช้งาน ไม่ใช่ข้อมูลที่ได้รับการตรวจสอบจากแหล่งทางการ
          </p>
        </div>

        {loading ? (
          <p className="text-sm text-[var(--color-gray-400)]">กำลังโหลดความคิดเห็น...</p>
        ) : comments.length === 0 ? (
          <p className="text-sm text-[var(--color-gray-400)]">ยังไม่มีความคิดเห็น — มาเป็นคนแรกที่แบ่งปัน!</p>
        ) : (
          <div>
            {comments.map((c) => (
              <CommentItem key={c.id} c={c} depth={0} />
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
