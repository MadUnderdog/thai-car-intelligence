import { describe, expect, it } from "vitest";
import { isAllowedDomain, isBlockedAddress, validateUrl } from "../../lib/security/url-policy";

describe("validateUrl", () => {
  it("accepts a public HTTPS URL without doing DNS in the unit test", async () => {
    await expect(
      validateUrl("https://example.com/research/article", { resolveDns: false }),
    ).resolves.toMatchObject({ ok: true });
  });

  it.each([
    "http://localhost/admin",
    "http://127.0.0.1:3000/",
    "http://192.168.1.10/internal",
    "http://169.254.169.254/latest/meta-data/",
    "https://user:password@example.com/private",
    "ftp://example.com/file",
    "http://192.0.2.1/",
    "http://198.51.100.1/",
    "http://203.0.113.1/",
    "http://192.88.99.1/",
    "http://198.18.0.1/",
  ])("rejects unsafe URL %s", async (url) => {
    await expect(validateUrl(url, { resolveDns: false })).resolves.toMatchObject({
      ok: false,
    });
  });

  it.each(["ff00::1", "100::1", "2001:2::1", "2001:10::1", "2001:db8::1"])(
    "blocks IPv6 special-use address %s",
    (address) => expect(isBlockedAddress(address)).toBe(true),
  );

  it("rejects a hostname when any DNS answer is private", async () => {
    await expect(
      validateUrl("https://mixed.example.test", {
        resolve: async () => ["93.184.216.34", "10.0.0.1"],
      }),
    ).resolves.toMatchObject({ ok: false, reason: "blocked-address" });
  });

  it("rejects DNS failures", async () => {
    await expect(
      validateUrl("https://unresolvable.example.test", {
        resolve: async () => {
          throw new Error("DNS failure");
        },
      }),
    ).resolves.toMatchObject({ ok: false, reason: "dns-resolution-failed" });
  });
});

describe("isAllowedDomain", () => {
  it("matches an exact domain and its subdomains, but not lookalikes", () => {
    expect(isAllowedDomain("https://news.example.com/story", ["example.com"])).toBe(true);
    expect(isAllowedDomain("https://example.com", ["example.com"])).toBe(true);
    expect(isAllowedDomain("https://example.com.evil.test", ["example.com"])).toBe(false);
  });
});
