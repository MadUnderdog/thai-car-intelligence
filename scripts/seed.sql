-- Thai Car Intelligence - Complete Database Seed
-- Run: docker exec pgvector psql -U hermes -d thai_car_intelligence -f /path/to/seed.sql

-- Clear existing data
DELETE FROM "Media";
DELETE FROM "VariantFeature";
DELETE FROM "Price";
DELETE FROM "PerformanceSpec";
DELETE FROM "BatterySpec";
DELETE FROM "ChargingSpec";
DELETE FROM "DimensionsSpec";
DELETE FROM "WarrantySpec";
DELETE FROM "SafetySpec";
DELETE FROM "Variant";
DELETE FROM "CarModel";
DELETE FROM "SourceDocument";
DELETE FROM "Source";
DELETE FROM "Manufacturer";
DELETE FROM "Alias";
DELETE FROM "Feature";

-- Features
INSERT INTO "Feature" (id, "nameEn", "nameTh", slug, category, "createdAt", "updatedAt") VALUES
(gen_random_uuid(), 'AEB', 'เบรกฉุกเฉินอัตโนมัติ', 'aeb', 'adas', NOW(), NOW()),
(gen_random_uuid(), 'ACC', 'ครูซคอนโทรล', 'acc', 'adas', NOW(), NOW()),
(gen_random_uuid(), 'LKA', 'ช่วยคงเลน', 'lka', 'adas', NOW(), NOW()),
(gen_random_uuid(), 'LDW', 'เตือนหลุมเลน', 'ldw', 'adas', NOW(), NOW()),
(gen_random_uuid(), 'BSM', 'เฝ้าระวังจุดบอด', 'bsm', 'adas', NOW(), NOW()),
(gen_random_uuid(), 'RCTA', 'เตือนรถข้างหลัง', 'rcta', 'adas', NOW(), NOW()),
(gen_random_uuid(), 'DOW', 'เตือนเปิดประตู', 'dow', 'adas', NOW(), NOW()),
(gen_random_uuid(), 'FCW', 'เตือนชนด้านหน้า', 'fcw', 'adas', NOW(), NOW()),
(gen_random_uuid(), '360 Camera', 'กล้อง 360', 'surround_view', 'adas', NOW(), NOW()),
(gen_random_uuid(), 'Dashcam', 'กล้องติดรถ', 'dashcam', 'safety', NOW(), NOW()),
(gen_random_uuid(), '7 Airbags', 'ถุงลม 7 ใบ', 'airbags_7', 'safety', NOW(), NOW()),
(gen_random_uuid(), '6 Airbags', 'ถุงลม 6 ใบ', 'airbags_6', 'safety', NOW(), NOW()),
(gen_random_uuid(), 'ABS', 'เบรก ABS', 'abs', 'safety', NOW(), NOW()),
(gen_random_uuid(), 'ESC', 'ควบคุมเสถียรภาพ', 'esc', 'safety', NOW(), NOW()),
(gen_random_uuid(), 'TPMS', 'เฝ้าระวังแรงดันยาง', 'tpms', 'safety', NOW(), NOW()),
(gen_random_uuid(), 'ISOFIX', 'ยึดเก้าอี้เด็ก', 'isofix', 'safety', NOW(), NOW()),
(gen_random_uuid(), 'Hill Start', 'ช่วยขึ้นทางลาด', 'hill_start', 'safety', NOW(), NOW()),
(gen_random_uuid(), 'Wireless Charging', 'ชาร์จไร้สาย', 'wireless_charging', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Apple CarPlay', 'CarPlay', 'apple_carplay', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Android Auto', 'Android Auto', 'android_auto', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Panoramic Roof', 'หลังคากระจก', 'panoramic_sunroof', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Power Tailgate', 'ท้ายเปิดอัตโนมัติ', 'power_tailgate', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Ventilated Seats', 'เบาะระบายอากาศ', 'ventilated_seats', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Heated Seats', 'เบาะซังความร้อน', 'heated_seats', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Power Seats', 'เบาะปรับไฟฟ้า', 'power_seats', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Dual Zone AC', 'แอร์ 2 โซน', 'dual_zone_ac', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Keyless Entry', 'เข้ารถไร้กุญแจ', 'keyless_entry', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Push Start', 'สตาร์ทปุ่ม', 'push_start', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Digital Cluster', 'จอดิจิทัล', 'digital_cluster', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'V2L', 'จ่ายไฟภายนอก', 'v2l', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Heat Pump', 'ปั๊มความร้อน', 'heat_pump', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Regen Braking', 'เบรกกลับพลังงาน', 'regen_braking', 'comfort', NOW(), NOW()),
(gen_random_uuid(), 'Traffic Jam Assist', 'ช่วยขับติดขัด', 'tja', 'adas', NOW(), NOW());

-- Manufacturers
INSERT INTO "Manufacturer" (id, "nameEn", "nameTh", slug, "websiteUrl", status, "createdAt", "updatedAt") VALUES
(gen_random_uuid(), 'BYD', 'บีวายดี', 'byd', 'https://www.byd.com/en-th', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'MG', 'เอ็มจี', 'mg', 'https://www.mgcars.com/th', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Toyota', 'โตโยต้า', 'toyota', 'https://www.toyota.co.th', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Honda', 'ฮอนด้า', 'honda', 'https://www.honda.co.th', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Nissan', 'นิสสัน', 'nissan', 'https://www.nissan.co.th', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Mazda', 'มาสด้า', 'mazda', 'https://www.mazda.co.th', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Mitsubishi', 'มิตซูบิชิ', 'mitsubishi', 'https://www.mitsubishi-motors.co.th', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Isuzu', 'อีซูซุ', 'isuzu', 'https://www.isuzu-tis.com', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Ford', 'ฟอร์ด', 'ford', 'https://www.ford.co.th', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Suzuki', 'ซูซูกิ', 'suzuki', 'https://www.suzuki.co.th', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Hyundai', 'ฮุนได', 'hyundai', 'https://www.hyundai.com/th', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Kia', 'เกีย', 'kia', 'https://www.kia.com/th', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Tesla', 'เทสลา', 'tesla', 'https://www.tesla.com', 'ACTIVE', NOW(), NOW());

-- Sources
INSERT INTO "Source" (id, "nameEn", "nameTh", "baseUrl", domain, "sourceType", "manufacturerId", "rightsStatus", status, "createdAt", "updatedAt") VALUES
(gen_random_uuid(), 'BYD Official', 'BYD ทางการ', 'https://www.byd.com/en-th', 'byd.com', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'byd'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'MG Official', 'MG ทางการ', 'https://www.mgcars.com/th', 'mgcars.com', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'mg'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Toyota Official', 'Toyota ทางการ', 'https://www.toyota.co.th', 'toyota.co.th', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'toyota'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Honda Official', 'Honda ทางการ', 'https://www.honda.co.th', 'honda.co.th', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'honda'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Nissan Official', 'Nissan ทางการ', 'https://www.nissan.co.th', 'nissan.co.th', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'nissan'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Mazda Official', 'Mazda ทางการ', 'https://www.mazda.co.th', 'mazda.co.th', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'mazda'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Mitsubishi Official', 'Mitsubishi ทางการ', 'https://www.mitsubishi-motors.co.th', 'mitsubishi-motors.co.th', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'mitsubishi'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Isuzu Official', 'Isuzu ทางการ', 'https://www.isuzu-tis.com', 'isuzu-tis.com', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'isuzu'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Ford Official', 'Ford ทางการ', 'https://www.ford.co.th', 'ford.co.th', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'ford'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Suzuki Official', 'Suzuki ทางการ', 'https://www.suzuki.co.th', 'suzuki.co.th', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'suzuki'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Hyundai Official', 'Hyundai ทางการ', 'https://www.hyundai.com/th', 'hyundai.com', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'hyundai'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Kia Official', 'Kia ทางการ', 'https://www.kia.com/th', 'kia.com', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'kia'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), 'Tesla Official', 'Tesla ทางการ', 'https://www.tesla.com', 'tesla.com', 'OFFICIAL_MANUFACTURER', (SELECT id FROM "Manufacturer" WHERE slug = 'tesla'), 'PUBLIC_DOMAIN', 'ACTIVE', NOW(), NOW());

-- Car Models
INSERT INTO "CarModel" (id, "manufacturerId", "nameEn", "nameTh", slug, status, "createdAt", "updatedAt") VALUES
-- BYD
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'byd'), 'ATTO 2', 'แอทโต 2', 'atto-2', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'byd'), 'ATTO 3', 'แอทโต 3', 'atto-3', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'byd'), 'Dolphin', 'โดลฟิน', 'dolphin', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'byd'), 'Seal', 'ซีล', 'seal', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'byd'), 'Sealion 7', 'ซีไลออน 7', 'sealion-7', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'byd'), 'Sealion 5 DM-i', 'ซีไลออน 5 DM-i', 'sealion-5-dmi', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'byd'), 'Sealion 6 DM-i', 'ซีไลออน 6 DM-i', 'sealion-6-dmi', 'ACTIVE', NOW(), NOW()),
-- MG
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'mg'), 'VS HEV', 'VS HEV', 'vs-hev', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'mg'), 'S5 EV PLUS', 'S5 EV PLUS', 's5-ev-plus', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'mg'), 'URBAN', 'URBAN', 'urban', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'mg'), 'ZS EV', 'ZS EV', 'zs-ev', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'mg'), 'MG4 MY2026', 'MG4 MY2026', 'mg4-my2026', 'ACTIVE', NOW(), NOW()),
-- Toyota
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'toyota'), 'Camry', 'คัมรี', 'camry', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'toyota'), 'Corolla Cross', 'โครอลล่า ครอส', 'corolla-cross', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'toyota'), 'Yaris Ativ', 'ยาริส อาทิฟ', 'yaris-ativ', 'ACTIVE', NOW(), NOW()),
-- Honda
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'honda'), 'Accord e:HEV', 'แอคคอร์ด e:HEV', 'accord-ehev', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'honda'), 'City', 'ซิตี้', 'city', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'honda'), 'HR-V', 'HR-V', 'hr-v', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'honda'), 'CR-V', 'CR-V', 'cr-v', 'ACTIVE', NOW(), NOW()),
-- Others
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'nissan'), 'Kicks e-POWER', 'คิกส์ e-POWER', 'kicks-epower', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'mazda'), 'CX-30', 'CX-30', 'cx-30', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'mitsubishi'), 'Xpander HEV', 'เอ็กแพนเดอร์ HEV', 'xpander-hev', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'isuzu'), 'D-MAX', 'D-MAX', 'd-max', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'ford'), 'Ranger', 'เรนเจอร์', 'ranger', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'suzuki'), 'Swift', 'สวิฟท์', 'swift', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'hyundai'), 'IONIQ 5', 'ไอออนิค 5', 'ioniq-5', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'kia'), 'EV6', 'EV6', 'ev6', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "Manufacturer" WHERE slug = 'tesla'), 'Model 3', 'โมเดล 3', 'model-3', 'ACTIVE', NOW(), NOW());

-- Variants
INSERT INTO "Variant" (id, "modelId", "nameEn", "nameTh", slug, "fuelType", "fuelTypeSource", status, "createdAt", "updatedAt") VALUES
-- BYD ATTO 2
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'atto-2'), 'Standard', 'สแตนดาร์ด', 'atto-2-standard', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'atto-2'), 'Extended', 'เอกซ์เทนเดด', 'atto-2-extended', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
-- BYD ATTO 3
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'atto-3'), 'Premium', 'พรีเมียม', 'atto-3-premium', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'atto-3'), 'Extended', 'เอกซ์เทนเดด', 'atto-3-extended', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
-- BYD Dolphin
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'dolphin'), 'Premium', 'พรีเมียม', 'dolphin-premium', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'dolphin'), 'Extended', 'เอกซ์เทนเดด', 'dolphin-extended', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
-- BYD Seal
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'seal'), 'Dynamic RWD', 'ไดนามิก RWD', 'seal-dynamic-rwd', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'seal'), 'Premium RWD', 'พรีเมียม RWD', 'seal-premium-rwd', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'seal'), 'Performance AWD', 'เพอร์ฟอร์แมนซ์ AWD', 'seal-performance-awd', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
-- BYD Sealion 7
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'sealion-7'), 'Premium RWD', 'พรีเมียม RWD', 'sealion-7-premium-rwd', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'sealion-7'), 'Performance AWD', 'เพอร์ฟอร์แมนซ์ AWD', 'sealion-7-performance-awd', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
-- BYD Sealion 5/6 DM-i
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'sealion-5-dmi'), 'DM-i', 'DM-i', 'sealion-5-dmi', 'PHEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'sealion-6-dmi'), 'DM-i', 'DM-i', 'sealion-6-dmi', 'PHEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
-- MG
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'vs-hev'), 'D', 'D', 'vs-hev-d', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'vs-hev'), 'X', 'X', 'vs-hev-x', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 's5-ev-plus'), 'X+', 'X+', 's5-ev-plus-x', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'urban'), 'URBAN', 'URBAN', 'urban', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'zs-ev'), 'Premium', 'พรีเมียม', 'zs-ev-premium', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'mg4-my2026'), 'Standard', 'สแตนดาร์ด', 'mg4-standard', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'mg4-my2026'), 'Extended', 'เอกซ์เทนเดด', 'mg4-extended', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
-- Toyota
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'camry'), 'HEV Premium', 'HEV พรีเมียม', 'camry-hev-premium', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'camry'), 'HEV Premium S', 'HEV พรีเมียม S', 'camry-hev-premium-s', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'corolla-cross'), 'HEV Smart', 'HEV สมาร์ท', 'corolla-cross-hev-smart', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'corolla-cross'), 'HEV Premium', 'HEV พรีเมียม', 'corolla-cross-hev-premium', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'yaris-ativ'), 'HEV Smart', 'HEV สมาร์ท', 'yaris-ativ-hev-smart', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'yaris-ativ'), 'HEV Premium', 'HEV พรีเมียม', 'yaris-ativ-hev-premium', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
-- Honda
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'accord-ehev'), 'e:HEV', 'e:HEV', 'accord-ehev', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'city'), 'S', 'S', 'city-s', 'Petrol', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'city'), 'V', 'V', 'city-v', 'Petrol', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'hr-v'), 'E', 'E', 'hr-v-e', 'Petrol', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'hr-v'), 'EL', 'EL', 'hr-v-el', 'Petrol', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'cr-v'), 'HEV E', 'HEV E', 'cr-v-hev-e', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'cr-v'), 'HEV EL', 'HEV EL', 'cr-v-hev-el', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
-- Others
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'kicks-epower'), 'V', 'V', 'kicks-epower-v', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'cx-30'), 'S', 'S', 'cx-30-s', 'Petrol', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'xpander-hev'), 'HEV', 'HEV', 'xpander-hev', 'HEV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'd-max'), 'Hi-Lander', 'Hi-Lander', 'd-max-hi-lander', 'Diesel', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'ranger'), 'Wildtrak', 'ไวล์ดแทรค', 'ranger-wildtrak', 'Diesel', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'swift'), 'GL', 'GL', 'swift-gl', 'Petrol', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'ioniq-5'), 'Long Range', 'Long Range', 'ioniq-5-long-range', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'ev6'), 'Long Range', 'Long Range', 'ev6-long-range', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW()),
(gen_random_uuid(), (SELECT id FROM "CarModel" WHERE slug = 'model-3'), 'Long Range', 'Long Range', 'model-3-long-range', 'EV', 'official_verified', 'ACTIVE', NOW(), NOW());

SELECT 'Variants: ' || COUNT(*) FROM "Variant";
