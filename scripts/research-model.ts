import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { z } from "zod";
import { runResearch, type ResearchRunInput } from "../workers/research/run";

const domainPattern = /^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i;
const httpUrl = z.string().url().refine((value) => /^https?:\/\//i.test(value), "must be an HTTP(S) URL");
export const researchRunInputSchema = z.object({
  model: z.string().optional(), entityType: z.string().optional(), entityId: z.string().optional(),
  officialDomains: z.array(z.string().trim().regex(domainPattern, "must be a valid domain")).min(1),
  seedPageUrls: z.array(httpUrl).min(1), discoveryQueries: z.array(z.string().min(1)).min(1),
  year: z.union([z.number().finite(), z.string().min(1)]).optional(), provider: z.string().optional(), name: z.string().optional(),
});

export function validateResearchRunInput(value: unknown): ResearchRunInput {
  return researchRunInputSchema.parse(value) as ResearchRunInput;
}

async function main(): Promise<void> {
  const inputPath = process.argv[2];
  if (!inputPath) throw new Error("Usage: tsx scripts/research-model.ts <input.json>");
  const input = validateResearchRunInput(JSON.parse(await readFile(inputPath, "utf8")));
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is required; refusing to start a research run.");
  const result = await runResearch(input);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main().catch((error: unknown) => {
  process.stderr.write(`research run failed safely: ${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
