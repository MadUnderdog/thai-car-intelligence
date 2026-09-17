# รถรู้จริง — Thai Car Intelligence

Source-backed automotive knowledge platform สำหรับรถยนต์ตลาดไทย

## สถานะปัจจุบัน

โปรเจกต์อยู่ระหว่างสร้าง vertical slice แรก:

- Next.js 16 + TypeScript strict + Tailwind
- PostgreSQL + pgvector schema และ migration
- Provenance/source model, research audit model และ price history
- SSRF-safe URL policy สำหรับ crawler
- Deterministic candidate discovery สำหรับ brochure/image กำลังต่อยอด
- หน้า landing ภาษาไทยและ search placeholder ที่ไม่แสดงข้อมูลปลอม

ยังไม่มีรถ seed จนกว่าจะผ่าน official-source verification

## Requirements

- Node.js 22+
- npm 10+
- PostgreSQL 16+ พร้อม extension `vector`

## Local development

```bash
npm install
cp .env.example .env
npm run prisma:validate
npm run prisma:generate
npm run typecheck
npm run lint
npm test
npm run dev
```

เปิด `http://localhost:3000`

## Database

โปรเจกต์นี้ไม่สร้าง PostgreSQL container ใหม่โดยอัตโนมัติ ให้กำหนด `DATABASE_URL` ไปยัง database ที่เตรียมไว้แล้ว

```bash
DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/thai_car_intelligence' npm run db:migrate
```

ตรวจ database และ extension โดยไม่แสดง secret:

```bash
DATABASE_URL='...' npx tsx scripts/check-db.ts
```

ห้ามใช้ `prisma migrate reset` กับ production database

## Embedding and incremental indexing

The local MVP uses the explicitly configured internal service `POST ${EMBEDDING_BASE_URL}/embed` with `{ "texts": ["..."] }`, returning `{ "embeddings": [[...]], "dimensions": 768 }`. No endpoint is assumed and no request is made unless `EMBEDDING_BASE_URL` is set. Configure `EMBEDDING_MODEL` as a metadata label and keep `EMBEDDING_DIMENSIONS=768`.

Index one extracted source document safely (unchanged chunks are deduplicated; only changed chunks are embedded):

```bash
EMBEDDING_BASE_URL=http://localhost:8080 npm run index:document -- --source-document-id UUID
npm run index:document -- --source-document-id UUID --dry-run
```

The migration `20260824130000_embedding_vector_768` is fail-closed and refuses to alter the pgvector column when `Embedding` contains rows. Do not use `prisma migrate reset`. To switch to an external 1536d provider, configure a separate provider and perform an explicitly reviewed vector-column migration/reindex; never mix dimensions in the 768d column.


Research pipeline แบ่งเป็น:

```text
Discovery → Verification → Extraction → Reconciliation → Validation → Indexing
```

Google Search/grounding, browser และ LLM ใช้ช่วยค้นหา candidate หรือแก้ความกำกวมได้ แต่ candidate จะเป็น official evidence ได้ต่อเมื่อเปิดและตรวจสอบหน้า/PDF จริงแล้วเท่านั้น ระบบต้องบันทึก source URL, source page, retrieved time, hash, market/model/year match และ confidence

ข้อจำกัดสำคัญ:

- ไม่ bypass login, CAPTCHA, paywall หรือ technical access control
- ไม่ scrape private groups/accounts
- ไม่ดาวน์โหลด/redistribute brochure หรือภาพเมื่อสิทธิ์ไม่ชัดเจน
- หากสิทธิ์ไม่ชัดเจน ให้เก็บ metadata และลิงก์ต้นฉบับแบบ reference-only
- Crawl failure ต้องไม่ทำให้ verified data เดิมถูกลบหรือกลายเป็น null

รายละเอียดอยู่ใน `docs/source-policy.md` และ `docs/research-pipeline.md`

## Project documents

- `Blueprint.md` — product requirements ฉบับเต็ม
- `docs/implementation-plan.md` — implementation plan
- `docs/data-model.md` — relational/provenance model
- `docs/source-policy.md` — source, legal และ SSRF policy
- `docs/research-pipeline.md` — discovery/verification workflow

## Quality gate

ห้ามประกาศ production-ready จนกว่าจะมี evidence จริงสำหรับหลาย manufacturer/model/trim, ราคาและ brochure ที่ verify แล้ว, page-level citation, hybrid search, RAG, comparison, admin review และ failure tests
