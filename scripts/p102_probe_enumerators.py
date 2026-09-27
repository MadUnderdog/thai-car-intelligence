#!/usr/bin/env python3
"""
P102 — identity-enumerator source probe (horizontal, single batch).

Purpose: decide WHICH high-recall identity enumerators are actually usable for
Thai-market model/variant enumeration, in ONE pass over a candidate list, so the
later harvest run only touches sources that really publish a taxonomy.

Role rule (Blueprint §96): everything probed here is an IDENTITY_ENUMERATOR
candidate. Nothing captured by this script is market truth, and nothing here
writes to staging or the production DB.

Usage:
  python3 scripts/p102_probe_enumerators.py
"""
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

OUT = os.path.join("audit", "coverage", "p102_enumerator_probe.json")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")

# candidate IDENTITY_ENUMERATOR sources (Thai-market scope, no sibling brands)
CANDIDATES = [
    # (id, url, why)
    ("one2car", "https://www.one2car.com/", "used-car portal: brand/model/submodel taxonomy"),
    ("one2car_sell", "https://www.one2car.com/sell", "used-car sell filter taxonomy"),
    ("viriyah", "https://www.viriyah.co.th/", "insurance/used-car taxonomy"),
    ("bangkok_insurance", "https://www.bangkokinsurance.com/", "insurance quote taxonomy"),
    ("ninecarthai", "https://www.9carthai.com/", "Thai auto media model/price index"),
    ("headlightmag", "https://www.headlightmag.com/", "Thai auto media model index"),
    ("autolife", "https://www.autolifethailand.tv/", "Thai auto media model index"),
    ("autocar_th", "https://www.autocar.co.th/", "Thai auto media/price index"),
    ("ttb_bank", "https://www.ttbbank.com/", "finance: car loan model taxonomy"),
    ("uob_th", "https://www.uob.co.th/", "finance: car loan model taxonomy"),
    ("dlt", "https://www.dlt.go.th/", "DLT (market reference / registration taxonomy)"),
    ("tisco", "https://www.tisco.co.th/", "finance: car loan model taxonomy"),
]

MODELISH = re.compile(r"(model|car|vehicle|brand|make|series|lineup|price|รุ่น|ยี่ห้อ|รถยนต์)",
                      re.I)


async def probe(page, sid, url):
    rec = {
        "id": sid, "url": url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "UNKNOWN", "http_status": 0, "title": "",
        "selects": [], "select_option_total": 0,
        "xhr_json": [], "candidate_links": [],
        "body_chars": 0, "error": "",
    }
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        rec["http_status"] = resp.status if resp else 0
        await page.wait_for_timeout(5000)
        try:
            rec["title"] = await page.title()
        except Exception:
            pass

        # <select> taxonomies
        try:
            rec["selects"] = await page.evaluate("""
              () => Array.from(document.querySelectorAll('select')).map(s => ({
                name: (s.name || s.id || ''),
                options: Array.from(s.options).map(o => (o.textContent||'').trim()).filter(Boolean)
              })).filter(s => s.options.length)
            """)
        except Exception:
            pass
        rec["select_option_total"] = sum(len(s["options"]) for s in rec["selects"])

        # XHR/fetch JSON endpoints (taxonomy APIs)
        try:
            rec["xhr_json"] = await page.evaluate("""
              () => (window.__p102xhr || []).slice(0, 60)
            """)
        except Exception:
            pass

        # candidate internal links
        try:
            rec["candidate_links"] = await page.evaluate("""
              () => {
                const out = [], seen = new Set();
                for (const a of document.querySelectorAll('a[href]')) {
                  const h = a.getAttribute('href') || '';
                  const t = (a.textContent || '').trim().slice(0, 80);
                  if (!t) continue;
                  if (!/model|car|vehicle|brand|series|lineup|price|รุ่น|ยี่ห้อ|รถยนต์/i.test(h + ' ' + t)) continue;
                  const key = h + '|' + t;
                  if (seen.has(key)) continue;
                  seen.add(key);
                  out.push({href: h, text: t});
                  if (out.length >= 80) break;
                }
                return out;
              }
            """)
        except Exception:
            pass

        try:
            rec["body_chars"] = await page.evaluate("() => document.body.innerText.length")
        except Exception:
            pass

        if rec["http_status"] and rec["http_status"] < 400 and rec["body_chars"] > 500:
            rec["status"] = "OK"
        elif rec["http_status"] in (403, 429):
            rec["status"] = "BLOCKED_HTTP_%s" % rec["http_status"]
        elif rec["http_status"] >= 400:
            rec["status"] = "BLOCKED_HTTP_%s" % rec["http_status"]
        else:
            rec["status"] = "NO_RESPONSE"
    except Exception as e:
        rec["status"] = "ERROR"
        rec["error"] = str(e)[:300]
    return rec


async def main():
    from playwright.async_api import async_playwright
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="th-TH", timezone_id="Asia/Bangkok", user_agent=UA,
        )
        page = await ctx.new_page()
        xhr = []
        page.on("response", lambda r: _on_resp(r, xhr))
        page.on("request", lambda req: None)
        # shared XHR buffer for the current page
        async def attach():
            pass
        for sid, url, why in CANDIDATES:
            xhr.clear()
            page.set_default_timeout(45000)
            rec = await probe(page, sid, url)
            rec["why"] = why
            rec["xhr_json"] = [x for x in xhr][:60]
            results.append(rec)
            print(f"{sid:22s} {rec['status']:22s} sel={rec['select_option_total']:4d} "
                  f"links={len(rec['candidate_links']):3d} xhr={len(rec['xhr_json']):3d} "
                  f"title={rec['title'][:50]}", flush=True)
        await browser.close()

    out = {
        "schema": "p102-identity-enumerator-probe/1",
        "role_note": "IDENTITY_ENUMERATOR candidates only (Blueprint §96) — "
                     "enumeration evidence, never market truth.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidates": results,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("wrote", OUT)


def _on_resp(response, buf):
    try:
        ct = response.headers.get("content-type", "")
        if "json" in ct:
            buf.append({"url": response.url, "status": response.status,
                        "content_type": ct})
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
