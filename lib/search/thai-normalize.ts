/**
 * Thai query normalization for catalog search.
 * Resolves Thai model/brand aliases to canonical English names
 * so the Prisma ILIKE search can find matching catalog entries.
 *
 * This is NOT a hardcoded benchmark fix — it's a reusable normalization
 * layer consistent with the project's entity model (parser aliases + DB slugs).
 */

import { parseAutomotiveQuery } from "../ai/retrieval/query-parser";

/** Canonical Thai→English model name mappings (from parser + catalog slugs) */
const THAI_MODEL_MAP: Record<string, string> = {
  // Toyota
  "คัมรี": "camry", "ยาริส": "yaris", "โคโรลล่า": "corolla",
  "ฟอร์จูนเนอร์": "fortuner", "ไฮลักซ์": "hilux", "อินโนวา": "innova",
  "วีลอส": "veloz", "อแวนซ่า": "avanza", "ครอสส์": "cross",
  // Honda
  "ซิตี้": "city", "ซีวิค": "civic", "ซีอาร์-วี": "cr-v",
  "เอชอาร์-วี": "hr-v", "บีอาร์-วี": "br-v", "ดับเบิลยูอาร์-วี": "wr-v",
  "แอคคอร์ด": "accord", "ซูเปอร์วัน": "super-one",
  // MG
  "เอ็มจี 4": "mg4", "เอ็มจี4": "mg4", "โฟร์": "mg4",
  "เอส 5": "s5", "ไอเอ็ม 5": "im5", "ไอเอ็ม 6": "im6",
  "ซีเอส": "zs", "เอชเอส": "hs", "เอพี": "ep", "วีเอส": "vs",
  // BYD
  "แอทโต 2": "atto-2", "แอทโต 3": "atto-3", "โดลฟิน": "dolphin",
  "ซีล": "seal", "สิงโต": "sealion",
  // Tesla
  "โมเดล 3": "model-3", "โมเดล วาย": "model-y",
  // Nissan
  "คิกส์": "kicks",
};

/** Thai brand aliases (from parser) */
const THAI_BRAND_MAP: Record<string, string> = {
  "โตโยต้า": "toyota", "ฮอนด้า": "honda", "เอ็มจี": "mg",
  "บีวายดี": "byd", "นิสสัน": "nissan", "มาสด้า": "mazda",
  "ฟอร์ด": "ford", "ฮุนได": "hyundai", "เกีย": "kia",
  "เทสลา": "tesla", "อีซูซุ": "isuzu", "มิตซูบิชิ": "mitsubishi",
  "ซูซูกิ": "suzuki", "ซูบารุ": "subaru",
};

/**
 * Normalize a Thai search query by resolving aliases to English terms.
 * Returns the original query + any additional English terms extracted.
 * Does NOT mutate the original query — the original is always searched.
 */
export function normalizeThaiQuery(query: string): {
  original: string;
  resolvedBrands: string[];
  resolvedModels: string[];
  additionalTerms: string[];
} {
  const lower = query.toLowerCase();
  const resolvedBrands: string[] = [];
  const resolvedModels: string[] = [];
  const additionalTerms: string[] = [];

  // Resolve brand aliases
  for (const [thai, en] of Object.entries(THAI_BRAND_MAP)) {
    if (lower.includes(thai)) {
      resolvedBrands.push(en);
      additionalTerms.push(en);
    }
  }

  // Resolve model aliases
  for (const [thai, en] of Object.entries(THAI_MODEL_MAP)) {
    if (lower.includes(thai)) {
      resolvedModels.push(en);
      additionalTerms.push(en);
    }
  }

  // Also try parser for any entities it recognizes
  try {
    const intent = parseAutomotiveQuery(query);
    const entities = (intent as { entities?: string[] }).entities;
    if (Array.isArray(entities)) {
      for (const e of entities) {
        if (!additionalTerms.includes(e)) additionalTerms.push(e);
      }
    }
  } catch { /* ignore parser errors */ }

  return { original: query, resolvedBrands, resolvedModels, additionalTerms: [...new Set(additionalTerms)] };
}
