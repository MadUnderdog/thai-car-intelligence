# Research pipeline

## Stage A: deterministic discovery

Stage A accepts HTML that has already been supplied by a fetcher or browser adapter. The DOM-independent parser extracts brochure/document and image candidates from ordinary links, image attributes, lazy-loading attributes, `srcset`, Open Graph/Twitter metadata, JSON-LD, and common download/gallery labels. URLs are resolved against the page URL and candidates retain their source page and discovery method. Scoring is deterministic and exposes every point in its breakdown; it does not invent URLs or call an LLM.

The brochure worker performs multi-page collection, de-duplication, stable ranking, and emits a `not_found` audit when no document is discovered. The image worker adds conservative role hints and can select the largest declared `srcset` item.

## Adapter boundary

A later browser/search adapter may fetch pages, follow search results, and provide HTML to Stage A. Search engines and Google grounding are discovery aids only: they may discover candidate URLs, but cannot mark a source verified without opening and checking the actual page or PDF. Validation, rights checks, and content extraction therefore remain subsequent stages.
