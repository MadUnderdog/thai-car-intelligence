# Golden Run Artifact

One real article: AutoLifeThailand Wuling EKSION EV

## Results
- Total time: 236.5s
- Stage A: ~53s (document mapping)
- Stage B: ~197s (field extraction)
- Accepted: 9 observations
- Rejected: 0
- Needs review: 0

## Evidence Chains
Each observation has:
- block_id: references a specific content block
- evidence_quote: exact substring of block content
- entity: brand + model (Wuling/EKSION EV)
- field: price, engine_l, horsepower_hp, etc.
- fingerprint: deterministic dedup hash

## Reproduction
```bash
python3 audit/golden-run/reproduce.py
```
