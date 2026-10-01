/**
 * P116 — vehicle detail view helpers (Blueprint 86/87 + tier-honest marks).
 *
 * Fallback rules: never invent an asset or a URL. No image → placeholder
 * (optionally linking the manufacturer's official site). No verified brochure
 * → "โบรชัวร์จากผู้ผลิต" pointing at the official site when known, plain text
 * otherwise.
 */

export type ImageBlock = { kind: "image" | "fallback" | "placeholder"; href: string | null };
export type BrochureBlock = {
  title: string;
  href: string | null;
  sourceName: string | null;
  verifiedAt: string | null;
  verified: boolean;
};

/** Spec "verified" marks: ONLY primary_official rows may claim official. */
export function specEvidenceFlags(rows: { sourceTier?: string | null }[]): boolean {
  return rows.some((row) => row?.sourceTier === "primary_official");
}

export function imageBlock(images: { url: string; role?: string | null }[], officialUrl: string | null): ImageBlock {
  const hero = images.find((img) => img.role === "hero") ?? images[0];
  if (hero) return { kind: "image", href: hero.url ?? null };
  if (officialUrl) return { kind: "fallback", href: officialUrl };
  return { kind: "placeholder", href: null };
}

export function brochureBlock(
  doc: { title?: string | null; url?: string | null; sourceName?: string | null; verifiedAt?: string | null; documentStatus?: string | null } | null,
  officialUrl: string | null,
): BrochureBlock {
  if (doc && doc.url) {
    return {
      title: doc.title || "โบรชัวร์จากผู้ผลิต",
      href: doc.url,
      sourceName: doc.sourceName ?? null,
      verifiedAt: doc.verifiedAt ?? null,
      verified: doc.documentStatus === "VERIFIED",
    };
  }
  return { title: "โบรชัวร์จากผู้ผลิต", href: officialUrl, sourceName: null, verifiedAt: null, verified: false };
}
