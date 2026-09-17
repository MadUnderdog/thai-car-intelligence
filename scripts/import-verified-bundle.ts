import { readFile } from "node:fs/promises";
import { importVerifiedBundle } from "../lib/catalog/importer";
import db from "../lib/db";

async function main() {
  const file = process.argv[2];
  const dryRun = process.argv.includes("--dry-run");
  if (!file || process.argv.slice(2).filter((arg) => arg !== "--dry-run").length !== 1) {
    console.error("Usage: tsx scripts/import-verified-bundle.ts <bundle.json> [--dry-run]");
    process.exitCode = 2;
    return;
  }
  try {
    const input = JSON.parse(await readFile(file, "utf8"));
    const result = await importVerifiedBundle(input, db, { dryRun });
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}

void main();
