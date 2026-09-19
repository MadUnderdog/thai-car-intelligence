export type AutomotiveIntent =
  | { type: "search"; entities: string[]; filters: AutomotiveFilters }
  | { type: "compare"; entities: string[] }
  | { type: "count"; brand: string | null }
  | { type: "cheapest" }
  | { type: "most_expensive" }
  | { type: "unknown" };

export type AutomotiveFilters = {
  fuelType?: string;
  maxPrice?: number;
  minPrice?: number;
  brand?: string;
  feature?: string;
};

const FUEL_TYPE_MAP: Record<string, string> = {
  // Thai
  "ไฟฟ้า": "EV", "ev": "EV", "ev ": "EV", "รถไฟฟ้า": "EV",
  "ไฮบริด": "HEV", "hev": "HEV", "ไฮบริดพลัส": "HEV+",
  "ปลั๊กอินไฮบริด": "PHEV", "phev": "PHEV",
  "เบนซิน": "Petrol", "น้ำมัน": "Petrol",
  "ดีเซล": "Diesel", "ดีเซลล์": "Diesel",
};

const MODEL_ALIASES: Record<string, string> = {
  "คัมรี": "camry", "ยาริส": "yaris", "แอทโต 2": "atto-2", "แอทโต 3": "atto-3",
  "โดลฟิน": "dolphin", "ซีล": "seal", "สิงโต": "sealion 7", "เอ็มจี 4": "mg4",
};

const BRAND_ALIASES: Record<string, string> = {
  "toyota": "toyota", "โตโยต้า": "toyota", "toy": "toyota",
  "honda": "honda", "ฮอนด้า": "honda",
  "mg": "mg", "เอ็มจี": "mg",
  "byd": "byd", "บีวายดี": "byd", "บีวายดี ออโต้": "byd",
  "nissan": "nissan", "นิสสัน": "nissan",
  "mazda": "mazda", "มาสด้า": "mazda",
  "ford": "ford", "ฟอร์ด": "ford",
  "mitsubishi": "mitsubishi", "มิตซูบิชิ": "mitsubishi", "มิตซู": "mitsubishi",
  "isuzu": "isuzu", "อีซูซุ": "isuzu",
  "suzuki": "suzuki", "ซูซูกิ": "suzuki",
  "hyundai": "hyundai", "ฮุนได": "hyundai",
  "kia": "kia", "เกีย": "kia",
  "tesla": "tesla", "เทสลา": "tesla",
};

function parseThaiNumber(text: string): number | undefined {
  // ไม่เกิน 800,000 → 800000
  // ต่ำกว่า 1,000,000 → 1000000
  // ราคา 7 แสน → 700000
  const cleaned = text.replace(/[,\s]/g, "");
  const numMatch = cleaned.match(/(\d+)/);
  if (!numMatch) {
    // Thai word numbers
    const wordMatch = text.match(/(\d+)\s*(แสน|หมื่น|ล้าน)/);
    if (wordMatch) {
      const n = parseInt(wordMatch[1]);
      if (wordMatch[2] === "แสน") return n * 100000;
      if (wordMatch[2] === "หมื่น") return n * 10000;
      if (wordMatch[2] === "ล้าน") return n * 1000000;
    }
    return undefined;
  }
  return parseInt(numMatch[1]);
}

function extractFuelType(text: string): string | undefined {
  const lower = text.toLowerCase();
  const sorted = Object.entries(FUEL_TYPE_MAP).sort((a, b) => b[0].length - a[0].length);
  for (const [key, value] of sorted) {
    // Word boundary check: "hev" should match before "ev" inside it
    const idx = lower.indexOf(key);
    if (idx >= 0) {
      const before = idx === 0 || /\s/.test(lower[idx - 1]);
      const after = idx + key.length >= lower.length || /\s/.test(lower[idx + key.length]);
      if (before && after) return value;
    }
  }
  return undefined;
}

function extractBrand(text: string): string | undefined {
  const lower = text.toLowerCase();
  for (const [key, value] of Object.entries(BRAND_ALIASES)) {
    if (lower.includes(key)) return value;
  }
  return undefined;
}

function extractPriceFilter(text: string): { maxPrice?: number; minPrice?: number } {
  // "ไม่เกิน 800,000", "ต่ำกว่า 1 ล้าน", "ราคาไม่เกิน 8 แสน"
  if (/ไม่เกิน|ต่ำกว่า|น้อยกว่า|under|below|less than/i.test(text)) {
    const price = parseThaiNumber(text);
    if (price) return { maxPrice: price };
  }
  // "มากกว่า 1,000,000", "over 1 million"
  if (/มากกว่า|เกิน|over|above|more than/i.test(text)) {
    const price = parseThaiNumber(text);
    if (price) return { minPrice: price };
  }
  // Bare number with price context
  if (/ราคา|บาท|price/i.test(text)) {
    const price = parseThaiNumber(text);
    if (price && price > 10000) return { maxPrice: price };
  }
  return {};
}

function extractEntities(text: string): string[] {
  const entities: string[] = [];
  // Known model names from DB (hardcoded common ones for fast lookup)
  const knownModels = [
    "camry", "yaris", "corolla altis", "fortuner", "hilux", "innova", "veloz", "avanza",
    "civic", "city", "hr-v", "cr-v", "accord", "super-one",
    "s5 ev", "mg4", "zs ev", "urban", "vs hev", "ep plus", "es",
    "atto 2", "atto 3", "dolphin", "seal", "sealion 7",
    "almera", "kicks", "x-trail", "terra",
    "mazda2", "mazda3", "cx-3", "cx-30", "cx-5", "cx-80",
    "ranger", "everest", "territory",
    "mirage", "attrage", "xpander", "triton", "pajero",
    "d-max", "mu-x",
    "swift", "celerio", "ertiga", "jimny",
    "stargazer", "tucson", "ioniq 5", "ioniq 6", "staria", "คัมรี", "ยาริส", "โดลฟิน", "ซีล", "สิงโต", "แอทโต",
    "sonet", "stonic", "sportage", "ev6", "ev9",
    "model 3", "model y", "im5", "im6",
  ];
  const lower = text.toLowerCase();
  for (const model of knownModels) {
    // Word-boundary match: check that model is not a substring of a larger word.
    // E.g. "es" must not match inside "tesla", "seal", etc.
    const idx = lower.indexOf(model);
    if (idx < 0) continue;
    const beforeOk = idx === 0 || /[\s,()\-]/.test(lower[idx - 1]);
    const afterIdx = idx + model.length;
    const afterOk = afterIdx >= lower.length || /[\s,()\-]/.test(lower[afterIdx]);
    if (beforeOk && afterOk) entities.push(model);
  }
  // Resolve Thai model names to English
  const thaiToEn: Record<string, string> = {
    "คัมรี": "camry", "ยาริส": "yaris", "โดลฟิน": "dolphin",
    "ซีล": "seal", "สิงโต": "sealion 7", "แอทโต": "atto",
  };
  return entities.map((e) => thaiToEn[e] ?? e);
}

/** Parse a natural language automotive question into structured intent and filters. */
export function parseAutomotiveQuery(question: string): AutomotiveIntent {
  const text = question.trim();

  // Detect comparison intent
  if (/เทียบ|เปรียบเทียบ|compare|vs\.?|versus/i.test(text)) {
    return { type: "compare", entities: extractEntities(text) };
  }

  // Detect count intent
  const brand = extractBrand(text);
  if (/มีกี่|กี่รุ่น|how many|มีกี่รุ่น/i.test(text) && brand) {
    return { type: "count", brand };
  }

  // Detect cheapest/most expensive
  if (/ถูกที่สุด|ราคาถูกที่สุด|ถูกสุด|cheapest|least expensive/i.test(text)) {
    return { type: "cheapest" };
  }
  if (/แพงที่สุด|ราคาแพงที่สุด|แพงสุด|most expensive|most costly/i.test(text)) {
    return { type: "most_expensive" as const };
  }

  // Default: search with filters
  const filters: AutomotiveFilters = {};
  const fuelType = extractFuelType(text);
  if (fuelType) filters.fuelType = fuelType;
  const price = extractPriceFilter(text);
  if (price.maxPrice) filters.maxPrice = price.maxPrice;
  if (price.minPrice) filters.minPrice = price.minPrice;
  const extractedBrand = extractBrand(text);
  if (extractedBrand) filters.brand = extractedBrand;

  return { type: "search", entities: extractEntities(text), filters };
}
