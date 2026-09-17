/** Deterministic, DOM-free extraction of links and image metadata from HTML. */

export type CandidateKind = "document" | "image";
export type DiscoveryMethod =
  | "href"
  | "src"
  | "srcset"
  | "lazy-src"
  | "lazy-srcset"
  | "og:image"
  | "twitter:image"
  | "json-ld:image";

export interface HtmlCandidate {
  url: string;
  kind: CandidateKind;
  sourcePageUrl: string;
  discoveryMethod: DiscoveryMethod;
  label?: string;
  width?: number;
}

const DOCUMENT_RE = /\.(?:pdf|docx?|xlsx?|pptx?|zip)(?:[?#]|$)/i;
const IMAGE_RE = /\.(?:jpe?g|png|webp|avif|gif|svg)(?:[?#]|$)/i;
const ATTR_RE = /([:\w-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/gi;
const TAG_RE = /<([a-z][\w:-]*)\b([^>]*)>/gi;
const URL_ATTRS = ["href", "src", "data-src", "data-lazy-src", "data-original", "data-image", "data-url"] as const;
const SRCSET_ATTRS = ["srcset", "data-srcset", "data-lazy-srcset"] as const;

function attributeMap(raw: string): Map<string, string> {
  const result = new Map<string, string>();
  for (const match of raw.matchAll(ATTR_RE)) {
    const value = match[2] ?? match[3] ?? match[4];
    if (value !== undefined) result.set(match[1].toLowerCase(), value.trim());
  }
  return result;
}

function resolveUrl(value: string, pageUrl: string): string | undefined {
  const cleaned = value.trim().replace(/^['"]|['"]$/g, "");
  if (!cleaned || cleaned.startsWith("#") || /^(?:data|javascript|mailto|tel):/i.test(cleaned)) return undefined;
  try {
    const url = new URL(cleaned, pageUrl);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : undefined;
  } catch {
    return undefined;
  }
}

function isDocument(url: string, label = ""): boolean {
  return DOCUMENT_RE.test(url) || /\b(?:download|brochure|catalog(?:ue)?|spec(?:ification)?|manual|ราคา|โบรชัวร์)\b/i.test(label);
}

function isImage(url: string, label = ""): boolean {
  return IMAGE_RE.test(url) || /\b(?:image|gallery|photo|hero|banner|cover|thumbnail)\b/i.test(label);
}

function addCandidate(list: HtmlCandidate[], seen: Set<string>, candidate: HtmlCandidate): void {
  const key = `${candidate.kind}|${candidate.url}`;
  if (!seen.has(key)) {
    seen.add(key);
    list.push(candidate);
  }
}

function parseSrcset(value: string): Array<{ url: string; width?: number }> {
  return value.split(",").flatMap((part) => {
    const pieces = part.trim().split(/\s+/);
    if (!pieces[0]) return [];
    const descriptor = pieces[1]?.match(/^(\d+)w$/i);
    return [{ url: pieces[0], width: descriptor ? Number(descriptor[1]) : undefined }];
  });
}

/** Extract document and image candidates without fetching or executing HTML. */
export function extractHtmlCandidates(html: string, pageUrl: string): HtmlCandidate[] {
  const candidates: HtmlCandidate[] = [];
  const seen = new Set<string>();
  const add = (value: string, method: DiscoveryMethod, kind?: CandidateKind, label?: string, width?: number) => {
    const url = resolveUrl(value, pageUrl);
    if (!url) return;
    const resolvedKind = kind ?? (isDocument(url, label) ? "document" : isImage(url, label) ? "image" : undefined);
    if (!resolvedKind) return;
    addCandidate(candidates, seen, { url, kind: resolvedKind, sourcePageUrl: pageUrl, discoveryMethod: method, label, width });
  };

  for (const match of html.matchAll(TAG_RE)) {
    const tag = match[1].toLowerCase();
    const attrs = attributeMap(match[2]);
    const label = [attrs.get("title"), attrs.get("alt"), attrs.get("aria-label"), attrs.get("download")].filter(Boolean).join(" ");
    for (const name of URL_ATTRS) {
      const value = attrs.get(name);
      if (value) add(value, name === "src" ? "src" : name === "href" ? "href" : "lazy-src", tag === "img" ? "image" : undefined, label);
    }
    for (const name of SRCSET_ATTRS) {
      const value = attrs.get(name);
      if (value) for (const item of parseSrcset(value)) add(item.url, name === "srcset" ? "srcset" : "lazy-srcset", "image", label, item.width);
    }
    if (tag === "meta") {
      const property = (attrs.get("property") ?? attrs.get("name") ?? "").toLowerCase();
      const content = attrs.get("content");
      if (content && property === "og:image") add(content, "og:image", "image");
      if (content && (property === "twitter:image" || property === "twitter:image:src")) add(content, "twitter:image", "image");
    }
  }

  for (const script of html.matchAll(/<script\b[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)) {
    try {
      const json: unknown = JSON.parse(script[1].trim());
      const values: unknown[] = [];
      const collect = (value: unknown) => {
        if (typeof value === "string") values.push(value);
        else if (Array.isArray(value)) value.forEach(collect);
        else if (value && typeof value === "object") Object.values(value).forEach(collect);
      };
      if (json && typeof json === "object") {
        const object = json as Record<string, unknown>;
        collect(object.image);
        if (Array.isArray(object["@graph"])) object["@graph"].forEach((entry) => collect((entry as Record<string, unknown>)?.image));
      }
      for (const value of values) add(value as string, "json-ld:image", "image");
    } catch { /* malformed JSON-LD is ignored deterministically */ }
  }
  return candidates;
}

export const discoverHtmlCandidates = extractHtmlCandidates;
