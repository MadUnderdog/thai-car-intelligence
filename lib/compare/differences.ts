import type { ComparisonField } from "./compare";

/** Keep every row unless every compared value is present and equal. */
export function onlyDifferentFields(fields: ComparisonField[]): ComparisonField[] {
  return fields.filter((field) => {
    const [first, ...rest] = field.values;
    return rest.some((value) => value !== first);
  });
}

export function formatComparisonValue(value: string | number | null, key: string): string {
  if (value === null || value === undefined) return "ไม่มีข้อมูล";
  const formatted = typeof value === "number" ? new Intl.NumberFormat("th-TH").format(value) : value;
  if (key === "price") return `${formatted} บาท`;
  if (key === "rangeKm") return `${formatted} กม.`;
  if (key === "batteryKwh") return `${formatted} kWh`;
  if (key === "powerKw") return `${formatted} kW`;
  if (key === "warrantyYears") return `${formatted} ปี`;
  return formatted;
}
