# P107 — Batch source discovery + official acquisition

**Wave:** P107 (after accepted P106, baseline `8fe60e5d2956fb5a83b67882551630c2193c5601`)
**date:** 2026-09-27 · **mode:** batch (one inventory → one acquisition batch → one
harvest → one test/gate run), no classifier/test re-iteration
**baseline result:** `p106_final_result.json` = 472 confirmed variants / 10 rows

---

## 1. Source inventory (`p107_source_inventory.json`)

16 targeted OEMs (every reachable OEM carrying a variant deficit), candidate URLs
derived from hrefs already inside committed first-party artifacts, ranked
price-sheet → catalog → brochure → pdf → equipment → spec → price → lineup →
configurator → compare → model page, capped at 7 per OEM, one polite GET each.

| | |
|---|---|
| URLs attempted | **110** (16 OEMs, no OEM skipped) |
| captured + provenance-verified | **94** |
| dropped after acquisition integrity check | 10 (`SOURCE_DROPPED`) |
| discarded as non-source (third-party/binary) | 5 (`DISCARDED_NON_SOURCE`) |
| connection failure | 1 (MG CDN `ChunkedEncodingError`) |
| HTTP 4xx/5xx | 0 |
| blocked OEM hosts requested | 0 (test asserts ∅ against the 13-host set) |

Per-OEM captured: Toyota 6 · Mazda 6 · MG 4 · Nissan 7 · Porsche 7 · Honda 5 ·
Mitsubishi 5 · Subaru 7 · Lexus 7 · GWM 6 · MINI 7 · Deepal 6 · Isuzu 7 ·
Suzuki 6 · Changan 4 · Jaguar 4.

Source types captured: brochure_pdf 35 · spec_page 18 · catalog_pdf 14 · pdf 9 ·
configurator 6 · equipment_page 4 · compare_page 4 · model_page 3 · price_page 1.

Every failure has an explicit `blocker` string in the inventory and an `error` in
`p107_capture_log.json`; nothing is silently dropped.

## 2. Acquisition integrity (source layer, not extraction)

Storing a downloaded PDF as base64 collided with the mandatory credential
sanitizer: 15 of 60 raw-PDF artifacts contained a chance `AIza…`-like sequence and
the writer inserted `[REDACTED:google_api_key]`, corrupting the encoding (sidecar
hash stayed self-consistent, but the bytes were no longer a decodable PDF).

`scripts/p107_reacquire_pdfs.py` re-fetched those URLs once and stored them as
derived text (`http_get_pdf_pdftotext`, `pdftotext -layout`), recording **both**
the downloaded PDF's SHA-256 and the stored text's SHA-256 in the capture log:

- re-acquired as `.txt` + sidecar: **9**
- dropped with `REACQUIRE_NO_TEXT_LAYER` (image-only PDF, or the URL is not a
  PDF at all): **10** — no evidence is ever taken from them
- remaining `.b64` artifacts all decode to a clean `%PDF` with no `REDACTED`
  marker (asserted by a test)

## 3. Batch harvest result

`scripts/p107_variant_harvest.py` (accepted P106 driver + PDF-capable source
reader + the one price-row repair in §4), seeded from the accepted P106 universe.

**Before → after**

| measure | P106 baseline | P107 | delta |
|---|---|---|---|
| first-party confirmed VARIANT | 472 | **482** | **+10** |
| first-party confirmed MODEL | 262 | 264 | +2 |
| identity-only records | 706 | 696 | −10 |
| identity-only variants | 390 | 380 | −10 |
| universe records | 1424 | 1424 | 0 |
| harvest rows | — | 13 | `existing 13` |
| evidence methods | — | grade_list 5 · name_price 4 · grade_bare 2 · page_bound 2 | — |
| conflicts | 25 | 25 | 0 |
| rejected rows | — | 11 | cross-page 7 · generic 3 · promotion 1 |
| variant deficit | 393 | **383** | −10 |

**Per-OEM delta (this wave)**

- **Toyota +5**: `Alphard HEV SMART`, `Alphard HEV PREMIUM`,
  `Alphard HEV PREMIUM LUXURY` (dedicated `/model/alphard`, name + published
  price row), `Altis HEV Smart`, `Altis 1.8G` (page-bound grade list)
- **Lexus +2**: `Nx 450H`, `Nx 350H` (official NX catalogue PDF)
- **MINI +2**: `John Cooper Works ALL-ELECTRIC MINI JOHN COOPER WORKS`,
  `… ACEMAN` (official brochure page, unique-ownership bare rows)
- **Changan +1**: `Lumin L DC` (official compare page)
- zero this wave: Mazda, Nissan, Porsche, Subaru, MG, Honda, Mitsubishi, GWM,
  Deepal, Isuzu, Suzuki, Jaguar, BMW, Kia — source-layer reasons in §5

**Yield:** 5 of 94 captured sources produced evidence
(`toyota_p107_alphard.html` 3 · `toyota_p107_altis.html` 2 ·
`mini_p107_brochure.html` 2 · `lexus_p107_AW_catalog_nov2025_Lexus_NX.pdf.b64` 2 ·
`changan_p107_compare-cars_dup.html` 1 — 4 rows on one variant).

## 4. The two changes made this wave (both with concrete evidence)

1. **`price_row_boundary` recognizes an English published price row.**
   Concrete failing evidence: on `https://www.toyota.co.th/en/model/alphard`
   four published rows (`Alphard HEV Smart` → `Start Price 3,590,000 Baht`,
   `Alphard HEV Premium`, `Alphard HEV Premium Luxury`, `Vellfire HEV Premium`)
   had the exact candidate label, sat in the page body, passed the promotion /
   generic / navigation gates — and were rejected only because the following
   published price line is English.  Red-first: `/tmp/p107_redbefore.log`
   = **2 failed / 1 passed** (`test_english_price_row_delimits_a_name_row`,
   `test_dedicated_alphard_page_confirms_its_own_grade_rows`).  The fix accepts
   a line carrying a price marker (`price`/`baht`/`thb`) together with a ≥5-digit
   figure; it still never reads, stores or verifies a price
   (`price_pass: false`; tests reject price keys and baht figures in evidence,
   and reject `Price list of the range`, `2026`, `Start Price 2026 Baht`).
   P104/P103/P102 logic and shared `PRICE_ROW` are untouched.
2. **Determinism tests no longer rewrite an accepted baseline.**
   A fixture-owning re-run of the P106 driver (new P107 captures present) changed
   P106's committed evidence, so `test_p106_variant_recovery.py::
   test_rerun_is_deterministic` failed.  Both P106 and P107 determinism tests now
   snapshot the wave's artifacts, run the driver twice, require identical
   evidence digests, and restore the snapshot — determinism is still proven
   (two runs, `assert first == second`), but a later wave's fixtures can never
   mutate an accepted baseline.  **`tests/test_p106_variant_recovery.py` is the
   only tracked file from a previous wave modified; no P106 logic, artifact or
   report was changed** (`p106_final_result.json` still `[462, 472]`).

No other code path changed: P105 R2 page-model binding, promotion/numeric label
blocker, cross-page rejection and deterministic ordering are all as accepted.

## 5. Source-layer gaps for the zero-gain OEMs (audited, per OEM)

- **Mazda (33):** the captured CX-30/2 catalog publishes grades only as
  `รุ่น 2.0 ULTRA` inside prose/table text, never as a model-bound grade row;
  `Mazda Cx-3 | 0` remains promotion-class and stays rejected.
- **Nissan (24):** `brochure-hub` publishes `e-Power` as the *only* label of
  Kicks on an aggregate page (single-label, fail-closed); Navara body styles
  (`Single Cab`, `King Cab`, `Double Cab`, `Pro 2X`) appear in prose only.
- **Porsche (21):** 7 official configurator/model URLs captured, all JS shells
  or codes — no published grade label in the returned markup.
- **Subaru (9):** brochures publish Crosstrek/Forester grades, but the
  candidates are recorded under `Subaru XV` → cross-model; BRZ `2.0 6AT/6MT`
  is not published in any captured source.
- **MINI (7):** `+2`; the rest are recorded under `MINI HATCH` while the price
  sheet heads sections `MINI COOPER.`, and `S ALL4 – CLASSIC` is not published
  (only `HIGHTRIM`, already consumed).
- **Changan (2):** `+1` (`L DC`); the candidate `L` never appears as a
  standalone published row.
- **Jaguar (2):** SVO pages carry `E` in prose only; the price sheet sections
  (`F-TYPE`) do not match the candidate model names.
- **Toyota (74→69):** `+5`; the remaining candidates appear only as body text or
  under labels owned by more than one model (`HEV SMART` is shared).
- **MG (29):** E-catalogues put grades inside table text and the labels
  (`D`, `X`, `V`, `D+`, `X+`, `V+`) are owned by several models → ambiguous,
  left identity-only.
- **Honda (18):** catalogs publish `e:HEV EL / EL+ / RS` inside combined text
  lines; two catalogs are image-only PDFs (no text layer, dropped).
- **Mitsubishi (17):** `GT` appears only in Mirage/Xpander brochures, not for
  the Outlander PHEV candidate → cross-model.
- **Lexus (9→7):** `+2`; `LS500h Pleat` appears in catalogue prose only.
- **GWM (9):** grade names (`ULTRA`, `HEV`) appear in *other* models' brochures
  (ORA5/Tank cross-over) → cross-model; the Tank-500 diesel brochure has no
  text layer (dropped).
- **Deepal (7):** S05 brochure publishes `MAX` as the single standalone label
  for `Deepal S05` (needs ≥2 grade rows → fail-closed); `PLUS`/`REEV PLUS`
  appear in other brochures → cross-model.
- **Isuzu (3):** fleet brochures and finance pages carry `RS` in prose only.
- **Suzuki (3):** the XL7 brochure has no text layer (dropped); equipment pages
  are per-grade shells whose markup does not contain the candidate labels.

## 6. Evidence quality

All 13 rows: provenance `ACQUISITION_VERIFIED`, `https` source URL equal to the
sidecar, artifact SHA-256 verified at read time, model bound either by the page
URL (`page_model_set`) or by the published line prefix, or — for bare rows — by
unique label ownership with ≥2 labels of that model on the page.  Every variant
was identity-only at the P106 baseline (test asserts `evidence ⊆ baseline
identity-only`), i.e. nothing was promoted from another status.

## 7. Gates (run once, after the batch)

- combined: **P107 18 + P106 20 + P105 50 + P104 267 + P103 51 + P102 40 = 446 passed**
- full pytest **844 passed, 1 error in 638.37s** →
  `audit/daily-runs/20260927-p107-pytest.log` — the single error is the separate
  pre-existing `_OPENROUTER_ALLOWED_MODEL` collection failure
  (`tests/test_generation_config_boundary.py`, untouched since `eef8c49`),
  collected with `--continue-on-collection-errors` (a first full run after the
  batch also flagged the two `test_spec_coverage_plan.py` cases while the plan
  was being regenerated from the 94 new artifacts; the regenerated plan is
  committed and the re-run is the 844-passed one above)
- vitest **488 passed / 2 skipped** · `tsc --noEmit` **rc 0** ·
  `prisma validate` **valid** · credential scan **0 hits / 9 files**
- `staging_written: false` · `price_pass: false` · `prisma_touched: false` ·
  `production_db_unchanged: true` · `p104_p103_p102_logic_changed: false`
- forbidden paths untouched (`prisma/`, `src/`, `package.json`, `Blueprint.md`,
  `lib/`, `audit/data-staging/`)

## 8. Audit surface

`p107_source_inventory.json` · `p107_capture_log.json` ·
`p107_variant_evidence.json` (13 rows) · `catalog_reconciliation_p107.json`
(11 rejected rows) · `identity_universe_p107.json` ·
`identity_matrix_p107.json` / `.md` · `p107_final_result.json` ·
`p107_target_plan.json` · this report · 94 new artifacts + sidecars ·
`scripts/p107_batch_acquire.py` · `scripts/p107_reacquire_pdfs.py` ·
`scripts/p107_variant_harvest.py` · `tests/test_p107_batch_sources.py` ·
`audit/daily-runs/20260927-p107-pytest.log`

## 9. Honest limits

Remaining variant deficit **383**, official breadth **19/32**, 13 OEMs blocked
and never requested, identity-only variants **380** never promoted, 10 sources
with no text layer and 5 non-source captures recorded instead of being used.
**This wave is complete for its batch scope only — the catalog is not complete
and is not claimed to be.**
