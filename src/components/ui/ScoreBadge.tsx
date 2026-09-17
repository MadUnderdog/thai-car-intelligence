type Props = {
  value: number; // 0-100
  label?: string;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
};

export default function ScoreBadge({ value, label, size = "md", showLabel = true }: Props) {
  const clamped = Math.max(0, Math.min(100, value));
  const color = clamped >= 80 ? "text-emerald-600" : clamped >= 50 ? "text-amber-600" : "text-red-500";
  const bgColor = clamped >= 80 ? "bg-emerald-500" : clamped >= 50 ? "bg-amber-500" : "bg-red-400";
  const sizeClass = size === "sm" ? "w-10 h-10 text-xs" : size === "lg" ? "w-16 h-16 text-lg" : "w-12 h-12 text-sm";

  return (
    <div className="inline-flex flex-col items-center gap-1">
      <div className={`${sizeClass} rounded-full border-2 border-gray-200 flex items-center justify-center relative overflow-hidden`}>
        <div className={`absolute bottom-0 left-0 right-0 ${bgColor} opacity-20`} style={{ height: `${clamped}%` }} />
        <span className={`relative font-bold ${color}`}>{clamped}</span>
      </div>
      {showLabel && label && <span className="text-[10px] text-gray-500 font-medium">{label}</span>}
    </div>
  );
}
