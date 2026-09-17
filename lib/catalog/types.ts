export type SourceProvenance = {
  id: string;
  url: string;
  titleTh: string | null;
  titleEn: string | null;
  documentStatus: string;
  verificationStatus: string | null;
  verifiedAt: string | null;
  source: {
    id: string;
    nameTh: string;
    nameEn: string;
    type: string;
    domain: string;
  };
};

export type CatalogPrice = {
  amount: number;
  currency: string;
  type: string;
  validFrom: string;
  validTo: string | null;
  observedAt: string;
  source: SourceProvenance;
};

export type CatalogManufacturer = {
  id: string;
  nameTh: string;
  nameEn: string;
  slug: string;
};

export type CatalogModel = CatalogManufacturer & {
  manufacturer: CatalogManufacturer;
  modelYear: number | null;
};

export type CatalogVariant = {
  id: string;
  nameTh: string;
  nameEn: string;
  slug: string;
  modelYear: number | null;
  manufacturer: CatalogManufacturer;
  model: { id: string; nameTh: string; nameEn: string; slug: string; modelYear: number | null };
  fuelType: string | null;
  aliases?: string[];
  prices: CatalogPrice[];
};

export type CatalogFilters = {
  manufacturer?: string;
  model?: string;
  fuelType?: string;
  maxPrice?: number;
  q?: string;
  page?: number;
  limit?: number;
};

export type CatalogPage = {
  results: CatalogVariant[];
  total: number;
  page: number;
  limit: number;
  hasMore: boolean;
};

export type CatalogModelDetail = {
  id: string;
  nameTh: string;
  nameEn: string;
  slug: string;
  modelYear: number | null;
  manufacturer: CatalogManufacturer;
  variants: CatalogVariant[];
};
