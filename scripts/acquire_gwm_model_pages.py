#!/usr/bin/env python3
"""GWM Thailand — official model price-page acquisition.

Discovery (no extra scraping): https://www.gwm.co.th/robots.txt points at
sitemap.xml -> sitemap index -> /th/sitemap.xml (42 URLs). The index publishes
13 model detail pages under /th/models/<slug>. Those pages are server-rendered
and are the only gwm.co.th endpoints found that publish a figure; the previously
captured homepage /en/models /gwm-data-car-models and mall.gwm.co.th artifacts
carry zero price markers and stay recorded as captured-but-price-free.

Capture goes through AcquisitionWriter so every artifact gets a capture-time
sidecar (sha256 + captured_at + acquisition_method). One polite request per
page, ~1.2s apart, http_get declared honestly (plain GET, certificate
verification left on, no header spoofing beyond a normal browser UA).

Newlines are normalised CRLF -> LF BEFORE hashing: AcquisitionReader reads
artifacts in text mode (universal newlines), so an artifact still carrying the
server's CRLF would hash to something the reader can never reproduce. This is
exactly what a Playwright capture stores, since Chromium's serializer emits LF.
"""
import os
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from thai_factory.acquisition.provenance import AcquisitionWriter  # noqa: E402

FIXTURE_DIR = "tests/fixtures/oem-artifacts"
SESSION_ID = "acquisition_gwm_model_pages"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")

# slugs straight out of https://www.gwm.co.th/th/sitemap.xml
MODEL_SLUGS = [
    "haval-h6", "ora-5-ev", "ora-5-hev", "poer", "sahar", "sahar-diesel",
    "tank-300", "tank-300-diesel", "tank-300-limited-lb", "tank-500",
    "tank-500-3t-diesel", "tank-500-diesel", "wey-g9",
]


def capture(slug: str, session: requests.Session) -> dict:
    url = f"https://www.gwm.co.th/th/models/{slug}"
    filename = f"gwm_th_model_{slug}.html"
    try:
        resp = session.get(url, timeout=30)
    except Exception as exc:  # network/DNS layer — never bypass it
        return {"slug": slug, "url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if resp.status_code != 200:
        return {"slug": slug, "url": url, "ok": False, "error": f"HTTP_{resp.status_code}"}

    # normalise line endings before the capture-time hash so the sidecar binds
    # bytes AcquisitionReader (text mode) can reproduce exactly
    content = resp.text.replace("\r\n", "\n").replace("\r", "\n")

    provenance = AcquisitionWriter.write(
        content=content,
        source_url=resp.url,
        acquisition_method="http_get",
        output_dir=FIXTURE_DIR,
        filename=filename,
        session_id=SESSION_ID,
    )
    return {"slug": slug, "url": resp.url, "ok": True, "filename": filename,
            "sha256": provenance["sha256"], "captured_at": provenance["captured_at"],
            "bytes": len(content)}


def main() -> int:
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "th,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    results = []
    for slug in MODEL_SLUGS:
        res = capture(slug, session)
        results.append(res)
        mark = "ok " if res.get("ok") else "ERR"
        print(f"  [{mark}] {slug:22} {res.get('filename', res.get('error'))}")
        time.sleep(1.2)

    ok = [r for r in results if r.get("ok")]
    print(f"\nCaptured {len(ok)}/{len(results)} GWM model pages with sidecars")
    return 0 if len(ok) == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
