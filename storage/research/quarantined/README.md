# Quarantined Research Artifacts

## nissan-full-price-json.json
**Reason**: Cross-contamination bug. The extraction script treated ALL prices
from the Nissan navigation menu JSON as belonging to the current model page.
Each price actually belongs to its specific model key in the JSON, not the
page URL.

**Impact**: March received Terra/Navara/Kicks/Leaf prices. X-Trail received
March prices. Leaf received Almera/March prices. test GT-R price 13,500,000
appeared in unrelated model data.

**Status**: Quarantined on 2026-09-19. DB prices were audited and corrected.
Serena V price fixed from 1,339,000 (Teana) to 1,469,000 (correct).
Livina E price fixed from 667,000 (outdated) to 672,000 (current).

**Lesson**: Never flatten all modelPrice values from a shared JSON. Each price
must be linked to its specific model key before extraction.

## nissan-trim-prices.json
**Reason**: Same cross-contamination bug. Extracted 340 "unique" trim prices
but most were from navigation menu, not model-specific data.

**Status**: Quarantined on 2026-09-19.

## DO NOT USE THESE FILES AS EVIDENCE
These files are preserved for debugging only. They must never be consumed
by production or research import code.
