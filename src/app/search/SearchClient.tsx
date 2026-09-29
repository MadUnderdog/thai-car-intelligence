"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { mapSearchResponse, type SearchView } from "../../../lib/ux/search-view";

type FilterState = { fuel: string; priceMin: string; priceMax: string; sort: string };

const FUEL_OPTIONS = [
  { value: "", label: "พลังงานทั้งหมด" },
  { value: "BEV", label: "ไฟฟ้า (BEV)" },
  { value: "HEV", label: "ไฮบริด (HEV)" },
  { value: "PHEV", label: "ปลั๊กอินไฮบริด (PHEV)" },
  { value: "Petrol", label: "น้ำมัน (Petrol)" },
  { value: "Diesel", label: "ดีเซล (Diesel)" },
];

const SORT_OPTIONS = [
  { value: "relevance", label: "ความเกี่ยวข้อง" },
  { value: "price_asc", label: "ราคา: ต่ำ → สูง" },
  { value: "price_desc", label: "ราคา: สูง → ต่ำ" },
];

const EMPTY_FILTERS: FilterState = { fuel: "", priceMin: "", priceMax: "", sort: "relevance" };

function hasAnyFilter(f: FilterState): boolean {
  return Boolean(f.fuel || f.priceMin || f.priceMax || f.sort !== "relevance");
}

function normalizeFilters(partial: Partial<FilterState>): FilterState {
  return {
    fuel: partial.fuel ?? "",
    priceMin: partial.priceMin ?? "",
    priceMax: partial.priceMax ?? "",
    sort: partial.sort ?? "relevance",
  };
}

function filterLabel(f: FilterState): string {
  const parts: string[] = [];
  if (f.fuel) parts.push(FUEL_OPTIONS.find((o) => o.value === f.fuel)?.label ?? f.fuel);
  if (f.priceMin) parts.push(`≥ ฿${Number(f.priceMin).toLocaleString()}`);
  if (f.priceMax) parts.push(`≤ ฿${Number(f.priceMax).toLocaleString()}`);
  if (f.sort !== "relevance") parts.push(SORT_OPTIONS.find((o) => o.value === f.sort)?.label ?? f.sort);
  return parts.join(" · ");
}

export default function SearchClient() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const q = searchParams.get("q") || "";

  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<SearchView>({ state: "loading", rows: [], searchMode: null, evidenceCount: 0, total: 0 });
  const [selected, setSelected] = useState<string[]>([]);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);

  const fetchResults = useCallback(async () => {
    if (!q) {
      setView({ state: "empty", rows: [], searchMode: null, evidenceCount: 0, total: 0 });
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const params = new URLSearchParams({ q, limit: "24" });
      if (filters.fuel) params.set("fuelType", filters.fuel);
      if (filters.priceMin) params.set("minPrice", filters.priceMin);
      if (filters.priceMax) params.set("maxPrice", filters.priceMax);
      if (filters.sort !== "relevance") params.set("sortBy", filters.sort);

      const res = await fetch(`/api/search?${params.toString()}`);
      const data = await res.json().catch(() => null);
      // P116: truthful states — !ok (400/503) is an ERROR, never "no results"
      setView(mapSearchResponse(data, res.ok));
    } catch {
      setView(mapSearchResponse(null, false));
    } finally {
      setLoading(false);
    }
  }, [q, filters.fuel, filters.priceMin, filters.priceMax, filters.sort]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  const clearFilters = useCallback(() => setFilters(EMPTY_FILTERS), []);

  const updateFilter = useCallback((key: keyof FilterState, value: string) => {
    setFilters((prev) => {
      const next = { ...prev, [key]: value };
      const query = new URLSearchParams(searchParams.toString());
      query.set("q", q);
      Object.entries(next).forEach(([k, v]) => {
        if (k === "sort" ? v !== "relevance" : v) query.set(k, v);
        else query.delete(k);
      });
      router.replace(`/search?${query.toString()}`);
      return next;
    });
  }, [q, router, searchParams]);

  const toggleCompare = useCallback((id: string) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((s) => s !== id);
      if (prev.length >= 4) return prev;
      return [...prev, id];
    });
  }, []);

  const goToCompare = useCallback(() => {
    if (selected.length < 2) return;
    router.push(`/compare?ids=${selected.join(",")}`);
  }, [router, selected]);

  return (
    <div className="min-h-screen bg-slate-50 pb-24">
      {/* Search bar */}
      <div className="bg-white border-b sticky top-0 z-40">
        <div className="max-w-md mx-auto px-4 py-3">
          <div className="relative">
            <input
              type="text"
              defaultValue={q}
              placeholder="ค้นหารุ่นรถ..."
              className="w-full pl-10 pr-4 py-2.5 border rounded-xl focus:ring-2 focus:ring-blue-500 text-sm"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  const query = new URLSearchParams(searchParams.toString());
                  query.set("q", (e.target as HTMLInputElement).value);
                  router.push(`/search?${query.toString()}`);
                }
              }}
            />
            <svg className="w-5 h-5 text-slate-400 absolute left-3 top-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>
      </div>

      <div className="max-w-md mx-auto px-4 py-4 space-y-4">
        {/* Filters */}
        <div className="bg-white rounded-xl border p-3 space-y-3">
          <div className="flex items-center justify-between">
            <button onClick={() => setShowFilters(!showFilters)} className="flex items-center gap-1 text-sm font-medium text-slate-700">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
              </svg>
              ตัวกรอง {hasAnyFilter(filters) && <span className="text-blue-600">({filterLabel(filters)})</span>}
            </button>
            {hasAnyFilter(filters) && (
              <button onClick={clearFilters} className="text-xs text-slate-500 hover:text-red-600">
                ล้างตัวกรอง
              </button>
            )}
          </div>
          {showFilters && (
            <div className="space-y-3 pt-2 border-t">
              <div>
                <label className="text-xs text-slate-500">พลังงาน</label>
                <select value={filters.fuel} onChange={(e) => updateFilter("fuel", e.target.value)} className="w-full mt-1 border rounded-lg px-3 py-2 text-sm">
                  {FUEL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-slate-500">ราคาต่ำสุด</label>
                  <input type="number" value={filters.priceMin} onChange={(e) => updateFilter("priceMin", e.target.value)} placeholder="0" className="w-full mt-1 border rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="text-xs text-slate-500">ราคาสูงสุด</label>
                  <input type="number" value={filters.priceMax} onChange={(e) => updateFilter("priceMax", e.target.value)} placeholder="3000000" className="w-full mt-1 border rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-500">เรียงตาม</label>
                <select value={filters.sort} onChange={(e) => updateFilter("sort", e.target.value)} className="w-full mt-1 border rounded-lg px-3 py-2 text-sm">
                  {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Search mode / vector evidence indicator (P115 additive fields) */}
        {!loading && view.state === "ok" && view.searchMode && (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="px-2 py-0.5 bg-slate-100 rounded-full">
              {view.searchMode === "hybrid" ? "ค้นหาแบบผสม (แคตตาล็อก + หลักฐาน)" : "ค้นหาจากแคตตาล็อก"}
            </span>
            {view.evidenceCount > 0 && (
              <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full">หลักฐานเพิ่มเติม {view.evidenceCount} รายการ</span>
            )}
          </div>
        )}

        {/* Results */}
        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-white rounded-xl border p-4 animate-pulse">
                <div className="h-4 bg-slate-200 rounded w-2/3 mb-2" />
                <div className="h-3 bg-slate-200 rounded w-1/3" />
              </div>
            ))}
          </div>
        )}

        {view.state === "error" && (
          <div className="bg-white rounded-xl border border-red-200 p-6 text-center space-y-2">
            <p className="text-sm font-medium text-red-700">ค้นหาไม่สำเร็จ</p>
            <p className="text-xs text-slate-500">ระบบค้นหาขัดข้องชั่วคราว — ไม่ใช่ “ไม่พบรถ”</p>
            <button onClick={fetchResults} className="text-xs px-4 py-2 bg-blue-600 text-white rounded-lg">ลองอีกครั้ง</button>
          </div>
        )}

        {!loading && view.state === "empty" && q && (
          <div className="bg-white rounded-xl border p-8 text-center">
            <p className="text-slate-500 text-sm mb-4">ไม่พบรถที่ตรงกับ &ldquo;{q}&rdquo;</p>
            <p className="text-xs text-slate-400">ลองค้นหาด้วยคำอื่น เช่น &ldquo;City&rdquo; หรือ &ldquo;Atto 3&rdquo;</p>
          </div>
        )}

        {!q && !loading && (
          <div className="bg-white rounded-xl border p-8 text-center">
            <p className="text-slate-500 text-sm">พิมพ์ชื่อรุ่นรถเพื่อค้นหา</p>
            <p className="text-xs text-slate-400 mt-2">ตัวอย่าง: Honda City, MG4, Atto 3, Yaris Cross</p>
          </div>
        )}

        {view.state === "ok" && (
          <div className="space-y-3">
            {view.rows.map((r) => (
              <div key={r.variantId} className="bg-white rounded-xl border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <a href={r.link} className="font-medium text-slate-900 hover:text-blue-600 block truncate">
                      {r.nameEn} {r.nameTh && r.nameTh !== r.nameEn && <span className="text-slate-500 font-normal">{r.nameTh}</span>}
                    </a>
                    <p className="text-sm text-slate-500 truncate">{r.manufacturerName} · {r.modelName}</p>
                    {r.priceAmount !== null && (
                      <div className="mt-1 flex items-center gap-2">
                        <span className="font-semibold text-slate-900">฿{r.priceAmount.toLocaleString()}</span>
                        <span className="text-[11px] px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded">ราคาปัจจุบัน</span>
                        {r.priceSourceUrl && (
                          <a href={r.priceSourceUrl} target="_blank" rel="noopener noreferrer" className="text-[11px] text-slate-500 hover:text-blue-600">
                            แหล่งข้อมูล{r.priceSourceName ? `: ${r.priceSourceName}` : ""}
                          </a>
                        )}
                      </div>
                    )}
                    {r.priceAmount === null && <p className="text-xs text-slate-400 mt-1">ยังไม่มีข้อมูลราคา</p>}
                  </div>
                  <button
                    onClick={() => toggleCompare(r.variantId)}
                    className={`shrink-0 px-3 py-2 rounded-lg text-sm border transition ${
                      selected.includes(r.variantId)
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-white text-slate-700 border-slate-300 hover:border-blue-400"
                    }`}
                    aria-pressed={selected.includes(r.variantId)}
                  >
                    {selected.includes(r.variantId) ? "✓" : "+ เทียบ"}
                  </button>
                </div>
              </div>
            ))}
            <p className="text-xs text-slate-400 text-center pb-4">พบ {view.rows.length} รุ่น · ราคาปัจจุบันที่ยืนยันแล้วเท่านั้น</p>
          </div>
        )}
      </div>

      {/* Floating compare bar */}
      {selected.length >= 2 && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t p-4 z-40">
          <div className="max-w-md mx-auto flex items-center justify-between">
            <span className="text-sm text-slate-600">เลือกแล้ว {selected.length} / 4 รุ่น</span>
            <button onClick={goToCompare} className="bg-blue-600 text-white px-6 py-2.5 rounded-xl font-medium hover:bg-blue-700 transition">
              เปรียบเทียบ →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
