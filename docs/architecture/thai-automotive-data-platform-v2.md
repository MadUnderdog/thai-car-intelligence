# Thai Automotive Intelligence Platform — Operating Doctrine v2.0

> **Canonical source of truth**: This document. Not Slack Canvas, not chat history.
> Every Hermes run working on this project MUST read this file before starting implementation.

---

## 1. Mission & Product Vision

Build Thailand's most accurate, evidence-backed automotive intelligence platform.

**Core principles:**
- Every data field has provenance — who said it, when, where
- Verified facts come only from official manufacturer sources
- Secondary sources provide breadth but never masquerade as authority
- Community can suggest research leads but never directly modify canonical data
- No fabricated data, no guessed prices, no invented specs

**Product phases:**
1. ✅ Catalog Foundation (schema, API, provenance gate)
2. Data Richness (specs, images, features, warranty, price history)
3. Public Product (detail page, comparison, search, evidence panel)
4. Community (comments, research leads, moderation)
5. Intelligence (price alerts, market analysis, AI comparison)

---

## 2. Source-of-Truth Hierarchy

1. **Actual code/runtime/DB on Ubuntu** — the running system
2. **GitHub main + current branches/PRs** — the versioned record
3. **This document** — the operating doctrine
4. **Blueprint.md** — project blueprint (reference, not law)

When conflicts arise, runtime reality wins over documentation.

---

## 3. Evidence States

### Price Evidence Lifecycle
```
DISCOVERED → REPORTED → NEEDS_RECONCILIATION → RECONCILED → VERIFIED → PUBLISHED
```

- **DISCOVERED**: Raw observation from any source, no quality assessment
- **REPORTED**: Extracted with structured metadata, source captured
- **NEEDS_RECONCILIATION**: Multiple observations exist, conflicts detected
- **RECONCILED**: Conflicts resolved, best evidence selected
- **VERIFIED**: Confirmed against official manufacturer source
- **PUBLISHED**: Exposed via public API (`currentOfficialPrice`)

### Spec Evidence Lifecycle
Same as prices. Specs from secondary sources are REPORTED, not VERIFIED.

---

## 4. Source Tiers vs Price Types

### Source Tiers (WHO published it)
| Tier | Description | Examples |
|------|-------------|----------|
| `primary_official` | Manufacturer's own website | honda.co.th, mgcars.com, byd.com |
| `secondary_automotive_media` | Professional automotive publications | HeadLight, AutoLifeThailand, AutoSpinn |
| `secondary_automotive_reference` | Automotive reference/listing sites | 9CARTHAI, One2car |
| `tertiary_listing` | Classifieds, forums, social | Facebook Marketplace, Pantip |

### Price Types (WHAT the price represents)
| Type | Thai Term | Description |
|------|-----------|-------------|
| `manufacturer_msrp_reported` | ราคาอย่างเป็นทางการ | Official MSRP reported by publisher |
| `launch_price` | ราคาเปิดตัว | Price at model launch |
| `starting_price` | ราคาเริ่มต้น | "Starting from" price |
| `campaign_price` | ราคาโปรโมชั่น/พิเศษ | Promotional/special price |
| `after_discount` | หลังหักส่วนลด | Price after discount |
| `unknown` | — | Unclassified |

**Critical rule:** Source tier is the PUBLICATION, not the article title. A HeadLight article titled "Official Price: Honda Civic" is still a SECONDARY source observation. Use `priceType: "manufacturer_msrp_reported"` to distinguish "official price reported by secondary source" from the source tier itself.

---

## 5. Web Extraction Decision Tree

Escalate in order. Do not give up because curl shows an empty SPA shell.

```
1. DIRECT HTTP
   curl -L -A 'Mozilla/5.0' -sS -D /tmp/headers.txt 'URL' -o /tmp/page.html
   Inspect: status, final URL, content type, response bytes

2. RAW HTML / EMBEDDED JSON
   rg -n 'price|priceValue|offers|variant|grade|vehicle|model|NEXT_DATA|NUXT|INITIAL_STATE|ld+json' /tmp/page.html
   Parse JSON-LD, __NEXT_DATA__, __NUXT__, __INITIAL_STATE__ if present
   MG sites embed prices in escaped JSON — grep can extract without browser

3. BROWSER RENDERING (for SPA sites)
   Use browser_exec → open exact page → wait for DOM readiness
   Inspect rendered body text, visible price elements
   Toyota sites are fully client-side SPA — prices NOT in HTML

4. NETWORK INSPECTION (Chrome DevTools → Network → Fetch/XHR)
   Look for requests containing: api, graphql, price, product, vehicle, model, variant, catalog
   Inspect JSON responses — find the endpoint that feeds the page

5. REPRODUCE DATA REQUEST
   Capture URL, query/body, headers (public only)
   Reproduce with curl/Python → save raw JSON → hash response → parse observations

6. SCREENSHOT/OCR ONLY LAST RESORT
   Use only when price is visibly rendered but unavailable through DOM/API
   Keep screenshot as evidence artifact
```

### Extraction Reliability by Manufacturer
| Manufacturer | Rendering | curl extraction | Browser needed? |
|-------------|-----------|-----------------|------------------|
| Honda | Server-rendered | ✅ Prices in HTML | No |
| MG | SPA with JSON payloads | ✅ Prices in `<script>` JSON | No |
| BYD | Client-side SPA | ⚠️ Some pages return 404 | Yes |
| Toyota | Client-side SPA | ❌ Prices not in HTML | Yes |

---

## 6. Reusable Adapter Architecture

```
URL → fetch → detect transport → extract raw payload → parse observations[] → normalize → dedupe → persist DISCOVERED
```

### Base Adapter Interface
```typescript
interface SourceAdapter {
  name: string;
  tier: SourceTier;
  domain: string;
  canHandle(url: string): boolean;
  fetchEvidence(url: string): Promise<string>;
  extractObservations(rawContent: string, url: string): ExtractedObservation[];
}
```

**One page with 12 variants → 12 observations.**

### Generic Extractors (fallbacks)
- HTML price pattern: `\d{1,3}(?:,\d{3})+ บาท`
- 9CARTHAI structured text: `Model Variant ราคา X,XXX,XXX`
- AutoSpinn equation format: `Model Variant = X,XXX,XXX`
- Embedded JSON: `title[^}]*price[^}]*`

### File Locations
- `lib/catalog/adapters/base.ts` — SourceAdapter interface + normalizer
- `lib/catalog/adapters/headlight.ts` — HeadLight adapter
- `scripts/harvest-engine.py` — Python harvest engine
- `scripts/dedup-harvest.py` — Deduplication
- `scripts/ingest-harvest.ts` — TypeScript DB ingestion

---

## 7. Observation Schema

```typescript
type ExtractedObservation = {
  manufacturer: string;
  model: string;
  variant: string;
  price: number;          // Normalized numeric
  priceText: string;      // Raw from source
  priceType: PriceType;
  market: string;         // Must be "Thailand"
  sourceExcerpt: string;  // Exact text containing the price
  articleTitle: string | null;
  publicationDate: string | null;
};
```

---

## 8. Dedup / Conflict / Reconciliation Rules

### Deduplication
- Deterministic: `content_hash = md5(url|model|variant|price)`
- Same source + same URL + same model + same variant + same price = duplicate
- Different source OR different URL OR different price = separate observation

### Conflicts
- Same model/variant from two sources = two observations (not overwritten)
- Conflicting prices remain separate with conflict status
- Do NOT choose the "correct" price during harvest
- Cross-source agreement is useful but NOT verification

### Reconciliation
- Happens AFTER harvest, not during
- Compare dates, price types, source tiers
- Select authoritative evidence based on recency + source tier + consistency
- Promote to VERIFIED only when confirmed against official manufacturer source

---

## 9. Spec Evidence Policy

The same observation architecture works for specs:

```
Source → Raw Evidence → Observation → Normalization → Reconciliation → Verification → Canonical Fact
```

### Spec Categories
| Category | Fields | Vehicle Types |
|----------|--------|---------------|
| Performance | horsepower, torque, 0-100, top_speed | All |
| Dimensions | length, width, height, wheelbase, ground_clearance | All |
| Battery | capacity_kwh, range_km, battery_type | EV/PHEV |
| Charging | ac_charging_kw, dc_charging_kw, charge_time_10_80 | EV/PHEV |
| Safety/ADAS | airbags, abs, esc, lane_keep, adaptive_cruise | All |
| Warranty | years, km | All |
| Drivetrain | transmission, drive_type, engine_displacement | All |
| Body/Seating | doors, seats, cargo_liters | All |
| Equipment | features list | All |

### Spec Rules
1. Same spec from two sources = two observations
2. Conflicting specs remain separate with conflict status
3. Historical specs keep their date context
4. Do not fabricate missing specs — report gaps honestly
5. Specs from secondary sources are REPORTED, not VERIFIED
6. Official specs require manufacturer website verification

---

## 10. Canonical Catalog Rules

### Verified Catalog (Published)
- Only prices with `sourceDocument.status = "VERIFIED"` pass `currentOfficialPrice`
- `GET /api/cars` returns ONLY verified prices
- No secondary evidence can bypass the publish gate

### Research Layer
- All secondary observations stored as `status: "DISCOVERED"`
- Never set `Price.sourceDocumentId` for secondary observations
- Never enter `currentOfficialPrice` for secondary observations
- Visible only in admin/research console, not public API

### Data Safety
- Existing verified prices remain untouched unless independently corrected
- No bulk spec/fuel/feature/warranty/media changes during harvest
- No fabricated model/variant mappings
- Historical/promotional prices stay date/type scoped

---

## 11. Community Boundary

```
User Comment → Optional Research Lead → ResearchCandidate → Source Verification → Canonical Fact
```

- Comments/replies/upvotes/downvotes/reports are USER CONTENT
- They can suggest research leads but never directly modify canonical data
- Moderation queue separate from admin catalog queue
- Community reputation does not affect data trust tiers

---

## 12. Admin/Research Console Direction

### Current Admin Endpoints
- `/api/admin/dashboard` — overview stats
- `/api/admin/quality` — data quality metrics
- `/api/admin/quality/variants` — variant completeness
- `/api/admin/research/queue` — research queue
- `/api/admin/candidates` — research candidates

### Future Research Console
- Observation browser (all 418+ research observations)
- Conflict detector (multi-source disagreements)
- Reconciliation workflow (select best evidence)
- Verification queue (promote to verified)
- Spec evidence tracker

---

## 13. Token/Compute Efficiency

- Use code for deterministic work: fetching, parsing, hashing, dedup, persistence
- Use model reasoning only for ambiguous mapping/extraction
- Batch URL processing with bounded concurrency
- Cache raw responses so reruns do not redownload
- One article with 12 variants → extract all 12 in one pass
- Do not spend 20 reasoning iterations re-reading one article

---

## 14. No-Loop Policy

**Rule:** Do not enter repeated audit-verify-reaudit cycles on the same data.

```
HARVEST MORE DATA → RECONCILE → VERIFY → PUBLISH → BUILD PRODUCT
```

- If a price is verified, move on — do not re-verify it each milestone
- If a batch is complete, proceed to the next task — do not re-audit the same batch
- Each milestone must produce NEW data or NEW capability, not re-examine old work
- Exception: specific data quality issues reported and needing targeted fix

---

## 15. AI Freeze

**Active until explicitly lifted:**
- No `lib/ai/` changes
- No AI Ask, provider/model/router/gateway/embedding work
- No LLM calls, image generation, reindexing, research-LLM
- No `.env` / `.env.local` / provider settings changes

---

## 16. Hermes Execution Discipline

- One milestone at a time — do not auto-proceed to the next
- A newer control message supersedes/redirects the current run
- Freeze messages are absolute until explicitly lifted
- Complete the entire scope in one pass — do not split control messages
- Every milestone must create measurable data/product delta
- Report exact numbers, not vague claims
- Stop after final report — do not automatically start next milestone

---

## 17. Extraction Pipeline (Current)

### Run Pattern
```bash
python3 scripts/harvest-engine.py       # Fetch + extract → harvested-observations.json
python3 scripts/dedup-harvest.py        # Dedupe → deduped-observations.json
npx tsx scripts/ingest-harvest.ts       # Ingest into database
```

### Yield (Last Run)
- 45 HeadLight articles → 144 observations
- 4 9CARTHAI price lists → 111 observations
- 6 AutoLifeThailand articles → 18 observations
- 1 AutoSpinn article → 20 observations
- Total: 293 deduped from 565 raw

### Curated Source Pool
| Source | Tier | Extraction Method |
|--------|------|-------------------|
| 9CARTHAI | secondary_automotive_reference | Direct HTTP |
| HeadLight Magazine | secondary_automotive_media | Direct HTTP |
| AutoSpinn | secondary_automotive_media | Direct HTTP |
| AutoLifeThailand | secondary_automotive_media | Direct HTTP |

---

## 18. Known Pitfalls

1. **Provenance enforcement silent failure**: `currentOfficialPrice` filter returns empty results when no prices have provenance — no error, just zero rows
2. **Prisma UUID mismatch**: `Price.sourceDocumentId` must be `@db.Uuid` in schema
3. **SPA JSON extraction**: MG sites embed prices in escaped JSON — grep works without browser
4. **Honda server-rendered**: Prices directly in HTML
5. **Toyota fully client-side**: Prices NOT in HTML — require browser/API
6. **Dead code with credentials**: Always check for hardcoded passwords in unused files
7. **Batch script sprawl**: Do NOT create batchN-evidence.ts / batchN-ingest.ts pairs — use reusable engine
8. **Source tier confusion**: Article title saying "Official Price" does NOT make the source primary_official

---

*Document version: 2.0 | Last updated: 2026-09-18 | Author: Hermes Agent*
*Canonical location: `docs/architecture/thai-automotive-data-platform-v2.md`*
