# Data model

The relational database is the canonical source of truth for normalized Thai car intelligence. `Manufacturer`, `CarModel`, `Variant`, `Feature`, and their aliases preserve official Thai and English names rather than replacing either with translations. A variant is the unit used for specifications and price observations.

## Provenance and trust

Every extracted fact is tied to a `SourceDocument` where possible. Documents retain canonical URLs, content hashes, fetch/publication timestamps, MIME/language metadata, rights status, document storage (`localPath`/`objectKey`), extracted text, and extraction status. `Source` records authority and an explicit source type (manufacturer brochure/price list/press release, authorized dealer, automotive media, news, social, community, or user submission). Confidence is stored as a decimal from 0 to 1 on extracted facts and research candidates; it is not a substitute for evidence.

`ResearchRun` and `ResearchCandidate` separate proposed values from accepted canonical data. A run records its entity/model target, queries, checked domains, page/document/image counts, changed-fact count, terminal error, and can finish as `PARTIAL_SUCCESS`. `BrochureVerification`, `ReviewItem`, and `DataChangeLog` support human review and an auditable before/after history; change logs retain evidence excerpts or JSON, proposed/applied flags, review status, and reviewer identity. Do not overwrite a price observation: insert a new `Price` row with its validity window and observation timestamp. Price rows enforce positive THB amounts, valid intervals, confidence in [0,1], and PostgreSQL exclusion of overlapping current intervals per variant/price type.

`DimensionsSpec`, `PerformanceSpec`, `BatterySpec`, `ChargingSpec`, `WarrantySpec`, and `SafetySpec` are normalized one-to-one tables for common fields. `VariantSpecExtra` remains JSONB for uncommon fields.

## Crawling and retrieval

`SourceHint`, `CrawlJob`, and `CrawlEvent` record crawl intent and operational history without making crawler state part of the catalog. `Embedding` stores chunk text, model, dimensions, content hash, and its source document. Its pgvector column is intentionally represented as `Unsupported("vector(1536)")`; 1536 is the initial provider dimension and changing providers requires a deliberate migration and re-embedding.

Rights status is explicit on sources, documents, and media. Unknown rights are retained as `UNKNOWN` so downstream publishing can require a conscious decision rather than assuming reuse is permitted.
