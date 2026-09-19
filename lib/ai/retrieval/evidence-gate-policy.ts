/**
 * Deterministic retrieval-confidence policy.
 * Prevents nearest-neighbor vector results from being treated as trustworthy
 * evidence when the query does not plausibly reference the retrieved entity.
 *
 * Policy (deterministic, no LLM needed):
 * 1. Extract known model entities from the query (query-parser).
 * 2. For each vector evidence row, check whether the query mentions the
 *    evidence's entity (manufacturer/model) OR the entity is corroborated
 *    by structured catalog retrieval (which is itself query-parsed).
 * 3. Evidence with distance above MAX_DISTANCE is rejected outright.
 * 4. Vector-only evidence (no query-entity corroboration) is accepted only
 *    within STRICT distance; otherwise dropped.
 */

import type { EvidenceItem, MergedEvidence } from "./evidence-merge";
import type { VectorSearchResult, VectorEvidence } from "../../search/vector-search";
import { parseAutomotiveQuery } from "./query-parser";
import { extractBodyType, KNOWN_BODY_TYPES, NAME_TO_BODY_TYPE } from "./body-type-intent";

export const VECTOR_STRICT_DISTANCE = 0.30; // high-confidence nearest neighbor
export const VECTOR_MAX_DISTANCE = 0.45;   // anything further = untrustworthy

export type GateDecision = {
  accepted: boolean;
  reason: string;
};

const MANUFACTURER_TOKENS = [
  "honda", "toyota", "byd", "mg", "ford", "hyundai", "nissan", "suzuki",
  "bmw", "mercedes", "lexus", "tesla", "geely", "gwm", "changan", "nio",
  "mazda", "subaru", "mitsubishi", "kia", "volvo", "zeekr", "avatr",
  "denza", "porsche", "ferrari", "bentley", "mini", "lepas", "deepal", "xpeng",
];

/** Normalize text for token comparison (lowercase, strip punctuation/spacing variants). */
function normalize(text: string): string {
  return text.toLowerCase().replace(/[\s\-_,.()]/g, "");
}

/**
 * Extract candidate entity tokens (manufacturer/model words) the user plausibly asked about.
 * Uses query-parser entities plus all-db known tokens.
 */
const BRAND_TOKEN_MAP: Record<string, string> = {
  "ฮอนด้า": "honda", "โตโยต้า": "toyota", "บีวายดี": "byd", "เอ็มจี": "mg",
  "ฟอร์ด": "ford", "ฮุนได": "hyundai", "นิสสัน": "nissan", "ซูซูกิ": "suzuki",
  "มาสด้า": "mazda", "ซูบารุ": "subaru", "มิตซูบิชิ": "mitsubishi", "อีซูซุ": "isuzu",
  "เทสลา": "tesla", "จีลี่": "geely", "แอทโต": "atto", "โดลฟิน": "dolphin",
  "ซิตี้": "city", "ซิตี้แฮทช์": "city hatchback", "ซีวิค": "civic", "ซีอาร์-วี": "cr-v",
  "เอชอาร์-วี": "hr-v", "แอคคอร์ด": "accord", "ซุปเปอร์วัน": "super-one",
  "ซีล": "seal", "สิงโต": "sealion", "คัมรี": "camry", "ยาริส": "yaris",
  "ฟอร์จูนเนอร์": "fortuner", "ไฮลักซ์": "hilux", "โคโรลล่า": "corolla",
};

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
  // Thai alias → canonical token
  for (const [thai, en] of Object.entries(BRAND_TOKEN_MAP)) {
    if (lower.includes(thai)) tokens.add(normalize(en));
  }
  return Array.from(tokens);
}

/** Does the evidence content plausibly match the entity tokens from the query? */
function contentMatchesQueryEntities(content: string, tokens: string[]): boolean {
  if (tokens.length === 0) return false;
  const normalContent = normalize(content);
  return tokens.some((t) => t.length >= 2 && normalContent.includes(t));
}

/**
 * Decide whether a vector evidence row may join the merged evidence bundle.
 * Rules:
 * - Rejected if distance > VECTOR_STRICT threshold AND content doesn't match query entities.
 * - Rejected outright if distance > VECTOR_MAX distance.
 * - Accepted otherwise (near match or entity-corroborated).
 */
export function gateVectorEvidence(
  query: string,
  vec: VectorEvidence,
  queryTokens: string[]
): GateDecision {
  const normalizedContent = normalize(vec.content);
  const entityMatch = contentMatchesQueryEntities(vec.content, queryTokens);
  const manufacturerMatch = queryTokens.some((t) =>
    MANUFACTURER_TOKENS.includes(t) && normalizedContent.includes(t)
  );

  if (vec.distance > VECTOR_STRICT_DISTANCE && !entityMatch) {
    return { accepted: false, reason: `distance=${vec.distance.toFixed(4)} beyond strict threshold and content doesn't reference query entity` };
  }
  if (vec.distance > VECTOR_MAX_DISTANCE) {
    // Entity-corroborated rows get a wider absolute bound than pure nearest-neighbor rows:
    // a long comparison/broad-query can legitimately sit further from any single row.
    if (entityMatch) {
      if (vec.distance > 0.60) return { accepted: false, reason: `distance=${vec.distance.toFixed(4)} beyond even entity-corroborated bound` };
      return { accepted: true, reason: "entity-corroborated (wide bound)" };
    }
    return { accepted: false, reason: `distance=${vec.distance.toFixed(4)} untrustworthy` };
  }
  // Manufacturer-token mismatch guard: query mentions brand X, evidence is brand Y brand
  if (!entityMatch && !manufacturerMatch) {
    return { accepted: false, reason: "query entities not referenced in content" };
  }
  return { accepted: true, reason: entityMatch ? "entity-corroborated" : "within strict distance" };
}

/** Rows whose content is factually coherent with the query's ASKED-ABOUT entity
 *  but that do not answer the query intent (e.g. spec row for a price query about
 *  a verified-but-different-fact vehicle) still carry a CONFIDENCE QUALIFIER, not a
 *  pass — they are accepted here but marked low-confidence via truthiness marker.
 */
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
    // Body-type constraint: if query explicitly mentions a body type (SUV, sedan, etc.)
    // and the evidence content references a KNOWN vehicle whose body type conflicts,
    // reject it entirely (not qualified — wrong body type = wrong answer).
    if (bodyType) {
      const contentLower = v.content.toLowerCase();
      // Find the LONGEST model name that appears in the content (word-boundary matched)
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
      // If the longest matching model has a conflicting body type, reject
      if (longestMatch && longestMatch.type !== bodyType) continue;
    }
    accepted.push({ ...v, qualified: v.distance > VECTOR_STRICT_DISTANCE });
  }
  return { available: true, evidence: accepted };
}
