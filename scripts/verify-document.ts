import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { z } from "zod";
import { verifyBrochureDocument } from "../workers/verification/document";

const httpUrl = z.string().url().refine((value) => /^https?:\/\//i.test(value), "must be an HTTP(S) URL");
export const documentVerificationInputSchema = z.object({
  documentUrl: httpUrl,
  sourcePageUrl: httpUrl,
  expectedModel: z.string().min(1).optional(),
  expectedMarket: z.string().min(1).optional(),
  expectedYear: z.union([z.number().int(), z.string().min(1)]).optional(),
  rightsStatus: z.enum(["unknown", "reference-only"]).optional(),
  tempDirectory: z.string().min(1).optional(),
  maxBytes: z.number().int().positive().optional(),
});

export function validateDocumentVerificationInput(value: unknown) {
  return documentVerificationInputSchema.parse(value);
}

async function main(): Promise<void> {
  const inputPath = process.argv[2];
  if (!inputPath) throw new Error("Usage: tsx scripts/verify-document.ts <input.json>");
  const input = validateDocumentVerificationInput(JSON.parse(await readFile(inputPath, "utf8")));
  const result = await verifyBrochureDocument(input);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error: unknown) => {
    process.stderr.write(`document verification failed safely: ${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
