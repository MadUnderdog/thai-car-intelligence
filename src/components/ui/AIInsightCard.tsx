import SourceBadge from "./SourceBadge";

type Source = {
  domain: string;
  tier: string;
  url?: string;
};

type Props = {
  question: string;
  answer: string;
  sources?: Source[];
  confidence?: "high" | "medium" | "low";
  loading?: boolean;
};

export default function AIInsightCard({ question, answer, sources, confidence, loading }: Props) {
  const confidenceConfig = {
    high: { bg: "bg-emerald-50", border: "border-emerald-200", label: "ความมั่นใจสูง", icon: "✓" },
    medium: { bg: "bg-amber-50", border: "border-amber-200", label: "ความมั่นใจปานกลาง", icon: "~" },
    low: { bg: "bg-red-50", border: "border-red-200", label: "ความมั่นใจต่ำ", icon: "!" },
  };
  const conf = confidence ? confidenceConfig[confidence] : null;

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      {/* Question */}
      <div className="px-5 py-3 bg-gray-50 border-b">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span className="text-lg">🤖</span>
          <span className="font-medium text-gray-700">{question}</span>
        </div>
      </div>

      {/* Answer */}
      <div className="px-5 py-4">
        {loading ? (
          <div className="flex items-center gap-2 text-gray-400">
            <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">กำลังค้นหาข้อมูล...</span>
          </div>
        ) : (
          <div className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{answer}</div>
        )}
      </div>

      {/* Footer */}
      {(conf || (sources && sources.length > 0)) && (
        <div className="px-5 py-3 bg-gray-50 border-t flex flex-wrap items-center gap-2">
          {conf && (
            <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${conf.bg} ${conf.border} border`}>
              <span>{conf.icon}</span> {conf.label}
            </span>
          )}
          {sources && sources.map((s, i) => (
            <SourceBadge key={i} tier={s.tier} sourceUrl={s.url} size="sm" />
          ))}
        </div>
      )}
    </div>
  );
}
