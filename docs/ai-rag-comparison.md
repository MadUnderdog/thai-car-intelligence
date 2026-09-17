# AI/RAG และการเปรียบเทียบ

ระบบส่วนนี้ออกแบบให้ทำงานแบบไม่มี API key ได้อย่างซื่อสัตย์:

- `getAIProvider()` ใช้ deterministic unavailable provider เมื่อ `AI_PROVIDER` ว่าง/ไม่รู้จัก หรือค่า `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL` ไม่ครบ จึงไม่มีการส่งข้อมูลออกหรือบันทึก key
- เมื่อตั้ง `AI_PROVIDER=openai-compatible` (รองรับ alias `openai`) adapter จะเรียก OpenAI-compatible `/chat/completions` และ `/embeddings` ด้วย timeout, ตรวจสอบรูปแบบผลลัพธ์และมิติ embedding; error ของ upstream, timeout และ config ที่ไม่ครบจะไม่ถูกกลบเป็นคำตอบปลอม
- ต้องตั้ง `AI_BASE_URL` เองเสมอ ไม่มีการเดา endpoint ผู้ให้บริการ ส่วน embedding ต้องตั้ง `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY` และ `EMBEDDING_MODEL` ก่อนเรียกใช้งาน
- ยังไม่มี Google/Gemini grounding adapter: ขอบเขตในอนาคตควรแยกเป็น provider boundary ใหม่ Google Search grounding ใช้ได้เพื่อ discovery เท่านั้น เว้นแต่จะเปิด evidence page/PDF จริงและตรวจสอบเนื้อหา/ตัวตน/ตลาดก่อนใช้เป็นหลักฐาน
- `/api/ai/ask` รับคำถามภาษาไทยและสร้าง evidence จากข้อมูล catalog ที่ตรวจสอบแล้วเท่านั้น เมื่อฐานข้อมูลหรือ AI ไม่พร้อมจะคืนสถานะที่บอกตรง ๆ ไม่สร้างคำตอบรถยนต์ขึ้นเอง
- การค้นหา AI แยกคำถามเป็น token ชื่อรุ่น/ชื่อค่ายที่ normalize และตัด stop words ก่อนค้นหา: ลองคำถามเต็มที่จำกัดความยาวก่อน แล้วจึงค้นหา token แต่ละคำแบบมีขอบเขตและ dedupe ตาม variant ID; คำถามที่ไม่มี candidate จะไม่ถูกใช้เป็น entity
- prompt กำหนดไม่ให้แต่งตัวเลข ราคา URL หรือ citation และต้องเปิดเผยข้อมูลขัดแย้ง/ไม่เพียงพอ
- citations ต้องอ้าง `evidenceId` และ URL เดียวกับ evidence ที่มีอยู่จริง
- `/compare` ใช้ structured data เป็นหลัก รองรับ variant ID 2–4 รายการ ช่องว่างแสดง `ไม่มีข้อมูล` และสามารถดูที่มาได้

## สัญญา API ถาม AI

`POST /api/ai/ask` body `{ "question": "..." }` คืน `{ answer, citations, whyThisAnswer, mode, status }` โดย `status` อาจเป็น `ok`, `unavailable`, `insufficient_evidence` หรือ `invalid_request`.
