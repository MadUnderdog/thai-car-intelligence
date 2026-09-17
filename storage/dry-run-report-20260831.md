# Thai Car Intelligence — Dry-Run Source Check Report

**Date:** 2026-08-31 09:08 ICT  
**Type:** Dry-run (no published data modified)  
**Script:** `scripts/dry-run-source-check.py`  
**Results JSON:** `storage/dry-run-source-check-latest.json`

---

## Summary

| Metric | Count |
|--------|-------|
| Total URLs checked | 32 |
| Accessible | 29 (90.6%) |
| Inaccessible | 3 (9.4%) |
| Published data modified | **NO** |

## Database Snapshot

| Table | Rows |
|-------|------|
| Manufacturer | 13 |
| CarModel | 72 |
| Variant | 74 |
| Source | 13 (all ACTIVE) |
| SourceDocument | 19 |
| Price | 79 |

---

## ❌ INACCESSIBLE SOURCES

### 1. Isuzu Thailand — `isuzu-taz.com` (DNS Failure)

- **Status:** Domain completely unreachable (DNS resolution fails)
- **Impact:** 2 URLs affected (Source.baseUrl + SourceDocument.url)
- **Root cause:** `isuzu-taz.com` domain appears expired/deprecated
- **Replacement:** Isuzu Thailand has moved to:
  - `https://www.isuzu-tis.com` (active, HTTP 200) — primary dealer/sales site
  - `https://www.isuzu.co.th` (active, HTTP 200) — corporate site
- **Recommended action:** Update Source.baseUrl to `https://www.isuzu-tis.com` and SourceDocument.url accordingly. Verify correct URL for price list data.

### 2. Honda Thailand — Intermittent HTTP 500

- **Status:** `honda.co.th` base URL returns 200, but document URL (same URL + trailing slash) initially returned HTTP 500
- **Impact:** 1 SourceDocument URL
- **Root cause:** Server-side issue; re-check with standard browser User-Agent returns 200. Likely rate-limits or blocks non-standard User-Agents.
- **Recommended action:** Monitor. Consider using browser adapter for Honda data.

---

## ⚠️ NOTABLE EDGE CASES (Reachable but Non-Standard)

### 3. Tesla Thailand — HTTP 403 (Bot Protection)

- **Status:** Both URLs return HTTP 403 Forbidden
- **Impact:** 2 URLs (Source.baseUrl + SourceDocument.url)
- **Root cause:** Tesla.com blocks non-browser User-Agents. Server IS reachable.
- **Recommended action:** Use browser adapter for Tesla scraping. No source URL change needed.

### 4. Suzuki Thailand — Redirect to Error Page

- **Status:** `suzuki.co.th/th` redirects to `suzuki.co.th/error` (HTTP 200)
- **Impact:** 1 SourceDocument URL
- **Root cause:** The `/th` path doesn't exist on Suzuki's site. The base URL `suzuki.co.th` works correctly.
- **Recommended action:** Update SourceDocument.url from `suzuki.co.th/th` to `suzuki.co.th`.

---

## 🔄 REDIRECT CHAINS

Several manufacturer base URLs redirect to Thai-localized pages:

| Source | Original URL | Redirects To |
|--------|-------------|--------------|
| Hyundai | hyundai.com | hyundai.com/th/th |
| Kia | kia.com | kia.com/th/th |
| Mazda | mazda.co.th | mazda.co.th/th |
| MG | mgcars.com | mgcars.com/th |
| Mitsubishi | mitsubishi-motors.co.th | mitsubishi-motors.co.th/th?rd=true |

These redirects are functional (all return 200) but indicate the `Source.baseUrl` stores the pre-redirect URL. Consider updating to the final Thai URLs for consistency.

---

## 🌐 Domain Accessibility Matrix

| Domain | URLs | Accessible | Status |
|--------|------|------------|--------|
| www.ford.co.th | 2 | 2/2 | ✅ |
| www.honda.co.th | 2 | 1/2 | ⚠️ Intermittent |
| www.hyundai.com | 2 | 2/2 | ✅ |
| www.isuzu-taz.com | 2 | 0/2 | ❌ DNS failure |
| www.kia.com | 2 | 2/2 | ✅ |
| www.mazda.co.th | 2 | 2/2 | ✅ |
| www.mgcars.com | 6 | 6/6 | ✅ |
| www.mitsubishi-motors.co.th | 2 | 2/2 | ✅ |
| www.nissan.co.th | 2 | 2/2 | ✅ |
| www.reverautomotive.com | 3 | 3/3 | ✅ |
| www.suzuki.co.th | 2 | 2/2 | ✅ (1 redirects to /error) |
| www.tesla.com | 2 | 2/2 | ✅ (403 but reachable) |
| www.toyota.co.th | 3 | 3/3 | ✅ |

---

## ⏱️ Performance

| Metric | Value |
|--------|-------|
| Average response time | 720ms |
| Min | 8ms (Isuzu DNS fail) |
| Max | 4,205ms (MG ZS EV page) |
| Timeout (12s) | 0 |

---

## Recommended Actions (Priority Order)

1. **[CRITICAL]** Update Isuzu Thailand source URLs from `isuzu-taz.com` to `isuzu-tis.com`
2. **[HIGH]** Update Suzuki SourceDocument URL from `suzuki.co.th/th` to `suzuki.co.th`
3. **[MEDIUM]** Update 5 manufacturer Source.baseUrls to Thai-localized final URLs
4. **[LOW]** Monitor Honda.co.th for intermittent 500 errors; configure browser adapter for Tesla

---

*No published data was modified during this dry-run. All results saved to `storage/`.*
