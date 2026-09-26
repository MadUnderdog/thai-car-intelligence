#!/usr/bin/env python3
"""Acquire a SMALL Thai-automotive-media batch through the provenance writer.

Targets come from storage/thai-source-registry.json (source_class
AUTOMOTIVE_MEDIA, search_method brand_price_page_crawl, URL pattern
/{brand}-price/). This is not speculative crawling: three documented URLs,
captured as artifacts + sidecars with the same AcquisitionWriter used for the
official lane, so a media observation carries a real artifact SHA and capture
timestamp.

Media rows stay AUTOMOTIVE_MEDIA / RESEARCH_UNVERIFIED forever — they are never
promoted to official, and an official value must never inherit a media locator.
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "lib"))

from thai_factory.acquisition.provenance import AcquisitionWriter  # noqa: E402

OUT_DIR = os.path.join(REPO, "tests", "fixtures", "media-artifacts")
REGISTRY = os.path.join(REPO, "storage", "thai-source-registry.json")
SESSION = "p100-media-batch"

# brand slug -> the 9CARTHAI price page this batch takes (documented pattern)
BATCH = ["toyota", "honda", "mazda"]


def registry_entry(domain: str) -> dict:
    """Registry entries are keyed by domain; the class/trust/URL pattern used
    below all come from the entry itself rather than being hard-coded."""
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    for e in reg["sources"]:
        if e.get("domain") == domain:
            return e
    raise KeyError(domain)


def fetch(url: str) -> tuple[str, int]:
    """Plain Chromium fetch — no UA rotation, no stealth, no bypass."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        status = resp.status if resp else 0
        html = page.content()
        browser.close()
    return html, status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    entry = registry_entry("9carthai.com")
    assert entry["source_class"] == "AUTOMOTIVE_MEDIA", entry["source_class"]
    assert entry["trust_state"] == "RESEARCH_UNVERIFIED", entry["trust_state"]
    pattern = "/{brand}-price/"   # the registry's documented brand_price_page_crawl shape
    base = "https://www.9carthai.com"

    report = []
    for brand in BATCH:
        url = f"{base}{pattern.format(brand=brand)}"
        try:
            html, status = fetch(url)
        except Exception as exc:                       # blocked / DNS / timeout
            report.append({"brand": brand, "url": url, "status": "FETCH_ERROR",
                           "detail": str(exc)[:200]})
            continue

        title = ""
        try:
            from html.parser import HTMLParser

            class T(HTMLParser):
                def __init__(self):
                    super().__init__(); self.in_title = False; self.buf = []
                def handle_starttag(self, tag, attrs):
                    if tag.lower() == "title":
                        self.in_title = True
                def handle_endtag(self, tag):
                    if tag.lower() == "title":
                        self.in_title = False
                def handle_data(self, data):
                    if self.in_title:
                        self.buf.append(data)
            t = T(); t.feed(html); title = "".join(t.buf).strip()
        except Exception:
            pass

        # subject-scope gate: the page must declare its own brand scope
        scope_ok = (status == 200 and brand.lower() in title.lower()
                    and "404" not in title and len(html) > 20_000)
        if not scope_ok:
            report.append({"brand": brand, "url": url, "status": "REJECTED",
                           "http": status, "title": title[:120], "bytes": len(html)})
            continue

        if args.dry_run:
            report.append({"brand": brand, "url": url, "status": "OK_DRY", "title": title[:120],
                           "bytes": len(html)})
            continue

        prov = AcquisitionWriter.write(
            content=html,
            source_url=url,
            acquisition_method="playwright",
            output_dir=OUT_DIR,
            filename=f"9carthai_{brand}_price.html",
            session_id=SESSION,
        )
        report.append({"brand": brand, "url": url, "status": "CAPTURED",
                       "title": title[:120], "bytes": len(html),
                       "sha256": prov["sha256"], "captured_at": prov["captured_at"]})

    print(json.dumps(report, ensure_ascii=False, indent=2))
    ok = [r for r in report if r["status"] in ("CAPTURED", "OK_DRY")]
    return 0 if len(ok) == len(BATCH) else 1


if __name__ == "__main__":
    raise SystemExit(main())
