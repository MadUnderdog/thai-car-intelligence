import { isAllowedDomain } from "../../lib/security/url-policy";
import { safeFetch, type SafeFetchOptions } from "../../lib/security/safe-fetch";
import { extractHtmlCandidates, type HtmlCandidate } from "../../lib/sources/discovery/html-candidates";
import { scoreBrochureCandidate, type BrochureScoreBreakdown } from "../../lib/sources/scoring/brochure-score";
import { discoverImages, type ImageCandidate } from "../discovery/image-discovery";
import { db } from "../../lib/db";

export type ResearchRunStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "PARTIAL_SUCCESS" | "FAILED" | "CANCELLED";

export interface ResearchRunInput {
  model?: string;
  entityType?: string;
  entityId?: string;
  officialDomains: readonly string[];
  seedPageUrls: readonly string[];
  discoveryQueries: readonly string[];
  year?: number | string;
  provider?: string;
  name?: string;
}

export interface ResearchCandidateReport {
  url: string;
  kind: "document" | "image";
  sourcePageUrl: string;
  discoveryMethod: HtmlCandidate["discoveryMethod"];
  score?: BrochureScoreBreakdown;
  role?: ImageCandidate["role"];
  label?: string;
  width?: number;
}

export interface ResearchReport {
  status: "discovered" | "not_found";
  queries: string[];
  domainsChecked: string[];
  pagesChecked: string[];
  candidates: ResearchCandidateReport[];
  errors: Array<{ url: string; error: string }>;
  reason?: string;
}

interface ResearchClient {
  researchRun: { create(args: { data: Record<string, unknown> }): Promise<{ id: string }>;
    update(args: { where: { id: string }; data: Record<string, unknown> }): Promise<unknown> };
  researchCandidate: { createMany(args: { data: Array<Record<string, unknown>> }): Promise<unknown> };
}

export interface ResearchRunOptions {
  client?: ResearchClient;
  fetch?: typeof fetch;
  now?: () => Date;
  safeFetchOptions?: Omit<SafeFetchOptions, "fetch">;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function candidateReport(candidate: HtmlCandidate, score?: BrochureScoreBreakdown, role?: ImageCandidate["role"]): ResearchCandidateReport {
  return { url: candidate.url, kind: candidate.kind, sourcePageUrl: candidate.sourcePageUrl, discoveryMethod: candidate.discoveryMethod, ...(score ? { score } : {}), ...(role ? { role } : {}), ...(candidate.label ? { label: candidate.label } : {}), ...(candidate.width !== undefined ? { width: candidate.width } : {}) };
}

async function markRunFailed(client: ResearchClient, runId: string, error: unknown, now: () => Date): Promise<void> {
  try {
    await client.researchRun.update({ where: { id: runId }, data: { status: "FAILED", error: errorMessage(error), completedAt: now() } });
  } catch {
    // Recovery is best effort; never mask the original persistence error.
  }
}

/** Fetch official HTML seed pages, discover reference-only candidates, and persist an auditable run. */
export async function runResearch(input: ResearchRunInput, options: ResearchRunOptions = {}): Promise<{ runId: string; status: ResearchRunStatus; report: ResearchReport }> {
  const client = options.client ?? (db as unknown as ResearchClient);
  const now = options.now ?? (() => new Date());
  const domains = [...new Set(input.officialDomains.map((domain) => domain.trim().toLowerCase()).filter(Boolean))];
  const queries = [...input.discoveryQueries];
  const seedUrls = [...new Set(input.seedPageUrls)];
  const startedAt = now();
  const created = await client.researchRun.create({ data: {
    name: input.name ?? `${input.model ?? "research"} discovery`, status: "RUNNING", provider: input.provider,
    entityType: input.entityType, entityId: input.entityId, queries, domainsChecked: domains, startedAt,
  } });
  const pages: Array<{ url: string; html: string }> = [];
  const errors: Array<{ url: string; error: string }> = [];

  for (const url of seedUrls) {
    if (!isAllowedDomain(url, domains)) {
      errors.push({ url, error: "Seed page is outside the official-domain allow-list." });
      continue;
    }
    try {
      const response = await safeFetch(url, { headers: { accept: "text/html,application/xhtml+xml" } }, { ...options.safeFetchOptions, fetch: options.fetch });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const contentType = response.headers.get("content-type") ?? "";
      if (contentType && !/text\/html|application\/xhtml\+xml/i.test(contentType)) throw new Error("Response is not HTML.");
      pages.push({ url, html: await response.text() });
    } catch (error) {
      errors.push({ url, error: errorMessage(error) });
    }
  }

  const discovered: ResearchCandidateReport[] = [];
  const seen = new Set<string>();
  for (const page of pages) {
    for (const candidate of extractHtmlCandidates(page.html, page.url)) {
      if (!isAllowedDomain(candidate.url, domains)) continue;
      const key = `${candidate.kind}|${candidate.url}`;
      if (seen.has(key)) continue;
      seen.add(key);
      if (candidate.kind === "document") {
        discovered.push(candidateReport(candidate, scoreBrochureCandidate({ candidate, officialDomains: domains, modelName: input.model, year: input.year, pageUrl: page.url })));
      } else {
        const image = discoverImages(page.html, page.url).find((item) => item.url === candidate.url);
        // Utility/branding assets are not vehicle image candidates.
        if (!image || image.role === "unknown" || image.role === "logo") continue;
        discovered.push(candidateReport(candidate, undefined, image.role));
      }
    }
  }

  const report: ResearchReport = discovered.length ? { status: "discovered", queries, domainsChecked: domains, pagesChecked: pages.map((page) => page.url), candidates: discovered, errors } : {
    status: "not_found", queries, domainsChecked: domains, pagesChecked: pages.map((page) => page.url), candidates: [], errors,
    reason: errors.length && pages.length === 0 ? "No seed page could be fetched." : "No allowed document or image candidate was found in the checked pages.",
  };
  const status: ResearchRunStatus = pages.length === 0 ? (errors.length ? "FAILED" : "SUCCEEDED") : errors.length ? "PARTIAL_SUCCESS" : "SUCCEEDED";
  try {
    if (discovered.length) await client.researchCandidate.createMany({ data: discovered.map((candidate) => ({ researchRunId: created.id, fieldName: candidate.kind === "document" ? "document_candidate" : "image_candidate", proposedValue: candidate, evidence: candidate.sourcePageUrl, confidence: candidate.score ? candidate.score.total / 100 : 0, status: "PENDING" })) });
  } catch (error) {
    await markRunFailed(client, created.id, error, now);
    throw error;
  }
  try {
    await client.researchRun.update({ where: { id: created.id }, data: { status, pagesChecked: pages.length, documentsFound: discovered.filter((candidate) => candidate.kind === "document").length, imagesFound: discovered.filter((candidate) => candidate.kind === "image").length, error: errors.length ? errors.map((item) => `${item.url}: ${item.error}`).join("\n") : null, completedAt: now() } });
  } catch (error) {
    await markRunFailed(client, created.id, error, now);
    throw error;
  }
  return { runId: created.id, status, report };
}

export const researchModel = runResearch;
