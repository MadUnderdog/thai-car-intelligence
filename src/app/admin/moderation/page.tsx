"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

type Report = { id: string; reason: string; createdAt: string };
type ModerationItem = {
  commentId: string;
  authorName: string;
  body: string;
  status: string;
  flaggedCount: number;
  upvotes: number;
  downvotes: number;
  isResearchLead: boolean;
  createdAt: string;
  reports: Report[];
  briefByReason: Record<string, number>;
};

const STATUS_LABELS: Record<string, string> = {
  VISIBLE: "แสดงอยู่", HIDDEN: "ซ่อนแล้ว", FLAGGED: "ถูกรายงาน", DELETED: "ลบแล้ว",
};

const STATUS_VARIANT: Record<string, "success" | "warning" | "default" | "danger"> = {
  VISIBLE: "success", HIDDEN: "default", FLAGGED: "warning", DELETED: "danger",
};

export default function AdminModerationPage() {
  const [items, setItems] = useState<ModerationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [researchLeadComment, setResearchLeadComment] = useState<string | null>(null);
  const [leadField, setLeadField] = useState("");
  const [leadValue, setLeadValue] = useState("");

  const loadQueue = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: "20" });
      if (statusFilter) params.set("status", statusFilter);
      const res = await fetch(`/api/admin/community/moderation?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { setError("ไม่ได้รับอนุญาต"); setLoading(false); return; }
      const data = await res.json();
      setItems(data.comments || []);
      setTotal(data.total || 0);
    } catch { setError("เชื่อมต่อเซิร์ฟเวอร์ไม่ได้"); }
    setLoading(false);
  }, [token, page, statusFilter]);

  useEffect(() => { if (token) loadQueue(); }, [token, loadQueue]);

  async function act(commentId: string, action: "HIDE" | "DELETE" | "RESTORE") {
    setActionLoading(commentId);
    try {
      await fetch("/api/admin/community/moderation", {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ commentId, action }),
      });
      setItems((prev) => prev.filter((i) => i.commentId !== commentId));
      setTotal((t) => t - 1);
    } catch { /* ignore */ }
    setActionLoading(null);
  }

  async function handoffResearchLead(commentId: string) {
    if (!leadField.trim() || !leadValue.trim()) return;
    setActionLoading(commentId);
    try {
      const res = await fetch("/api/admin/community/research-lead", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ commentId, fieldName: leadField, proposedValue: leadValue }),
      });
      if (res.ok) {
        setItems((prev) => prev.map((i) => i.commentId === commentId ? { ...i, isResearchLead: true } : i));
        setResearchLeadComment(null);
        setLeadField("");
        setLeadValue("");
      }
    } catch { /* ignore */ }
    setActionLoading(null);
  }

  if (!token) {
    return (
      <div className="container-narrow py-8">
        <Card><CardBody className="max-w-md mx-auto py-8">
          <h1 className="text-xl font-bold mb-4">เข้าสู่ระบบผู้ดูแล</h1>
          <input type="password" placeholder="Admin Token" className="w-full border rounded px-3 py-2 mb-3"
            onChange={(e) => setToken(e.target.value)} />
          <Button onClick={() => setToken(token)} disabled={!token}>เข้าสู่ระบบ</Button>
        </CardBody></Card>
      </div>
    );
  }

  return (
    <div className="container-narrow py-8">
      <h1 className="text-2xl font-bold mb-4">จัดการความคิดเห็น</h1>
      <p className="text-sm text-[var(--color-gray-500)] mb-4">{total} รายการ</p>

      <div className="flex gap-2 mb-4">
        {["", "FLAGGED", "HIDDEN", "VISIBLE"].map((s) => (
          <button key={s} onClick={() => { setStatusFilter(s); setPage(1); }}
            className={`px-3 py-1 text-sm rounded border ${statusFilter === s ? "bg-[var(--color-primary-600)] text-white border-[var(--color-primary-600)]" : "border-[var(--color-gray-300)] text-[var(--color-gray-600)]"}`}>
            {s ? STATUS_LABELS[s] : "ทั้งหมด"}
          </button>
        ))}
      </div>

      {loading ? <div className="text-center py-8">กำลังโหลด...</div> : error ? <div className="text-red-500">{error}</div> : items.length === 0 ? (
        <Card><CardBody className="text-center py-8 text-[var(--color-gray-500)]">ไม่มีความคิดเห็นที่ต้องจัดการ</CardBody></Card>
      ) : (
        <>
          <div className="space-y-4">
            {items.map((item) => (
              <Card key={item.commentId}>
                <CardBody>
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{item.authorName}</span>
                      <Badge variant={STATUS_VARIANT[item.status] || "default"}>{STATUS_LABELS[item.status]}</Badge>
                      {item.isResearchLead && <Badge variant="info">research lead</Badge>}
                      <span className="text-xs text-[var(--color-gray-400)]"> flagged={item.flaggedCount}</span>
                    </div>
                    <span className="text-xs text-[var(--color-gray-400)]">{new Date(item.createdAt).toLocaleString("th-TH")}</span>
                  </div>
                  <p className="text-sm mb-3">{item.body}</p>
                  <div className="text-xs text-[var(--color-gray-500)] mb-3">
                    รายงาน: {Object.entries(item.briefByReason).map(([r, c]) => `${r}(${c})`).join(", ")}
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <Button variant="secondary" size="sm" disabled={actionLoading === item.commentId} onClick={() => act(item.commentId, "HIDE")}>ซ่อน</Button>
                    <Button variant="secondary" size="sm" disabled={actionLoading === item.commentId} onClick={() => act(item.commentId, "DELETE")}>ลบ</Button>
                    {item.status !== "VISIBLE" && (
                      <Button variant="ghost" size="sm" disabled={actionLoading === item.commentId} onClick={() => act(item.commentId, "RESTORE")}>กู้คืน</Button>
                    )}
                    {!item.isResearchLead && (
                      <Button variant="ghost" size="sm" onClick={() => setResearchLeadComment(researchLeadComment === item.commentId ? null : item.commentId)}>
                        ส่งต่อเป็น research lead
                      </Button>
                    )}
                  </div>
                  {researchLeadComment === item.commentId && (
                    <div className="mt-3 p-3 bg-[var(--color-gray-50)] rounded border border-[var(--color-gray-200)]">
                      <div className="flex gap-2 mb-2">
                        <input placeholder="fieldName" value={leadField} onChange={(e) => setLeadField(e.target.value)}
                          className="flex-1 px-3 py-1.5 text-sm border rounded" />
                        <input placeholder="ค่าที่เสนอ" value={leadValue} onChange={(e) => setLeadValue(e.target.value)}
                          className="flex-1 px-3 py-1.5 text-sm border rounded" />
                      </div>
                      <Button size="sm" disabled={!leadField.trim() || !leadValue.trim() || actionLoading === item.commentId}
                        onClick={() => handoffResearchLead(item.commentId)}>ส่งต่อ</Button>
                    </div>
                  )}
                </CardBody>
              </Card>
            ))}
          </div>
          <div className="flex justify-between items-center mt-4">
            <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>ก่อนหน้า</Button>
            <span className="text-sm text-[var(--color-gray-500)]">หน้า {page}</span>
            <Button variant="ghost" size="sm" disabled={items.length < 20} onClick={() => setPage((p) => p + 1)}>ถัดไป</Button>
          </div>
        </>
      )}
    </div>
  );
}
