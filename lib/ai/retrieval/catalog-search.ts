import type { CatalogPage, CatalogVariant } from "../../catalog/types";
import { searchCatalog, getCheapestVariant, getMostExpensiveVariant, officialSourceTypes } from "../../catalog/queries";
import { smartCatalogSearch, parseBrandModelQuery } from "../../discovery/exact-model-retrieval";
import { QUESTION_SEARCH_LIMIT } from "./question-terms";
import { parseAutomotiveQuery } from "./query-parser";
import db from "../../db";

const MAX_CATALOG_QUERY_LENGTH = 120;

type CatalogSearch = (filters: { q: string; limit: number; page: number; fuelType?: string; maxPrice?: number }) => Promise<CatalogPage>;

type ExactSearchResult = { results: any[]; matchType: string; exactMatch: boolean };
type ExactSearch = (query: string, limit: number) => Promise<ExactSearchResult>;
type CatalogSearchDeps = { exactSearch?: ExactSearch };

const OFFICIAL_SOURCE_TYPES = new Set<string>(officialSourceTypes);

/**
 * P115 (G4): the same price eligibility the structured catalog enforces
 * (lib/catalog/queries currentOfficialPrice) — isCurrent + VERIFIED
 * SourceDocument + ACTIVE official source + VERIFIED BrochureVerification.
 * exactModelRetrieval only filters isCurrent, so its rows must be
 * re-checked here before any price can enter structured AI evidence.
 */
function isOfficialCurrentPrice(price: unknown): boolean {
  const p = price as {
    isCurrent?: boolean;
    sourceDocument?: {
      status?: string;
      source?: { status?: string; sourceType?: string };
      verifications?: Array<{ status?: string }>;
    } | null;
  } | null;
  if (!p || p.isCurrent !== true) return false;
  const doc = p.sourceDocument;
  if (!doc || doc.status !== "VERIFIED") return false;
  const source = doc.source;
  if (!source || source.status !== "ACTIVE" || !OFFICIAL_SOURCE_TYPES.has(source.sourceType ?? "")) return false;
  return (doc.verifications ?? []).some((v) => v?.status === "VERIFIED");
}

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

/**
 * Search with exact model retrieval first, then structured filters,
 * then keyword fallback.
 *
 * CRITICAL FIX: Explicit model queries (e.g., "Honda City") now return
 * ONLY matching models, not arbitrary same-brand models.
 */
export async function searchQuestionCatalog(
  question: string,
  searchFn?: CatalogSearch,
  deps?: CatalogSearchDeps,
): Promise<CatalogVariant[]> {
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
  const exactSearch: ExactSearch = deps?.exactSearch ?? ((qq, ll) => smartCatalogSearch(db, qq, ll));

  // P115 (G7): explicit model scope = parser entities OR the repo's own
  // brand/model parser — short models the entity list doesn't know
  // ("MG EP") must still reach exact-model-first, not skip to fallback.
  const modelScope = intent.type === "search" &&
    (intent.entities.length > 0 || !!parseBrandModelQuery(question).model);

  // NEW: Try exact model retrieval FIRST for explicit model queries
  if (intent.type === "search" && modelScope) {
    const fullQuery = intent.entities.length > 0 ? intent.entities.join(" ") : question;
    const exactResult = await exactSearch(fullQuery, QUESTION_SEARCH_LIMIT);

    if (exactResult.exactMatch && exactResult.results.length > 0) {
      // Exact match found — use only these results
      // Map the Prisma variant results to CatalogVariant format
      for (const variant of exactResult.results) {
        // P115 (G4): only prices that satisfy the structured catalog's
        // official+verified+current eligibility may become AI evidence.
        const eligiblePrices = Array.isArray(variant.prices)
          ? variant.prices.filter(isOfficialCurrentPrice)
          : [];
        if (eligiblePrices.length > 0) {
          const catalogVariant: CatalogVariant = {
            id: variant.id,
            nameTh: variant.nameTh,
            nameEn: variant.nameEn,
            slug: variant.slug,
            modelYear: variant.modelYear,
            manufacturer: variant.model?.manufacturer,
            model: variant.model,
            aliases: variant.aliases?.map((a: any) => a.value) ?? [],
            fuelType: variant.fuelType ?? null,
            prices: eligiblePrices.map((p: any) => ({
              amount: Number(p.amount),
              currency: p.currency,
              type: p.priceType,
              validFrom: p.validFrom?.toISOString?.() ?? "",
              validTo: p.validTo?.toISOString?.() ?? null,
              observedAt: p.observedAt?.toISOString?.() ?? "",
              source: {
                id: p.sourceDocument?.id ?? "",
                url: p.sourceDocument?.canonicalUrl ?? p.sourceDocument?.url ?? "",
                titleTh: p.sourceDocument?.titleTh ?? null,
                titleEn: p.sourceDocument?.titleEn ?? null,
                documentStatus: p.sourceDocument?.status ?? "",
                verificationStatus: p.sourceDocument?.verifications?.[0]?.status ?? null,
                verifiedAt: p.sourceDocument?.verifications?.[0]?.verifiedAt?.toISOString?.() ?? null,
                source: {
                  id: p.sourceDocument?.source?.id ?? "",
                  nameTh: p.sourceDocument?.source?.nameTh ?? "",
                  nameEn: p.sourceDocument?.source?.nameEn ?? "",
                  type: p.sourceDocument?.source?.sourceType ?? "",
                  domain: p.sourceDocument?.source?.domain ?? "",
                },
              },
            })),
          };
          found.set(catalogVariant.id, catalogVariant);
        }
      }

      // If exact match returned results, return them directly
      if (found.size > 0) {
        return Array.from(found.values());
      }
    }
    // If no exact match, continue with fallback strategies below
  }

  // 1. Structured filter search (price, fuelType, brand)
  const structuredFilters: { fuelType?: string; maxPrice?: number } = {};
  if (intent.type === "search" && intent.filters.fuelType) structuredFilters.fuelType = intent.filters.fuelType;
  if (intent.type === "search" && intent.filters.maxPrice) structuredFilters.maxPrice = intent.filters.maxPrice;

  if (Object.keys(structuredFilters).length > 0) {
    const filtered = await searcher({ q: "", limit: QUESTION_SEARCH_LIMIT, page: 1, ...structuredFilters });
    addResults(filtered.results);
  }

  // 2. Entity-based search (fallback — only if exact retrieval returned nothing)
  if (found.size === 0) {
    let terms = buildSearchTerms(question, intent.type === "search" ? intent.entities : []);
    // P115 (G5): an explicit model query must never fall back to a
    // brand-only term — "honda"/"mg" alone would return arbitrary
    // same-brand rows (CR-V, Civic, EXTENDER…) for "Honda City"/"MG EP".
    // Brand browse WITHOUT a model scope keeps brand terms (legitimate).
    if (modelScope && intent.type === "search" && intent.filters.brand) {
      terms = terms.filter((term) => term !== intent.filters.brand);
    }
    for (const term of terms.slice(0, 6)) {
      const page = await searcher({ q: term.slice(0, MAX_CATALOG_QUERY_LENGTH), limit: QUESTION_SEARCH_LIMIT, page: 1 });
      addResults(page.results);
    }
  }

  return Array.from(found.values());
}
