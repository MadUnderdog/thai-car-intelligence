import { createHash, randomBytes } from "crypto";

/**
 * Anonymous, pseudonymous identity for community participation.
 * - voterToken: persisted in an httpOnly cookie (stable identity per browser,
 *   enables one-vote-per-comment and one-report-per-comment uniqueness).
 * - ipAddressHash: salted SHA-256 of the request IP, stored for abuse
 *   investigation only. Never the raw IP.
 */
const TOKEN_COOKIE = "tci_token";

export function getTokenCookieName(): string {
  return TOKEN_COOKIE;
}

export function newToken(): string {
  return randomBytes(24).toString("hex");
}

export function hashIp(ip: string | null | undefined): string {
  const salt = process.env.COMMUNITY_IP_SALT || "tci-fallback-salt";
  return createHash("sha256").update(`${salt}:${ip || "unknown"}`).digest("hex");
}

export function extractIp(headers: Headers): string | null {
  const fwd = headers.get("x-forwarded-for");
  if (fwd) return fwd.split(",")[0].trim();
  return headers.get("x-real-ip");
}
