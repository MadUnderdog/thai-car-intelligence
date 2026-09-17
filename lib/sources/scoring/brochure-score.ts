import { isAllowedDomain } from "../../security/url-policy";
import type { HtmlCandidate } from "../discovery/html-candidates";

export interface BrochureScoreInput {
  candidate: Pick<HtmlCandidate, "url" | "sourcePageUrl" | "label" | "kind">;
  officialDomains?: readonly string[];
  modelName?: string;
  year?: number | string;
  pageUrl?: string;
}

export interface BrochureScoreBreakdown {
  officialDomain: number;
  directPageLinkage: number;
  modelName: number;
  thaiOrThailand: number;
  year: number;
  thaiOrSpecTerms: number;
  total: number;
}

const THAI_TERMS = /(?:ไทย|ประเทศไทย|thailand|thai|\.co\.th\b)/i;
const SPEC_TERMS = /(?:spec(?:ification)?s?|โบรชัวร์|brochure|catalog(?:ue)?|ราคา|price|download|ดาวน์โหลด|manual|คู่มือ)/i;

function textFor(input: BrochureScoreInput): string {
  return `${input.candidate.url} ${input.candidate.label ?? ""}`;
}

function modelMatches(text: string, model?: string): boolean {
  if (!model?.trim()) return false;
  const escaped = model.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // Hyphenated variants are separate models, except a year suffix (Yaris-2025).
  return new RegExp(`(^|[^\\p{L}\\p{N}-])${escaped}(?=$|[^\\p{L}\\p{N}-]|-(?:19|20)\\d{2}(?:$|[^\\p{L}\\p{N}]))`, "iu").test(text);
}

/** Score a brochure candidate with an inspectable, deterministic breakdown. */
export function scoreBrochureCandidate(input: BrochureScoreInput): BrochureScoreBreakdown {
  const text = textFor(input);
  const officialDomain = input.officialDomains?.length && isAllowedDomain(input.candidate.url, input.officialDomains) ? 30 : 0;
  const pageUrl = input.pageUrl ?? input.candidate.sourcePageUrl;
  const directPageLinkage = input.candidate.sourcePageUrl === pageUrl ? 15 : 0;
  const modelName = modelMatches(text, input.modelName) ? 25 : 0;
  const thaiOrThailand = THAI_TERMS.test(text) ? 10 : 0;
  const yearText = input.year === undefined ? "" : String(input.year);
  const year = yearText !== "" && text.includes(yearText) ? 10 : 0;
  const thaiOrSpecTerms = SPEC_TERMS.test(text) ? 10 : 0;
  return { officialDomain, directPageLinkage, modelName, thaiOrThailand, year, thaiOrSpecTerms,
    total: officialDomain + directPageLinkage + modelName + thaiOrThailand + year + thaiOrSpecTerms };
}

export function scoreBrochure(input: BrochureScoreInput): BrochureScoreBreakdown {
  return scoreBrochureCandidate(input);
}
