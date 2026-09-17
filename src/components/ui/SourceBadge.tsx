type Props = {
  tier: string | null | undefined;
  sourceUrl?: string | null;
  size?: "sm" | "md";
};

const TIER_CONFIG: Record<string, { bg: string; text: string; icon: string; label: string }> = {
  official_verified: { bg: "bg-emerald-50", text: "text-emerald-700", icon: "✓", label: "ทางการ" },
  secondary_verified: { bg: "bg-sky-50", text: "text-sky-700", icon: "✓", label: "ยืนยัน" },
  reference: { bg: "bg-amber-50", text: "text-amber-700", icon: "~", label: "อ้างอิง" },
  inferred: { bg: "bg-orange-50", text: "text-orange-700", icon: "⚠", label: "อนุมาน" },
};

const DEFAULT = { bg: "bg-gray-100", text: "text-gray-500", icon: "—", label: "ไม่มีข้อมูล" };

export default function SourceBadge({ tier, sourceUrl, size = "sm" }: Props) {
  const config = tier ? TIER_CONFIG[tier] || DEFAULT : DEFAULT;
  const sizeClass = size === "sm" ? "text-[10px] px-2 py-0.5" : "text-xs px-2.5 py-1";

  const badge = (
    <span className={`inline-flex items-center gap-1 rounded-full font-medium ${config.bg} ${config.text} ${sizeClass}`}>
      <span>{config.icon}</span>
      <span>{config.label}</span>
    </span>
  );

  if (sourceUrl) {
    return <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="hover:opacity-80 transition" title={sourceUrl}>{badge}</a>;
  }
  return badge;
}
