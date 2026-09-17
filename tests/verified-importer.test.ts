import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { importVerifiedBundle, parseVerifiedBundle, validateVerifiedBundle } from "../lib/catalog/importer";

const fixture = JSON.parse(readFileSync(new URL("../fixtures/verified/camry.json", import.meta.url), "utf8"));

describe("verified catalog bundles", () => {
  it("accepts the official Camry model-page fixture", () => {
    expect(parseVerifiedBundle(fixture).records).toHaveLength(3);
  });

  it("rejects missing evidence and non-THB prices", () => {
    const missing = structuredClone(fixture);
    missing.source.evidenceExcerpt = "";
    expect(validateVerifiedBundle(missing).success).toBe(false);
    const nonThb = structuredClone(fixture);
    nonThb.records[0].prices[0].currency = "USD";
    expect(validateVerifiedBundle(nonThb).success).toBe(false);
  });

  it("rejects brochure mislabeling and unsupported sources", () => {
    const brochure = structuredClone(fixture);
    brochure.source.verification.notes = "Brochure verified";
    expect(validateVerifiedBundle(brochure).success).toBe(false);
    const unsupported = structuredClone(fixture);
    unsupported.source.sourceType = "AUTOMOTIVE_MEDIA";
    expect(validateVerifiedBundle(unsupported).success).toBe(false);
  });

  it("dry-runs without touching the database and counts all prices", async () => {
    const result = await importVerifiedBundle(fixture, {} as never, { dryRun: true });
    expect(result).toMatchObject({ dryRun: true, records: 3, prices: 3 });
  });

  it("uses one transaction for an import", async () => {
    const transaction = vi.fn().mockImplementation(async (callback: (tx: unknown) => Promise<void>) => callback({}));
    const client = { $transaction: transaction };
    // The transaction callback will fail at the first database operation, but proves writes are never outside it.
    await expect(importVerifiedBundle(fixture, client as never)).rejects.toThrow();
    expect(transaction).toHaveBeenCalledTimes(1);
  });
});
