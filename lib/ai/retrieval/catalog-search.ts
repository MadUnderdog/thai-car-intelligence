import type { CatalogPage, CatalogVariant } from "../../catalog/types";
import { searchCatalog, getCheapestVariant, getMostExpensiveVariant } from "../../catalog/queries";
import { QUESTION_SEARCH_LIMIT } from "./question-terms";
import { parseAutomotiveQuery } from "./query-parser";

const MAX_CATALOG_QUERY_LENGTH = 120;

type CatalogSearch = (filters: { q: string; limit: number; page: number; fuelType?: string; maxPrice?: number }) => Promise<CatalogPage>;

function buildSearchTerms(question: string, entities: string[]): string[] {
  const terms: string[] = [];
  if (entities.length > 0) {
    terms.push(...entities);
  }
  const text = question.toLowerCase()
    .replace(/ราคา|เท่าไหร่|เท่าไร|มี|รถ|รุ่น|ที่|ของ|ไหม|ครับ|ค่ะ|กี่|เปรียบเทียบ|เทียบ|ไม่เกิน|ต่ำกว่า|มากกว่า|under|over|compare|how|much|what|is|the|have|price/g, " ")
    .replace(/\s+/g, " ").trim();
  for (const token of text.split(" ")) {
    const t = token.trim();
    if (t.length >= 2 && !terms.includes(t)) terms.push(t);
  }
  return terms.slice(0, 6);
}

/** Deterministic fast-path for ranking queries */
async function handleRankingQuery(intent: { type: string }): Promise<CatalogVariant[]> {
  if (intent.type === "cheapest") {
    const result = await getCheapestVariant();
    return result ? [result] : [];
  }
  if (intent.type === "most_expensive") {
    const result = await getMostExpensiveVariant();
    return result ? [result] : [];
  }
  return [];
}

/** Search with structured filters first, then keyword fallback. */
export async function searchQuestionCatalog(question: string, searchFn?: CatalogSearch): Promise<CatalogVariant[]> {
  const intent = parseAutomotiveQuery(question);

  // Fast path: ranking queries go directly to DB
  if (intent.type === "cheapest" || intent.type === "most_expensive") {
    return handleRankingQuery(intent);
  }

  const found = new Map<string, CatalogVariant>();
  const addResults = (results: CatalogVariant[]) => {
    for (const result of results) found.set(result.id, result);
  };

  const searcher = searchFn ?? searchCatalog;

  // 1. Structured filter search (price, fuelType, brand)
  const structuredFilters: { fuelType?: string; maxPrice?: number } = {};
  if (intent.type === "search" && intent.filters.fuelType) structuredFilters.fuelType = intent.filters.fuelType;
  if (intent.type === "search" && intent.filters.maxPrice) structuredFilters.maxPrice = intent.filters.maxPrice;

  if (Object.keys(structuredFilters).length > 0) {
    const filtered = await searcher({ q: "", limit: QUESTION_SEARCH_LIMIT, page: 1, ...structuredFilters });
    addResults(filtered.results);
  }

  // 2. Entity-based search
  const terms = buildSearchTerms(question, intent.type === "search" ? intent.entities : []);
  for (const term of terms.slice(0, 6)) {
    const page = await searcher({ q: term.slice(0, MAX_CATALOG_QUERY_LENGTH), limit: QUESTION_SEARCH_LIMIT, page: 1 });
    addResults(page.results);
  }

  return Array.from(found.values());
}
