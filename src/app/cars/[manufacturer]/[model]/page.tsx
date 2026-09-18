import { notFound } from "next/navigation";
import pool from "@/lib/db-pg";
import type { Metadata } from "next";
import VehicleDetailClient from "./VehicleDetailClient";

type Props = { params: Promise<{ model: string; manufacturer: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { model, manufacturer } = await params;
  const result: any = await pool.query(
    `SELECT cm."nameEn", cm."nameTh", m."nameEn" as "mfrNameEn", m."nameTh" as "mfrTh"
     FROM "CarModel" cm JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
     WHERE cm.slug = $1 AND m.slug = $2 AND cm.status = 'ACTIVE' AND m.status = 'ACTIVE'`,
    [model, manufacturer]
  );
  if (!result.rows[0]) return { title: "ไม่พบข้อมูลรถ" };
  const r = result.rows[0];
  return { title: `${r.nameEn} | Thai Car Intel`, description: `ข้อมูล ${r.nameEn} ${r.mfrNameEn}` };
}

export default async function VehicleDetailPage({ params }: Props) {
  const { model, manufacturer } = await params;

  const modelResult: any = await pool.query(
    `SELECT cm.id, cm."nameEn", cm."nameTh", m."nameEn" as "mfrNameEn", m."nameTh" as "mfrTh", m.slug as "mfrSlug"
     FROM "CarModel" cm JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
     WHERE cm.slug = $1 AND m.slug = $2 AND cm.status = 'ACTIVE' AND m.status = 'ACTIVE'`,
    [model, manufacturer]
  );
  if (!modelResult.rows[0]) notFound();
  const carModel = modelResult.rows[0];

  const variants: any = await pool.query(
    `SELECT v.id, v."nameEn", v."nameTh", v.slug, v."fuelType",
      p.amount as price,
      ps."powerKw", ps."torqueNm", ps."rangeKm",
      bs."capacityKwh", bs.chemistry,
      cs."dcPowerKw", cs."acPowerKw",
      ds."lengthMm", ds."widthMm", ds."heightMm", ds."wheelbaseMm", ds."groundClearanceMm",
      ws."vehicleYears", ws."vehicleDistanceKm", ws."batteryYears"
     FROM "Variant" v
     LEFT JOIN "Price" p ON p."variantId" = v.id AND p."isCurrent" = true
       AND p."sourceDocumentId" IS NOT NULL
       AND EXISTS (SELECT 1 FROM "SourceDocument" sd JOIN "BrochureVerification" bv ON bv."sourceDocumentId" = sd.id
                   WHERE sd.id = p."sourceDocumentId" AND sd.status = 'VERIFIED' AND bv.status = 'VERIFIED')
     LEFT JOIN "PerformanceSpec" ps ON ps."variantId" = v.id
     LEFT JOIN "BatterySpec" bs ON bs."variantId" = v.id
     LEFT JOIN "ChargingSpec" cs ON cs."variantId" = v.id
     LEFT JOIN "DimensionsSpec" ds ON ds."variantId" = v.id
     LEFT JOIN "WarrantySpec" ws ON ws."variantId" = v.id
     WHERE v."modelId" = $1 AND v.status = 'ACTIVE'
     ORDER BY p.amount ASC NULLS LAST`,
    [carModel.id]
  );

  const media: any = await pool.query(
    `SELECT url, role, "captionTh", "captionEn" FROM "Media" WHERE "modelId" = $1 AND type = 'IMAGE' LIMIT 5`,
    [carModel.id]
  );

  const modelData = {
    id: carModel.id,
    name: carModel.nameEn,
    nameTh: carModel.nameTh,
    brand: carModel.mfrNameEn,
    brandTh: carModel.mfrTh,
    variants: variants.rows.map((v: any) => ({
      id: v.id,
      name: v.nameEn,
      nameTh: v.nameTh,
      slug: v.slug,
      price: v.price ? Number(v.price) : null,
      fuelType: v.fuelType,
      powerKw: v.powerKw ? Number(v.powerKw) : null,
      torqueNm: v.torqueNm ? Number(v.torqueNm) : null,
      rangeKm: v.rangeKm ? Number(v.rangeKm) : null,
      batteryKwh: v.capacityKwh ? Number(v.capacityKwh) : null,
      batteryChemistry: v.chemistry || null,
      chargeDcKw: v.dcPowerKw ? Number(v.dcPowerKw) : null,
      chargeAcKw: v.acPowerKw ? Number(v.acPowerKw) : null,
      dimensionsMm: v.lengthMm ? `${Number(v.lengthMm)}x${Number(v.widthMm)}x${Number(v.heightMm)}` : null,
      wheelbaseMm: v.wheelbaseMm ? Number(v.wheelbaseMm) : null,
      groundClearanceMm: v.groundClearanceMm ? Number(v.groundClearanceMm) : null,
      warrantyYears: v.vehicleYears ? Number(v.vehicleYears) : null,
      warrantyKm: v.vehicleDistanceKm ? Number(v.vehicleDistanceKm) : null,
    })),
    images: media.rows.map((m: any) => ({ url: m.url, role: m.role, caption: m.captionTh || m.captionEn })),
  };

  return <VehicleDetailClient model={modelData} />;
}
