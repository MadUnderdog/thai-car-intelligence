# Verified catalog bundle importer

`import-verified-bundle.ts` imports small, manually checked JSON bundles without fetching URLs. The Zod contract requires the official source URL and title, retrieval time, evidence excerpt, SHA-256 content hash, explicit page verification, preserved Thai/English names, and per-price evidence. Only positive THB prices are accepted. The importer is transactional and idempotent by source URL/base URL plus document hash and by natural slugs.

```bash
npx tsx scripts/import-verified-bundle.ts fixtures/verified/camry.json --dry-run
npx tsx scripts/import-verified-bundle.ts fixtures/verified/camry.json
```

## Model-page facts versus brochure facts

A model page can verify a displayed current/list price and the exact grade name shown beside it. It does **not** verify the contents of a downloadable brochure, its specifications, or its page numbering. The Camry fixture therefore contains only three official model-page prices and no unsupported specifications.

The fixture's `contentHash` is the SHA-256 of its preserved evidence excerpt (the bundle's immutable evidence payload; no page bytes are downloaded or retained). The current schema has one legacy `BrochureVerification` table and catalog queries require a verified document plus a verified verification row. For compatibility, the importer uses that row only for a `MODEL_PAGE` document and appends an explicit note: **official model-page evidence only; brochure contents remain NEEDS_REVIEW**. It does not mark a brochure document as verified, does not ingest brochure bytes, and does not claim brochure facts. A future schema can replace this compatibility row with a type-specific source-document verification table without changing the input contract.

The importer rejects non-official source types, missing evidence, non-THB/non-positive prices, and any input that attempts to describe a model page as brochure-verified. Dry-run validates and counts records/prices without opening a database transaction.
