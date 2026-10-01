#!/usr/bin/env python3
"""P103 — targeted official captures for identity layers with no reusable bytes.

Subaru: the registry host (subaru.co.th) is NXDOMAIN/BLOCKED_DNS and is never
requested; the official Thai importer property that is REACHABLE is
www.subaru.asia (already established by scripts/acquire_subaru_page.py and the
sidecar on subaru_th_home_page.html).  The lineup page publishes models and
starting prices but no grade/variant layer, so this wave captures the official
model pages, where grades are published.

Every capture goes through AcquisitionWriter so the artifact and its
`.prov.json` sidecar come from one acquisition event.  Newlines are normalised
CRLF -> LF BEFORE hashing (AcquisitionReader reads text mode).  One polite GET
per target, default certificate validation, no header spoofing beyond a normal
browser UA.  Nothing is captured for an OEM the registry records as BLOCKED_*.
"""
from __future__ import annotations

import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from thai_factory.acquisition.provenance import AcquisitionWriter  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO, "tests/fixtures/oem-artifacts")
SESSION_ID = "p103_official_model_pages"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
POLITENESS_S = 1.5

# (brand, url, filename) — official Subaru Asia Thai market model pages
TARGETS = [
    ("Subaru", "https://www.subaru.asia/th/th/forester/", "subaru_th_model_forester.html"),
    ("Subaru", "https://www.subaru.asia/th/th/crosstrek/", "subaru_th_model_crosstrek.html"),
    ("Subaru", "https://www.subaru.asia/th/th/brz/", "subaru_th_model_brz.html"),
]


def capture(brand: str, url: str, filename: str, session: requests.Session) -> dict:
    out: dict = {"brand": brand, "url": url, "filename": filename}
    try:
        resp = session.get(url, timeout=30)
    except Exception as exc:                       # network/DNS/TLS — never bypass
        out.update(ok=False, error=f"{type(exc).__name__}: {exc}")
        return out
    if resp.status_code != 200:
        out.update(ok=False, error=f"HTTP_{resp.status_code}")
        return out
    content = resp.text.replace("\r\n", "\n").replace("\r", "\n")
    provenance = AcquisitionWriter.write(
        content=content,
        source_url=resp.url,
        acquisition_method="http_get",
        output_dir=FIXTURE_DIR,
        filename=filename,
        session_id=SESSION_ID)
    out.update(ok=True, bytes=len(content),
               sha256=provenance.get("sha256"),
               captured_at=provenance.get("captured_at"))
    return out


def main() -> int:
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "th-TH,th;q=0.9"})
    results = []
    for brand, url, filename in TARGETS:
        path = os.path.join(FIXTURE_DIR, filename)
        if os.path.exists(path) and os.path.exists(path + ".prov.json"):
            results.append({"brand": brand, "url": url, "filename": filename,
                            "ok": True, "reused": True})
            print(f"  reused {filename}")
            continue
        res = capture(brand, url, filename, session)
        results.append(res)
        print(f"  {'ok  ' if res.get('ok') else 'FAIL'} {filename} "
              f"{res.get('bytes', 0)}B {res.get('error', '')}")
        time.sleep(POLITENESS_S)
    out = os.path.join(REPO, "audit/coverage/p103_capture_log.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"artifact": "p103_capture_log/1", "session_id": SESSION_ID,
                   "results": results}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {out}")
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
