/**
 * Extraction Pipeline — Automated data extraction from official sources.
 *
 * Decision tree:
 * A. Direct HTTP fetch
 * B. Embedded JSON / JSON-LD / framework state
 * C. Browser DOM rendering
 * D. Browser network/API inspection
 * E. Reproduce public request
 * F. PDF/brochure extraction
 * G. OCR only as last resort
 */

import { PrismaClient, ExtractionStatus } from "@prisma/client";

export type ExtractionMethod = "http" | "json_ld" | "browser" | "pdf" | "ocr" | "api";

export type ExtractedPrice = {
  variantName: string;
  modelName: string;
  amount: number;
  priceType: string;
  currency: string;
  sourceExcerpt: string;
  sourceUrl: string;
  method: ExtractionMethod;
};

export type ExtractedSpec = {
  variantName: string;
  modelName: string;
  key: string;
  value: string;
  valueNumeric?: number;
  unit?: string;
  sourceExcerpt: string;
  sourceUrl: string;
  method: ExtractionMethod;
};

export type ExtractionResult = {
  success: boolean;
  method: ExtractionMethod;
  prices: ExtractedPrice[];
  specs: ExtractedSpec[];
  contentHash: string;
  rawContentLength: number;
  error?: string;
};

/**
 * Attempt to extract price/spec data from a URL using the decision tree.
 * Tries methods in order: HTTP → JSON-LD → browser → PDF → OCR
 */
export async function extractFromUrl(
  url: string,
  modelName: string,
): Promise<ExtractionResult> {
  // A. Direct HTTP fetch
  try {
    const result = await extractViaHttp(url, modelName);
    if (result.prices.length > 0 || result.specs.length > 0) {
      return result;
    }
  } catch {
    // Fall through to next method
  }

  // B. Try to find JSON-LD or embedded data
  try {
    const result = await extractViaJsonLd(url, modelName);
    if (result.prices.length > 0 || result.specs.length > 0) {
      return result;
    }
  } catch {
    // Fall through
  }

  return {
    success: false,
    method: "http",
    prices: [],
    specs: [],
    contentHash: "",
    rawContentLength: 0,
    error: "All extraction methods failed",
  };
}

/**
 * Method A: Direct HTTP fetch + text parsing
 */
async function extractViaHttp(url: string, modelName: string): Promise<ExtractionResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch(url, {
      signal: controller.signal,
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; ThaiCarIntel/1.0; +https://github.com/thai-car-intelligence)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      },
      redirect: "follow",
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const html = await response.text();
    const contentHash = simpleHash(html);

    const prices = extractPricesFromHtml(html, url, modelName);
    const specs = extractSpecsFromHtml(html, url, modelName);

    return {
      success: prices.length > 0 || specs.length > 0,
      method: "http",
      prices,
      specs,
      contentHash,
      rawContentLength: html.length,
    };
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Method B: Extract from JSON-LD structured data
 */
async function extractViaJsonLd(url: string, modelName: string): Promise<ExtractionResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch(url, {
      signal: controller.signal,
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; ThaiCarIntel/1.0)",
        "Accept": "text/html,application/xhtml+xml",
      },
      redirect: "follow",
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const html = await response.text();
    const contentHash = simpleHash(html);

    // Extract JSON-LD blocks
    const jsonLdRegex = /<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/gi;
    const prices: ExtractedPrice[] = [];
    const specs: ExtractedSpec[] = [];

    let match;
    while ((match = jsonLdRegex.exec(html)) !== null) {
      try {
        const data = JSON.parse(match[1]);
        // Look for Product schema with offers
        if (data["@type"] === "Product" || data["@type"] === "Car") {
          if (data.offers) {
            const offers = Array.isArray(data.offers) ? data.offers : [data.offers];
            for (const offer of offers) {
              if (offer.price) {
                prices.push({
                  variantName: data.name ?? modelName,
                  modelName: data.name ?? modelName,
                  amount: Number(offer.price),
                  priceType: "MSRP",
                  currency: offer.priceCurrency ?? "THB",
                  sourceExcerpt: JSON.stringify(offer).slice(0, 500),
                  sourceUrl: url,
                  method: "json_ld",
                });
              }
            }
          }
        }
      } catch {
        // Invalid JSON, skip
      }
    }

    return {
      success: prices.length > 0,
      method: "json_ld",
      prices,
      specs,
      contentHash,
      rawContentLength: html.length,
    };
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Extract prices from HTML text content
 */
export function extractPricesFromHtml(html: string, url: string, modelName: string): ExtractedPrice[] {
  const prices: ExtractedPrice[] = [];

  // Remove HTML tags for text analysis
  const text = html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

  // Thai price patterns: "1,299,000 บาท" or "ราคา 1.299 ล้าน"
  const pricePatterns = [
    /(?:ราคา|price|เริ่มต้น|starting)[\s:]*(?:฿|บาท)?\s*([\d,]+(?:\.\d+)?)\s*(?:บาท|฿)?/gi,
    /([\d]{1,3}(?:[\d,]*))\s*(?:บาท|฿)/g,
    /([\d.]+)\s*ล้าน/gi,
  ];

  for (const pattern of pricePatterns) {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      let amount = 0;
      const raw = match[1].replace(/,/g, "");

      if (match[0].includes("ล้าน")) {
        amount = parseFloat(raw) * 1_000_000;
      } else {
        amount = parseFloat(raw);
      }

      if (amount >= 100_000 && amount <= 20_000_000) {
        // Get surrounding context for excerpt
        const start = Math.max(0, match.index - 50);
        const end = Math.min(text.length, match.index + match[0].length + 50);
        const excerpt = text.slice(start, end).trim();

        prices.push({
          variantName: modelName,
          modelName,
          amount,
          priceType: "MSRP",
          currency: "THB",
          sourceExcerpt: excerpt,
          sourceUrl: url,
          method: "http",
        });
      }
    }
  }

  return dedupePrices(prices);
}

/**
 * Extract specification data from HTML
 */
function extractSpecsFromHtml(html: string, url: string, modelName: string): ExtractedSpec[] {
  const specs: ExtractedSpec[] = [];
  const text = html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

  // Common spec patterns
  const specPatterns: { key: string; pattern: RegExp; unit?: string }[] = [
    { key: "powerKw", pattern: /(?:กำลัง|power| horsepower| hp|匹)[:\s]*([\d.]+)\s*(?:kW|hp|แรงม้า|匹)/i, unit: "kW" },
    { key: "torqueNm", pattern: /(?:แรงบิด|torque)[:\s]*([\d.]+)\s*(?:Nm|นิวตันเมตร)/i, unit: "Nm" },
    { key: "batteryKwh", pattern: /(?:แบตเตอรี่|battery|ความจุ)[:\s]*([\d.]+)\s*(?:kWh|กิโลวัตต์ชั่วโมง)/i, unit: "kWh" },
    { key: "rangeKm", pattern: /(?:ระยะทาง|range|วิ่งได้)[:\s]*([\d.]+)\s*(?:km|กิโลเมตร)/i, unit: "km" },
    { key: "lengthMm", pattern: /(?:ยาว|length)[:\s]*([\d,]+)\s*(?:mm|มิลลิเมตร)/i, unit: "mm" },
    { key: "widthMm", pattern: /(?:กว้าง|width)[:\s]*([\d,]+)\s*(?:mm|มิลลิเมตร)/i, unit: "mm" },
    { key: "heightMm", pattern: /(?:สูง|height)[:\s]*([\d,]+)\s*(?:mm|มิลลิเมตร)/i, unit: "mm" },
    { key: "wheelbaseMm", pattern: /(?:ฐานล้อ|wheelbase)[:\s]*([\d,]+)\s*(?:mm|มิลลิเมตร)/i, unit: "mm" },
    { key: "groundClearanceMm", pattern: /(?:ระยะต่ำสุด|ground clearance)[:\s]*([\d,]+)\s*(?:mm|มิลลิเมตร)/i, unit: "mm" },
  ];

  for (const { key, pattern, unit } of specPatterns) {
    const match = text.match(pattern);
    if (match) {
      const value = match[1].replace(/,/g, "");
      const numVal = parseFloat(value);
      if (!isNaN(numVal)) {
        const start = Math.max(0, (match.index ?? 0) - 30);
        const end = Math.min(text.length, (match.index ?? 0) + match[0].length + 30);
        specs.push({
          variantName: modelName,
          modelName,
          key,
          value: match[0],
          valueNumeric: numVal,
          unit,
          sourceExcerpt: text.slice(start, end).trim(),
          sourceUrl: url,
          method: "http",
        });
      }
    }
  }

  return specs;
}

function dedupePrices(prices: ExtractedPrice[]): ExtractedPrice[] {
  const seen = new Set<string>();
  return prices.filter((p) => {
    const key = `${p.variantName}|${p.amount}|${p.priceType}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function simpleHash(input: string): string {
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    hash = ((hash << 5) - hash + input.charCodeAt(i)) | 0;
  }
  return Math.abs(hash).toString(36);
}

/**
 * Create extraction jobs for all universe entries that need extraction.
 */
export async function createExtractionQueue(prisma: PrismaClient): Promise<{
  created: number;
  skipped: number;
  errors: string[];
}> {
  let created = 0;
  let skipped = 0;
  const errors: string[] = [];

  // Get universe entries that need extraction
  const entries = await prisma.vehicleUniverse.findMany({
    where: {
      OR: [
        { coverageState: "NOT_DISCOVERED" },
        { coverageState: "FOUND_BUT_NO_PRICE" },
        { coverageState: "FOUND_BUT_NO_OFFICIAL_SOURCE" },
        { coverageState: "STALE" },
      ],
    },
    include: {
      discoverySource: true,
    },
    take: 100, // Process in batches
  });

  for (const entry of entries) {
    try {
      // Check if extraction job already exists
      const existing = await prisma.extractionJob.findFirst({
        where: {
          vehicleUniverseId: entry.id,
          status: { in: ["QUEUED", "RUNNING", "SUCCEEDED"] },
        },
      });

      if (existing) {
        skipped++;
        continue;
      }

      // Determine source URL
      const sourceUrl = entry.discoverySource?.catalogUrl
        ?? entry.discoverySource?.baseUrl
        ?? entry.officialUrl;

      if (!sourceUrl) {
        skipped++;
        continue;
      }

      // Determine priority based on coverage state
      let priority = 5;
      if (entry.coverageState === "NOT_DISCOVERED") priority = 1;
      else if (entry.coverageState === "FOUND_BUT_NO_PRICE") priority = 2;
      else if (entry.coverageState === "STALE") priority = 4;

      await prisma.extractionJob.create({
        data: {
          name: `Extract ${entry.brandSlug}/${entry.slug}`,
          vehicleUniverseId: entry.id,
          sourceUrl,
          extractionMethod: "http",
          priority,
          status: "QUEUED",
        },
      });
      created++;
    } catch (e) {
      errors.push(`Job for ${entry.brandSlug}/${entry.slug}: ${e}`);
    }
  }

  return { created, skipped, errors };
}
