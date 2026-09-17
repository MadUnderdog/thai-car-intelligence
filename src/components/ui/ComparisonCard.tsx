import SourceBadge from "./SourceBadge";

type Field = {
  label: string;
  values: (string | number | null)[];
  sourceTier?: string;
};

type Props = {
  vehicles: { brand: string; model: string; variant?: string; price?: number | null }[];
  fields: Field[];
};

export default function ComparisonCard({ vehicles, fields }: Props) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="grid border-b" style={{ gridTemplateColumns: `180px repeat(${vehicles.length}, 1fr)` }}>
        <div className="p-4 bg-gray-50 font-medium text-sm text-gray-500">สเปก</div>
        {vehicles.map((v, i) => (
          <div key={i} className="p-4 text-center border-l">
            <div className="text-xs text-gray-400 uppercase">{v.brand}</div>
            <div className="font-semibold text-sm">{v.model}</div>
            {v.variant && <div className="text-xs text-gray-500">{v.variant}</div>}
            {v.price && <div className="text-sm font-bold text-blue-700 mt-1">฿{v.price.toLocaleString()}</div>}
          </div>
        ))}
      </div>

      {/* Fields */}
      {fields.map((field, fi) => (
        <div key={fi} className="grid border-b last:border-b-0" style={{ gridTemplateColumns: `180px repeat(${vehicles.length}, 1fr)` }}>
          <div className="p-3 bg-gray-50 text-sm text-gray-600 flex items-center gap-2">
            {field.label}
            {field.sourceTier && <SourceBadge tier={field.sourceTier} size="sm" />}
          </div>
          {field.values.map((val, vi) => (
            <div key={vi} className="p-3 text-center border-l text-sm font-medium">
              {val !== null ? val : <span className="text-gray-300">—</span>}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
