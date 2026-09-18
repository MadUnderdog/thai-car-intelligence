"use client";

import Link from "next/link";
import { Card, CardBody } from "@/components/ui/Card";
import { CommunitySection } from "@/components/community/CommunitySection";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

type Variant = {
  id: string;
  name: string;
  nameTh: string;
  slug: string;
  price: number | null;
  fuelType: string;
  powerKw: number | null;
  torqueNm: number | null;
  rangeKm: number | null;
  batteryKwh: number | null;
  batteryChemistry: string | null;
  chargeDcKw: number | null;
  chargeAcKw: number | null;
  dimensionsMm: string | null;
  wheelbaseMm: number | null;
  groundClearanceMm: number | null;
  warrantyYears: number | null;
  warrantyKm: number | null;
  // evidence provenance per section (from page.tsx joins)
  evidence: {
    priceVerified: boolean;
    performance: boolean;
    battery: boolean;
    charging: boolean;
    dimensions: boolean;
    warranty: boolean;
    lastVerifiedAt: string | null;
  };
  // research-only observations (NOT verified) — shown clearly distinct
  researchSpecs: { label: string; value: string }[];
};

type ModelData = {
  id: string;
  name: string;
  nameTh: string;
  brand: string;
  brandTh: string;
  variants: Variant[];
  images: { url: string; role: string; caption: string | null }[];
};

const NO_DATA = "ยังไม่มีข้อมูลยืนยัน";

function SpecRow({ label, value, unit }: { label: string; value: string | number | null; unit?: string }) {
  return (
    <div className="flex justify-between py-2 border-b border-[var(--color-gray-100)] last:border-0">
      <span className="text-[var(--color-gray-500)]">{label}</span>
      {value != null ? (
        <span className="font-medium text-[var(--color-gray-900)]">
          {typeof value === "number" ? value.toLocaleString() : value}
          {unit ? ` ${unit}` : ""}
        </span>
      ) : (
        <span className="text-[var(--color-gray-400)] text-sm italic">{NO_DATA}</span>
      )}
    </div>
  );
}

function EvidenceDot({ ok }: { ok: boolean }) {
  return ok
    ? <span className="text-[var(--color-success-600)]" title="ตรวจสอบจากแหล่งทางการแล้ว">✔️ ยืนยันแล้ว</span>
    : <span className="text-[var(--color-gray-400)]" title="ยังไม่มีการตรวจสอบจากแหล่งทางการ">⛔ ยังไม่ยืนยัน</span>;
}

function ResearchOnlyBlock({ researchSpecs, name }: { researchSpecs: { label: string; value: string }[]; name: string }) {
  if (researchSpecs.length === 0) return null;
  return (
    <Card className="border-l-4 border-[var(--color-warning-400)]">
      <CardBody>
        <h3 className="font-medium text-[var(--color-gray-700)] mb-2">ข้อมูลจากงานวิจัย (ยังไม่ยืนยัน) — {name}</h3>
        <p className="text-xs text-[var(--color-gray-500)] mb-2">
          ⚠️ ข้อมูลจากการรวบรวมสื่อ/งานวิจัย ยังไม่ผ่านการตรวจสอบจากแหล่งทางการ โปรดใช้เพื่อการอ้างอิงเบื้องต้น
        </p>
        <ul className="text-sm space-y-1">
          {researchSpecs.map((r) => (
            <li key={r.label} className="flex justify-between">
              <span className="text-[var(--color-gray-500)]">{r.label}</span>
              <span className="italic text-[var(--color-gray-700)]">{r.value}</span>
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

export default function VehicleDetailClient({ model }: { model: ModelData }) {
  const heroImage = model.images.find((img) => img.role === "hero") || model.images[0];
  const primary = model.variants[0];

  return (
    <div className="container-narrow py-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-[var(--color-gray-500)] mb-6">
        <Link href="/cars" className="hover:text-[var(--color-primary-600)]">รถยนต์</Link>
        <span>/</span>
        <span className="text-[var(--color-gray-900)]">{model.brand} {model.name}</span>
      </nav>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Hero */}
          <Card className="overflow-hidden">
            <div className="relative h-64 md:h-96 bg-[var(--color-gray-100)]">
              {heroImage ? (
                <img src={heroImage.url} alt={`${model.brand} ${model.name}`} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-6xl text-[var(--color-gray-300)]">🚗</div>
              )}
            </div>
            <CardBody>
              <div className="text-sm text-[var(--color-gray-500)] mb-1">{model.brandTh}</div>
              <h1 className="text-2xl md:text-3xl font-bold text-[var(--color-gray-900)]">{model.name}</h1>
              <div className="text-[var(--color-gray-600)]">{model.nameTh}</div>
              {primary && (
                <div className="mt-3 flex flex-wrap items-baseline gap-3">
                  <span className="text-2xl font-bold text-[var(--color-primary-600)]">
                    {primary.price ? `฿${primary.price.toLocaleString()}` : NO_DATA}
                  </span>
                  <span className="text-xs">
                    <EvidenceDot ok={primary.evidence.priceVerified} />
                  </span>
                  {primary.evidence.lastVerifiedAt && (
                    <span className="text-xs text-[var(--color-gray-400)]">
                      ตรวจสอบล่าสุด {new Date(primary.evidence.lastVerifiedAt).toLocaleDateString("th-TH")}
                    </span>
                  )}
                </div>
              )}
            </CardBody>
          </Card>

          {/* Variants table */}
          <Card>
            <CardBody>
              <h2 className="text-lg font-semibold text-[var(--color-gray-900)] mb-4">รุ่นย่อย ({model.variants.length})</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-gray-200)]">
                      <th className="text-left py-3 px-2 text-[var(--color-gray-500)] font-medium">รุ่นย่อย</th>
                      <th className="text-left py-3 px-2 text-[var(--color-gray-500)] font-medium">เชื้อเพลง</th>
                      <th className="text-right py-3 px-2 text-[var(--color-gray-500)] font-medium">กำลัง</th>
                      <th className="text-right py-3 px-2 text-[var(--color-gray-500)] font-medium">ระยะทาง</th>
                      <th className="text-right py-3 px-2 text-[var(--color-gray-500)] font-medium">ราคา</th>
                    </tr>
                  </thead>
                  <tbody>
                    {model.variants.map((v) => (
                      <tr key={v.id} className="border-b border-[var(--color-gray-100)] hover:bg-[var(--color-gray-50)]">
                        <td className="py-3 px-2">
                          <span className="font-medium text-[var(--color-gray-900)]">
                            {v.name}
                          </span>
                        </td>
                        <td className="py-3 px-2">
                          <Badge variant={v.fuelType === "BEV" ? "success" : v.fuelType === "EV" ? "success" : v.fuelType === "HEV" ? "warning" : "default"}>
                            {v.fuelType}
                          </Badge>
                        </td>
                        <td className="py-3 px-2 text-right text-[var(--color-gray-700)]">
                          {v.powerKw ? `${Math.round(v.powerKw * 1.341)} แรงม้า` : NO_DATA}
                        </td>
                        <td className="py-3 px-2 text-right text-[var(--color-gray-700)]">
                          {v.rangeKm ? `${Math.round(v.rangeKm)} km` : NO_DATA}
                        </td>
                        <td className="py-3 px-2 text-right font-bold text-[var(--color-primary-600)]">
                          {v.price ? `฿${v.price.toLocaleString()}` : NO_DATA}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-[var(--color-gray-400)] mt-2">
                ℹ️ ราคาที่แสดงเป็นราคาที่ผ่านการตรวจสอบจากแหล่งข้อมูลทางการเท่านั้น
              </p>
            </CardBody>
          </Card>

          {/* Detailed verified specs for first variant with data */}
          {model.variants.length > 0 && (
            <Card>
              <CardBody>
                <h2 className="text-lg font-semibold text-[var(--color-gray-900)] mb-4">
                  สเปคหลัก — {model.variants[0].name}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
                  <div>
                    <h3 className="font-medium text-[var(--color-gray-700)] mb-1 flex items-center justify-between gap-2">
                      ประสิทธิภาพ
                      <span className="text-[10px] font-normal"><EvidenceDot ok={model.variants[0].evidence.performance} /></span>
                    </h3>
                    <SpecRow label="กำลังสูงสุด" value={model.variants[0].powerKw} unit="kW" />
                    <SpecRow label="แรงบิด" value={model.variants[0].torqueNm} unit="Nm" />
                    <SpecRow label="ระยะทาง" value={model.variants[0].rangeKm} unit="km" />
                  </div>
                  <div>
                    <h3 className="font-medium text-[var(--color-gray-700)] mb-3 flex items-center justify-between gap-2">
                      แบตเตอรี่และการชาร์จ
                      <span className="text-[10px] font-normal">
                        <EvidenceDot ok={model.variants[0].evidence.battery || model.variants[0].evidence.charging} />
                      </span>
                    </h3>
                    <SpecRow label="ความจุแบตเตอรี่" value={model.variants[0].batteryKwh} unit="kWh" />
                    <SpecRow label="ประเภทแบตเตอรี่" value={model.variants[0].batteryChemistry} />
                    <SpecRow label="ชาร์จ DC" value={model.variants[0].chargeDcKw} unit="kW" />
                    <SpecRow label="ชาร์จ AC" value={model.variants[0].chargeAcKw} unit="kW" />
                  </div>
                  <div>
                    <h3 className="font-medium text-[var(--color-gray-700)] mb-3 flex items-center justify-between gap-2">
                      ขนาด
                      <span className="text-[10px] font-normal"><EvidenceDot ok={model.variants[0].evidence.dimensions} /></span>
                    </h3>
                    <SpecRow label="ยาวxกว้างxสูง" value={model.variants[0].dimensionsMm} unit="mm" />
                    <SpecRow label="ฐานล้อ" value={model.variants[0].wheelbaseMm} unit="mm" />
                    <SpecRow label="ระยะต่ำสุด" value={model.variants[0].groundClearanceMm} unit="mm" />
                  </div>
                  <div>
                    <h3 className="font-medium text-[var(--color-gray-700)] mb-3 flex items-center justify-between gap-2">
                      การรับประกัน
                      <span className="text-[10px] font-normal"><EvidenceDot ok={model.variants[0].evidence.warranty} /></span>
                    </h3>
                    <SpecRow label="ระยะเวลา" value={model.variants[0].warrantyYears} unit="ปี" />
                    <SpecRow label="ระยะทาง" value={model.variants[0].warrantyKm} unit="km" />
                  </div>
                </div>
                <p className="text-xs text-[var(--color-gray-400)] mt-3">
                  ℹ️ แสดงเฉพาะข้อมูลที่ตรวจสอบแล้ว — ช่องที่ระบุ &quot;{NO_DATA}&quot; ยังไม่มีแหล่งข้อมูลที่ยืนยันได้
                </p>
              </CardBody>
            </Card>
          )}

          {/* Research-only observations (clearly NOT verified) */}
          {model.variants.length > 0 && (
            <ResearchOnlyBlock researchSpecs={model.variants[0].researchSpecs} name={model.variants[0].name} />
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <Card>
            <CardBody className="space-y-3">
              <Link href={`/compare?ids=${model.variants[0]?.id ?? ""}`}>
                <Button className="w-full" variant="primary">
                  ⚖️ เปรียบเทียบรุ่นนี้
                </Button>
              </Link>
              <Button className="w-full" variant="secondary">
                🔖 บันทึก
              </Button>
              <Link href="/ai-ask">
                <Button className="w-full" variant="ghost">
                  💬 ถาม AI เกี่ยวกับรุ่นนี้
                </Button>
              </Link>
            </CardBody>
          </Card>
        </div>
      </div>

      {/* Community comments (Part E) */}
      <div className="mt-8">
        <CommunitySection modelId={model.id} />
      </div>
    </div>
  );
}
