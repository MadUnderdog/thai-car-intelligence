import Link from "next/link";

export default function VehicleNotFound() {
  return (
    <main className="min-h-screen bg-[#f6f7f2] px-5 py-16 text-[#14221d] sm:px-8">
      <div className="mx-auto max-w-xl rounded-3xl border border-[#d9dfd8] bg-white p-8 text-center sm:p-12">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-[#708d12]">ไม่พบข้อมูลรถ</p>
        <h1 className="mt-4 text-3xl font-semibold tracking-[-0.04em]">ไม่พบรุ่นรถที่ต้องการ</h1>
        <p className="mt-4 text-sm leading-6 text-[#647269]">ลิงก์นี้อาจไม่ถูกต้อง หรือรุ่นนี้ยังไม่มีข้อมูลที่เผยแพร่ในฐานข้อมูล</p>
        <Link href="/search" className="mt-8 inline-flex min-h-12 items-center rounded-full bg-[#14221d] px-6 font-semibold text-white hover:bg-[#30483d]">กลับไปค้นหา</Link>
      </div>
    </main>
  );
}
