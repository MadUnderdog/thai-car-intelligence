import type { CatalogPage, CatalogVariant } from "../catalog/types";

export type CompareOption = {
  id: string;
  label: string;
  detail: string;
  price: number | null;
};

export function mapCatalogToCompareOptions(page: CatalogPage): CompareOption[] {
  return page.results.map((variant) => ({
    id: variant.id,
    label: variant.nameTh,
    detail: `${variant.manufacturer.nameTh} · ${variant.model.nameTh}${variant.modelYear ? ` · ${variant.modelYear}` : ""}`,
    price: variant.prices[0]?.amount ?? null,
  }));
}

export function optionLabel(variant: CatalogVariant): string {
  return `${variant.manufacturer.nameTh} · ${variant.model.nameTh} · ${variant.nameTh}`;
}
