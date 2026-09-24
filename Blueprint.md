# Blueprint — Thai Car Intelligence & Community Web App

## 0. Project intent

Build a production-ready Thai-language web application for researching, comparing, asking AI questions about, and discussing cars sold in Thailand.

The application must work well on:
- Mobile browsers first
- Desktop browsers
- Tablet layouts

The core product is **not just a car catalog**. It is a source-backed car intelligence system combining:

1. Structured vehicle/trim/price/specification data
2. Official-source images and real brochures
3. Semantic search using PostgreSQL + pgvector
4. AI Q&A using an LLM API configured through environment/settings
5. Automated source discovery and data update workflows
6. Community discussions attached to specific vehicles
7. General discussion
8. Optional automotive news section
9. Provenance, source dates, confidence, and change history

The system must strongly distinguish:
- Official manufacturer/dealer information
- Information extracted from brochures
- Information from reputable automotive media
- Community/user opinions
- AI-generated summaries/inferences

Never present an AI inference or community opinion as official specification.

---

# 1. Product principles

## 1.1 Source-first

Every important factual vehicle field should have provenance.

Examples:
- Price
- Trim name
- Battery capacity
- Motor power
- Dimensions
- Warranty
- Charging capability
- ADAS features
- Standard equipment
- Launch date
- Promotion/discount

A source record should contain:
- URL
- Source type
- Publisher
- Retrieved timestamp
- Publication/updated date if available
- Document title
- Document/file hash where applicable
- Extraction method
- Confidence
- Relevant page number for PDFs
- Optional quoted/source excerpt

Prefer primary sources in this order:

1. Thai manufacturer/importer official website
2. Official Thai brochure/spec sheet
3. Official Thai price list
4. Official press release
5. Authorized dealer material
6. Reputable automotive media
7. Community/social sources

Social posts must NOT overwrite official specifications automatically.

---

# 2. Important legal/operational constraint for the research agent

The research/update agent may browse public websites and public social/news pages to discover information.

It must NOT:
- Bypass login requirements
- Bypass CAPTCHA
- Circumvent paywalls
- Circumvent technical access controls
- Scrape private groups/accounts
- Pretend to be a human to defeat anti-bot controls
- Download content where access is clearly prohibited
- Re-publish copyrighted brochure text wholesale
- Copy entire news articles

For brochures and images:
- Store the source URL and metadata.
- Prefer linking to the original official document/page.
- If storing a local copy is permitted, store it with provenance.
- Do not assume that because a PDF is publicly reachable it may legally be redistributed.
- Use robots.txt/terms/access restrictions where applicable.
- If unsure, keep a reference/cache metadata record rather than redistributing the document.

The agent should use browser/search capabilities available to it and collect public information transparently.

---

# 3. Recommended architecture

## Frontend

Recommended:
- Next.js
- TypeScript
- Tailwind CSS
- Responsive/mobile-first UI
- Server-side rendering for SEO-sensitive pages
- Client-side interactive comparison/search components

Recommended UI priorities:
- Fast first render
- Large touch targets
- Sticky comparison controls on mobile
- Bottom navigation on mobile if useful
- Desktop sidebar/search/filter layout
- Dark mode optional

## Backend

Recommended:
- Next.js server/API routes OR separate TypeScript backend
- PostgreSQL
- pgvector
- Object storage/local media storage for permitted assets
- Background job worker

Use one repository unless there is a strong reason to split services.

## Database

PostgreSQL + pgvector.

Use migrations.

Do NOT make the vector database the source of truth.

Structured relational tables remain authoritative for:
- manufacturers
- models
- generations
- variants/trims
- prices
- specifications
- sources
- documents
- media
- discussions
- users
- update jobs

pgvector is for retrieval.

---

# 4. Suggested repository structure

```text
/
├─ app/
│  ├─ (public)/
│  │  ├─ cars/
│  │  ├─ compare/
│  │  ├─ search/
│  │  ├─ discussions/
│  │  └─ news/
│  ├─ admin/
│  └─ api/
├─ components/
├─ lib/
│  ├─ ai/
│  ├─ embeddings/
│  ├─ search/
│  ├─ sources/
│  ├─ pricing/
│  └─ validation/
├─ workers/
│  ├─ crawler/
│  ├─ brochure/
│  ├─ extraction/
│  ├─ embedding/
│  └─ update/
├─ db/
│  ├─ migrations/
│  └─ seed/
├─ scripts/
├─ public/
├─ storage/
├─ tests/
├─ docs/
├─ .env.example
├─ docker-compose.yml
└─ README.md
```

Adapt to the existing server/project conventions rather than blindly replacing an existing codebase.

---

# 5. Database model

## 5.1 manufacturers

Fields:

- id
- name
- slug
- country
- official_url
- logo_media_id
- active
- created_at
- updated_at

Examples:
- Toyota
- Honda
- BYD
- MG
- Tesla
- GWM
- AION
- NETA
- Changan/Deepal
- Geely
- OMODA/Jaecoo
- Volvo
- BMW
- Mercedes-Benz
- etc.

Do not hardcode only the above list.

---

## 5.2 models

Represents a model family.

Fields:

- id
- manufacturer_id
- name
- slug
- body_type
- segment
- generation
- model_year
- Thailand_status
- official_url
- description
- created_at
- updated_at

Example:

Toyota Camry

Do NOT treat every trim as a separate model.

---

## 5.3 variants / trims

Represents the actual purchasable version.

Fields:

- id
- model_id
- name
- slug
- model_year
- drivetrain
- transmission
- fuel_type
- battery_kwh
- motor_power_kw
- motor_power_hp
- torque_nm
- range_claimed
- range_standard
- charging_ac_kw
- charging_dc_kw
- acceleration_0_100
- top_speed
- seats
- doors
- status
- first_seen_at
- last_verified_at

Important:
Variant names must preserve the official Thai/English naming.

Examples:
- X+
- D
- Premium
- Long Range
- Performance
- RS
- GR Sport

Do not normalize away meaningful trim suffixes.

---

# 6. Pricing model

Do NOT store only one `price` field.

Use:

## prices

- id
- variant_id
- price_type
- amount_thb
- currency
- valid_from
- valid_to
- source_id
- confidence
- notes
- is_current

price_type examples:
- msrp
- official_price
- promotional_price
- launch_price
- special_dealer_price
- estimated_price

The UI must clearly label:
- Official list price
- Current official promotion
- Dealer promotion
- Estimated/unverified price

Never silently replace MSRP with promotional price.

Maintain price history.

---

# 7. Specification model

Avoid one giant JSON blob as the only storage mechanism.

Use normalized core fields plus flexible JSON for less common equipment.

Suggested tables:

- dimensions
- performance_specs
- battery_specs
- charging_specs
- warranty_specs
- safety_specs
- adas_features
- equipment
- interior_features
- exterior_features
- infotainment_features

Also allow:

```text
variant_specs_extra JSONB
```

for uncommon fields.

---

# 8. Equipment / feature normalization

A major goal is being able to answer questions like:

- Which cars under 1 million THB have adaptive cruise?
- Which EVs have 800V charging?
- Which cars have ventilated seats?
- Which trims have 360 camera?
- Which cars have powered tailgate?
- Which models have lane centering?
- Which cars have V2L?
- Which models have heat pump?

Therefore create canonical feature IDs.

Example:

```text
feature:
  adaptive_cruise_control
  lane_centering
  blind_spot_monitor
  rear_cross_traffic_alert
  surround_view_camera
  ventilated_front_seats
  powered_tailgate
  wireless_android_auto
  wireless_apple_carplay
  v2l
  heat_pump
```

Store:
- feature_id
- variant_id
- availability
- standard/optional
- source_id
- confidence

Do not infer that a feature exists merely because a higher trim has it.

---

# 9. Source/provenance model

## sources

Fields:

- id
- url
- canonical_url
- domain
- source_type
- publisher
- title
- retrieved_at
- published_at
- language
- credibility_score
- content_hash
- status

source_type:

- official_manufacturer
- official_brochure
- official_price_list
- official_press_release
- authorized_dealer
- automotive_media
- news
- social
- community
- user_submission

## source_documents

Fields:

- id
- source_id
- document_type
- local_path/object_key
- mime_type
- file_hash
- page_count
- extracted_text
- extraction_status
- rights_status
- created_at

For PDFs, preserve page numbers during extraction.

---

# 10. Brochure ingestion

The update agent should discover real brochures.

Pipeline:

```text
discover URL
    ↓
validate access
    ↓
download only when allowed
    ↓
calculate SHA-256
    ↓
detect duplicate
    ↓
extract PDF text
    ↓
OCR if necessary
    ↓
extract tables
    ↓
identify vehicle/trim
    ↓
validate against existing data
    ↓
create proposed changes
    ↓
confidence scoring
    ↓
auto-apply safe changes
    ↓
flag conflicts for review
    ↓
embed useful chunks
```

For every PDF chunk preserve:
- source_id
- document_id
- page_number
- text
- vehicle_id/variant_id if known

This is critical for AI citations.

---

# 11. Image strategy

Use official/manufacturer images whenever possible.

Store:

- media_id
- source_url
- local/object path if legally permitted
- alt_text
- image_type
- vehicle_id
- variant_id
- source_id
- rights_status
- width
- height
- hash

image_type examples:

- hero
- exterior
- interior
- dashboard
- wheel
- charging
- safety
- color
- brochure_render

Do not use random Google image results as authoritative vehicle imagery.

If an official page references an image, record its source.

---

# 12. Semantic search architecture

Use PostgreSQL + pgvector.

Recommended embedding record:

```text
embeddings
- id
- entity_type
- entity_id
- chunk_type
- content
- metadata JSONB
- source_id
- embedding vector(...)
- created_at
- updated_at
```

Chunk types:

- model_summary
- variant_specs
- price
- equipment
- brochure_page
- brochure_section
- official_article
- media_review
- community_post
- news

Embedding provider must be configurable.

Environment example:

```env
AI_PROVIDER=openai
AI_API_KEY=
AI_MODEL=
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=
EMBEDDING_MODEL=
EMBEDDING_DIMENSIONS=
```

Do not hardcode API keys.

---

# 13. Hybrid search

Do NOT rely on vector search alone.

Implement:

1. Exact/keyword search
2. PostgreSQL full-text search
3. pgvector similarity
4. Structured filters
5. Optional reranking

Example query:

> "รถไฟฟ้าไม่เกิน 800,000 ที่เบาะระบายอากาศ"

The system should:
- parse budget
- identify EV
- identify ventilated seats
- filter structured data
- semantic-search supporting evidence
- return exact matching variants

---

# 14. AI Q&A

The user can ask:

> MG S5 X+ เทียบกับ BYD Sealion 5 Premium ยังไง

AI flow:

```text
user question
    ↓
intent detection
    ↓
entity/model/variant extraction
    ↓
structured DB filters
    ↓
keyword search
    ↓
vector search
    ↓
source ranking
    ↓
context assembly
    ↓
LLM
    ↓
answer + source references
```

The AI should answer in Thai by default.

It should explicitly distinguish:

- Fact
- Source-backed comparison
- Community opinion
- AI analysis

Example:

> "ตามโบรชัวร์..."
> "จากเว็บทางการ..."
> "ผู้ใช้บางรายรายงาน..."
> "จากข้อมูลที่มี ผมประเมินว่า..."

Never fabricate a citation.

---

# 15. AI configuration

Support multiple providers.

Example `.env`:

```env
AI_PROVIDER=openai
AI_API_KEY=
AI_MODEL=

EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=
EMBEDDING_MODEL=

# Optional second provider
AI_FALLBACK_PROVIDER=
AI_FALLBACK_API_KEY=
AI_FALLBACK_MODEL=
```

Also create an admin settings page if appropriate.

API keys must:
- never be sent to the browser
- never appear in HTML
- never be logged
- never be stored in Git
- never be returned through public API responses

Server-side only.

---

# 16. Update agent

Create a separate update worker.

Responsibilities:

1. Discover new models
2. Discover new trims
3. Find current official prices
4. Find official brochures
5. Detect changed brochures
6. Detect changed specifications
7. Detect new promotions
8. Find relevant automotive news
9. Find public community discussion
10. Propose updates
11. Record source provenance
12. Re-embed changed content

Run periodically.

Recommended initial schedule:
- official price/spec scan: daily
- brochure scan: daily/weekly
- news scan: every few hours
- community discovery: every few hours
- deep full catalog verification: weekly

Do not aggressively crawl every website.

Use per-domain rate limits.

---

# 17. Update conflict system

Never silently overwrite conflicting facts.

Example:

Official site says:

```text
699,000 THB
```

Dealer says:

```text
679,000 THB
```

Store both.

Mark:
- official_price = 699000
- dealer_promotion = 679000

The UI should show:

> ราคาอย่างเป็นทางการ 699,000 บาท
>
> พบโปรโมชันดีลเลอร์ 679,000 บาท
>
> ตรวจพบเมื่อ: YYYY-MM-DD

---

# 18. Confidence system

Every extracted fact should have confidence.

Example:

```text
0.98 = official structured page
0.97 = official brochure table
0.90 = official press release
0.80 = reputable media quoting official source
0.65 = dealer
0.45 = community
```

These are starting heuristics, not absolute truth.

Confidence should also consider:
- source freshness
- agreement with other sources
- extraction quality
- whether value is directly stated
- OCR quality

---

# 19. Data verification

Create an automated validation layer.

Checks:

- price is positive
- currency is THB
- battery kWh plausible
- power/torque plausible
- dimensions plausible
- wheelbase < overall length
- seats integer
- model/trim names are not duplicated
- price history doesn't overlap incorrectly
- source exists for important facts
- discontinued trims are not shown as current
- old prices are not marked current
- contradictory official values are flagged

Do not "fix" suspicious data silently.

Flag it.

---

# 20. Vehicle page

Each vehicle family page should contain:

- Hero image
- Current price range
- Trim selector
- Model overview
- Key specifications
- All trims
- Price history
- Equipment comparison
- Dimensions
- Performance
- Battery/charging
- Warranty
- Safety/ADAS
- Official brochure
- Official source links
- Media reviews
- Community discussion
- News
- AI "ถามเกี่ยวกับรุ่นนี้"

Example URL:

```text
/cars/mg/s5-ev
/cars/mg/s5-ev/x-plus
```

---

# 21. Comparison system

Users can compare 2–4 variants.

Example:

```text
MG S5 EV X+
BYD Atto 3 Extended
Tesla Model 3 Premium
Toyota Camry HEV Premium
```

Comparison categories:

- Price
- Size
- Cabin
- Power
- Torque
- acceleration
- top speed
- battery
- range
- charging
- fuel economy
- warranty
- ADAS
- safety
- comfort
- equipment
- trunk/cargo
- ownership notes

Important:
The UI must allow "compare only meaningful differences".

---

# 22. User comments / community

Create discussion objects linked to:

- model
- variant
- manufacturer
- news article
- general category

Suggested tables:

```text
users
threads
posts
post_reactions
post_reports
tags
thread_tags
mentions
```

A thread can be:

```text
general
car_model
variant
news
buying_advice
ownership
maintenance
charging
```

---

# 23. Community moderation

At minimum:

- report post
- edit history
- soft delete
- rate limiting
- spam detection
- duplicate detection
- blocked words
- moderator queue

AI can assist moderation but should not automatically ban users solely based on an uncertain model output.

---

# 24. AI classification for community

When a user posts:

> "S5 X+ นั่งหลังสบายไหม"

Classify it into:

```text
model = MG S5 EV
variant = X+
topic = comfort
intent = question
```

Then index it.

The car page can show:

> ชุมชนกำลังพูดถึง
>
> - ความนุ่มนวล
> - เบาะหลัง
> - เสียงลม
> - ADAS
> - การกินไฟ

Do not convert anecdotal comments into specifications.

---

# 25. News system

News should be separate from official vehicle data.

Fields:

- title
- slug
- source
- original_url
- published_at
- summary
- image
- related_models
- related_manufacturers
- tags

Do not copy full articles.

Store:
- headline
- short original summary or generated summary
- source link

Clearly identify source.

---

# 26. Search UX

Global search should understand:

- model names
- trim names
- Thai names
- English names
- misspellings
- abbreviations
- price ranges
- features

Examples:

```text
mg s5
เอ็มจี s5
s5 x+
รถไฟฟ้า 7 แสน
รถไม่เกินล้าน
รถ ev ชาร์จเร็ว
camry hybrid
```

Use aliases table:

```text
aliases
- entity_type
- entity_id
- alias
```

---

# 27. Discovery / ingestion sources

The agent should build a source registry.

Example categories:

### Official manufacturers/importers
- Manufacturer Thailand websites
- Official model pages
- Official downloadable brochures
- Official price lists
- Official press releases

### Automotive media
Use reputable Thai automotive media for:
- launches
- test drives
- updates
- promotions
- real-world observations

### Public social sources
Use only publicly accessible content for:
- owner complaints
- common issues
- user experiences
- observed pricing

Community claims must remain labeled as anecdotal.

---

# 28. Source crawler design

Create:

```text
source_registry
```

Fields:

- domain
- source_type
- crawl_enabled
- crawl_interval
- rate_limit_ms
- allowed_paths
- blocked_paths
- parser
- last_crawled_at
- last_success_at
- last_error

Do not make a universal crawler that blindly scrapes everything.

Use domain-specific adapters where necessary.

Example:

```text
OfficialToyotaAdapter
OfficialMGAdapter
OfficialBYDAdapter
GenericPDFAdapter
GenericNewsAdapter
```

Generic extraction is fallback only.

---

# 29. Change detection

For every important source:

```text
fetch
→ normalize
→ hash
→ compare
→ detect changed content
→ extract
→ compare fields
→ generate proposed update
```

Store:

```text
data_change_log
```

Fields:

- entity
- field
- old_value
- new_value
- source_id
- detected_at
- confidence
- applied
- reviewed_by
- review_status

---

# 30. Admin dashboard

Required:

## Catalog
- manufacturers
- models
- trims
- prices

## Sources
- source registry
- broken sources
- new sources
- source health

## Documents
- brochures
- extraction status
- OCR status
- duplicate documents

## Data review
- pending changes
- conflicts
- suspicious values

## AI
- provider
- model
- embedding provider
- usage
- errors
- latency

## Crawl jobs
- running
- completed
- failed
- last run
- next run

## Community
- reports
- moderation queue
- spam

---

# 31. API design

Example endpoints:

```text
GET /api/cars
GET /api/cars/:slug
GET /api/cars/:slug/variants
GET /api/compare
GET /api/search
POST /api/ai/ask

GET /api/sources/:id
GET /api/brochures/:id

GET /api/discussions
POST /api/discussions
POST /api/posts

GET /api/news
```

Admin:

```text
POST /api/admin/crawl
POST /api/admin/reindex
POST /api/admin/verify
GET  /api/admin/conflicts
POST /api/admin/approve-change
```

---

# 32. Security

Implement:

- authentication
- authorization
- CSRF protection where relevant
- rate limiting
- request validation
- SQL injection protection
- XSS protection
- secure cookies
- server-side API keys
- upload validation
- file size limits
- SSRF protection for URL fetching
- crawler domain allowlist
- timeout limits
- logging without secrets

The crawler must not allow arbitrary user-supplied URLs to reach internal network addresses.

Block:
- localhost
- 127.0.0.0/8
- private RFC1918 networks
- link-local addresses
- cloud metadata endpoints

---

# 33. SEO

Vehicle pages should be indexable.

Generate:
- title
- meta description
- canonical URL
- OpenGraph image
- structured data where appropriate

Example:

```text
MG S5 EV X+ ราคา 699,000 บาท | สเปก ออปชัน เทียบรุ่น
```

Do not claim current price in SEO metadata if it is not verified.

---

# 34. Mobile UX

Prioritize mobile.

Vehicle page:

```text
[image]

MG S5 EV
เริ่มต้น xxx,xxx บาท

[ถาม AI] [เปรียบเทียบ]

Key specs
Price
Range
Power
Battery

[เลือกเกรด]
```

Comparison should be horizontally scrollable but also have:
- sticky row labels
- highlight differences
- "show differences only"

Community:
- easy reply
- image upload
- report
- quote
- notification

---

# 35. AI source citations

Every AI factual answer should ideally expose evidence.

Example:

> MG S5 EV X+ มีแบตเตอรี่ ... ตามโบรชัวร์...

Then UI:

```text
แหล่งข้อมูล
[MG Thailand — Brochure 2026, หน้า 8]
[MG Thailand — Model Page]
```

For PDF evidence, retain page number.

The LLM must receive source IDs, not just raw text.

---

# 36. RAG prompt policy

System prompt should enforce:

1. Never invent specifications.
2. Never invent prices.
3. If sources conflict, explain conflict.
4. Prefer official Thai sources.
5. State date of source when useful.
6. Separate facts from opinions.
7. Do not turn community comments into facts.
8. Say "ไม่พบข้อมูล" when evidence is insufficient.
9. Do not infer an option exists merely because it exists in another trim.
10. Do not use outdated price as current price.

---

# 37. Embedding strategy

Embed chunks rather than entire brochures.

Recommended chunk size:
- roughly 300–800 tokens
- overlap 50–120 tokens

Keep metadata:

```json
{
  "manufacturer": "MG",
  "model": "S5 EV",
  "variant": "X+",
  "source_type": "official_brochure",
  "page": 8
}
```

For exact specs, structured DB should be preferred over vector retrieval.

Vector search is supporting evidence and discovery.

---

# 38. Ranking

Suggested retrieval score:

```text
final_score =
  0.40 * semantic_similarity
+ 0.25 * keyword_score
+ 0.20 * source_quality
+ 0.10 * freshness
+ 0.05 * entity_match
```

Tune after real-world evaluation.

For exact price/spec questions, structured DB gets priority.

---

# 39. Initial data population

The agent should NOT attempt to scrape every Thai car in one huge uncontrolled job.

Phase 1:
- Build source adapters
- Import a manageable set of major brands
- Verify schema
- Validate prices
- Verify brochure extraction
- Test RAG

Phase 2:
- Expand brands
- Add more trims
- Add price history
- Add community

Phase 3:
- News
- automated change detection
- recommendation/search intelligence

---

# 40. Suggested initial coverage

Start with popular Thai-market brands and models.

Do not hardcode a permanent brand list.

Create a configurable source registry and seed current models from official sources.

Priority can be:

```text
Tesla
BYD
MG
Toyota
Honda
GWM
AION
Changan
Deepal
Geely
OMODA
JAECOO
NETA
Volvo
BMW
Mercedes-Benz
Hyundai
Kia
Isuzu
Ford
Mitsubishi
Nissan
Mazda
Suzuki
```

The list should be expanded based on actual Thai-market availability.

---

# 41. Comparison philosophy

The product should not blindly say "best".

Instead provide:

### Objective
- price
- dimensions
- power
- equipment
- warranty
- charging
- efficiency

### Source-backed interpretation
- comfort evidence
- owner feedback
- common complaints

### AI analysis
- value proposition
- likely fit
- tradeoffs

Example:

```text
คุ้มกว่าในด้านอุปกรณ์
คุ้มกว่าในด้านราคา
ได้เปรียบด้านขนาด
ได้เปรียบด้านการชาร์จ
มีความเสี่ยงด้าน...
```

Make it clear these are analyses, not manufacturer claims.

---

# 42. Recommendation engine

Later phase.

User can say:

> มีงบ 800,000 อยากได้ EV นั่งสบาย ไม่เกิน 120 km/h

System converts to constraints:

```text
budget <= 800000
fuel_type = EV
priority = comfort
top_speed_requirement <= 120 OR user preference
```

Then rank variants.

Do not use subjective AI scoring as the only mechanism.

Use transparent weighted criteria.

---

# 43. Data freshness

Show:

```text
ตรวจสอบข้อมูลล่าสุด: 24 ส.ค. 2026
```

For individual fields, show:
- last verified
- source date
- source

A price should not simply say "current" if it has not been checked recently.

---

# 44. Testing

Required tests:

## Unit
- price parser
- trim parser
- spec parser
- PDF extraction
- source ranking
- embedding metadata

## Integration
- PostgreSQL
- pgvector
- AI provider
- crawler
- PDF ingestion

## E2E
- mobile search
- car page
- comparison
- AI question
- community post
- admin approval

## Data tests
Create fixtures with:
- conflicting prices
- old brochures
- duplicate trims
- OCR mistakes
- dealer promotions
- discontinued models

---

# 45. Observability

Log:

- crawl job ID
- source ID
- duration
- HTTP status
- extraction result
- changed entities
- embedding count
- AI latency
- AI errors
- token usage if available

Never log:
- API keys
- auth tokens
- private user data unnecessarily

---

# 46. Cost control

The system should minimize LLM/embedding cost.

Use:

- hash-based change detection
- cache
- deduplication
- only re-embed changed chunks
- structured DB for exact lookup
- smaller model for classification
- larger model only for complex reasoning
- batch embedding
- queue workers

Do not send the entire catalog to the LLM.

---

# 47. AI provider abstraction

Implement interface:

```ts
interface AIProvider {
  chat(input: ChatInput): Promise<ChatOutput>
  embed(input: string[]): Promise<EmbeddingOutput>
}
```

Providers should be swappable.

Do not couple the database to one AI vendor.

---

# 48. Deployment

Assume PostgreSQL + pgvector already exists on the server.

The agent must inspect the existing environment before changing anything.

First inspect:

```bash
uname -a
docker --version
docker compose version
node --version
pnpm --version || npm --version
psql --version
```

Then inspect PostgreSQL:

```sql
SELECT version();
SELECT extname FROM pg_extension;
```

Verify:

```text
vector
```

exists.

Do not reinstall PostgreSQL if the existing instance is usable.

---

# 49. Environment configuration

Create:

```text
.env.example
```

with:

```env
DATABASE_URL=

AI_PROVIDER=
AI_API_KEY=
AI_MODEL=

EMBEDDING_PROVIDER=
EMBEDDING_API_KEY=
EMBEDDING_MODEL=
EMBEDDING_DIMENSIONS=

NEXT_PUBLIC_APP_URL=

STORAGE_PROVIDER=
STORAGE_BUCKET=
STORAGE_ENDPOINT=
STORAGE_ACCESS_KEY=
STORAGE_SECRET_KEY=

CRAWLER_USER_AGENT=
```

Never commit `.env`.

---

# 50. Agent execution plan

Hermes Agent should execute in this order.

## Step 1 — Inspect

- inspect server
- inspect existing project
- inspect PostgreSQL
- inspect pgvector
- inspect available disk
- inspect runtime
- inspect existing reverse proxy
- inspect existing services
- inspect environment variables

Do not destroy an existing project.

## Step 2 — Plan

Create:

```text
docs/implementation-plan.md
```

and identify:
- what already exists
- what needs to be added
- conflicts
- deployment strategy

## Step 3 — Scaffold

Build application skeleton.

## Step 4 — Database

Create migrations.

## Step 5 — Core catalog

Implement:
- manufacturers
- models
- variants
- prices
- specs
- sources

## Step 6 — Source ingestion

Implement official source adapters and generic PDF ingestion.

## Step 7 — Search

Implement:
- FTS
- pgvector
- hybrid search

## Step 8 — AI

Implement RAG and provider abstraction.

## Step 9 — UI

Implement:
- search
- vehicle pages
- comparison
- AI chat
- source display

## Step 10 — Community

Implement discussions and moderation.

## Step 11 — Update workers

Implement scheduled crawling/update pipeline.

## Step 12 — Testing

Run tests and data validation.

## Step 13 — Seed data

Import initial Thai-market catalog from verified sources.

## Step 14 — Deployment

Deploy without breaking existing services.

---

# 51. Very important: data quality gate

Before marking the project "done", Hermes must demonstrate at least:

- multiple manufacturers
- multiple models
- multiple trims
- current prices with sources
- at least several real brochures
- PDF page-level source references
- working semantic search
- working hybrid search
- working AI Q&A
- working comparison
- working mobile layout
- working admin source/change review

Do not seed fake data just to make the UI look populated.

If a value is unavailable, use null and show "ไม่มีข้อมูล".

Never fabricate realistic-looking specifications.

---

# 52. Acceptance test examples

Test question:

> "MG S5 EV X+ ราคาเท่าไหร่"

Expected:
- exact variant resolution
- current official price
- source
- date verified

Test:

> "S5 X+ กับ Model 3 Premium ขนาดต่างกันยังไง"

Expected:
- structured dimension comparison
- source-backed values
- no invented dimensions

Test:

> "รถไม่เกิน 800,000 ที่มีเบาะระบายอากาศ"

Expected:
- structured filtering
- variant-level result
- source evidence

Test:

> "คนใช้ S5 บ่นเรื่องอะไร"

Expected:
- community/media evidence
- clearly labeled anecdotal information
- no claim that complaints are universal

Test:

> "โบรชัวร์บอกว่าอะไรเกี่ยวกับ ADAS"

Expected:
- brochure retrieval
- page reference
- direct evidence
- AI summary

---

# 53. Recommended additional feature: "Why this answer?"

Every AI answer should optionally expose:

```text
ข้อมูลที่ใช้ตอบ
- Official brochure, p. 8
- Official price page
- 4 community posts
- 2 automotive articles
```

This is a major trust feature.

---

# 54. Recommended additional feature: "Data timeline"

Vehicle page should optionally show:

```text
24 Aug 2026 — Price verified
18 Aug 2026 — New brochure detected
10 Aug 2026 — Promotion detected
02 Aug 2026 — Specification updated
```

This makes the system useful even when prices change frequently.

---

# 55. Recommended additional feature: "Report incorrect data"

Every important fact should have:

```text
ข้อมูลนี้ผิดหรือไม่?
[แจ้งแก้ไข]
```

Users can submit:
- corrected price
- corrected trim
- missing feature
- broken source
- wrong image

User submissions should enter review flow and should not directly overwrite authoritative data.

---

# 56. Final implementation rule

Build the system as a **source-backed automotive knowledge platform**, not a simple CRUD car website.

The most important architectural rule is:

```text
Structured facts
    +
Source provenance
    +
Hybrid retrieval
    +
RAG
    +
Human/reviewable change control
    +
Community evidence
```

The system must remain useful even if the AI provider is changed.

The system must remain useful even if vector search is temporarily unavailable.

The database must remain the source of truth.

---

# 57. Deliverables expected from Hermes Agent

At minimum:

```text
README.md
.env.example
docs/implementation-plan.md
docs/data-model.md
docs/source-policy.md
database migrations
application source
worker source
tests
seed scripts
deployment instructions
```

And a working deployed web application.

At the end, report:

1. What was built
2. Where it is deployed
3. Database used
4. pgvector status
5. AI provider/model
6. Embedding provider/model
7. Number of manufacturers
8. Number of models
9. Number of variants
10. Number of verified price records
11. Number of brochures
12. Number of indexed chunks
13. Number of source records
14. Number of tests passed
15. Remaining data-quality issues
16. Scheduled update jobs
17. Any legal/access limitations encountered

Do not claim success for an item that was not actually verified.



# Blueprint v2 — Research Agent / Official Media Ingestion Upgrade

> This section supersedes the earlier generic crawler/media assumptions.
> Version 1 had two practical failures:
> 1. The agent often failed to locate the actual official brochure.
> 2. It failed to reliably identify/extract the correct official vehicle images from manufacturer websites or brochures.
>
> The implementation must therefore treat **web research, document discovery, image discovery, and verification as first-class engineering problems**, not as a simple scraper.

---

# 58. Agent role split

Use Hermes Agent with **GPT-5.6 Luna** as the primary reasoning/coding/research model.

The same agent environment may perform:

- project implementation
- database migrations
- source research
- official website inspection
- brochure discovery
- image discovery
- data extraction
- validation
- scheduled refresh jobs
- troubleshooting

Do NOT assume that one prompt to an LLM is sufficient to discover a brochure.

The system must provide explicit tools/workflows for:

```text
search
→ open official site
→ inspect model page
→ inspect links
→ inspect downloads
→ inspect PDFs
→ inspect image URLs
→ inspect source HTML when permitted
→ follow official document links
→ verify vehicle identity
→ record provenance
```

---

# 59. Official-source discovery must be multi-pass

When adding/updating a vehicle, do NOT search only for:

```text
"MG S5 brochure"
```

Use a search strategy.

## Pass A — Official domain discovery

Find the official Thai manufacturer/importer domain first.

Examples of search intents:

```text
<brand> Thailand official
<model> Thailand official
<model> site:<official-domain>
```

The agent must identify the authoritative Thai-market domain before trusting search results.

---

## Pass B — Model page discovery

Search:

```text
<model> official
<model> ราคา official
<model> brochure official
<model> specification official
<model> download official
<model> pdf official
```

Prefer pages on the verified official domain.

---

## Pass C — Internal-link traversal

Once the official model page is found, inspect:

- page links
- download buttons
- PDF links
- brochure links
- specification links
- price list links
- media/download sections
- hidden or secondary model pages
- regional/Thai subdomains
- asset/CDN URLs

Do not stop merely because the model page itself does not visibly show "Brochure".

A brochure may be exposed through:
- Download PDF
- Specifications
- Catalogue
- Product information
- Downloads
- Media
- Resources
- Price list
- campaign landing page

---

# 60. Brochure discovery strategy

Implement a dedicated `brochure_discovery` pipeline.

```text
model
  ↓
official-domain resolver
  ↓
official model-page resolver
  ↓
link extraction
  ↓
PDF candidate detection
  ↓
candidate scoring
  ↓
PDF verification
  ↓
vehicle/market/year verification
  ↓
brochure registration
```

## Candidate scoring

A candidate brochure should receive a score based on:

- official domain
- URL contains model name
- document title contains model name
- Thai-market indicators
- model-year match
- publication/update date
- official page links directly to PDF
- PDF contains expected model name
- PDF contains Thai language
- PDF contains price/specification terms
- document is current

Example conceptual score:

```text
official_domain       +40
official_page_link    +20
model_name_match      +15
Thailand_match        +10
Thai_text             +5
year_match             +5
specification_match   +5
```

Thresholds should be configurable.

Do not trust search-result snippets alone.

---

# 61. Brochure verification

A PDF is not accepted as the model brochure merely because its filename looks correct.

Verification should inspect:

1. PDF metadata
2. first page
3. title/cover
4. text extraction
5. relevant specification pages
6. model name
7. trim names
8. market/country indicators
9. model year where available
10. source page that linked to the PDF

Store:

```text
brochure_verification
- document_id
- model_match
- market_match
- year_match
- trim_match
- official_link_match
- verification_score
- verified_at
```

If the PDF is ambiguous, mark it:

```text
needs_review
```

Do not ingest it as authoritative.

---

# 62. Search engine discovery fallback

If the official site navigation is poor, the agent may use public search engines to discover official assets.

Search patterns should include:

```text
site:official-domain model brochure
site:official-domain filetype:pdf model
site:official-domain model catalogue
site:official-domain model specification
site:official-domain model price
```

Also search likely asset/CDN paths where search results expose them.

Important:

Search results are for discovery.

The final source must be verified by opening the actual official page/document whenever possible.

---

# 63. Brochure versioning

Never treat a brochure as a single permanent document.

A model can have:

```text
2024 brochure
2025 brochure
2026 brochure
facelift brochure
MY2026 brochure
promotion brochure
```

Each document gets:

```text
document_id
model_id
market
model_year
publication_date
retrieved_at
content_hash
status
```

If the file changes:

```text
new hash
→ new document version
→ compare extracted facts
→ generate changes
```

Never delete the old version.

---

# 64. Image discovery must be a dedicated pipeline

Do not ask the LLM to "find an image" and assume the resulting URL is correct.

Implement:

```text
official model page
        ↓
extract image candidates
        ↓
extract src/srcset/og:image
        ↓
extract JSON-LD image
        ↓
inspect linked image/CDN URLs
        ↓
extract brochure images where permitted
        ↓
download/cache where permitted
        ↓
verify image identity
        ↓
store provenance
```

Image sources should be ranked:

1. Official model page hero image
2. Official model page gallery
3. Official media/download asset
4. Official brochure
5. Official press release
6. Authorized dealer
7. Other sources only as clearly labeled fallback

---

# 65. Web image extraction

The browser/research agent should inspect:

- `<img src>`
- `srcset`
- lazy-loading attributes
- OpenGraph `og:image`
- Twitter/X card image
- JSON-LD `image`
- CSS background images where practical
- gallery data embedded in JavaScript
- API/JSON payloads exposed to the page
- linked CDN assets

The agent should not rely only on the visual screenshot of the page.

Example:

```text
visible image
    ↓
find DOM element
    ↓
resolve highest-resolution source
    ↓
record canonical/source URL
```

Prefer the original/high-resolution asset rather than a thumbnail.

---

# 66. Image identity verification

A downloaded image must be checked against the intended vehicle.

At minimum verify:

- brand
- model
- body style
- generation/facelift
- exterior/interior
- trim if identifiable
- color if known

Use multiple signals:

```text
source URL
page context
alt text
filename
nearby text
structured metadata
visual inspection when necessary
```

The AI may assist with image classification, but the final record must preserve the source page.

Do not label a generic brand image as a model-specific image.

---

# 67. Image roles

Store explicit roles:

```text
hero
exterior_front
exterior_rear
exterior_side
interior_front
interior_rear
dashboard
infotainment
wheel
charging
safety
adas
color
brochure_cover
brochure_page
press_photo
```

This allows the UI to construct a proper gallery instead of showing arbitrary images.

---

# 68. Image duplicate detection

Use:

- SHA-256 for exact duplicates
- perceptual hash for resized/recompressed duplicates

Store:

```text
content_hash
perceptual_hash
width
height
mime_type
file_size
```

Do not store the same image repeatedly just because it appears on multiple official pages.

Keep multiple source references if necessary.

---

# 69. Image rights/provenance

Every image needs:

```text
source_url
source_page_url
source_type
rights_status
retrieved_at
```

Possible rights status:

```text
unknown
reference_only
official_public_asset
licensed
user_uploaded
do_not_redistribute
```

If redistribution rights are unclear:

- keep source URL
- optionally keep a temporary/cache copy for processing if permitted
- do not expose the local copy publicly
- use the official source URL in the UI

Do not assume "official website" automatically means unlimited redistribution rights.

---

# 70. If brochure contains images

Treat brochure images separately from brochure text.

Pipeline:

```text
PDF
 ↓
identify pages
 ↓
extract embedded images
 ↓
render pages when necessary
 ↓
detect vehicle images
 ↓
associate page number
 ↓
associate model/variant
 ↓
store provenance
```

Prefer extracting the original embedded image when possible.

If only a rendered page is available, mark it as:

```text
derived_from_pdf_page
```

rather than pretending it is the original image asset.

---

# 71. Browser-first research

For difficult official websites, the agent should use an actual browser-capable research path if available.

Do not depend exclusively on:

```text
HTTP GET → parse HTML
```

Modern manufacturer sites may use:

- JavaScript rendering
- client-side routing
- API requests
- lazy-loaded galleries
- dynamically inserted download links

The research process should therefore support:

```text
browser-rendered page
+
DOM inspection
+
network/resource discovery where available
```

If browser tooling is unavailable, fall back to:
- search engine discovery
- HTML parsing
- public JSON/metadata
- direct public asset URLs

---

# 72. Do not let the LLM hallucinate missing assets

This is a hard rule.

Bad:

```text
LLM: "The official brochure can be found at..."
```

without actually opening/verifying it.

Correct:

```text
candidate URL found
→ fetch/open
→ verify PDF
→ calculate hash
→ record source
```

If no brochure is found:

```text
brochure_status = not_found
```

and record:

```text
searched_at
domains_searched
queries_used
pages_checked
reason
```

Then retry on a later scheduled run.

---

# 73. Research evidence log

Create:

```text
research_runs
```

Fields:

```text
id
entity_type
entity_id
started_at
completed_at
agent_model
search_queries
domains_checked
pages_checked
documents_found
images_found
facts_changed
status
error
```

This makes it possible to diagnose why an agent failed.

Example:

```text
MG S5 EV
Run #142
GPT-5.6 Luna
Official MG domain checked
Model page checked
3 download links checked
2 PDFs found
1 verified as 2026 Thai brochure
18 image candidates
7 accepted
```

---

# 74. Two-stage research architecture

Do not have one giant agent prompt perform everything.

Use:

## Stage A — Discovery

Goal:

> Find candidate official pages, PDFs, images, and sources.

Output structured candidates.

## Stage B — Verification

Goal:

> Open each candidate and determine whether it actually belongs to this vehicle/market/year/trim.

Output verified sources.

## Stage C — Extraction

Goal:

> Extract structured facts from verified sources.

## Stage D — Reconciliation

Goal:

> Compare new values with existing database and detect conflicts.

## Stage E — Indexing

Goal:

> Update embeddings only for changed content.

This is much more reliable than one-shot agent scraping.

---

# 75. Scheduled cron design

The cron job must NOT simply say:

```text
"Search the internet for new car data."
```

Instead:

```text
job
 ↓
select entities due for refresh
 ↓
run discovery
 ↓
run verification
 ↓
run extraction
 ↓
run reconciliation
 ↓
run validation
 ↓
apply safe changes
 ↓
queue conflicts
 ↓
re-index changed chunks
 ↓
record research run
```

---

# 76. Refresh priority

Prioritize:

### High frequency
- current prices
- promotions
- official model pages
- newly published brochures
- model availability

### Medium frequency
- equipment/specification
- official images
- press releases

### Lower frequency
- dimensions
- core mechanical specs
- historical documents

### Event-driven where possible
- new model launch
- facelift
- price cut
- Motor Show promotion
- trim discontinuation

---

# 77. Cron failure behavior

If one website fails:

DO NOT fail the entire update job.

Use:

```text
source A → success
source B → timeout
source C → success
```

Result:

```text
partial_success
```

Keep previous verified data.

Do not set fields to null merely because the website temporarily failed.

---

# 78. Price protection

This is especially important.

A failed crawl must never cause:

```text
current_price = null
```

because the official page temporarily returned an error.

Instead:

```text
last_verified_price remains current
source_status = temporarily_unavailable
```

Only update after successful verification.

---

# 79. Image protection

Likewise, if an image URL disappears:

Do not immediately delete the current hero image.

Use:

```text
active
missing_on_latest_scan
retired
```

Only retire after repeated failed scans or explicit source confirmation.

---

# 80. AI model task routing

Use GPT-5.6 Luna for difficult reasoning tasks.

Suggested tasks:

### GPT-5.6 Luna
- difficult source identification
- brochure verification
- ambiguous trim mapping
- conflicting data analysis
- image identity verification
- complex extraction validation
- RAG answer generation
- code implementation/debugging

Do not spend expensive model calls on simple deterministic tasks.

Use normal code for:
- hashing
- URL normalization
- MIME detection
- duplicate detection
- schema validation
- numeric parsing
- scheduling
- HTTP status handling

---

# 81. Agent must leave an audit trail

Every automated modification should be explainable.

For example:

```text
Changed:
MG S5 EV X+ price
699000 → 679000

Reason:
Official source changed.

Evidence:
source_id=1284
document_id=441
retrieved_at=2026-08-24
```

If the AI proposed it:

```text
proposed_by = gpt-5.6-luna
approved_by = automated_validation
```

If uncertain:

```text
review_status = pending
```

---

# 82. Admin "research now" button

Admin UI should support:

```text
[Research this model now]
```

Options:

```text
☑ official website
☑ brochure
☑ prices
☑ images
☑ news
☑ public community
```

Show live/progress results:

```text
Finding official page...
✓ Found

Finding brochure...
✓ Found 2026 Thai PDF

Verifying...
✓ Correct model

Finding images...
✓ 12 candidates
✓ 8 verified

Updating database...
✓ 14 facts changed
```

This will be extremely useful during initial catalog construction.

---

# 83. Manual source override

Admin must be able to explicitly set:

```text
Official model URL
Official brochure URL
Official price URL
Official gallery URL
```

The automated agent should use these as high-priority seeds.

This solves cases where the website is difficult for automated discovery.

---

# 84. Source hints

Create:

```text
source_hints
```

Example:

```text
manufacturer = MG
model = S5 EV
official_model_url = ...
official_brochure_url = ...
official_price_url = ...
official_gallery_url = ...
```

Once manually verified, scheduled agents can start from these known-good anchors.

This creates a feedback loop:

```text
human verified once
→ agent remembers source
→ future refresh becomes easier
```

---

# 85. Data import from existing knowledge

If manually providing initial source URLs or brochures, import them as:

```text
user_provided_source
```

Do not pretend the agent discovered them.

This distinction matters for auditability.

---

# 86. Image UI fallback

If no redistributable official image is available:

Do NOT show a random image.

Instead:

```text
[ดูภาพจากเว็บไซต์ผู้ผลิต]
```

linking to the official page.

The vehicle database should remain visually usable even without local image hosting.

---

# 87. Brochure UI fallback

If the brochure cannot legally/technically be locally hosted:

Show:

```text
โบรชัวร์จากผู้ผลิต
[เปิดเอกสารต้นฉบับ]
```

and retain:
- title
- source
- date
- verified status

---

# 88. Research quality metrics

Add dashboard metrics:

```text
Official source coverage
Brochure coverage
Image coverage
Price freshness
Specification freshness
Unverified facts
Conflicting facts
Failed crawls
```

Example:

```text
Official source coverage     96%
Verified brochure coverage   83%
Verified hero image coverage 91%
Prices < 24h old             78%
Conflicting facts             12
```

These metrics are more useful than simply saying "1,000 cars indexed".

---

# 89. Definition of "verified vehicle"

A vehicle variant should not be marked `verified` unless:

- official model source exists OR trusted secondary source exists
- trim identity is confirmed
- current/last-known price has a source when price is available
- at least core specs have provenance
- market is confirmed as Thailand
- no unresolved critical conflict exists

Use:

```text
verified
partially_verified
needs_review
unverified
```

---

# 90. New acceptance tests for v2

## Brochure discovery

Input:

```text
MG S5 EV X+
```

Expected:
- official Thai domain identified
- model page identified
- brochure candidate found if publicly available
- PDF opened
- model verified
- Thai-market relevance verified
- page count recorded
- hash recorded
- source linked

If not found:
- system records search attempt
- no fake brochure URL
- status = not_found

## Image discovery

Expected:
- official hero/gallery candidates found where available
- original/high-resolution URLs preferred
- source page stored
- duplicate images deduplicated
- image role assigned

## Changed brochure

Expected:
- old brochure retained
- new hash creates new version
- changed specs identified
- embeddings updated only for changed chunks

## Temporary website failure

Expected:
- previous verified data remains
- source marked unavailable
- no destructive overwrite

## Conflicting official sources

Expected:
- conflict recorded
- no silent overwrite
- admin review available

---

# 91. Recommended first production workflow

For each new model:

```text
1. Create manufacturer
2. Find official Thai domain
3. Find official model page
4. Manually/AI verify model identity
5. Register source hint
6. Discover brochure
7. Verify brochure
8. Discover official images
9. Extract trims
10. Extract official prices
11. Extract specifications
12. Validate
13. Generate embeddings
14. Publish model
15. Start scheduled refresh
```

Only after this works reliably for 5–10 models should the agent scale to hundreds.

---

# 92. Final v2 principle

The difficult part of this project is not:

> "Can GPT write the website?"

The difficult part is:

> "Can the system reliably find the correct official evidence, prove that it belongs to the correct Thai-market vehicle/trim/year, extract it, and notice when it changes?"

Therefore the production architecture must optimize for:

```text
DISCOVERY
   ↓
VERIFICATION
   ↓
EXTRACTION
   ↓
RECONCILIATION
   ↓
PROVENANCE
   ↓
INDEXING
   ↓
AI
```

not:

```text
AI → scrape → save → hope
```

This is the required architecture for version 1 production data ingestion.

---

# Part II — Data acquisition factory & daily update roadmap (A–I)

> Added 2026-09-24, branch `fix/p1-provenance-gate`, baseline commit `e1d2809`.
>
> This part is **normative** for the data acquisition/update factory. Earlier sections remain background design: §16 (update agent), §17 (update conflict), §28 (source crawler design), §29 (change detection), §75–77 (cron/refresh). Where they conflict with this part, **this part wins**. Do not create competing plan documents; update this part in-place.

---

# 93. A. OEM coverage & coverage registry

## Goal

Cover every vehicle brand/model **officially sold in Thailand**, tracked in a maintainable coverage registry. Full Thailand-market coverage may **never be claimed** unless the registry objectively proves it (every in-scope brand either captured-with-sidecar or blocked-with-evidence and ladder exhausted).

## Registry

Single source of truth: `audit/coverage/oem-registry.json` (machine) with a generated human view `docs/oem-coverage.md`. One row per brand × source endpoint:

```text
brand                  official brand/importer name (as published)
in_scope               bool — officially sold in Thailand?
source_urls[]          ordered candidate official URLs (primary first)
source_type            OFFICIAL_SITE | OFFICIAL_PDF | OFFICIAL_STRUCTURED_DATA |
                       OFFICIAL_PRESS | DEALER | SECONDARY
access_status          REACHABLE | BLOCKED_HTTP_403 | BLOCKED_HTTP_404 |
                       BLOCKED_DNS | BLOCKED_TLS | BLOCKED_TIMEOUT |
                       ERROR_PAGE | DEALER_REDIRECT | UNKNOWN
acquisition_method     playwright | http_get | None
adapter_status         NONE | DISCOVERED | PARSED | PARSED_TESTED
provenance_status      ACQUISITION_VERIFIED | LEGACY_UNVERIFIED | NONE
last_success_at        ISO timestamp of last capture that produced parseable data
last_success_sha256    artifact hash from that capture
blocker_evidence       {checked_at, http_status_or_error, url} — real probe result
next_retry_at          timestamp from backoff policy (§94)
fallback_ladder[]      alternates already tried + result (evidence, not guesses)
```

## Coverage claim rule

```text
coverage_% = brands with provenance_status=ACQUISITION_VERIFIED AND adapter_status=PARSED_TESTED
             ÷ in_scope brands
```

Attempt counts, captured counts and blocked counts are **operational telemetry**, never market coverage.

## Fallback ladder (per blocked brand, in order)

1. Primary model-list/price page (as published).
2. ≤2 sensible alternates per acquisition cycle (`/models`, `/model-list`, `/cars`, sitemap-listed model pages). **Then move on** — do not loop on one domain.
3. Official PDF price list / brochure (documented on an official page).
4. Official structured data (JSON-LD, sitemap XML, published API/JSON endpoints).
5. Official press/release page carrying prices.

If all fail: record `access_status` + `blocker_evidence`, set `next_retry_at` from §94, continue horizontally. A captured page that redirects to an error page or a dealer domain is stored but marked `ERROR_PAGE`/`DEALER_REDIRECT`; no adapter may extract business rows from it.

---

# 94. B. Daily acquisition / update system

## Pipeline

```text
DISCOVER → ACQUIRE → HASH/PROVENANCE → DIFF → QUARANTINE
   → EVIDENCE PACKET → ACCEPTANCE → PROMOTION → DB → AUDIT LOG
```

## Acquisition contract (hard rules)

- Every **new** capture goes through `AcquisitionWriter.write()` and produces artifact + `.prov.json` **from the same acquisition event**: `source_url`, `captured_at` (runtime clock at capture), `acquisition_method`, `sha256`, `session_id`, `provenance_state=ACQUISITION_VERIFIED`.
- Reads go through `AcquisitionReader` (fail-closed: hash mismatch or missing sidecar ⇒ `ProvenanceError`, no silent continue).
- Never retrofit timestamps/hashes after capture. Legacy fixtures stay `LEGACY_UNVERIFIED` until genuinely recaptured.
- `captured_at` (source acquisition), `artifact_mtime` (filesystem bookkeeping), `staging_timestamp` (extraction run) are three separate concepts; never substituted.

## Idempotency

- Artifacts are content-addressed by SHA-256.
- Re-capture with **same SHA** ⇒ record only `{run_id, source, status: UNCHANGED}`; **no new business rows**, no ChangeCandidate, no alert.
- Re-capture with **new SHA** ⇒ run parser; compare extracted output to last accepted output:
  - identical output ⇒ `CONTENT_CHANGED_OUTPUT_UNCHANGED` (store artifact, log only),
  - different output ⇒ create **ChangeCandidate** `{source, old_sha, new_sha, field_level_diff[]}` → QUARANTINE.
- Two consecutive runs over the same artifact must yield an identical observation set (no duplicates) — enforced by test (§98).

## Retry / backoff / source-failure handling

```text
BLOCKED_HTTP_403   → no UA rotation, no bypass; retry +7d, then monthly
BLOCKED_HTTP_404   → ladder (≤2 alternates/cycle); retry +14d (redesigns happen)
BLOCKED_DNS        → retry weekly ×4, then monthly
BLOCKED_TLS        → retry monthly; NEVER disable certificate verification
BLOCKED_TIMEOUT    → retry next run ×2 with backoff (30s, 120s), then cycle-blocked
5xx / transient    → same-run retry (30s, 120s), else RETRY_NEXT_RUN
ERROR_PAGE /
DEALER_REDIRECT    → store capture, extract nothing, fix URL target in registry
```

Per-host politeness: ≥5 s between requests, capped requests per host per day, jittered schedule.

## Alerting (signal, not noise)

Alert **only** on: price change for a tracked model; model/variant added or removed; new conflict record; hash/provenance verification failure; source state transition (reachable → blocked); promotion-gate failure.

Never alert on: unchanged capture, repeated known blocker, expected ladder outcome.

One daily digest (MD + JSON) per run: `audit/daily-runs/YYYYMMDD.{md,json}` — following the global rule that every data run ends with a full report.

---

# 95. C. Data quality & acceptance rules

Explicit prohibitions and the mechanism that prevents each:

```text
model/variant cross-contamination
    → identity level (MODEL|VARIANT) declared per adapter and per row;
      locator re-resolution must find the extracted name+price in ONE card;
      variant names are never created by splitting (no invented Standard/Base/Entry).

historical/stale price becomes current
    → currentness defaults to UNKNOWN; CURRENT requires dated in-stock/price-list
      evidence within the freshness window (§43); fixture rows are never "current".

MSRP starting range mislabeled as exact variant price
    → price_type is mandatory: MSRP_STARTING (เริ่มต้น/ราคาเริ่มต้น/starting at)
      vs EXACT_VARIANT (grade-specific). Never converted between types.

duplicate parser paths
    → one canonical adapter per (source, page-type), recorded in the registry;
      any second path must state why and must produce identical rows in a test.

shared media/article price-block contamination
    → MEDIA_DISCOVERY class rows never become official prices; article price blocks
      need a vehicle-scoped locator or they stay unextracted.

placeholder / duplicated specs
    → null/empty and repeated-sentinel scans in staging validation;
      placeholder values quarantined, not promoted.

secondary source promoted to official
    → trust tiers (official_verified > secondary_verified > reference > inferred)
      are non-increasing; only an official artifact can set official_verified.

provenance mistaken for semantic correctness
    → ACQUISITION_VERIFIED proves capture integrity only; semantic acceptance
      is a separate gate (§98). The two are reported separately, always.
```

## Mandatory fields on every observation

```text
identity.level + identity names | price.type + value + currentness
scope (Thailand official market) | source.class + trust tier
evidence.locator (canonical, re-resolvable) + evidence.excerpt (same record)
provenance: sha256 + captured_at + provenance_state + session_id
```

Rows missing any field are quarantined, not staged as accepted.

---

# 96. D. Multi-source assembly

- **Field-level provenance**: an assembled model/variant stores `{field → {value, source_id, artifact_sha256, locator, observed_at, trust_tier}}`. Never one blob of provenance per row.
- **Join keys**: `manufacturer_slug + model_slug + variant_slug + model_year`, resolved through an alias table with its own evidence. Joins never match on display strings alone; `candidate_id` until reconciliation produces a `canonical_id`.
- **Source classes** (roles): `IDENTITY_ENUMERATOR` (names/lineup), `MARKET_TRUTH` (official price/spec), `MARKET_REFERENCE` (reference datasets e.g. FIPE/Thai DLT), `MEDIA_DISCOVERY` (articles, discovery only). Roles never silently upgrade.
- **Conflict policy**: within the same trust tier, newest dated observation wins; across tiers, higher tier wins but the conflict is still recorded. Nothing is ever silently overwritten.
- **Contamination tests required**: field attributed to source A must carry evidence from A's artifact (hash match); a test must fail if source B's locator is attached to source A's value.

---

# 97. E. Evidence packets & change management

## EvidencePacket contents

```text
packet_id, created_at, run_id
observation(s) with identity/price/scope semantics
artifact: path + sha256 + sidecar provenance (captured_at, method, session, state)
canonical locator + independently re-resolved excerpt (model + price in one record)
source.class + trust tier + source_url (openable in a browser)
conflicts[] — each side with ITS OWN evidence (never merged into one value)
diff vs previous accepted packet (for change candidates)
status: QUARANTINED | ACCEPTED | REJECTED
acceptance decision + reason + gate results; append-only ledger entry
```

## Conflict representation

A conflict is an explicit record holding both observations with their separate artifacts/locators. Unresolved conflicts **remain quarantined indefinitely** — never averaged, never majority-voted into the dataset.

## AI role (later, after volume)

AI reads packets and proposes reconciliation (alias merges, conflict resolution, dedupe). It must **cite packet ids**, may only emit decisions + rationale, and **cannot introduce facts not present in packets**. Proposals pass the same acceptance gates as heuristic decisions before promotion. No AI reconciliation layer is built before real volume exists.

---

# 98. F. Testing & quality gates

## Required test categories

```text
1  sidecar/hash integrity        tamper artifact → extraction FAILS (ProvenanceError)
2  locator re-resolution         stored locator → re-resolve against committed
                                 artifact → resolved card contains model + price
3  current vs stale conflict     dated evidence vs UNKNOWN → correct currentness
4  model-range vs variant MSRP   เริ่มต้น → MSRP_STARTING, grade price → EXACT_VARIANT
5  duplicate/idempotent rerun    same artifact twice → identical observation set
6  cross-model contamination     adjacent price swap / deleted price / mismatch
                                 → extraction changes deterministically
7  provenance/trust preservation ACQUISITION_VERIFIED vs LEGACY_UNVERIFIED survive
                                 extraction → staging unchanged
8  multi-source assembly         per-field source matches its artifact hash
9  promotion gates               ungated row cannot reach accepted set
10 daily update regression       fixture-based daily-run replay, no live web in CI
```

Every adapter ships with tests from categories 1, 2, 4, 6 before its rows are trusted.

## Objective acceptance gates: acquisition → production DB

```text
G1  every row from new captures: sidecar present + hash verifies fail-closed
G2  every active adapter: locator re-resolution + mutation tests green
G3  identity/price-type/currentness consistent with source wording (rule table)
G4  idempotent rerun proven (no duplicate business rows)
G5  cross-source contamination suite green
G6  sample audit: random rows re-opened in a browser show the same number
G7  producer ≠ verifier: verifier code path independent of extractor
G8  gate report (MD+JSON) committed with counts before any promotion writes
```

A gate failure blocks promotion; it does not trigger an architecture rewrite.

---

# 99. G. Operating model

```text
one canonical acquisition framework   lib/thai_factory/acquisition/ (writer/reader/ladder)
per-OEM adapters (only where DOM differs)  scripts/collect_multi_oem.py → lib adapters
coverage registry (single source of truth) audit/coverage/oem-registry.json
scheduler / orchestrator              cron (Phase 4); manual runs before that
diff / change queue                   audit/change-queue/*.jsonl (ChangeCandidates)
evidence packet store                 lib/thai_factory/acceptance/ + storage/quarantine
acceptance / promotion worker         AcceptanceRunner + append-only AcceptanceLedger
audit / reporting                     audit/daily-runs/ + audit/data-staging/summary.json
```

**Defect policy (anti-perfectionism):** before changing code, identify the failing boundary and reproduce it with one end-to-end record. If the architecture already satisfies that boundary, stop patching. Non-blocking defects are logged as follow-ups (registry/ledger) and work continues horizontally. Only stop for: corrupted data, broken provenance, wrong identity semantics, or broken evidence integrity. **No endless verifier rewrites** — the verifier stays frozen (v9).

---

# 100. H. Current verified state (baseline @ `e1d2809`)

VERIFIED facts (independently checked against the remote tree):

- Branch/commit: `fix/p1-provenance-gate` @ `e1d2809`.
- Tests: **80/80** (17 provenance/boundary + 63 extraction fixtures), all offline from committed artifacts.
- Staging: **176/176** rows carry SHA-256, `provenance_state` and a canonical locator.
- Provenance: **2/8 sources `ACQUISITION_VERIFIED`** (Lexus, Honda Models — sidecar-backed), **6/8 `LEGACY_UNVERIFIED`** (Toyota, Mazda, Nissan, Honda City, Isuzu, BMW).
- Rows by source/identity: Toyota 99 VARIANT · Mazda 10 MODEL · Nissan 10 MODEL · Honda City 4 VARIANT · Isuzu 6 MODEL · BMW 35 MODEL · Lexus 6 MODEL · Honda Models 6 MODEL. All `currentness=UNKNOWN` except rows explicitly dated by their source.
- Acquisition attempts: 25 OEM endpoints across 2 sessions — 5 captured (with sidecars), 20 blocked. **These are operational telemetry, not market coverage** (see §93).
- Sidecars present in tree: `lexus_models_page.html.prov.json`, `honda_models_page.html.prov.json`, plus captured-but-unparsed `porsche_home_page`, `toyota_model_page`, `suzuki_models_page`, `mg_models_page` (all `ACQUISITION_VERIFIED`).

LEGACY / unproven (explicitly not claimed):

- Legacy manifest timestamps for Toyota/Honda/Isuzu/BMW are `LEGACY_UNVERIFIED` — retained as historical notes, never called "real acquisition".
- Mazda/Nissan `captured_at = UNKNOWN` (no acquisition record).
- Blocked/captured counts do not establish Thailand-market coverage.

Known non-blocking follow-ups (logged, not fixed now):

- Lexus adapter writes `acquisition_method: "playwright_fixture"` while its sidecar says `playwright` — propagate the sidecar value when the adapter is next touched.
- Lexus locator test checks presence only; stronger re-resolution test to be added under Phase 2 (pattern already proven on BMW).

---

# 101. I. Phased roadmap

## Phase 1 — Broad OEM acquisition coverage ← CURRENT

- **Objective**: breadth — coverage registry covering every in-scope Thai brand, each either sidecar-captured or blocked-with-evidence.
- **Deliverables**: `audit/coverage/oem-registry.json` + generated view; new `.prov.json` captures via `AcquisitionWriter`; adapter + tests per newly parsed OEM; acquisition run reports.
- **Entry**: provenance architecture accepted (`b33a0ef`); first sidecar exercised (`c847dbf`). ✅
- **Exit**: registry = 100% of in-scope brands; every reachable OEM `PARSED_TESTED`; every blocked brand has blocker evidence + ladder ≤2 alternates/cycle tried.
- **Blockers allowed**: 403/404/DNS/TLS/timeouts (documented), Fipe 429 (retry window ~22 h).
- **Do NOT work on**: verifier rewrites, production DB bulk load, AI reconciliation, test-framework expansion beyond per-adapter needs, provenance redesign.

## Phase 2 — Normalized provenance + adapter quality

- **Objective**: all active adapters propagate sidecar provenance verbatim (no invented labels) and pass re-resolution + mutation tests.
- **Deliverables**: `acquisition_method` propagation fix (Lexus cleanup), per-adapter re-resolution tests, mutation tests complete for all adapters.
- **Entry**: Phase 1 registry exists for the adapters in question.
- **Exit**: zero label mismatches; every adapter satisfies §98 categories 1/2/4/6.
- **Do NOT work on**: provenance architecture changes (reopen only on a concrete end-to-end defect), new OEM hunting (stays Phase 1).

## Phase 3 — Evidence packets / acceptance / promotion

- **Objective**: wire the existing EvidencePacket/AcceptanceRunner/Ledger framework to real captures: QUARANTINE → PACKET → ACCEPTANCE → PROMOTION.
- **Deliverables**: packets for verified rows, acceptance gate report (G1–G8), first promotion into the accepted set with ledger entries.
- **Entry**: Phase 2 exit for the sources being promoted.
- **Exit**: first real promotion run with a committed gate report; zero ungated rows.
- **Do NOT work on**: production canonical DB writes before gates pass; PR #3 stays open.

## Phase 4 — Daily diff + scheduled updates + alerting

- **Objective**: idempotent scheduled runs implementing §94 end-to-end.
- **Deliverables**: scheduler, diff/ChangeCandidate queue, daily digests, alert rules.
- **Entry**: Phase 3 promotion working for ≥ the verified sources.
- **Exit**: 7 consecutive green daily runs, alerts only on meaningful changes, no duplicate rows.
- **Do NOT work on**: new source classes, AI reconciliation.

## Phase 5 — Multi-source assembly + semantic enrichment at scale

- **Objective**: field-level multi-source assembly (§96) + AI-assisted reconciliation after volume.
- **Deliverables**: assembled records with per-field provenance, alias table, contamination tests, AI proposals citing packet ids.
- **Entry**: sustained volume from Phase 4.
- **Exit**: contamination suite green; unresolved conflicts provably still quarantined.
- **Do NOT work on**: enrichment from any old/contaminated DB.

## Phase 6 — Production hardening & observability

- **Objective**: production promotion with full audit trail, freshness SLOs, monitoring.
- **Deliverables**: production promotion worker, audit queries, freshness/coverage dashboards, incident runbooks.
- **Entry**: Phase 5 exit + all G1–G8 gates green on the promoted set.
- **Exit**: production DB receives only accepted packets; every field traceable to artifact + locator.
- **Do NOT work on**: expanding scope beyond Thailand official-market catalog.

## Standing constraints (all phases)

- PR #3 open/unmerged; branch `fix/p1-provenance-gate` until told otherwise.
- No production DB expansion with unverified data; no model/provider/config changes; embedding config never used for generation; only approved generation models.
- No skills/self-improvement/memory/reference edits from data work.
- Raw artifacts immutable; every price observation must have a source URL a buyer can open and see the same number.
- Report every data run as (a) exact remote SHA, (b) artifact count + bytes, (c) per-OEM rows by identity level, (d) hash coverage, (e) locator coverage, (f) tests + blockers — and nothing claims "verified/current" that evidence does not prove.
