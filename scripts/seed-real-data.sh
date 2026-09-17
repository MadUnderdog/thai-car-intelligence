#!/usr/bin/env bash
# Seed real car data — matches actual schema
cd /home/ubuntu/thai-car-intelligence

echo "=== Seeding Real Car Data ==="

insert_mfr() {
  docker exec pgvector psql -U hermes -d thai_car_intelligence -c "
    INSERT INTO \"Manufacturer\" (id, slug, \"nameEn\", \"nameTh\", \"websiteUrl\", \"createdAt\", \"updatedAt\")
    VALUES (gen_random_uuid(), '$1', '$2', '$3', '$4', NOW(), NOW());
  " 2>/dev/null
}

insert_model() {
  docker exec pgvector psql -U hermes -d thai_car_intelligence -c "
    INSERT INTO \"CarModel\" (id, \"manufacturerId\", \"nameEn\", \"nameTh\", slug, segment, \"createdAt\", \"updatedAt\")
    VALUES (gen_random_uuid(), (SELECT id FROM \"Manufacturer\" WHERE \"nameEn\" = '$1'), '$2', '$3', '$4', '$5', NOW(), NOW());
  " 2>/dev/null
}

insert_variant() {
  docker exec pgvector psql -U hermes -d thai_car_intelligence -c "
    INSERT INTO \"Variant\" (id, \"modelId\", \"nameEn\", \"nameTh\", slug, \"modelYear\", \"fuelType\", \"createdAt\", \"updatedAt\")
    VALUES (gen_random_uuid(), (SELECT id FROM \"CarModel\" WHERE slug = '$1'), '$2', '$3', '$4', 2026, '$5', NOW(), NOW());
  " 2>/dev/null
}

insert_price() {
  docker exec pgvector psql -U hermes -d thai_car_intelligence -c "
    INSERT INTO \"Price\" (id, \"variantId\", \"priceType\", amount, currency, \"validFrom\", \"observedAt\", \"isCurrent\", \"sourceUrl\")
    VALUES (gen_random_uuid(), (SELECT id FROM \"Variant\" WHERE slug = '$1'), 'MSRP', $2, 'THB', '$3', NOW(), true, '$4');
  " 2>/dev/null
}

echo "--- Manufacturers ---"
insert_mfr "byd" "BYD" "บีวายดี" "https://www.byd.com/en-th"
insert_mfr "mg" "MG" "เอ็มจี" "https://www.mgcars.com/th"
insert_mfr "honda" "Honda" "ฮอนด้า" "https://www.honda.co.th"
insert_mfr "toyota" "Toyota" "โตโยต้า" "https://www.toyota.co.th"

echo "--- BYD Models ---"
insert_model "BYD" "ATTO 2" "อัตโต 2" "atto-2" "Compact SUV"
insert_model "BYD" "ATTO 3" "อัตโต 3" "atto-3" "SUV"
insert_model "BYD" "Dolphin" "ดอลฟิน" "dolphin" "Hatchback"
insert_model "BYD" "Seal" "ซีล" "seal" "Sedan"
insert_model "BYD" "Sealion 7" "ซีไลออน 7" "sealion-7" "SUV"
insert_model "BYD" "Sealion 6 DM-i" "ซีไลออน 6" "sealion-6" "SUV"
insert_model "BYD" "Sealion 5 DM-i" "ซีไลออน 5" "sealion-5" "SUV"
insert_model "BYD" "M6" "เอ็ม 6" "m6" "MPV"

echo "--- BYD Variants ---"
insert_variant "atto-2" "Dynamic" "ไดนามิก" "atto-2-dynamic" "BEV"
insert_price "atto-2-dynamic" 629900 "2026-01-01" "https://www.byd.com/en-th/car/atto2"
insert_variant "atto-2" "Premium" "พรีเมียม" "atto-2-premium" "BEV"
insert_price "atto-2-premium" 659900 "2026-01-01" "https://www.byd.com/en-th/car/atto2"

insert_variant "atto-3" "Standard Range" "สแตนดาร์ด" "atto-3-standard" "BEV"
insert_price "atto-3-standard" 629900 "2026-01-01" "https://www.byd.com/en-th/car/atto3"
insert_variant "atto-3" "Extended Range" "เอ็กซ์เตนเดด" "atto-3-extended" "BEV"
insert_price "atto-3-extended" 719900 "2026-01-01" "https://www.byd.com/en-th/car/atto3"

insert_variant "dolphin" "Dynamic" "ไดนามิก" "dolphin-dynamic" "BEV"
insert_price "dolphin-dynamic" 799900 "2026-01-01" "https://www.byd.com/en-th/car/dolphin"
insert_variant "dolphin" "Premium" "พรีเมียม" "dolphin-premium" "BEV"
insert_price "dolphin-premium" 899900 "2026-01-01" "https://www.byd.com/en-th/car/dolphin"

insert_variant "seal" "Dynamic RWD" "ไดนามิก" "seal-dynamic" "BEV"
insert_price "seal-dynamic" 1099900 "2026-01-01" "https://www.byd.com/en-th/car/seal"
insert_variant "seal" "Performance AWD" "เพอร์ฟอร์แมนซ์" "seal-performance" "BEV"
insert_price "seal-performance" 1299900 "2026-01-01" "https://www.byd.com/en-th/car/seal"

insert_variant "sealion-7" "Advanced" "อดวานซ์ด" "sealion-7-advanced" "BEV"
insert_price "sealion-7-advanced" 1718020 "2026-01-01" "https://www.byd.com/en-th/car/sealion7"

insert_variant "m6" "Electric" "อิเล็กทริก" "m6-ev" "BEV"
insert_price "m6-ev" 859900 "2026-01-01" "https://www.byd.com/en-th/car/m6"

echo "--- MG Models ---"
insert_model "MG" "URBAN" "เออร์บัน" "mg-urban" "SUV"
insert_model "MG" "MG4" "เอ็มจี 4" "mg4" "Hatchback"
insert_model "MG" "S5 EV PLUS" "เอส 5" "mg-s5" "SUV"
insert_model "MG" "ZS EV" "เซดเอส อีวี" "mg-zs-ev" "SUV"
insert_model "MG" "ES" "อีเอส" "mg-es" "Sedan"
insert_model "MG" "EP Plus" "อีพี พลัส" "mg-ep" "Sedan"
insert_model "MG" "IM5" "ไอเอ็ม 5" "mg-im5" "Sedan"
insert_model "MG" "IM6" "ไอเอ็ม 6" "mg-im6" "SUV"
insert_model "MG" "MAXUS 7" "แม็กซัส 7" "mg-maxus7" "MPV"
insert_model "MG" "MAXUS 9" "แม็กซัส 9" "mg-maxus9" "MPV"
insert_model "MG" "CYBERSTER" "ไซเบอร์สเตอร์" "mg-cyberster" "Roadster"
insert_model "MG" "MG3 HYBRID+" "เอ็มจี 3" "mg3-hybrid" "Hatchback"
insert_model "MG" "VS HEV" "วีเอส" "mg-vs-hev" "SUV"
insert_model "MG" "HS PHEV" "เอชเอส" "mg-hs-phev" "SUV"
insert_model "MG" "MG5" "เอ็มจี 5" "mg5" "Sedan"
insert_model "MG" "ZS" "เซดเอส" "mg-zs" "SUV"
insert_model "MG" "EXTENDER" "เอ็กซ์เตนเดอร์" "mg-extender" "Pickup"

echo "--- MG Variants ---"
insert_variant "mg-urban" "EV" "อีวี" "mg-urban-ev" "BEV"
insert_price "mg-urban-ev" 579900 "2026-01-01" "https://www.mgcars.com/th/cars/mg-urban"
insert_variant "mg4" "Standard" "สแตนดาร์ด" "mg4-standard" "BEV"
insert_price "mg4-standard" 669900 "2026-01-01" "https://www.mgcars.com/th/cars/mg4-my2026"
insert_variant "mg-s5" "EV PLUS" "อีวี พลัส" "mg-s5-ev" "BEV"
insert_price "mg-s5-ev" 749900 "2026-01-01" "https://www.mgcars.com/th/cars/mg-s5-ev-plus"
insert_variant "mg-zs-ev" "Premium" "พรีเมียม" "mg-zs-ev-premium" "BEV"
insert_price "mg-zs-ev-premium" 829900 "2026-01-01" "https://www.mgcars.com/th/cars/mg-zs-ev"
insert_variant "mg-es" "EV" "อีวี" "mg-es-ev" "BEV"
insert_price "mg-es-ev" 959000 "2026-01-01" "https://www.mgcars.com/th/cars/mg-es"
insert_variant "mg-ep" "EV" "อีวี" "mg-ep-ev" "BEV"
insert_price "mg-ep-ev" 771000 "2026-01-01" "https://www.mgcars.com/th/cars/mg-ep-plus"
insert_variant "mg-im5" "EV" "อีวี" "mg-im5-ev" "BEV"
insert_price "mg-im5-ev" 1549900 "2026-01-01" "https://www.mgcars.com/th/cars/mg-im5"
insert_variant "mg-im6" "EV" "อีวี" "mg-im6-ev" "BEV"
insert_price "mg-im6-ev" 1399900 "2026-01-01" "https://www.mgcars.com/th/cars/mg-im6"
insert_variant "mg-maxus7" "EV" "อีวี" "mg-maxus7-ev" "BEV"
insert_price "mg-maxus7-ev" 1399000 "2026-01-01" "https://www.mgcars.com/th/cars/mg-maxus7"
insert_variant "mg-maxus9" "EV" "อีวี" "mg-maxus9-ev" "BEV"
insert_price "mg-maxus9-ev" 1849900 "2026-01-01" "https://www.mgcars.com/th/cars/mg-maxus9-my26"
insert_variant "mg-cyberster" "EV" "อีวี" "mg-cyberster-ev" "BEV"
insert_price "mg-cyberster-ev" 2499000 "2026-01-01" "https://www.mgcars.com/th/cars/mg-cyberster"
insert_variant "mg3-hybrid" "HYBRID+" "ไฮบริด+" "mg3-hybrid-plus" "HEV"
insert_price "mg3-hybrid-plus" 579900 "2026-01-01" "https://www.mgcars.com/th/cars/all-new-mg3"
insert_variant "mg-vs-hev" "D" "ดี" "mg-vs-hev-d" "HEV"
insert_price "mg-vs-hev-d" 699000 "2026-01-01" "https://www.mgcars.com/th/cars/mg-vs-hev"
insert_variant "mg-hs-phev" "Premium" "พรีเมียม" "mg-hs-phev-premium" "PHEV"
insert_price "mg-hs-phev-premium" 1299000 "2026-01-01" "https://www.mgcars.com/th/cars/mg-hs"
insert_variant "mg5" "Standard" "สแตนดาร์ด" "mg5-standard" "ICE"
insert_price "mg5-standard" 629900 "2026-01-01" "https://www.mgcars.com/th/cars/mg5"
insert_variant "mg-zs" "Standard" "สแตนดาร์ด" "mg-zs-standard" "ICE"
insert_price "mg-zs-standard" 599000 "2026-01-01" "https://www.mgcars.com/th/cars/mg-zs"
insert_variant "mg-extender" "DC" "ดีซี" "mg-extender-dc" "ICE"
insert_price "mg-extender-dc" 769000 "2026-01-01" "https://www.mgcars.com/th/cars/mg-extender-dc"

echo "--- Honda Models ---"
insert_model "Honda" "City" "ซิตี้" "honda-city" "Sedan"
insert_model "Honda" "City Hatchback" "ซิตี้ แฮตช์แบ็ก" "honda-city-hb" "Hatchback"
insert_model "Honda" "Civic" "ซิวิค" "honda-civic" "Sedan"
insert_model "Honda" "HR-V" "เอชอาร์-วี" "honda-hr-v" "SUV"
insert_model "Honda" "CR-V" "ซีอาร์-วี" "honda-cr-v" "SUV"
insert_model "Honda" "Accord" "ออคคอร์ด" "honda-accord" "Sedan"
insert_model "Honda" "WR-V" "ดับเบิลยูอาร์-วี" "honda-wr-v" "SUV"
insert_model "Honda" "BR-V" "บีอาร์-วี" "honda-br-v" "SUV"
insert_model "Honda" "Super-ONE" "ซูเปอร์-วัน" "honda-super-one" "SUV"
insert_model "Honda" "e:N2" "อี:เอ็น 2" "honda-en2" "SUV"
insert_model "Honda" "Civic Type R" "ซิวิค ไทพ์ อาร์" "honda-civic-tr" "Sedan"

echo "--- Honda Variants ---"
insert_variant "honda-city" "e:HEV" "อี:เอชอีวี" "honda-city-ehev" "HEV"
insert_price "honda-city-ehev" 569000 "2026-01-01" "https://www.honda.co.th/city"
insert_variant "honda-city-hb" "e:HEV" "อี:เอชอีวี" "honda-city-hb-ehev" "HEV"
insert_price "honda-city-hb-ehev" 579000 "2026-01-01" "https://www.honda.co.th/cityhatchback"
insert_variant "honda-civic" "e:HEV" "อี:เอชอีวี" "honda-civic-ehev" "HEV"
insert_price "honda-civic-ehev" 949000 "2026-01-01" "https://www.honda.co.th/civic"
insert_variant "honda-hr-v" "e:HEV" "อี:เอชอีวี" "honda-hr-v-ehev" "HEV"
insert_price "honda-hr-v-ehev" 949000 "2026-01-01" "https://www.honda.co.th/hrvehev"
insert_variant "honda-cr-v" "e:HEV" "อี:เอชอีวี" "honda-cr-v-ehev" "HEV"
insert_price "honda-cr-v-ehev" 1409000 "2026-01-01" "https://www.honda.co.th/crv"
insert_variant "honda-accord" "e:HEV" "อี:เอชอีวี" "honda-accord-ehev" "HEV"
insert_price "honda-accord-ehev" 1479000 "2026-01-01" "https://www.honda.co.th/accordehev"
insert_variant "honda-wr-v" "Other" "อื่นๆ" "honda-wr-v-ice" "ICE"
insert_price "honda-wr-v-ice" 799000 "2026-01-01" "https://www.honda.co.th/wrv"
insert_variant "honda-br-v" "Other" "อื่นๆ" "honda-br-v-ice" "ICE"
insert_price "honda-br-v-ice" 915000 "2026-01-01" "https://www.honda.co.th/brv"
insert_variant "honda-super-one" "EV" "อีวี" "honda-super-one-ev" "BEV"
insert_price "honda-super-one-ev" 990000 "2026-01-01" "https://www.honda.co.th/super-one"
insert_variant "honda-en2" "EV" "อีวี" "honda-en2-ev" "BEV"
insert_price "honda-en2-ev" 1429000 "2026-01-01" "https://www.honda.co.th/en2"
insert_variant "honda-civic-tr" "Turbo" "เทอร์โบ" "honda-civic-tr-turbo" "ICE"
insert_price "honda-civic-tr-turbo" 3990000 "2026-01-01" "https://www.honda.co.th/civictyper"

echo "--- Toyota Models ---"
insert_model "Toyota" "Yaris ATIV" "ยาริส อาทิฟ" "toyota-yaris-ativ" "Sedan"
insert_model "Toyota" "Yaris" "ยาริส" "toyota-yaris" "Hatchback"
insert_model "Toyota" "Corolla Altis" "โครอลลัอ อัลติส" "toyota-corolla-altis" "Sedan"
insert_model "Toyota" "Camry" "แคมรี่" "toyota-camry" "Sedan"
insert_model "Toyota" "Yaris Cross" "ยาริส ครอส" "toyota-yaris-cross" "SUV"
insert_model "Toyota" "Corolla Cross" "โครอลลัอ ครอส" "toyota-corolla-cross" "SUV"
insert_model "Toyota" "bZ4X" "บีแซด4เอ็กซ์" "toyota-bz4x" "SUV"
insert_model "Toyota" "Fortuner" "ฟอร์จูเนอร์" "toyota-fortuner" "SUV"
insert_model "Toyota" "Hilux" "ฮิลักซ์" "toyota-hilux" "Pickup"
insert_model "Toyota" "Innova Zenix" "อินโนวา เซนิกซ์" "toyota-innova" "MPV"

echo "--- Toyota Variants ---"
insert_variant "toyota-yaris-ativ" "HEV" "เอชอีวี" "toyota-yaris-ativ-hev" "HEV"
insert_price "toyota-yaris-ativ-hev" 569000 "2026-01-01" "https://www.toyota.co.th/en/model-list"
insert_variant "toyota-yaris-ativ" "Nightshade" "ไนท์เชด" "toyota-yaris-ativ-ns" "HEV"
insert_price "toyota-yaris-ativ-ns" 709000 "2026-01-01" "https://www.toyota.co.th/en/model-list"
insert_variant "toyota-yaris-ativ" "GR Sport" "จีอาร์" "toyota-yaris-ativ-grs" "HEV"
insert_price "toyota-yaris-ativ-grs" 779000 "2026-01-01" "https://www.toyota.co.th/en/model-list"
insert_variant "toyota-yaris" "ICE" "ไอซีอี" "toyota-yaris-ice" "ICE"
insert_price "toyota-yaris-ice" 584000 "2026-01-01" "https://www.toyota.co.th/en/model-list"
insert_variant "toyota-corolla-altis" "HEV" "เอชอีวี" "toyota-corolla-altis-hev" "HEV"
insert_price "toyota-corolla-altis-hev" 909000 "2026-01-01" "https://www.toyota.co.th/en/model-list"
insert_variant "toyota-corolla-altis" "GR Sport" "จีอาร์" "toyota-corolla-altis-grs" "HEV"
insert_price "toyota-corolla-altis-grs" 1129000 "2026-01-01" "https://www.toyota.co.th/en/model-list"
insert_variant "toyota-camry" "HEV" "เอชอีวี" "toyota-camry-hev" "HEV"
insert_price "toyota-camry-hev" 1475000 "2026-01-01" "https://www.toyota.co.th/en/model-list"
insert_variant "toyota-yaris-cross" "HEV" "เอชอีวี" "toyota-yaris-cross-hev" "HEV"
insert_price "toyota-yaris-cross-hev" 799000 "2026-01-01" "https://www.toyota.co.th/en/model-list"
insert_variant "toyota-corolla-cross" "HEV" "เอชอีวี" "toyota-corolla-cross-hev" "HEV"
insert_price "toyota-corolla-cross-hev" 999000 "2026-01-01" "https://www.toyota.co.th/en/model-list"
insert_variant "toyota-bz4x" "EV" "อีวี" "toyota-bz4x-ev" "BEV"
insert_price "toyota-bz4x-ev" 1299000 "2026-01-01" "https://www.toyota.co.th/en/model-list"
insert_variant "toyota-fortuner" "ICE" "ไอซีอี" "toyota-fortuner-ice" "ICE"
insert_price "toyota-fortuner-ice" 1199000 "2026-01-01" "https://www.toyota.co.th/en/model-list"
insert_variant "toyota-hilux" "ICE" "ไอซีอี" "toyota-hilux-ice" "ICE"
insert_price "toyota-hilux-ice" 699000 "2026-01-01" "https://www.toyota.co.th/en/model-list"
insert_variant "toyota-innova" "HEV" "เอชอีวี" "toyota-innova-hev" "HEV"
insert_price "toyota-innova-hev" 999000 "2026-01-01" "https://www.toyota.co.th/en/model-list"

echo ""
echo "=== Verifying Data ==="
docker exec pgvector psql -U hermes -d thai_car_intelligence -c "
SELECT 
  mfr.\"nameEn\" as manufacturer,
  cm.\"nameEn\" as model,
  COUNT(DISTINCT v.id) as variants,
  MIN(p.amount) as min_price,
  MAX(p.amount) as max_price
FROM \"Manufacturer\" mfr
JOIN \"CarModel\" cm ON cm.\"manufacturerId\" = mfr.id
LEFT JOIN \"Variant\" v ON v.\"modelId\" = cm.id
LEFT JOIN \"Price\" p ON p.\"variantId\" = v.id
GROUP BY mfr.\"nameEn\", cm.\"nameEn\"
ORDER BY mfr.\"nameEn\", min_price;
"

echo ""
echo "=== Seed Complete ==="
