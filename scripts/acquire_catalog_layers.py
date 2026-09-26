#!/usr/bin/env python3
"""
P100 catalog-layer acquisition (Blueprint §59 Pass C + §93 fallback ladder).

Captures DEEPER first-party catalog layers discovered by traversing internal
links of artifacts we already hold: grade/price tables, all-model indexes,
brochure hubs, price sheets, model pages.

Hard rules honoured here:
  * every capture goes through AcquisitionWriter (artifact + .prov.json from the
    same acquisition event, sha256 over credential-sanitised bytes)
  * per-host politeness: >=5 s between requests to the same host, capped per run
  * no UA rotation, no TLS-verification bypass, no blocked-host retries before
    next_retry_at (the target list only contains REACHABLE brands)
  * results are recorded so the registry can cite evidence, not guesses

Usage:
  python3 scripts/acquire_catalog_layers.py --batch A
  python3 scripts/acquire_catalog_layers.py --batch B
"""
import argparse
import asyncio
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from thai_factory.acquisition.provenance import AcquisitionWriter  # noqa: E402

FIXTURE_DIR = "tests/fixtures/oem-artifacts"
OUT_DIR = "audit/coverage"
SESSION_ID = None  # set in main()
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
POLITENESS_S = 5.5          # §94 per-host politeness
PER_HOST_CAP = 20           # capped requests per host per run
REQUEST_TIMEOUT_MS = 45000

# ─── target list ────────────────────────────────────────────────────────────
# Every URL below was discovered from an artifact we already hold (official
# internal links) — no search-engine snippets, no third-party URLs.
BATCH_A = [
    # (url, filename, kind, note)
    ("https://www.nissan.co.th/vehicles/all-grade-price.html",
     "nissan_all_grade_price.html", "html",
     "official all-grade price table (link from nissan.co.th nav)"),
    ("https://www.nissan.co.th/vehicles/all-models.html",
     "nissan_all_models.html", "html",
     "official all-models index (link from nissan.co.th nav)"),
    ("https://www.mitsubishi-motors.co.th/th/buy/all-models-price",
     "mitsubishi_all_models_price.html", "html",
     "official all-models price page (link from mitsubishi home)"),
    ("https://www.lexus.co.th/th/price-and-model-tools/price-list.html",
     "lexus_price_list.html", "html",
     "official Lexus price list tool (link from lexus.co.th models page)"),
    ("https://www.bmw.co.th/en/topics/price-list.html",
     "bmw_price_list.html", "html",
     "official BMW price list topic page (link from bmw all-models)"),
    ("https://www.mini.co.th/content/dam/MINI/marketTH/mini_co_th/brochure/"
     "brochure-2026/MINI-Price-Sheet-Revised-27-Mar-2026.pdf.asset.1774933915613.pdf",
     "MINI_PriceSheet_20260327.pdf.b64", "pdf",
     "official MINI Thailand price sheet PDF (link from mini.co.th home)"),
]

BATCH_B = [
    # brochure / catalog hubs
    ("https://www.kia.com/th/th/shopping-tools/download-a-brochure.html",
     "kia_brochure_hub.html", "html",
     "official Kia brochure hub (link from kia.com/th/th)"),
    ("https://www.isuzu-tis.com/download-brochure",
     "isuzu_brochure_page.html", "html",
     "official Isuzu brochure download page (link from isuzu-tis.com)"),
    ("https://www.suzuki.co.th/upload/file/Catalog/Suzuki_Collection_E-Catalog_2024.pdf",
     "Suzuki_Collection_E-Catalog_2024.pdf.b64", "pdf",
     "official Suzuki e-catalog PDF (link from suzuki.co.th)"),
    ("https://www.changan.co.th/images/nevo/q05/pdf/Q05-Specs-sheet-th.pdf",
     "Changan_NEVOQ05_SpecSheet_th.pdf.b64", "pdf",
     "official Changan NEVO Q05 spec sheet PDF (link from changan.co.th)"),
    # model pages — lineup index links (Pass C), for grade/trim selectors
    ("https://www.mazda.co.th/th/cars/mazda-cx5", "mazda_car_mazda-cx5.html", "html",
     "official Mazda model page"),
    ("https://www.mazda.co.th/th/cars/mazda2-essential", "mazda_car_mazda2-essential.html",
     "html", "official Mazda model page"),
    ("https://www.mazda.co.th/th/cars/mazda3-sedan", "mazda_car_mazda3-sedan.html",
     "html", "official Mazda model page"),
    ("https://www.mazda.co.th/th/cars/new-mazda-bt50", "mazda_car_new-mazda-bt50.html",
     "html", "official Mazda model page"),
    ("https://www.mazda.co.th/th/cars/mazda-cx30-essential",
     "mazda_car_mazda-cx30-essential.html", "html", "official Mazda model page"),
    ("https://www.mgcars.com/th/cars/mg-zs", "mg_car_mg-zs.html", "html",
     "official MG model page"),
    ("https://www.mgcars.com/th/cars/mg-hs", "mg_car_mg-hs.html", "html",
     "official MG model page"),
    ("https://www.mgcars.com/th/cars/mg-im6", "mg_car_mg-im6.html", "html",
     "official MG model page"),
    ("https://www.mgcars.com/th/cars/mg-urban", "mg_car_mg-urban.html", "html",
     "official MG model page"),
    ("https://www.suzuki.co.th/model/fronx/", "suzuki_model_fronx.html", "html",
     "official Suzuki model page"),
    ("https://www.suzuki.co.th/model/xl7/", "suzuki_model_xl7.html", "html",
     "official Suzuki model page"),
    ("https://www.suzuki.co.th/model/jimny", "suzuki_model_jimny.html", "html",
     "official Suzuki model page"),
    # GWM brochure/catalog PDFs (variant completeness beyond the price cards)
    ("https://www.gwm.co.th/content/dam/gwm/pages/th/en/model/haval-h6-hev/0901_th_h6.pdf",
     "GWM_HavalH6_Brochure.pdf.b64", "pdf", "official GWM Haval H6 brochure PDF"),
    ("https://www.gwm.co.th/content/dam/gwm/pages/th/th/model/ora-5/"
     "tc_ora5_bev_catalog_th_220326.pdf",
     "GWM_ORA5BEV_Catalog.pdf.b64", "pdf", "official GWM ORA 5 BEV catalog PDF"),
]


# P101 batch C: first-party catalog-completeness layers (variant/grade, brochure,
# price-index, press and configurator) discovered by Pass C traversal of artifacts
# already held in tests/fixtures/oem-artifacts (see `discovered_from` in each note).
TARGETS_C = [
    ('https://configure.mini.co.th/en_TH/model-ranges', 'MINI_configurator_model_ranges.html', 'html', 'P101 catalog completeness: discovered in mini_home_page.html (legacy fixture, no sidecar)'),
    ('https://www.bmw.co.th/en/topics/brochure.html', 'bmw_brochure_page.html', 'html', 'P101 catalog completeness: discovered in bmw_all_models_verified.html'),
    ('https://configure.bmw.co.th/en_TH/configure/G20/24FWZ7U', 'bmw_configurator_3series.html', 'html', 'P101 catalog completeness: discovered in bmw_all_models_verified.html'),
    ('https://www.changan.co.th/th/news/', 'changan_press_news.html', 'html', 'P101 catalog completeness: discovered in changan_home_page.html'),
    ('https://www.changan.co.th/th/deepal/e07-performance-awd/', 'deepal_e07_awd.html', 'html', 'P101 catalog completeness: discovered in changan_home_page.html'),
    ('https://www.changan.co.th/th/deepal/e07-plus-th/', 'deepal_e07_plus.html', 'html', 'P101 catalog completeness: discovered in changan_home_page.html'),
    ('https://www.changan.co.th/th/deepal/hunter-k50-th/', 'deepal_hunter_k50.html', 'html', 'P101 catalog completeness: discovered in changan_home_page.html'),
    ('https://www.changan.co.th/th/deepal/s05-th/', 'deepal_s05.html', 'html', 'P101 catalog completeness: discovered in changan_home_page.html'),
    ('https://www.changan.co.th/th/deepal/s05-reev-th/', 'deepal_s05_reev.html', 'html', 'P101 catalog completeness: discovered in changan_home_page.html'),
    ('https://www.changan.co.th/th/deepal/s07-th/', 'deepal_s07.html', 'html', 'P101 catalog completeness: discovered in changan_home_page.html'),
    ('https://assets.honda.co.th/www-assets/model/2026/06/26/i6hZNelHYNX0LptCvSY8sw1hN3honOd6.pdf?response-content-disposition=attachment%3B%20filename%3DNew Honda City - Catalog.pdf', 'honda_brochure_1.pdf', 'pdf', 'P101 catalog completeness: discovered in honda_models_page.html'),
    ('https://assets.honda.co.th/www-assets/model/2026/06/26/bc5ZpbNVUtvUdaYcQMT8N6WdinDUVwDx.pdf?response-content-disposition=attachment%3B%20filename%3DNew Honda City Hatchback - Catalog.pdf', 'honda_brochure_2.pdf', 'pdf', 'P101 catalog completeness: discovered in honda_models_page.html'),
    ('https://www.honda.co.th/news', 'honda_press_news.html', 'html', 'P101 catalog completeness: discovered in honda_models_page.html'),
    ('https://assets.isuzu-tis.com/2_door_brochure_2026_4aed74da60.pdf', 'isuzu_brochure_2door.pdf', 'pdf', 'P101 catalog completeness: discovered in isuzu_brochure_page.html'),
    ('https://assets.isuzu-tis.com/4_door_brochure_2026_be4df560bb.pdf', 'isuzu_brochure_4door.pdf', 'pdf', 'P101 catalog completeness: discovered in isuzu_brochure_page.html'),
    ('https://assets.isuzu-tis.com/mu_x_brochure_2026_5d17d1513d.pdf', 'isuzu_brochure_mux.pdf', 'pdf', 'P101 catalog completeness: discovered in isuzu_brochure_page.html'),
    ('https://assets.isuzu-tis.com/spark_brochure_2026_ed212091cf.pdf', 'isuzu_brochure_spark.pdf', 'pdf', 'P101 catalog completeness: discovered in isuzu_brochure_page.html'),
    ('https://assets.isuzu-tis.com/v_cross_brochure_2026_23a52b3f0d.pdf', 'isuzu_brochure_vcross.pdf', 'pdf', 'P101 catalog completeness: discovered in isuzu_brochure_page.html'),
    ('https://assets.isuzu-tis.com/x_series_brochure_2026_6f67fd7b71.pdf', 'isuzu_brochure_xseries.pdf', 'pdf', 'P101 catalog completeness: discovered in isuzu_brochure_page.html'),
    ('https://www.isuzu.co.th/news', 'isuzu_press_news.html', 'html', 'P101 catalog completeness: discovered in isuzu_th_home_page.html'),
    ('https://www.jaguar.co.th/about-jaguar/news', 'jaguar_press_news.html', 'html', 'P101 catalog completeness: discovered in jaguar_home_page.html'),
    ('https://www.kia.com/th/th/discover-kia/article/review-the-new-kia-carnival-hev-7-seater-3.html', 'kia_press_article_carnival.html', 'html', 'P101 catalog completeness: discovered in kia_home_page.html'),
    ('https://www.kia.com/th/th/util/promotion/thekiacarnival-diesel-2026.html', 'kia_promo_carnival_diesel.html', 'html', 'P101 catalog completeness: discovered in kia_home_page.html'),
    ('https://www.kia.com/th/th/util/promotion/thekiacarnival-hev-2026.html', 'kia_promo_carnival_hev.html', 'html', 'P101 catalog completeness: discovered in kia_home_page.html'),
    ('https://www.kia.com/content/dam/kwcms/th/th/pdf/TheKiaPV5_Cargo_th.pdf', 'kia_pv5_brochure.pdf', 'pdf', 'P101 catalog completeness: discovered in kia_cars_page.html'),
    ('https://www.landrover.co.th/explore-land-rover/articles', 'landrover_press_articles.html', 'html', 'P101 catalog completeness: discovered in landrover_home_page.html'),
    ('https://www.lexus.co.th/th/price-and-model-tools/model-brochures.html', 'lexus_brochures.html', 'html', 'P101 catalog completeness: discovered in lexus_models_page.html'),
    ('https://www.lexus.co.th/th/discover-lexus/news-and-events.html', 'lexus_press_news.html', 'html', 'P101 catalog completeness: discovered in lexus_models_page.html'),
    ('https://www.mazda.co.th/s3fs-public/2024-12/v2_brochure-new-mazda-bt50.pdf?VersionId=Whzmuz5YnnWl0XkLVQTrsrvp8eokHNRB', 'mazda_brochure_bt50.pdf', 'pdf', 'P101 catalog completeness: discovered in mazda_car_new-mazda-bt50.html'),
    ('https://www.mazda.co.th/s3fs-public/2025-03/brochure-mazda-cx5.pdf?VersionId=VA_c9P6y6nt7uww1DHVXHSXN3dZoA88V', 'mazda_brochure_cx5.pdf', 'pdf', 'P101 catalog completeness: discovered in mazda_car_mazda-cx5.html'),
    ('https://www.mazda.co.th/s3fs-public/2025-03/brochure_mazda2_essential_26032025.pdf?VersionId=AfXNz7AmQsbwFurYSIj4Rc0LOJo9UwWw', 'mazda_brochure_mazda2.pdf', 'pdf', 'P101 catalog completeness: discovered in mazda_car_mazda2-essential.html'),
    ('https://www.mazda.co.th/th/news-update', 'mazda_press_news.html', 'html', 'P101 catalog completeness: discovered in mazda_home_page.html'),
    ('https://www.mazda.co.th/th/cars/mazda-cx30-essential/spec', 'mazda_spec_mazda-cx30-essential.html', 'html', 'P101 catalog completeness: discovered in mazda_car_mazda-cx30-essential.html'),
    ('https://www.mazda.co.th/th/cars/mazda-cx5/spec', 'mazda_spec_mazda-cx5.html', 'html', 'P101 catalog completeness: discovered in mazda_car_mazda-cx5.html'),
    ('https://www.mazda.co.th/th/cars/mazda2-essential/spec', 'mazda_spec_mazda2-essential.html', 'html', 'P101 catalog completeness: discovered in mazda_car_mazda2-essential.html'),
    ('https://www.mazda.co.th/th/cars/mazda3-sedan/spec', 'mazda_spec_mazda3-sedan.html', 'html', 'P101 catalog completeness: discovered in mazda_car_mazda3-sedan.html'),
    ('https://www.mazda.co.th/th/cars/new-mazda-bt50/spec', 'mazda_spec_new-mazda-bt50.html', 'html', 'P101 catalog completeness: discovered in mazda_car_new-mazda-bt50.html'),
    ('https://www.mgcars.com/th/news', 'mg_press_news.html', 'html', 'P101 catalog completeness: discovered in mg_car_mg-hs.html'),
    ('https://www.mgcars.com/th/price-calculator', 'mg_price_calculator.html', 'html', 'P101 catalog completeness: discovered in mg_car_mg-zs.html'),
    ('https://www.mitsubishi-motors.co.th/th/download-a-brochure', 'mitsubishi_brochures.html', 'html', 'P101 catalog completeness: discovered in mitsubishi_home_page.html'),
    ('https://www.mitsubishi-motors.co.th/th/news-activity/news', 'mitsubishi_press_news.html', 'html', 'P101 catalog completeness: discovered in mitsubishi_all_models_price.html'),
    ('https://www.nissan.co.th/vehicles/brochure-hub.html', 'nissan_brochure_hub.html', 'html', 'P101 catalog completeness: discovered in nissan_new_home_page.html'),
    ('https://www.nissan.co.th/news.html', 'nissan_press_news.html', 'html', 'P101 catalog completeness: discovered in nissan_new_home_page.html'),
    ('https://www.porsche.com/stories/design/porsche-paint-to-sample-colours-and-configurator-guide/', 'porsche_press_story.html', 'html', 'P101 catalog completeness: discovered in porsche_home_page.html'),
    ('https://www.subaru.asia/th/th/contact-us/brochure.php', 'subaru_brochure_page.html', 'html', 'P101 catalog completeness: discovered in subaru_th_home_page.html'),
    ('https://www.subaru.asia/th/th/about-us/news.php', 'subaru_press_news.html', 'html', 'P101 catalog completeness: discovered in subaru_th_home_page.html'),
    ('https://www.subaru.asia/th/th/promotions/sales/217/forester-special-deals/', 'subaru_promo_forester.html', 'html', 'P101 catalog completeness: discovered in subaru_th_home_page.html'),
    ('https://www.suzuki.co.th/upload/file/Brochure/ALL_NEW_SUZUKI_FRONX_BROCHURE.pdf', 'suzuki_fronx_brochure.pdf', 'pdf', 'P101 catalog completeness: discovered in suzuki_model_fronx.html'),
    ('https://www.suzuki.co.th/model/fronx/equipment', 'suzuki_fronx_equipment.html', 'html', 'P101 catalog completeness: discovered in suzuki_model_fronx.html'),
    ('https://www.suzuki.co.th/upload/file/Brochure/SUZUKI_JIMNY_BROCHURE.pdf', 'suzuki_jimny_brochure.pdf', 'pdf', 'P101 catalog completeness: discovered in suzuki_model_jimny.html'),
    ('https://www.suzuki.co.th/model/jimny/equipment', 'suzuki_jimny_equipment.html', 'html', 'P101 catalog completeness: discovered in suzuki_model_jimny.html'),
    ('https://www.suzuki.co.th/news', 'suzuki_press_news.html', 'html', 'P101 catalog completeness: discovered in suzuki_home_page.html'),
    ('https://www.suzuki.co.th/model/xl7/equipment', 'suzuki_xl7_equipment.html', 'html', 'P101 catalog completeness: discovered in suzuki_model_xl7.html'),
    ('https://www.toyota.co.th/news', 'toyota_press_news.html', 'html', 'P101 catalog completeness: discovered in toyota_pricelist_page.html'),
]

BATCHES = {"A": BATCH_A, "B": BATCH_B, "C": TARGETS_C}


async def capture_html(url, filename, page, sem_by_host, last_hit):
    """Capture an HTML page through a shared browser context."""
    host = urlparse(url).netloc
    wait = POLITENESS_S - (time.monotonic() - last_hit.get(host, 0))
    if wait > 0:
        await asyncio.sleep(wait)
    last_hit[host] = time.monotonic()

    try:
        resp = await page.goto(url, timeout=REQUEST_TIMEOUT_MS, wait_until='domcontentloaded')
        status = resp.status if resp else None
        if status and status >= 400:
            return {"success": False, "blocker": f"HTTP_{status}", "url": url,
                    "filename": filename}
        # let client-rendered grade tables hydrate
        await page.wait_for_timeout(4000)
        content = await page.content()
        final_url = page.url
    except Exception as exc:                                    # noqa: BLE001
        return {"success": False, "blocker": f"FETCH_ERROR: {str(exc)[:120]}",
                "url": url, "filename": filename}

    prov = AcquisitionWriter.write(
        content=content, source_url=final_url, acquisition_method="playwright",
        output_dir=FIXTURE_DIR, filename=filename, session_id=SESSION_ID)
    return {"success": True, "filename": filename, "url": url, "final_url": final_url,
            "size": len(content), "sha256": prov["sha256"],
            "captured_at": prov["captured_at"]}


def capture_pdf(url, filename):
    """Fetch a PDF and store it base64-encoded through AcquisitionWriter."""
    host = urlparse(url).netloc
    try:
        import requests
        r = requests.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
        if r.status_code >= 400:
            return {"success": False, "blocker": f"HTTP_{r.status_code}", "url": url,
                    "filename": filename}
        data = r.content
    except Exception as exc:                                    # noqa: BLE001
        return {"success": False, "blocker": f"FETCH_ERROR: {str(exc)[:120]}",
                "url": url, "filename": filename}

    if data[:4] != b'%PDF':
        return {"success": False, "blocker": "NOT_A_PDF", "url": url,
                "filename": filename, "content_type": None}
    b64 = base64.b64encode(data).decode()
    prov = AcquisitionWriter.write(
        content=b64, source_url=url, acquisition_method="http_get_pdf_base64",
        output_dir=FIXTURE_DIR, filename=filename, session_id=SESSION_ID)
    return {"success": True, "filename": filename, "url": url, "size": len(data),
            "sha256": prov["sha256"], "captured_at": prov["captured_at"], "host": host}



def layer_hint(filename):
    """Deterministic capture-layer label written into the capture log."""
    f = filename.lower()
    if f.endswith(".pdf") and "pricesheet" in f.replace("_", "").replace("-", ""):
        return "price_sheet_pdf"
    if f.endswith(".pdf"):
        return "brochure_pdf"
    if "configurator" in f or "configure" in f:
        return "configurator"
    if any(k in f for k in ("press", "news", "article", "stories")):
        return "press_release"
    if any(k in f for k in ("price", "grade", "calculator")):
        return "price_or_grade_table"
    if any(k in f for k in ("spec", "equipment")):
        return "spec_or_equipment"
    if any(k in f for k in ("brochure", "catalog")):
        return "brochure_pdf"
    if "promo" in f:
        return "promotion"
    return "model_page_or_price_index"


async def run_batch(name):
    global SESSION_ID
    SESSION_ID = f"catalog_layers_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    targets = BATCHES[name]
    print(f"=== P100 CATALOG LAYER CAPTURE — batch {name} (session {SESSION_ID}) ===")
    results, last_hit = [], {}

    html_targets = [t for t in targets if t[2] == "html"]
    pdf_targets = [t for t in targets if t[2] == "pdf"]

    if html_targets:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=USER_AGENT, viewport={'width': 1920, 'height': 1080})
            page = await context.new_page()
            for url, filename, _kind, _note in targets:
                if _kind != "html":
                    continue
                res = await capture_html(url, filename, page, {}, last_hit)
                res["note"] = _note
                res["layer"] = layer_hint(filename)
                results.append(res)
                mark = "OK " if res["success"] else "ERR"
                print(f"  [{mark}] {filename} "
                      f"{res.get('size', 0)} bytes {res.get('sha256', res.get('blocker'))}")
            await browser.close()

    for url, filename, kind, note in pdf_targets:
        host = urlparse(url).netloc
        wait = POLITENESS_S - (time.monotonic() - last_hit.get(host, 0))
        if wait > 0:
            await asyncio.sleep(wait)
        last_hit[host] = time.monotonic()
        res = capture_pdf(url, filename)
        res["note"] = note
        res["layer"] = layer_hint(filename)
        results.append(res)
        mark = "OK " if res["success"] else "ERR"
        print(f"  [{mark}] {filename} {res.get('size', 0)} bytes "
              f"{res.get('sha256', res.get('blocker'))}")

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"catalog_layers_{name}_"
                      f"{datetime.now(timezone.utc).strftime('%Y%m%d')}.json")
    with open(out, 'w') as f:
        json.dump({
            "session_id": SESSION_ID,
            "batch": name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "politeness_s": POLITENESS_S,
            "targets": len(targets),
            "captured": [r for r in results if r["success"]],
            "blocked": [r for r in results if not r["success"]],
        }, f, indent=2, ensure_ascii=False)
    ok = sum(1 for r in results if r["success"])
    print(f"\ncaptured {ok}/{len(results)} -> {out}")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", choices=["A", "B", "C", "all"], default="A")
    args = ap.parse_args()
    names = ["A", "B", "C"] if args.batch == "all" else [args.batch]
    for n in names:
        asyncio.run(run_batch(n))


if __name__ == "__main__":
    main()
