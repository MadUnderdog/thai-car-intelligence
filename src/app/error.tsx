"use client";

import { useEffect } from "react";

export default function Error({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error("Route error:", error.message);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-5 py-16">
      <div className="mx-auto max-w-xl text-center">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-[var(--color-danger-600)]">
          เกิดข้อผิดพลาด
        </p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-[var(--color-gray-900)]">
          ไม่สามารถโหลดหน้านี้ได้
        </h1>
        <p className="mt-4 text-sm leading-6 text-[var(--color-gray-500)]">
          ระบบขัดข้องชั่วคราว กรุณาลองใหม่อีกครั้ง
        </p>
        <button
          onClick={() => retry()}
          className="mt-8 inline-flex items-center rounded-full bg-[var(--color-primary-600)] px-6 py-3 text-sm font-semibold text-white hover:bg-[var(--color-primary-700)] transition-colors"
        >
          ลองใหม่
        </button>
      </div>
    </div>
  );
}
