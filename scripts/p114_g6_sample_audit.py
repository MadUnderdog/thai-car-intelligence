#!/usr/bin/env python3
"""P114 G6 — sample re-open audit (ONE run).

Re-opens the deterministic G6 sample of accepted-row source URLs for real
(Playwright Chromium; curl+pdftotext for PDFs), and checks identity / value /
locator against BOTH the live bytes and the committed artifact.

Read-only: writes /tmp/p114_g6_browser.json + prints a table. No DB access.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time

SAMPLE = "/tmp/p114_g6_sample.json"
OUT = "/tmp/p114_g6_browser.json"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/153.0.0.0 Safari/537.36")
FIX = "/home/ubuntu/Projects/thai-car-intelligence/tests/fixtures/oem-artifacts/"


def canon(s: str) -> str:
    return re.sub(r"[^0-9a-zก-๙]+", " ", (s or "").lower()).strip()


def artifact_text(fn: str) -> str:
    if fn.endswith(".pdf") or fn.endswith(".pdf.b64"):
        data = open(FIX + fn, "rb").read()
        if fn.endswith(".pdf.b64"):
            import base64
            raw = data.decode("utf-8", "ignore")
            raw = re.sub(r"-----[^-]+-----", "", raw)
            data = base64.b64decode(re.sub(r"\s+", "", raw))
        tmp = "/tmp/p114_g6.pdf"
        open(tmp, "wb").write(data)
        return subprocess.run(["pdftotext", "-layout", tmp, "-"],
                              capture_output=True, timeout=90
                              ).stdout.decode("utf-8", "ignore")
    raw = open(FIX + fn, encoding="utf-8", errors="ignore").read()
    if fn.endswith(".json"):
        try:
            raw = raw + "\n" + json.dumps(json.loads(raw), ensure_ascii=False)
        except Exception:
            pass
        return raw
    return re.sub(r"<[^>]+>", "\n", raw)


def evaluate(field: str, text: str, s: dict):
    t = canon(text)
    if field == "identity":
        ok = canon(s["model"]) in t and canon(s["variant"]) in t
        return bool(ok), f"model&variant_present={ok}"
    if field == "price":
        m = re.search(r"[\d,]{4,}", s.get("quote") or "")
        digits = re.sub(r"\D", "", m.group(0)) if m else ""
        ok = bool(digits) and digits in re.sub(r"\D", "", text)
        return bool(ok), f"digits({digits})_present={bool(ok)}"
    q = s.get("quote") or ""
    lab, _, val = q.partition("=")
    ok = canon(lab.strip()) in t and (
        canon(val.strip()) in t or
        (re.sub(r"\D", "", val) and
         re.sub(r"\D", "", val) in re.sub(r"\D", "", text)))
    return bool(ok), f"label&value_present={bool(ok)}"


def main() -> int:
    sample = json.load(open(SAMPLE))
    results = []
    browser = None
    page = None
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True,
                                     args=["--no-sandbox",
                                           "--ignore-certificate-errors"])
        ctx = browser.new_context(user_agent=UA, ignore_https_errors=True)
        page = ctx.new_page()
    except Exception as e:
        print(f"browser unavailable: {e}", file=sys.stderr)
        browser = None

    for s in sample:
        url = s["url"]
        row = dict(s)
        is_pdf = ".pdf" in url
        if is_pdf:
            r = subprocess.run(["curl", "-sL", "--max-time", "60", "-A", UA,
                                url], capture_output=True, timeout=90)
            if r.returncode == 0 and r.stdout:
                open("/tmp/p114_g6_live.pdf", "wb").write(r.stdout)
                try:
                    live = subprocess.run(
                        ["pdftotext", "-layout", "/tmp/p114_g6_live.pdf", "-"],
                        capture_output=True, timeout=90
                    ).stdout.decode("utf-8", "ignore")
                except Exception:
                    live = ""
                row["method"] = "curl+pdftotext"
            else:
                live, row["method"] = "", "curl_failed"
        else:
            live = ""
            raw_curl = ""
            r0 = subprocess.run(["curl", "-sL", "--max-time", "45", "-A", UA,
                                 url], capture_output=True, timeout=60)
            if r0.returncode == 0 and r0.stdout:
                txt = r0.stdout.decode("utf-8", "ignore")
                if not url.endswith(".json"):
                    txt = re.sub(r"<[^>]+>", "\n", txt)
                raw_curl = txt
            if page is not None:
                try:
                    page.goto(url, timeout=45000,
                              wait_until="domcontentloaded")
                    # give SPAs time to hydrate before reading innerText
                    time.sleep(6.0)
                    live = page.inner_text("body") or ""
                    html = page.content() or ""
                    row["method"] = "playwright-chromium"
                except Exception as e:
                    html = ""
                    row["method"] = f"playwright_error:{type(e).__name__}"
            else:
                html = ""
            # live evidence = rendered innerText + full DOM + raw HTTP bytes
            live = "\n".join([live, html, raw_curl])
            if raw_curl:
                row["method"] = (row.get("method", "") + "+curl").strip("+")
        art = artifact_text(s["artifact"])
        live_ok, live_detail = evaluate(s["field"], live or "", s)
        art_ok, art_detail = evaluate(s["field"], art, s)
        row.update({
            "live_bytes": len(live or ""),
            "live_ok": live_ok, "live_check": live_detail,
            "artifact_ok": art_ok, "artifact_check": art_detail,
            "reachable": bool(live and len(live) > 50),
            "verdict": "PASS" if (live_ok and art_ok) else
                       ("ARTIFACT_ONLY" if art_ok else "FAIL"),
        })
        results.append(row)
        print(f"{row['packet_id']} {row['oem']:12s} {row['field']:8s} "
              f"{row['method'][:34]:34s} live_ok={live_ok} art_ok={art_ok} "
              f"-> {row['verdict']}")
    if browser:
        browser.close()
    json.dump(results, open(OUT, "w"), ensure_ascii=False, indent=1)
    n_pass = sum(1 for r in results if r["verdict"] == "PASS")
    print(f"G6: {n_pass}/{len(results)} PASS "
          f"(ARTIFACT_ONLY={sum(1 for r in results if r['verdict']=='ARTIFACT_ONLY')}, "
          f"FAIL={sum(1 for r in results if r['verdict']=='FAIL')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
