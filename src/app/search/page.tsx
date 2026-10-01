"use client";

import { Suspense } from "react";
import SearchClient from "./SearchClient";

export default function SearchPage() {
  // P116: SearchClient reads useSearchParams() — static prerender requires a
  // Suspense boundary (missing-suspense-with-csr-bailout broke `next build`).
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-slate-50 flex items-center justify-center">
          <div className="text-slate-400 text-sm">กำลังโหลด...</div>
        </div>
      }
    >
      <SearchClient />
    </Suspense>
  );
}
