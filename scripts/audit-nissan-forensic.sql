-- Nissan Forensic Audit — 2026-09-20
-- This script documents all DB changes made during the forensic pass.
-- Run in order. Idempotent where possible.

-- 1. BEFORE STATE: 10 Nissan prices
-- Price IDs:
--   bcce55a6-cb0c-4cae-afbe-a976f1aeea7d  Almera VL 573000
--   d83ebf62-970a-46be-b927-ab18bcf4622e  Kicks E 789900 (DUPLICATE)
--   76b9f6fd-14ab-4657-8762-341723a9ce98  Kicks e-POWER 789900
--   02cb9b89-371f-430c-a274-fdf2a4af7016  Navara King Cab Calibre E 606000
--   2dc061bb-bf5b-4d5c-b6d2-769ae57e8bc8  Leaf EV 1590000
--   6a2983b9-5cc9-4e10-bf92-d32a168d4f86  Livina E 667000 (NO PROVENANCE)
--   0af5a4f1-64ee-440c-9941-5eae8a4e51be  March E 420000
--   ddde05d2-09d3-43d3-b7c5-26906384532c  Serena V 1339000 (TEANA PRICE!)
--   b5f3104f-713b-4779-b964-cd35418e43d7  Terra 2.3 V 1199000
--   ca3aaf1d-4871-4133-b805-e13c831dfd20  X-Trail V 1699000

-- 2. FIXES APPLIED:

-- 2a. Delete Kicks E duplicate (d83ebf62)
-- DELETE FROM "Price" WHERE id = 'd83ebf62-970a-46be-b927-ab18bcf4622e';

-- 2b. Fix Serena V: 1339000 → 1469000 (was Teana price)
-- UPDATE "Price" SET amount = 1469000 WHERE id = 'ddde05d2-09d3-43d3-b7c5-26906384532c';

-- 2c. Fix Livina E: 667000 → 672000 (was outdated)
-- UPDATE "Price" SET amount = 672000 WHERE id = '6a2983b9-5cc9-4e10-bf92-d32a168d4f86';

-- 2d. Restore Livina provenance (was NULL)
-- Created SourceDocument + BrochureVerification for Livina

-- 2e. Reclassify ALL Nissan prices MSRP → LIST_PRICE
-- UPDATE "Price" SET "priceType" = 'LIST_PRICE' WHERE id IN (...);

-- 3. AFTER STATE: 9 Nissan prices
-- All LIST_PRICE, all with provenance chain
