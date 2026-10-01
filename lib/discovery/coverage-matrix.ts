/**
 * Coverage Matrix — Machine-readable report of data completeness.
 *
 * Returns per-brand, per-model, per-variant coverage with gap states,
 * extraction status, freshness, and next-action recommendations.
 */

import { PrismaClient, Prisma } from "@prisma/client";

export type CoverageGapState =
  | "NOT_DISCOVERED"
  | "FOUND_BUT_NO_PRICE"
  | "FOUND_BUT_NO_OFFICIAL_SOURCE"
  | "PRICE_ONLY"
  | "PARTIAL_SPECS"
  | "FULL_SPECS_UNVERIFIED"
  | "VERIFIED"
  | "STALE"
  | "CONFLICT"
  | "EXTRACTION_FAILED"
  | "NOT_APPLICABLE";

export type BrandCoverage = {
  brand: string;
  brandSlug: string;
  modelsDiscovered: number;
  modelsVerified: number;
  variantsDiscovered: number;
  variantsVerified: number;
  priceCoverage: number;     // percentage
  specCoverage: number;      // percentage
  fullyVerified: number;
  researchOnly: number;
  missingSources: number;
  extractionFailures: number;
  staleSources: number;
  unresolvedConflicts: number;
};

export type CoverageMatrix = {
  timestamp: string;
  totals: {
    brands: number;
    models: number;
    variants: number;
    activeModels: number;
    upcomingModels: number;
    discontinuedModels: number;
    officialSourceDocuments: number;
    researchObservations: number;
    verifiedPrices: number;
    priceCoveragePercent: number;
    fullyVerifiedVariants: number;
    researchOnlyVariants: number;
    extractionFailures: number;
    staleSources: number;
    unresolvedConflicts: number;
  };
  byBrand: BrandCoverage[];
  gapDistribution: Record<CoverageGapState, number>;
  nextActions: { priority: number; action: string; target: string }[];
};

export async function computeCoverageMatrix(prisma: PrismaClient): Promise<CoverageMatrix> {
  // 1. Universe totals
  const [totalBrands, totalModels, totalVariants] = await Promise.all([
    prisma.manufacturer.count({ where: { status: "ACTIVE" } }),
    prisma.carModel.count({ where: { status: "ACTIVE" } }),
    prisma.variant.count({ where: { status: "ACTIVE" } }),
  ]);

  // 2. Universe entries by brand
  const universeByBrand = await prisma.vehicleUniverse.groupBy({
    by: ["brandSlug"],
    _count: { id: true },
    orderBy: { _count: { id: "desc" } },
  });

  // 3. Gap distribution
  const gapDist = await prisma.vehicleUniverse.groupBy({
    by: ["coverageState"],
    _count: { id: true },
  });
  const gapDistribution: Record<string, number> = {};
  for (const g of gapDist) {
    gapDistribution[g.coverageState] = g._count.id;
  }

  // 4. Per-brand coverage
  const brands = await prisma.manufacturer.findMany({
    where: { status: "ACTIVE" },
    include: {
      models: {
        where: { status: "ACTIVE" },
        include: {
          variants: {
            where: { status: "ACTIVE" },
            include: {
              prices: { where: { isCurrent: true }, select: { id: true } },
              specs: { select: { id: true } },
              dimensions: { select: { id: true } },
              performance: { select: { id: true } },
              battery: { select: { id: true } },
              charging: { select: { id: true } },
              safety: { select: { id: true } },
              warranty: { select: { id: true } },
            },
          },
        },
      },
    },
  });

  const byBrand: BrandCoverage[] = brands.map((brand) => {
    const modelsDiscovered = brand.models.length;
    const variants = brand.models.flatMap((m) => m.variants);
    const variantsDiscovered = variants.length;

    const variantsWithPrice = variants.filter((v) => v.prices.length > 0).length;
    const variantsWithSpecs = variants.filter(
      (v) => v.specs.length > 0 || v.dimensions || v.performance || v.battery || v.charging || v.safety || v.warranty,
    ).length;

    return {
      brand: brand.nameEn,
      brandSlug: brand.slug,
      modelsDiscovered,
      modelsVerified: 0, // Requires official verification
      variantsDiscovered,
      variantsVerified: 0,
      priceCoverage: variantsDiscovered > 0 ? Math.round((variantsWithPrice / variantsDiscovered) * 100) : 0,
      specCoverage: variantsDiscovered > 0 ? Math.round((variantsWithSpecs / variantsDiscovered) * 100) : 0,
      fullyVerified: 0,
      researchOnly: variantsDiscovered - variantsWithPrice,
      missingSources: 0,
      extractionFailures: 0,
      staleSources: 0,
      unresolvedConflicts: 0,
    };
  });

  // 5. Source/document counts
  const [officialDocs, researchCandidates, verifiedPrices, staleSources] = await Promise.all([
    prisma.sourceDocument.count({
      where: { source: { sourceType: { in: ["OFFICIAL_MANUFACTURER", "OFFICIAL_MANUFACTURER_BROCHURE", "OFFICIAL_MANUFACTURER_PRICE_LIST", "OFFICIAL_MANUFACTURER_PRESS_RELEASE"] } } },
    }),
    prisma.researchCandidate.count({ where: { status: "PENDING" } }),
    prisma.price.count({ where: { isCurrent: true, sourceDocument: { status: "VERIFIED" } } }),
    prisma.sourceDocument.count({ where: { fetchedAt: { lt: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000) } } }),
  ]);

  // 6. Next actions
  const nextActions: { priority: number; action: string; target: string }[] = [];

  // Priority 1: Brand/model with no official source
  const noSource = await prisma.vehicleUniverse.findMany({
    where: { discoverySourceId: null },
    take: 10,
    select: { brandSlug: true, slug: true, nameEn: true },
  });
  for (const e of noSource) {
    nextActions.push({ priority: 1, action: "NO_OFFICIAL_SOURCE", target: `${e.brandSlug}/${e.slug}` });
  }

  // Priority 2: Missing price
  const noPrice = await prisma.vehicleUniverse.findMany({
    where: { coverageState: "FOUND_BUT_NO_PRICE" },
    take: 10,
    select: { brandSlug: true, slug: true, nameEn: true },
  });
  for (const e of noPrice) {
    nextActions.push({ priority: 2, action: "MISSING_PRICE", target: `${e.brandSlug}/${e.slug}` });
  }

  // Priority 4: Stale sources
  const stale = await prisma.vehicleUniverse.findMany({
    where: { coverageState: "STALE" },
    take: 10,
    select: { brandSlug: true, slug: true, nameEn: true },
  });
  for (const e of stale) {
    nextActions.push({ priority: 4, action: "STALE_SOURCE", target: `${e.brandSlug}/${e.slug}` });
  }

  const priceCoveragePercent = totalVariants > 0
    ? Math.round((verifiedPrices / totalVariants) * 100)
    : 0;

  return {
    timestamp: new Date().toISOString(),
    totals: {
      brands: totalBrands,
      models: totalModels,
      variants: totalVariants,
      activeModels: totalModels,
      upcomingModels: 0,
      discontinuedModels: 0,
      officialSourceDocuments: officialDocs,
      researchObservations: researchCandidates,
      verifiedPrices,
      priceCoveragePercent,
      fullyVerifiedVariants: 0,
      researchOnlyVariants: totalVariants - verifiedPrices,
      extractionFailures: 0,
      staleSources,
      unresolvedConflicts: 0,
    },
    byBrand,
    gapDistribution: gapDistribution as Record<CoverageGapState, number>,
    nextActions: nextActions.sort((a, b) => a.priority - b.priority),
  };
}
