import { createHash } from "node:crypto";
import { execFile as execFileCallback } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { safeFetch, type SafeFetchOptions } from "../../lib/security/safe-fetch";

const defaultExecFile = promisify(execFileCallback);
const DEFAULT_MAX_BYTES = 20 * 1024 * 1024;
const SNIPPET_LENGTH = 800;
const MAX_OCR_PAGES = 50;
const MAX_COMMAND_BUFFER = 2 * 1024 * 1024;
const COMMAND_TIMEOUT_MS = 30_000;

type PdfMetadata = Record<string, string>;
type CommandRunner = (command: string, args: string[], options: { encoding: "utf8"; maxBuffer: number; timeout: number }) => Promise<{ stdout: string }>;

const runDefaultCommand: CommandRunner = async (command, args, options) => defaultExecFile(command, args, options) as unknown as Promise<{ stdout: string }>;
export interface ExtractedPageSnippet { pageNumber: number; text: string; }
export interface BrochureVerificationInput {
  documentUrl: string;
  sourcePageUrl: string;
  expectedModel?: string;
  expectedMarket?: string;
  expectedYear?: number | string;
  rightsStatus?: "unknown" | "reference-only";
  fetch?: typeof fetch;
  tempDirectory?: string;
  maxBytes?: number;
  safeFetchOptions?: Omit<SafeFetchOptions, "fetch" | "maxResponseBytes">;
  /** Test seam and optional worker override; production defaults to child_process. */
  commandRunner?: CommandRunner;
  ocrLanguage?: string;
}
export interface BrochureVerificationResult {
  documentUrl: string;
  sourcePageUrl: string;
  modelMatch: boolean | null;
  marketMatch: boolean | null;
  yearMatch: boolean | null;
  officialLinkMatch: boolean;
  verificationScore: number;
  status: "VERIFIED" | "NEEDS_REVIEW" | "FAILED";
  fileHash: string | null;
  pageCount: number | null;
  metadata: PdfMetadata;
  extractedPageSnippets: ExtractedPageSnippet[];
  extractionMethod: "pdftotext" | "ocr" | null;
  extractionStatus: "SUCCEEDED" | "FAILED" | "OCR_UNAVAILABLE";
  rightsStatus: "unknown" | "reference-only";
  error?: string;
}

function emptyResult(input: BrochureVerificationInput, error: string): BrochureVerificationResult {
  return {
    documentUrl: input.documentUrl, sourcePageUrl: input.sourcePageUrl,
    modelMatch: null, marketMatch: null, yearMatch: null,
    officialLinkMatch: sameSite(input.documentUrl, input.sourcePageUrl), verificationScore: 0,
    status: "FAILED", fileHash: null, pageCount: null, metadata: {},
    extractedPageSnippets: [], extractionMethod: null, extractionStatus: "FAILED",
    rightsStatus: input.rightsStatus ?? "unknown", error,
  };
}

function sameSite(documentUrl: string, sourcePageUrl: string): boolean {
  try {
    const documentHost = new URL(documentUrl).hostname.toLowerCase().replace(/^www\./, "");
    const sourceHost = new URL(sourcePageUrl).hostname.toLowerCase().replace(/^www\./, "");
    return documentHost === sourceHost || documentHost.endsWith(`.${sourceHost}`) || sourceHost.endsWith(`.${documentHost}`);
  } catch { return false; }
}

function containsExpected(text: string, expected: string | number | undefined): boolean | null {
  if (expected === undefined || expected === "") return null;
  const value = String(expected).trim();
  if (!value) return null;
  return new RegExp(`(^|[^\\p{L}\\p{N}])${value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?=$|[^\\p{L}\\p{N}])`, "iu").test(text);
}

function parsePdfInfo(output: string): { pageCount: number | null; metadata: PdfMetadata } {
  const metadata: PdfMetadata = {};
  for (const line of output.split(/\r?\n/)) {
    const match = line.match(/^([^:]+):\s*(.*)$/);
    if (match && match[2]) metadata[match[1].trim()] = match[2].trim();
  }
  const pages = Number.parseInt(metadata.Pages ?? "", 10);
  return { pageCount: Number.isInteger(pages) && pages >= 0 ? pages : null, metadata };
}

async function inspectPdf(path: string, runCommand: CommandRunner): Promise<{ pageCount: number; metadata: PdfMetadata; pages: ExtractedPageSnippet[] }> {
  const info = await runCommand("pdfinfo", [path], { encoding: "utf8", maxBuffer: 256 * 1024, timeout: COMMAND_TIMEOUT_MS });
  const parsed = parsePdfInfo(info.stdout);
  if (!parsed.pageCount) throw new Error("PDF page count could not be determined.");
  const pages: ExtractedPageSnippet[] = [];
  for (let page = 1; page <= parsed.pageCount; page += 1) {
    const result = await runCommand("pdftotext", ["-layout", "-f", String(page), "-l", String(page), path, "-"], { encoding: "utf8", maxBuffer: MAX_COMMAND_BUFFER, timeout: COMMAND_TIMEOUT_MS });
    const text = result.stdout.replace(/\s+/g, " ").trim();
    pages.push({ pageNumber: page, text: text.slice(0, SNIPPET_LENGTH) });
  }
  return { pageCount: parsed.pageCount, metadata: parsed.metadata, pages };
}

/** Scans with mostly empty text extraction need an image OCR pass. */
export function shouldUseOcr(pages: ExtractedPageSnippet[]): boolean {
  if (!pages.length) return false;
  const emptyPages = pages.filter((page) => page.text.trim().length < 24).length;
  return emptyPages >= Math.ceil(pages.length / 2);
}

export function selectOcrLanguage(installedLanguages: string[], requested?: string): string | null {
  const languages = installedLanguages.map((language) => language.trim()).filter(Boolean);
  if (requested?.trim()) return requested.trim().split(/[+,]/).every((language) => languages.includes(language)) ? requested.trim() : null;
  if (languages.includes("eng") && languages.includes("tha")) return "eng+tha";
  if (languages.includes("tha")) return "tha";
  if (languages.includes("eng")) return "eng";
  return null;
}

async function ocrPages(path: string, directory: string, pages: ExtractedPageSnippet[], runCommand: CommandRunner, language: string): Promise<ExtractedPageSnippet[]> {
  if (pages.length > MAX_OCR_PAGES) throw new Error(`OCR page limit exceeded (${MAX_OCR_PAGES}).`);
  const ocrPages: ExtractedPageSnippet[] = [];
  for (const page of pages) {
    const prefix = join(directory, `page-${page.pageNumber}`);
    await runCommand("pdftoppm", ["-png", "-r", "150", "-scale-to", "2000", "-f", String(page.pageNumber), "-l", String(page.pageNumber), path, prefix], { encoding: "utf8", maxBuffer: 256 * 1024, timeout: COMMAND_TIMEOUT_MS });
    const imagePath = `${prefix}-${page.pageNumber}.png`;
    const result = await runCommand("tesseract", [imagePath, "stdout", "-l", language, "--psm", "3"], { encoding: "utf8", maxBuffer: MAX_COMMAND_BUFFER, timeout: COMMAND_TIMEOUT_MS });
    ocrPages.push({ pageNumber: page.pageNumber, text: result.stdout.replace(/\s+/g, " ").trim().slice(0, SNIPPET_LENGTH) });
  }
  return ocrPages;
}

async function detectOcrLanguage(runCommand: CommandRunner, requested?: string): Promise<string | null> {
  const result = await runCommand("tesseract", ["--list-langs"], { encoding: "utf8", maxBuffer: 256 * 1024, timeout: COMMAND_TIMEOUT_MS });
  return selectOcrLanguage(result.stdout.split(/\r?\n/).filter((line) => !/^list of available languages/i.test(line)), requested);
}

/** Verify a brochure without retaining or publishing its downloaded bytes. */
export async function verifyBrochureDocument(input: BrochureVerificationInput): Promise<BrochureVerificationResult> {
  const base = { ...input, rightsStatus: input.rightsStatus ?? "unknown" as const };
  const maxBytes = input.maxBytes ?? DEFAULT_MAX_BYTES;
  if (!Number.isInteger(maxBytes) || maxBytes <= 0) return emptyResult(base, "Invalid document size limit.");
  let response: Response;
  try {
    response = await safeFetch(input.documentUrl, { headers: { accept: "application/pdf" } }, {
      ...input.safeFetchOptions, fetch: input.fetch, maxResponseBytes: maxBytes,
    });
  } catch (error) {
    return emptyResult(base, error instanceof Error ? error.message : String(error));
  }
  if (!response.ok) return emptyResult(base, `Document fetch returned HTTP ${response.status}.`);
  const contentType = (response.headers.get("content-type") ?? "").split(";", 1)[0].trim().toLowerCase();
  if (contentType !== "application/pdf") return emptyResult(base, `Expected application/pdf content type, received ${contentType || "none"}.`);

  let directory: string | undefined;
  try {
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.byteLength > maxBytes) throw new Error("Document exceeds the configured size limit.");
    if (bytes.byteLength < 5 || new TextDecoder().decode(bytes.slice(0, 5)) !== "%PDF-") throw new Error("Downloaded document is not a PDF.");
    directory = await mkdtemp(join(input.tempDirectory ?? tmpdir(), "brochure-verification-"));
    const path = join(directory, "document.pdf");
    await writeFile(path, bytes, { mode: 0o600 });
    const fileHash = createHash("sha256").update(bytes).digest("hex");
    const runCommand = input.commandRunner ?? runDefaultCommand;
    const inspected = await inspectPdf(path, runCommand);
    let pages = inspected.pages;
    let extractionMethod: "pdftotext" | "ocr" = "pdftotext";
    let extractionStatus: "SUCCEEDED" | "FAILED" | "OCR_UNAVAILABLE" = "SUCCEEDED";
    let extractionWarning: string | undefined;
    if (shouldUseOcr(pages)) {
      let language: string | null = null;
      try {
        language = await detectOcrLanguage(runCommand, input.ocrLanguage);
        if (!language) throw new Error(input.ocrLanguage ? `Requested OCR language is unavailable: ${input.ocrLanguage}.` : "No supported OCR language installed (eng or tha).");
      } catch (error) {
        extractionStatus = "OCR_UNAVAILABLE";
        extractionWarning = `OCR unavailable; scanned pages were not verified. ${error instanceof Error ? error.message : String(error)}`;
      }
      if (language) {
        try {
          pages = await ocrPages(path, directory, pages, runCommand, language);
          extractionMethod = "ocr";
        } catch (error) {
          extractionStatus = "FAILED";
          extractionWarning = `OCR failed; scanned pages were not verified. ${error instanceof Error ? error.message : String(error)}`;
        }
      }
    }
    const fullText = pages.map((page) => page.text).join("\n");
    const modelMatch = containsExpected(fullText, input.expectedModel);
    const marketMatch = input.expectedMarket
      ? /^(thailand|thai|ประเทศไทย|ไทย)$/iu.test(input.expectedMarket.trim())
        ? /\bthailand\b|ประเทศไทย|ไทย/iu.test(fullText)
        : containsExpected(fullText, input.expectedMarket)
      : null;
    const yearMatch = containsExpected(fullText, input.expectedYear);
    const officialLinkMatch = sameSite(input.documentUrl, input.sourcePageUrl);
    const checks = [modelMatch, marketMatch, yearMatch, officialLinkMatch];
    const available = checks.filter((check): check is boolean => check !== null);
    const verificationScore = available.length ? Math.round(available.filter(Boolean).length / available.length * 100) : 0;
    const checksPassed = available.length > 0 && available.every(Boolean);
    const status = extractionStatus === "SUCCEEDED" && checksPassed ? "VERIFIED" : "NEEDS_REVIEW";
    return { documentUrl: input.documentUrl, sourcePageUrl: input.sourcePageUrl, modelMatch, marketMatch, yearMatch, officialLinkMatch, verificationScore, status, fileHash, pageCount: inspected.pageCount, metadata: inspected.metadata, extractedPageSnippets: pages, extractionMethod, extractionStatus, rightsStatus: base.rightsStatus, ...(extractionWarning ? { error: extractionWarning } : {}) };

  } catch (error) {
    return { ...emptyResult(base, error instanceof Error ? error.message : String(error)), extractionStatus: "FAILED" };
  } finally {
    if (directory) await rm(directory, { recursive: true, force: true }).catch(() => undefined);
  }
}

export const verifyDocument = verifyBrochureDocument;
