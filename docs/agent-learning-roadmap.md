# Agent Learning Roadmap

> Study patterns จาก open-source projects เพื่อพัฒนา Thai Car Intelligence
> ไม่ใช่ copy code แต่เป็น internal engineering knowledge

---

## 1. Web Research & Browser Automation

### References: browser-use, Playwright, Crawlee

**ปัญหาที่แก้:** Official รถ websites ใช้ JavaScript rendering, lazy-load galleries, บางทีมี anti-bot protection

**Pattern ที่เรียนรู้:**

| Pattern | ปัญหา | Thai Car Intel | Status |
|---------|--------|----------------|--------|
| Browser-first DOM inspection | HTTP GET ไม่พอสำหรับ SPA | vehicle pages ที่ render ด้วย JS | ใช้แล้ว (safe-fetch + web_extract fallback) |
| Multi-pass discovery | ไม่เจอ PDF ในหน้าแรก | brochure discovery pipeline | ใช้แล้ว |
| Per-domain rate limiting | โดน block | crawler respect robots.txt | ใช้แล้ว |
| Retry with exponential backoff | timeout ชั่วคราว | safe-fetch retry | ควรเพิ่ม |
| Redirect chain validation | SSRF via redirect | safe-fetch redirect protection | ใช้แล้ว |
| Candidate scoring | ผลค้นหาเยอะเกินไป | brochure score breakdown | ใช้แล้ว |
| Session persistence | anti-bot detection | ไม่จำเป็นสำหรับ official sources | ข้าม |

**สิ่งที่ควรทำต่อ:**
- เพิ่ม retry policy ใน safe-fetch (backoff + jitter)
- เพิ่ม cache layer สำหรับ pages ที่ fetch บ่อย
- บันทึก HTTP headers สำหรับ debug

**ความเสี่ยง:** low - ไม่กระทบ existing architecture

---

## 2. Document & PDF Intelligence

### References: RAGFlow, PyMuPDF, Tesseract

**ปัญหาที่แก้:** Brochure รถเป็น scanned PDF, มีตาราง, ภาษาไทย/อังกฤษผสม

**Pattern ที่เรียนรู้:**

| Pattern | ปัญหา | Thai Car Intel | Status |
|---------|--------|----------------|--------|
| Text layer detection | ไม่รู้ว่า PDF มี text หรือ scan | document verification | ใช้แล้ว |
| OCR fallback (Tesseract eng+tha) | scanned brochure | PDF verification pipeline | ใช้แล้ว |
| Page-level extraction | ต้องอ้างอิงหน้า | pdftotext with page numbers | ใช้แล้ว |
| PDF metadata inspection | ไม่รู้ model year/market | pdfinfo | ใช้แล้ว |
| Hash-based dedup | brochure ซ้ำกัน | SHA-256 content hash | ใช้แล้ว |
| Table extraction | spec tables ใน PDF | ยังไม่มี - ควรเพิ่ม | TODO |
| Confidence scoring | ไม่แน่ใจว่า extract ถูก | verificationScore | ใช้แล้ว |
| OCR quality assessment | OCR ผลลัพธ์แย่ | extractionStatus | ควรเพิ่ม confidence |

**สิ่งที่ควรทำต่อ:**
- เพิ่ม table extraction สำหรับ spec sheets
- เพิ่ม OCR confidence metric
- บันทึก extracted text พร้อม page number สำหรับ citation

**ความเสี่ยง:** medium - OCR accuracy ขึ้นกับ Tesseract model quality

---

## 3. Production RAG Architecture

### References: Haystack, production RAG systems

**ปัญหาที่แก้:** AI Q&A ต้องตอบจากหลักฐานจริง ไม่ใช่ fabrication

**Pattern ที่เรียนรู้:**

| Pattern | ปัญหา | Thai Car Intel | Status |
|---------|--------|----------------|--------|
| Hybrid retrieval (structured + vector) | ราคาต้อง exact, specs ต้อง semantic | hybrid search | ใช้แล้ว |
| Metadata filtering | ต้องกรอง verified sources only | vector query filters | ใช้แล้ว |
| Bounded chunking | chunk ใหญ่เกินไป | chunker.ts | ใช้แล้ว |
| Citation validation | AI สร้าง URL ปลอม | citations.ts | ใช้แล้ว |
| Source-provenance context | ไม่รู้ว่า answer มาจากไหน | whyThisAnswer | ใช้แล้ว |
| Reranking | ผลค้นหาเยอะเกินไป | ยังไม่มี | ควรเพิ่ม |
| Retrieval evaluation | ไม่รู้ว่า search ดีแค่ไหน | ยังไม่มี | ควรเพิ่ม |
| Query decomposition | คำถามซับซ้อนเกินไป | question-terms.ts | ใช้แล้ว |

**สิ่งที่ควรทำต่อ:**
- เพิ่ม reranking step สำหรับ evidence
- บันทึก retrieval metrics (precision, recall)
- สร้าง evaluation dataset สำหรับ acceptance tests

**ความเสี่ยง:** low - incremental improvements

---

## 4. Data Quality Engineering

### References: Great Expectations, dbt testing

**ปัญหาที่แก้:** ข้อมูลรถผิด/ซ้ำ/ล้าสมัย

**Pattern ที่เรียนรู้:**

| Pattern | ปัญหา | Thai Car Intel | Status |
|---------|--------|----------------|--------|
| Schema validation | ข้อมูลผิด type/format | Prisma schema + Zod | ใช้แล้ว |
| Price history constraints | ราคาซ้ำ/overlap | exclusion constraint | ใช้แล้ว |
| Source freshness tracking | ข้อมูลเก่า | verifiedAt/observedAt | ใช้แล้ว |
| Conflict detection | ราคาขัดแย้ง | price history + source | ใช้แล้ว |
| Anomaly detection | ราคาผิดปกติ | ยังไม่มี | ควรเพิ่ม |
| Data contracts | importer validation | Zod schemas | ใช้แล้ว |
| Automated validation | ตรวจข้อมูลอัตโนมัติ | database constraints | ใช้แล้ว |
| Manual review queue | ข้อมูลน่าสงสัย | ReviewItem model | มี schema แล้ว ยังไม่มี UI |

**สิ่งที่ควรทำต่อ:**
- เพิ่ม price anomaly detection (e.g. ราคาเปลี่ยน >50%)
- เพิ่ม freshness alert (ข้อมูลเก่า >30 วัน)
- สร้าง data quality dashboard

**ความเสี่ยง:** low

---

## 5. Agent Production Patterns

### References: 12-factor agents, reliable AI architectures

**ปัญหาที่แก้:** Research agents ต้องรันซ้ำได้ ไม่ทำลายข้อมูล

**Pattern ที่เรียนรู้:**

| Pattern | ปัญหา | Thai Car Intel | Status |
|---------|--------|----------------|--------|
| Audit trail | ไม่รู้ว่า agent ทำอะไร | research_runs + data_change_logs | ใช้แล้ว |
| Staged pipeline | ทำทุกอย่างพร้อมกันไม่ได้ | Discovery→Verify→Extract→Reconcile | ใช้แล้ว |
| Partial success | บาง source ล้มเหลว | PARTIAL_SUCCESS status | ใช้แล้ว |
| Tool boundaries | agent ทำอะไรได้/ไม่ได้ | safe-fetch + domain allowlist | ใช้แล้ว |
| Human approval points | ข้อมูลสำคัญต้องคน approve | ReviewItem/BrochureVerification | มี schema แล้ว |
| State management | ทำซ้ำไม่ได้ status | research run status tracking | ใช้แล้ว |
| Observability | ไม่รู้ว่า agent ทำงานยังไง | research run fields | ใช้แล้ว แต่ไม่มี dashboard |

**สิ่งที่ควรทำต่อ:**
- สร้าง research run dashboard
- เพิ่ม structured logging
- บันทึก token/latency metrics

**ความเสี่ยง:** low

---

## 6. Vehicle Data Modeling

**ปัญหาที่แก้:** ข้อมูลรถไทยมีความซับซ้อน (ชื่อ Thai/English, model year, facelift, EV naming)

**Pattern ที่เรียนรู้จาก domain knowledge:**

| Pattern | ปัญหา | Thai Car Intel | Status |
|---------|--------|----------------|--------|
| Manufacturer → Model → Variant hierarchy | รถหลาย trim | schema | ใช้แล้ว |
| Official Thai/English names | ชื่อไทย/อังกฤษ | nameTh + nameEn | ใช้แล้ว |
| Price history with source | ราคาเปลี่ยน | prices table | ใช้แล้ว |
| Variant aliases | ชื่อเรียกต่างกัน | aliases table | ใช้แล้ว |
| Model year handling | รถหลายปี model | modelYear field | ใช้แล้ว |
| Fuel type classification | EV/HEV/PHEV/Petrol/Diesel | VariantSpec key | ใช้แล้ว |
| Facelift handling | minor change ไม่ใช่ generation ใหม่ | ยังไม่มี | ควรเพิ่ม |
| Generation tracking | รถหลาย generation | ยังไม่มี | ควรเพิ่ม |

**สิ่งที่ควรทำต่อ:**
- เพิ่ม generation/facelift model
- เพิ่ม Thai nickname aliases (e.g. "วีออส" = Vios)
- เพิ่ม EV-specific naming (kWh, km range)

**ความเสี่ยง:** medium - schema change

---

## 7. Image Asset Verification

### References: CLIP, multimodal retrieval

**ปัญหาที่แก้:** ภาพรถต้องตรงรุ่น ไม่ใช่ generic

**Pattern ที่เรียนรู้:**

| Pattern | ปัญหา | Thai Car Intel | Status |
|---------|--------|----------------|--------|
| SHA-256 dedup | ภาพซ้ำกัน | contentHash | ใช้แล้ว |
| Perceptual hash | ภาพ resize/compress | perceptualHash field | มี schema แล้ว ยังไม่ implement |
| Role classification | ภาพ interior/exterior | image role | ใช้แล้ว |
| Source provenance | ไม่รู้ว่าภาพมาจากไหน | sourcePageUrl + sourceDocument | ใช้แล้ว |
| CLIP-based classification | ไม่รู้ว่าภาพเป็นรถรุ่นไหน | ยังไม่มี | ควรเพิ่ม |
| Image similarity | ภาพคล้ายกัน | ยังไม่มี | ควรเพิ่ม |

**สิ่งที่ควรทำต่อ:**
- Implement perceptual hash
- เพิ่ม CLIP-based image classification (local model)
- บันทึก image metadata (width, height, format)

**ความเสี่ยง:** medium - ต้อง setup CLIP model

---

## Summary

| Area | ใช้แล้ว | ควรเพิ่ม | Priority |
|------|---------|----------|----------|
| Web Research | 80% | retry policy, cache | Medium |
| PDF Intelligence | 70% | table extraction, OCR confidence | Medium |
| RAG | 75% | reranking, eval dataset | High |
| Data Quality | 65% | anomaly detection, freshness alerts | High |
| Agent Patterns | 70% | dashboard, structured logging | Medium |
| Vehicle Modeling | 75% | generation, facelift, aliases | Medium |
| Image Verification | 55% | perceptual hash, CLIP classification | Low |

**Total adoption rate: ~70%** — ระบบที่สร้างไปแล้วใช้ pattern ที่ดีอยู่แล้ว ~70% สิ่งที่เหลือเป็น incremental improvement
