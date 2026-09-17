"use client";

import { useState } from "react";

type Props = {
  id: string;
  brand: string;
  model: string;
  variant?: string;
  price: number | null;
  fuelType: string | null;
  image?: string | null;
  powerKw?: number | null;
  torqueNm?: number | null;
  sourceTier?: string;
  selected?: boolean;
  onCompare?: (id: string) => void;
  href?: string;
};

export default function VehicleCard(p: Props) {
  const [imgError, setImgError] = useState(false);
  const tierColor = p.sourceTier === "official_verified" ? "bg-emerald-50 text-emerald-700"
    : p.sourceTier === "secondary_verified" ? "bg-sky-50 text-sky-700"
    : p.sourceTier === "reference" ? "bg-amber-50 text-amber-700"
    : "bg-gray-100 text-gray-500";
  const tierLabel = p.sourceTier === "official_verified" ? "ทางการ"
    : p.sourceTier === "secondary_verified" ? "ยืนยัน"
    : p.sourceTier === "reference" ? "อ้างอิง"
    : "—";

  const Card = p.href ? "a" : "div";
  const cardProps = p.href ? { href: p.href } : {};

  return (
    <Card {...cardProps} className="group bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-md hover:border-blue-200 transition-all duration-200 overflow-hidden flex flex-col">
      {/* Image */}
      <div className="relative h-44 bg-gradient-to-br from-gray-50 to-gray-100 overflow-hidden">
        {p.image && !imgError ? (
          <img src={p.image} alt={`${p.brand} ${p.model}`} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" onError={() => setImgError(true)} />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-4xl text-gray-300">🚗</div>
        )}
        {/* Fuel badge */}
        {p.fuelType && (
          <span className={`absolute top-3 left-3 px-2.5 py-1 rounded-full text-xs font-semibold ${
            p.fuelType === "EV" ? "bg-blue-600 text-white" :
            p.fuelType === "HEV" ? "bg-emerald-600 text-white" :
            p.fuelType === "PHEV" ? "bg-purple-600 text-white" :
            "bg-gray-600 text-white"
          }`}>
            {p.fuelType === "EV" ? "⚡ EV" : p.fuelType === "HEV" ? "🔋 HEV" : p.fuelType === "PHEV" ? "🔌 PHEV" : p.fuelType}
          </span>
        )}
        {/* Compare checkbox */}
        {p.onCompare && (
          <button onClick={(e) => { e.preventDefault(); e.stopPropagation(); p.onCompare!(p.id); }}
            className={`absolute top-3 right-3 w-8 h-8 rounded-full border-2 flex items-center justify-center text-sm font-bold transition-all ${
              p.selected ? "bg-blue-600 border-blue-600 text-white shadow-md" : "bg-white/90 border-gray-200 text-gray-400 hover:border-blue-400 hover:text-blue-500"
            }`}>
            {p.selected ? "✓" : "+"}
          </button>
        )}
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col">
        <div className="text-xs text-gray-400 uppercase tracking-wide font-medium">{p.brand}</div>
        <h3 className="font-semibold text-gray-900 mt-0.5 leading-tight">{p.model}</h3>
        {p.variant && <div className="text-sm text-gray-500 mt-0.5">{p.variant}</div>}

        {/* Specs row */}
        {(p.powerKw || p.torqueNm) && (
          <div className="flex gap-3 mt-2 text-xs text-gray-500">
            {p.powerKw && <span>{Math.round(p.powerKw)} kW</span>}
            {p.torqueNm && <span>{Math.round(p.torqueNm)} Nm</span>}
          </div>
        )}

        <div className="mt-auto pt-3 flex items-end justify-between">
          <div>
            {p.price ? (
              <div className="text-lg font-bold text-blue-700">฿{p.price.toLocaleString()}</div>
            ) : (
              <div className="text-sm text-gray-400">ไม่มีข้อมูลราคา</div>
            )}
          </div>
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${tierColor}`}>{tierLabel}</span>
        </div>
      </div>
    </Card>
  );
}
