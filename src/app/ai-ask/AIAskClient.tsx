"use client";

import { useState } from "react";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

type TrustState = {
  confidence: "VERIFIED" | "QUALIFIED" | "INSUFFICIENT" | "CLARIFICATION_NEEDED" | "RESEARCH_UNVERIFIED";
  retrievalMode: string;
  verifiedEvidenceCount: number;
  qualifiedEvidenceCount: number;
  hasResearchObservations: boolean;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Array<{ label: string; url?: string; content?: string }>;
  trust?: TrustState;
};

const TRUST_CONFIG: Record<string, { label: string; variant: "success" | "warning" | "default" | "danger"; icon: string }> = {
  VERIFIED: { label: "ข้อมูลยืนยันแล้ว", variant: "success", icon: "✔️" },
  QUALIFIED: { label: "ข้อมูลบางส่วน", variant: "warning", icon: "⚠️" },
  INSUFFICIENT: { label: "ยังไม่มีข้อมูลยืนยัน", variant: "default", icon: "⛔" },
  CLARIFICATION_NEEDED: { label: "กรุณาระบุให้ชัดเจน", variant: "default", icon: "❓" },
  RESEARCH_UNVERIFIED: { label: "ข้อมูลจากงานวิจัย", variant: "default", icon: "📋" },
};

const EXAMPLE_QUESTIONS = [
  "MG S5 ราคาเท่าไหร่?",
  "Honda City Hatchback ราคาเท่าไหร่?",
  "Honda SUV ราคาเท่าไหร่?",
  "Tesla Model Y ราคาเท่าไหร่?",
];

export default function AIAskClient() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg: Message = { id: `msg-${Date.now()}`, role: "user", content: input.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/ai/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userMsg.content }),
      });
      const data = await res.json();

      if (data.status === "unavailable") {
        setError("ระบบ AI ไม่พร้อมใช้งาน");
        setMessages((prev) => [...prev, { id: `msg-${Date.now()}-err`, role: "assistant", content: "ขออภัย ระบบ AI ไม่พร้อมใช้งานในขณะนี้ กรุณาลองใหม่ภายหลัง" }]);
      } else {
        setMessages((prev) => [...prev, {
          id: `msg-${Date.now()}-ai`,
          role: "assistant",
          content: data.answer || "ไม่พบคำตอบ",
          citations: data.citations || [],
          trust: data.trust,
        }]);
      }
    } catch {
      setError("ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้");
    }
    setLoading(false);
  };

  return (
    <div className="container-narrow py-8">
      <h1 className="text-3xl font-bold text-[var(--color-gray-900)] mb-2">ถาม AI เกี่ยวกับรถยนต์</h1>
      <p className="text-[var(--color-gray-500)] mb-6">ถามคำถามเกี่ยวกับรถยนต์ตลาดไทย ระบบจะค้นหาข้อมูลจากฐานข้อมูลที่ผ่านการตรวจสอบ</p>

      {/* Chat area */}
      <Card className="mb-4 min-h-[400px] max-h-[600px] overflow-y-auto">
        <CardBody>
          {messages.length === 0 && (
            <div className="text-center py-12">
              <div className="text-5xl mb-4">💬</div>
              <p className="text-[var(--color-gray-500)] mb-4">ยังไม่มีบทสนทนา</p>
              <p className="text-sm text-[var(--color-gray-400)] mb-3">ลองถามตัวอย่าง:</p>
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button key={q} onClick={() => setInput(q)}
                    className="px-3 py-1.5 text-sm bg-[var(--color-gray-100)] text-[var(--color-gray-700)] rounded-[var(--radius-lg)] hover:bg-[var(--color-gray-200)] transition-colors">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-4">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-[var(--radius-xl)] px-4 py-3 ${msg.role === "user" ? "bg-[var(--color-primary-600)] text-white" : "bg-[var(--color-gray-100)] text-[var(--color-gray-800)]"}`}>
                  <div className="whitespace-pre-wrap text-sm">{msg.content}</div>

                  {/* Trust state badge */}
                  {msg.trust && (
                    <div className="mt-2 flex items-center gap-2 flex-wrap">
                      <Badge variant={TRUST_CONFIG[msg.trust.confidence]?.variant || "default"}>
                        {TRUST_CONFIG[msg.trust.confidence]?.icon} {TRUST_CONFIG[msg.trust.confidence]?.label}
                      </Badge>
                      {msg.trust.verifiedEvidenceCount > 0 && (
                        <span className="text-xs text-[var(--color-gray-500)]">
                          หลักฐานยืนยัน {msg.trust.verifiedEvidenceCount} รายการ
                        </span>
                      )}
                      {msg.trust.qualifiedEvidenceCount > 0 && (
                        <span className="text-xs text-[var(--color-gray-500)]">
                          หลักฐานบางส่วน {msg.trust.qualifiedEvidenceCount} รายการ
                        </span>
                      )}
                    </div>
                  )}

                  {/* Sources */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-[var(--color-gray-300)] text-xs text-[var(--color-gray-600)]">
                      <div className="font-medium mb-1">แหล่งข้อมูล:</div>
                      {msg.citations.slice(0, 3).map((c, i) => (
                        <div key={i} className="truncate">
                          {c.url ? (
                            <a href={c.url} target="_blank" rel="noopener" className="text-[var(--color-primary-600)] hover:underline">{c.label}</a>
                          ) : c.label}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-[var(--color-gray-100)] rounded-[var(--radius-xl)] px-4 py-3 text-sm text-[var(--color-gray-500)]">
                  กำลังค้นหาข้อมูล...
                </div>
              </div>
            )}
          </div>
        </CardBody>
      </Card>

      {/* Input area */}
      <div className="flex gap-2">
        <input type="text" value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="พิมพ์คำถามของคุณ..."
          className="flex-1 px-4 py-3 bg-white border border-[var(--color-gray-300)] rounded-[var(--radius-xl)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-500)] focus:border-transparent"
          disabled={loading} />
        <Button onClick={sendMessage} disabled={loading || !input.trim()} isLoading={loading}>ส่ง</Button>
      </div>

      {error && (
        <div className="mt-3 p-3 bg-[var(--color-danger-50)] border border-[var(--color-danger-500)]/20 text-[var(--color-danger-600)] rounded-[var(--radius-lg)] text-sm">{error}</div>
      )}
    </div>
  );
}
