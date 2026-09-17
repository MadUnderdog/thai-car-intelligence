import "dotenv/config";
import { readFileSync, readdirSync } from "fs";
import { importVerifiedBundle } from "../lib/catalog/importer";
import { getDb } from "../lib/db";

async function main() {
  const db = getDb();
  const files = readdirSync("fixtures/verified").filter((f) => f.endsWith(".json"));
  let ok = 0, fail = 0;
  for (const file of files) {
    try {
      const input = JSON.parse(readFileSync("fixtures/verified/" + file, "utf8"));
      await importVerifiedBundle(input, db, { dryRun: false });
      ok++;
    } catch (e: unknown) {
      fail++;
      console.error("FAIL:", file, e instanceof Error ? e.message : String(e));
    }
  }
  console.log("Imported:", ok, "Failed:", fail);
  await db.$disconnect();
}
main();
