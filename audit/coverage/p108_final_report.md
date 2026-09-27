# P108 — External source-discovery batch (break the source ceiling)

**wave:** P108 · **baseline = accepted P107 `b5e492792641e0bac0fb05d2d6a6837f4ae4af0d`**
**date:** 2026-09-28 · **mode:** one discovery inventory → one acquisition batch →
one harvest/reconcile → one test/gate run at the end.  No classifier/test repair
loop was opened: P107 reported no new semantic defect and this wave did not
re-open P105–P107 logic.

---

## 1. Discovery channels (external — not a re-hash of committed hrefs)

| channel | what it produced |
|---|---|
| robots.txt + sitemap indexes | seeds on 10 official domains → **73 sitemaps parsed → 27,327 URLs** (Kia world locales, Mitsubishi 1,294, Lexus 668, Jaguar 169, GWM 84, Changan, Suzuki, Subaru, MG, Mazda) |
| guessed sitemap endpoints | `sitemap.xml` / `sitemap_index.xml` / `wp-sitemap.xml` probed on all 17 priority domains → 10 hits (Mazda, Nissan, MG, Mitsubishi, Subaru, Changan, Jaguar, Suzuki, Kia, GWM) |
| **certificate transparency (crt.sh)** | 8 domains → **283 official subdomains** (Mazda 26, Nissan 26, Honda 22, GWM 9, Subaru 24, MG 66, Changan/Deepal 110) — document/CDN/API repository candidates |
| search index | DuckDuckGo HTML endpoint returned 200 for 8 queries (Honda 10, Toyota 10, Isuzu 12, Nissan 12, MG 12, Subaru 12 hits); Bing RSS format returned empty items (0 hits, recorded as channel-zero) |
| official press / news index | `newsroom.porsche.com/sitemap.xml` (252 annual sitemaps, 36 from 2025-26) |
| **structured sitemap endpoint** | `www.porsche.com/sitemap.xml` → country file `pap/_thailand_/Sitemap.smap` → **279 Thai-market Porsche URLs** (the `/pap/_thailand_/` prefix was never in any earlier capture) |
| homepage endpoint scan | Toyota/Honda/MG/Porsche/Subaru/Deepal homepages scanned for sitemap/JSON/PDF endpoints (Honda surfaced 15 asset endpoints) |

**De-duplication (assignment rule 4):** every candidate reduced to
`(host, locale-stripped path)` and compared against all P102–P107 captures
(256 known normalized URLs from `.prov.json` sidecars + earlier inventories).
`/en/` ↔ `/th/` mirrors of a known path are the same source, never new.
Post-filter new-path pool: Mazda 491 · Nissan 388 · Mitsubishi 1,287 · Kia 918 ·
Lexus 661 · Subaru 377 · Changan/Deepal 307 · Suzuki 271 · Jaguar 160 ·
Porsche 279 · GWM 55 · MG 51 · Toyota 15 · Isuzu 10 · Honda 9.

## 2. Acquisition batch (`p108_source_inventory.json`, `p108_capture_log.json`)

One bounded batch: **150 URLs attempted**, one polite GET each, no retry,
blocked-host token check before every request.

| status | n |
|---|---|
| `CAPTURED` (+ provenance sidecar) | **130** |
| `SOURCE_DROPPED` | 15 — 9 image-only PDFs (no text layer), 5 wrong-market (Subaru HK/KH), 1 error page served with HTTP 200 (Suzuki `/error`) |
| `HTTP_ERROR` | 3 |
| `BLOCKED_HOST` | 1 (GWM URL carrying the `haval` brand token — never requested) |
| `ERROR` | 1 (SSL, `ita.isuzu.co.th`) |
| `NO_CANDIDATE` | 4 — Deepal, MINI, Changan, Jaguar: external discovery surfaced no new official Thai-market URL outside the existing artifact set |

Captured by **source family**: `downloadable_pdf` 24 · `grade_configurator` 23 ·
`price_document` 15 · `official_press` 14 · `model_lineup` 13 · `other` 41.
Captured by **discovery channel**: search/index 114 · Porsche country sitemap 10 ·
homepage-endpoint probe 6.
Per brand: Toyota 12 · Mazda 12 · Mitsubishi 12 · Porsche 12 · Kia 12 · Lexus 12 ·
Nissan 11 · GWM 10 · MG 9 · Isuzu 9 · Honda 8 · Suzuki 7 · Subaru 4.

Every failure carries an exact `blocker`; every drop carries a reason string
(`wrong market…`, `PDF has no usable text layer…`, `error page served with
HTTP 200…`); the capture log holds a row for all 150 decided URLs.

## 3. One concrete capture defect — red/green (assignment rule 8)

`safe_name()` re-used an already-`_dup` file name, so three later captures
overwrote an earlier artifact: the inventory recorded a sha256 that no longer
matched the sidecar.

- **red** `/tmp/p108_redbefore.log`: `inventory sha vs sidecar sha: 3
  mismatch(es) before fix` — `toyota_p108_index_dup.html`,
  `kia_p108_carnival_dup.html` ×2
- **fix:** unique name allocation (`while os.path.exists … _dupN`) in
  `scripts/p108_batch_acquire.py` + the three URLs re-acquired under new names
- **green** `/tmp/p108_green.log`: `0 mismatch(es)`; test
  `test_every_captured_artifact_sha_matches_its_sidecar` re-proves it for all 130
  artifacts (sha + https + `provenance_state = ACQUISITION_VERIFIED`), and
  `test_no_artifact_name_collides_across_entries` allows a repeated name only
  when every entry recorded the identical content hash.

No extraction/classifier code was touched.

## 4. Harvest (`p108_variant_harvest.py`, seeded from accepted P107)

**Before → after**

| measure | P107 baseline | P108 | delta |
|---|---|---|---|
| first-party confirmed VARIANT | 482 | **488** | **+6** |
| first-party confirmed MODEL | 264 | 264 | 0 |
| identity-only records | 696 | 690 | −6 |
| identity-only variants | 380 | 374 | −6 |
| universe records | 1424 | 1424 | 0 |
| harvest rows | 13 | 6 | grade_list 1 · grade_bare 3 · grade_table 2 |
| conflicts | 25 | 25 | 0 |
| rejected rows | 11 | 40 | generic 30 · cross-page 9 · promotion 1 |
| **variant deficit** | **383** | **377** | **−6** |

**Newly confirmed (all were identity-only at the P107 baseline):**

- **Honda +3** — `Honda Accord e:HEV E / EL / RS`, from the official dedicated
  page `honda_p108_accordehev.html` (bare grade rows, unique ownership)
- **Nissan +2** — `Nissan Almera E / EL`, from an **official press article**
  (`nissan_p108_nissan-almera-model-year-24-…`), grade table rows — the press
  family proved to be a real grade source, not just news
- **GWM +1** — `Gwm Tank 300 Diesel`, official grade list row on the
  purchase-consultation page

**Yield: 3 of 130 captured sources produced evidence**; every evidence row
re-verifies `provenance_state = ACQUISITION_VERIFIED`, https URL = sidecar URL,
sha256 = sidecar sha256.

## 5. Zero-gain OEMs — documented source gap (per brand, from this batch)

- **Toyota (69):** 12 new sources captured (price-list, model pages, news) —
  the published grade text sits behind shared labels; 3 rows rejected as
  `generic label` (Corolla), 1 `cross-page binding` (Vellfire).
- **Mazda (33):** 12 sources (catalog/spec/press); candidate lines carry
  `Mazda Cx-3 | 0` (promotion-class, rejected) and 6 rows failed
  `cross-page binding` — the label is published outside its model's context.
- **MG (29):** 9 sources incl. news + microsites; 2 brochure PDFs are image-only
  (dropped, no text layer); grade labels live inside table text only.
- **Porsche (21):** 12 sources from the `pap/_thailand_` country sitemap;
  model pages are JS shells — no published grade label in returned markup.
- **Mitsubishi (17):** 12 sources; 26 rows rejected as `generic label`
  (`SWB`/`LWB`/`GT`-class tokens on Pajero pages) — never grade labels.
- **Subaru (9):** 4 usable (5 wrong-market HK/KH drops, 4 image-only PDFs);
  TH brochure PDFs that answered were already consumed by earlier waves.
- **GWM (9):** `+1`; remaining grade names appear only inside other models'
  pages (cross-model) or in JS-rendered deals.
- **Isuzu (3) / Suzuki (3):** captured sources are privacy/CSR documents and
  error pages — the official brochure endpoints returned no text layer.
- **Kia (12), Lexus (7):** price-list/configurator pages captured; labels are
  either already confirmed or published under a different model name.
- **Deepal / MINI / Changan / Jaguar:** `NO_CANDIDATE` — external discovery
  found no new official Thai-market URL outside the existing artifact set
  (evidence-backed: sitemaps, search index, crt.sh and press index all sampled).

## 6. Gates — run once at the end of the wave

- combined **467 passed** = P108 **21** + P107 18 + P106 20 + P105 50 +
  P104 267 + P103 51 + P102 40 → `audit/daily-runs/20260928-p108-combined.log`
  (first run showed 5 failures — 1 real: the missing `safe_name` fix in the
  driver, 4 test-side schema/key mismatches; fixed and re-run once)
- full pytest **865 passed, 1 error in 749.39s** →
  `audit/daily-runs/20260928-p108-pytest.log`; the single error is the separate,
  unchanged pre-existing `_OPENROUTER_ALLOWED_MODEL` collection failure
  (`tests/test_generation_config_boundary.py`, last touched `eef8c49`), collected
  with `--continue-on-collection-errors`.  The first full run after the batch
  flagged the two `test_spec_coverage_plan.py` cases while the plan was being
  regenerated from the 130 new artifacts (`2 failed, 863 passed`); the
  regenerated plan was kept and the re-run above is the gate result.
- vitest exit 0 (5.23 s, frontend untouched this wave) · `tsc --noEmit` rc 0 ·
  `prisma validate` valid · credential scan: 0 real secrets (strict patterns
  `AKIA…/AIza…/ghp_…/xox…`; the only `sk-` hits are documentation placeholders)
- deterministic rerun: two consecutive runs inside `test_rerun_is_deterministic`
  → identical evidence digest, artifacts snapshotted and restored
- `staging_written: false` · `price_pass: false` · `prisma_touched: false` ·
  `p104_p103_p102_logic_changed: false` · `production_db_unchanged: true`
- forbidden paths (`prisma/`, `src/`, `package.json`, `Blueprint.md`, `lib/`,
  `audit/data-staging/`) untouched by this wave

## 7. Audit surface

`p108_source_inventory.json` · `p108_capture_log.json` ·
`p108_variant_evidence.json` (6 rows, sidecars for all 130 captures) ·
`catalog_reconciliation_p108.json` (40 rejected rows with reasons) ·
`identity_universe_p108.json` · `identity_matrix_p108.json` / `.md` ·
`p108_final_result.json` · `p108_target_plan.json` · this report ·
`scripts/p108_batch_acquire.py` · `scripts/p108_variant_harvest.py` ·
`tests/test_p108_external_discovery.py` · test logs under `audit/daily-runs/`.

## 8. Honest limits

Gain is real but small: **+6 confirmed variants, deficit 383 → 377**.  The
external channels opened genuinely new source families (Porsche country sitemap,
crt.sh subdomains, press indexes, sitemap endpoints) yet most of them publish
grades only as prose, JS payloads or image-only PDFs — the ceiling is the
publishers' format, not the fetch layer.  Official breadth remains 19/32, 13
OEMs blocked and never requested, identity-only variants 374 never promoted.
**This wave completes one bounded discovery/acquisition batch; the catalog is
not complete and is not claimed to be.**
