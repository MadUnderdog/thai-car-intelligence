/**
 * Exact Model Retrieval — fixes the root design where explicit model
 * queries return unrelated same-brand models via broad brand-level ILIKE.
 *
 * Priority order:
 * 1. Exact model identity (slug match)
 * 2. Exact alias match
 * 3. Exact variant identity
 * 4. Same-brand fallback (only when no exact match found)
 *
 * If exact model is absent, returns clear insufficient/research state.
 */

import { PrismaClient, Prisma } from "@prisma/client";

type ExactMatchResult = {
  found: boolean;
  matchType: "exact_model" | "exact_alias" | "exact_variant" | "brand_fallback" | "none";
  variants: any[];
  total: number;
};

/**
 * Attempt exact model retrieval before falling back to broad search.
 *
 * Given a query like "Honda City", this returns only Honda City variants,
 * NOT Honda CR-V, Honda Civic, etc.
 */
export async function exactModelRetrieval(
  prisma: PrismaClient,
  query: string,
  limit: number = 10,
): Promise<ExactMatchResult> {
  const normalized = query.trim().toLowerCase();

  // 1. Try exact model slug match
  const slug = normalized.replace(/\s+/g, "-");
  const exactModel = await prisma.carModel.findFirst({
    where: {
      slug,
      status: "ACTIVE",
      manufacturer: { status: "ACTIVE" },
    },
    include: {
      variants: {
        where: { status: "ACTIVE" },
        include: {
          prices: {
            where: { isCurrent: true },
            include: { sourceDocument: { include: { source: true, verifications: { where: { status: "VERIFIED" }, take: 1 } } } },
            orderBy: { amount: "asc" },
            take: 3,
          },
          aliases: { take: 5 },
        },
        orderBy: { nameEn: "asc" },
      },
      manufacturer: { select: { id: true, nameEn: true, slug: true } },
      aliases: { take: 10 },
    },
  });

  if (exactModel) {
    return {
      found: true,
      matchType: "exact_model",
      variants: exactModel.variants,
      total: exactModel.variants.length,
    };
  }

  // 2. Try alias match
  const aliasMatch = await prisma.alias.findFirst({
    where: {
      value: { contains: normalized, mode: "insensitive" },
      modelId: { not: null },
    },
    include: {
      model: {
        include: {
          variants: {
            where: { status: "ACTIVE" },
            include: {
              prices: {
                where: { isCurrent: true },
                include: { sourceDocument: { include: { source: true, verifications: { where: { status: "VERIFIED" }, take: 1 } } } },
                orderBy: { amount: "asc" },
                take: 3,
              },
            },
          },
          manufacturer: { select: { id: true, nameEn: true, slug: true } },
        },
      },
    },
  });

  if (aliasMatch?.model) {
    return {
      found: true,
      matchType: "exact_alias",
      variants: aliasMatch.model.variants,
      total: aliasMatch.model.variants.length,
    };
  }

  // 3. Try exact variant slug match
  const variantSlug = normalized.replace(/\s+/g, "-");
  const exactVariant = await prisma.variant.findFirst({
    where: {
      slug: variantSlug,
      status: "ACTIVE",
      model: { status: "ACTIVE", manufacturer: { status: "ACTIVE" } },
    },
    include: {
      model: { select: { id: true, nameEn: true, slug: true, manufacturer: { select: { id: true, nameEn: true, slug: true } } } },
      prices: {
        where: { isCurrent: true },
        include: { sourceDocument: { include: { source: true, verifications: { where: { status: "VERIFIED" }, take: 1 } } } },
        orderBy: { amount: "asc" },
        take: 3,
      },
    },
  });

  if (exactVariant) {
    return {
      found: true,
      matchType: "exact_variant",
      variants: [exactVariant],
      total: 1,
    };
  }

  // 4. No exact match — return "none" to signal insufficient data
  // Do NOT fall back to broad brand ILIKE here. The caller decides
  // whether to attempt brand-level search as a separate step.
  return {
    found: false,
    matchType: "none",
    variants: [],
    total: 0,
  };
}

/**
 * Extract brand and model tokens from a query string.
 * "Honda City 2025" → { brand: "honda", model: "city", tokens: ["city"] }
 * "BYD Atto 3" → { brand: "byd", model: "atto 3", tokens: ["atto 3"] }
 */
export function parseBrandModelQuery(query: string): {
  brand: string | null;
  model: string | null;
  tokens: string[];
} {
  const text = query.trim().toLowerCase();

  const BRANDS: Record<string, string> = {
    "toyota": "toyota", "honda": "honda", "nissan": "nissan", "mazda": "mazda",
    "mg": "mg", "byd": "byd", "ford": "ford", "chevrolet": "chevrolet",
    "mitsubishi": "mitsubishi", "suzuki": "suzuki", "isuzu": "isuzu",
    "hyundai": "hyundai", "kia": "kia", "bmw": "bmw", "mercedes-benz": "mercedes-benz",
    "mercedes": "mercedes-benz", "volvo": "volvo", "mini": "mini", "porsche": "porsche",
    "tesla": "tesla", "nio": "nio", "xpeng": "xpeng", "zeekr": "zeekr",
    "avatr": "avatr", "denza": "denza", "geely": "geely", "subaru": "subaru",
    "gwm": "gwm", "changan": "changan", "chery": "chery",
    "lexus": "lexus",
    // Thai aliases
    "โตโยต้า": "toyota", "ฮอนด้า": "honda", "นิสสัน": "nissan",
    "มาสด้า": "mazda", "เอ็มจี": "mg", "บีวายดี": "byd",
    "ฟอร์ด": "ford", "มิตซูบิชิ": "mitsubishi", "มิตซู": "mitsubishi",
    "ซูซูกิ": "suzuki", "อีซูซุ": "isuzu", "ฮุนได": "hyundai",
    "เกีย": "kia", "บีเอ็มดับบลิว": "bmw", "เมอร์เซเดส-เบนซ์": "mercedes-benz",
    "วอลโว่": "volvo", "มินิ": "mini", "ปอร์เช่": "porsche",
    "เทสลา": "tesla", "นิโอ": "nio", "เอ็กซ์เพ่ง": "xpeng",
    "ซีเคอร์": "zeekr", "อาวาทร์": "avatr", "เดนซ่า": "denza",
    "จีลี่": "geely", "ซูบารุ": "subaru", "จีดับบลิวเอ็ม": "gwm",
    "ฉางอัน": "changan", "เชอรี่": "chery", "เล็กซัส": "lexus",
  };

  let brand: string | null = null;
  let remaining = text;

  // Find brand in text
  for (const [key, value] of Object.entries(BRANDS)) {
    if (text.includes(key)) {
      brand = value;
      remaining = text.replace(key, "").trim();
      break;
    }
  }

  // Model is the remaining text after brand removal
  const model = remaining.length > 0 ? remaining : null;
  const tokens = remaining.split(/\s+/).filter((t) => t.length >= 2);

  return { brand, model, tokens };
}

/**
 * Smart catalog search that uses exact model retrieval first,
 * then falls back to brand-level search ONLY when no exact match exists.
 *
 * This fixes the root issue: "Honda City" no longer returns Honda CR-V.
 */
export async function smartCatalogSearch(
  prisma: PrismaClient,
  query: string,
  limit: number = 10,
): Promise<{
  results: any[];
  matchType: string;
  exactMatch: boolean;
}> {
  const { brand, model } = parseBrandModelQuery(query);

  // If we have both brand and model, try exact model retrieval
  if (brand && model) {
    const exactResult = await exactModelRetrieval(prisma, `${brand} ${model}`, limit);
    if (exactResult.found) {
      return {
        results: exactResult.variants,
        matchType: exactResult.matchType,
        exactMatch: true,
      };
    }

    // Try just the model name without brand
    const modelOnly = await exactModelRetrieval(prisma, model, limit);
    if (modelOnly.found) {
      // Verify the model belongs to the specified brand
      const matchingVariants = modelOnly.variants.filter((v: any) => {
        const modelBrand = v.model?.manufacturer?.slug ?? "";
        return modelBrand === brand || modelBrand.includes(brand);
      });
      if (matchingVariants.length > 0) {
        return {
          results: matchingVariants,
          matchType: "exact_model_brand_verified",
          exactMatch: true,
        };
      }
    }
  }

  // If we have just a model name without brand
  if (model && !brand) {
    const exactResult = await exactModelRetrieval(prisma, model, limit);
    if (exactResult.found) {
      return {
        results: exactResult.variants,
        matchType: exactResult.matchType,
        exactMatch: true,
      };
    }
  }

  // No exact match found — return empty with clear signal
  // The caller (evidence gate, AI Ask) should handle this as
  // "model not found in verified catalog" rather than polluting
  // evidence with unrelated same-brand models.
  return {
    results: [],
    matchType: "none",
    exactMatch: false,
  };
}
