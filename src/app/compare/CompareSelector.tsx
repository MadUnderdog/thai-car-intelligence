"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { CatalogPage } from "../../../lib/catalog/types";
import { mapCatalogToCompareOptions, type CompareOption } from "../../../lib/compare/selector";

const MAX_SELECTIONS = 4;

export default function CompareSelector() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryIds = useMemo(() => (searchParams.get("ids") ?? "").split(",").map((id) => id.trim()).filter(Boolean).slice(0, MAX_SELECTIONS), [searchParams]);
  const [options, setOptions] = useState<CompareOption[]>([]);
  const selected = queryIds;
  const [state, setState] = useState<"loading" | "ready" | "empty" | "error">("loading");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/cars?limit=100", { signal: controller.signal })
      .then(async (response) => {
        const data = (await response.json()) as CatalogPage & { error?: string };
        if (!response.ok) throw new Error(data.error ?? "catalog_unavailable");
        return data;
      })
      .then((data) => {
        const mapped = mapCatalogToCompareOptions(data);
        setOptions(mapped);
        setState(mapped.length ? "ready" : "empty");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState("error");
      });
    return () => controller.abort();
  }, []);

  function updateSelection(id: string) {
    const next = selected.includes(id) ? selected.filter((item) => item !== id) : selected.length < MAX_SELECTIONS ? [...selected, id] : selected;
    const params = new URLSearchParams(searchParams.toString());
    if (next.length) params.set("ids", next.join(","));
    else params.delete("ids");
    router.push(`${pathname}${params.toString() ? `?${params}` : ""}`, { scroll: false });
  }

  return (
    <section className="rounded-3xl border border-[#d9dfd8] bg-white p-5 sm:p-7" aria-labelledby="compare-selector-title">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h2 id="compare-selector-title" className="text-lg font-bold">เลือกรุ่นที่ต้องการเปรียบเทียบ</h2>
          <p className="mt-1 text-sm text-[#647269]">เลือก 2–4 รุ่นจากข้อมูลที่มีราคาและแหล่งข้อมูลทางการที่ตรวจสอบแล้ว</p>
        </div>
        <p className="text-sm font-semibold text-[#52625a]" aria-live="polite">เลือกแล้ว {selected.length}/{MAX_SELECTIONS}</p>
      </div>
      {state === "loading" && <p className="mt-6 rounded-2xl bg-[#f6f7f2] p-4 text-sm text-[#647269]" role="status">กำลังโหลดรายการรุ่นที่ตรวจสอบแล้ว…</p>}
      {state === "error" && <div className="mt-6 rounded-2xl border border-[#e8c8c8] bg-[#fff8f8] p-4 text-sm text-[#8d3f3f]" role="alert">ไม่สามารถโหลดรายการรถได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง</div>}
      {state === "empty" && <p className="mt-6 rounded-2xl bg-[#f6f7f2] p-4 text-sm text-[#647269]">ยังไม่มีรุ่นรถที่ผ่านการตรวจสอบในฐานข้อมูล</p>}
      {state === "ready" && <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {options.map((option) => {
          const checked = selected.includes(option.id);
          const disabled = !checked && selected.length >= MAX_SELECTIONS;
          return <label key={option.id} className={`flex cursor-pointer items-start gap-3 rounded-2xl border p-4 transition ${checked ? "border-[#9abf18] bg-[#f7fbe8]" : "border-[#e5eae3] hover:border-[#b9c9b7]"} ${disabled ? "cursor-not-allowed opacity-50" : ""}`}>
            <input type="checkbox" checked={checked} disabled={disabled} onChange={() => updateSelection(option.id)} className="mt-1 h-4 w-4 accent-[#708d12]" aria-label={`เลือก ${option.label}`} />
            <span className="min-w-0"><span className="block font-semibold">{option.label}</span><span className="mt-1 block text-xs text-[#718078]">{option.detail}</span><span className="mt-2 block text-xs text-[#52625a]">ราคา: {option.price === null ? "ไม่มีข้อมูล" : `${new Intl.NumberFormat("th-TH").format(option.price)} บาท`}</span></span>
          </label>;
        })}
      </div>}
      {selected.length === 1 && <p className="mt-4 text-sm text-[#8d6b1e]" role="status">เลือกรุ่นเพิ่มอีกอย่างน้อย 1 รุ่นเพื่อเริ่มเปรียบเทียบ</p>}
    </section>
  );
}
