"use client";

import Link from "next/link";
import { Card, CardBody } from "@/components/ui/Card";
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

export default function VehicleDetailClient({ model }: { model: ModelData }) {
  const heroImage = model.images.find((img) => img.role === "hero") || model.images[0];

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
                          <Link href={`/cars/${model.brand.toLowerCase()}/${v.slug}`} className="font-medium text-[var(--color-gray-900)] hover:text-[var(--color-primary-600)]">
                            {v.name}
                          </Link>
                        </td>
                        <td className="py-3 px-2">
                          <Badge variant={v.fuelType === "EV" ? "success" : v.fuelType === "HEV" ? "warning" : "default"}>
                            {v.fuelType}
                          </Badge>
                        </td>
                        <td className="py-3 px-2 text-right text-[var(--color-gray-700)]">
                          {v.powerKw ? `${Math.round(v.powerKw)} kW` : "—"}
                        </td>
                        <td className="py-3 px-2 text-right text-[var(--color-gray-700)]">
                          {v.rangeKm ? `${Math.round(v.rangeKm)} km` : "—"}
                        </td>
                        <td className="py-3 px-2 text-right font-bold text-[var(--color-primary-600)]">
                          {v.price ? `฿${v.price.toLocaleString()}` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <Card>
            <CardBody className="space-y-3">
              <Button className="w-full" variant="primary">
                + เพิ่มเพื่อเปรียบเทียบ
              </Button>
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
    </div>
  );
}
