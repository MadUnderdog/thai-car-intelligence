import Link from "next/link";

export default function Footer() {
  return (
    <footer className="bg-[var(--color-gray-900)] text-[var(--color-gray-400)] mt-auto">
      <div className="container-wide py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="md:col-span-2">
            <div className="flex items-center gap-2.5 font-bold text-lg text-white mb-3">
              <span className="w-8 h-8 bg-[var(--color-primary-600)] rounded-[var(--radius-lg)] flex items-center justify-center text-sm">
                🚗
              </span>
              Car Intelligence
            </div>
            <p className="text-sm leading-relaxed max-w-md">
              แพลตฟอร์มข้อมูลรถยนต์ตลาดไทย ที่รวบรวมข้อมูลจากแหล่งทางการและแหล่งอ้างอิทธิพล
              พร้อมระบบประเมินความน่าเชื่อถือของข้อมูล (Source-backed provenance)
            </p>
          </div>

          {/* Quick links */}
          <div>
            <h3 className="text-sm font-semibold text-white mb-3">นำทาง</h3>
            <div className="flex flex-col gap-2 text-sm">
              <Link href="/cars" className="hover:text-white transition-colors">รถยนต์ทั้งหมด</Link>
              <Link href="/search" className="hover:text-white transition-colors">ค้นหา</Link>
              <Link href="/compare" className="hover:text-white transition-colors">เปรียบเทียบ</Link>
              <Link href="/ai-ask" className="hover:text-white transition-colors">ถาม AI</Link>
            </div>
          </div>

          {/* About */}
          <div>
            <h3 className="text-sm font-semibold text-white mb-3">เกี่ยวกับ</h3>
            <p className="text-sm">
              ข้อมูลเป็นข้อมูลอ้างอิง ไม่ใช่ข้อมูลทางการจากผู้ผลิต
              กรุณาตรวจสอบแหล่งข้อมูลก่อนตัดสินใจ
            </p>
          </div>
        </div>

        <div className="mt-8 pt-8 border-t border-[var(--color-gray-800)] text-xs text-center">
          © 2026 Car Intelligence Thailand
        </div>
      </div>
    </footer>
  );
}
