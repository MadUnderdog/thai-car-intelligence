/**
 * Universe Seeder — Seeds the master vehicle universe into the database.
 *
 * Idempotent: re-running does not create duplicates.
 * Links discovered universe entries to existing Manufacturer/CarModel/Variant
 * records when they exist.
 */

import { PrismaClient } from "@prisma/client";
import { THAILAND_UNIVERSE, getUniverseStats } from "./universe-data";

export type SeedResult = {
  brandsProcessed: number;
  modelsProcessed: number;
  variantsProcessed: number;
  brandsCreated: number;
  modelsCreated: number;
  variantsCreated: number;
  universeEntriesCreated: number;
  universeEntriesLinked: number;
  discoverySourcesCreated: number;
  errors: string[];
};

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[aeiou]/g, "") // crude but works for brand slugs
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export async function seedUniverse(prisma: PrismaClient): Promise<SeedResult> {
  const result: SeedResult = {
    brandsProcessed: 0,
    modelsProcessed: 0,
    variantsProcessed: 0,
    brandsCreated: 0,
    modelsCreated: 0,
    variantsCreated: 0,
    universeEntriesCreated: 0,
    universeEntriesLinked: 0,
    discoverySourcesCreated: 0,
    errors: [],
  };

  for (const brand of THAILAND_UNIVERSE) {
    result.brandsProcessed++;
    try {
      // 1. Find or create Manufacturer
      let manufacturer = await prisma.manufacturer.findUnique({ where: { slug: brand.slug } });
      if (!manufacturer) {
        manufacturer = await prisma.manufacturer.create({
          data: {
            nameTh: brand.nameTh,
            nameEn: brand.nameEn,
            slug: brand.slug,
            websiteUrl: brand.websiteUrl,
            status: "ACTIVE",
          },
        });
        result.brandsCreated++;
      }

      // 2. Create DiscoverySource for the brand
      const existingSource = await prisma.discoverySource.findUnique({
        where: { baseUrl: brand.websiteUrl },
      });
      if (!existingSource) {
        await prisma.discoverySource.create({
          data: {
            manufacturerId: manufacturer.id,
            nameTh: `${brand.nameTh} — เว็บไซต์ทางการ`,
            nameEn: `${brand.nameEn} — Official Website`,
            baseUrl: brand.websiteUrl,
            catalogUrl: brand.catalogUrl ?? null,
            domain: new URL(brand.websiteUrl).hostname,
            sourceType: "OFFICIAL_MANUFACTURER",
            discoveryMethod: "manual_research",
            priority: 10,
            status: "DISCOVERED",
          },
        });
        result.discoverySourcesCreated++;
      }

      // 3. Process models
      for (const model of brand.models) {
        result.modelsProcessed++;
        try {
          // Find or create CarModel
          let carModel = await prisma.carModel.findFirst({
            where: { slug: model.slug, manufacturerId: manufacturer.id },
          });
          if (!carModel) {
            carModel = await prisma.carModel.create({
              data: {
                manufacturerId: manufacturer.id,
                nameTh: model.nameTh,
                nameEn: model.nameEn,
                slug: model.slug,
                bodyType: model.bodyType ?? null,
                segment: model.segment ?? null,
                generation: model.generation ?? null,
                status: "ACTIVE" as any,
              },
            });
            result.modelsCreated++;
          }

          // Process variants
          if (model.variants) {
            for (const variant of model.variants) {
              result.variantsProcessed++;
              try {
                let dbVariant = await prisma.variant.findFirst({
                  where: { slug: variant.slug, modelId: carModel.id },
                });
                if (!dbVariant) {
                  dbVariant = await prisma.variant.create({
                    data: {
                      modelId: carModel.id,
                      nameTh: variant.nameTh,
                      nameEn: variant.nameEn,
                      slug: variant.slug,
                      status: "ACTIVE" as any,
                    },
                  });
                  result.variantsCreated++;
                }

                // Create VehicleUniverse entry for variant
                const existingUniverse = await prisma.vehicleUniverse.findFirst({
                  where: { brandSlug: brand.slug, slug: variant.slug, modelYear: null },
                });
                if (!existingUniverse) {
                  await prisma.vehicleUniverse.create({
                    data: {
                      manufacturerId: manufacturer.id,
                      carModelId: carModel.id,
                      variantId: dbVariant.id,
                      nameTh: variant.nameTh,
                      nameEn: variant.nameEn,
                      slug: variant.slug,
                      brandSlug: brand.slug,
                      modelYear: undefined,
                      status: "ACTIVE" as any,
                      coverageState: "NOT_DISCOVERED",
                      aliases: [model.nameEn, model.nameTh, variant.nameEn, variant.nameTh],
                    },
                  });
                  result.universeEntriesCreated++;
                }
              } catch (e) {
                result.errors.push(`Variant ${brand.slug}/${model.slug}/${variant.slug}: ${e}`);
              }
            }
          }

          // Also create a universe entry for the model itself
          const existingModelUniverse = await prisma.vehicleUniverse.findFirst({
            where: { brandSlug: brand.slug, slug: model.slug, modelYear: null },
          });
          if (!existingModelUniverse) {
            await prisma.vehicleUniverse.create({
              data: {
                manufacturerId: manufacturer.id,
                carModelId: carModel.id,
                nameTh: model.nameTh,
                nameEn: model.nameEn,
                slug: model.slug,
                brandSlug: brand.slug,
                modelYear: undefined,
                status: "ACTIVE" as any,
                coverageState: "NOT_DISCOVERED",
                officialUrl: brand.catalogUrl ?? null,
                aliases: [model.nameEn, model.nameTh],
              },
            });
            result.universeEntriesCreated++;
          }
        } catch (e) {
          result.errors.push(`Model ${brand.slug}/${model.slug}: ${e}`);
        }
      }
    } catch (e) {
      result.errors.push(`Brand ${brand.slug}: ${e}`);
    }
  }

  return result;
}

/** Get universe statistics from the database */
export async function getUniverseDBStats(prisma: PrismaClient) {
  const [brands, models, variants, discoverySources, universeEntries, extractionJobs] = await Promise.all([
    prisma.manufacturer.count(),
    prisma.carModel.count(),
    prisma.variant.count(),
    prisma.discoverySource.count(),
    prisma.vehicleUniverse.count(),
    prisma.extractionJob.count(),
  ]);

  const coverageStates = await prisma.vehicleUniverse.groupBy({
    by: ["coverageState"],
    _count: { id: true },
  });

  const brandStats = await prisma.vehicleUniverse.groupBy({
    by: ["brandSlug"],
    _count: { id: true },
    orderBy: { _count: { id: "desc" } },
  });

  const fileStats = getUniverseStats();

  return {
    db: { brands, models, variants, discoverySources, universeEntries, extractionJobs },
    coverageStates: Object.fromEntries(coverageStates.map((c) => [c.coverageState, c._count.id])),
    brandCoverage: brandStats.map((b) => ({ brand: b.brandSlug, count: b._count.id })),
    fileStats,
  };
}
