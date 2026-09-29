/**
 * P117 — blocked-word detection for community posts (Blueprint 23 minimum).
 *
 * This is a DISCLOSED STARTER LIST (spam/gambling/loan solicitations), not an
 * exhaustive profanity filter. Matching is deterministic: NFKC-normalized,
 * lowercased input; Thai tokens match as substrings (Thai has no word
 * boundaries), English tokens match on ASCII word boundaries.
 *
 * Rejection happens BEFORE any persistence — a blocked post never becomes a
 * row of any kind, so a false positive can never leak into official data.
 */

const THAI_BLOCKED = [
  "คาสิโน",
  "เครดิตฟรี",
  "บาคาร่า",
  "แทงบอล",
  "พนันออนไลน์",
  "เว็บพนัน",
  "หวยออนไลน์",
  "แอดไลน์รับ",
  "ปล่อยสินเชื่อ",
  "ให้กู้ยืม",
];

const ENGLISH_BLOCKED = ["casino", "viagra", "pornhub"];

export function normalizeForBlocklist(text: string): string {
  return text.normalize("NFKC").toLowerCase();
}

/** Returns the matched blocked term, or null when the text is clean. */
export function findBlockedTerm(raw: string): string | null {
  const text = normalizeForBlocklist(raw);
  for (const term of THAI_BLOCKED) {
    if (text.includes(normalizeForBlocklist(term))) return term;
  }
  for (const term of ENGLISH_BLOCKED) {
    const pattern = new RegExp(`(?<![a-z0-9])${term}(?![a-z0-9])`);
    if (pattern.test(text)) return term;
  }
  return null;
}
