#!/usr/bin/env python3
"""Subaru Thailand — official lineup price-page acquisition (alternate host).

Why this host: the registry's primary Subaru URL `https://www.subaru.co.th/` is
NXDOMAIN (BLOCKED_DNS, recorded 2026-09-24, next re-probe 2026-10-01 per §94).
That host is never requested here. The fallback ladder (§93 rung 2/4) points at
the official Subaru Asia property instead: `https://www.subaru.asia/` resolves,
answers 200 and serves the Thailand market at `/th/th/` (footer: "© 2026 TC
Subaru (Thailand) Co.,Ltd." — the Thai importer itself, page `lang="th"`,
prices published in THB).

Capture goes through AcquisitionWriter so the artifact and its `.prov.json`
sidecar are written from the same acquisition event (sha256 + captured_at +
acquisition_method). One polite GET, certificate verification left on, no
header spoofing beyond a normal browser UA.

Newlines are normalised CRLF -> LF BEFORE hashing: AcquisitionReader reads
artifacts in text mode, so an artifact still carrying the server's CRLF would
hash to something the reader can never reproduce.
"""
import os
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from thai_factory.acquisition.provenance import AcquisitionWriter  # noqa: E402

FIXTURE_DIR = "tests/fixtures/oem-artifacts"
SESSION_ID = "acquisition_subaru_th_lineup"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")

# the Thailand-market lineup page on the official Subaru Asia property
TARGETS = [
    ("https://www.subaru.asia/th/th/", "subaru_th_home_page.html"),
]


def capture(url: str, filename: str, session: requests.Session) -> dict:
    try:
        resp = session.get(url, timeout=30)
    except Exception as exc:  # network/DNS/TLS layer — never bypass it
        return {"url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if resp.status_code != 200:
        return {"url": url, "ok": False, "error": f"HTTP_{resp.status_code}"}

    content = resp.text.replace("\r\n", "\n").replace("\r", "\n")
    provenance = AcquisitionWriter.write(
        content=content,
        source_url=resp.url,
        acquisition_method="http_get",
        output_dir=FIXTURE_DIR,
        filename=filename,
        session_id=SESSION_ID,
    )
    return {"url": resp.url, "ok": True, "filename": filename,
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
    for url, filename in TARGETS:
        res = capture(url, filename, session)
        results.append(res)
        mark = "ok " if res.get("ok") else "ERR"
        print(f"  [{mark}] {filename:28} {res.get('sha256', res.get('error'))}")
        time.sleep(1.2)

    ok = [r for r in results if r.get("ok")]
    print(f"\nCaptured {len(ok)}/{len(results)} Subaru Thailand pages with sidecars")
    return 0 if len(ok) == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
