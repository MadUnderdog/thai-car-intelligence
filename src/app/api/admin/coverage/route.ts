import { NextResponse } from "next/server";
import { z } from "zod";
import { db } from "../../../../../lib/db";
import { Prisma } from "@prisma/client";

export const dynamic = "force-dynamic";

const querySchema = z.object({ brand: z.string().trim().optional() });

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const filters = querySchema.safeParse(Object.fromEntries(params));
  if (!filters.success) return NextResponse.json({ error: "invalid" }, { status: 400 });

  try {
    const where: Prisma.CarModelWhereInput = { status: "ACTIVE", manufacturer: { status: "ACTIVE" } };
    if (filters.data.brand) where.manufacturer = { ...where.manufacturer as Prisma.ManufacturerWhereInput, slug: { contains: filters.data.brand, mode: "insensitive" } };

    const models = await db.carModel.findMany({
      where,
      include: {
        manufacturer: { select: { nameEn: true, slug: true } },
        variants: {
          where: { status: "ACTIVE" },
          include: {
            prices: { where: { isCurrent: true }, select: { id: true } },
            specs: { select: { id: true } },
            media: { select: { id: true } },
            features: { select: { variantId: true } },
          },
        },
      },
      orderBy: { nameEn: "asc" },
    });

    const results = models.map((model) => {
      const variants = model.variants;
      const totalVariants = variants.length;
      const variantsWithPrice = variants.filter((v) => v.prices.length > 0).length;
      const variantsWithSpec = variants.filter((v) => v.specs.length > 0).length;
      const variantsWithImage = variants.filter((v) => v.media.length > 0).length;
      const variantsWithFeature = variants.filter((v) => v.features.length > 0).length;

      return {
        manufacturer: model.manufacturer.nameEn,
        manufacturerSlug: model.manufacturer.slug,
        model: model.nameEn,
        slug: model.slug,
        totalVariants,
        withPrice: variantsWithPrice,
        withSpec: variantsWithSpec,
        withImage: variantsWithImage,
        withFeature: variantsWithFeature,
        pricePct: totalVariants > 0 ? Math.round((variantsWithPrice / totalVariants) * 100) : 0,
        specPct: totalVariants > 0 ? Math.round((variantsWithSpec / totalVariants) * 100) : 0,
        imagePct: totalVariants > 0 ? Math.round((variantsWithImage / totalVariants) * 100) : 0,
        featurePct: totalVariants > 0 ? Math.round((variantsWithFeature / totalVariants) * 100) : 0,
        overallPct: totalVariants > 0 ? Math.round(((variantsWithPrice + variantsWithSpec + variantsWithImage + variantsWithFeature) / (totalVariants * 4)) * 100) : 0,
      };
    });

    return NextResponse.json({ models: results, total: results.length });
  } catch {
    return NextResponse.json({ error: "database_unavailable", models: [], total: 0 }, { status: 503 });
  }
}
