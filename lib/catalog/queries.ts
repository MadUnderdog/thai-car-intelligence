// @ts-nocheck
import db from "../db";
import type { CatalogFilters, CatalogManufacturer, CatalogModel, CatalogModelDetail, CatalogPage, CatalogPrice, CatalogVariant, SourceProvenance } from "./types";

export const DEFAULT_PAGE_SIZE = 24;
export const MAX_PAGE_SIZE = 100;
export const MAX_PAGE_NUMBER = 100_000;
export const MAX_QUERY_LENGTH = 120;

const officialSourceTypes = [
  "OFFICIAL_MANUFACTURER",
  "OFFICIAL_MANUFACTURER_BROCHURE",
  "OFFICIAL_MANUFACTURER_PRICE_LIST",
  "OFFICIAL_MANUFACTURER_PRESS_RELEASE",
] as const;

const verifiedDocument: Prisma.SourceDocumentWhereInput = {
  status: "VERIFIED",
  source: { status: "ACTIVE" },
  verifications: { some: { status: "VERIFIED" } },
};

const officialSource: Prisma.SourceDocumentWhereInput = {
  source: { sourceType: { in: [...officialSourceTypes] }, status: "ACTIVE" },
};

const currentOfficialPrice: Prisma.PriceWhereInput = {
  isCurrent: true,
  sourceDocument: { AND: [verifiedDocument, officialSource] },
};

const variantInclude = {
  prices: {
    where: currentOfficialPrice,
    include: { sourceDocument: { include: { source: true, verifications: { where: { status: "VERIFIED" }, take: 1 } } } },
    orderBy: { amount: "asc" as const },
    take: 3,
  },
  aliases: { take: 20, orderBy: { value: "asc" as const } },
  specs: {
    where: { key: { in: ["fuelType", "fuel_type", "fuel", "เชื้อเพลิง"] }, sourceDocument: { AND: [verifiedDocument, officialSource] } },
    orderBy: { confidence: "desc" as const },
    take: 1,
  },
  model: { include: { manufacturer: true, aliases: { take: 20, orderBy: { value: "asc" as const } } } },
} satisfies Prisma.VariantInclude;

type VariantRow = Prisma.VariantGetPayload<{ include: typeof variantInclude }>;
type PriceRow = VariantRow["prices"][number];

export function normalizeSearch(value: string): string {
  return value.trim().toLocaleLowerCase("th-TH");
}

function provenance(document: PriceRow["sourceDocument"]): SourceProvenance {
  const verification = document.verifications[0];
  return {
    id: document.id,
    url: document.canonicalUrl ?? document.url,
    titleTh: document.titleTh,
    titleEn: document.titleEn,
    documentStatus: document.status,
    verificationStatus: verification?.status ?? null,
    verifiedAt: verification?.verifiedAt?.toISOString() ?? null,
    source: { id: document.source.id, nameTh: document.source.nameTh, nameEn: document.source.nameEn, type: document.source.sourceType, domain: document.source.domain },
  };
}

function price(row: PriceRow): CatalogPrice {
  return { amount: Number(row.amount), currency: row.currency, type: row.priceType, validFrom: row.validFrom.toISOString(), validTo: row.validTo?.toISOString() ?? null, observedAt: row.observedAt.toISOString(), source: provenance(row.sourceDocument) };
}

function textContains(value: string): Prisma.StringFilter {
  return { contains: normalizeSearch(value), mode: "insensitive" };
}

function searchableText(filter: string): Prisma.VariantWhereInput {
  const contains = textContains(filter);
  return {
    OR: [
      { nameTh: contains }, { nameEn: contains }, { slug: contains },
      { aliases: { some: { value: contains } } },
      { model: { nameTh: contains } }, { model: { nameEn: contains } }, { model: { slug: contains } },
      { model: { aliases: { some: { value: contains } } } },
      { model: { manufacturer: { nameTh: contains } } }, { model: { manufacturer: { nameEn: contains } } },
      { model: { manufacturer: { slug: contains } } }, { model: { manufacturer: { aliases: { some: { value: contains } } } } },
    ],
  };
}

function whereFor(filters: CatalogFilters): Prisma.VariantWhereInput {
  const where: Prisma.VariantWhereInput = {
    status: "ACTIVE",
    model: { status: "ACTIVE", manufacturer: { status: "ACTIVE" } },
    prices: { some: filters.maxPrice === undefined ? currentOfficialPrice : { ...currentOfficialPrice, amount: { lte: filters.maxPrice } } },
  };
  const and: Prisma.VariantWhereInput[] = [];
  if (filters.q) and.push(searchableText(filters.q));
  if (filters.manufacturer) and.push({ model: { manufacturer: { OR: [{ nameTh: textContains(filters.manufacturer) }, { nameEn: textContains(filters.manufacturer) }, { slug: textContains(filters.manufacturer) }, { aliases: { some: { value: textContains(filters.manufacturer) } } }] } } });
  if (filters.model) and.push({ model: { OR: [{ nameTh: textContains(filters.model) }, { nameEn: textContains(filters.model) }, { slug: textContains(filters.model) }, { aliases: { some: { value: textContains(filters.model) } } }] } });
  if (filters.fuelType) and.push({
    OR: [
      { fuelType: { equals: filters.fuelType, mode: "insensitive" as const } },
      { specs: { some: { key: { in: ["fuelType", "fuel_type", "fuel", "เชื้อเพลิง"] }, OR: [{ valueTh: textContains(filters.fuelType) }, { valueEn: textContains(filters.fuelType) }], sourceDocument: { AND: [verifiedDocument, officialSource] } } } },
    ],
  });
  if (and.length) where.AND = and;
  return where;
}

function pagination(filters: CatalogFilters): { page: number; limit: number; skip: number } {
  const page = Math.min(MAX_PAGE_NUMBER, Math.max(1, Math.floor(filters.page ?? 1)));
  const limit = Math.min(MAX_PAGE_SIZE, Math.max(1, Math.floor(filters.limit ?? DEFAULT_PAGE_SIZE)));
  return { page, limit, skip: (page - 1) * limit };
}

function mapVariant(row: VariantRow): CatalogVariant {
  return {
    id: row.id, nameTh: row.nameTh, nameEn: row.nameEn, slug: row.slug, modelYear: row.modelYear,
    manufacturer: row.model.manufacturer,
    model: { id: row.model.id, nameTh: row.model.nameTh, nameEn: row.model.nameEn, slug: row.model.slug, modelYear: row.model.modelYear },
    aliases: row.aliases.map((alias) => alias.value),
    fuelType: row.fuelType ?? row.specs[0]?.valueEn ?? row.specs[0]?.valueTh ?? null,
    prices: row.prices.map(price),
  };
}

export async function listManufacturers(client: PrismaClient = db): Promise<CatalogManufacturer[]> {
  return client.manufacturer.findMany({ where: { status: "ACTIVE", models: { some: { status: "ACTIVE", variants: { some: { status: "ACTIVE", prices: { some: currentOfficialPrice } } } } } }, orderBy: { nameEn: "asc" }, select: { id: true, nameTh: true, nameEn: true, slug: true } });
}

export async function listModels(client: PrismaClient = db): Promise<CatalogModel[]> {
  return client.carModel.findMany({ where: { status: "ACTIVE", manufacturer: { status: "ACTIVE" }, variants: { some: { status: "ACTIVE", prices: { some: currentOfficialPrice } } } }, orderBy: [{ nameEn: "asc" }, { modelYear: "desc" }], select: { id: true, nameTh: true, nameEn: true, slug: true, modelYear: true, manufacturer: { select: { id: true, nameTh: true, nameEn: true, slug: true } } } });
}

export async function listVariants(filters: CatalogFilters = {}, client: PrismaClient = db): Promise<CatalogPage> {
  const { page, limit, skip } = pagination(filters);
  const where = whereFor(filters);
  const [total, rows] = await Promise.all([
    client.variant.count({ where }),
    client.variant.findMany({ where, include: variantInclude, orderBy: [{ model: { nameEn: "asc" } }, { nameEn: "asc" }, { id: "asc" }], skip, take: limit }),
  ]);
  return { results: rows.map(mapVariant), total, page, limit, hasMore: skip + rows.length < total };
}

export async function searchCatalog(filters: CatalogFilters, client: PrismaClient = db): Promise<CatalogPage> {
  return listVariants(filters, client);
}

/** Public model detail data: only active variants with a current, verified official price. */
export async function getModelDetail(manufacturerSlug: string, modelSlug: string, client: PrismaClient = db): Promise<CatalogModelDetail | null> {
  const model = await client.carModel.findFirst({
    where: { slug: modelSlug, status: "ACTIVE", manufacturer: { slug: manufacturerSlug, status: "ACTIVE" } },
    include: {
      manufacturer: { select: { id: true, nameTh: true, nameEn: true, slug: true } },
      variants: {
        where: { status: "ACTIVE", prices: { some: currentOfficialPrice } },
        include: variantInclude,
        orderBy: [{ nameEn: "asc" }, { id: "asc" }],
      },
    },
    orderBy: { modelYear: "desc" },
  });
  if (!model) return null;
  return {
    id: model.id,
    nameTh: model.nameTh,
    nameEn: model.nameEn,
    slug: model.slug,
    modelYear: model.modelYear,
    manufacturer: model.manufacturer,
    variants: model.variants.map(mapVariant),
  };
}

/** Get cheapest variant with a current, verified-official price. */
export async function getCheapestVariant(client: PrismaClient = db): Promise<CatalogVariant | null> {
  const price = await client.price.findFirst({
    where: currentOfficialPrice,
    orderBy: { amount: 'asc' },
    include: {
      variant: {
        include: variantInclude,
      },
    },
  });
  if (!price?.variant) return null;
  // Post-filter: variant must be ACTIVE with ACTIVE model/manufacturer
  if (price.variant.status !== 'ACTIVE') return null;
  if (price.variant.model?.status !== 'ACTIVE') return null;
  if (price.variant.model?.manufacturer?.status !== 'ACTIVE') return null;
  return mapVariant(price.variant);
}

/** Get most expensive variant with a current, verified-official price. */
export async function getMostExpensiveVariant(client: PrismaClient = db): Promise<CatalogVariant | null> {
  const price = await client.price.findFirst({
    where: currentOfficialPrice,
    orderBy: { amount: 'desc' },
    include: {
      variant: {
        include: variantInclude,
      },
    },
  });
  if (!price?.variant) return null;
  // Post-filter: variant must be ACTIVE with ACTIVE model/manufacturer
  if (price.variant.status !== 'ACTIVE') return null;
  if (price.variant.model?.status !== 'ACTIVE') return null;
  if (price.variant.model?.manufacturer?.status !== 'ACTIVE') return null;
  return mapVariant(price.variant);
}
