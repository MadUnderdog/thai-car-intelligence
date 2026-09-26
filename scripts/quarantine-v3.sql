-- quarantine-v3.sql
-- Uses subqueries instead of JOINs on target table
-- Date: 2026-09-20

BEGIN;

-- ============================================================
-- STEP 1: Ensure quarantine columns exist
-- ============================================================
ALTER TABLE "Price" ADD COLUMN IF NOT EXISTS "quarantineReason" text;
ALTER TABLE "Price" ADD COLUMN IF NOT EXISTS "quarantineStatus" text DEFAULT 'ACTIVE';
ALTER TABLE "VariantSpec" ADD COLUMN IF NOT EXISTS "quarantineReason" text;
ALTER TABLE "VariantSpec" ADD COLUMN IF NOT EXISTS "quarantineStatus" text DEFAULT 'ACTIVE';

-- ============================================================
-- STEP 2: Quarantine GR Corolla → Corolla Altis contamination
-- ============================================================
UPDATE "Price"
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'cross_model_contamination: grcorolla price misattributed to Corolla Altis'
WHERE id IN (
  SELECT p.id
  FROM "Price" p
  JOIN "Variant" v ON p."variantId" = v.id
  JOIN "CarModel" cm ON v."modelId" = cm.id
  LEFT JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd.id
  WHERE cm."nameEn" = 'Corolla Altis'
    AND (sd.url ILIKE '%grcorolla%' OR p."sourceUrl" ILIKE '%grcorolla%')
);

-- ============================================================
-- STEP 3: Quarantine prices where sourceDocument URL
-- series_code doesn't match model name
-- ============================================================
UPDATE "Price"
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'cross_model_contamination: sourceDocument URL series_code does not match model'
WHERE id IN (
  SELECT p.id
  FROM "Price" p
  JOIN "Variant" v ON p."variantId" = v.id
  JOIN "CarModel" cm ON v."modelId" = cm.id
  LEFT JOIN "SourceDocument" sd ON p."sourceDocumentId" = sd.id
  WHERE p."quarantineStatus" = 'ACTIVE'
    AND sd.url IS NOT NULL
    AND (
      (sd.url ILIKE '%series_code=grcorolla%' AND cm."nameEn" != 'GR Corolla')
      OR (sd.url ILIKE '%series_code=gryaris%' AND cm."nameEn" != 'GR Yaris')
      OR (sd.url ILIKE '%series_code=yarisativ%' AND cm."nameEn" NOT ILIKE '%yaris%ativ%')
      OR (sd.url ILIKE '%series_code=corollacross%' AND cm."nameEn" NOT ILIKE '%corolla%cross%')
      OR (sd.url ILIKE '%series_code=altis%' AND cm."nameEn" NOT ILIKE '%corolla%altis%')
      OR (sd.url ILIKE '%series_code=hilux_champ%' AND cm."nameEn" NOT ILIKE '%hilux%')
      OR (sd.url ILIKE '%series_code=fortuner_leader%' AND cm."nameEn" NOT ILIKE '%fortuner%')
      OR (sd.url ILIKE '%series_code=fortuner_grsport%' AND cm."nameEn" NOT ILIKE '%fortuner%')
      OR (sd.url ILIKE '%series_code=veloz%' AND cm."nameEn" NOT ILIKE '%veloz%')
      OR (sd.url ILIKE '%series_code=innovazenix%' AND cm."nameEn" NOT ILIKE '%innova%')
      OR (sd.url ILIKE '%series_code=bz4x%' AND cm."nameEn" != 'bZ4X')
      OR (sd.url ILIKE '%series_code=camry%' AND cm."nameEn" != 'Camry')
    )
);

-- ============================================================
-- STEP 4: Quarantine stale current prices
-- ============================================================
UPDATE "Price"
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'stale_current: isCurrent=true but validTo is in the past'
WHERE "isCurrent" = true
  AND "validTo" IS NOT NULL
  AND "validTo" < NOW()
  AND "quarantineStatus" = 'ACTIVE';

-- ============================================================
-- STEP 5: Quarantine VariantSpecs with cross-model source URLs
-- ============================================================
UPDATE "VariantSpec"
SET "quarantineStatus" = 'QUARANTINED',
    "quarantineReason" = 'cross_model_contamination: source article URL does not match model'
WHERE id IN (
  SELECT vs.id
  FROM "VariantSpec" vs
  JOIN "Variant" v ON vs."variantId" = v.id
  JOIN "CarModel" cm ON v."modelId" = cm.id
  JOIN "SourceDocument" sd ON vs."sourceDocumentId" = sd.id
  WHERE sd.url LIKE '%headlightmag%'
    AND vs."quarantineStatus" = 'ACTIVE'
    AND sd.url NOT ILIKE '%' || replace(lower(replace(cm."nameEn", ' ', '-')), ' ', '-') || '%'
    AND sd.url NOT ILIKE '%' || replace(lower(cm."nameEn"), ' ', '') || '%'
);

-- ============================================================
-- STEP 6: Create ModelAlias table
-- ============================================================
CREATE TABLE IF NOT EXISTS "ModelAlias" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  "canonicalModelId" uuid NOT NULL REFERENCES "CarModel"(id) ON DELETE CASCADE,
  "aliasModelId" uuid NOT NULL REFERENCES "CarModel"(id) ON DELETE CASCADE,
  reason text NOT NULL,
  "createdAt" timestamp(3) DEFAULT CURRENT_TIMESTAMP,
  UNIQUE("canonicalModelId", "aliasModelId")
);

-- ============================================================
-- STEP 7: Populate ModelAlias for all duplicate pairs
-- ============================================================
INSERT INTO "ModelAlias" ("canonicalModelId", "aliasModelId", reason) VALUES
('4187797a-c648-4f26-9774-72d082b73a59', '445ce97d-5067-447f-b28f-859577aa50bc', 'duplicate_model: Yaris'),
('7af9e452-4c82-4593-8213-b74ec733d395', 'ec72aeff-b84b-491b-9752-411df038d6b3', 'duplicate_model: Corolla Altis'),
('fda08b07-1ff0-4d24-a284-293d3bd76d9a', '1d5850ff-3c9d-4344-b8f0-0c40caf797aa', 'duplicate_model: Corolla Cross'),
('d9e4c103-91de-484c-a990-51dfac9b2cd7', '73b14331-7072-449c-acb3-6fd5445e2d19', 'duplicate_model: Camry'),
('62fe0644-74c8-40b3-97a3-c03e0e8a3bc4', '9eb356cf-30e8-4454-b6ea-901ca38afbfc', 'duplicate_model: Fortuner'),
('3556de94-ee68-44fe-b4db-86332e7ddf9f', '738a8d18-2acb-46fc-9310-a5f51c6c947a', 'duplicate_model: Hilux'),
('2dd75fb8-9040-4792-a3b4-462b76e369a5', 'e07ba6e3-594e-4a3f-a665-f4241051b347', 'duplicate_model: Innova Zenix'),
('ffc3c2c4-73e6-48e3-a2d1-28e7655ebf84', 'd7898be2-2e68-41b9-b9a0-74a6a1cf350d', 'duplicate_model: Yaris Cross'),
('9739ee86-5983-497d-b73a-777740a0ec52', '6031c4fc-aa01-4935-b239-7edf8ece362a', 'duplicate_model: bZ4X'),
('8e3bd9c3-9008-46f2-a453-56187a221df5', '49527f9e-59cd-4745-803c-e7b1b6c8b05b', 'duplicate_model: Accord'),
('ca098613-a180-4eae-b7e4-3babed3f960c', '0b1d246f-f327-4663-a151-a1e1a1f1b65e', 'duplicate_model: Civic'),
('031a30a9-bf21-46b8-9d64-d8ca64fc0fc4', 'b3901ef8-7417-44bb-92f4-37631fe90be4', 'duplicate_model: City'),
('350032b4-c9da-4cb0-a105-1ac31c61bf60', '3571c6a1-28f2-489a-a8dd-3614f969bff0', 'duplicate_model: City Hatchback'),
('0cafc6d6-afc7-4dbb-a0de-3822a81bd68b', '9d754cac-0d33-4058-92e4-59472ce84032', 'duplicate_model: HR-V'),
('28b12fbc-cdbc-48d7-8696-b6eec181ca41', 'dc520fa1-c171-4beb-a2c1-bc92de4cfe19', 'duplicate_model: CR-V'),
('4da529ab-b933-4e0b-8999-d5e33a5c8c4d', 'c538c025-ea54-490f-90e2-51314cee2193', 'duplicate_model: Civic Type R'),
('04df86b3-d727-47ac-9ecb-9cba255af825', '4ea1326f-8058-4efe-a5b4-261a843af914', 'duplicate_model: BR-V'),
('5189b36c-e3d7-43a6-97f7-5023ca5b7d5a', '98c46693-0f7c-430a-bae8-a9c69649a096', 'duplicate_model: e:N2'),
('3e764cc3-c908-4c76-89b2-e2153c920074', 'd808d2d2-646c-4a22-9230-0f33687b1663', 'duplicate_model: WR-V'),
('0a131bab-e937-460d-8ac3-dc14cf5bb2f0', 'f555f60b-9794-48e8-a627-ece50fce09d2', 'duplicate_model: Super-ONE'),
('7235a334-f948-4b1c-ad57-e7bd2538951b', '65c4ca3f-d008-420b-8351-1a34c082869f', 'duplicate_model: URBAN'),
('ce4c675e-264a-400a-b940-b60fbe99326c', 'cfd7b64b-3fb4-4fd4-910a-fe01bfddd1be', 'duplicate_model: CYBERSTER'),
('42b4c100-4e95-47f4-b07b-41b5ece1a230', '0fe95675-0692-47c1-9739-b8e699286897', 'duplicate_model: EP Plus'),
('f6a70a1a-759e-46ff-87b4-70933aaa346c', '9bef760e-b2af-4657-a762-89f8c1e169c0', 'duplicate_model: ES'),
('a7ec01d9-ee71-48e7-a0af-153f11448574', 'ae0be834-6cad-42c0-aaf8-2d9ff580c8bc', 'duplicate_model: IM6'),
('3c5a0a6c-5fc1-4db4-9044-3ad9fd9b5a18', 'efcd12b7-20b6-4a40-94ef-26cbc3cd658d', 'duplicate_model: IM5'),
('eccfea5e-6be0-4ac0-98a3-c1c2eb4df794', 'f2710324-f366-4124-86a8-3cff7cc7cedf', 'duplicate_model: ZS'),
('8873b451-4fbd-4d0e-ac36-5b330e51652e', '6efa70b0-52eb-4787-a221-34ebe6f1fd12', 'duplicate_model: ZS EV'),
('6f40eeea-f307-449d-9ecd-d3222344de26', 'f3990b1e-e602-4bec-9611-0ee4f04ef825', 'duplicate_model: VS HEV'),
('461cbacc-3ec3-4b0e-bf27-134f715253ff', '089bb1a9-6e3d-4670-91c0-3bbc1a0c3f36', 'duplicate_model: HS PHEV'),
('ed5ed7e7-6f63-423f-9a2e-3c8f45a12f28', '6eb08b9f-6bce-416d-a5ad-4bdfa3d2b8cf', 'duplicate_model: EXTENDER'),
('7a78854f-a7a9-4041-94bd-fdc59b43fdce', '3fa85dbe-c217-4b67-91e6-688eab956d95', 'duplicate_model: MG3 HYBRID+'),
('18f94e91-da68-49a2-8a63-4cefadaf86b6', '4459be63-1c63-4f55-93af-6132576856a1', 'duplicate_model: MAXUS 7'),
('5d2510f0-68a3-4857-adf0-3030e6c0dc43', 'a45208dd-8b0e-4dac-bb38-ef7ebf449c97', 'duplicate_model: MAXUS 9'),
('2463ef40-9e92-488d-b105-b229a66a32ed', 'c9d111ea-99ff-4c39-ba9c-25817d5d0637', 'duplicate_model: S5 EV PLUS'),
('6bbc00f0-912d-4243-ab3b-bf5aa88f9ae1', 'f87526d5-684b-4b47-924d-8b6e30288b7c', 'duplicate_model: Kicks'),
('ebf5a7f7-7629-43dd-a197-34285508567e', '905fcb61-d225-47a9-8e8a-8397419e35c6', 'duplicate_model: Mazda 6e'),
('c396364b-3141-48eb-b526-d213376b68df', 'd27cbf46-a43c-4b84-8d72-fbb26525e265', 'duplicate_model: Crosstrek'),
('39c8d4e5-286f-45ea-bd23-01be8c84826b', '1f55aa6f-2bc8-458d-8dee-3494aaa0c355', 'duplicate_model: Model Y'),
('a65853d3-bf26-4442-8d0c-e32a0a087642', 'd9fa1353-4192-4574-ace3-4523965aefde', 'duplicate_model: Model 3'),
('2090049f-2c4d-434c-8ecb-54777ff83280', 'ed0aa352-2a00-40ce-b4b5-051fee5010c5', 'duplicate_model: Ioniq 5'),
('eaadf15e-709b-4326-91f9-158c2fc5e22c', '32ba650a-1342-435f-8c03-9856645bfb51', 'duplicate_model: Santa Fe'),
('03305e7a-3040-41bc-b1b7-2592f45c033b', '295fae1e-3106-4f18-8790-5920c6417ca2', 'duplicate_model: Firefly'),
('17ecdc6b-38e9-4046-886c-1e1eda76ff21', 'c61cacbb-08e0-4698-8895-b7f3ac20aee6', 'duplicate_model: Avatr 11'),
('ddd6010d-eeb4-4cb8-b463-ac8c70ce0fd0', 'b00923cb-64c2-4ebc-b58f-b16ccb5ac5ea', 'duplicate_model: Xpeng L03'),
('1d49bc9c-355e-41a3-8404-b3e598f71b23', '94640355-ee33-4769-a435-0fc53b6abaad', 'duplicate_model: Zeekr X'),
('dbdfbfdf-dc57-467f-a772-e339eecb4458', '77cc7811-b210-4d88-ab0f-522ca022aaac', 'duplicate_model: Denza Z9GT'),
('4ac00767-d393-4f8c-9618-4854cdc5978c', '938341ef-4612-43ea-a0a5-12367b653b82', 'duplicate_model: Tank 500'),
('fbb8d652-29e2-446a-afd7-3ed56d4768b0', '445e2cc5-8f6f-4e07-a90c-1f69d09905f9', 'duplicate_model: Sealion 5 DM-i'),
('49edffa9-0e1e-4a4a-adcb-ebeffe5a9987', '023e741d-c3e3-414d-9d77-968214671334', 'duplicate_model: Sealion 6 DM-i')
ON CONFLICT DO NOTHING;

-- ============================================================
-- STEP 8: Verification counts
-- ============================================================
SELECT 'prices_quarantined' as metric, count(*) as val FROM "Price" WHERE "quarantineStatus" = 'QUARANTINED'
UNION ALL SELECT 'prices_active', count(*) FROM "Price" WHERE "quarantineStatus" = 'ACTIVE'
UNION ALL SELECT 'specs_quarantined', count(*) FROM "VariantSpec" WHERE "quarantineStatus" = 'QUARANTINED'
UNION ALL SELECT 'specs_active', count(*) FROM "VariantSpec" WHERE "quarantineStatus" = 'ACTIVE'
UNION ALL SELECT 'model_aliases', count(*) FROM "ModelAlias"
ORDER BY metric;

COMMIT;
