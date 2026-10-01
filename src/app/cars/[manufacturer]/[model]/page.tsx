import { notFound } from "next/navigation";
import pool from "@/lib/db-pg";
import type { Metadata } from "next";
import VehicleDetailClient from "./VehicleDetailClient";
import { detailModelLookupSql, variantRowsSql, researchRowsSql, brochureSql } from "../../../../../lib/catalog/detail-queries";
import { specEvidenceFlags, brochureBlock, imageBlock } from "../../../../../lib/ux/detail-view";

type Props = { params: Promise<{ model: string; manufacturer: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { model, manufacturer } = await params;
  const result: any = await pool.query(detailModelLookupSql, [model, manufacturer]);
  if (!result.rows[0]) return { title: "ไม่พบข้อมูลรถ" };
  const r = result.rows[0];
  return { title: `${r.nameEn} | Thai Car Intel`, description: `ข้อมูล ${r.nameEn} ${r.mfrNameEn}` };
}

export default async function VehicleDetailPage({ params }: Props) {
  const { model, manufacturer } = await params;

  // P116: one shared lookup — BOTH slugs + ACTIVE on model AND manufacturer
  // (cross-manufacturer/model slugs 404, never resolve across entities).
  const modelResult: any = await pool.query(detailModelLookupSql, [model, manufacturer]);
  if (!modelResult.rows[0]) notFound();
  const carModel = modelResult.rows[0];

  // P116: price join uses the full currentOfficialPrice chain
  // (lib/catalog/price-sql — isCurrent + VERIFIED doc + ACTIVE official
  //  source + VERIFIED brochure verification); provenance rides along.
  const variants: any = await pool.query(variantRowsSql, [carModel.id]);

  // Research-only (VariantSpec, research-scoped source documents — NOT verified)
  const research: any = variants.rows.length
    ? await pool.query(researchRowsSql, [variants.rows.map((v: any) => v.id)])
    : { rows: [] };

  const media: any = await pool.query(
    `SELECT url, role, "captionTh", "captionEn" FROM "Media" WHERE "modelId" = $1 AND type = 'IMAGE' LIMIT 5`,
    [carModel.id]
  );

  // Blueprint 87: verified official brochure/price-list PDF for the brand;
  // falls back to the official site link (never an invented file).
  const brochure: any = await pool.query(brochureSql, [carModel.mfrId]);
  const brochureDoc = brochure.rows[0] ?? null;

  const researchByVariant: Record<string, { label: string; value: string }[]> = {};
  for (const r of research.rows) {
    const label = r.key;
    const value = r.valueNumeric != null ? `${Number(r.valueNumeric).toLocaleString()}${r.unit ? ` ${r.unit}` : ""}` : `${r.value ?? ""}${r.unit ? ` ${r.unit}` : ""}`;
    if (!value.trim()) continue;
    (researchByVariant[r.variantId] ??= []).push({ label, value });
  }

  const modelData = {
    id: carModel.id,
    name: carModel.nameEn,
    nameTh: carModel.nameTh,
    brand: carModel.mfrNameEn,
    brandTh: carModel.mfrTh,
    officialUrl: carModel.officialUrl ?? null,
    brochure: brochureBlock(brochureDoc ? {
      title: brochureDoc.titleEn || brochureDoc.titleTh,
      url: brochureDoc.canonicalUrl || brochureDoc.url,
      sourceName: brochureDoc.sourceName,
      verifiedAt: brochureDoc.verifiedAt,
      documentStatus: brochureDoc.documentStatus,
    } : null, carModel.officialUrl ?? null),
    variants: variants.rows.map((v: any) => ({
      id: v.id,
      name: v.nameEn,
      nameTh: v.nameTh,
      slug: v.slug,
      price: v.price ? Number(v.price) : null,
      priceSource: v.priceSourceUrl ? {
        url: v.priceSourceCanonical || v.priceSourceUrl,
        sourceName: v.priceSourceName || null,
        verifiedAt: v.lastVerifiedAt ? new Date(v.lastVerifiedAt).toISOString() : null,
      } : null,
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
      evidence: {
        priceVerified: !!v.priceVerified,
        // P116: tier-honest marks — "ตรวจสอบจากแหล่งทางการแล้ว" only for
        // primary_official rows (secondary/media spec rows never claim official)
        performance: specEvidenceFlags([{ sourceTier: v.perfTier }]),
        battery: specEvidenceFlags([{ sourceTier: v.battTier }]),
        charging: specEvidenceFlags([{ sourceTier: v.chargeTier }]),
        dimensions: specEvidenceFlags([{ sourceTier: v.dimsTier }]),
        warranty: specEvidenceFlags([{ sourceTier: v.warrantyTier }]),
        lastVerifiedAt: v.lastVerifiedAt ? new Date(v.lastVerifiedAt).toISOString() : null,
      },
      researchSpecs: researchByVariant[v.id] ?? [],
    })),
    images: media.rows.map((m: any) => ({ url: m.url, role: m.role, caption: m.captionTh || m.captionEn })),
    // Blueprint 86: no provenable image → placeholder + official-source link
    heroFallback: imageBlock(
      media.rows.map((m: any) => ({ url: m.url, role: m.role })),
      carModel.officialUrl ?? null,
    ),
  };

  return <VehicleDetailClient model={modelData} />;
}
