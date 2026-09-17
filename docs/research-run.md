# Persisted research-run discovery

`workers/research/run.ts` performs a bounded, reference-only discovery pass over explicitly supplied official seed pages.

## Input

Create a JSON file containing:

```json
{
  "model": "Yaris",
  "entityType": "CarModel",
  "entityId": "optional-uuid",
  "officialDomains": ["toyota.co.th"],
  "seedPageUrls": ["https://toyota.co.th/cars/yaris"],
  "discoveryQueries": ["Yaris brochure Thailand"],
  "year": 2025
}
```

Every seed URL is checked against `officialDomains`; requests are made only through `safeFetch`, which validates HTTPS/HTTP destinations, DNS, redirects, timeouts, and response size. Pages must be HTML. Discovered document and image URLs are also restricted to the allow-list.

The CLI validates the JSON with Zod before checking the database or creating a run: all three arrays are required and non-empty, domains must be bare DNS names, and seed pages must be HTTP(S) URLs. Image discovery classifies utility, navigation, logo, and branding assets as `unknown`; these are excluded from persisted vehicle candidates, so `imagesFound` counts only persisted image candidates.

## Running

```bash
DATABASE_URL='postgresql://...' npx tsx scripts/research-model.ts input.json
```

The command prints the persisted run ID, final status, and structured report. It exits without creating a run when `DATABASE_URL` is absent. Candidate rows are metadata only: no PDF/image is downloaded or stored, all candidates remain `PENDING`, and source-page URLs are retained in both the candidate evidence and report. Rights remain unresolved and must be handled by later verification stages.

A run is `PARTIAL_SUCCESS` when at least one page succeeds while another fails. If no page succeeds, it is `FAILED` when there were fetch errors. An empty successful pass is reported as `not_found` in the report while retaining a durable run record.

If candidate insertion or final run completion fails, the original error is rethrown after a best-effort update marks the newly-created run `FAILED`.

## Programmatic use

`runResearch(input, { fetch, client, now })` accepts injected fetch, Prisma-like persistence, and clock dependencies for deterministic tests. The production default uses the lazy Prisma singleton from `lib/db.ts`.
