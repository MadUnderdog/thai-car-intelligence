export type SourceType = "official" | "government" | "news" | "industry" | "community" | "social" | "reference";

export type RightsStatus = "unknown" | "permitted" | "restricted" | "licensed" | "public-domain" | "user-provided";
export type ResearchStatus = "discovered" | "validated" | "fetchable" | "blocked" | "failed" | "archived";

export interface SourcePolicy {
  /** Official sources take precedence over secondary reporting for factual claims. */
  precedence: number;
  allowedDomains?: readonly string[];
  requiresAttribution: boolean;
  rights: RightsStatus;
  /** Whether downloaded content may be stored; reference-only means keep URL/metadata only. */
  referenceOnly: boolean;
}

export interface SourceConfig extends SourcePolicy {
  id: string;
  name: string;
  type: SourceType;
  baseUrl: string;
  enabled: boolean;
  notes?: string;
}

export interface DiscoveryCandidate {
  url: string;
  title?: string;
  sourceId?: string;
  discoveredAt: string;
  sourceType?: SourceType;
  rights?: RightsStatus;
}

export interface SourceRecord extends DiscoveryCandidate {
  status: ResearchStatus;
  canonicalUrl?: string;
  fetchedAt?: string;
  contentHash?: string;
  error?: string;
}
