# Vehicle Data Staging Dataset

**Generated**: 2026-09-22T18:04:14.695159
**Total Observations**: 1673

## Summary

- **Unique Brands**: 30
- **Unique Models**: 1617
- **Unique Variants**: 65
- **Price Observations**: 85
- **Spec Observations**: 48
- **Unique Source URLs**: 44

## Source Classes

- **STRUCTURED_REF**: 1509
- **OEM_OFFICIAL**: 88
- **MEDIA_DISCOVERY**: 54
- **MARKETPLACE**: 22

## Top Sources

- **Fipe API (Mercedes-Benz)**: 563
- **Fipe API (BMW)**: 323
- **Fipe API (Toyota)**: 222
- **Fipe API (Nissan)**: 200
- **Fipe API (Honda)**: 117
- **HeadLightMag**: 54
- **Toyota Thailand Official**: 35
- **open-ev-data**: 26
- **Fipe API (Mazda)**: 25
- **Fipe API (BYD)**: 22

## Brands Covered

bmw, brand - bmw, byd, chevrolet, fiat, ford, gwm, haval, honda, hyundai, isuzu, kia, lexus, mazda, mercedes-benz, mercedes_benz, mg, mini, mitsubishi, nio, nissan, nissan e.p., porsche, subaru, suzuki, tesla, toyota, volvo, xpeng, zeekr

## File Format

Each line in `vehicle_observations.jsonl` is a JSON object with:
- `observation_id`: Unique identifier
- `timestamp`: When collected
- `source`: Source class, URL, name, precedence, native_id
- `identity`: Brand/model/variant (raw and normalized)
- `price`: Value, type, currency, currentness
- `specs`: Field/value pairs
- `raw_labels`: Original source labels
- `evidence_excerpt`: Text evidence

## Usage

```python
import json

with open('vehicle_observations.jsonl') as f:
    for line in f:
        obs = json.loads(line)
        # Process observation
```

## Notes

- All observations preserve raw labels alongside normalized keys
- Nothing is thrown away — uncertain records are kept for later review
- Source precedence guides ranking, not deletion
- This is staging data — not verified/canonical
