"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

type ComparisonVehicle = {
  id: string;
  name: string;
  nameTh: string;
  model: string;
  modelTh: string;
  brand: string;
  brandTh: string;
  price: { amount: number; type: string } | null;
  specs: {
    power: number | null;
    torque: number | null;
    range: number | null;
    length: number | null;
    width: number | null;
    height: number | null;
    wheelbase: number | null;
    battery: number | null;
    chemistry: string | null;
    acCharge: number | null;
    dcCharge: number | null;
  };
  features: { slug: string; nameEn: string; nameTh: string; standard: boolean }[];
};

const SPEC_GROUPS = [
  {
    group: "ราคา",
    fields: [
      { key: "price", label: "ราคา", format: (v: any) => v ? `฿${Number(v.amount).toLocaleString()}` : "—" },
    ],
  },
  {
    group: "สมรรถนะ",
    fields: [
      { key: "power", label: "กำลัง", unit: "kW" },
      { key: "torque", label: "แรงบิด", unit: "Nm" },
      { key: "range", label: "ระยะทาง", unit: "km" },
    ],
  },
  {
    group: "มิติ",
    fields: [
      { key: "length", label: "ยาว", unit: "mm" },
      { key: "width", label: "กว้าง", unit: "mm" },
      { key: "height", label: "สูง", unit: "mm" },
      { key: "wheelbase", label: "ฐานล้อ", unit: "mm" },
    ],
  },
  {
    group: "แบตเตอรี่และการชาร์จ",
    fields: [
      { key: "battery", label: "แบตเตอรี่", unit: "kWh" },
      { key: "acCharge", label: "ชาร์จ AC", unit: "kW" },
      { key: "dcCharge", label: "ชาร์จเร็ว DC", unit: "kW" },
    ],
  },
];

const NO_DATA = "ยังไม่มีข้อมูลยืนยัน";

function formatValue(field: any, value: any) {
  if (value === null || value === undefined) return NO_DATA;
  if (field.format) return field.format(value);
  return `${value} ${field.unit || ""}`.trim();
}

export default function ComparePage() {
  const [data, setData] = useState<ComparisonVehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ids = params.get("ids");
    if (!ids) {
      setError("กรุณาเลือกรถอย่างน้อย 2 รุ่น");
      setLoading(false);
      return;
    }

    fetch(`/api/compare?ids=${ids}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.error) {
          setError(d.error === "variants_not_found" ? "ไม่พบรถที่เลือก" : "ไม่สามารถโหลดข้อมูลได้");
        } else {
          setData(d.comparison || []);
        }
        setLoading(false);
      })
      .catch(() => {
        setError("ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้");
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="container-narrow py-8">
        <div className="text-center py-12 text-[var(--color-gray-500)]">กำลังโหลด...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-narrow py-8">
        <Card>
          <CardBody className="text-center py-12">
            <div className="text-4xl mb-3">⚠️</div>
            <div className="text-[var(--color-gray-600)] mb-4">{error}</div>
            <Link href="/search">
              <Button>ไปหน้าค้นหา</Button>
            </Link>
          </CardBody>
        </Card>
      </div>
    );
  }

  if (data.length < 2) {
    return (
      <div className="container-narrow py-8">
        <Card>
          <CardBody className="text-center py-12">
            <div className="text-4xl mb-3">🚗</div>
            <div className="text-[var(--color-gray-600)] mb-4">กรุณาเลือกรถอย่างน้อย 2 รุ่นเพื่อเปรียบเทียบ</div>
            <Link href="/search">
              <Button>ไปหน้าค้นหา</Button>
            </Link>
          </CardBody>
        </Card>
      </div>
    );
  }

  const allFeatures = Array.from(new Set(data.flatMap((v) => v.features.map((f) => f.slug))));

  return (
    <div className="container-narrow py-8">
      <h1 className="text-3xl font-bold text-[var(--color-gray-900)] mb-6">เปรียบเทียบรถยนต์</h1>

      {/* Vehicle headers */}
      <div className={`grid gap-4 mb-6 ${data.length === 2 ? "grid-cols-2" : data.length === 3 ? "grid-cols-3" : "grid-cols-2 md:grid-cols-4"}`}>
        {data.map((v) => (
          <Card key={v.id} variant="elevated" className="text-center">
            <CardBody>
              <div className="text-sm text-[var(--color-gray-500)] mb-1">{v.brand}</div>
              <div className="font-bold text-lg text-[var(--color-gray-900)] mb-1">{v.name}</div>
              <div className="text-sm text-[var(--color-gray-600)] mb-3">{v.model}</div>
              {v.price && (
                <div className="text-xl font-bold text-[var(--color-primary-600)]">
                  ฿{v.price.amount.toLocaleString()}
                </div>
              )}
            </CardBody>
          </Card>
        ))}
      </div>

      {/* Spec groups */}
      <div className="space-y-6">
        {SPEC_GROUPS.map((group) => (
          <Card key={group.group}>
            <CardBody>
              <h3 className="text-sm font-semibold text-[var(--color-gray-500)] mb-4 uppercase tracking-wider">{group.group}</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <tbody>
                    {group.fields.map((field) => (
                      <tr key={field.key} className="border-b border-[var(--color-gray-100)] last:border-0">
                        <td className="py-3 pr-4 text-[var(--color-gray-600)] font-medium whitespace-nowrap w-32">{field.label}</td>
                        {data.map((v: any) => {
                          const value = field.key === "price" ? v.price : v.specs[field.key];
                          return (
                            <td key={v.id} className="py-3 px-2 text-center text-[var(--color-gray-900)]">
                              {formatValue(field, value)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>
        ))}

        {/* Features comparison */}
        {allFeatures.length > 0 && (
          <Card>
            <CardBody>
              <h3 className="text-sm font-semibold text-[var(--color-gray-500)] mb-4 uppercase tracking-wider">อุปกรณ์และระบบช่วยเหลือ</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <tbody>
                    {allFeatures.map((slug) => {
                      const feature = data[0].features.find((f) => f.slug === slug);
                      return (
                        <tr key={slug} className="border-b border-[var(--color-gray-100)] last:border-0">
                          <td className="py-2 pr-4 text-[var(--color-gray-600)] font-medium whitespace-nowrap">
                            {feature?.nameTh || slug}
                          </td>
                          {data.map((v) => {
                            const hasFeature = v.features.some((f) => f.slug === slug);
                            return (
                              <td key={v.id} className="py-2 px-2 text-center">
                                {hasFeature ? (
                                  <span className="text-[var(--color-success-600)]">✓</span>
                                ) : (
                                  <span className="text-[var(--color-gray-300)]">—</span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>
        )}
      </div>
      {/* Provenance note */}
      <p className="text-xs text-[var(--color-gray-400)] mt-4">
        ℹ️ ข้อมูลที่แสดงเป็นข้อมูลที่ผ่านการตรวจสอบจากแหล่งข้อมูลทางการเท่านั้น — ช่องที่ระบุ &quot;{NO_DATA}&quot; ยังไม่มีแหล่งข้อมูลที่ยืนยันได้
      </p>
    </div>
  );
}
