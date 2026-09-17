import { lookup } from "node:dns/promises";
import { isIP } from "node:net";

export type UrlRejectionReason =
  | "invalid-url"
  | "unsupported-scheme"
  | "credentials-not-allowed"
  | "missing-hostname"
  | "blocked-hostname"
  | "blocked-address"
  | "dns-resolution-failed";

export type UrlPolicyResult =
  | { ok: true; url: URL; addresses: string[] }
  | { ok: false; reason: UrlRejectionReason; message: string };

export interface UrlPolicyOptions {
  /** Resolve hostnames before allowing them. Keep enabled outside deterministic tests. */
  resolveDns?: boolean;
  /** Injectable resolver for callers/tests; it must return all address records. */
  resolve?: (hostname: string) => Promise<ReadonlyArray<string>>;
}

const BLOCKED_HOSTNAMES = new Set([
  "localhost",
  "localhost.localdomain",
  "metadata",
  "metadata.google.internal",
  "instance-data.ec2.internal",
]);

function isBlockedHostname(hostname: string): boolean {
  const name = hostname.toLowerCase().replace(/\.$/, "");
  return BLOCKED_HOSTNAMES.has(name) || name.endsWith(".localhost");
}

function ipv4ToNumber(address: string): number | undefined {
  const octets = address.split(".");
  if (octets.length !== 4 || octets.some((part) => !/^\d+$/.test(part))) return undefined;
  const values = octets.map(Number);
  if (values.some((value) => value > 255)) return undefined;
  return ((values[0] * 256 + values[1]) * 256 + values[2]) * 256 + values[3];
}

function ipv4InRange(address: string, start: string, end: string): boolean {
  const value = ipv4ToNumber(address);
  const lower = ipv4ToNumber(start);
  const upper = ipv4ToNumber(end);
  return value !== undefined && lower !== undefined && upper !== undefined && value >= lower && value <= upper;
}

function ipv6ToBytes(address: string): number[] | undefined {
  let value = address.toLowerCase().replace(/^\[|\]$/g, "");
  if (value.includes("%")) return undefined; // zone identifiers are not valid public URL destinations
  const embedded = value.includes(".");
  if (embedded) {
    const lastColon = value.lastIndexOf(":");
    const ipv4 = ipv4ToNumber(value.slice(lastColon + 1));
    if (lastColon < 0 || ipv4 === undefined) return undefined;
    value = `${value.slice(0, lastColon)}:${(ipv4 >>> 16).toString(16)}:${(ipv4 & 0xffff).toString(16)}`;
  }
  const halves = value.split("::");
  if (halves.length > 2) return undefined;
  const left = halves[0] ? halves[0].split(":") : [];
  const right = halves.length === 2 && halves[1] ? halves[1].split(":") : [];
  if ([...left, ...right].some((part) => !/^[\da-f]{1,4}$/.test(part))) return undefined;
  const missing = 8 - left.length - right.length;
  if ((halves.length === 1 && missing !== 0) || (halves.length === 2 && missing < 1)) return undefined;
  return [...left, ...Array.from({ length: missing }, () => "0"), ...right]
    .flatMap((part) => [parseInt(part, 16) >> 8, parseInt(part, 16) & 255]);
}

function isBlockedAddress(address: string): boolean {
  const version = isIP(address);
  if (version === 4) {
    return (
      ipv4InRange(address, "0.0.0.0", "0.255.255.255") ||
      ipv4InRange(address, "10.0.0.0", "10.255.255.255") ||
      ipv4InRange(address, "100.64.0.0", "100.127.255.255") ||
      ipv4InRange(address, "127.0.0.0", "127.255.255.255") ||
      ipv4InRange(address, "169.254.0.0", "169.254.255.255") ||
      ipv4InRange(address, "172.16.0.0", "172.31.255.255") ||
      ipv4InRange(address, "192.0.0.0", "192.0.0.255") ||
      ipv4InRange(address, "192.0.2.0", "192.0.2.255") ||
      ipv4InRange(address, "192.88.99.0", "192.88.99.255") ||
      ipv4InRange(address, "192.168.0.0", "192.168.255.255") ||
      ipv4InRange(address, "198.18.0.0", "198.19.255.255") ||
      ipv4InRange(address, "198.51.100.0", "198.51.100.255") ||
      ipv4InRange(address, "203.0.113.0", "203.0.113.255") ||
      ipv4InRange(address, "224.0.0.0", "255.255.255.255")
    );
  }
  if (version !== 6) return true;
  const bytes = ipv6ToBytes(address);
  if (!bytes) return true;
  const first = (bytes[0] << 8) | bytes[1];
  const second = (bytes[2] << 8) | bytes[3];
  const isUnspecified = bytes.every((byte) => byte === 0);
  const isLoopback = isUnspecified === false && bytes.slice(0, 15).every((byte) => byte === 0) && bytes[15] === 1;
  const isMappedV4 = bytes.slice(0, 10).every((byte) => byte === 0) && bytes[10] === 255 && bytes[11] === 255;
  const mapped = `${bytes[12]}.${bytes[13]}.${bytes[14]}.${bytes[15]}`;
  return (
    isUnspecified || isLoopback || (isMappedV4 && isBlockedAddress(mapped)) ||
    (first & 0xfe00) === 0xfc00 || // unique local (fc00::/7)
    (first & 0xffc0) === 0xfe80 || // link-local (fe80::/10)
    bytes[0] === 0xff || // multicast (ff00::/8)
    (first === 0x0100 && bytes.slice(2, 8).every((byte) => byte === 0)) || // discard-only (100::/64)
    (first === 0x2001 && second === 0x0002 && bytes[4] === 0 && bytes[5] === 0) || // benchmarking (2001:2::/48)
    (first === 0x2001 && (second & 0xfff0) === 0x0010) || // ORCHIDv2 and reserved (2001:10::/28)
    (first === 0x2001 && second === 0x0db8) // documentation range
  );
}

/** Validate a URL before any fetch. DNS failures are rejected, not treated as public. */
export async function validateUrl(input: string, options: UrlPolicyOptions = {}): Promise<UrlPolicyResult> {
  let url: URL;
  try {
    url = new URL(input);
  } catch {
    return { ok: false, reason: "invalid-url", message: "The value is not a valid URL." };
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return { ok: false, reason: "unsupported-scheme", message: "Only HTTP and HTTPS URLs are allowed." };
  }
  if (url.username || url.password) {
    return { ok: false, reason: "credentials-not-allowed", message: "URLs containing credentials are not allowed." };
  }
  const hostname = url.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (!hostname) return { ok: false, reason: "missing-hostname", message: "URL has no hostname." };
  if (isBlockedHostname(hostname) || (isIP(hostname) > 0 && isBlockedAddress(hostname))) {
    return { ok: false, reason: "blocked-hostname", message: "The destination hostname is not public." };
  }

  if (!isIP(hostname) && options.resolveDns !== false) {
    try {
      const resolver = options.resolve ?? (async (name: string) => (await lookup(name, { all: true })).map(({ address }) => address));
      const addresses = [...(await resolver(hostname))];
      if (addresses.length === 0 || addresses.some(isBlockedAddress)) {
        return { ok: false, reason: "blocked-address", message: "The hostname resolves to a non-public address." };
      }
      return { ok: true, url, addresses };
    } catch {
      return { ok: false, reason: "dns-resolution-failed", message: "The hostname could not be resolved safely." };
    }
  }
  return { ok: true, url, addresses: isIP(hostname) ? [hostname] : [] };
}

/** Domain allow-list check; matches only the exact domain or a dot-delimited subdomain. */
export function isAllowedDomain(input: string | URL, allowedDomains: Iterable<string>): boolean {
  let hostname: string;
  try {
    hostname = typeof input === "string" ? new URL(input).hostname : input.hostname;
  } catch {
    return false;
  }
  const candidate = hostname.toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, "");
  return [...allowedDomains].some((domain) => {
    const normalized = domain.toLowerCase().trim().replace(/^\.|\.$/g, "");
    return normalized !== "" && (candidate === normalized || candidate.endsWith(`.${normalized}`));
  });
}

export { isBlockedAddress };
