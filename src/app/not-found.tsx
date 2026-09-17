import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center px-5 py-16">
      <div className="mx-auto max-w-xl text-center">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-[var(--color-primary-600)]">
          404
        </p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-[var(--color-gray-900)]">
          ไม่พบหน้าที่ต้องการ
        </h1>
        <p className="mt-4 text-sm leading-6 text-[var(--color-gray-500)]">
          หน้าที่คุณค้นหาอาจถูกลย้าย ไม่มีอยู่แล้ว หรือลิงก์ไม่ถูกต้อง
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            href="/"
            className="inline-flex items-center rounded-full bg-[var(--color-primary-600)] px-6 py-3 text-sm font-semibold text-white hover:bg-[var(--color-primary-700)] transition-colors"
          >
            กลับหน้าแรก
          </Link>
          <Link
            href="/search"
            className="inline-flex items-center rounded-full border border-[var(--color-gray-300)] bg-white px-6 py-3 text-sm font-semibold text-[var(--color-gray-700)] hover:bg-[var(--color-gray-50)] transition-colors"
          >
            ค้นหารถ
          </Link>
        </div>
      </div>
    </div>
  );
}
