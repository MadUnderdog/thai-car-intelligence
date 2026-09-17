// @ts-nocheck
import db from "../db";

export type ComparisonField = { key: string; label: string; values: (string | number | null)[] };
export type ComparisonSource = { url: string; title: string | null };
export type ComparisonVariant = { id: string; name: string; manufacturer: string; model: string; fields: Record<string, string | number | null>; provenance: ComparisonSource[] };
export type ComparisonResult = { variants: ComparisonVariant[]; fields: ComparisonField[] };

const specs = ["fuelType", "price", "rangeKm", "batteryKwh", "powerKw", "warrantyYears"] as const;
const labels: Record<string, string> = { fuelType: "เชื้อเพลิง", price: "ราคาเริ่มต้น", rangeKm: "ระยะทาง", batteryKwh: "ความจุแบตเตอรี่", powerKw: "กำลัง", warrantyYears: "รับประกันรถ" };
const officialSourceTypes = ["OFFICIAL_MANUFACTURER", "OFFICIAL_MANUFACTURER_BROCHURE", "OFFICIAL_MANUFACTURER_PRICE_LIST", "OFFICIAL_MANUFACTURER_PRESS_RELEASE"] as const;
const value = (v: unknown): string | number | null => {
  if (v === null || v === undefined) return null;
  const text = typeof v === "object" && "toString" in v ? String(v) : v;
  if (typeof text === "string" && text.trim() !== "" && Number.isFinite(Number(text))) return Number(text);
  return text as string | number;
};

export async function compareVariants(ids: string[], client: PrismaClient = db): Promise<ComparisonResult> {
  const unique = [...new Set(ids)].slice(0, 4);
  if (unique.length < 2) return { variants: [], fields: [] };
  const rows = await client.variant.findMany({ where: { id: { in: unique }, status: "ACTIVE" }, include: { model: { include: { manufacturer: true } }, prices: { where: { isCurrent: true, sourceDocument: { status: "VERIFIED", source: { status: "ACTIVE", sourceType: { in: [...officialSourceTypes] } }, verifications: { some: { status: "VERIFIED" } } } }, include: { sourceDocument: true }, orderBy: { amount: "asc" }, take: 1 }, specs: true, battery: true, performance: true, warranty: true } });
  const variants = unique.flatMap((id) => { const row = rows.find((item) => item.id === id); if (!row) return []; const fuel = row.specs.find((s) => ["fuelType", "fuel_type", "fuel", "เชื้อเพลิง"].includes(s.key)); const fields = { fuelType: fuel?.valueTh ?? fuel?.valueEn ?? null, price: value(row.prices[0]?.amount), rangeKm: value(row.performance?.rangeKm), batteryKwh: value(row.battery?.capacityKwh), powerKw: value(row.performance?.powerKw), warrantyYears: row.warranty?.vehicleYears ?? null }; return [{ id: row.id, name: row.nameTh, manufacturer: row.model.manufacturer.nameTh, model: row.model.nameTh, fields, provenance: row.prices.map((p) => ({ url: p.sourceDocument.canonicalUrl ?? p.sourceDocument.url, title: p.sourceDocument.titleTh ?? p.sourceDocument.titleEn })) }]; });
  return { variants, fields: specs.map((key) => ({ key, label: labels[key], values: variants.map((v) => v.fields[key]) })) };
}
