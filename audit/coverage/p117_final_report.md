# P117 — COMMUNITY + MODERATION OVER PROMOTED VEHICLE CONTEXT

**Status: COMPLETE (awaiting review) · 2026-09-29 · base `2a30e39e31832b25782339380841045a83eb8570` · PR #3 OPEN/UNMERGED**

## Before → after (every defect red-before/green-after)

| # | Boundary | Before (base 2a30e39) | After (P117) |
|---|---|---|---|
| D1 | E/2 privilege | POST body `isResearchLead:true` → **client self-grants the badge** | field never read (always false); only admin `/research-lead` (Bearer, auth before DB) sets it; anon → 401 |
| D2 | C/1 scope | reply `modelId ?? parent.modelId` → **payload could move a reply to another model** | replies inherit parent scope verbatim; parent must be VISIBLE; client scope fields ignored |
| D1–D7 (scope) | D/1/6/8 | malformed UUID → **Prisma throw**, nonexistent entity → **orphan persisted 201**, mismatched model+variant accepted, `page=abc` → NaN | `lib/community/scope.ts`: UUID → 400, existence+ACTIVE → 404 (0 orphans), model↔variant agreement → 400, pagination finite → 400 — POST and GET |
| D4 | G/3 report | reporterToken = cookie\|\|hashIp → **clearing the cookie minted new identities → one actor could auto-hide anything** | reporterToken = hashIp(ip) always → one report/comment/IP idempotent; 3 distinct IPs → FLAGGED, all report rows preserved |
| D5 | J/10 Blueprint 23 | blocked-words **did not exist** | `blocked-words.ts` (disclosed starter list, NFKC+lowercase, Thai substring/EN word-boundary) → 400 **before persistence** (0 rows, deterministic, benign unaffected) |
| D6 | I/6 | no try/catch anywhere: DB errors = thrown exception, SQL in error text | 7 handlers → generic JSON 500; test injects error containing `SELECT * FROM "CommunityComment"` and asserts body has no SELECT/Prisma/stack |
| D7 | M | GET orderBy tie-unsound | final `{id:'asc'}` tiebreak; repeated GET deep-equal |
| N | N | vote buttons 20px, submit/report reasons 28px | ≥32px everywhere in the section; smoke asserts [] |

Baseline community tables **byte-identical after all runs**: comments 39 / reports 16 / votes 12, 0 `[p117-fixture]` rows.

## Red-before / green-after

- `20260929-p117-redbefore.log`: **23 failed | 8 passed (31)** on untouched base (test-harness fix disclosed: dynamic routes need the `{params}` context arg)
- `20260929-p117-smoke-red.log`: touch-target FAIL (11 buttons <32px)
- Green: focused **31** in one implementation pass + focused cycle for the touch defect → smoke **14/14**

## Gates — ONE chain (`proc_d409e8714682` exit 0) + one pytest env correction

- tsc **0** · focused **31 passed** rc=0 · deterministic rerun **31** · combined community/moderation/security/UX **78 passed (9 files)** rc=0 · full vitest **563 passed | 2 skipped (47)** rc=0
- full pytest **964 passed, 1 error** (1392.23s) — the ONLY error is the known pre-existing `generation_config_boundary` ImportError (P49), reported separately
- **Disclosed env correction**: this session's chain shell resolved `python3` to Hermes tools 3.14.7 (no playwright); `extract_from_html` spawns `python3` → `ModuleNotFoundError: playwright` → first pytest attempt showed 64 environment failures. Re-ran the pytest gate ONCE with PATH prefixed to `~/.hermes/hermes-agent/venv` (has playwright+pytest) → 964/1-error. No test/code changed to achieve it.
- prisma validate **0** · credential scan **0 hits** · build **rc=0** · **mobile smoke RC=0, 14/14** (390×844: section renders, heading + disclaimer, form/vote/reply/report controls, touch targets ≥32px, no overflow, 0 console/runtime errors, disclaimer scoped inside community section)

## Mandatory tests A–N (all non-vacuous)

A model-scope persist/GET · B variant scope + other-model exclusion · C malicious reply inherits parent (base showed modelB) · D1–D7 format/existence/ACTIVE/consistency (spy proves `status='ACTIVE'`; orphan counts 0) · E1/E2 badge not client-settable + admin-only setter · F HIDDEN parent hides parent+reply+count, DELETE reply, RESTORE · G1 per-IP report idempotency (base minted 2 rows), G2 3-distinct → FLAGGED with 3 evidence rows · H vote idempotent/switch + **counters == vote rows invariant** · I1–I4 malformed inputs 400, I6a–g safe 500 ×7 routes · J blocked-word 400/0-rows/deterministic · K queue lists FLAGGED w/ reports+briefByReason, HIDE → public GET excludes, RESTORE → back, anon 401 · L catalog/evidence sources contain **zero** community-table references + label/disclaimer guards · M orderBy tiebreak + repeated GET identical · N smoke 14/14

## STOP-condition evidence

A) flows contract-correct (31+78+563 green, smoke) ✓ B) abuse-resistant (per-IP idempotency, rate limits kept, deterministic auto-hide ≥3 distinct IPs, blocked words, privilege isolation) ✓ C) clearly anecdotal (heading + disclaimer preserved and asserted; badge only via admin) ✓ D) auditable (report rows never deleted on auto-hide; moderation queue + resolved flags) ✓ E) **no catalog/provenance contamination** (L1 static zero-reference proof; community tables have no FK into catalog) ✓ F) **no unauthorized schema/provider/refresh work** (0 schema files touched; community writes only via fixtures with verified cleanup) ✓ G) tests real/deterministic (rerun 31 identical, GET deep-equal, counters invariant) · local==remote + PR #3 OPEN/UNMERGED — verified post-push (SHA in Slack report)

## Honest limits

- in-memory single-process rate limiter; report/vote identity is per-IP (NAT shares one identity — deliberate, replaces the cookie identity that enabled auto-hide spam)
- blocked-words = disclosed starter list; **edit history N/A** (no edit endpoint exists — disclosed, not faked)
- pre-fix report rows remain keyed by old cookie tokens (no migration); `CommunityUser` table doesn't exist (anonymous by design)
- never declares moderation/coverage completeness
