import { describe, expect, it, vi } from "vitest";
import { safeFetch } from "../../lib/security/safe-fetch";

const publicDns = async (): Promise<ReadonlyArray<string>> => ["93.184.216.34"];

describe("safeFetch", () => {
  it("validates redirect targets before following them", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 302, headers: { Location: "http://127.0.0.1/admin" } }));

    await expect(
      safeFetch("https://example.test/start", { method: "GET" }, {
        fetch: fetchMock,
        resolve: publicDns,
      }),
    ).rejects.toThrow(/not public/i);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/start",
      expect.objectContaining({ redirect: "manual" }),
    );
  });

  it("follows a validated redirect and returns the final response", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 301, headers: { Location: "/next" } }))
      .mockResolvedValueOnce(new Response("ok", { status: 200 }));

    const response = await safeFetch("https://example.test/start", undefined, {
      fetch: fetchMock,
      resolve: publicDns,
    });

    expect(await response.text()).toBe("ok");
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://example.test/next",
      expect.objectContaining({ redirect: "manual" }),
    );
  });

  it("enforces the redirect limit", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(null, { status: 302, headers: { Location: "/again" } }),
    );

    await expect(
      safeFetch("https://example.test/start", undefined, {
        fetch: fetchMock,
        resolve: publicDns,
        maxRedirects: 2,
      }),
    ).rejects.toThrow(/redirect limit/i);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("enforces the response-size limit", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response("12345"));

    await expect(
      safeFetch("https://example.test/large", undefined, {
        fetch: fetchMock,
        resolve: publicDns,
        maxResponseBytes: 4,
      }),
    ).rejects.toThrow(/response size/i);
  });
});
