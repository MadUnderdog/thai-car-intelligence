#!/usr/bin/env python3
"""P106 — targeted official captures for variant/grade layers still identity-only.

Only REACHABLE OEMs from the accepted P105 matrix are requested; blocked OEMs
(BYD, Audi, Chevrolet, Ford, Tesla, Chery, Haval, NETA, Peugeot, Volvo, Avance,
Mercedes-Benz, Smart) are never contacted.  One polite GET per target, default
certificate validation, normal browser UA, no header spoofing, no retry of a
failed host in this session.

Every capture goes through AcquisitionWriter so the artifact and its
`.prov.json` sidecar come from one acquisition event; CRLF is normalised to LF
BEFORE hashing (AcquisitionReader reads text mode).  Targets are grade /
lineup / features pages discovered from hrefs already committed in P102–P105
artifacts (the reuse ladder stopped at what the repository holds).
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
SESSION_ID = "p106_official_grade_pages"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
POLITENESS_S = 1.5

# (brand, url, filename) — grade/lineup/features pages for the zero-gain and
# high-deficit reachable OEMs in p106_target_plan.json
TARGETS = [
    ("Subaru", "https://www.subaru.asia/th/th/brz/lineup.php", "subaru_th_lineup_brz.html"),
    ("Subaru", "https://www.subaru.asia/th/th/crosstrek/lineup.php", "subaru_th_lineup_crosstrek.html"),
    ("Subaru", "https://www.subaru.asia/th/th/forester/lineup.php", "subaru_th_lineup_forester.html"),
    ("Kia", "https://www.kia.com/th/th/cars/carnival/features.html", "kia_carnival_features.html"),
    ("Kia", "https://www.kia.com/th/th/cars/carnival-hev/features.html", "kia_carnival_hev_features.html"),
    ("Kia", "https://www.kia.com/th/th/cars/ev5/features.html", "kia_ev5_features.html"),
    ("Jaguar", "https://www.jaguar.co.th/jaguar-range/f-type/models", "jaguar_f_type_models.html"),
    ("Jaguar", "https://www.jaguar.co.th/electric-cars/overview", "jaguar_electric_overview.html"),
    ("Porsche", "https://www.porsche.com/thailand/models/cayenne/", "porsche_th_cayenne.html"),
    ("Porsche", "https://www.porsche.com/thailand/models/911/", "porsche_th_911.html"),
    ("Porsche", "https://www.porsche.com/thailand/models/718/", "porsche_th_718.html"),
    ("Mazda", "https://www.mazda.co.th/th/cars", "mazda_all_cars.html"),
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
    out.update(ok=True, final_url=resp.url, bytes=len(content),
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
              f"{res.get('bytes', 0)}B {res.get('error', '')} {res.get('final_url', '')}")
        time.sleep(POLITENESS_S)
    out = os.path.join(REPO, "audit/coverage/p106_capture_log.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"artifact": "p106_capture_log/1", "session_id": SESSION_ID,
                   "results": results}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
