#!/usr/bin/env tsx
import "dotenv/config";
import { z } from "zod";
import { getDb } from "../lib/db";
import { getLocalEmbeddingClient, type LocalEmbeddingClient } from "../lib/embeddings/local-service";
import { indexSourceDocument } from "../workers/indexing/embed-document";

const inputSchema = z.object({ sourceDocumentId: z.string().uuid(), dryRun: z.boolean().default(false) });
function argsToInput(argv: string[]): unknown {
  const jsonAt = argv.indexOf("--json");
  if (jsonAt >= 0) return JSON.parse(argv[jsonAt + 1] ?? "");
  const idAt = argv.indexOf("--source-document-id");
  return { sourceDocumentId: idAt >= 0 ? argv[idAt + 1] : undefined, dryRun: argv.includes("--dry-run") };
}

async function main() {
  let input;
  try { input = inputSchema.parse(argsToInput(process.argv.slice(2))); }
  catch (error) { throw new Error(`Invalid index input: ${error instanceof Error ? error.message : "invalid JSON or arguments"}`); }
  const configured = getLocalEmbeddingClient();
  const client: LocalEmbeddingClient | null = configured ?? (input.dryRun ? { provider: "local", model: process.env.EMBEDDING_MODEL?.trim() || "local-bge-base", dimensions: 768, embed: async () => { throw new Error("dry-run embedding should not be called"); } } : null);
  if (!client) throw new Error("EMBEDDING_BASE_URL is required for indexing; no network endpoint is assumed");
  const result = await indexSourceDocument(input.sourceDocumentId, { db: getDb(), embeddings: client }, { dryRun: input.dryRun });
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

main().catch((error) => { process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`); process.exitCode = 1; });
