# PDF brochure verification

`workers/verification/document.ts` verifies a discovered brochure as a reference, without turning the downloaded bytes into a public asset.

## Usage

Create a JSON input file:

```json
{
  "documentUrl": "https://manufacturer.example/brochures/model-2025-th.pdf",
  "sourcePageUrl": "https://manufacturer.example/model",
  "expectedModel": "Model",
  "expectedMarket": "Thailand",
  "expectedYear": 2025,
  "rightsStatus": "unknown"
}
```

Run:

```bash
npx tsx scripts/verify-document.ts input.json
```

The worker fetches only through `safeFetch`, checks the HTTP status, `application/pdf` content type, response size, and PDF signature, then writes the bytes to a mode-0600 temporary processing directory. It computes SHA-256, uses the locally installed `pdfinfo` and `pdftotext` tools, returns page-numbered snippets and metadata, and removes the temporary directory in a `finally` block. When pdftotext yields mostly empty pages (the scanned-brochure case), it capability-checks `tesseract --list-langs`, renders each page with `pdftoppm`, and OCRs the rendered image. The default OCR language is `eng+tha` when both traineddata files are installed, otherwise an installed `tha` or `eng`; `ocrLanguage` can request another installed language combination. OCR is bounded to 50 pages, 150 DPI, 2 MiB command output, and 30 seconds per command. It never writes to `public/` or returns a retained file path.

Extraction is reported as `extractionMethod: "pdftotext"` or `"ocr"`. If tesseract is missing, its languages are unsupported, or OCR cannot start, the result remains `NEEDS_REVIEW` with `extractionStatus: "OCR_UNAVAILABLE"` and an explanatory error; it is never silently treated as verified. OCR success alone also cannot verify a brochure: expected model/market/year checks and the same-site official-link check must still pass. OCR failures after PDF inspection preserve the original page numbers and pdftotext snippets for review.

A `VERIFIED` result means the requested identity checks and same-site source-link check passed. A mismatch is `NEEDS_REVIEW`; transport, type, size, malformed-PDF, or extraction failures are `FAILED`. Verification does not change a research candidate's `PENDING` status and does not publish a document.

## Rights and publication

A public URL is not permission to redistribute, mirror, or publicly host a brochure. Rights are therefore `unknown` by default, or `reference-only` when explicitly supplied. The result is evidence for human review: publish the official URL and only redistribute the document when separate rights authorization is recorded. Verification is not publication, licensing, or a copyright determination.

## Local requirements

The verification path requires `pdfinfo` and `pdftotext` (Poppler) on the worker host. Scanned-document fallback additionally uses `pdftoppm` (Poppler) and optional `tesseract` with `eng` and/or `tha` traineddata. If tesseract or a supported language is unavailable, verification safely returns `NEEDS_REVIEW` with `OCR_UNAVAILABLE`; it does not install tools or claim the scan was verified. These tools are deliberately invoked only against the private temporary file; no PDF content is sent to an external parser.
