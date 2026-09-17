# Thai Car Intelligence & Community Platform Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** สร้างแพลตฟอร์มข้อมูลรถยนต์ตลาดไทยที่มีข้อมูลเชิงโครงสร้าง แหล่งอ้างอิงระดับฟิลด์ ระบบค้นหาแบบ hybrid, RAG Q&A ภาษาไทย, comparison, community และ ingestion pipeline ที่ตรวจสอบ brochure/image จากแหล่งทางการได้จริง

**Architecture:** ใช้ monorepo เดียวแบบ modular โดย Next.js ทำ public/admin UI และ API, PostgreSQL + pgvector เป็นฐานข้อมูลหลัก, worker แยก process สำหรับ discovery/verification/extraction/reconciliation/indexing, และ object storage เก็บไฟล์เฉพาะ asset ที่มีสิทธิ์ใช้งาน หากสิทธิ์ไม่ชัดเจนให้เก็บ metadata/source URL และแสดงลิงก์ต้นฉบับแทนการ redistribute

**Tech Stack:** Next.js + TypeScript strict, Tailwind CSS, PostgreSQL + pgvector, Prisma migrations/client, Zod, Vitest, Playwright, Docker Compose, provider abstraction สำหรับ AI/embedding, structured logging และ cron/queue worker

---

## 1. หลักการที่ต้องยึด

1. Relational database เป็น source of truth; vector index เป็นเพียง retrieval support
2. Important facts ทุกฟิลด์ต้องมี provenance, confidence, freshness และ source excerpt/page เมื่อมี
3. ห้ามใช้ community/media/AI inference แทน official specification
4. ห้ามลบหรือ null ข้อมูลเดิมเพราะ crawl ล้มเหลวชั่วคราว
5. Brochure/image ต้องผ่าน discovery → verification → extraction ก่อน publish
6. Conflict ต้องเก็บหลายค่าและเข้า review queue ห้าม overwrite เงียบ ๆ
7. API key อยู่ server-side เท่านั้น และห้าม log secret
8. เริ่มจาก 5–10 models ที่ตรวจสอบได้จริงก่อนขยาย catalog
9. ใช้ deterministic code กับ parsing/hash/validation; ใช้ LLM เฉพาะงานที่ต้อง reasoning
10. ทุก release ต้องมีหลักฐานจาก test และ data-quality gate ไม่ใช้ fake seed data

## 2. Assumptions และขอบเขตเริ่มต้น

- เป็นโปรเจกต์ใหม่ ไม่แก้หรือทับ project/service เดิมโดยอัตโนมัติ
- Target แรกคือ Thai-market vehicle catalog และ responsive web; native mobile app ไม่อยู่ใน v1
- Authentication ใช้ email/OAuth ที่เหมาะกับ deployment แต่ต้องมี role `user`, `moderator`, `admin`
- AI provider และ embedding provider เปลี่ยนได้ผ่าน interface/env; ห้ามผูก schema กับ vendor เดียว
- Initial release แบ่งเป็น MVP ที่ใช้งาน end-to-end ได้ และ production hardening หลัง data pipeline ผ่าน acceptance tests
- News และ public community discovery เป็น secondary evidence แยกจาก official vehicle facts
- Default language คือภาษาไทย โดยเก็บชื่อ official Thai/English เดิมไว้ครบ

## 3. Repository ที่จะสร้าง

```text
thai-car-intelligence/
├─ app/
│  ├─ (public)/cars/
│  ├─ (public)/compare/
│  ├─ (public)/search/
│  ├─ (public)/discussions/
│  ├─ (public)/news/
│  ├─ admin/
│  └─ api/
├─ components/
├─ lib/
│  ├─ ai/
│  ├─ auth/
│  ├─ db/
│  ├─ embeddings/
│  ├─ search/
│  ├─ sources/
│  ├─ validation/
│  └─ security/
├─ workers/
│  ├─ discovery/
│  ├─ verification/
│  ├─ extraction/
│  ├─ reconciliation/
│  └─ indexing/
├─ prisma/
│  ├─ schema.prisma
│  ├─ migrations/
│  └─ seed/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ data/
│  └─ e2e/
├─ scripts/
├─ docs/
├─ public/
├─ storage/.gitkeep
├─ .env.example
├─ docker-compose.yml
├─ package.json
├─ README.md
└─ Blueprint.md
```

---

# Phase 0 — Project contract and environment

### Task 0.1: สร้าง repository และ project contract

**Files:** `README.md`, `Blueprint.md`, `docs/architecture.md`, `docs/decisions/0001-source-backed-architecture.md`

- คัดลอก blueprint เป็น `Blueprint.md` โดยไม่ตัดข้อกำหนดด้าน provenance/legal/data quality
- เขียน architecture decision ว่า PostgreSQL เป็น source of truth และ worker pipeline เป็น staged workflow
- ระบุสิ่งที่อยู่นอก v1: native app, blind universal crawler, automatic user ban, uncontrolled full-catalog scrape

**Verify:** reviewer ตรวจได้ว่า architecture decision ครอบคลุม source-first, audit trail, failure protection และ provider abstraction

### Task 0.2: ตรวจ runtime และ service ที่มีอยู่แบบ read-only

**Commands:**

```bash
uname -a
docker --version
docker compose version
node --version
pnpm --version || npm --version
psql --version
docker ps
```

**Verify:** บันทึกผลใน `docs/environment-inventory.md`; ห้าม reinstall/stop/delete service ใด ๆ จนกว่าจะตรวจ port, volume และ owner ครบ

### Task 0.3: สร้าง Next.js TypeScript strict skeleton

**Files:** `package.json`, `tsconfig.json`, `next.config.ts`, `app/layout.tsx`, `app/page.tsx`, `app/globals.css`

- เปิด strict mode
- เพิ่ม lint/typecheck/test scripts
- กำหนด Thai font, metadata และ mobile-first viewport

**Verify:** `pnpm lint`, `pnpm typecheck`, `pnpm build` ผ่าน

### Task 0.4: สร้าง environment contract และ secret policy

**Files:** `.env.example`, `.env.local.example`, `lib/config/env.ts`, `.gitignore`, `docs/source-policy.md`

- กำหนด `DATABASE_URL`, `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, embedding config, storage config, app URL, crawler user agent
- validate env ด้วย Zod ตอน server start
- redact key/token/cookie ใน logger และห้าม expose ผ่าน client bundle

**Verify:** test missing required server env fails clearly; `git check-ignore .env` ยืนยันว่าไม่ track secret

---

# Phase 1 — Database foundation

### Task 1.1: เปิดใช้ pgvector และ migration baseline

**Files:** `prisma/schema.prisma`, `prisma/migrations/*`, `scripts/check-db.ts`

- ตรวจ extension `vector` ก่อน migration
- migration ต้องสร้าง/ตรวจ `CREATE EXTENSION IF NOT EXISTS vector` เฉพาะ database ที่ได้รับอนุญาต
- ไม่ทำลายตาราง/ข้อมูลเดิม

**Verify:** query `SELECT extname FROM pg_extension` ต้องพบ `vector`; migration status clean

### Task 1.2: สร้าง catalog และ provenance schema

**Tables:** `manufacturers`, `models`, `variants`, `sources`, `source_documents`, `prices`, `variant_specs`, `features`, `variant_features`, `aliases`, `media`

- เก็บ official names และ slug แยกกัน
- ราคาใช้ history: type, amount, validity, source, confidence, `is_current`
- important facts ต้องเชื่อม source ผ่าน fact/provenance relation หรือ source_id ที่ชัดเจน
- media มี source page, rights status, hash, perceptual hash, role

**Verify:** migration + Prisma generate; integration test insert manufacturer → model → variant → price/source และ query ย้อนกลับ provenance ได้

### Task 1.3: สร้าง research/change/audit schema

**Tables:** `research_runs`, `research_candidates`, `brochure_verifications`, `data_change_log`, `review_items`, `source_hints`, `crawl_jobs`, `crawl_events`, `embeddings`

- research run บันทึก model, queries, domains/pages checked, found documents/images, status/error
- change log เก็บ old/new value, evidence, confidence, proposed/applied/review status
- embedding metadata ต้องมี entity, chunk type, source, page และ model/dimension

**Verify:** fixture run สามารถบันทึก `partial_success`, conflict และ pending review โดยไม่สูญเสีย previous verified value

### Task 1.4: สร้าง normalized spec tables และ validation constraints

**Files:** `prisma/schema.prisma`, `lib/validation/specs.ts`, `lib/validation/prices.ts`, `tests/unit/validation/*`

- dimensions, performance, battery, charging, warranty, safety แยกจาก JSONB extras
- ใช้ database constraints เท่าที่เหมาะสม และ Zod/domain validation สำหรับ plausibility
- ตรวจ price positive/THB, wheelbase < length, integer seats, non-overlapping current price intervals

**Verify:** tests ครอบคลุม invalid values, duplicate trim, old price incorrectly current และ suspicious OCR value; suspicious data ต้อง flag ไม่ใช่ auto-fix

---

# Phase 2 — Source policy และ staged research pipeline

### Task 2.1: สร้าง source registry และ domain safety policy

**Files:** `lib/sources/types.ts`, `lib/sources/registry.ts`, `lib/security/url-policy.ts`, `prisma/seed/source-registry.ts`

- source types: official manufacturer/brochure/price/press, dealer, media, news, social, community
- domain allowlist สำหรับ crawler และ SSRF block: localhost, loopback, RFC1918, link-local, metadata endpoints
- enforce timeout, response-size limit, robots/terms policy marker และ user agent

**Verify:** unit tests ปฏิเสธ private/internal URLs, unsupported schemes, oversized responses และ unregistered crawl domain

### Task 2.2: สร้าง browser/search discovery interface

**Files:** `lib/sources/discovery/search-provider.ts`, `lib/sources/discovery/browser-provider.ts`, `workers/discovery/types.ts`

- interface รองรับ search engine discovery, rendered browser DOM, links, src/srcset/og:image/JSON-LD/gallery payload
- output เป็น candidate ที่มี URL, source page, anchor text, type, discovery method, score inputs
- ไม่ให้ LLM สร้าง URL เป็นหลักฐานโดยไม่มี fetch/open result

**Verify:** fixture HTML และ rendered-page fixture สกัด PDF/image candidates ได้ครบจากหลาย metadata locations

### Task 2.3: ทำ brochure discovery แบบ multi-pass

**Files:** `workers/discovery/brochure-discovery.ts`, `lib/sources/scoring/brochure-score.ts`, `tests/unit/discovery/brochure-discovery.test.ts`

Pipeline:

```text
official domain → model page → internal links → PDF candidates → score → fetch/open → register
```

- search official domain ก่อน
- ใช้ model/brochure/specification/catalogue/price และ `site:`/`filetype:pdf` fallback
- score official domain, direct page link, model/Thailand/Thai/year/spec terms
- หากไม่พบ ให้บันทึก queries/domains/pages/reason และ `not_found` ห้าม fabricate URL

**Verify:** fixture MG S5 มี candidate ที่ score สูงกว่า random PDF; negative fixture ถูก mark `needs_review` หรือ `not_found`

### Task 2.4: ทำ brochure verification และ versioning

**Files:** `workers/verification/brochure-verifier.ts`, `workers/extraction/pdf.ts`, `lib/documents/hash.ts`

- ตรวจ metadata, cover/first page, model, market, year, trims, Thai text, source page linkage
- คำนวณ SHA-256; hash ใหม่สร้าง document version ใหม่และไม่ลบของเก่า
- เก็บ page number ทุก extracted chunk
- OCR เป็น fallback และบันทึก extraction/OCR quality

**Verify:** integration fixture มี old/new brochure; ระบบเก็บทั้งสอง version, detect changed facts และ assign verification score

### Task 2.5: ทำ official image discovery และ verification

**Files:** `workers/discovery/image-discovery.ts`, `workers/verification/image-verifier.ts`, `lib/media/dedup.ts`

- ดึง `<img>`, `srcset`, lazy attrs, og:image, Twitter card, JSON-LD, CSS/API gallery เมื่อทำได้
- จัดอันดับ official hero/gallery/media/brochure/dealer
- ตรวจ identity จาก source URL, context, alt, filename และ visual review hook
- role ชัดเจน เช่น `hero`, `exterior_front`, `interior_front`, `dashboard`
- exact hash + perceptual hash dedup; rights status แยก `reference_only`/`do_not_redistribute`

**Verify:** image fixture เลือก high-resolution source ไม่ใช่ thumbnail, deduplicate resized copy และเก็บ source page/role/rights ครบ

### Task 2.6: แยก extraction, reconciliation และ safe apply

**Files:** `workers/extraction/facts.ts`, `workers/reconciliation/compare.ts`, `workers/reconciliation/apply-safe.ts`, `tests/integration/reconciliation.test.ts`

- extraction คืนค่า fact + evidence + confidence ไม่ใช่ค่าเปล่า
- conflict เก็บ official/dealer/media/community แยกกัน
- safe apply อนุญาตเฉพาะ validated, sufficiently confident, non-conflicting changes
- crawl failure/temporary missing image คงข้อมูลเดิมและเปลี่ยน source status เป็น unavailable/missing_on_latest_scan

**Verify:** tests ราคา official 699,000 vs dealer 679,000 แสดงทั้งคู่; timeout ไม่ทำให้ current price กลายเป็น null; image หายครั้งเดียวไม่ retire

---

# Phase 3 — Catalog ingestion และ seed ที่ตรวจสอบได้

### Task 3.1: สร้าง importer สำหรับ verified source bundle

**Files:** `scripts/import-source-bundle.ts`, `prisma/seed/fixtures/`, `docs/data-import-format.md`

- input ต้องมี source URL, source type, retrieved date, market, evidence/page และ rights metadata
- แยก `user_provided_source` จาก agent-discovered source
- ห้าม import rows ที่ไม่มี provenance ของ important facts

**Verify:** dry-run report จำนวน manufacturers/models/variants/prices/documents และ reject incomplete fixture

### Task 3.2: onboard 5–10 รุ่นจากหลาย manufacturer

**Files:** `prisma/seed/initial-catalog.ts`, `docs/initial-catalog-report.md`

ลำดับต่อรุ่น:

```text
manufacturer → official Thai domain → model page → source hint → brochure → images → trims → prices → specs → validate
```

- เริ่มจากกลุ่มที่มี official Thai evidence หาได้จริง ไม่ hardcode permanent brand list
- ใช้ null + “ไม่มีข้อมูล” เมื่อหาไม่ได้
- ไม่สร้างข้อมูลสมจริงปลอมเพื่อเติม UI

**Verify:** report แสดง source URL และ verification state ของทุก variant; อย่างน้อยหลาย manufacturer/model/trim และมี brochure จริงหลายฉบับ

### Task 3.3: สร้าง freshness และ coverage metrics

**Files:** `lib/quality/metrics.ts`, `app/admin/data-quality/page.tsx`, `docs/data-quality-gate.md`

Metrics: official source coverage, brochure coverage, verified hero coverage, price freshness, unverified facts, conflicts, failed crawls

**Verify:** metrics คำนวณจาก database จริง ไม่ใช่ hardcoded; drill-down ไปยัง source/review item ได้

---

# Phase 4 — Search และ retrieval

### Task 4.1: Implement exact search, aliases และ PostgreSQL FTS

**Files:** `lib/search/normalize-thai.ts`, `lib/search/aliases.ts`, `lib/search/fts.ts`, `app/api/search/route.ts`

- รองรับ Thai/English, aliases, abbreviations, misspellings ที่บันทึกได้
- แยก exact variant resolution จาก fuzzy/semantic result
- parse budget, EV/fuel และ canonical features เป็น structured filters

**Verify:** queries `mg s5`, `เอ็มจี s5`, `s5 x+`, `รถไม่เกินล้าน` resolve expected entity/filter

### Task 4.2: สร้าง embedding/indexing pipeline แบบ incremental

**Files:** `lib/embeddings/provider.ts`, `workers/indexing/chunker.ts`, `workers/indexing/embed-changed.ts`

- chunk 300–800 tokens overlap 50–120 โดย preserve source/page metadata
- hash content ก่อน embed; re-embed เฉพาะ changed chunks
- deterministic structured facts ไม่ต้องส่งทั้ง catalog เข้า LLM

**Verify:** unchanged source ไม่เพิ่ม embedding; changed brochure page เพิ่มเฉพาะ chunk ที่เปลี่ยน; dimension mismatch ถูก reject

### Task 4.3: สร้าง hybrid ranking และ structured-first retrieval

**Files:** `lib/search/hybrid.ts`, `lib/search/ranking.ts`, `tests/unit/search/hybrid.test.ts`

- combine exact/FTS/vector/structured filters/source quality/freshness/entity match
- exact price/spec query ให้ relational data มาก่อน vector evidence
- expose evidence IDs ให้ downstream RAG

**Verify:** budget + feature query คืน variant-level result พร้อม supporting source; vector unavailable แล้วยัง exact/FTS/structured search ใช้ได้

---

# Phase 5 — AI Q&A และ source citations

### Task 5.1: สร้าง AI provider abstraction

**Files:** `lib/ai/types.ts`, `lib/ai/providers/*`, `lib/ai/provider-factory.ts`

```ts
interface AIProvider {
  chat(input: ChatInput): Promise<ChatOutput>
  embed(input: string[]): Promise<EmbeddingOutput>
}
```

- provider/model จาก env/settings
- timeout, retry, fallback, token/latency metrics
- strip/handle provider reasoning fields โดยไม่ expose secret

**Verify:** mock provider contract test ผ่าน; provider failure คืน controlled error/fallback และไม่ log key

### Task 5.2: สร้าง RAG context builder และ policy prompt

**Files:** `lib/ai/retrieval/context-builder.ts`, `lib/ai/prompts/rag-th.ts`, `lib/ai/citations.ts`

บังคับ policy:

- ห้าม invent spec/price/citation
- conflict ต้องอธิบาย
- official Thai source มาก่อน
- แยก Fact / source-backed comparison / community opinion / AI analysis
- ไม่พบข้อมูลต้องพูดว่า “ไม่พบข้อมูล”
- ห้ามย้าย option จาก trim อื่นมาเป็น trim เป้าหมาย

**Verify:** adversarial fixture ตรวจว่า answer ไม่เปลี่ยน community claim เป็น fact และ citation ทุก factual claim ชี้ source/page ที่มีจริง

### Task 5.3: สร้าง `POST /api/ai/ask` และ “Why this answer?”

**Files:** `app/api/ai/ask/route.ts`, `components/ai/Answer.tsx`, `components/sources/EvidenceList.tsx`

- intent/entity extraction → structured retrieval → hybrid evidence → LLM → Thai answer + citations
- แสดง source title, publisher, retrieved/source date, brochure page เมื่อมี
- ไม่ส่ง API key หรือ internal prompt ให้ browser

**Verify:** acceptance queries MG S5 price, dimension comparison, EV budget/ventilated seat, community complaints, ADAS brochure answer ให้ผลตาม blueprint

---

# Phase 6 — Public UX

### Task 6.1: สร้าง vehicle family/variant page

**Files:** `app/(public)/cars/[manufacturer]/[model]/page.tsx`, `app/(public)/cars/[manufacturer]/[model]/[variant]/page.tsx`, `components/cars/*`

Sections: hero/source fallback, current official price, promotion label, trim selector, specs, equipment, dimensions, battery/charging, warranty, brochure link, source links, media/community/news, ask AI

**Verify:** SSR metadata/canonical/OG ถูกต้อง; unavailable image/brochure แสดง official source link ไม่ใช่ random asset

### Task 6.2: สร้าง comparison 2–4 variants

**Files:** `app/(public)/compare/page.tsx`, `components/compare/*`, `lib/compare/differences.ts`

- mobile horizontal scroll + sticky row labels
- show differences only
- label official/estimated/dealer/community/AI analysis แยกชัดเจน

**Verify:** เปรียบเทียบ 2–4 variants แล้วค่าที่ missing ไม่ถูกเติมด้วย inference; accessibility keyboard/touch ผ่าน

### Task 6.3: สร้าง search UX และ responsive shell

**Files:** `app/(public)/search/page.tsx`, `components/layout/*`, `components/search/*`

- mobile-first large touch targets, desktop filters/sidebar, optional bottom navigation
- loading/empty/error states และ source freshness visible

**Verify:** Playwright viewport mobile/tablet/desktop ตรวจ search → result → car page flow และ WCAG basic checks

---

# Phase 7 — Community, moderation และ user corrections

### Task 7.1: สร้าง auth, users, threads/posts schema และ API

**Files:** `lib/auth/*`, `app/api/discussions/*`, `components/community/*`

- threads link model/variant/news/general category
- rate limiting, validation, soft delete, edit history, mentions/reactions
- report incorrect data แยกจาก post report และส่ง review queue

**Verify:** unauthenticated write ถูกปฏิเสธ; authorized post/read/edit/report flow ผ่าน integration test

### Task 7.2: สร้าง moderation queue

**Files:** `lib/moderation/*`, `app/admin/moderation/page.tsx`, `app/api/admin/moderation/*`

- blocked words/spam/duplicate detection เป็น assistive signal
- AI ห้าม auto-ban จาก uncertain output เพียงอย่างเดียว
- moderator action มี audit log

**Verify:** report → queue → moderator resolve พร้อม history; rate limit และ soft delete ทำงาน

### Task 7.3: จัดประเภท community evidence โดยไม่เลื่อนสถานะเป็น fact

**Files:** `workers/extraction/community-classifier.ts`, `lib/search/community-index.ts`

- classify model/variant/topic/intent
- index เป็น `community_post` และแสดง “ผู้ใช้บางรายรายงาน”

**Verify:** “S5 X+ นั่งหลังสบายไหม” map ถูก entity/topic แต่ไม่สร้าง safety/spec fact จากข้อความ

---

# Phase 8 — Admin และ operational workflow

### Task 8.1: สร้าง admin catalog/source/document/change pages

**Files:** `app/admin/catalog/*`, `app/admin/sources/*`, `app/admin/documents/*`, `app/admin/reviews/*`

- CRUD อย่างปลอดภัยสำหรับ entities/source hints
- conflict/pending change review พร้อม old/new/evidence/confidence
- manual overrides: model/brochure/price/gallery URL

**Verify:** admin approve/reject change แล้วอ่านกลับได้; public page แสดงเฉพาะ applied state

### Task 8.2: เพิ่ม “Research this model now” job

**Files:** `app/api/admin/research/route.ts`, `workers/orchestrator/research-model.ts`, `components/admin/ResearchProgress.tsx`

Stages: official website, brochure, prices, images, news/community ตาม checkbox; progress event ต้องแสดง discovery/verification/extraction/reconciliation/indexing

**Verify:** run จริงหนึ่ง model ได้ research_run ID, partial success รองรับ source timeout, progress และ final audit trail ครบ

### Task 8.3: สร้าง observability

**Files:** `lib/observability/logger.ts`, `lib/observability/metrics.ts`, `app/admin/operations/page.tsx`

Log job ID/source ID/duration/status/extraction result/changed entities/embedding count/AI latency/errors/token usage; redact secrets/private data

**Verify:** log snapshot ไม่มี API key/auth token; dashboard แสดง failed/partial/success job และ latency

---

# Phase 9 — Scheduled refresh และ deployment

### Task 9.1: สร้าง due-entity scheduler และ per-domain rate limits

**Files:** `workers/scheduler/*`, `workers/crawl/domain-limiter.ts`, `prisma/seed/schedules.ts`

Schedules: prices/spec daily, brochures daily/weekly, news/community every few hours, deep verification weekly; priority ตาม freshness/event

**Verify:** scheduler เลือกเฉพาะ due entities, ไม่ยิง domain เกิน rate limit และ one-source failure ไม่ fail ทั้ง job

### Task 9.2: สร้าง worker runtime และ retry semantics

**Files:** `workers/runner.ts`, `docker/worker.Dockerfile`, `docker-compose.yml`

- web/worker แยก service แต่ใช้ database เดียว
- retry เฉพาะ transient error, dead-letter/review สำหรับ repeated failure
- graceful shutdown และ idempotent job execution

**Verify:** rerun job เดิมไม่ duplicate source/document/embedding; timeout → partial_success และ previous data remains

### Task 9.3: สร้าง production deployment และ backup plan

**Files:** `Dockerfile`, `docker-compose.yml`, `docs/deployment.md`, `scripts/healthcheck.ts`, `scripts/backup-check.ts`

- inspect existing ports/volumes/reverse proxy ก่อน deploy
- ไม่ stop/replace existing PostgreSQL; backup bind mounts ก่อน Docker state-changing operations
- health checks web/worker/db/vector; migration rollback procedure

**Verify:** deploy staging ใหม่ได้โดยไม่ชน service เดิม, smoke test public/admin/API และตรวจ pgvector extension จาก live database

---

# Phase 10 — Test, quality gate และ release

### Task 10.1: Unit/integration test suite

**Targets:** parsers, URL policy, brochure scoring/verification, image extraction/dedup, price history, source ranking, chunk metadata, provider abstraction, RAG citations, validation

**Verify:** `pnpm test --run` ผ่านและ coverage report แยก domain สำคัญ; ไม่ใช้ network จริงใน unit tests

### Task 10.2: Data fixtures และ failure tests

**Fixtures:** conflicting prices, old/new brochures, wrong market PDF, OCR errors, duplicate trims, dealer promotion, discontinued model, temporary 404, missing image, vector unavailable

**Verify:** safe failure behavior ครบ: no destructive null, no silent overwrite, no fake citation, old version retained

### Task 10.3: E2E และ accessibility

**Files:** `tests/e2e/*.spec.ts`, `playwright.config.ts`

Flows: mobile search, vehicle page, comparison, AI ask, source citation, community post/report, admin approval/research-now

**Verify:** Playwright ผ่าน Chromium mobile/desktop; run axe/basic keyboard checks; build production ผ่าน

### Task 10.4: Final data-quality gate

ก่อน release ต้องมีหลักฐานจริง:

- หลาย manufacturers/models/variants
- current/last-verified prices พร้อม source
- brochure หลายฉบับที่ verified และ page-level references
- official images หรือ explicit source-link fallback
- working hybrid search และ vector-disabled fallback
- working AI Q&A พร้อม citations
- working comparison/mobile layout/admin review
- research audit trail และ scheduled jobs

สร้าง `docs/release-report.md` ระบุจำนวนจริง: manufacturers, models, variants, verified prices, brochures, chunks, sources, tests, remaining issues, scheduled jobs และ legal/access limitations ห้ามกรอกตัวเลขจนกว่าจะ query/verify จากระบบจริง

---

## 4. Suggested execution order

1. Phase 0–1: skeleton, environment, database, migration
2. Phase 2: discovery/verification pipeline ก่อน UI สวยงาม
3. Phase 3: verified seed 5–10 models
4. Phase 4–5: search/RAG/citations
5. Phase 6: public UX
6. Phase 7–8: community/admin
7. Phase 9: scheduler/deployment
8. Phase 10: full verification/release

ห้ามข้าม Phase 2–3 แล้วใช้ mock/fake catalog เป็นหลัก เพราะจะทำให้ผ่านเฉพาะ visual demo แต่ไม่ผ่าน product intent

## 5. Definition of done

- `pnpm lint`, `pnpm typecheck`, `pnpm test --run`, `pnpm build` ผ่าน
- database migration clean และ pgvector ตรวจพบจาก live DB
- public UI ใช้งานบน mobile/desktop
- exact/FTS/vector/structured hybrid search ทำงาน และ vector outage ไม่ทำให้ basic search พัง
- AI answer ทุก factual claim มี evidence ที่อ่านย้อนกลับได้ หรือระบุว่าไม่พบข้อมูล
- official/dealer/community/AI status แยกชัดเจน
- brochure/image discovery มี research run และ verification record
- crawl failure ไม่ทำลายข้อมูล verified เดิม
- admin review และ manual source override ทำงาน
- deployment/smoke test ผ่านโดยไม่กระทบ existing services
- release report ใช้ตัวเลขจาก database/test output จริงเท่านั้น

## 6. Risks, trade-offs และวิธีรับมือ

| ประเด็น | ความเสี่ยง | วิธีรับมือ |
|---|---|---|
| Official sites เป็น JS-heavy | HTTP parser หา asset ไม่เจอ | browser-rendered DOM + search fallback + manual source hints |
| PDF rights ไม่ชัด | redistribute ไม่ได้ | metadata/reference-only และลิงก์ต้นฉบับ |
| ราคาขัดแย้ง/เปลี่ยนเร็ว | ผู้ใช้เข้าใจผิด | price history + source type + freshness + conflict review |
| OCR ผิด | spec ผิด | page evidence + plausibility checks + review threshold |
| LLM hallucination | ความน่าเชื่อถือลด | structured-first retrieval + citation validator + “ไม่พบข้อมูล” |
| Vector provider ล่ม | Q&A/search ใช้ไม่ได้ | FTS/exact/structured fallback และ queue reindex |
| Crawl ถูกบล็อก | job ล้ม | rate limit, browser/public fallback, partial success, ไม่ bypass access control |
| Catalog ใหญ่เร็วเกินไป | ค่าใช้จ่าย/คุณภาพตก | staged onboarding, hash-based change detection, model routing |
| Existing server conflict | downtime/data loss | read-only inventory, backup bind mounts, isolated ports/staging |

## 7. Open decisions ก่อนเริ่ม implementation จริง

1. ชื่อ repository และ deployment hostname
2. Auth provider และวิธีส่ง email/OAuth
3. Queue backend: PostgreSQL-backed queue ใน MVP หรือ Redis/managed queue
4. Object storage และ policy สำหรับ reference-only assets
5. AI/embedding provider ที่จะใช้ใน environment จริง
6. จำนวน initial models ที่พร้อมจัดหา official source ให้ครบ
7. ต้องการเปิด news/community discovery ใน MVP หรือหลัง core catalog
8. ผู้อนุมัติ manual review และ retention policy ของ research artifacts

**Recommendation:** เริ่มด้วย MVP ที่มี catalog + source/provenance + brochure/image research + hybrid search + RAG citation + comparison ก่อน community/news เต็มรูปแบบ เพราะเป็นแกนความแตกต่างและเป็น data-quality risk สูงสุดของผลิตภัณฑ์นี้
