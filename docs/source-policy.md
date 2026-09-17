# Source policy

The research pipeline treats source selection and access as policy decisions, not as permission to retrieve anything found on the web.

## Precedence and provenance

- Prefer a publisher's official website, filing, release, product page, or government record for claims about that publisher or organization.
- Use reputable secondary reporting to add context, and retain the source URL and retrieval timestamp.
- Registry entries are configuration, not a permanent brand list. Domains must be explicitly supplied by the application or operator.
- A URL is never considered valid merely because it looks plausible: candidates must pass URL safety validation and must be traceable to a real discovery result.

## Legal and access limits

- Follow applicable law, terms of service, robots/access controls, copyright, and rate limits.
- Only retrieve content that the application is authorized to access. Do not use credentials embedded in URLs.
- Do not bypass CAPTCHAs, paywalls, authentication, geo-blocks, bot checks, or other access controls.
- A failed, blocked, or unverified candidate remains failed/blocked; the pipeline must not invent a replacement URL or claim that content was retrieved.

## Assets and rights

- Store only content for which the project has a documented right or license to retain. Preserve attribution where required.
- `referenceOnly` sources may be linked and cited with metadata, but their page body, images, and other assets must not be copied into durable storage by default.
- Unknown or restricted rights require review before persistence or republication. A public URL does not itself grant reuse rights.
- Prefer official assets when an asset is needed; otherwise use a licensed, public-domain, or user-provided alternative and record its rights status.

## Network safety

- Only HTTP and HTTPS are accepted. Localhost, loopback, private/RFC1918, link-local, multicast, cloud metadata, and DNS names resolving to those ranges are rejected.
- URL credentials are rejected. Domain allow-lists match the exact configured domain or a dot-delimited subdomain, never a lookalike suffix.
- DNS validation should run immediately before fetching, and the eventual HTTP client should prevent redirects from escaping the same policy. **`lib/security/safe-fetch.ts` is the only permitted crawler fetch path**: it validates every URL, uses manual redirects, re-validates each `Location`, and applies redirect, timeout, and response-size limits. Tests use injected resolvers or mocked fetch implementations and never make network requests.
