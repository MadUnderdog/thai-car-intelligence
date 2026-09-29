/**
 * P116 — compare UI helpers: truthful error messages + three-state features.
 * Feature cells: ✓ installed · ✗ explicitly not installed · ไม่มีข้อมูล unknown
 * (no row at all for that variant — never guessed as "not installed").
 */

export function compareErrorMessage(code: string | null | undefined): string {
  if (code === "need_at_least_2") return "กรุณาเลือกรถอย่างน้อย 2 รุ่น";
  if (code === "variants_not_found") return "ไม่พบรถที่เลือก";
  if (code === "invalid_ids") return "รายการที่เลือกไม่ถูกต้อง";
  return "ไม่สามารถโหลดข้อมูลได้";
}

export function featureCellText(features: { slug: string; available?: boolean }[], slug: string): string {
  const row = features.find((f) => f.slug === slug);
  if (!row) return "ไม่มีข้อมูล";
  return row.available === true ? "✓" : "✗";
}
