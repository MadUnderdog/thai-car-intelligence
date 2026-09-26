# P100 catalog completeness matrix (20260926)

- in-scope OEMs: **32** · with staged rows: **19**
- MODEL rows: **188** distinct models · **349** distinct variants · **479** staged rows (all ACQUISITION_VERIFIED)

| OEM | rows | models | variants | layers checked | gaps |
|---|---:|---:|---:|---|---|
| Audi | 0 | 0 | 0 | — | no_staged_catalog; layers: lineup_index,model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Avance | 0 | 0 | 0 | — | no_staged_catalog; layers: lineup_index,model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| BMW | 84 | 34 | 49 | lineup_index, price_or_grade_table | 25 models w/o variants; layers: model_page,brochure_pdf,structured_payload,configurator,press_release |
| BYD | 0 | 0 | 0 | — | no_staged_catalog; layers: lineup_index,model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Changan | 4 | 2 | 2 | brochure_pdf, lineup_index, model_page, price_or_grade_table | 1 models w/o variants; layers: structured_payload,configurator,press_release |
| Chery | 0 | 0 | 0 | — | no_staged_catalog; layers: lineup_index,model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Chevrolet | 0 | 0 | 0 | — | no_staged_catalog; layers: lineup_index,model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Deepal | 5 | 5 | 0 | lineup_index, model_page | 5 models w/o variants; layers: price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Ford | 0 | 0 | 0 | — | no_staged_catalog; layers: lineup_index,model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| GWM | 29 | 13 | 17 | brochure_pdf, lineup_index, model_page | 7 models w/o variants; layers: price_or_grade_table,structured_payload,configurator,press_release |
| Haval | 0 | 0 | 0 | — | no_staged_catalog; layers: lineup_index,model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Honda | 42 | 17 | 32 | lineup_index, model_page, price_or_grade_table, structured_payload | 8 models w/o variants; layers: brochure_pdf,configurator,press_release |
| Isuzu | 6 | 6 | 0 | brochure_pdf, lineup_index | 6 models w/o variants; layers: model_page,price_or_grade_table,structured_payload,configurator,press_release |
| Jaguar | 1 | 1 | 1 | brochure_pdf, lineup_index, price_or_grade_table, structured_payload | layers: model_page,configurator,press_release |
| Kia | 3 | 3 | 0 | brochure_pdf, lineup_index | 3 models w/o variants; layers: model_page,price_or_grade_table,structured_payload,configurator,press_release |
| Land Rover | 11 | 4 | 11 | brochure_pdf, lineup_index, price_or_grade_table, structured_payload | layers: model_page,configurator,press_release |
| Lexus | 33 | 10 | 27 | lineup_index, model_page, price_or_grade_table, structured_payload | layers: brochure_pdf,configurator,press_release |
| MG | 7 | 7 | 0 | lineup_index, model_page | 7 models w/o variants; layers: price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| MINI | 5 | 5 | 0 | brochure_pdf, lineup_index, price_or_grade_table | 5 models w/o variants; layers: model_page,structured_payload,configurator,press_release |
| Mazda | 10 | 10 | 0 | lineup_index, model_page | 10 models w/o variants; layers: price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Mercedes-Benz | 0 | 0 | 0 | — | no_staged_catalog; layers: lineup_index,model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Mitsubishi | 25 | 11 | 19 | lineup_index, price_or_grade_table | 3 models w/o variants; layers: model_page,brochure_pdf,structured_payload,configurator,press_release |
| NETA | 0 | 0 | 0 | — | no_staged_catalog; layers: lineup_index,model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Nissan | 33 | 10 | 23 | lineup_index, price_or_grade_table | 1 models w/o variants; layers: model_page,brochure_pdf,structured_payload,configurator,press_release |
| Peugeot | 0 | 0 | 0 | — | no_staged_catalog; layers: lineup_index,model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Porsche | 72 | 6 | 69 | lineup_index, model_page | layers: price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Smart | 0 | 0 | 0 | lineup_index | no_staged_catalog; layers: model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Subaru | 5 | 5 | 0 | lineup_index | 5 models w/o variants; layers: model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Suzuki | 5 | 5 | 0 | brochure_pdf, lineup_index, model_page | 5 models w/o variants; layers: price_or_grade_table,structured_payload,configurator,press_release |
| Tesla | 0 | 0 | 0 | — | no_staged_catalog; layers: lineup_index,model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |
| Toyota | 99 | 34 | 99 | lineup_index, model_page, price_or_grade_table, structured_payload | layers: brochure_pdf,configurator,press_release |
| Volvo | 0 | 0 | 0 | — | no_staged_catalog; layers: lineup_index,model_page,price_or_grade_table,brochure_pdf,structured_payload,configurator,press_release |

## gaps and reasons

- **Audi** / no_staged_catalog: access_status=BLOCKED_HTTP_403; blocker={"checked_at": "2026-09-24T13:41:32.369118+00:00", "http_status_or_error": "HTTP_403", "url": "https://www.audi.co.th/"}
- **Audi** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Avance** / no_staged_catalog: access_status=BLOCKED_DNS; blocker={"checked_at": "2026-09-24T13:41:33.586368+00:00", "http_status_or_error": "ConnectionError: HTTPSConnectionPool(host='www.avancemotors.com', port=443): Max retries exceeded with url: / (Caused by NameResolutionError(\"HTTPSConnection(host='www.avancemot", "url": "https://www.avancemotors.com/"}
- **Avance** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **BMW** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: lineup_index, price_or_grade_table — Convertible 4 series, Coupé 2 series, Coupé 4 series, Coupé M2, Coupé M4, Roadster Z4, SAC X4, SAC X6
- **BMW** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **BYD** / no_staged_catalog: access_status=BLOCKED_HTTP_404; blocker={"checked_at": "2026-09-24T13:41:31.848172+00:00", "http_status_or_error": "HTTP_404", "url": "https://www.byd.com/th/"}
- **BYD** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Changan** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: brochure_pdf, lineup_index, model_page, price_or_grade_table — Lumin L DC
- **Changan** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Chery** / no_staged_catalog: access_status=BLOCKED_DNS; blocker={"checked_at": "2026-09-24T13:41:33.757563+00:00", "http_status_or_error": "ConnectionError: HTTPSConnectionPool(host='www.chery.co.th', port=443): Max retries exceeded with url: / (Caused by NameResolutionError(\"HTTPSConnection(host='www.chery.co.th', ", "url": "https://www.chery.co.th/"}
- **Chery** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Chevrolet** / no_staged_catalog: access_status=BLOCKED_HTTP_403; blocker={"checked_at": "2026-09-24T14:16:16.748942+00:00", "http_status_or_error": "HTTP_403 via Playwright (requests GET earlier returned 200 — browser-level block)", "url": "https://www.chevrolet.co.th/"}
- **Chevrolet** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Deepal** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: lineup_index, model_page — e07-plus, hunter-k50, s05, s05-reev, s07
- **Deepal** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Ford** / no_staged_catalog: access_status=BLOCKED_HTTP_403; blocker={"checked_at": "2026-09-24T13:41:32.087860+00:00", "http_status_or_error": "HTTP_403", "url": "https://www.ford.co.th/"}
- **Ford** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **GWM** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: brochure_pdf, lineup_index, model_page — GWM POER SAHAR DIESEL, ORA 5 EV, ORA 5 HEV, POER 2.4T PRO, TANK 300 LIMITED, TANK 500 3.0T DIESEL, WEY G9
- **GWM** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Haval** / no_staged_catalog: access_status=BLOCKED_DNS; blocker={"checked_at": "2026-09-24T13:41:33.654558+00:00", "http_status_or_error": "ConnectionError: HTTPSConnectionPool(host='www.haval.co.th', port=443): Max retries exceeded with url: / (Caused by NameResolutionError(\"HTTPSConnection(host='www.haval.co.th', ", "url": "https://www.haval.co.th/"}
- **Haval** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Honda** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: lineup_index, model_page, price_or_grade_table, structured_payload — Civic Type R, HEV, N1, N2, ONE, Super-ONE, e:N1, e:N2
- **Honda** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Isuzu** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: brochure_pdf, lineup_index — MU-X, NEW ISUZU D-MAX HI-LANDER, NEW ISUZU D-MAX SPACECAB, NEW ISUZU D-MAX SPARK, NEW ISUZU V-CROSS 4x4, X-SERIES
- **Isuzu** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Jaguar** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Kia** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: brochure_pdf, lineup_index — The Kia Carnival Diesel SXL, The Kia EV5, The Kia Sorento PHEV
- **Kia** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Land Rover** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Lexus** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **MG** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: lineup_index, model_page — MG HS PHEV, MG MAXUS 7, MG MAXUS 9, MG Urban, MG ZS, MG4, MGS5 EV PLUS
- **MG** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **MINI** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: brochure_pdf, lineup_index, price_or_grade_table — ALL-ELECTRIC MINI ACEMAN, ALL-ELECTRIC MINI COOPER, JOHN COOPER WORKS, MINI COUNTRYMAN, MINI Cooper Convertible
- **MINI** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Mazda** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: lineup_index, model_page — MAZDA CX-8, MAZDA3 FASTBACK, MAZDA3 SEDAN, MAZDA6 20TH ANNIVERSARY EDITION, NEW MAZDA BT-50, NEW MAZDA CX-3 ESSENTIAL, NEW MAZDA CX-30 ESSENTIAL, NEW MAZDA CX-5
- **Mazda** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Mercedes-Benz** / no_staged_catalog: access_status=BLOCKED_HTTP_403; blocker={"checked_at": "2026-09-24T14:16:16.748942+00:00", "http_status_or_error": "HTTP_403 via Playwright (probe was BLOCKED_TIMEOUT — browser-level block)", "url": "https://www.mercedes-benz.co.th/"}
- **Mercedes-Benz** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Mitsubishi** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: lineup_index, price_or_grade_table — เอ็กซ์แพนเดอร์ ครอส เอชอีวี, เอ็กซ์แพนเดอร์ เอชอีวี, ไทรทัน
- **Mitsubishi** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **NETA** / no_staged_catalog: access_status=BLOCKED_DNS; blocker={"checked_at": "2026-09-24T13:41:33.300875+00:00", "http_status_or_error": "ConnectionError: HTTPSConnectionPool(host='www.neta.co.th', port=443): Max retries exceeded with url: / (Caused by NameResolutionError(\"HTTPSConnection(host='www.neta.co.th', po", "url": "https://www.neta.co.th/"}
- **NETA** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Nissan** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: lineup_index, price_or_grade_table — นิสสัน เทอร์ร่า
- **Nissan** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Peugeot** / no_staged_catalog: access_status=BLOCKED_HTTP_403; blocker={"checked_at": "2026-09-24T13:41:35.062412+00:00", "http_status_or_error": "HTTP_403", "url": "https://www.peugeot.co.th/"}
- **Peugeot** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Porsche** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Smart** / no_staged_catalog: access_status=DEALER_REDIRECT; blocker={"checked_at": "2026-09-25T14:16:39.761675+00:00", "http_status_or_error": "REDIRECT_TO_UNRELATED_DOMAIN: https://www.smartsecurity.in.th/ (HTTP 200) — unchanged since 2026-09-24; body sha256 e99e6e9a09a9f52c…; URL-decision evidence in audit/coverage/smart-url-decision-20260925/", "url": "https://www.smart.co.th/"}
- **Smart** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Subaru** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: lineup_index — ALL NEW FORESTER, BRZ, CROSSTREK, WRX, WRX WAGON
- **Subaru** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Suzuki** / models_without_published_variant_rows: no first-party grade/trim layer captured for these models in this cycle — checked layers: brochure_pdf, lineup_index, model_page — ALL NEW SUZUKI FRONX, ALL NEW SUZUKI e VITARA, CARRY, JIMNY, XL7 HYBRID
- **Suzuki** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Tesla** / no_staged_catalog: access_status=BLOCKED_HTTP_403; blocker={"checked_at": "2026-09-24T13:41:32.086082+00:00", "http_status_or_error": "HTTP_403", "url": "https://www.tesla.com/th_th"}
- **Tesla** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Toyota** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
- **Volvo** / no_staged_catalog: access_status=BLOCKED_TLS; blocker={"checked_at": "2026-09-24T13:41:32.815537+00:00", "http_status_or_error": "SSLError: HTTPSConnectionPool(host='www.volvo.co.th', port=443): Max retries exceeded with url: /en/models.html (Caused by SSLErro", "url": "https://www.volvo.co.th/en/models.html"}
- **Volvo** / layers_not_checked: not present in captured official artifacts / not discovered by Pass C traversal this cycle
