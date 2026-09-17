# Recommended Improvements

> Actionable improvements ที่ควรทำต่อ จาก agent-learning-roadmap
> เรียงตาม priority: High → Medium → Low

---

## High Priority (ทำตอนนี้/เร็ว ๆ นี้)

### 1. RAG Retrieval Evaluation

**ปัญหา:** ไม่รู้ว่า search results ดีพอสำหรับ AI Q&A หรือไม่

**วิธีทำ:**
- สร้าง evaluation dataset 20-30 questions ที่มี expected answers
- วัด retrieval precision@k, recall@k
- เพิ่ม metric ใน admin dashboard

**Cost:** 2-3 วัน
**Benefit:** รู้ว่า system ดีจริงแค่ไหน, มี baseline สำหรับปรับปรุง

### 2. Price Anomaly Detection

**ปัญหา:** ราคาผิดปกติ (e.g. Camry 1 บาท) จะถูก import เข้ามาโดยไม่ถูกจับ

**วิธีทำ:**
- เพิ่ม Zod validation: price must be within ±50% of category average
- เพิ่ม change detection: ถ้าราคาเปลี่ยน >30% ต้อง flag
- เพิ่ม freshness check: ข้อมูลเก่า >60 วันต้อง alert

**Cost:** 1-2 วัน
**Benefit:** ป้องกัน data corruption

### 3. Retry Policy สำหรับ safe-fetch

**ปัญหา:** timeout ชั่วคราวทำให้ research run fail ทั้งที่ source ยังใช้ได้

**วิธีทำ:**
- เพิ่ม exponential backoff + jitter
- Max 3 retries
- บันทึก retry count ใน research run

**Cost:** 1 วัน
**Benefit:** ลด false negative จาก network issues

---

## Medium Priority (ทำเดือนหน้า)

### 4. Table Extraction สำหรับ Brochure

**ปัญหา:** Spec tables ใน brochure ถูก extract เป็น plain text ไม่ได้ structure

**วิธีทำ:**
- ใช้ pdfplumber หรือ camelot สำหรับ table extraction
- Map table rows → variant/spec fields
- บันทึก page number + table position

**Cost:** 3-5 วัน
**Benefit:** ได้ structured data จาก brochure จริง

### 5. Structured Logging

**ปัญหา:** ไม่มี centralized log สำหรับ debug

**วิธีทำ:**
- ใช้ pino หรือ structured console.log
- Log format: `{ ts, level, component, runId, message, meta }`
- ไม่ log secrets

**Cost:** 2 วัน
**Benefit:** debug ง่ายขึ้น, วิเคราะห์ performance ได้

### 6. Data Quality Dashboard

**ปัญหา:** ไม่เห็นภาพรวม data quality

**วิธีทำ:**
- สร้าง `/admin/data-quality` page
- แสดง: manufacturer coverage, price freshness, source health, conflicts
- Auto-refresh

**Cost:** 2-3 วัน
**Benefit:** เห็นปัญหาก่อน user เจอ

### 7. Generation/Facelift Model

**ปัญหา:** Camry 2024 vs Camry 2026 ต้องแยกกันชัดเจน

**วิธีทำ:**
- เพิ่ม `generation` field ใน model
- เพิ่ม `facelift` boolean ใน variant
- แยก model year กับ generation

**Cost:** 2-3 วัน (schema migration + data fix)
**Benefit:** จัดกลุ่มรถได้ถูกต้อง

### 8. Research Run Dashboard

**ปัญหา:** ไม่เห็นว่า agent ทำอะไรอยู่

**วิธีทำ:**
- สร้าง `/admin/research` page
- แสดง research runs, status, errors, candidates
- Filter by status/brand/date

**Cost:** 2 วัน
**Benefit:** monitor agent health

---

## Low Priority (ทำเมื่อมีเวลา)

### 9. Perceptual Hash สำหรับ Images

**วิธีทำ:** ใช้ `phash` npm package
**Cost:** 1 วัน
**Benefit:** dedup รูป resize/compress

### 10. CLIP-based Image Classification

**วิธีทำ:** ใช้ local CLIP model สำหรับ classify interior/exterior/hero
**Cost:** 3-4 วัน + model download
**Benefit:** auto-classify images

### 11. Retrieval Reranking

**วิธีทำ:** เพิ่ม cross-encoder reranking หลัง vector search
**Cost:** 2-3 วัน + reranker model
**Benefit:** search results ดีขึ้น

### 12. Thai Nickname Aliases

**วิธีทำ:** เพิ่ม aliases เช่น "วีออส" → Vios, "ไฮแลนเดอร์" → Highlander
**Cost:** 1-2 วัน (data entry + import)
**Benefit:** search ภาษาไทยง่ายขึ้น

---

## Execution Order

```text
Phase 1 (สัปดาห์นี้):
  1. Price anomaly detection
  2. Retry policy

Phase 2 (เดือนหน้า):
  3. Table extraction
  4. Structured logging
  5. Data quality dashboard

Phase 3 (เมื่อมีเวลา):
  6. Generation model
  7. Research dashboard
  8. RAG evaluation dataset
```

---

## Rule: Every improvement must pass this checklist

- [ ] ไม่ breaking existing features
- [ ] มี tests
- [ ] ไม่เพิ่ม complexity ที่ไม่จำเป็น
- [ ] ใช้ dependency ที่มีอยู่แล้ว
- [ ] มี rollback plan
- [ ] Documented in this file
