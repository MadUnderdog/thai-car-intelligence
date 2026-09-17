"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

type SearchResult = {
  id: string;
  nameEn: string;
  nameTh: string;
  slug: string;
  fuelType: string;
  manufacturerName: string;
  manufacturerSlug: string;
  modelName: string;
  modelSlug: string;
};

type SearchStats = {
  totalManufacturers: number;
  evCount: number;
  hevCount: number;
};

const FUEL_TYPES = [
  { value: "", label: "ทุกประเภท" },
  { value: "EV", label: "รถไฟฟ้า EV" },
  { value: "HEV", label: "ไฮบริด HEV" },
  { value: "PHEV", label: "ปลั๊กอิน PHEV" },
  { value: "Petrol", label: "เบนซิน" },
  { value: "Diesel", label: "ดีเซล" },
];

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [fuelType, setFuelType] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [stats, setStats] = useState<SearchStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([]);

  const doSearch = useCallback(async () => {
    setLoading(true);
    setHasSearched(true);
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (fuelType) params.set("fuelType", fuelType);
    if (maxPrice) params.set("maxPrice", maxPrice);
    params.set("limit", "24");

    try {
      const res = await fetch(`/api/search?${params}`);
      const data = await res.json();
      setResults(data.results || []);
      setStats({
        totalManufacturers: data.totalManufacturers || 0,
        evCount: data.evCount || 0,
        hevCount: data.hevCount || 0,
      });
    } catch {
      setResults([]);
    }
    setLoading(false);
  }, [query, fuelType, maxPrice]);

  useEffect(() => {
    const timer = setTimeout(() => doSearch(), 300);
    return () => clearTimeout(timer);
  }, [doSearch]);

  const toggleCompare = (id: string) => {
    setSelectedForCompare((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 4) return prev;
      return [...prev, id];
    });
  };

  return (
    <div className="container-narrow py-8">
      <h1 className="text-3xl font-bold text-[var(--color-gray-900)] mb-6">ค้นหารถ</h1>

      {/* Search input */}
      <div className="flex gap-2 mb-6">
        <div className="flex-1">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="ค้นหาด้วยชื่อรุ่น, ยี่ห้อ, หรือคุณสมบัติ..."
            className="w-full px-4 py-3 bg-white border border-[var(--color-gray-300)] rounded-[var(--radius-xl)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-500)] focus:border-transparent"
          />
        </div>
        <Button onClick={doSearch} isLoading={loading}>
          ค้นหา
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <select
          value={fuelType}
          onChange={(e) => setFuelType(e.target.value)}
          className="px-4 py-2 bg-white border border-[var(--color-gray-300)] rounded-[var(--radius-lg)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-500)]"
        >
          {FUEL_TYPES.map((ft) => (
            <option key={ft.value} value={ft.value}>{ft.label}</option>
          ))}
        </select>
        <input
          type="number"
          inputMode="numeric"
          value={maxPrice}
          onChange={(e) => setMaxPrice(e.target.value)}
          placeholder="ราคาสูงสุด"
          className="px-4 py-2 bg-white border border-[var(--color-gray-300)] rounded-[var(--radius-lg)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-500)] w-36"
        />
      </div>

      {/* Compare bar */}
      {selectedForCompare.length > 0 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-[var(--color-primary-600)] text-white px-6 py-3 rounded-[var(--radius-xl)] shadow-lg flex items-center gap-4 z-[var(--z-sticky)]">
          <span className="text-sm font-medium">เลือกแล้ว {selectedForCompare.length}/4 คัน</span>
          <Link
            href={`/compare?ids=${selectedForCompare.join(",")}`}
            className="px-4 py-1.5 bg-white text-[var(--color-primary-600)] text-sm font-medium rounded-[var(--radius-lg)] hover:bg-[var(--color-primary-50]"
          >
            เปรียบเทียบ
          </Link>
        </div>
      )}

      {/* Results */}
      {loading && <div className="text-center py-12 text-[var(--color-gray-500)]">กำลังค้นหา...</div>}

      {!loading && hasSearched && results.length === 0 && (
        <div className="text-center py-12">
          <div className="text-4xl mb-3">🔍</div>
          <div className="text-[var(--color-gray-600)] text-lg">ไม่พบผลลัพธ์</div>
          <div className="text-[var(--color-gray-400)] mt-2">ลองค้นหาด้วยคำอื่น หรือเปลี่ยนตัวกรอง</div>
        </div>
      )}

      {!loading && results.length > 0 && (
        <>
          <div className="text-sm text-[var(--color-gray-500)] mb-4">พบ {results.length} ผลลัพธ์</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {results.map((r) => {
              const isSelected = selectedForCompare.includes(r.id);
              return (
                <div key={r.id} className={`relative ${isSelected ? "ring-2 ring-[var(--color-primary-500)] rounded-[var(--radius-xl)]" : ""}`}>
                  <Link href={`/cars/${r.manufacturerSlug}/${r.modelSlug}`}>
                    <Card variant="bordered" className="h-full hover:shadow-md transition-shadow">
                      <div className="p-4">
                        <div className="flex items-start justify-between mb-2">
                          <Badge
                            variant={r.fuelType === "EV" ? "success" : r.fuelType === "HEV" ? "warning" : "default"}
                          >
                            {r.fuelType}
                          </Badge>
                        </div>
                        <div className="text-xs text-[var(--color-gray-500)] mb-1">{r.manufacturerName}</div>
                        <h3 className="font-semibold text-[var(--color-gray-900)] mb-3">{r.nameEn}</h3>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.preventDefault();
                            toggleCompare(r.id);
                          }}
                          className="w-full"
                        >
                          {isSelected ? "✓ เลือกแล้ว" : "+ เปรียบเทียบ"}
                        </Button>
                      </div>
                    </Card>
                  </Link>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
