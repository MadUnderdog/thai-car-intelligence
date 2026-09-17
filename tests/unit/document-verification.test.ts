import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { describe, expect, it, vi } from "vitest";
import { verifyBrochureDocument, selectOcrLanguage, shouldUseOcr, type ExtractedPageSnippet } from "../../workers/verification/document";

const pdfUrl = "https://toyota.co.th/files/corolla-2025-th.pdf";
const sourcePageUrl = "https://toyota.co.th/cars/corolla";
const safeFetchOptions = { resolveDns: false };

async function fixtureResponse(contentType = "application/pdf"): Promise<Response> {
  const body = await readFile(new URL("../fixtures/brochure.pdf", import.meta.url));
  return new Response(body, { status: 200, headers: { "content-type": contentType } });
}

describe("OCR capability helpers", () => {
  const emptyPages: ExtractedPageSnippet[] = [{ pageNumber: 1, text: "" }, { pageNumber: 2, text: "short" }];

  it("detects scanned pages and selects Thai plus English when installed", () => {
    expect(shouldUseOcr(emptyPages)).toBe(true);
    expect(selectOcrLanguage(["eng", "tha"])).toBe("eng+tha");
    expect(selectOcrLanguage(["eng"])).toBe("eng");
    expect(selectOcrLanguage(["eng"], "tha")).toBeNull();
  });

  it("uses OCR output with page numbers when the capability is available", async () => {
    const body = await readFile(new URL("../fixtures/brochure.pdf", import.meta.url));
    const commands = vi.fn(async (command: string, args: string[]) => {
      if (command === "pdfinfo") return { stdout: "Pages: 2\n" };
      if (command === "pdftotext") return { stdout: "" };
      if (command === "tesseract" && args[0] === "--list-langs") return { stdout: "List of available languages in /usr/share/tessdata/:\neng\ntha\n" };
      if (command === "pdftoppm") return { stdout: "" };
      if (command === "tesseract") return { stdout: "Camry Thailand 2025" };
      throw new Error(`unexpected command ${command}`);
    });
    const result = await verifyBrochureDocument({ documentUrl: pdfUrl, sourcePageUrl, expectedModel: "Camry", expectedMarket: "Thailand", expectedYear: 2025, fetch: vi.fn(async () => new Response(body, { status: 200, headers: { "content-type": "application/pdf" } })), commandRunner: commands, tempDirectory: "/tmp", safeFetchOptions });
    expect(result).toMatchObject({ status: "VERIFIED", extractionMethod: "ocr", extractionStatus: "SUCCEEDED" });
    expect(result.extractedPageSnippets.map((page) => page.pageNumber)).toEqual([1, 2]);
    expect(commands).toHaveBeenCalledWith("tesseract", expect.arrayContaining(["-l", "eng+tha"]), expect.anything());
  });

  it("does not treat unsupported OCR capability as verification", async () => {
    const body = await readFile(new URL("../fixtures/brochure.pdf", import.meta.url));
    const commands = vi.fn(async (command: string, args: string[]) => {
      void args;
      if (command === "pdfinfo") return { stdout: "Pages: 2\n" };
      if (command === "pdftotext") return { stdout: "" };
      throw new Error(`spawn ${command} ENOENT`);
    });
    const result = await verifyBrochureDocument({ documentUrl: pdfUrl, sourcePageUrl, expectedModel: "Corolla", fetch: vi.fn(async () => new Response(body, { status: 200, headers: { "content-type": "application/pdf" } })), commandRunner: commands, tempDirectory: "/tmp", safeFetchOptions });
    expect(result).toMatchObject({ status: "NEEDS_REVIEW", extractionMethod: "pdftotext", extractionStatus: "OCR_UNAVAILABLE", pageCount: 2 });
    expect(result.error).toMatch(/OCR unavailable/i);
  });
});

describe("verifyBrochureDocument", () => {
  it("hashes and parses a PDF, preserving page numbers and matching identity", async () => {
    const body = await readFile(new URL("../fixtures/brochure.pdf", import.meta.url));
    const result = await verifyBrochureDocument({ documentUrl: pdfUrl, sourcePageUrl, expectedModel: "Corolla", expectedMarket: "Thailand", expectedYear: 2025, fetch: vi.fn(async () => fixtureResponse()), tempDirectory: "/tmp", safeFetchOptions });
    expect(result).toMatchObject({ status: "VERIFIED", modelMatch: true, marketMatch: true, yearMatch: true, officialLinkMatch: true, pageCount: 2, rightsStatus: "unknown", fileHash: createHash("sha256").update(body).digest("hex") });
    expect(result.extractedPageSnippets).toHaveLength(2);
    expect(result.extractedPageSnippets[0].pageNumber).toBe(1);
  });

  it("rejects a non-PDF content type", async () => {
    const result = await verifyBrochureDocument({ documentUrl: pdfUrl, sourcePageUrl, expectedModel: "Corolla", fetch: vi.fn(async () => fixtureResponse("text/html")), safeFetchOptions });
    expect(result.status).toBe("FAILED");
    expect(result.error).toMatch(/content type/i);
  });

  it("flags a parsed but wrong document for review", async () => {
    const result = await verifyBrochureDocument({ documentUrl: pdfUrl, sourcePageUrl, expectedModel: "Yaris", expectedMarket: "Thailand", expectedYear: 2025, fetch: vi.fn(async () => fixtureResponse()), safeFetchOptions });
    expect(result.status).toBe("NEEDS_REVIEW");
    expect(result.modelMatch).toBe(false);
  });

  it("returns FAILED for fetch timeouts/errors without writing a public file", async () => {
    const result = await verifyBrochureDocument({ documentUrl: pdfUrl, sourcePageUrl, expectedModel: "Corolla", fetch: vi.fn(async () => { throw new Error("The operation was aborted"); }), safeFetchOptions });
    expect(result.status).toBe("FAILED");
    expect(result.fileHash).toBeNull();
  });
});
