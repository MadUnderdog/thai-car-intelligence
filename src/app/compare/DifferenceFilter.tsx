"use client";

import { useEffect, useRef, type ReactNode } from "react";

export default function DifferenceFilter({ children }: { children: ReactNode }) {
  const enabled = useRef(false);
  useEffect(() => {
    const rows = document.querySelectorAll<HTMLElement>("#comparison-rows tr");
    rows.forEach((row) => { row.hidden = enabled.current && row.dataset.different !== "true"; });
  }, []);
  function toggle(checked: boolean) {
    enabled.current = checked;
    document.querySelectorAll<HTMLElement>("#comparison-rows tr").forEach((row) => { row.hidden = checked && row.dataset.different !== "true"; });
  }
  return <div><label className="flex cursor-pointer items-center gap-3 text-sm"><input type="checkbox" className="peer sr-only" aria-label="แสดงเฉพาะความแตกต่าง" onChange={(event) => toggle(event.currentTarget.checked)} /><span aria-hidden="true" className="relative h-6 w-11 rounded-full bg-[#c8d3c8] transition peer-checked:bg-[#708d12] after:absolute after:left-1 after:top-1 after:h-4 after:w-4 after:rounded-full after:bg-white after:transition peer-checked:after:translate-x-5" /><span>แสดงเฉพาะความแตกต่าง</span></label>{children}</div>;
}
