import { extractHtmlCandidates, type HtmlCandidate } from "../../lib/sources/discovery/html-candidates";

export type ImageRole = "hero" | "gallery" | "thumbnail" | "logo" | "unknown";
export interface ImageCandidate extends HtmlCandidate { kind: "image"; role: ImageRole; }

function roleFor(candidate: HtmlCandidate): ImageRole {
  const text = `${candidate.url} ${candidate.label ?? ""}`.toLowerCase();
  // Page chrome is not vehicle media. Check before size/name heuristics so an
  // icon named "small" cannot become a meaningful thumbnail.
  if (/logo|brand|ตราสัญลักษณ์|icon|menu|arrow|chevron|caret|nav(?:igation)?/.test(text)) return "unknown";
  if (/thumb|thumbnail|small|preview/.test(text) || (candidate.width !== undefined && candidate.width < 600)) return "thumbnail";
  if (/gallery|photo|ด้าน|front|rear|interior/.test(text)) return "gallery";
  if (/hero|banner|cover|featured/.test(text) || (candidate.width !== undefined && candidate.width >= 1200)) return "hero";
  return "unknown";
}

/** Choose the largest declared srcset width, falling back to document order. */
export function selectHighestResolutionSrcset(candidates: readonly HtmlCandidate[]): HtmlCandidate | undefined {
  return candidates.filter((candidate) => candidate.kind === "image").reduce<HtmlCandidate | undefined>((best, candidate) =>
    !best || (candidate.width ?? 0) > (best.width ?? 0) ? candidate : best, undefined);
}

/** Extract image candidates and attach conservative, explainable role hints. */
export function discoverImages(html: string, pageUrl: string): ImageCandidate[] {
  return extractHtmlCandidates(html, pageUrl).filter((candidate): candidate is HtmlCandidate & { kind: "image" } => candidate.kind === "image")
    .map((candidate) => ({ ...candidate, role: roleFor(candidate) }));
}

export const collectImageCandidates = discoverImages;
