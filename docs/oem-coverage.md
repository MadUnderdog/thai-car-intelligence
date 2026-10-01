# OEM Coverage View

> GENERATED from `audit/coverage/oem-registry.json` by `scripts/generate_coverage_view.py` — do not edit by hand.
> Generated at: 2026-09-25T14:17:01.004115+00:00

## Coverage

```text
coverage = brands(ACQUISITION_VERIFIED AND PARSED_TESTED) / in_scope
         = 19 / 32 = 59.4%
```

- Verified + parsed-tested brands: Toyota, Honda, Nissan, Mazda, Mitsubishi, Isuzu, Suzuki, MG, BMW, Subaru, Porsche, Lexus, Deepal, Changan, GWM, Jaguar, Land Rover, MINI, Kia
- Currently reachable endpoints: 19 / 32
- Blocked endpoints: 13 / 32
- Scope candidates unresolved: 2

> Attempt, capture and blocked counts are **operational telemetry, never market coverage** (§93).

## Brands

| Brand | In scope | Access | Adapter | Provenance | Last success (data) | Next retry |
|---|---|---|---|---|---|---|
| Toyota | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| Honda | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-25 | 2026-09-25 |
| Nissan | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| Mazda | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| Mitsubishi | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| Isuzu | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| Suzuki | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| MG | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| BYD | yes | ⛔ `BLOCKED_HTTP_404` | NONE | NONE | — | 2026-10-08 |
| Tesla | yes | ⛔ `BLOCKED_HTTP_403` | NONE | NONE | — | 2026-10-01 |
| Ford | yes | ⛔ `BLOCKED_HTTP_403` | NONE | NONE | — | 2026-10-01 |
| Chevrolet | yes | ⛔ `BLOCKED_HTTP_403` | NONE | NONE | — | 2026-10-01 |
| Mercedes-Benz | yes | ⛔ `BLOCKED_HTTP_403` | NONE | NONE | — | 2026-10-01 |
| Audi | yes | ⛔ `BLOCKED_HTTP_403` | NONE | NONE | — | 2026-10-01 |
| BMW | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| Volvo | yes | ⛔ `BLOCKED_TLS` | NONE | NONE | — | 2026-10-24 |
| Subaru | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-25 | 2026-10-01 |
| Porsche | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| Lexus | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| NETA | yes | ⛔ `BLOCKED_DNS` | NONE | NONE | — | 2026-10-01 |
| Deepal | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-10-01 |
| Avance | yes | ⛔ `BLOCKED_DNS` | NONE | NONE | — | 2026-10-01 |
| Changan | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| GWM | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-25 | 2026-09-25 |
| Haval | yes | ⛔ `BLOCKED_DNS` | NONE | NONE | — | 2026-10-01 |
| Chery | yes | ⛔ `BLOCKED_DNS` | NONE | NONE | — | 2026-10-01 |
| Jaguar | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| Land Rover | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| MINI | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| Smart | yes | ⚠️ `DEALER_REDIRECT` | NONE | NONE | — | 2026-09-26 |
| Kia | yes | 🟢 `REACHABLE` | PARSED_TESTED | ACQUISITION_VERIFIED | 2026-09-24 | 2026-09-25 |
| Peugeot | yes | ⛔ `BLOCKED_HTTP_403` | NONE | NONE | — | 2026-10-01 |
| Perodua | no | ❓ `UNKNOWN` | NONE | NONE | — | — |

## Blocked — evidence

- **BYD** `BLOCKED_HTTP_404` — HTTP_404 at <https://www.byd.com/th/> (checked 2026-09-24T13:41:31Z); retry 2026-10-08
- **Tesla** `BLOCKED_HTTP_403` — HTTP_403 at <https://www.tesla.com/th_th> (checked 2026-09-24T13:41:32Z); retry 2026-10-01
- **Ford** `BLOCKED_HTTP_403` — HTTP_403 at <https://www.ford.co.th/> (checked 2026-09-24T13:41:32Z); retry 2026-10-01
- **Chevrolet** `BLOCKED_HTTP_403` — HTTP_403 via Playwright (requests GET earlier returned 200 — browser-level block) at <https://www.chevrolet.co.th/> (checked 2026-09-24T14:16:16Z); retry 2026-10-01
  - ladder: BLOCKED_HTTP_403 — probe=REACHABLE; acquisition attempt → HTTP_403 via Playwright (requests GET earlier returned 200 — browser-level block) at <https://www.chevrolet.co.th/> (2026-09-24T14:16:16)
- **Mercedes-Benz** `BLOCKED_HTTP_403` — HTTP_403 via Playwright (probe was BLOCKED_TIMEOUT — browser-level block) at <https://www.mercedes-benz.co.th/> (checked 2026-09-24T14:16:16Z); retry 2026-10-01
  - ladder: BLOCKED_HTTP_403 — probe=BLOCKED_TIMEOUT; acquisition attempt → HTTP_403 via Playwright (probe was BLOCKED_TIMEOUT — browser-level block) at <https://www.mercedes-benz.co.th/> (2026-09-24T14:16:16)
- **Audi** `BLOCKED_HTTP_403` — HTTP_403 at <https://www.audi.co.th/> (checked 2026-09-24T13:41:32Z); retry 2026-10-01
- **Volvo** `BLOCKED_TLS` — SSLError: HTTPSConnectionPool(host='www.volvo.co.th', port=443): Max retries exceeded with url: /en/models.html (Caused by SSLErro at <https://www.volvo.co.th/en/models.html> (checked 2026-09-24T13:41:32Z); retry 2026-10-24
- **NETA** `BLOCKED_DNS` — ConnectionError: HTTPSConnectionPool(host='www.neta.co.th', port=443): Max retries exceeded with url: / (Caused by NameResolutionError("HTTPSConnection(host='www.neta.co.th', po at <https://www.neta.co.th/> (checked 2026-09-24T13:41:33Z); retry 2026-10-01
- **Avance** `BLOCKED_DNS` — ConnectionError: HTTPSConnectionPool(host='www.avancemotors.com', port=443): Max retries exceeded with url: / (Caused by NameResolutionError("HTTPSConnection(host='www.avancemot at <https://www.avancemotors.com/> (checked 2026-09-24T13:41:33Z); retry 2026-10-01
- **Haval** `BLOCKED_DNS` — ConnectionError: HTTPSConnectionPool(host='www.haval.co.th', port=443): Max retries exceeded with url: / (Caused by NameResolutionError("HTTPSConnection(host='www.haval.co.th',  at <https://www.haval.co.th/> (checked 2026-09-24T13:41:33Z); retry 2026-10-01
- **Chery** `BLOCKED_DNS` — ConnectionError: HTTPSConnectionPool(host='www.chery.co.th', port=443): Max retries exceeded with url: / (Caused by NameResolutionError("HTTPSConnection(host='www.chery.co.th',  at <https://www.chery.co.th/> (checked 2026-09-24T13:41:33Z); retry 2026-10-01
  - ladder: NO_PRICE_EVIDENCE — HTTP_200 (host resolves; page footer '© Copyright 2025 Chery(Thailand).All Right Reserved.'; 0 published price figures on / , /models/tiggo8 and /models/chery-q — raw and Chromium-rendered) at <https://www.chery-thailand.com/> (2026-09-25T13:49:52)
- **Smart** `DEALER_REDIRECT` — REDIRECT_TO_UNRELATED_DOMAIN: https://www.smartsecurity.in.th/ (HTTP 200) — unchanged since 2026-09-24; body sha256 e99e6e9a09a9f52c…; URL-decision evidence in audit/coverage/smart-url-decision-20260925/ at <https://www.smart.co.th/> (checked 2026-09-25T14:16:39Z); retry 2026-09-26
- **Peugeot** `BLOCKED_HTTP_403` — HTTP_403 at <https://www.peugeot.co.th/> (checked 2026-09-24T13:41:35Z); retry 2026-10-01

## Scope candidates — unresolved

- **Hyundai** — hyundai.co.th DNS not resolved in probe; official Thai sales presence not confirmed (evidence: BLOCKED_DNS)
- **Daihatsu** — daihatsu.co.th DNS not resolved in probe; passenger-vehicle sales presence unconfirmed (evidence: BLOCKED_DNS)

## Captured artifacts (brand → endpoints)

- **Toyota**
  - `toyota_model_page.html` ← https://www.toyota.co.th/model-list · ACQUISITION_VERIFIED · unparsed · 258b3015796f
  - `toyota_page.html` ← https://www.toyota.co.th/pricelist · LEGACY_UNVERIFIED · parsed · c25bf262437a
  - `toyota_pricelist_page.html` ← https://www.toyota.co.th/en/pricelist · ACQUISITION_VERIFIED · parsed · 5d0ba584bcc3
- **Honda**
  - `honda_models_page.html` ← https://www.honda.co.th/models · ACQUISITION_VERIFIED · parsed · 6eb120085da1
  - `honda_city_page.html` ← https://www.honda.co.th/en/city · LEGACY_UNVERIFIED · unparsed · 8d11ebd4f720
  - `honda_city_recapture.html` ← https://www.honda.co.th/en/city · ACQUISITION_VERIFIED · parsed · 1953984e5b3b
- **Nissan**
  - `nissan_page.html` ← https://www.nissan-thailand.com · LEGACY_UNVERIFIED · parsed · 861be1b78785
  - `nissan_new_home_page.html` ← https://www.nissan.co.th/ · ACQUISITION_VERIFIED · parsed · cec34588e44f
- **Mazda**
  - `mazda_page.html` ← https://www.mazda.co.th/en/vehicles · LEGACY_UNVERIFIED · unparsed · cd8ca9667ce5
  - `mazda_home_page.html` ← https://www.mazda.co.th/th · ACQUISITION_VERIFIED · parsed · 3e49287146ee
- **Mitsubishi**
  - `mitsubishi_home_page.html` ← https://www.mitsubishi-motors.co.th/th?rd=true · ACQUISITION_VERIFIED · parsed · eaa2b0f9e01f
- **Isuzu**
  - `isuzu_page.html` ← https://www.isuzu.com · LEGACY_UNVERIFIED · parsed · e9d00350296d
  - `isuzu_th_home_page.html` ← https://www.isuzu.co.th/ · ACQUISITION_VERIFIED · unparsed · 5d27fa1ffd76
  - `isuzu_th_rendered_page.html` ← https://www.isuzu.co.th/ · ACQUISITION_VERIFIED · unparsed · 7f7956308b83
  - `isuzu_tis_page.html` ← https://www.isuzu-tis.com/ · ACQUISITION_VERIFIED · parsed · 313163cf3f44
- **Suzuki**
  - `suzuki_models_page.html` ← https://www.suzuki.co.th/error · ACQUISITION_VERIFIED · unparsed · c22e9bcffbec
  - `suzuki_home_page.html` ← https://www.suzuki.co.th/ · ACQUISITION_VERIFIED · parsed · 2b9c4cc94730
- **MG**
  - `mg_models_page.html` ← https://www.jnt.co.th/ · ACQUISITION_VERIFIED · unparsed · b502e443cf65
  - `mg_home_page.html` ← https://www.mgcars.com/th · ACQUISITION_VERIFIED · parsed · ee75dda64330
- **BMW**
  - `bmw_models_page.html` ← https://www.bmw.co.th/en/all-models.html · LEGACY_UNVERIFIED · parsed · 14df12365814
  - `bmw_all_models_verified.html` ← https://www.bmw.co.th/en/all-models.html · ACQUISITION_VERIFIED · parsed · 6b88cd605511
- **Subaru**
  - `subaru_th_home_page.html` ← https://www.subaru.asia/th/th/ · ACQUISITION_VERIFIED · parsed · 7626c14f97a7
- **Porsche**
  - `porsche_home_page.html` ← https://www.porsche.com/pap/_thailand_/ · ACQUISITION_VERIFIED · unparsed · e7a53c39351f
  - `porsche_macan_model_page.html` ← https://www.porsche.com/pap/_thailand_/models/macan/#modelRangeId=macan · ACQUISITION_VERIFIED · parsed · 7e0630709119
- **Lexus**
  - `lexus_models_page.html` ← https://www.lexus.co.th/th.html · ACQUISITION_VERIFIED · parsed · be1f5d866979
- **Deepal**
  - `changan_home_page.html` ← https://www.changan.co.th/th/ · ACQUISITION_VERIFIED · parsed · 28c9f50b8623
- **Changan**
  - `changan_home_page.html` ← https://www.changan.co.th/th/ · ACQUISITION_VERIFIED · unparsed · 28c9f50b8623
  - `changan_nevo_q05_page.html` ← https://www.changan.co.th/th/nevo-q05/ · ACQUISITION_VERIFIED · parsed · b7cb2be2088c
  - `changan_lumin_page.html` ← https://www.changan.co.th/th/lumin/luminl-dc-th/ · ACQUISITION_VERIFIED · parsed · 8d84d5f80f5e
  - `changan_promotion_page.html` ← https://www.changan.co.th/th/promotion/ · ACQUISITION_VERIFIED · parsed · d1f57ae37d4d
- **GWM**
  - `gwm_home_page.html` ← https://www.gwm.co.th/en · ACQUISITION_VERIFIED · unparsed · c311d963f280
  - `gwm_models_page.html` ← https://www.gwm.co.th/en/models · ACQUISITION_VERIFIED · unparsed · e7a9070ab8c8
  - `gwm_data_models_page.html` ← https://www.gwm.co.th/en/gwm-data-car-models · ACQUISITION_VERIFIED · unparsed · d09dec4fa516
  - `gwm_mall_home.html` ← https://mall.gwm.co.th/ · ACQUISITION_VERIFIED · unparsed · 1fcace8cd759
  - `gwm_th_model_haval-h6.html` ← https://www.gwm.co.th/th/models/haval-h6 · ACQUISITION_VERIFIED · parsed · 236ada0f0db7
  - `gwm_th_model_ora-5-ev.html` ← https://www.gwm.co.th/th/models/ora-5-ev · ACQUISITION_VERIFIED · parsed · 6ca2b21a3d84
  - `gwm_th_model_ora-5-hev.html` ← https://www.gwm.co.th/th/models/ora-5-hev · ACQUISITION_VERIFIED · parsed · 8182d7d5c3e1
  - `gwm_th_model_poer.html` ← https://www.gwm.co.th/th/models/poer · ACQUISITION_VERIFIED · parsed · f83c07e4ff58
  - `gwm_th_model_sahar-diesel.html` ← https://www.gwm.co.th/th/models/sahar-diesel · ACQUISITION_VERIFIED · parsed · 662b719e379f
  - `gwm_th_model_sahar.html` ← https://www.gwm.co.th/th/models/sahar · ACQUISITION_VERIFIED · parsed · b1bdea00126f
  - `gwm_th_model_tank-300-diesel.html` ← https://www.gwm.co.th/th/models/tank-300-diesel · ACQUISITION_VERIFIED · parsed · a54714afc4fd
  - `gwm_th_model_tank-300-limited-lb.html` ← https://www.gwm.co.th/th/models/tank-300-limited-lb · ACQUISITION_VERIFIED · parsed · 3e458640a5c1
  - `gwm_th_model_tank-300.html` ← https://www.gwm.co.th/th/models/tank-300 · ACQUISITION_VERIFIED · parsed · c1d3072c46c5
  - `gwm_th_model_tank-500-3t-diesel.html` ← https://www.gwm.co.th/th/models/tank-500-3t-diesel · ACQUISITION_VERIFIED · parsed · a47b4c5ddac3
  - `gwm_th_model_tank-500-diesel.html` ← https://www.gwm.co.th/th/models/tank-500-diesel · ACQUISITION_VERIFIED · parsed · 434bb47d8536
  - `gwm_th_model_tank-500.html` ← https://www.gwm.co.th/th/models/tank-500 · ACQUISITION_VERIFIED · parsed · 409b6ea36511
  - `gwm_th_model_wey-g9.html` ← https://www.gwm.co.th/th/models/wey-g9 · ACQUISITION_VERIFIED · parsed · 23c92f204509
- **Jaguar**
  - `jaguar_home_page.html` ← https://www.jaguar.co.th/ · ACQUISITION_VERIFIED · unparsed · 05d97f701cf4
  - `jaguar_range_page.html` ← https://www.jaguar.co.th/jaguar-range/overview · ACQUISITION_VERIFIED · unparsed · 12ad7deb8700
  - `TH_Jaguar_PriceSheet.pdf.b64` ← https://cdn-jaguarlandrover.com/system/apio/th/TH_Jaguar_PriceSheet.pdf · ACQUISITION_VERIFIED · parsed · 9806c8ba7068
- **Land Rover**
  - `landrover_home_page.html` ← https://www.landrover.co.th/ · ACQUISITION_VERIFIED · unparsed · e82a21773190
  - `landrover_discovery_page.html` ← https://www.landrover.co.th/discovery/overview · ACQUISITION_VERIFIED · unparsed · 660b8fa629d4
  - `landrover_range_rover_page.html` ← https://www.landrover.co.th/range-rover/overview · ACQUISITION_VERIFIED · unparsed · aa02b1b04953
  - `TH_LandRover_PriceSheet.pdf.b64` ← https://cdn-jaguarlandrover.com/system/apio/th/TH_LandRover_PriceSheet.pdf · ACQUISITION_VERIFIED · parsed · 38497d2d7377
- **MINI**
  - `mini_home_page.html` ← https://www.mini.co.th/en_TH/home.html · ACQUISITION_VERIFIED · parsed · b662bd5b0cca
- **Smart**
  - `smart_home_page.html` ← https://www.smartsecurity.in.th/ · ACQUISITION_VERIFIED · unparsed · 503b08966576
- **Kia**
  - `kia_home_page.html` ← https://www.kia.com/th/th · ACQUISITION_VERIFIED · unparsed · 53e94ea876b4
  - `kia_cars_page.html` ← https://www.kia.com/th/th · ACQUISITION_VERIFIED · parsed · d068ec29fcbe
