"use client";

import { useState, useEffect } from "react";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

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

export default function AdminModerationPage() {
  const [items, setItems] = useState<ModerationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  async function loadQueue() {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch("/api/admin/community/moderation", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { setError("ไม่ได้รับอนุญาต"); setLoading(false); return; }
      const data = await res.json();
      setItems(data.comments || []);
    } catch { setError("เชื่อมต่อเซิร์ฟเวอร์ไม่ได้"); }
    setLoading(false);
  }

  useEffect(() => { if (token) loadQueue(); }, [token]);

  async function act(commentId: string, action: "HIDE" | "DELETE" | "RESTORE") {
    setActionLoading(commentId);
    try {
      await fetch("/api/admin/community/moderation", {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ commentId, action }),
      });
      setItems((prev) => prev.filter((i) => i.commentId !== commentId));
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
      <h1 className="text-2xl font-bold mb-6">จัดการความคิดเห็น (Moderation Queue)</h1>
      {loading ? <div className="text-center py-8">กำลังโหลด...</div> : error ? <div className="text-red-500">{error}</div> : items.length === 0 ? (
        <Card><CardBody className="text-center py-8 text-[var(--color-gray-500)]">ไม่มีความคิดเห็นที่ต้องจัดการ</CardBody></Card>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <Card key={item.commentId}>
              <CardBody>
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <span className="font-medium">{item.authorName}</span>
                    <span className="text-xs text-[var(--color-gray-400)] ml-2">{STATUS_LABELS[item.status] || item.status}</span>
                    <span className="text-xs text-[var(--color-gray-400)] ml-2"> flagged={item.flaggedCount}</span>
                  </div>
                  <span className="text-xs text-[var(--color-gray-400)]">{new Date(item.createdAt).toLocaleString("th-TH")}</span>
                </div>
                <p className="text-sm mb-3">{item.body}</p>
                <div className="text-xs text-[var(--color-gray-500)] mb-3">
                  รายงาน: {Object.entries(item.briefByReason).map(([r, c]) => `${r}(${c})`).join(", ")}
                </div>
                <div className="flex gap-2">
                  <Button variant="secondary" disabled={actionLoading === item.commentId} onClick={() => act(item.commentId, "HIDE")}>ซ่อน</Button>
                  <Button variant="secondary" disabled={actionLoading === item.commentId} onClick={() => act(item.commentId, "DELETE")}>ลบ</Button>
                  {item.status !== "VISIBLE" && (
                    <Button variant="ghost" disabled={actionLoading === item.commentId} onClick={() => act(item.commentId, "RESTORE")}>กู้คืน</Button>
                  )}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
