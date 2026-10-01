"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { compareErrorMessage, featureCellText } from "../../../lib/ux/compare-view";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import DifferenceFilter from "./DifferenceFilter";

type ComparisonVehicle = {
  id: string;
  name: string;
  nameTh: string;
  model: string;
  modelTh: string;
  brand: string;
  brandTh: string;
  price: { amount: number; type: string; sourceUrl: string | null; sourceName: string | null } | null;
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
  features: { slug: string; nameEn: string; nameTh: string; standard: boolean; available?: boolean }[];
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
          // P116: truthful per-code messages (need_at_least_2 ≠ generic failure)
          setError(compareErrorMessage(d.error));
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
              {v.price ? (
                <div className="space-y-0.5">
                  <div className="text-xl font-bold text-[var(--color-primary-600)]">
                    ฿{v.price.amount.toLocaleString()}
                  </div>
                  {v.price.sourceUrl && (
                    <a
                      href={v.price.sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block text-[11px] text-[var(--color-gray-400)] hover:text-[var(--color-primary-600)]"
                    >
                      แหล่งข้อมูล{v.price.sourceName ? `: ${v.price.sourceName}` : ""}
                    </a>
                  )}
                </div>
              ) : (
                <div className="text-sm text-[var(--color-gray-400)]">ยังไม่มีข้อมูลราคา</div>
              )}
            </CardBody>
          </Card>
        ))}
      </div>

      {/* Spec groups */}
      <div className="mb-2 flex items-center justify-between">
        <DifferenceFilter />
      </div>
      <div id="comparison-rows" className="space-y-6">
        {SPEC_GROUPS.map((group) => {
          // P121: never render a spec group where NO selected vehicle has ANY
          // value (e.g. battery/charging blocks on gasoline-only pairs) —
          // empty groups read as broken, not as truthful-unavailable.
          const hasAnyValue = group.fields.some((field) =>
            data.some((v: any) =>
              (field.key === "price" ? v.price : v.specs?.[field.key]) != null
            )
          );
          if (!hasAnyValue) return null;
          return (
          <Card key={group.group}>
            <CardBody>
              <h3 className="text-sm font-semibold text-[var(--color-gray-500)] mb-4 uppercase tracking-wider">{group.group}</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <tbody>
                    {group.fields.map((field) => {
                      // P121: difference-filter target — a row is "different"
                      // when the rendered values are not all identical
                      const rowValues = data.map((v: any) =>
                        JSON.stringify((field.key === "price" ? v.price : v.specs[field.key]) ?? null)
                      );
                      const different = new Set(rowValues).size > 1;
                      return (
                      <tr key={field.key} data-different={different ? "true" : "false"} className="border-b border-[var(--color-gray-100)] last:border-0">
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
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>
          );
        })}

        {/* Features comparison */}
        {allFeatures.length > 0 && (
          <Card>
            <CardBody>
              <h3 className="text-sm font-semibold text-[var(--color-gray-500)] mb-4 uppercase tracking-wider">อุปกรณ์และระบบช่วยเหลือ</h3>
              <p className="text-xs text-[var(--color-gray-400)] mb-3">✓ ติดตั้ง · ✗ ไม่ติดตั้ง (ยืนยันแล้ว) · ไม่มีข้อมูล = ยังไม่มีแหล่งข้อมูลยืนยัน</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <tbody>
                    {allFeatures.map((slug) => {
                      // label from ANY selected vehicle (not only the first)
                      const feature = data.flatMap((v) => v.features).find((f) => f.slug === slug);
                      const cells = data.map((v) => featureCellText(v.features, slug));
                      const different = new Set(cells).size > 1;
                      return (
                        <tr key={slug} data-different={different ? "true" : "false"} className="border-b border-[var(--color-gray-100)] last:border-0">
                          <td className="py-2 pr-4 text-[var(--color-gray-600)] font-medium whitespace-nowrap">
                            {feature?.nameTh || slug}
                          </td>
                          {data.map((v) => {
                            // P116 three-state: ✓ installed · ✗ explicitly not
                            // installed · ไม่มีข้อมูล = no row (never guessed)
                            const cell = featureCellText(v.features, slug);
                            const isInstalled = cell === "✓";
                            const isMissing = cell === "ไม่มีข้อมูล";
                            return (
                              <td key={v.id} className="py-2 px-2 text-center">
                                <span
                                  className={
                                    isInstalled
                                      ? "text-[var(--color-success-600)]"
                                      : isMissing
                                        ? "text-[var(--color-gray-400)] text-xs"
                                        : "text-[var(--color-gray-500)]"
                                  }
                                >
                                  {cell}
                                </span>
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
