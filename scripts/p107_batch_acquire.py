#!/usr/bin/env python3
"""P107 — batch source discovery + official acquisition.

One batch, no micro-iteration: for every OEM the P105/P106 waves gained nothing
on, take the official URLs already linked from committed first-party artifacts
(price / spec / grade / equipment / lineup / brochure / catalog / configurator
pages and PDFs), try them in one pass, capture what answers through
AcquisitionWriter, and record every miss as an explicit source-layer blocker.

Boundaries: blocked OEM hosts are never contacted, no header spoofing beyond a
normal browser UA, one polite GET per URL, no retry inside the batch, no price
is read or verified (prices are row boundaries at most).
"""
from __future__ import annotations

import base64
import datetime
import json
import os
import re
import sys
import time
import urllib.parse

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from thai_factory.acquisition.provenance import AcquisitionWriter  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO, "tests/fixtures/oem-artifacts")
OUT = os.path.join(REPO, "audit/coverage")
SESSION_ID = "p107_batch_sources_20260927"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
POLITENESS_S = 0.4
PER_OEM_CAP = 7
GLOBAL_CAP = 110

# OEMs the assignment targets, with the deficit carried from the accepted P106 wave
TARGET_DEFICIT = {"Mazda": 33, "Nissan": 24, "Porsche": 21, "Subaru": 9, "MINI": 7,
                  "Changan": 2, "Jaguar": 2, "Toyota": 74, "MG": 29, "Honda": 18,
                  "Mitsubishi": 17, "Lexus": 9, "GWM": 9, "Deepal": 7, "Isuzu": 3,
                  "Suzuki": 3}
BLOCKED_HOSTS = {"BYD", "Audi", "Chevrolet", "Ford", "Tesla", "Chery", "Haval",
                 "NETA", "Peugeot", "Volvo", "Avance", "Mercedes-Benz", "Smart"}
# hostnames that are official/first-party properties or their own asset CDNs
EXTRA_HOSTS = ("assets.honda.co.th", "assets.isuzu-tis.com", "api.www.changan.co.th",
               "cdn-jaguarlandrover.com", "configurator.porsche.com",
               "mg-upload.sgp1.cdn.digitaloceanspaces.com", "www.subaru.asia")
TRACKING = ("doubleclick", "googleads", "google-analytics", "liveperson",
            "visualwebsiteoptimizer", "facebook", "tiktok", "youtube", "line.me",
            "instagram", "bing.com", "clarity.ms", "hotjar", "zendesk")
SOURCE_HINTS = (("price_sheet_pdf", r"price.?sheet"), ("catalog_pdf", r"catalog|collection"),
                ("brochure_pdf", r"brochure|leaflet|brochures"), ("pdf", r"\.pdf"),
                ("equipment_page", r"equipment"), ("spec_page", r"specification|/spec"),
                ("price_page", r"price|pricelist"), ("lineup_page", r"lineup|catalogue|catalog"),
                ("compare_page", r"compare"), ("configurator", r"configurator"),
                ("model_page", r"/model|/cars|/vehicles|/range"))


def source_type(url: str) -> str:
    low = url.lower()
    for name, pat in SOURCE_HINTS:
        if re.search(pat, low):
            return name
    return "other"


def rank(url: str) -> int:
    st = source_type(url)
    order = {"price_sheet_pdf": 0, "catalog_pdf": 1, "brochure_pdf": 2, "pdf": 3,
             "equipment_page": 4, "spec_page": 5, "price_page": 6, "lineup_page": 7,
             "configurator": 8, "compare_page": 9, "model_page": 10, "other": 11}
    return order.get(st, 11)


def safe_name(brand: str, url: str) -> str:
    slug = urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1] or "index"
    slug = urllib.parse.unquote(slug)
    if source_type(url).endswith("pdf") and not slug.lower().endswith(".pdf"):
        slug = (slug + ".pdf") if "." not in slug else slug
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", slug).strip("_")[:60] or "page"
    if not slug.lower().endswith((".html", ".pdf", ".json")):
        slug += ".html"
    ext = ".pdf.b64" if slug.lower().endswith(".pdf") else ""
    base = brand.lower().replace("-", "_")
    stem = slug[:-len(".pdf")] if ext else slug[:-len(".html")]
    name = f"{base}_p107_{stem}{ext if ext else '.html'}"
    # never overwrite an artifact from an earlier wave
    if os.path.exists(os.path.join(FIXTURE_DIR, name)):
        name = name.replace(".", "_dup.", 1)
    return name


def load_candidates() -> dict:
    with open("/tmp/p107_candidates.json", encoding="utf-8") as fh:
        return json.load(fh)


def committed_urls() -> set:
    urls = set()
    for fn in os.listdir(FIXTURE_DIR):
        if fn.endswith(".prov.json"):
            try:
                urls.add(json.load(open(os.path.join(FIXTURE_DIR, fn),
                                        encoding="utf-8"))["source_url"].split("#")[0])
            except Exception:
                continue
    return urls


def main() -> int:
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    candidates = load_candidates()
    already = committed_urls()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "th-TH,th;q=0.9"})

    inventory, capture_log = [], []
    total = 0
    for brand in sorted(TARGET_DEFICIT, key=lambda b: -TARGET_DEFICIT[b]):
        urls = [u for u in candidates.get(brand, [])
                if u.split("#")[0] not in already
                and not any(t in u.lower() for t in TRACKING)]
        urls.sort(key=lambda u: (rank(u), u))
        chosen = urls[:PER_OEM_CAP]
        for url in chosen:
            if total >= GLOBAL_CAP:
                break
            total += 1
            entry = {"brand": brand, "url": url, "source_type": source_type(url),
                     "deficit_at_baseline": TARGET_DEFICIT[brand]}
            try:
                resp = session.get(url, timeout=25, allow_redirects=True)
            except Exception as exc:
                entry.update(status="ERROR", ok=False,
                             blocker=f"{type(exc).__name__}: {exc}")
                inventory.append(entry)
                capture_log.append({**{k: entry[k] for k in ("brand", "url", "source_type")},
                                    "ok": False, "error": entry["blocker"]})
                time.sleep(POLITENESS_S)
                continue
            entry["http_status"] = resp.status_code
            if resp.status_code != 200:
                entry.update(status="HTTP_ERROR", ok=False,
                             blocker=f"HTTP_{resp.status_code} after redirects")
                inventory.append(entry)
                capture_log.append({**{k: entry[k] for k in ("brand", "url", "source_type")},
                                    "ok": False, "error": entry["blocker"]})
                time.sleep(POLITENESS_S)
                continue
            final_url = resp.url
            ctype = (resp.headers.get("Content-Type") or "").lower()
            is_pdf = "pdf" in ctype or final_url.lower().split("?")[0].endswith(".pdf")
            filename = safe_name(brand, final_url)
            try:
                if is_pdf:
                    b64 = base64.b64encode(resp.content).decode("ascii")
                    prov = AcquisitionWriter.write(
                        content=b64, source_url=final_url,
                        acquisition_method="http_get_pdf_base64",
                        output_dir=FIXTURE_DIR, filename=filename,
                        session_id=SESSION_ID)
                    size = len(resp.content)
                else:
                    text = resp.text.replace("\r\n", "\n").replace("\r", "\n")
                    prov = AcquisitionWriter.write(
                        content=text, source_url=final_url,
                        acquisition_method="http_get",
                        output_dir=FIXTURE_DIR, filename=filename,
                        session_id=SESSION_ID)
                    size = len(text)
            except Exception as exc:
                entry.update(status="WRITE_ERROR", ok=False,
                             blocker=f"{type(exc).__name__}: {exc}")
                inventory.append(entry)
                capture_log.append({**{k: entry[k] for k in ("brand", "url", "source_type")},
                                    "ok": False, "error": entry["blocker"]})
                time.sleep(POLITENESS_S)
                continue
            entry.update(status="CAPTURED", ok=True, artifact=filename,
                         sha256=prov.get("sha256"), bytes=size,
                         final_url=final_url, content_type=ctype[:60],
                         usable=size > 2000, blocker="")
            inventory.append(entry)
            capture_log.append({"brand": brand, "url": url, "final_url": final_url,
                                "source_type": entry["source_type"], "filename": filename,
                                "ok": True, "sha256": prov.get("sha256"), "bytes": size})
            time.sleep(POLITENESS_S)
        if total >= GLOBAL_CAP:
            break

    # explicit per-OEM gap rows for OEMs where nothing was even attempted
    attempted = {e["brand"] for e in inventory}
    for brand, deficit in TARGET_DEFICIT.items():
        if brand not in attempted:
            inventory.append({"brand": brand, "url": None, "source_type": None,
                              "status": "NO_CANDIDATE", "ok": False,
                              "deficit_at_baseline": deficit,
                              "blocker": "no grade/price/brochure URL linked from "
                                         "committed first-party artifacts; sitemap "
                                         "layer not reachable in this batch"})

    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(os.path.join(OUT, "p107_source_inventory.json"), "w", encoding="utf-8") as fh:
        json.dump({"artifact": "p107_source_inventory/1", "generated_at": stamp,
                   "session_id": SESSION_ID,
                   "method": "href-derived official URLs from committed first-party "
                             "artifacts, rank(price/spec/equipment/lineup/brochure) "
                             "first, one polite GET each, no retry in batch",
                   "target_deficit": TARGET_DEFICIT,
                   "attempted": total, "captured": sum(1 for e in inventory if e.get("ok")),
                   "entries": inventory}, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(os.path.join(OUT, "p107_capture_log.json"), "w", encoding="utf-8") as fh:
        json.dump({"artifact": "p107_capture_log/1", "generated_at": stamp,
                   "session_id": SESSION_ID, "results": capture_log},
                  fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    ok = sum(1 for e in capture_log if e.get("ok"))
    print(f"attempted={total} captured={ok} failed={len(capture_log) - ok}")
    for e in capture_log:
        mark = "ok  " if e.get("ok") else "FAIL"
        print(f"  {mark} {e['brand']:11s} {e['source_type']:16s} "
              f"{(e.get('filename') or e.get('error',''))[:60]:60s} {e['url'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
