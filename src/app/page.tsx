"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

type Model = {
  id: string;
  nameEn: string;
  nameTh: string;
  slug: string;
  manufacturer: { nameEn: string; nameTh: string; slug: string };
  minPrice: number | null;
  maxPrice: number | null;
  variantCount: number;
  primaryFuelType: string;
  heroImage: string | null;
};

type Stats = {
  totalVariants: number;
  totalManufacturers: number;
  evCount: number;
  hevCount: number;
};

function ModelCard({ model }: { model: Model }) {
  return (
    <Link href={`/cars/${model.manufacturer.slug}/${model.slug}`}>
      <Card variant="elevated" className="h-full overflow-hidden group">
        <div className="relative h-48 bg-[var(--color-gray-100)] overflow-hidden">
          {model.heroImage ? (
            <img
              src={model.heroImage}
              alt={`${model.manufacturer.nameEn} ${model.nameEn}`}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              loading="lazy"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-4xl text-[var(--color-gray-300)]">
              🚗
            </div>
          )}
          <div className="absolute top-3 left-3">
            <Badge
              variant={model.primaryFuelType === "EV" ? "success" : model.primaryFuelType === "HEV" ? "warning" : "default"}
              size="md"
            >
              {model.primaryFuelType}
            </Badge>
          </div>
        </div>
        <CardBody>
          <div className="text-xs text-[var(--color-gray-500)] mb-1">{model.manufacturer.nameEn}</div>
          <h3 className="font-semibold text-[var(--color-gray-900)] mb-2 group-hover:text-[var(--color-primary-600)] transition-colors">
            {model.nameEn}
          </h3>
          <div className="flex items-center justify-between">
            <div>
              {model.minPrice && model.maxPrice ? (
                <div className="text-lg font-bold text-[var(--color-primary-600)]">
                  ฿{model.minPrice.toLocaleString()} - ฿{model.maxPrice.toLocaleString()}
                </div>
              ) : (
                <div className="text-sm text-[var(--color-gray-400)]">ไม่มีข้อมูลราคา</div>
              )}
            </div>
            <div className="text-xs text-[var(--color-gray-400)]">{model.variantCount} รุ่นย่อย</div>
          </div>
        </CardBody>
      </Card>
    </Link>
  );
}

export default function HomePage() {
  const [models, setModels] = useState<Model[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/models?limit=12")
      .then((r) => r.json())
      .then((data) => {
        setModels(data.results || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));

    fetch("/api/cars?limit=1")
      .then((r) => r.json())
      .then((data) => {
        setStats({
          totalVariants: data.total || 0,
          totalManufacturers: data.totalManufacturers || 0,
          evCount: data.evCount || 0,
          hevCount: data.hevCount || 0,
        });
      })
      .catch(() => {});
  }, []);

  const evModels = models.filter((m) => m.primaryFuelType === "EV").slice(0, 4);
  const hevModels = models.filter((m) => m.primaryFuelType === "HEV").slice(0, 4);

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="bg-gradient-to-br from-[var(--color-primary-900)] via-[var(--color-primary-800)] to-[var(--color-primary-900)] text-white">
        <div className="container-narrow py-20 text-center">
          <h1 className="text-4xl md:text-5xl font-bold mb-4 tracking-tight">
            Car Intelligence Thailand
          </h1>
          <p className="text-[var(--color-primary-200)] text-lg mb-8 max-w-2xl mx-auto">
            ค้นคว้า เปรียบเทียบ และถาม AI เกี่ยวกับรถยนต์ตลาดไทย
            จากแหล่งข้อมูลที่ตรวจสอบได้
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link
              href="/search"
              className="px-6 py-3 bg-white text-[var(--color-primary-700)] font-semibold rounded-[var(--radius-xl)] hover:bg-[var(--color-primary-50)] transition-colors"
            >
              ค้นหารถ
            </Link>
            <Link
              href="/compare"
              className="px-6 py-3 bg-[var(--color-primary-700)] text-white font-semibold rounded-[var(--radius-xl)] hover:bg-[var(--color-primary-600)] transition-colors"
            >
              เปรียบเทียบ
            </Link>
          </div>
        </div>
      </section>

      {/* Stats */}
      {stats && (
        <section className="container-narrow -mt-8">
          <Card variant="elevated" className="grid grid-cols-2 md:grid-cols-4 divide-x divide-[var(--color-gray-100)]">
            <div className="p-6 text-center">
              <div className="text-3xl font-bold text-[var(--color-primary-600)]">{stats.totalVariants}</div>
              <div className="text-sm text-[var(--color-gray-500)] mt-1">รถยนต์</div>
            </div>
            <div className="p-6 text-center">
              <div className="text-3xl font-bold text-[var(--color-success-600)]">{stats.evCount}</div>
              <div className="text-sm text-[var(--color-gray-500)] mt-1">EV</div>
            </div>
            <div className="p-6 text-center">
              <div className="text-3xl font-bold text-[var(--color-warning-600)]">{stats.hevCount}</div>
              <div className="text-sm text-[var(--color-gray-500)] mt-1">HEV</div>
            </div>
            <div className="p-6 text-center">
              <div className="text-3xl font-bold text-[var(--color-gray-700)]">{stats.totalManufacturers}</div>
              <div className="text-sm text-[var(--color-gray-500)] mt-1">แบรนด์</div>
            </div>
          </Card>
        </section>
      )}

      {/* EV Section */}
      {evModels.length > 0 && (
        <section className="container-narrow py-12">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-[var(--color-gray-900)]">⚡ รถยนต์ไฟฟ้า EV</h2>
            <Link href="/search?q=EV" className="text-sm text-[var(--color-primary-600)] hover:underline">
              ดูทั้งหมด →
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {evModels.map((m) => (
              <ModelCard key={m.id} model={m} />
            ))}
          </div>
        </section>
      )}

      {/* HEV Section */}
      {hevModels.length > 0 && (
        <section className="container-narrow py-12">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-[var(--color-gray-900)]">🔋 รถยนต์ไฮบริด HEV</h2>
            <Link href="/search?q=HEV" className="text-sm text-[var(--color-primary-600)] hover:underline">
              ดูทั้งหมด →
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {hevModels.map((m) => (
              <ModelCard key={m.id} model={m} />
            ))}
          </div>
        </section>
      )}

      {/* All Models */}
      <section className="container-narrow py-12">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-[var(--color-gray-900)]">รถยนต์ทั้งหมด</h2>
          <Link href="/cars" className="text-sm text-[var(--color-primary-600)] hover:underline">
            ดูทั้งหมด →
          </Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {models.slice(0, 6).map((m) => (
            <ModelCard key={m.id} model={m} />
          ))}
        </div>
      </section>
    </div>
  );
}
