/**
 * Deterministic retrieval-confidence policy (P12.6 hardened).
 *
 * Prevents nearest-neighbor vector results from being treated as trustworthy
 * evidence when the query does not plausibly reference the retrieved entity.
 *
 * Defense layers (all deterministic, no LLM needed):
 * 1. Source-type guard: RESEARCH/unverified evidence is rejected when type is available.
 * 2. Canonical model identity: exact brand+model pairing via canonical table.
 * 3. Entity-level specificity: query-specific terms must match evidence content.
 * 4. Brand consistency: evidence must reference the query's manufacturer brand.
 * 5. Body-type constraint: conflicting vehicle body types are rejected.
 * 6. Distance thresholds: strict (0.30) and max (0.45) with entity-corroborated wide bound (0.60).
 *
 * The canonical identity table is the SINGLE source of truth for model identity.
 * Short tokens (EP, ZS, HS) use canonical matching, not substring/length rules.
 */

import type { VectorSearchResult, VectorEvidence } from "../../search/vector-search";
import { parseAutomotiveQuery } from "./query-parser";
import { extractBodyType, KNOWN_BODY_TYPES, NAME_TO_BODY_TYPE, BODY_TYPE_MAP } from "./body-type-intent";

// ── Thresholds ────────────────────────────────────────────────────────────
export const VECTOR_STRICT_DISTANCE = 0.30;
export const VECTOR_MAX_DISTANCE = 0.45;

export type GateDecision = {
  accepted: boolean;
  reason: string;
};

// ── Canonical Model Identity ──────────────────────────────────────────────
// Every known model gets an explicit identity. This replaces substring/length heuristics.
// canonicalName: exact normalized name (lowercase, no spaces/punctuation)
// brand: manufacturer name (normalized)
// aliases: alternative names that belong to the SAME canonical identity (including trim/variant aliases)
// excludes: names that MUST NOT match this identity (cross-model exclusions)

type CanonicalModel = {
  canonicalName: string;
  brand: string;
  /** Names that belong to this exact model identity (including variants/trims) */
  aliases: string[];
  /** Names that must NOT be accepted for this model (cross-collision guards) */
  excludes: string[];
};

const CANONICAL_MODELS: CanonicalModel[] = [
  // ── MG ──
  { canonicalName: "mg ep", brand: "mg", aliases: ["mg ep", "mgep", "mg-ep", "เอพี", "เอ็มจี เอพี"], excludes: ["ep plus", "epplus", "ep-plus", "mg ep plus", "mg ep+"] },
  { canonicalName: "mg ep plus", brand: "mg", aliases: ["mg ep plus", "mgepplus", "mg-ep-plus", "ep plus", "epplus", "ep-plus", "mg ep+"], excludes: [] },
  { canonicalName: "mg im5", brand: "mg", aliases: ["mg im5", "mg im 5", "mgim5", "mg-im5", "mg-im-5", "ไอเอ็ม 5", "ไอเอ็ม5", "เอ็มจี ไอเอ็ม 5"], excludes: ["im6", "im 6", "mg im6"] },
  { canonicalName: "mg im6", brand: "mg", aliases: ["mg im6", "mg im 6", "mgim6", "mg-im6", "mg-im-6", "ไอเอ็ม 6", "ไอเอ็ม6", "เอ็มจี ไอเอ็ม 6"], excludes: ["im5", "im 5", "mg im5"] },
  { canonicalName: "mg4", brand: "mg", aliases: ["mg4", "mg 4", "mg-4", "เอ็มจี 4", "เอ็มจี4", "โฟร์"], excludes: [] },
  { canonicalName: "mg zs", brand: "mg", aliases: ["mg zs", "mgzs", "mg-zs", "ซีเอส"], excludes: [] },
  { canonicalName: "mg zs ev", brand: "mg", aliases: ["mg zs ev", "mgzs ev", "mg-zs-ev"], excludes: [] },
  { canonicalName: "mg hs", brand: "mg", aliases: ["mg hs", "mghs", "mg-hs", "เอชเอส"], excludes: [] },
  { canonicalName: "mg3 hybrid", brand: "mg", aliases: ["mg3 hybrid", "mg3 hybrid+", "mg3hybrid", "mg3-hybrid"], excludes: [] },
  { canonicalName: "mg s5 ev", brand: "mg", aliases: ["mg s5 ev", "mg s5", "mg s5 ev plus", "mgs5ev", "mg-s5-ev", "เอส 5"], excludes: [] },
  { canonicalName: "mg urban", brand: "mg", aliases: ["mg urban", "mgurban", "mg-urban"], excludes: [] },
  { canonicalName: "mg es", brand: "mg", aliases: ["mg es", "mges", "mg-es"], excludes: [] },
  { canonicalName: "mg vs hev", brand: "mg", aliases: ["mg vs hev", "mgvshev", "mg-vs-hev", "วีเอส"], excludes: [] },
  { canonicalName: "mg5", brand: "mg", aliases: ["mg5", "mg 5", "mg-5"], excludes: [] },

  // ── Honda ──
  { canonicalName: "city", brand: "honda", aliases: ["city", "honda city", "hondacity", "honda-city", "ซิตี้", "ฮอนด้า ซิตี้"], excludes: ["city hatchback", "cityhatchback"] },
  { canonicalName: "city hatchback", brand: "honda", aliases: ["city hatchback", "cityhatchback", "city-hatchback", "honda city hatchback", "ซิตี้แฮทช์", "แฮทช์แบ็ก"], excludes: [] },
  { canonicalName: "civic", brand: "honda", aliases: ["civic", "honda civic", "hondacivic", "honda-civic", "ซีวิค"], excludes: [] },
  { canonicalName: "cr-v", brand: "honda", aliases: ["cr-v", "crv", "honda cr-v", "hondacrv", "honda-crv", "ซีอาร์-วี"], excludes: [] },
  { canonicalName: "hr-v", brand: "honda", aliases: ["hr-v", "hrv", "honda hr-v", "hondahrv", "honda-hrv", "เอชอาร์-วี"], excludes: [] },
  { canonicalName: "accord", brand: "honda", aliases: ["accord", "honda accord", "hondaaccord", "honda-accord", "แอคคอร์ด"], excludes: [] },
  { canonicalName: "br-v", brand: "honda", aliases: ["br-v", "brv", "honda br-v", "hondabrv", "honda-br-v", "บีอาร์-วี"], excludes: [] },
  { canonicalName: "wr-v", brand: "honda", aliases: ["wr-v", "wrv", "honda wr-v", "hondawrv", "honda-wr-v"], excludes: [] },
  { canonicalName: "super one", brand: "honda", aliases: ["super one", "super-one", "superone", "honda super one", "ซุปเปอร์วัน"], excludes: [] },

  // ── Toyota ──
  { canonicalName: "camry", brand: "toyota", aliases: ["camry", "toyota camry", "toyotacamry", "toyota-camry", "คัมรี"], excludes: [] },
  { canonicalName: "yaris", brand: "toyota", aliases: ["yaris", "toyota yaris", "toyotayaris", "toyota-yaris", "ยาริส"], excludes: ["yaris cross", "yariscross"] },
  { canonicalName: "yaris cross", brand: "toyota", aliases: ["yaris cross", "yariscross", "yaris-cross", "toyota yaris cross"], excludes: [] },
  { canonicalName: "corolla altis", brand: "toyota", aliases: ["corolla altis", "corollaaltis", "corolla-altis", "toyota corolla altis", "โคโรลล่า"], excludes: [] },
  { canonicalName: "fortuner", brand: "toyota", aliases: ["fortuner", "toyota fortuner", "toyotafortuner", "toyota-fortuner", "ฟอร์จูนเนอร์"], excludes: [] },
  { canonicalName: "hilux", brand: "toyota", aliases: ["hilux", "toyota hilux", "toyotahilux", "toyota-hilux", "ไฮลักซ์"], excludes: [] },

  // ── BYD ──
  { canonicalName: "atto 2", brand: "byd", aliases: ["atto 2", "atto2", "atto-2", "byd atto 2", "แอทโต 2"], excludes: ["atto 3", "atto3", "atto-3"] },
  { canonicalName: "atto 3", brand: "byd", aliases: ["atto 3", "atto3", "atto-3", "byd atto 3", "แอทโต 3"], excludes: ["atto 2", "atto2", "atto-2"] },
  { canonicalName: "dolphin", brand: "byd", aliases: ["dolphin", "byd dolphin", "byddolphin", "byd-dolphin", "โดลฟิน"], excludes: [] },
  { canonicalName: "seal", brand: "byd", aliases: ["seal", "byd seal", "bydseal", "byd-seal", "ซีล"], excludes: [] },
  { canonicalName: "sealion 7", brand: "byd", aliases: ["sealion 7", "sealion7", "sealion-7", "byd sealion 7", "สิงโต"], excludes: [] },

  // ── Tesla ──
  { canonicalName: "model 3", brand: "tesla", aliases: ["model 3", "model3", "model-3", "tesla model 3", "teslamodel3", "tesla-model-3", "โมเดล 3"], excludes: ["model y", "modely", "model-y"] },
  { canonicalName: "model y", brand: "tesla", aliases: ["model y", "modely", "model-y", "tesla model y", "teslamodely", "tesla-model-y", "โมเดล วาย"], excludes: ["model 3", "model3", "model-3"] },

  // ── Nissan ──
  { canonicalName: "kicks", brand: "nissan", aliases: ["kicks", "nissan kicks", "nissankicks", "nissan-kicks", "คิกส์"], excludes: [] },
];

// ── Trusted vs Untrusted Source Types ──────────────────────────────────────
// Evidence types the gate treats as trustworthy
const TRUSTED_SOURCE_TYPES = new Set([
  "OFFICIAL_MANUFACTURER",
  "OFFICIAL_BROCHURE",
  "OFFICIAL_PRICE_LIST",
  "AUTHORIZED_DEALER",
  "VERIFIED_AUTOMOTIVE_REFERENCE",
]);

// Evidence types the gate explicitly rejects (defense-in-depth)
const UNTRUSTED_SOURCE_TYPES = new Set([
  "RESEARCH",
  "UNVERIFIED",
  "COMMUNITY",
  "USER_SUBMISSION",
]);

// ── Text Normalization ─────────────────────────────────────────────────────
function normalize(text: string): string {
  return text.toLowerCase().replace(/[\s\-_,.()]/g, "");
}

// ── Manufacturer Tokens ────────────────────────────────────────────────────
const MANUFACTURER_TOKENS = [
  "honda", "toyota", "byd", "mg", "ford", "hyundai", "nissan", "suzuki",
  "bmw", "mercedes", "lexus", "tesla", "geely", "gwm", "changan", "nio",
  "mazda", "subaru", "mitsubishi", "kia", "volvo", "zeekr", "avatr",
  "denza", "porsche", "ferrari", "bentley", "mini", "lepas", "deepal", "xpeng",
];

const BRAND_TOKEN_MAP: Record<string, string> = {
  "ฮอนด้า": "honda", "โตโยต้า": "toyota", "บีวายดี": "byd", "เอ็มจี": "mg",
  "ฟอร์ด": "ford", "ฮุนได": "hyundai", "นิสสัน": "nissan", "ซูซูกิ": "suzuki",
  "มาสด้า": "mazda", "ซูบารุ": "subaru", "มิตซูบิชิ": "mitsubishi", "อีซูซุ": "isuzu",
  "เทสลา": "tesla", "จีลี่": "geely", "แอทโต": "atto", "โดลฟิน": "dolphin",
  "ซิตี้": "city", "ซิตี้แฮทช์": "city hatchback", "ซีวิค": "civic", "ซีอาร์-วี": "cr-v",
  "เอชอาร์-วี": "hr-v", "แอคคอร์ด": "accord", "ซุปเปอร์วัน": "super one", "ซูเปอร์วัน": "super one",
  "ซีล": "seal", "สิงโต": "sealion", "คัมรี": "camry", "ยาริส": "yaris",
  "ฟอร์จูนเนอร์": "fortuner", "ไฮลักซ์": "hilux", "โคโรลล่า": "corolla altis",
  "ไอเอ็ม 5": "im5", "ไอเอ็ม 6": "im6", "เอส 5": "s5 ev",
  "เอพี": "ep", "วีเอส": "vs hev", "ซีเอส": "zs", "เอชเอส": "hs",
};

const THAI_QUERY_WORDS = new Set([
  "ราคา", "เท่าไหร่", "ราคาเท่าไหร่", "เท่าไร", "ราคากี่", "กี่บาท", "มี", "รถ", "รุ่น", "ที่", "ของ", "ไหม", "ครับ", "ค่ะ",
  "กี่", "เปรียบเทียบ", "เทียบ", "ไม่เกิน", "ต่ำกว่า", "มากกว่า", "ถูกที่สุด", "แพงที่สุด",
  "ระยะทาง", "กำลัง", "แรงม้า", "แบตเตอรี่", "ชาร์จ", "วิ่ง", "กี่km", "กี่kwh",
  "weight", "compare", "price", "how", "much", "what", "is", "the", "have", "model", "electric", "ev", "hev",
]);

// ── Entity Extraction ──────────────────────────────────────────────────────

function queryEntityTokens(query: string): string[] {
  const tokens = new Set<string>();
  try {
    const intent = parseAutomotiveQuery(query);
    const entities = (intent as { entities?: unknown }).entities;
    if (Array.isArray(entities)) {
      for (const e of entities) tokens.add(normalize(String(e)));
    }
    const filters = (intent as { filters?: { brand?: string } }).filters;
    if (filters?.brand) tokens.add(normalize(filters.brand));
  } catch {
    // parser failure → rely on brand tokens only
  }
  const lower = query.toLowerCase();
  for (const m of MANUFACTURER_TOKENS) {
    if (lower.includes(m)) tokens.add(m);
  }
  for (const [thai, en] of Object.entries(BRAND_TOKEN_MAP)) {
    if (lower.includes(thai)) tokens.add(normalize(en));
  }
  return Array.from(tokens);
}

function contentMatchesQueryEntities(content: string, tokens: string[]): boolean {
  if (tokens.length === 0) return false;
  const normalContent = normalize(content);
  return tokens.some((t) => t.length >= 2 && normalContent.includes(t));
}

// ── Canonical Model Identity Matching ──────────────────────────────────────

/**
 * Check if an alias appears in text with proper word boundaries.
 * Uses original (non-normalized) text for boundary detection.
 * Word boundary = start/end of string, space, punctuation, or transition between
 * letter types (letter↔digit, letter↔Thai).
 */
function matchesWithBoundaries(text: string, alias: string): boolean {
  const lower = text.toLowerCase();
  const aliasLower = alias.toLowerCase();
  // Try each position in the text
  let searchFrom = 0;
  while (true) {
    const idx = lower.indexOf(aliasLower, searchFrom);
    if (idx < 0) return false;
    // Check word boundary before
    const beforeOk = idx === 0 || /[\s\-_,.()!@#$%^&*+={}[\]|\\:;"'<>?/]/.test(lower[idx - 1]) ||
      (idx > 0 && /\d/.test(lower[idx - 1]) !== /\d/.test(lower[idx])) ||
      (idx > 0 && /[a-z]/.test(lower[idx - 1]) !== /[a-z]/.test(lower[idx]));
    // Check word boundary after
    const afterIdx = idx + aliasLower.length;
    const afterOk = afterIdx >= lower.length || /[\s\-_,.()!@#$%^&*+={}[\]|\\:;"'<>?/]/.test(lower[afterIdx]) ||
      (afterIdx < lower.length && /\d/.test(lower[afterIdx - 1]) !== /\d/.test(lower[afterIdx])) ||
      (afterIdx < lower.length && /[a-z]/.test(lower[afterIdx - 1]) !== /[a-z]/.test(lower[afterIdx]));
    if (beforeOk && afterOk) return true;
    searchFrom = idx + 1;
  }
}

/**
 * Given query text and evidence content, determine if they refer to the
 * SAME canonical model identity.
 *
 * This is the core of short-token safety: "MG EP" query vs "MG EP Plus"
 * evidence → queryModel="mg ep", evidenceModel="mg ep plus" → not same identity → excluded.
 */
function canonicalIdentityMatch(
  queryText: string,
  evidenceContent: string
): { match: boolean; isExcluded: boolean; queryModel: string | null; evidenceModel: string | null } {
  // Find which canonical model(s) the query refers to (use word-boundary matching).
  // Track the longest matching alias per model to find the MOST SPECIFIC match.
  const queryMatches: { model: CanonicalModel; aliasLen: number }[] = [];
  for (const model of CANONICAL_MODELS) {
    let bestLen = 0;
    for (const alias of model.aliases) {
      if (matchesWithBoundaries(queryText, alias) && alias.length > bestLen) {
        bestLen = alias.length;
      }
    }
    if (bestLen > 0) queryMatches.push({ model, aliasLen: bestLen });
  }
  // Sort by alias length descending — most specific match first
  queryMatches.sort((a, b) => b.aliasLen - a.aliasLen);

  // Find which canonical model(s) the evidence refers to
  const evidenceMatches: { model: CanonicalModel; aliasLen: number }[] = [];
  for (const model of CANONICAL_MODELS) {
    let bestLen = 0;
    for (const alias of model.aliases) {
      if (matchesWithBoundaries(evidenceContent, alias) && alias.length > bestLen) {
        bestLen = alias.length;
      }
    }
    if (bestLen > 0) evidenceMatches.push({ model, aliasLen: bestLen });
  }
  evidenceMatches.sort((a, b) => b.aliasLen - a.aliasLen);

  if (queryMatches.length === 0 && evidenceMatches.length === 0) {
    return { match: false, isExcluded: false, queryModel: null, evidenceModel: null };
  }
  if (queryMatches.length === 0) {
    return { match: false, isExcluded: false, queryModel: null, evidenceModel: evidenceMatches[0]?.model.canonicalName ?? null };
  }
  if (evidenceMatches.length === 0) {
    return { match: false, isExcluded: false, queryModel: queryMatches[0]?.model.canonicalName ?? null, evidenceModel: null };
  }

  // Use the BEST (most specific) match from each side
  const bestQuery = queryMatches[0].model;
  const bestEvidence = evidenceMatches[0].model;

  // Same canonical identity?
  if (bestQuery.canonicalName === bestEvidence.canonicalName) {
    return { match: true, isExcluded: false, queryModel: bestQuery.canonicalName, evidenceModel: bestEvidence.canonicalName };
  }

  // Cross-exclusion: does the query model explicitly exclude the evidence model?
  if (bestQuery.excludes.some((ex) => normalize(ex) === normalize(bestEvidence.canonicalName))) {
    return { match: false, isExcluded: true, queryModel: bestQuery.canonicalName, evidenceModel: bestEvidence.canonicalName };
  }

  // Same brand: check if one is a strict prefix of the other
  if (bestQuery.brand === bestEvidence.brand) {
    const qNorm2 = normalize(bestQuery.canonicalName);
    const eNorm2 = normalize(bestEvidence.canonicalName);
    if (eNorm2.startsWith(qNorm2) && eNorm2.length > qNorm2.length) {
      return { match: false, isExcluded: true, queryModel: bestQuery.canonicalName, evidenceModel: bestEvidence.canonicalName };
    }
    if (qNorm2.startsWith(eNorm2) && qNorm2.length > eNorm2.length) {
      return { match: false, isExcluded: true, queryModel: bestQuery.canonicalName, evidenceModel: bestEvidence.canonicalName };
    }
  }

  return { match: false, isExcluded: false, queryModel: bestQuery.canonicalName, evidenceModel: bestEvidence.canonicalName };
}

// ── Source Type Guard ──────────────────────────────────────────────────────

/**
 * Defense-in-depth: reject untrusted evidence at the gate level.
 * Production SQL already filters for VERIFIED SourceDocuments, but the gate
 * must ALSO reject when source metadata carries RESEARCH/unverified status.
 */
function sourceTypeGuard(sourceType: string): { trusted: boolean; reason: string } {
  const st = sourceType.toUpperCase().replace(/[\s\-]/g, "_");
  if (UNTRUSTED_SOURCE_TYPES.has(st) || UNTRUSTED_SOURCE_TYPES.has(sourceType)) {
    return { trusted: false, reason: `sourceType=${sourceType} is untrusted (research/unverified)` };
  }
  if (TRUSTED_SOURCE_TYPES.has(st) || TRUSTED_SOURCE_TYPES.has(sourceType)) {
    return { trusted: true, reason: `sourceType=${sourceType} is trusted` };
  }
  // Unknown source type → treat as untrusted (fail-closed)
  return { trusted: false, reason: `sourceType=${sourceType} is unknown/uncertain (fail-closed)` };
}

// ── Brand Consistency Guard ────────────────────────────────────────────────

/**
 * Contract: when query specifies explicit brand+model, evidence MUST also
 * reference that brand. Brand-only queries remain multi-model.
 * Evidence with NO brand reference is rejected when query has explicit brand+model.
 */
function brandConsistencyGuard(
  query: string,
  content: string,
  queryTokens: string[]
): boolean {
  const queryBrands = queryTokens.filter((t) => MANUFACTURER_TOKENS.includes(t));
  if (queryBrands.length === 0) return true;
  const contentLower = normalize(content);
  const contentBrands = MANUFACTURER_TOKENS.filter((b) => contentLower.includes(b));
  // Fail-closed: when query specifies explicit brand+model, evidence without
  // any brand identity is rejected (no silent weakening to model-only).
  if (contentBrands.length === 0) {
    // Check if query references a specific canonical model (brand+model)
    // vs brand-only. Brand-only = allow no-brand evidence; brand+model = reject.
    const hasModelInQuery = queryTokens.some(
      (t) => !MANUFACTURER_TOKENS.includes(t) && t.length >= 2
    );
    return !hasModelInQuery;
  }
  // Mixed-entity rejection: when query specifies a single brand but evidence mentions
  // multiple different brands, reject to prevent adversarial cross-brand contamination
  // (e.g., evidence mentioning both Toyota City and Honda City for a Honda City query).
  if (queryBrands.length === 1 && contentBrands.length > 1) return false;
  return contentBrands.some((cb) => queryBrands.includes(cb));
}

// ── Core Gate Function ─────────────────────────────────────────────────────

/**
 * Decide whether a vector evidence row may join the merged evidence bundle.
 *
 * Defense layers (applied in order):
 * 1. Source type guard: reject RESEARCH/unverified evidence
 * 2. Canonical model identity: exact brand+model pairing
 * 3. Brand consistency guard: evidence must reference query brand
 * 4. Entity specificity guard: query-specific terms must match evidence
 * 5. Distance threshold checks
 */
export function gateVectorEvidence(
  query: string,
  vec: VectorEvidence,
  queryTokens: string[]
): GateDecision {
  const normalizedContent = normalize(vec.content);

  // ── Layer 1: Source type guard ───────────────────────────────────────
  const srcGuard = sourceTypeGuard(vec.source.sourceType);
  if (!srcGuard.trusted) {
    return { accepted: false, reason: srcGuard.reason };
  }

  // ── Layer 2: Canonical model identity ────────────────────────────────
  const identity = canonicalIdentityMatch(query, vec.content);
  if (identity.isExcluded) {
    return {
      accepted: false,
      reason: `canonical identity mismatch: query=${identity.queryModel}, evidence=${identity.evidenceModel}`,
    };
  }
  // Both query and evidence reference canonical models but don't match → different models
  if (identity.queryModel && identity.evidenceModel && identity.queryModel !== identity.evidenceModel && !identity.match) {
    return {
      accepted: false,
      reason: `different canonical models: query=${identity.queryModel}, evidence=${identity.evidenceModel}`,
    };
  }

  // ── Layer 3: Brand consistency guard ─────────────────────────────────
  if (!brandConsistencyGuard(query, vec.content, queryTokens)) {
    return { accepted: false, reason: "evidence brand does not match query brand" };
  }

  // ── Layer 4: Entity specificity guard ────────────────────────────────
  const entitySpecificTerms = queryTokens.filter(
    (t) => !MANUFACTURER_TOKENS.includes(t) && t.length >= 2
  );
  const entitySpecificMatch =
    entitySpecificTerms.length === 0 ||
    entitySpecificTerms.some((t) => normalizedContent.includes(t));

  if (!entitySpecificMatch) {
    return {
      accepted: false,
      reason: `query specifies [${entitySpecificTerms.join(",")}] but evidence does not reference these entities`,
    };
  }

  // ── Layer 5: Distance thresholds ─────────────────────────────────────
  const entityMatch = contentMatchesQueryEntities(vec.content, queryTokens);

  if (vec.distance > VECTOR_STRICT_DISTANCE && !entityMatch) {
    return { accepted: false, reason: `distance=${vec.distance.toFixed(4)} beyond strict threshold and content doesn't reference query entity` };
  }
  if (vec.distance > VECTOR_MAX_DISTANCE) {
    if (entityMatch) {
      if (vec.distance > 0.60) return { accepted: false, reason: `distance=${vec.distance.toFixed(4)} beyond even entity-corroborated bound` };
      return { accepted: true, reason: "entity-corroborated (wide bound)" };
    }
    return { accepted: false, reason: `distance=${vec.distance.toFixed(4)} untrustworthy` };
  }

  // ── Final: entity match required ─────────────────────────────────────
  if (!entityMatch) {
    return { accepted: false, reason: "query entities not referenced in content" };
  }
  return { accepted: true, reason: "entity-corroborated" };
}

// ── Public API ─────────────────────────────────────────────────────────────

export type GatedEvidence = VectorEvidence & { qualified: boolean };

/** Returns gate-filtered vector result based on deterministic policy. */
export function applyEvidenceThresholds(query: string, result: VectorSearchResult): VectorSearchResult {
  if (!result.available || result.evidence.length === 0) return result;
  const tokens = queryEntityTokens(query);
  const bodyType = extractBodyType(query);
  const accepted: GatedEvidence[] = [];
  for (const v of result.evidence) {
    const decision = gateVectorEvidence(query, v, tokens);
    if (!decision.accepted) continue;
    // Body-type constraint
    if (bodyType) {
      const contentLower = v.content.toLowerCase();
      let longestMatch: { name: string; type: string } | null = null;
      for (const [name, knownType] of Object.entries(NAME_TO_BODY_TYPE)) {
        const nameLower = name.toLowerCase();
        const idx = contentLower.indexOf(nameLower);
        if (idx >= 0) {
          const beforeOk = idx === 0 || /[\s,()]/.test(contentLower[idx - 1]);
          const afterOk = idx + nameLower.length >= contentLower.length || /[\s,()]/.test(contentLower[idx + nameLower.length]);
          if (beforeOk && afterOk) {
            if (!longestMatch || name.length > longestMatch.name.length) {
              longestMatch = { name, type: knownType };
            }
          }
        }
      }
      if (longestMatch && longestMatch.type !== bodyType) continue;
    }
    accepted.push({ ...v, qualified: v.distance > VECTOR_STRICT_DISTANCE });
  }
  return { available: true, evidence: accepted };
}
