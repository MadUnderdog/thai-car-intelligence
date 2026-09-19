"use client";

import { useState } from "react";
import {
  Card,
  CardHeader,
  CardBody,
  CardFooter,
} from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

/* ------------------------------------------------------------------ */
/*  Section wrapper                                                    */
/* ------------------------------------------------------------------ */
function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold text-[var(--color-gray-900)]">
          {title}
        </h2>
        {description && (
          <p className="mt-1 text-sm text-[var(--color-gray-500)]">
            {description}
          </p>
        )}
      </div>
      <div className="space-y-6">{children}</div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  1. Header                                                          */
/* ------------------------------------------------------------------ */
function Header() {
  return (
    <header className="border-b border-[var(--color-gray-200)] bg-white py-4">
      <div className="container-narrow flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-[var(--color-primary-700)]">
            🚗 Thai Car Intelligence
          </span>
          <Badge variant="info"> showcse </Badge>
        </div>
        <nav className="flex items-center gap-4 text-sm text-[var(--color-gray-600)]">
          <a href="#" className="hover:text-[var(--color-primary-600)]">
            หน้าแรก
          </a>
          <a href="#" className="hover:text-[var(--color-primary-600)]">
            รถยนต์
          </a>
          <a href="#" className="hover:text-[var(--color-primary-600)]">
            เปรียบเทียบ
          </a>
        </nav>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/*  2. Breadcrumb                                                      */
/* ------------------------------------------------------------------ */
function Breadcrumb() {
  const items = [
    { label: "หน้าแรก", href: "/" },
    { label: "รถยนต์", href: "/cars" },
    { label: "Toyota Camry 2024", href: "/cars/toyota-camry-2024" },
  ];
  return (
    <nav aria-label="เส้นทางนำทาง" className="flex items-center gap-1 text-sm">
      {items.map((item, i) => (
        <span key={item.href} className="flex items-center gap-1">
          {i > 0 && (
            <span className="text-[var(--color-gray-400)]">/</span>
          )}
          {i < items.length - 1 ? (
            <a
              href={item.href}
              className="text-[var(--color-primary-600)] hover:underline"
            >
              {item.label}
            </a>
          ) : (
            <span className="text-[var(--color-gray-700)] font-medium">
              {item.label}
            </span>
          )}
        </span>
      ))}
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/*  3. Model Hero                                                      */
/* ------------------------------------------------------------------ */
function ModelHero() {
  return (
    <div className="rounded-[var(--radius-xl)] bg-gradient-to-br from-[var(--color-primary-800)] to-[var(--color-primary-900)] p-8 text-white">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge variant="success">ใหม่</Badge>
            <Badge variant="info">ไฟฟ้า</Badge>
          </div>
          <h1 className="text-3xl font-bold">Toyota bZ4X 2024</h1>
          <p className="text-[var(--color-primary-200)]">
            รถยนต์ไฟฟ้า SUV ขนาดกลาง — ระยะทางวิ่งได้สูงสุด 516 กม.
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm text-[var(--color-primary-300)]">
            ราคาเริ่มต้น
          </p>
          <p className="text-3xl font-bold">฿1,999,000</p>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  4. Price Block                                                     */
/* ------------------------------------------------------------------ */
function PriceBlock() {
  const trims = [
    { name: "EV One", price: 1_999_000 },
    { name: "EV Comfort", price: 2_249_000 },
    { name: "EV Premium", price: 2_499_000 },
  ];
  return (
    <Card variant="bordered">
      <CardHeader>
        <h3 className="font-semibold text-[var(--color-gray-900)]">
          💰 ราคาและรุ่นย่อย
        </h3>
      </CardHeader>
      <CardBody>
        <div className="space-y-3">
          {trims.map((t) => (
            <div
              key={t.name}
              className="flex items-center justify-between rounded-[var(--radius-lg)] border border-[var(--color-gray-200)] px-4 py-3"
            >
              <span className="text-sm font-medium">{t.name}</span>
              <span className="text-lg font-bold text-[var(--color-primary-700)]">
                ฿{t.price.toLocaleString("th-TH")}
              </span>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  5. Trust / Evidence Indicator                                       */
/* ------------------------------------------------------------------ */
function TrustIndicator() {
  return (
    <Card variant="default">
      <CardBody>
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-success-50)]">
            <span className="text-xl">✅</span>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold">ข้อมูลยืนยันแล้ว</span>
              <Badge variant="success" size="sm">
                ผ่านการตรวจสอบ
              </Badge>
            </div>
            <p className="text-xs text-[var(--color-gray-500)]">
              ราคาและข้อมูลจำเพาะได้รับการยืนยันจากแหล่งข้อมูลอย่างเป็นทางการ 3
              แหล่ง ณ วันที่ 15 ก.ย. 2024
            </p>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  6. Spec Table                                                      */
/* ------------------------------------------------------------------ */
function SpecTable() {
  const specs = [
    { label: "มิติรถ (กว้าง x ยาว x สูง)", value: "1,860 × 4,690 × 1,650 มม." },
    { label: "ระยะฐานล้อ", value: "2,850 มม." },
    { label: "น้ำหนัก", value: "1,910 กก." },
    { label: "ความจุแบตเตอรี่", value: "71.4 kWh" },
    { label: "กำลังมอเตอร์", value: "150 kW (204 แรงม้า)" },
    { label: "ระบบขับเคลื่อน", value: "AWD สองมอเตอร์" },
    { label: "ระยะวิ่ง (WLTP)", value: "411 กม." },
    { label: "เวลาชาร์จ 0→80%", value: "~30 นาที (DC Fast)" },
  ];
  return (
    <Card variant="bordered">
      <CardHeader>
        <h3 className="font-semibold text-[var(--color-gray-900)]">
          📋 ข้อมูลจำเพาะ
        </h3>
      </CardHeader>
      <CardBody className="px-0">
        <table className="w-full text-sm">
          <tbody>
            {specs.map((s, i) => (
              <tr
                key={s.label}
                className={
                  i % 2 === 0
                    ? "bg-[var(--color-gray-50)]"
                    : "bg-white"
                }
              >
                <td className="px-6 py-3 text-[var(--color-gray-600)]">
                  {s.label}
                </td>
                <td className="px-6 py-3 font-medium text-right">
                  {s.value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  7. Button Variants                                                 */
/* ------------------------------------------------------------------ */
function ButtonShowcase() {
  const [loading, setLoading] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary">Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="danger">Danger</Button>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" size="sm">
          เล็ก
        </Button>
        <Button variant="primary" size="md">
          ปานกลาง
        </Button>
        <Button variant="primary" size="lg">
          ใหญ่
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="primary"
          isLoading={loading}
          onClick={() => {
            setLoading(true);
            setTimeout(() => setLoading(false), 2000);
          }}
        >
          {loading ? "กำลังโหลด..." : "กดเพื่อทดสอบ loading"}
        </Button>
        <Button variant="primary" disabled>
          ปิดใช้งาน
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  8. Input / Select                                                  */
/* ------------------------------------------------------------------ */
function InputSelectShowcase() {
  const [value, setValue] = useState("");
  return (
    <Card variant="bordered">
      <CardBody>
        <div className="grid gap-4 md:grid-cols-2">
          <Input
            label="ค้นหารถยนต์"
            placeholder="เช่น Toyota Camry"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            hint="พิมพ์ชื่อรุ่นรถเพื่อค้นหา"
          />
          <Input
            label="งบประมาณสูงสุด"
            placeholder="2,000,000"
            error="กรุณาระบุงบประมาณ"
          />
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-[var(--color-gray-700)]">
              ประเภทเชื้อเพลิง
            </label>
            <select className="w-full rounded-[var(--color-gray-200)] border border-[var(--color-gray-300)] bg-white px-3 py-2 text-sm">
              <option>ทั้งหมด</option>
              <option>เบนซิน</option>
              <option>ดีเซล</option>
              <option>ไฟฟ้า (BEV)</option>
              <option>ไฮบริด (HEV/PHEV)</option>
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-[var(--color-gray-700)]">
              ยี่ห้อ
            </label>
            <select className="w-full rounded-[var(--color-gray-200)] border border-[var(--color-gray-300)] bg-white px-3 py-2 text-sm">
              <option>ทั้งหมด</option>
              <option>Toyota</option>
              <option>Honda</option>
              <option>Mazda</option>
              <option>BYD</option>
            </select>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  9. Tabs                                                            */
/* ------------------------------------------------------------------ */
function TabsShowcase() {
  const [active, setActive] = useState("specs");
  const tabs = [
    { id: "specs", label: "ข้อมูลจำเพาะ" },
    { id: "price", label: "ราคา" },
    { id: "reviews", label: "รีวิว" },
    { id: "news", label: "ข่าวสาร" },
  ];
  return (
    <div>
      <div className="flex gap-0 border-b border-[var(--color-gray-200)]">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              active === tab.id
                ? "border-b-2 border-[var(--color-primary-600)] text-[var(--color-primary-700)]"
                : "text-[var(--color-gray-500)] hover:text-[var(--color-gray-700)]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="py-4 text-sm text-[var(--color-gray-600)]">
        เนื้อหาของแท็บ &ldquo;{tabs.find((t) => t.id === active)?.label}&rdquo;
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  10. Empty State                                                    */
/* ------------------------------------------------------------------ */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius-xl)] border-2 border-dashed border-[var(--color-gray-300)] bg-white px-6 py-16 text-center">
      <span className="mb-4 text-4xl">🔍</span>
      <h3 className="text-lg font-semibold text-[var(--color-gray-900)]">
        ไม่พบผลลัพธ์
      </h3>
      <p className="mt-1 max-w-sm text-sm text-[var(--color-gray-500)]">
        ยังไม่มีรถยนต์ที่ตรงกับเงื่อนไขการค้นหาของคุณ
        ลองปรับเปลี่ยนตัวกรองหรือค้นหาใหม่
      </p>
      <Button variant="secondary" className="mt-4">
        ล้างตัวกรอง
      </Button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  11. Loading Skeleton                                               */
/* ------------------------------------------------------------------ */
function SkeletonBlock() {
  return (
    <div className="space-y-3">
      <div className="h-4 w-1/3 animate-pulse rounded bg-[var(--color-gray-200)]" />
      <div className="h-4 w-2/3 animate-pulse rounded bg-[var(--color-gray-200)]" />
      <div className="h-4 w-1/2 animate-pulse rounded bg-[var(--color-gray-200)]" />
      <div className="mt-4 flex gap-4">
        <div className="h-20 w-20 animate-pulse rounded bg-[var(--color-gray-200)]" />
        <div className="flex-1 space-y-2">
          <div className="h-3 w-full animate-pulse rounded bg-[var(--color-gray-100)]" />
          <div className="h-3 w-4/5 animate-pulse rounded bg-[var(--color-gray-100)]" />
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  12. Community Comment                                              */
/* ------------------------------------------------------------------ */
function CommunityComment() {
  const comments = [
    {
      author: "สมชาย รักรถ",
      date: "12 ก.ย. 2024",
      text: "ขับ bZ4X มา 3 เดือน ประหยัดค่าน้ำมันมาก แนะนำเลยครับ!",
      helpful: 24,
    },
    {
      author: "สายไฟ EV",
      date: "8 ก.ย. 2024",
      text: "ชาร์จเร็วจริงตามที่โฆษณาไว้ ใช้ได้จริงในชีวิตประจำวัน",
      helpful: 18,
    },
  ];
  return (
    <div className="space-y-3">
      <h3 className="font-semibold text-[var(--color-gray-900)]">
        💬 ความคิดเห็นจากชุมชน ({comments.length})
      </h3>
      {comments.map((c) => (
        <Card key={c.author} variant="default">
          <CardBody>
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--color-primary-100)] text-xs font-bold text-[var(--color-primary-700)]">
                {c.author.charAt(0)}
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{c.author}</span>
                  <span className="text-xs text-[var(--color-gray-400)]">
                    {c.date}
                  </span>
                </div>
                <p className="text-sm text-[var(--color-gray-700)]">
                  {c.text}
                </p>
                <button className="text-xs text-[var(--color-primary-600)] hover:underline">
                  👍 มีประโยชน์ ({c.helpful})
                </button>
              </div>
            </div>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  13. Research-Only Warning                                          */
/* ------------------------------------------------------------------ */
function ResearchWarning() {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-warning-500)]/40 bg-[var(--color-warning-50)] px-5 py-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-lg">⚠️</span>
        <div className="space-y-1">
          <p className="text-sm font-semibold text-[var(--color-warning-600)]">
            เฉพาะข้อมูลวิจัยเท่านั้น
          </p>
          <p className="text-xs text-[var(--color-warning-600)]">
            ข้อมูลในหน้านี้มีวัตถุประสงค์เพื่อการวิจัยและการศึกษาเท่านั้น
            ไม่ถือเป็นคำแนะนำในการซื้อ ราคาที่แสดงอาจไม่ตรงกับราคาจริง
            กรุณาตรวจสอบกับตัวแทนจำหน่ายก่อนตัดสินใจ
          </p>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  14. Provenance Block                                               */
/* ------------------------------------------------------------------ */
function ProvenanceBlock() {
  const sources = [
    {
      name: "Toyota Thailand Official",
      url: "https://www.toyota.co.th",
      verified: true,
      date: "2024-09-01",
    },
    {
      name: "CAR250",
      url: "https://www.car250.com",
      verified: true,
      date: "2024-09-05",
    },
    {
      name: "EV Society Thailand",
      url: "https://evsoc.or.th",
      verified: false,
      date: "2024-08-20",
    },
  ];
  return (
    <Card variant="bordered">
      <CardHeader>
        <div className="flex items-center gap-2">
          <span>📎</span>
          <h3 className="font-semibold text-[var(--color-gray-900)]">
            แหล่งอ้างอิง (Provenance)
          </h3>
        </div>
      </CardHeader>
      <CardBody className="space-y-2">
        {sources.map((s) => (
          <div
            key={s.name}
            className="flex items-center justify-between rounded-[var(--radius-lg)] bg-[var(--color-gray-50)] px-4 py-2"
          >
            <div className="flex items-center gap-2">
              <a
                href={s.url}
                className="text-sm text-[var(--color-primary-600)] hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                {s.name}
              </a>
              {s.verified ? (
                <Badge variant="success" size="sm">
                  ยืนยัน
                </Badge>
              ) : (
                <Badge variant="warning" size="sm">
                  ยังไม่ยืนยัน
                </Badge>
              )}
            </div>
            <span className="text-xs text-[var(--color-gray-400)]">
              {s.date}
            </span>
          </div>
        ))}
      </CardBody>
      <CardFooter>
        <p className="text-xs text-[var(--color-gray-500)]">
          อัปเดตครั้งสุดท้าย: 15 ก.ย. 2024 — ข้อมูลผ่านการตรวจสอบจากแหล่งที่มา{" "}
          {sources.filter((s) => s.verified).length}/{sources.length} แหล่ง
        </p>
      </CardFooter>
    </Card>
  );
}

/* ================================================================== */
/*  PAGE                                                               */
/* ================================================================== */
export default function ShowcaseClient() {
  return (
    <div className="min-h-screen bg-[var(--color-gray-50)]">
      <Header />

      <main className="container-narrow space-y-12 py-10">
        {/* Breadcrumb */}
        <Breadcrumb />

        <h1 className="text-2xl font-bold text-[var(--color-gray-900)]">
          🎨 ตัวอย่าง UI Primitives
        </h1>

        {/* Model Hero */}
        <Section
          title="1. Model Hero"
          description="ส่วนหัวแบบเต็มหน้าจอสำหรับหน้ารายละเอียดรถ"
        >
          <ModelHero />
        </Section>

        {/* Price Block */}
        <Section
          title="2. Price Block"
          description="ตารางราคาและรุ่นย่อย"
        >
          <PriceBlock />
        </Section>

        {/* Trust / Evidence Indicator */}
        <Section
          title="3. Trust / Evidence Indicator"
          description="ตัวบ่งชี้ความน่าเชื่อถือของข้อมูล"
        >
          <TrustIndicator />
        </Section>

        {/* Spec Table */}
        <Section
          title="4. Spec Table"
          description="ตารางข้อมูลจำเพาะทางเทคนิค"
        >
          <SpecTable />
        </Section>

        {/* Button Variants */}
        <Section
          title="5. Button Variants"
          description="ปุ่มทุก variant, ทุกขนาด, loading state"
        >
          <ButtonShowcase />
        </Section>

        {/* Input / Select */}
        <Section
          title="6. Input / Select"
          description="ช่องป้อนข้อมูลและตัวเลือกแบบฟอร์ม"
        >
          <InputSelectShowcase />
        </Section>

        {/* Tabs */}
        <Section title="7. Tabs" description="แท็บนำทางแบบโต้ตอบ">
          <TabsShowcase />
        </Section>

        {/* Empty State */}
        <Section
          title="8. Empty State"
          description="สถานะเมื่อไม่มีข้อมูล"
        >
          <EmptyState />
        </Section>

        {/* Loading Skeleton */}
        <Section
          title="9. Loading Skeleton"
          description="โครงกระดูกโหลดข้อมูล"
        >
          <SkeletonBlock />
        </Section>

        {/* Community Comment */}
        <Section
          title="10. Community Comment"
          description="ความคิดเห็นจากชุมชนผู้ใช้"
        >
          <CommunityComment />
        </Section>

        {/* Research Warning */}
        <Section
          title="11. Research-Only Warning"
          description="คำเตือนข้อมูลสำหรับการวิจัยเท่านั้น"
        >
          <ResearchWarning />
        </Section>

        {/* Provenance Block */}
        <Section
          title="12. Provenance Block"
          description="แหล่งอ้างอิงและความถูกต้องของข้อมูล"
        >
          <ProvenanceBlock />
        </Section>

        {/* Badges showcase */}
        <Section
          title="13. Badge Variants"
          description="ทุก variant ของ Badge"
        >
          <div className="flex flex-wrap items-center gap-3">
            <Badge>Default</Badge>
            <Badge variant="success">สำเร็จ</Badge>
            <Badge variant="warning">เตือน</Badge>
            <Badge variant="danger">อันตราย</Badge>
            <Badge variant="info">ข้อมูล</Badge>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge size="sm">เล็ก</Badge>
            <Badge size="md">ปานกลาง</Badge>
          </div>
        </Section>
      </main>

      <footer className="border-t border-[var(--color-gray-200)] bg-white py-6 text-center text-xs text-[var(--color-gray-500)]">
        Thai Car Intelligence — Showcase Template &copy; 2024
      </footer>
    </div>
  );
}
