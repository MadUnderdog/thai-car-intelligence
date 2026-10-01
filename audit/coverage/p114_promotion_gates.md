# P114 promotion gates (G1–G8) — committed BEFORE any DB write

- generated: 2026-09-28T14:19:37.754578+00:00 · head: `4da86e63e12f23b04d1f7b1ff61a13dae099b173`
- scope: 417 ACCEPTED packets of 488 frozen (71 quarantined excluded)
- all gates: **PASS**

| gate | status | evidence |
|---|---|---|
| G1_sidecar_sha | PASS | 2136 |
| G2_locator_re_resolution | PASS | 2136 |
| G3_semantics | PASS |  |
| G4_idempotent_rerun | PASS |  |
| G5_contamination | PASS |  |
| G6_sample_reopen | PASS | 11 |
| G7_producer_ne_verifier | PASS | scripts/p114_promote.py |
| G8_gate_report_committed_before_write | PASS | ['audit/coverage/p114_promotion_preflight.json', 'audit/coverage/p114_promotion_gates.json', 'audit/coverage/p114_promotion_gates.md'] |

## Planned DB delta (read-only preflight)
```json
{
  "manufacturers_insert": [
    "Deepal",
    "Jaguar",
    "Land Rover"
  ],
  "models_insert": 127,
  "variants_insert": 404,
  "variants_present_no_action": 13,
  "ambiguous_model_matches": [
    {
      "key": [
        "toyota",
        "yaris ativ"
      ],
      "rows": 2,
      "tie_break": "deterministic: min id"
    },
    {
      "key": [
        "toyota",
        "yaris ativ"
      ],
      "rows": 2,
      "tie_break": "deterministic: min id"
    },
    {
      "key": [
        "toyota",
        "yaris ativ"
      ],
      "rows": 2,
      "tie_break": "deterministic: min id"
    }
  ],
  "sources_insert_hosts": [
    "cdn-jaguarlandrover.com",
    "configurator.porsche.com",
    "www.bmw.co.th",
    "www.gwm.co.th",
    "www.isuzu-tis.com",
    "www.kia.com",
    "www.lexus.co.th",
    "www.mini.co.th",
    "www.porsche.com",
    "www.subaru.asia",
    "www.suzuki.co.th"
  ],
  "source_documents_insert": 122,
  "source_documents_reuse": 0,
  "price_inserts_by_status": {
    "EXACT_CURRENT_MSRP_VERIFIED": 264,
    "MSRP_STARTING_NOT_EXACT": 29,
    "EXACT_BINDING_NOT_VERIFIED_CURRENT": 1
  },
  "spec_inserts_total": 1388,
  "spec_inserts_by_field_key": {
    "seats": 159,
    "displacement_cc": 91,
    "drivetrain": 65,
    "height_mm": 194,
    "length_mm": 273,
    "torque_nm": 126,
    "wheelbase_mm": 134,
    "width_mm": 178,
    "ground_clearance_mm": 58,
    "power_ps": 104,
    "range_km": 6
  },
  "legacy_current_price_demotions": 7,
  "data_change_log_rows_expected": 2223
}
```

## G6 sample rows
- PKT-0001 · Toyota · identity · playwright-chromium+curl · PASS · `https://www.toyota.co.th/en/pricelist`
- PKT-0099 · Honda · identity · playwright-chromium+curl · PASS · `https://www.honda.co.th/en/city`
- PKT-0103 · Changan · identity · playwright-chromium+curl · PASS · `https://www.changan.co.th/th/promotion/`
- PKT-0001 · Toyota · price · playwright-chromium+curl · PASS · `https://www.toyota.co.th/en/pricelist`
- PKT-0099 · Honda · price · playwright-chromium+curl · PASS · `https://www.honda.co.th/en/city`
- PKT-0105 · Jaguar · price · curl+pdftotext · PASS · `https://cdn-jaguarlandrover.com/system/apio/th/TH_Jaguar_PriceSheet.pdf`
- PKT-0106 · Land Rover · price · curl+pdftotext · PASS · `https://cdn-jaguarlandrover.com/system/apio/th/TH_LandRover_PriceSheet.pdf`
- PKT-0001 · Toyota · spec · playwright-chromium+curl · PASS · `https://www.toyota.co.th/en/model/api/car-series/`
- PKT-0168 · Porsche · spec · playwright-chromium+curl · PASS · `https://configurator.porsche.com/en-TH/mode/model/95BBV1`
- PKT-0230 · Lexus · spec · playwright-chromium+curl · PASS · `https://www.lexus.co.th/th/price-and-model-tools/model-brochures.html`
- PKT-0334 · BMW · spec · playwright-chromium · PASS · `https://www.bmw.co.th/th/all-models/m-series/bmw-2-series-m-models/bmw-m2-coupe.html`

No DB write happens until this report is committed (G8). A failing gate blocks promotion — it does not trigger a rewrite.
