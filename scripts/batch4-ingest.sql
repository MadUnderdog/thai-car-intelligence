-- Batch4 mass harvest ingestion
BEGIN;

INSERT INTO "Source" ("id", "nameTh", "nameEn", "sourceType", "baseUrl", "domain", "rightsStatus", "status", "createdAt", "updatedAt")
VALUES (gen_random_uuid(), 'HeadLight Magazine', 'HeadLight Magazine', 'AUTOMOTIVE_MEDIA', 'https://www.headlightmag.com', 'www.headlightmag.com', 'UNKNOWN', 'ACTIVE', NOW(), NOW())
ON CONFLICT ("nameEn") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-ford-ranger-wolftrak-2026/',
  'https://www.headlightmag.com/official-price-ford-ranger-wolftrak-2026/',
  'ราคาอย่างเป็นทางการ Ford Ranger WOLFTRAK : 949,000 - 1,089,000 บาท | ดีเซล 2.0L Turbo 10AT 4x2 / 4x4 - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Ford Ranger WOLFTRAK : 949,000 - 1,089,000 บาท | ดีเซล 2.0L Turbo 10AT 4x2 / 4x4 - HeadLight Magazine',
  'text/html',
  'th',
  '46309902929c',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-ford-ranger-wolftrak-2026/',
  'https://www.headlightmag.com/official-price-ford-ranger-wolftrak-2026/',
  'ราคาอย่างเป็นทางการ Ford Ranger WOLFTRAK : 949,000 - 1,089,000 บาท | ดีเซล 2.0L Turbo 10AT 4x2 / 4x4 - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Ford Ranger WOLFTRAK : 949,000 - 1,089,000 บาท | ดีเซล 2.0L Turbo 10AT 4x2 / 4x4 - HeadLight Magazine',
  'text/html',
  'th',
  '4dd708696b49',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-ford-ranger-wolftrak-2026/',
  'https://www.headlightmag.com/official-price-ford-ranger-wolftrak-2026/',
  'ราคาอย่างเป็นทางการ Ford Ranger WOLFTRAK : 949,000 - 1,089,000 บาท | ดีเซล 2.0L Turbo 10AT 4x2 / 4x4 - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Ford Ranger WOLFTRAK : 949,000 - 1,089,000 บาท | ดีเซล 2.0L Turbo 10AT 4x2 / 4x4 - HeadLight Magazine',
  'text/html',
  'th',
  '8c8637b426a6',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-ford-ranger-wolftrak-2026/',
  'https://www.headlightmag.com/official-price-ford-ranger-wolftrak-2026/',
  'ราคาอย่างเป็นทางการ Ford Ranger WOLFTRAK : 949,000 - 1,089,000 บาท | ดีเซล 2.0L Turbo 10AT 4x2 / 4x4 - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Ford Ranger WOLFTRAK : 949,000 - 1,089,000 บาท | ดีเซล 2.0L Turbo 10AT 4x2 / 4x4 - HeadLight Magazine',
  'text/html',
  'th',
  '6d4760c39f3b',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-lepas-l6/',
  'https://www.headlightmag.com/official-price-lepas-l6/',
  'ราคาอย่างเป็นทางการ LEPAS L6 : 769,900 - 799,900 บาท | ขุมพลังไฟฟ้า วิ่งไกลสุด 500 km. (NEDC) - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ LEPAS L6 : 769,900 - 799,900 บาท | ขุมพลังไฟฟ้า วิ่งไกลสุด 500 km. (NEDC) - HeadLight Magazine',
  'text/html',
  'th',
  'a5cb74674a44',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-lepas-l6/',
  'https://www.headlightmag.com/official-price-lepas-l6/',
  'ราคาอย่างเป็นทางการ LEPAS L6 : 769,900 - 799,900 บาท | ขุมพลังไฟฟ้า วิ่งไกลสุด 500 km. (NEDC) - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ LEPAS L6 : 769,900 - 799,900 บาท | ขุมพลังไฟฟ้า วิ่งไกลสุด 500 km. (NEDC) - HeadLight Magazine',
  'text/html',
  'th',
  '809ee63b7edd',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-lepas-l6/',
  'https://www.headlightmag.com/official-price-lepas-l6/',
  'ราคาอย่างเป็นทางการ LEPAS L6 : 769,900 - 799,900 บาท | ขุมพลังไฟฟ้า วิ่งไกลสุด 500 km. (NEDC) - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ LEPAS L6 : 769,900 - 799,900 บาท | ขุมพลังไฟฟ้า วิ่งไกลสุด 500 km. (NEDC) - HeadLight Magazine',
  'text/html',
  'th',
  '024ea522a8df',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-lepas-l6/',
  'https://www.headlightmag.com/official-price-lepas-l6/',
  'ราคาอย่างเป็นทางการ LEPAS L6 : 769,900 - 799,900 บาท | ขุมพลังไฟฟ้า วิ่งไกลสุด 500 km. (NEDC) - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ LEPAS L6 : 769,900 - 799,900 บาท | ขุมพลังไฟฟ้า วิ่งไกลสุด 500 km. (NEDC) - HeadLight Magazine',
  'text/html',
  'th',
  'ae70d8e66f25',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-civic-ehev-2026-s-plus-shift/',
  'https://www.headlightmag.com/official-price-honda-civic-ehev-2026-s-plus-shift/',
  'ราคาอย่างเป็นทางการ Honda Civic e:HEV S+ Shift : 949,000 - 1,259,000 บาท | เพิ่มระบบ S+ Shift / BSI / CTM - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda Civic e:HEV S+ Shift : 949,000 - 1,259,000 บาท | เพิ่มระบบ S+ Shift / BSI / CTM - HeadLight Magazine',
  'text/html',
  'th',
  '54729291d19d',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-civic-ehev-2026-s-plus-shift/',
  'https://www.headlightmag.com/official-price-honda-civic-ehev-2026-s-plus-shift/',
  'ราคาอย่างเป็นทางการ Honda Civic e:HEV S+ Shift : 949,000 - 1,259,000 บาท | เพิ่มระบบ S+ Shift / BSI / CTM - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda Civic e:HEV S+ Shift : 949,000 - 1,259,000 บาท | เพิ่มระบบ S+ Shift / BSI / CTM - HeadLight Magazine',
  'text/html',
  'th',
  '2514faa7abea',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-civic-ehev-2026-s-plus-shift/',
  'https://www.headlightmag.com/official-price-honda-civic-ehev-2026-s-plus-shift/',
  'ราคาอย่างเป็นทางการ Honda Civic e:HEV S+ Shift : 949,000 - 1,259,000 บาท | เพิ่มระบบ S+ Shift / BSI / CTM - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda Civic e:HEV S+ Shift : 949,000 - 1,259,000 บาท | เพิ่มระบบ S+ Shift / BSI / CTM - HeadLight Magazine',
  'text/html',
  'th',
  'f80a9af55189',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-byd-seal-6-2026/',
  'https://www.headlightmag.com/official-price-byd-seal-6-2026/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค BYD Seal 6 : 799,900 - 949,900 บาท - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค BYD Seal 6 : 799,900 - 949,900 บาท - HeadLight Magazine',
  'text/html',
  'th',
  '52f9bff17d25',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-byd-seal-6-2026/',
  'https://www.headlightmag.com/official-price-byd-seal-6-2026/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค BYD Seal 6 : 799,900 - 949,900 บาท - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค BYD Seal 6 : 799,900 - 949,900 บาท - HeadLight Magazine',
  'text/html',
  'th',
  '0df305161075',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-byd-seal-6-2026/',
  'https://www.headlightmag.com/official-price-byd-seal-6-2026/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค BYD Seal 6 : 799,900 - 949,900 บาท - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค BYD Seal 6 : 799,900 - 949,900 บาท - HeadLight Magazine',
  'text/html',
  'th',
  '454c86fd3622',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-byd-sealion-5-dm-i-super-phev/',
  'https://www.headlightmag.com/official-price-byd-sealion-5-dm-i-super-phev/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค BYD Sealion 5 DM-i : 699,900 - 799,900 บาท - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค BYD Sealion 5 DM-i : 699,900 - 799,900 บาท - HeadLight Magazine',
  'text/html',
  'th',
  'd50a40c26bc4',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-byd-sealion-5-dm-i-super-phev/',
  'https://www.headlightmag.com/official-price-byd-sealion-5-dm-i-super-phev/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค BYD Sealion 5 DM-i : 699,900 - 799,900 บาท - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค BYD Sealion 5 DM-i : 699,900 - 799,900 บาท - HeadLight Magazine',
  'text/html',
  'th',
  '2335f39573dc',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-byd-sealion-5-dm-i-super-phev/',
  'https://www.headlightmag.com/official-price-byd-sealion-5-dm-i-super-phev/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค BYD Sealion 5 DM-i : 699,900 - 799,900 บาท - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค BYD Sealion 5 DM-i : 699,900 - 799,900 บาท - HeadLight Magazine',
  'text/html',
  'th',
  '3035f422af01',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-suzuki-carry-my2026/',
  'https://www.headlightmag.com/official-price-suzuki-carry-my2026/',
  'ราคาอย่างเป็นทางการ Suzuki CARRY MY2026 : 375,000 บาท | ปรับอ็อพชั่น ราคาลดลง 20,000 บาท - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Suzuki CARRY MY2026 : 375,000 บาท | ปรับอ็อพชั่น ราคาลดลง 20,000 บาท - HeadLight Magazine',
  'text/html',
  'th',
  '527049fa05ed',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-avatr-11-my2026/',
  'https://www.headlightmag.com/official-price-avatr-11-my2026/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค AVATR 11 MY2026 : 2,299,000 - 2,899,000 บาท | เปลี่ยนช่วงล่าง MR Suspension - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค AVATR 11 MY2026 : 2,299,000 - 2,899,000 บาท | เปลี่ยนช่วงล่าง MR Suspension - HeadLight Magazine',
  'text/html',
  'th',
  'd1c27ddf8a3f',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-avatr-11-my2026/',
  'https://www.headlightmag.com/official-price-avatr-11-my2026/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค AVATR 11 MY2026 : 2,299,000 - 2,899,000 บาท | เปลี่ยนช่วงล่าง MR Suspension - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค AVATR 11 MY2026 : 2,299,000 - 2,899,000 บาท | เปลี่ยนช่วงล่าง MR Suspension - HeadLight Magazine',
  'text/html',
  'th',
  '63940f3518e4',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-avatr-11-my2026/',
  'https://www.headlightmag.com/official-price-avatr-11-my2026/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค AVATR 11 MY2026 : 2,299,000 - 2,899,000 บาท | เปลี่ยนช่วงล่าง MR Suspension - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค AVATR 11 MY2026 : 2,299,000 - 2,899,000 บาท | เปลี่ยนช่วงล่าง MR Suspension - HeadLight Magazine',
  'text/html',
  'th',
  '9de4271e533a',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-mitsubishi-attrage-my2026/',
  'https://www.headlightmag.com/official-price-mitsubishi-attrage-my2026/',
  'ราคาอย่างเป็นทางการ Mitsubishi Attrage MY2026 : 564,000 - 619,000 บาท | ปรับดีไซน์ เครื่องยนต์ EURO6 - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Mitsubishi Attrage MY2026 : 564,000 - 619,000 บาท | ปรับดีไซน์ เครื่องยนต์ EURO6 - HeadLight Magazine',
  'text/html',
  'th',
  'c0b2917b31fe',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-mitsubishi-attrage-my2026/',
  'https://www.headlightmag.com/official-price-mitsubishi-attrage-my2026/',
  'ราคาอย่างเป็นทางการ Mitsubishi Attrage MY2026 : 564,000 - 619,000 บาท | ปรับดีไซน์ เครื่องยนต์ EURO6 - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Mitsubishi Attrage MY2026 : 564,000 - 619,000 บาท | ปรับดีไซน์ เครื่องยนต์ EURO6 - HeadLight Magazine',
  'text/html',
  'th',
  '2353a378d667',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'text/html',
  'th',
  '4686bd671045',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'text/html',
  'th',
  'a2a3729cd547',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'text/html',
  'th',
  'b22be20cb6f9',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'text/html',
  'th',
  'dd96fd8b33cf',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'text/html',
  'th',
  '53e76c6b9f53',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'text/html',
  'th',
  '1a1ead62d63c',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'text/html',
  'th',
  'f4959da68c10',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'https://www.headlightmag.com/official-price-honda-city-big-minorchange-2026/',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda CITY Big Minorchange 2026 : 569,000 - 749,000 บาท | ปรับใหญ่รอบคัน ราคาต่ำลง ! - HeadLight Magazine',
  'text/html',
  'th',
  'a9b32949289d',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-mg-urban-2026/',
  'https://www.headlightmag.com/official-price-mg-urban-2026/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG URBAN : 529,900 - 709,900 บาท* - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG URBAN : 529,900 - 709,900 บาท* - HeadLight Magazine',
  'text/html',
  'th',
  '1841110ece40',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-mg-urban-2026/',
  'https://www.headlightmag.com/official-price-mg-urban-2026/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG URBAN : 529,900 - 709,900 บาท* - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG URBAN : 529,900 - 709,900 บาท* - HeadLight Magazine',
  'text/html',
  'th',
  '175178ce538a',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-mg-urban-2026/',
  'https://www.headlightmag.com/official-price-mg-urban-2026/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG URBAN : 529,900 - 709,900 บาท* - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG URBAN : 529,900 - 709,900 บาท* - HeadLight Magazine',
  'text/html',
  'th',
  '903b53da4ac0',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-mg-urban-2026/',
  'https://www.headlightmag.com/official-price-mg-urban-2026/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG URBAN : 529,900 - 709,900 บาท* - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG URBAN : 529,900 - 709,900 บาท* - HeadLight Magazine',
  'text/html',
  'th',
  '42b42730ca5f',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-changan-nevo-q05/',
  'https://www.headlightmag.com/official-price-changan-nevo-q05/',
  'ราคาอย่างเป็นทางการ Changan NEVO Q05 : 599,900 - 679,900 บาท | B-SUV ขุมพลังไฟฟ้า วิ่งไกล 462 km. (NEDC) - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Changan NEVO Q05 : 599,900 - 679,900 บาท | B-SUV ขุมพลังไฟฟ้า วิ่งไกล 462 km. (NEDC) - HeadLight Magazine',
  'text/html',
  'th',
  'ae447172a178',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-changan-nevo-q05/',
  'https://www.headlightmag.com/official-price-changan-nevo-q05/',
  'ราคาอย่างเป็นทางการ Changan NEVO Q05 : 599,900 - 679,900 บาท | B-SUV ขุมพลังไฟฟ้า วิ่งไกล 462 km. (NEDC) - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Changan NEVO Q05 : 599,900 - 679,900 บาท | B-SUV ขุมพลังไฟฟ้า วิ่งไกล 462 km. (NEDC) - HeadLight Magazine',
  'text/html',
  'th',
  '3bc6b2702917',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-accord-2026/',
  'https://www.headlightmag.com/official-price-honda-accord-2026/',
  'ราคาอย่างเป็นทางการ Honda Accord (MY2026) : 1,479,000 - 1,764,000 บาท | เพิ่มภายในขาว ภายนอกเทา Urban Gray - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda Accord (MY2026) : 1,479,000 - 1,764,000 บาท | เพิ่มภายในขาว ภายนอกเทา Urban Gray - HeadLight Magazine',
  'text/html',
  'th',
  '7e711d29752a',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-accord-2026/',
  'https://www.headlightmag.com/official-price-honda-accord-2026/',
  'ราคาอย่างเป็นทางการ Honda Accord (MY2026) : 1,479,000 - 1,764,000 บาท | เพิ่มภายในขาว ภายนอกเทา Urban Gray - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda Accord (MY2026) : 1,479,000 - 1,764,000 บาท | เพิ่มภายในขาว ภายนอกเทา Urban Gray - HeadLight Magazine',
  'text/html',
  'th',
  '791db40bbc5f',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-honda-accord-2026/',
  'https://www.headlightmag.com/official-price-honda-accord-2026/',
  'ราคาอย่างเป็นทางการ Honda Accord (MY2026) : 1,479,000 - 1,764,000 บาท | เพิ่มภายในขาว ภายนอกเทา Urban Gray - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Honda Accord (MY2026) : 1,479,000 - 1,764,000 บาท | เพิ่มภายในขาว ภายนอกเทา Urban Gray - HeadLight Magazine',
  'text/html',
  'th',
  'a552100d2cdc',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-suzuki-jimny-with-safety-support-my2026/',
  'https://www.headlightmag.com/official-price-suzuki-jimny-with-safety-support-my2026/',
  'ราคาอย่างเป็นทางการ Suzuki JIMNY MY2026 : 1,590,000 - 1,620,000 บาท | เพิ่มระบบ Safety Support ถุงลม 6 ตำแหน่ง - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Suzuki JIMNY MY2026 : 1,590,000 - 1,620,000 บาท | เพิ่มระบบ Safety Support ถุงลม 6 ตำแหน่ง - HeadLight Magazine',
  'text/html',
  'th',
  '9edce4dd4b3e',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-suzuki-jimny-with-safety-support-my2026/',
  'https://www.headlightmag.com/official-price-suzuki-jimny-with-safety-support-my2026/',
  'ราคาอย่างเป็นทางการ Suzuki JIMNY MY2026 : 1,590,000 - 1,620,000 บาท | เพิ่มระบบ Safety Support ถุงลม 6 ตำแหน่ง - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ Suzuki JIMNY MY2026 : 1,590,000 - 1,620,000 บาท | เพิ่มระบบ Safety Support ถุงลม 6 ตำแหน่ง - HeadLight Magazine',
  'text/html',
  'th',
  'f4373a7cf38c',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-mg4-my2026-2/',
  'https://www.headlightmag.com/official-price-mg4-my2026-2/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG4 MY2026 : 579,900 - 699,900 บาท | ภายในใหม่ ขุมพลังใหม่ - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG4 MY2026 : 579,900 - 699,900 บาท | ภายในใหม่ ขุมพลังใหม่ - HeadLight Magazine',
  'text/html',
  'th',
  '6f3d0d6fcb29',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-mg4-my2026-2/',
  'https://www.headlightmag.com/official-price-mg4-my2026-2/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG4 MY2026 : 579,900 - 699,900 บาท | ภายในใหม่ ขุมพลังใหม่ - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG4 MY2026 : 579,900 - 699,900 บาท | ภายในใหม่ ขุมพลังใหม่ - HeadLight Magazine',
  'text/html',
  'th',
  '4b5202299575',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-mg4-my2026-2/',
  'https://www.headlightmag.com/official-price-mg4-my2026-2/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG4 MY2026 : 579,900 - 699,900 บาท | ภายในใหม่ ขุมพลังใหม่ - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG4 MY2026 : 579,900 - 699,900 บาท | ภายในใหม่ ขุมพลังใหม่ - HeadLight Magazine',
  'text/html',
  'th',
  '23e4686798fa',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-mg4-my2026-2/',
  'https://www.headlightmag.com/official-price-mg4-my2026-2/',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG4 MY2026 : 579,900 - 699,900 บาท | ภายในใหม่ ขุมพลังใหม่ - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ + เทียบสเป็ค MG4 MY2026 : 579,900 - 699,900 บาท | ภายในใหม่ ขุมพลังใหม่ - HeadLight Magazine',
  'text/html',
  'th',
  'ac040b5ffa5d',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-mg-im-5-long-range-rwd/',
  'https://www.headlightmag.com/official-price-mg-im-5-long-range-rwd/',
  'ราคาอย่างเป็นทางการ MG IM5 : 1,449,900 บาท | ขุมพลังไฟฟ้า 407 แรงม้า RWD แบตฯ 100kWh วิ่งไกล 860 km. (NEDC) - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ MG IM5 : 1,449,900 บาท | ขุมพลังไฟฟ้า 407 แรงม้า RWD แบตฯ 100kWh วิ่งไกล 860 km. (NEDC) - HeadLight Magazine',
  'text/html',
  'th',
  '5fe09d599e16',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-mg-im-5-long-range-rwd/',
  'https://www.headlightmag.com/official-price-mg-im-5-long-range-rwd/',
  'ราคาอย่างเป็นทางการ MG IM5 : 1,449,900 บาท | ขุมพลังไฟฟ้า 407 แรงม้า RWD แบตฯ 100kWh วิ่งไกล 860 km. (NEDC) - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ MG IM5 : 1,449,900 บาท | ขุมพลังไฟฟ้า 407 แรงม้า RWD แบตฯ 100kWh วิ่งไกล 860 km. (NEDC) - HeadLight Magazine',
  'text/html',
  'th',
  'a85818334ccb',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-nio-firefly/',
  'https://www.headlightmag.com/official-price-nio-firefly/',
  'ราคาอย่างเป็นทางการ NIO FireFly : 799,000 บาท | 143 แรงม้า RWD แบตฯ 42 kWh วิ่งไกล 400 km. (NEDC) - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ NIO FireFly : 799,000 บาท | 143 แรงม้า RWD แบตฯ 42 kWh วิ่งไกล 400 km. (NEDC) - HeadLight Magazine',
  'text/html',
  'th',
  'efdcda5434a1',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'HeadLight Magazine' LIMIT 1),
  'https://www.headlightmag.com/official-price-tesla-model-y-l-long-wheelbase/',
  'https://www.headlightmag.com/official-price-tesla-model-y-l-long-wheelbase/',
  'ราคาอย่างเป็นทางการ TESLA MODEL Y L : เริ่มต้น 1,999,000 บาท | ฐานล้อยาว เบาะ 3 แถว 6 ที่นั่ง - HeadLight Magazine',
  'ราคาอย่างเป็นทางการ TESLA MODEL Y L : เริ่มต้น 1,999,000 บาท | ฐานล้อยาว เบาะ 3 แถว 6 ที่นั่ง - HeadLight Magazine',
  'text/html',
  'th',
  '0a6f79def45a',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "Source" ("id", "nameTh", "nameEn", "sourceType", "baseUrl", "domain", "rightsStatus", "status", "createdAt", "updatedAt")
VALUES (gen_random_uuid(), 'AutoLifeThailand', 'AutoLifeThailand', 'AUTOMOTIVE_MEDIA', 'https://autolifethailand.tv', 'autolifethailand.tv', 'UNKNOWN', 'ACTIVE', NOW(), NOW())
ON CONFLICT ("nameEn") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-special-price-byd-seal-5-dm-i-phev-plug-in-hybrid-sep-2026/',
  'https://autolifethailand.tv/official-special-price-byd-seal-5-dm-i-phev-plug-in-hybrid-sep-2026/',
  'ส่วนลด 100,000 ! BYD Seal 5 DM-i PHEV ราคาพิเศษ : 499,900 - 649,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'ส่วนลด 100,000 ! BYD Seal 5 DM-i PHEV ราคาพิเศษ : 499,900 - 649,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'text/html',
  'th',
  '5abd0f442342',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-special-price-byd-seal-5-dm-i-phev-plug-in-hybrid-sep-2026/',
  'https://autolifethailand.tv/official-special-price-byd-seal-5-dm-i-phev-plug-in-hybrid-sep-2026/',
  'ส่วนลด 100,000 ! BYD Seal 5 DM-i PHEV ราคาพิเศษ : 499,900 - 649,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'ส่วนลด 100,000 ! BYD Seal 5 DM-i PHEV ราคาพิเศษ : 499,900 - 649,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'text/html',
  'th',
  '1cb94d8422a0',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-special-price-byd-seal-5-dm-i-phev-plug-in-hybrid-sep-2026/',
  'https://autolifethailand.tv/official-special-price-byd-seal-5-dm-i-phev-plug-in-hybrid-sep-2026/',
  'ส่วนลด 100,000 ! BYD Seal 5 DM-i PHEV ราคาพิเศษ : 499,900 - 649,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'ส่วนลด 100,000 ! BYD Seal 5 DM-i PHEV ราคาพิเศษ : 499,900 - 649,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'text/html',
  'th',
  '7b374aadd50a',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-special-price-byd-seal-5-dm-i-phev-plug-in-hybrid-sep-2026/',
  'https://autolifethailand.tv/official-special-price-byd-seal-5-dm-i-phev-plug-in-hybrid-sep-2026/',
  'ส่วนลด 100,000 ! BYD Seal 5 DM-i PHEV ราคาพิเศษ : 499,900 - 649,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'ส่วนลด 100,000 ! BYD Seal 5 DM-i PHEV ราคาพิเศษ : 499,900 - 649,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'text/html',
  'th',
  '803a1497f9a7',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-price-discount-byd-sealion-5-dm-i-phev-sep-2026/',
  'https://autolifethailand.tv/official-price-discount-byd-sealion-5-dm-i-phev-sep-2026/',
  'ส่วนลด 100,000 ! BYD Sealion 5 DM-i PHEV ราคาอย่างเป็นทางการ : 659,900 - 744,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'ส่วนลด 100,000 ! BYD Sealion 5 DM-i PHEV ราคาอย่างเป็นทางการ : 659,900 - 744,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'text/html',
  'th',
  '568e92f51c8a',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-price-discount-byd-sealion-5-dm-i-phev-sep-2026/',
  'https://autolifethailand.tv/official-price-discount-byd-sealion-5-dm-i-phev-sep-2026/',
  'ส่วนลด 100,000 ! BYD Sealion 5 DM-i PHEV ราคาอย่างเป็นทางการ : 659,900 - 744,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'ส่วนลด 100,000 ! BYD Sealion 5 DM-i PHEV ราคาอย่างเป็นทางการ : 659,900 - 744,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'text/html',
  'th',
  'dbadfa4ca0a0',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-price-discount-byd-sealion-5-dm-i-phev-sep-2026/',
  'https://autolifethailand.tv/official-price-discount-byd-sealion-5-dm-i-phev-sep-2026/',
  'ส่วนลด 100,000 ! BYD Sealion 5 DM-i PHEV ราคาอย่างเป็นทางการ : 659,900 - 744,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'ส่วนลด 100,000 ! BYD Sealion 5 DM-i PHEV ราคาอย่างเป็นทางการ : 659,900 - 744,900 บาท (ประกอบไทย) | 3 วัน 18-19-20 กันยายน นี้ ! - Autolifethailand.tv',
  'text/html',
  'th',
  '267804a3ba86',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/offcial-price-denza-z9gt-ev-bev-thailand-2026/',
  'https://autolifethailand.tv/offcial-price-denza-z9gt-ev-bev-thailand-2026/',
  'DENZA Z9GT รถไฟฟ้า100% ราคาอย่างเป็นทางการ : 2,899,900 บาท | มอเตอร์ 3 ตัว 1,156 แรงม้า ชาร์จ DC 1,500 kW - Autolifethailand.tv',
  'DENZA Z9GT รถไฟฟ้า100% ราคาอย่างเป็นทางการ : 2,899,900 บาท | มอเตอร์ 3 ตัว 1,156 แรงม้า ชาร์จ DC 1,500 kW - Autolifethailand.tv',
  'text/html',
  'th',
  '1903211dfd96',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/offcial-price-denza-z9gt-ev-bev-thailand-2026/',
  'https://autolifethailand.tv/offcial-price-denza-z9gt-ev-bev-thailand-2026/',
  'DENZA Z9GT รถไฟฟ้า100% ราคาอย่างเป็นทางการ : 2,899,900 บาท | มอเตอร์ 3 ตัว 1,156 แรงม้า ชาร์จ DC 1,500 kW - Autolifethailand.tv',
  'DENZA Z9GT รถไฟฟ้า100% ราคาอย่างเป็นทางการ : 2,899,900 บาท | มอเตอร์ 3 ตัว 1,156 แรงม้า ชาร์จ DC 1,500 kW - Autolifethailand.tv',
  'text/html',
  'th',
  '75a04b55bc6c',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-price-discount-byd-atto-2-ev-bev-sep-2026/',
  'https://autolifethailand.tv/official-price-discount-byd-atto-2-ev-bev-sep-2026/',
  'ส่วนลด 90,000 ! BYD ATTO 2 รถไฟฟ้า100% ราคาพิเศษ : 569,900 บาท (นำเข้า CBU จีน) | Surprise Deal 11-12-13 กันยายน นี้ เท่านั้น ! - Autolifethailand.tv',
  'ส่วนลด 90,000 ! BYD ATTO 2 รถไฟฟ้า100% ราคาพิเศษ : 569,900 บาท (นำเข้า CBU จีน) | Surprise Deal 11-12-13 กันยายน นี้ เท่านั้น ! - Autolifethailand.tv',
  'text/html',
  'th',
  'ae752e4544b7',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-price-discount-byd-atto-2-ev-bev-sep-2026/',
  'https://autolifethailand.tv/official-price-discount-byd-atto-2-ev-bev-sep-2026/',
  'ส่วนลด 90,000 ! BYD ATTO 2 รถไฟฟ้า100% ราคาพิเศษ : 569,900 บาท (นำเข้า CBU จีน) | Surprise Deal 11-12-13 กันยายน นี้ เท่านั้น ! - Autolifethailand.tv',
  'ส่วนลด 90,000 ! BYD ATTO 2 รถไฟฟ้า100% ราคาพิเศษ : 569,900 บาท (นำเข้า CBU จีน) | Surprise Deal 11-12-13 กันยายน นี้ เท่านั้น ! - Autolifethailand.tv',
  'text/html',
  'th',
  '67a16fff0989',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-price-tesla-model-y-thailand/',
  'https://autolifethailand.tv/official-price-tesla-model-y-thailand/',
  'ราคาอย่างเป็นทางการ TESLA Model Y : 1,959,000 - 2,509,000 บาท (นำเข้า CBU) | C-SUV โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'ราคาอย่างเป็นทางการ TESLA Model Y : 1,959,000 - 2,509,000 บาท (นำเข้า CBU) | C-SUV โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'text/html',
  'th',
  '1c3e9c9ce58a',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-price-tesla-model-y-thailand/',
  'https://autolifethailand.tv/official-price-tesla-model-y-thailand/',
  'ราคาอย่างเป็นทางการ TESLA Model Y : 1,959,000 - 2,509,000 บาท (นำเข้า CBU) | C-SUV โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'ราคาอย่างเป็นทางการ TESLA Model Y : 1,959,000 - 2,509,000 บาท (นำเข้า CBU) | C-SUV โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'text/html',
  'th',
  'f0c9f6c4df66',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-price-tesla-model-y-thailand/',
  'https://autolifethailand.tv/official-price-tesla-model-y-thailand/',
  'ราคาอย่างเป็นทางการ TESLA Model Y : 1,959,000 - 2,509,000 บาท (นำเข้า CBU) | C-SUV โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'ราคาอย่างเป็นทางการ TESLA Model Y : 1,959,000 - 2,509,000 บาท (นำเข้า CBU) | C-SUV โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'text/html',
  'th',
  'b50a73adfd63',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-price-tesla-model-y-thailand/',
  'https://autolifethailand.tv/official-price-tesla-model-y-thailand/',
  'ราคาอย่างเป็นทางการ TESLA Model Y : 1,959,000 - 2,509,000 บาท (นำเข้า CBU) | C-SUV โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'ราคาอย่างเป็นทางการ TESLA Model Y : 1,959,000 - 2,509,000 บาท (นำเข้า CBU) | C-SUV โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'text/html',
  'th',
  'a9d2cb461bcb',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-price-tesla-model-3-official-thailand/',
  'https://autolifethailand.tv/official-price-tesla-model-3-official-thailand/',
  'ราคาอย่างเป็นทางการ TESLA Model 3 : 1,759,000 - 2,309,000 บาท (นำเข้า CBU) | Sedan โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'ราคาอย่างเป็นทางการ TESLA Model 3 : 1,759,000 - 2,309,000 บาท (นำเข้า CBU) | Sedan โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'text/html',
  'th',
  '3cb2677e6873',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-price-tesla-model-3-official-thailand/',
  'https://autolifethailand.tv/official-price-tesla-model-3-official-thailand/',
  'ราคาอย่างเป็นทางการ TESLA Model 3 : 1,759,000 - 2,309,000 บาท (นำเข้า CBU) | Sedan โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'ราคาอย่างเป็นทางการ TESLA Model 3 : 1,759,000 - 2,309,000 บาท (นำเข้า CBU) | Sedan โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'text/html',
  'th',
  'd2346c5e06f5',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoLifeThailand' LIMIT 1),
  'https://autolifethailand.tv/official-price-tesla-model-3-official-thailand/',
  'https://autolifethailand.tv/official-price-tesla-model-3-official-thailand/',
  'ราคาอย่างเป็นทางการ TESLA Model 3 : 1,759,000 - 2,309,000 บาท (นำเข้า CBU) | Sedan โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'ราคาอย่างเป็นทางการ TESLA Model 3 : 1,759,000 - 2,309,000 บาท (นำเข้า CBU) | Sedan โดยบริษัทแม่ Tesla Official (Thailand) - Autolifethailand.tv',
  'text/html',
  'th',
  '4cf25967c219',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "Source" ("id", "nameTh", "nameEn", "sourceType", "baseUrl", "domain", "rightsStatus", "status", "createdAt", "updatedAt")
VALUES (gen_random_uuid(), '9CARTHAI', '9CARTHAI', 'AUTOMOTIVE_MEDIA', 'https://www.9carthai.com', 'www.9carthai.com', 'UNKNOWN', 'ACTIVE', NOW(), NOW())
ON CONFLICT ("nameEn") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'e8b1ff3135a4',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'de56f6e39e9c',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '7692212e1d35',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '8d7901df83c0',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'e3cf537cbf17',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '3febe9f2ee7b',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '423a2ce7069a',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '75f6931fd931',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'ee35606d15c0',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '1fd945435af5',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'ab7bd7ecb7d8',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'ffdc17fa651b',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '4fde1a0ddb17',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '53248aaab567',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '7ff0754346cc',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'bff52df1bbba',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '620ea759ceae',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '522613ce80d0',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'f97cc4234fbe',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '7acfdd0d8dd2',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'c6c6efe2b87c',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'b7136a387ebc',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '838ef9f0da43',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '238e1183c348',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '2194367237af',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '9b7770b0a543',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '4234ffb83034',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'ab7d3392ec85',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/honda-price/',
  'https://www.9carthai.com/honda-price/',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  '[ดาวน์น้อย ออกรถง่าย] Honda ราคารถ ฮอนด้า 2026-2027 - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '52b4d2f296cb',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '069f057fc244',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '5c250b122cdc',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'fdba92e633c7',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '159cfd278c8e',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'd3d00ffc98d9',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '85b86a00e58c',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '66e441d68626',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  'b69681177214',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '584b6d5f36bb',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '316fffd9a822',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '96ee1d10cfbe',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '6103b3fca3cc',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '55fc390a3196',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '16d3fcc1eff4',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '3f9481b1600e',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '798bf200a35e',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '56232bfcbae1',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '0119a608cd05',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '208ab3be20bb',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '53f5aad77a8f',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = '9CARTHAI' LIMIT 1),
  'https://www.9carthai.com/toyota-price/',
  'https://www.9carthai.com/toyota-price/',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'Toyota 2026-2027 ราคารถ โตโยต้า [โปรโมชั่นดีที่สุด-ช่วยดันทุกเคส] - 9CARTHAI : 9CARTHAI',
  'text/html',
  'th',
  '8c193574dce1',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "Source" ("id", "nameTh", "nameEn", "sourceType", "baseUrl", "domain", "rightsStatus", "status", "createdAt", "updatedAt")
VALUES (gen_random_uuid(), 'AutoSpinn', 'AutoSpinn', 'AUTOMOTIVE_MEDIA', 'https://www.autospinn.com', 'www.autospinn.com', 'UNKNOWN', 'ACTIVE', NOW(), NOW())
ON CONFLICT ("nameEn") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  'beed6e243077',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  '0a326cb3f44d',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  '7c1ef77096e1',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  '3c44ce672660',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  'a39357253bf6',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  '262257b3575a',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  'fce7288c78fb',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  'e3c9de0e3f59',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  'bcbc308db46d',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  '6f253cd2b1b3',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  'ee9b82c27fe4',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  'a40b3ed8bd81',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  'f4050b571c55',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  '7676c5b106ab',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  '691a29497fc0',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  '2ca421c03462',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  '35f462d03dd5',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  'ea29aec9b31f',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  '2bd4a71119a1',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;

INSERT INTO "SourceDocument" ("id", "sourceId", "url", "canonicalUrl", "titleTh", "titleEn", "mimeType", "language", "contentHash", "fetchedAt", "documentType", "status", "rightsStatus", "extractionStatus", "createdAt", "updatedAt")
VALUES (
  gen_random_uuid(),
  (SELECT id FROM "Source" WHERE "nameEn" = 'AutoSpinn' LIMIT 1),
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'https://www.autospinn.com/2026/03/byd-price-updated-148444',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'รถ BYD ราคาเท่าไหร่แล้ว ? อัปเดตแต่ละรุ่น 2026 สรุปจบในที่เดียว - ราคารถยนต์และตารางผ่อน |',
  'text/html',
  'th',
  'cb1a97d8722f',
  NOW(),
  'price_article',
  'DISCOVERED',
  'UNKNOWN',
  'SUCCEEDED',
  NOW(),
  NOW()
)
ON CONFLICT ("sourceId", "contentHash") DO NOTHING;
COMMIT;