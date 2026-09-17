import { extractHtmlCandidates, type HtmlCandidate } from "../../lib/sources/discovery/html-candidates";
import { scoreBrochureCandidate, type BrochureScoreBreakdown } from "../../lib/sources/scoring/brochure-score";

export interface DiscoveryPage { url: string; html: string; }
export interface ScoredBrochureCandidate { candidate: HtmlCandidate; score: BrochureScoreBreakdown; }
export interface NotFoundAudit {
  status: "not_found";
  searchedAt: string;
  domains: string[];
  queries: string[];
  pagesChecked: string[];
  reason: string;
}
export interface BrochureDiscoveryOptions {
  officialDomains?: readonly string[];
  modelName?: string;
  year?: number | string;
  searchedAt?: string;
  queries?: readonly string[];
}
export interface BrochureDiscoveryResult { candidates: ScoredBrochureCandidate[]; audit?: NotFoundAudit; }

type BrochureScoringOptions = Pick<BrochureDiscoveryOptions, "officialDomains" | "modelName" | "year">;
type NotFoundAuditOptions = Pick<BrochureDiscoveryOptions, "officialDomains" | "queries" | "searchedAt">;

/** Collect and rank brochure/document candidates from already-fetched pages. */
export function discoverBrochures(pages: readonly DiscoveryPage[], options: BrochureDiscoveryOptions = {}): BrochureDiscoveryResult {
  const scoringOptions: BrochureScoringOptions = {
    officialDomains: options.officialDomains,
    modelName: options.modelName,
    year: options.year,
  };
  const byUrl = new Map<string, ScoredBrochureCandidate>();
  for (const page of pages) {
    for (const candidate of extractHtmlCandidates(page.html, page.url).filter((item) => item.kind === "document")) {
      const score = scoreBrochureCandidate({ ...scoringOptions, candidate, pageUrl: page.url });
      const existing = byUrl.get(candidate.url);
      if (!existing || score.total > existing.score.total) byUrl.set(candidate.url, { candidate, score });
    }
  }
  const candidates = [...byUrl.values()].sort((a, b) => b.score.total - a.score.total || a.candidate.url.localeCompare(b.candidate.url));
  if (candidates.length > 0) return { candidates };
  return { candidates, audit: createNotFoundAudit(pages, options) };
}

/** Build a durable audit explaining a deterministic empty discovery pass. */
export function createNotFoundAudit(pages: readonly DiscoveryPage[], options: NotFoundAuditOptions = {}): NotFoundAudit {
  const officialDomains = options.officialDomains ?? [];
  const queries = options.queries ?? [];
  return {
    status: "not_found",
    searchedAt: options.searchedAt ?? new Date().toISOString(),
    domains: [...officialDomains],
    queries: [...queries],
    pagesChecked: pages.map((page) => page.url),
    reason: "No brochure or document candidate was found in the checked pages.",
  };
}

export const collectBrochureCandidates = discoverBrochures;
