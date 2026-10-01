# Vehicle Data Staging Dataset

**Generated**: 2024-09-22 (from actual rows)
**Total raw observations**: 1,679

## Separate Counts

### Identity
- **Brands**: 27
- **Model candidates**: 1,599 (normalized brand:model pairs)
- **Variant candidates**: 173 (normalized brand:model:variant triples)
- **Identity levels**:
  - VARIANT: 174 (OEM official prices with exact variant)
  - MODEL_OR_TRIM_UNKNOWN: 1,483 (Fipe API — model or trim level unknown)
  - BRAND_ONLY: 22 (Thai reference — make only, no model)
- **Unknown/conflicted identities**: 1,505

### Value Data
- **Price observations**: 148 (OEM official variant MSRP)
- **Spec observations**: 0 (pending next collection)

### Sources
- **Unique source URLs**: 1,524
- **By class**:
  - OEM_OFFICIAL: 148 (Toyota/Honda/BYD/MG/Nissan/Mazda/Mitsubishi/Haval/Ford/Isuzu/Suzuki/Tesla/BMW/Mercedes-Benz)
  - STRUCTURED_REF: 1,509 (Fipe API + open-ev-data)
  - MARKET_REFERENCE: 22 (Thai market knowledge base)

## Source Precedence
- OEM_OFFICIAL: 100
- GOVERNMENT_DLT: 95
- STRUCTURED_REF: 80
- MEDIA_DISCOVERY: 60
- MARKET_REFERENCE: 50
- MARKETPLACE: 40
- USER_CONTRIBUTED: 20

## File Format

Each line in `vehicle_observations.jsonl` is a JSON object with:
- `observation_id`: Unique identifier
- `timestamp`: When collected
- `source`: Source class, URL, name, precedence, native_id
- `identity`: Brand/model/variant (raw and normalized), identity_level
- `price`: Value, type, currency, currentness
- `specs`: Field/value pairs
- `raw_labels`: Original source labels
- `evidence_excerpt`: Text evidence

## Notes

- All observations preserve raw labels alongside normalized keys
- Fipe rows marked as MODEL_OR_TRIM_UNKNOWN (not assumed models)
- Thai Reference is MARKET_REFERENCE (not marketplace)
- Price currentness is UNKNOWN unless source evidence establishes currentness
- Nothing is thrown away — uncertain records kept for review
