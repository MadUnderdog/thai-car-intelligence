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

export default function CarsPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [brand, setBrand] = useState("");
  const [fuelType, setFuelType] = useState("");
  const [bodyType, setBodyType] = useState("");
  const [sortBy, setSortBy] = useState("price_asc");
  const [compareList, setCompareList] = useState<string[]>([]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (search) params.set("q", search);
    if (brand) params.set("manufacturer", brand);
    if (fuelType) params.set("fuelType", fuelType);
    params.set("limit", "50");
    fetch(`/api/models?${params}`).then(r => r.json()).then(d => {
      let results = d.results || [];
      if (sortBy === "price_asc") results.sort((a: any, b: any) => (a.minPrice || 999999999) - (b.minPrice || 999999999));
      if (sortBy === "price_desc") results.sort((a: any, b: any) => (b.minPrice || 0) - (a.minPrice || 0));
      setModels(results);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [search, brand, fuelType, sortBy]);

  const toggleCompare = (id: string) => {
    setCompareList(prev => prev.includes(id) ? prev.filter(x => x !== id) : prev.length < 4 ? [...prev, id] : prev);
  };

  const brands = ["Toyota", "Honda", "BYD", "MG", "Mazda", "Nissan", "Ford", "Hyundai", "Kia", "Tesla", "Isuzu", "Mitsubishi", "Suzuki"];

  // Client-side body-type filter (slug → type mapping)
  const BODY_TYPE_SLUGS: Record<string, string> = {
    "honda-city": "sedan", "honda-city-hb": "hatchback", "honda-civic": "sedan",
    "honda-civic-tr": "coupe", "honda-cr-v": "SUV", "honda-hr-v": "SUV",
    "honda-br-v": "SUV", "honda-wr-v": "SUV", "honda-accord": "sedan",
    "honda-en2": "sedan", "honda-super-one": "SUV",
    "toyota-yaris": "hatchback", "toyota-yaris-ativ": "sedan",
    "toyota-corolla-altis": "sedan", "toyota-camry": "sedan",
    "toyota-fortuner": "SUV", "toyota-hilux": "pickup",
    "toyota-yaris-cross": "SUV", "toyota-bz4x": "SUV",
    "mg4": "hatchback", "mg-s5": "SUV", "mg-im5": "sedan", "mg-im6": "SUV",
    "mg-zs": "SUV", "mg-zs-ev": "SUV", "mg3-hybrid": "hatchback",
    "mg-hs-phev": "SUV", "mg-urban": "hatchback", "mg-ep": "sedan",
    "mg-es": "sedan", "mg-extender": "pickup", "mg-cyberster": "coupe",
    "mg-maxus7": "MPV", "mg-maxus9": "SUV", "mg-vs-hev": "sedan", "mg5": "sedan",
    "atto-2": "SUV", "atto-3": "SUV", "dolphin": "hatchback",
    "seal": "sedan", "seal-6": "sedan", "sealion-5": "SUV",
    "sealion-6": "SUV", "sealion-7": "SUV", "m6": "SUV",
    "denza-z9gt": "wagon", "geely-ex5": "SUV", "gwm-tank-500": "SUV",
    "tesla-model-3": "sedan", "tesla-model-y": "SUV",
    "hyundai-ioniq-5": "SUV", "hyundai-santa-fe": "SUV",
    "nio-firefly": "hatchback", "nissan-kicks": "SUV",
    "subaru-crosstrek": "SUV", "mazda-6e": "sedan", "avatr-11": "SUV",
  };

  const filteredModels = bodyType
    ? models.filter((m) => BODY_TYPE_SLUGS[m.slug] === bodyType)
    : models;

  return (
    <div className="container-narrow py-8">
      <h1 className="text-3xl font-bold text-[var(--color-gray-900)] mb-6">รถยนต์ทั้งหมด</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <input
          type="text"
          placeholder="ค้นหา..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] px-4 py-2 bg-white border border-[var(--color-gray-300)] rounded-[var(--radius-lg)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-500)]"
        />
        <select value={brand} onChange={e => setBrand(e.target.value)} className="px-4 py-2 bg-white border border-[var(--color-gray-300)] rounded-[var(--radius-lg)]">
          <option value="">ทุกแบรนด์</option>
          {brands.map(b => <option key={b} value={b}>{b}</option>)}
        </select>
        <select value={fuelType} onChange={e => setFuelType(e.target.value)} className="px-4 py-2 bg-white border border-[var(--color-gray-300)] rounded-[var(--radius-lg)]">
          <option value="">ทุกเชื้อเพลิง</option>
          <option value="EV">EV</option>
          <option value="HEV">HEV</option>
          <option value="Petrol">เบนซิน</option>
          <option value="Diesel">ดีเซล</option>
        </select>
        <select value={bodyType} onChange={e => setBodyType(e.target.value)} className="px-4 py-2 bg-white border border-[var(--color-gray-300)] rounded-[var(--radius-lg)]">
          <option value="">ทุกประเภท</option>
          <option value="SUV">SUV / ครอสโอเวอร์</option>
          <option value="sedan">ซีดาน</option>
          <option value="hatchback">แฮทช์แบ็ก</option>
          <option value="pickup">กระบะ</option>
          <option value="MPV">MPV / มินิแวน</option>
          <option value="coupe">คูเป้</option>
        </select>
        <select value={sortBy} onChange={e => setSortBy(e.target.value)} className="px-4 py-2 bg-white border border-[var(--color-gray-300)] rounded-[var(--radius-lg)]">
          <option value="price_asc">ราคาต่ำ → สูง</option>
          <option value="price_desc">ราคาสูง → ต่ำ</option>
        </select>
      </div>

      {/* Compare bar */}
      {compareList.length >= 2 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-[var(--color-primary-600)] text-white px-6 py-3 rounded-[var(--radius-xl)] shadow-lg flex items-center gap-4 z-[var(--z-sticky)]">
          <span className="text-sm font-medium">เลือกแล้ว {compareList.length}/4 คัน</span>
          <Link
            href={`/compare?ids=${compareList.join(",")}`}
            className="px-4 py-1.5 bg-white text-[var(--color-primary-600)] text-sm font-medium rounded-[var(--radius-lg)] hover:bg-[var(--color-primary-50]"
          >
            เปรียบเทียบ
          </Link>
        </div>
      )}

      {/* Results */}
      <div className="text-sm text-[var(--color-gray-500)] mb-4">{filteredModels.length} รุ่น{bodyType ? ` (${bodyType})` : ""}</div>

      {loading ? (
        <div className="text-center py-12 text-[var(--color-gray-500)]">กำลังโหลด...</div>
      ) : models.length === 0 ? (
        <div className="text-center py-12 text-[var(--color-gray-500)]">ไม่พบรถยนต์</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredModels.map(model => (
            <div key={model.id} className="relative">
              <Link href={`/cars/${model.manufacturer.slug}/${model.slug}`}>
                <Card variant="elevated" className="h-full overflow-hidden group">
                  {/* Image */}
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

                  {/* Content */}
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

              {/* Compare button */}
              <button
                onClick={(e) => { e.preventDefault(); toggleCompare(model.id); }}
                className={`absolute top-3 right-3 w-8 h-8 rounded-full border-2 flex items-center justify-center text-sm transition ${
                  compareList.includes(model.id)
                    ? "bg-[var(--color-primary-600)] border-[var(--color-primary-600)] text-white"
                    : "bg-white border-[var(--color-gray-300)] text-[var(--color-gray-400)] hover:border-[var(--color-primary-400)]"
                }`}
              >
                {compareList.includes(model.id) ? "✓" : "+"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
