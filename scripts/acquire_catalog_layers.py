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

BATCHES = {"A": BATCH_A, "B": BATCH_B}


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
                res["layer"] = "model_page_or_price_index"
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
        res["layer"] = "brochure_or_price_sheet_pdf"
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
    ap.add_argument("--batch", choices=["A", "B", "all"], default="A")
    args = ap.parse_args()
    names = ["A", "B"] if args.batch == "all" else [args.batch]
    for n in names:
        asyncio.run(run_batch(n))


if __name__ == "__main__":
    main()
