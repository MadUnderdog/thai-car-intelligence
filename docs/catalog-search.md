# Catalog and structured search

## Read APIs

- `GET /api/cars` lists only active variants having a current price whose source document is `VERIFIED`, has a verified brochure/source check, and is from an active official manufacturer source.
- `GET /api/search` accepts `q`, `fuelType`, and `maxPrice`; it searches normalized manufacturer/model/variant names and aliases using the same verified-catalog rules.
- Optional pagination parameters are `page` (1-based, default `1`, maximum `100000`) and `limit` (default `24`, maximum `100`). Responses contain `results`, `total`, `page`, `limit`, and `hasMore`. Filtering, counting, ordering, and pagination are performed by the database; the API never loads the full catalog into memory.
- Text filters are trimmed and limited to 120 characters. Invalid values, including non-positive pages and limits above 100, return HTTP 400.

Both endpoints return HTTP 200 with `results: []` and `total: 0` when the database is reachable but the catalog is empty. A database/connection failure is different: it returns HTTP 503 with `error: "catalog_unavailable"`, an empty results array, and pagination metadata. They never create or infer vehicle records. Every returned price includes source-document and source metadata; inactive sources and non-verified documents are excluded from provenance and filtering.

## Search status

Search is deliberately deterministic and structured-first. The response includes `vectorAvailable: false` and `searchMode: "structured-fallback"` until embeddings and a vector retrieval implementation are actually available. This flag must not be changed merely because the schema contains an embedding table.

## Source bundles

`lib/catalog/importer.ts` exports `sourceBundleSchema`, `parseSourceBundle`, and `validateSourceBundle`. A bundle is a validation contract only: it does not seed the database. Prices must be positive finite numbers and use the supported `THB` currency. Every price and fact requires a valid URL and non-empty evidence. A record-level provenance object may be supplied for records whose important facts use it. Empty bundles are valid, allowing ingestion jobs to represent an empty verified source result without fake vehicle rows.
