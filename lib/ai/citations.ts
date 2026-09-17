import type { Citation, EvidenceContext } from "./types";

export function validateCitations(citations: Citation[], evidence: EvidenceContext[]): Citation[] {
  const byId = new Map(evidence.map((item) => [item.id, item]));
  return citations.filter((citation) => {
    const item = byId.get(citation.evidenceId);
    if (!item || !item.sourcePageUrl) return false;
    try {
      const url = new URL(citation.sourcePageUrl);
      const evidenceUrl = new URL(item.sourcePageUrl);
      return ["http:", "https:"].includes(url.protocol) && url.href === evidenceUrl.href;
    } catch {
      return false;
    }
  });
}

export function citationsAreValid(citations: Citation[], evidence: EvidenceContext[]): boolean {
  return citations.length === validateCitations(citations, evidence).length;
}
