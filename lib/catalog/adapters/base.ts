/**
 * Base SourceAdapter interface and shared extraction utilities.
 * 
 * One page with 12 variants → 12 observations.
 * Each adapter returns raw extracted text; shared normalizer handles pricing.
 */

export type SourceTier =
  | "primary_official"           // Direct manufacturer website
  | "secondary_automotive_media" // HeadLight, AutoLife, AutoSpinn
  | "secondary_automotive_reference" // 9CARTHAI, One2car
  | "tertiary_listing"           // Classifieds, forums
  | "unknown";

export type PriceType =
  | "manufacturer_msrp_reported"  // "ราคาอย่างเป็นทางการ" / "official price"
  | "launch_price"                // "ราคาเปิดตัว"
  | "starting_price"              // "ราคาเริ่มต้น"
  | "campaign_price"              // "ราคาโปรโมชั่น" / "ราคาพิเศษ"
  | "after_discount"              // "หลังหักส่วนลด"
  | "unknown";

export type ExtractedObservation = {
  manufacturer: string;
  model: string;
  variant: string;
  price: number;
  priceText: string;
  priceType: PriceType;
  market: string;
  sourceExcerpt: string;
  articleTitle: string | null;
  publicationDate: string | null;
};

export type SourceAdapter = {
  name: string;
  tier: SourceTier;
  domain: string;
  
  /** Can this adapter handle the given URL? */
  canHandle: (url: string) => boolean;
  
  /** Fetch the page and extract raw content */
  fetchEvidence: (url: string) => Promise<string>;
  
  /** Parse raw content into observations (one page → many rows) */
  extractObservations: (rawContent: string, url: string) => ExtractedObservation[];
};

/**
 * Normalize price text to numeric value.
 * Handles: "1,299,000", "1299000", "1,299,000 บาท", "1.299 ล้าน"
 */
export function normalizePrice(raw: string): { numeric: number; text: string } | null {
  // Remove "บาท", "฿", commas, spaces
  let cleaned = raw.replace(/บาท|฿|\s/g, "").replace(/,/g, "");
  
  // Handle "ล้าน" (million)
  const millionMatch = cleaned.match(/([\d.]+)\s*ล้าน/);
  if (millionMatch) {
    const num = parseFloat(millionMatch[1]) * 1000000;
    if (!isNaN(num) && num > 100000) {
      return { numeric: num, text: raw.trim() };
    }
  }
  
  // Standard numeric extraction
  const numMatch = cleaned.match(/([\d]{1,3}(?:[\d,]*))([\d]{3})/);
  if (numMatch) {
    const num = parseInt(numMatch[1].replace(/,/g, "") + numMatch[2]);
    if (!isNaN(num) && num > 100000) {
      return { numeric: num, text: raw.trim() };
    }
  }
  
  // Fallback: just digits
  const fallback = cleaned.match(/(\d{5,})/);
  if (fallback) {
    const num = parseInt(fallback[1]);
    if (!isNaN(num) && num > 100000) {
      return { numeric: num, text: raw.trim() };
    }
  }
  
  return null;
}

/**
 * Detect price type from Thai text context.
 */
export function detectPriceType(text: string): PriceType {
  if (/อย่างเป็นทางการ|official price|ราคาจำหน่าย/.test(text)) return "manufacturer_msrp_reported";
  if (/เปิดตัว|launch/.test(text)) return "launch_price";
  if (/เริ่มต้น|starting/.test(text)) return "starting_price";
  if (/โปรโมชั่น|พิเศษ|campaign|ลด|discount/.test(text)) return "campaign_price";
  if (/หลังหักส่วนลด|after discount/.test(text)) return "after_discount";
  return "unknown";
}

/**
 * Content hash for deduplication.
 */
export function contentHash(url: string, model: string, variant: string, price: number): string {
  const input = `${url}|${model}|${variant}|${price}`;
  // Simple deterministic hash (not crypto, just for dedup)
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    const char = input.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0;
  }
  return `h${Math.abs(hash).toString(36)}`;
}
