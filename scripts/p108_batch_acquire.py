#!/usr/bin/env python3
"""P108 — external source-discovery acquisition batch.

Inputs are URLs produced by *external* discovery channels only (robots/sitemap
indexes, sub-domain certificate transparency, search index, official press
indexes, structured sitemap endpoints) and de-duplicated against every URL
already captured by P102–P107 — a URL is never counted twice and a locale
mirror of a known path is never a new source.

One bounded batch, one polite GET per URL, no retry, blocked hosts never
contacted.  PDFs are stored as derived text (`http_get_pdf_pdftotext`,
pdftotext -layout) so the credential sanitizer can never corrupt a payload;
an image-only PDF is dropped with an explicit blocker.  No price is read,
stored or verified.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from thai_factory.acquisition.provenance import AcquisitionWriter  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO, "tests/fixtures/oem-artifacts")
OUT = os.path.join(REPO, "audit/coverage")
SESSION_ID = "p108_external_discovery_20260928"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
POLITENESS_S = 0.4
GLOBAL_CAP = 150

# deficit carried by the accepted P107 wave (p107 report §5)
TARGET_DEFICIT = {"Toyota": 69, "Mazda": 33, "MG": 29, "Nissan": 24, "Porsche": 21,
                  "Honda": 18, "Mitsubishi": 17, "Subaru": 9, "GWM": 9, "Lexus": 7,
                  "MINI": 5, "Deepal": 7, "Changan": 1, "Jaguar": 2, "Isuzu": 3,
                  "Suzuki": 3, "Kia": 12}
PRIORITY = ["Toyota", "Mazda", "MG", "Nissan", "Porsche", "Honda", "Mitsubishi",
            "Subaru", "GWM", "Deepal", "MINI", "Changan", "Jaguar", "Isuzu",
            "Suzuki", "Lexus", "Kia"]
PER_OEM_CAP = 12
BLOCKED_HOSTS = {"BYD", "Audi", "Chevrolet", "Ford", "Tesla", "Chery", "Haval",
                 "NETA", "Peugeot", "Volvo", "Avance", "Mercedes-Benz", "Smart"}
TRACKING = ("doubleclick", "googleads", "google-analytics", "liveperson",
            "visualwebsiteoptimizer", "facebook", "tiktok", "youtube", "line.me",
            "instagram", "bing.com", "clarity.ms", "hotjar", "zendesk", "facebook")

# distinct source families (assignment §3); ranked, and a batch must draw from
# at least three families per priority OEM whenever the discovery layer offers them
FAMILY_HINTS = (("price_document", r"price|pricelist|ราคา"),
                ("downloadable_pdf", r"\.pdf|brochure|catalog|collection|leaflet"),
                ("grade_configurator", r"configurator|configure|grade|trim|equipment|spec"),
                ("structured_payload", r"\.json|api\.|/api/|\.smap"),
                ("official_press", r"news|press|newsroom|article"),
                ("model_lineup", r"model|models|vehicles|/cars|/range|lineup|pap/_"))
FAMILY_ORDER = {"price_document": 0, "downloadable_pdf": 1, "grade_configurator": 2,
                "structured_payload": 3, "official_press": 4, "model_lineup": 5,
                "other": 6}


def family(url: str) -> str:
    low = url.lower()
    for name, pat in FAMILY_HINTS:
        if re.search(pat, low):
            return name
    return "other"


def safe_name(brand: str, url: str) -> str:
    path = urllib.parse.urlparse(url).path.rstrip("/")
    slug = urllib.parse.unquote(path.split("/")[-1] or "index")
    if not slug.lower().endswith((".html", ".pdf", ".json", ".xml")):
        slug = (slug + ".pdf") if url.lower().split("?")[0].endswith(".pdf") else slug + ".html"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", slug).strip("_")[:60] or "page"
    base = brand.lower().replace("-", "_")
    stem, ext = os.path.splitext(slug)
    name = f"{base}_p108_{stem}{ext}"
    n = 1
    while os.path.exists(os.path.join(FIXTURE_DIR, name)):
        n += 1
        name = f"{base}_p108_{stem}_dup{n}{ext}"
    return name


def nrm(url: str):
    m = re.match(r"https?://([^/?#]+)([^?#]*)", url)
    if not m:
        return None
    host = m.group(1).lower().replace("www.", "")
    path = re.sub(r"^/(en|th|en_TH|th_TH)(?=/)", "", m.group(2).rstrip("/") or "/")
    return host, re.sub(r"-(en|th)$", "", path)


def committed_norm() -> set:
    known = set()
    for fn in os.listdir(FIXTURE_DIR):
        if fn.endswith(".prov.json"):
            try:
                u = json.load(open(os.path.join(FIXTURE_DIR, fn), encoding="utf-8"))["source_url"]
                key = nrm(u.split("#")[0])
                if key:
                    known.add(key)
            except Exception:
                continue
    for inv in ("p107_source_inventory.json", "p106_capture_log.json", "p103_first_party_catalog.json"):
        p = os.path.join(OUT, inv)
        if not os.path.exists(p):
            continue
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        for key in ("entries", "results", "candidates"):
            for e in data.get(key) or []:
                u = e.get("url") or e.get("source_url")
                if isinstance(u, str):
                    k = nrm(u.split("#")[0])
                    if k:
                        known.add(k)
    return known


def pdftext(content: bytes) -> tuple[str, str]:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        fh.write(content)
        pdf_path = fh.name
    txt_path = pdf_path + ".txt"
    try:
        subprocess.run(["pdftotext", "-layout", pdf_path, txt_path],
                       check=False, capture_output=True, timeout=60)
        if os.path.exists(txt_path):
            with open(txt_path, encoding="utf-8", errors="ignore") as fh:
                return fh.read(), "http_get_pdf_pdftotext"
    except Exception:
        pass
    finally:
        for p in (pdf_path, txt_path):
            if os.path.exists(p):
                os.unlink(p)
    return "", "http_get_pdf_pdftotext"


def load_candidates() -> dict:
    with open("/tmp/p108_new_paths.json", encoding="utf-8") as fh:
        raw = json.load(fh)
    out = {}
    for brand, rows in raw.items():
        seen, keep = set(), []
        for row in rows:
            u = row["url"]
            key = nrm(u)
            if not key or key in seen:
                continue
            seen.add(key)
            keep.append({"url": u, "family": family(u), "channel": row.get("channel", "index")})
        out[brand] = keep
    return out


def main() -> int:
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    candidates = load_candidates()
    known = committed_norm()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "th-TH,th;q=0.9"})

    inventory, capture_log = [], []
    total = 0
    for brand in sorted(PRIORITY, key=lambda b: -TARGET_DEFICIT.get(b, 0)):
        rows = [r for r in candidates.get(brand, [])
                if nrm(r["url"]) not in known
                and not any(t in r["url"].lower() for t in TRACKING)]
        # one pick per family first, then fill by rank — distinct families, no
        # duplicate path, no locale mirror
        picked, rest = [], []
        for fam in sorted(FAMILY_ORDER, key=lambda f: FAMILY_ORDER[f]):
            same = sorted([r for r in rows if r["family"] == fam], key=lambda r: r["url"])
            if same:
                picked.append(same[0])
                rest.extend(same[1:])
        picked.extend(sorted(rest, key=lambda r: (FAMILY_ORDER.get(r["family"], 6), r["url"])))
        for row in picked[:PER_OEM_CAP]:
            if total >= GLOBAL_CAP:
                break
            total += 1
            url = row["url"]
            entry = {"brand": brand, "url": url, "source_family": row["family"],
                     "discovery_channel": row["channel"],
                     "deficit_at_baseline": TARGET_DEFICIT.get(brand)}
            if any(b.lower() in url.lower() for b in BLOCKED_HOSTS):
                entry.update(status="BLOCKED_HOST", ok=False,
                             blocker="blocked OEM brand token in URL; never requested")
                inventory.append(entry)
                continue
            try:
                resp = session.get(url, timeout=25, allow_redirects=True)
            except Exception as exc:
                entry.update(status="ERROR", ok=False,
                             blocker=f"{type(exc).__name__}: {exc}")
                inventory.append(entry)
                capture_log.append({"brand": brand, "url": url, "source_family": row["family"],
                                    "ok": False, "error": entry["blocker"]})
                time.sleep(POLITENESS_S)
                continue
            entry["http_status"] = resp.status_code
            if resp.status_code != 200:
                entry.update(status="HTTP_ERROR", ok=False,
                             blocker=f"HTTP_{resp.status_code} after redirects")
                inventory.append(entry)
                capture_log.append({"brand": brand, "url": url, "source_family": row["family"],
                                    "ok": False, "error": entry["blocker"]})
                time.sleep(POLITENESS_S)
                continue
            final_url = resp.url
            ctype = (resp.headers.get("Content-Type") or "").lower()
            is_pdf = "pdf" in ctype or final_url.lower().split("?")[0].endswith(".pdf")
            filename = safe_name(brand, final_url)
            if is_pdf:
                text, method = pdftext(resp.content)
                if len(text.strip()) < 200:
                    entry.update(status="SOURCE_DROPPED", ok=False,
                                 blocker="PDF has no usable text layer (image-only or not a PDF)")
                    inventory.append(entry)
                    capture_log.append({"brand": brand, "url": url, "source_family": row["family"],
                                        "ok": False, "error": entry["blocker"]})
                    time.sleep(POLITENESS_S)
                    continue
                content, size = text, len(text)
            else:
                method, content = "http_get", resp.text.replace("\r\n", "\n").replace("\r", "\n")
                size = len(content)
            try:
                prov = AcquisitionWriter.write(content=content, source_url=final_url,
                                               acquisition_method=method,
                                               output_dir=FIXTURE_DIR, filename=filename,
                                               session_id=SESSION_ID)
            except Exception as exc:
                entry.update(status="WRITE_ERROR", ok=False,
                             blocker=f"{type(exc).__name__}: {exc}")
                inventory.append(entry)
                time.sleep(POLITENESS_S)
                continue
            entry.update(status="CAPTURED", ok=True, artifact=filename, sha256=prov.get("sha256"),
                         bytes=size, final_url=final_url, content_type=ctype[:60],
                         usable=size > 2000, blocker="")
            inventory.append(entry)
            capture_log.append({"brand": brand, "url": url, "final_url": final_url,
                                "source_family": row["family"], "discovery_channel": row["channel"],
                                "filename": filename, "ok": True, "sha256": prov.get("sha256"),
                                "bytes": size})
            time.sleep(POLITENESS_S)
        if total >= GLOBAL_CAP:
            break

    attempted = {e["brand"] for e in inventory}
    for brand in PRIORITY:
        if brand not in attempted:
            inventory.append({"brand": brand, "url": None, "source_family": None,
                              "status": "NO_CANDIDATE", "ok": False,
                              "deficit_at_baseline": TARGET_DEFICIT.get(brand),
                              "blocker": "external discovery (sitemap index / search index / "
                                         "certificate transparency / press index) surfaced no "
                                         "new official Thai-market URL that was not already a "
                                         "P107 or earlier artifact"})

    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(os.path.join(OUT, "p108_source_inventory.json"), "w", encoding="utf-8") as fh:
        json.dump({"artifact": "p108_source_inventory/1", "generated_at": stamp,
                   "session_id": SESSION_ID,
                   "method": "external discovery only: robots+sitemap indexes, sitemap endpoints, "
                             "certificate-transparency subdomains, search index, official press "
                             "indexes; de-duplicated by normalized (host, locale-stripped path) "
                             "against every P102-P107 capture; families ranked "
                             "price/pdf/configurator/api/press/lineup",
                   "target_deficit": TARGET_DEFICIT, "attempted": total,
                   "captured": sum(1 for e in inventory if e.get("ok")),
                   "entries": inventory}, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(os.path.join(OUT, "p108_capture_log.json"), "w", encoding="utf-8") as fh:
        json.dump({"artifact": "p108_capture_log/1", "generated_at": stamp,
                   "session_id": SESSION_ID, "results": capture_log}, fh,
                  ensure_ascii=False, indent=2)
        fh.write("\n")
    ok = sum(1 for e in capture_log if e.get("ok"))
    print(f"attempted={total} captured={ok} failed={len(capture_log) - ok}")
    fam = {}
    for e in capture_log:
        fam.setdefault(e.get("source_family"), [0, 0])
        fam[e.get("source_family")][0 if e.get("ok") else 1] += 1
    print("families ok/fail:", json.dumps(fam))
    for e in capture_log:
        mark = "ok  " if e.get("ok") else "FAIL"
        print(f"  {mark} {e['brand']:11s} {str(e.get('source_family')):20s} "
              f"{(e.get('filename') or e.get('error', ''))[:52]:52s} {e['url'][:66]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
