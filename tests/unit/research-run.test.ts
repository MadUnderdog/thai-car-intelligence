import { describe, expect, it } from "vitest";
import { runResearch, type ResearchRunInput } from "../../workers/research/run";
import { validateResearchRunInput } from "../../scripts/research-model";

const input: ResearchRunInput = {
  model: "Yaris", officialDomains: ["toyota.co.th"], seedPageUrls: ["https://toyota.co.th/yaris", "https://toyota.co.th/failed"], discoveryQueries: ["Yaris brochure"], year: 2025,
};
const html = '<a href="/files/yaris-2025-th.pdf" download="Brochure">Yaris brochure</a><img src="/img/yaris.jpg" alt="hero">';
function mockClient() {
  const runs: Array<Record<string, unknown>> = [];
  const candidates: Array<Record<string, unknown>> = [];
  return {
    runs, candidates,
    researchRun: {
      create: async ({ data }: { data: Record<string, unknown> }) => { runs.push({ id: "run-1", ...data }); return { id: "run-1" }; },
      update: async ({ data }: { where: { id: string }; data: Record<string, unknown> }) => { Object.assign(runs[0], data); },
    },
    researchCandidate: { createMany: async ({ data }: { data: Array<Record<string, unknown>> }) => { candidates.push(...data); } },
  };
}
function response(body: string, status = 200, contentType = "text/html") { return new Response(body, { status, headers: { "content-type": contentType } }); }

describe("persisted research discovery", () => {
  it("rejects malformed CLI input before research can start", () => {
    expect(() => validateResearchRunInput({ officialDomains: ["https://toyota.co.th"], seedPageUrls: ["not-a-url"], discoveryQueries: [] })).toThrow();
    expect(() => validateResearchRunInput({ officialDomains: ["toyota.co.th"], seedPageUrls: ["https://toyota.co.th/yaris"], discoveryQueries: ["Yaris"] })).not.toThrow();
  });

  it("persists document and image candidates with source provenance", async () => {
    const client = mockClient();
    const result = await runResearch({ ...input, seedPageUrls: [input.seedPageUrls[0]] }, { client, fetch: async () => response(html), now: () => new Date("2026-01-01T00:00:00Z"), safeFetchOptions: { resolveDns: false } });
    expect(result.status).toBe("SUCCEEDED");
    expect(result.report.status).toBe("discovered");
    expect(client.candidates).toHaveLength(2);
    expect(client.candidates.every((candidate) => candidate.status === "PENDING")).toBe(true);
    expect(client.candidates[0].evidence).toBe("https://toyota.co.th/yaris");
    expect(client.runs[0]).toMatchObject({ pagesChecked: 1, documentsFound: 1, imagesFound: 1 });
  });

  it("preserves successful pages and marks mixed fetches partial success", async () => {
    const client = mockClient();
    const fetch: typeof globalThis.fetch = async (input) => String(input).endsWith("failed") ? Promise.reject(new Error("timeout")) : response(html);
    const result = await runResearch(input, { client, fetch, safeFetchOptions: { resolveDns: false } });
    expect(result.status).toBe("PARTIAL_SUCCESS");
    expect(result.report.pagesChecked).toEqual(["https://toyota.co.th/yaris"]);
    expect(result.report.errors).toHaveLength(1);
  });

  it("records not_found without inventing candidates", async () => {
    const client = mockClient();
    const result = await runResearch({ ...input, seedPageUrls: ["https://toyota.co.th/empty"] }, { client, fetch: async () => response("<p>nothing</p>"), safeFetchOptions: { resolveDns: false } });
    expect(result.status).toBe("SUCCEEDED");
    expect(result.report).toMatchObject({ status: "not_found", candidates: [], pagesChecked: ["https://toyota.co.th/empty"] });
    expect(client.candidates).toHaveLength(0);
  });

  it("does not fetch or register pages outside official domains", async () => {
    const client = mockClient(); let fetches = 0;
    const result = await runResearch({ ...input, seedPageUrls: ["https://evil.example/yaris"] }, { client, fetch: async () => { fetches += 1; return response(html); }, safeFetchOptions: { resolveDns: false } });
    expect(fetches).toBe(0);
    expect(result.status).toBe("FAILED");
    expect(result.report.errors[0].error).toContain("allow-list");
    expect(client.candidates).toHaveLength(0);
  });

  it("marks the run failed and rethrows when candidate persistence fails", async () => {
    const client = mockClient();
    client.researchCandidate.createMany = async () => { throw new Error("candidate database unavailable"); };
    await expect(runResearch({ ...input, seedPageUrls: [input.seedPageUrls[0]] }, { client, fetch: async () => response(html), safeFetchOptions: { resolveDns: false } })).rejects.toThrow("candidate database unavailable");
    expect(client.runs[0]).toMatchObject({ status: "FAILED", error: "candidate database unavailable" });
  });

  it("attempts failed recovery and preserves the final update error", async () => {
    const client = mockClient();
    let updates = 0;
    client.researchRun.update = async ({ data }) => { updates += 1; Object.assign(client.runs[0], data); throw new Error(updates === 1 ? "final update unavailable" : "recovery unavailable"); };
    await expect(runResearch({ ...input, seedPageUrls: [input.seedPageUrls[0]] }, { client, fetch: async () => response(html), safeFetchOptions: { resolveDns: false } })).rejects.toThrow("final update unavailable");
    expect(updates).toBe(2);
    expect(client.runs[0]).toMatchObject({ status: "FAILED", error: "final update unavailable" });
  });
});
