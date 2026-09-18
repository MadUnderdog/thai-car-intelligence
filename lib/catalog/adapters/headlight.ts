/**
 * HeadLight Magazine adapter — extracts full variant price tables from official price articles.
 */

import type { SourceAdapter, ExtractedObservation, PriceType } from "./base";
import { normalizePrice, detectPriceType } from "./base";

export const headlightAdapter: SourceAdapter = {
  name: "HeadLight Magazine",
  tier: "secondary_automotive_media",
  domain: "headlightmag.com",

  canHandle: (url: string) => url.includes("headlightmag.com"),

  fetchEvidence: async (url: string): Promise<string> => {
    const res = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0 (compatible; ThaiCarIntel/1.0)" },
    });
    return await res.text();
  },

  extractObservations: (html: string, url: string): ExtractedObservation[] => {
    const observations: ExtractedObservation[] = [];
    
    // Extract title
    const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
    const title = titleMatch ? titleMatch[1].trim() : null;
    
    // Extract all prices from the article
    const pricePattern = /(\d{1,3}(?:,\d{3})+)\s*บาท/g;
    const prices: string[] = [];
    let match;
    while ((match = pricePattern.exec(html)) !== null) {
      prices.push(match[1]);
    }
    
    // Extract variant names from heading/paragraph context
    const variantPattern = /(?:รุ่น|variant|grade)\s*[:：]?\s*([A-Za-z0-9\s\-\+\.]+)/gi;
    const variants: string[] = [];
    while ((match = variantPattern.exec(html)) !== null) {
      variants.push(match[1].trim());
    }
    
    // Try to extract structured data from HTML
    // Look for price tables or lists
    const tablePattern = /<(?:tr|li|div)[^>]*>([^<]*(?:ราคา|price)[^<]*)<\/(?:tr|li|div)>/gi;
    const tableRows: string[] = [];
    while ((match = tablePattern.exec(html)) !== null) {
      tableRows.push(match[1]);
    }
    
    // Extract model name from title or URL
    const modelFromUrl = url.split("/").pop()?.replace(/official-price-|special-price-/i, "").replace(/-/g, " ") || "";
    
    // For each price found, create an observation
    // If we have variant names, match them; otherwise use generic
    const uniquePrices = [...new Set(prices)];
    
    for (let i = 0; i < uniquePrices.length && i < 20; i++) {
      const normalized = normalizePrice(uniquePrices[i]);
      if (!normalized) continue;
      
      const variant = variants[i] || `Standard`;
      const excerpt = html.substring(
        Math.max(0, html.indexOf(uniquePrices[i]) - 100),
        Math.min(html.length, html.indexOf(uniquePrices[i]) + 100)
      ).replace(/<[^>]+>/g, " ").trim();
      
      observations.push({
        manufacturer: extractManufacturer(html, url),
        model: extractModel(html, url, title),
        variant,
        price: normalized.numeric,
        priceText: normalized.text,
        priceType: detectPriceType(excerpt),
        market: "Thailand",
        sourceExcerpt: excerpt.substring(0, 200),
        articleTitle: title,
        publicationDate: null,
      });
    }
    
    return observations;
  },
};

function extractManufacturer(html: string, url: string): string {
  const lower = (html + url).toLowerCase();
  const manufacturers = [
    "honda", "toyota", "byd", "mg", "ford", "hyundai", "nissan", "suzuki",
    "bmw", "mercedes", "lexus", "tesla", "geely", "gwm", "changan", "nio",
    "mazda", "subaru", "mitsubishi", "kia", "volvo", "zeekr", "avatr",
    "denza", "porsche", "ferrari", "bentley", "mini", "lepas",
  ];
  for (const m of manufacturers) {
    if (lower.includes(m)) return m.charAt(0).toUpperCase() + m.slice(1);
  }
  return "Unknown";
}

function extractModel(html: string, url: string, title: string | null): string {
  // Try URL path
  const urlModel = url.split("/").pop()?.replace(/official-price-|special-price-/i, "").replace(/-/g, " ") || "";
  if (urlModel.length > 3) return urlModel;
  
  // Try title
  if (title) {
    const titleModel = title.replace(/Official Price:?\s*/i, "").replace(/Special Price:?\s*/i, "").trim();
    if (titleModel.length > 2) return titleModel;
  }
  
  return "Unknown";
}
