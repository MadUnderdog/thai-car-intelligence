#!/usr/bin/env python3
"""P111 — one bounded price-source discovery + acquisition batch.

Phase 1 (discover): build ONE inventory of official current Thai price sources
for the OEMs that still have UNVERIFIED_PRICE rows after P110.  Channels:
stored sitemap/search pools from the P108 discovery run, plus fresh
robots.txt + sitemap-index fetches for hosts whose stored pool is thin.  Every
candidate is de-duplicated against every URL already captured (normalized host
+ locale-stripped path) and blocked OEMs are never contacted.

Phase 2 (acquire): one acquisition batch over the inventory — one polite GET
per URL, no retry, AcquisitionWriter + .prov.json + SHA for every capture,
PDF payloads converted to text with pdftotext so the credential sanitizer can
never corrupt them.  No price is read here; the price pass runs afterwards.
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
SESSION_ID = "p111_price_sources_20260928"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
POLITENESS_S = 0.4
GLOBAL_CAP = 140
PER_OEM_CAP = 14

# unverified rows left by P110 (reconciliation), driving discovery priority
UNVERIFIED = {"Porsche": 69, "Honda": 27, "Nissan": 23, "GWM": 22, "MINI": 15,
              "Lexus": 11, "Mazda": 8, "Isuzu": 7, "MG": 7, "BMW": 6,
              "Changan": 4, "Deepal": 4, "Mitsubishi": 4, "Kia": 3, "Toyota": 2,
              "Subaru": 1, "Suzuki": 1}
PRIORITY = sorted(UNVERIFIED, key=lambda b: -UNVERIFIED[b])
BLOCKED = {"BYD", "Audi", "Chevrolet", "Ford", "Tesla", "Chery", "Haval", "NETA",
           "Peugeot", "Volvo", "Avance", "Mercedes-Benz", "Smart"}

HOSTS = {
    "Porsche": ["porsche.com"],
    "Honda": ["honda.co.th"], "Nissan": ["nissan.co.th"], "GWM": ["gwm.co.th"],
    "MINI": ["mini.co.th"], "Lexus": ["lexus.co.th"], "Mazda": ["mazda.co.th"],
    "Isuzu": ["isuzu-tis.com", "isuzu.co.th"], "MG": ["mgcars.com"],
    "BMW": ["bmw.co.th"], "Changan": ["changan.co.th"], "Deepal": ["changan.co.th"],
    "Mitsubishi": ["mitsubishi-motors.co.th"], "Kia": ["kia.com"],
    "Toyota": ["toyota.co.th"], "Subaru": ["subaru.asia"], "Suzuki": ["suzuki.co.th"],
}
# Thai-market relevance per brand (a URL outside this scope is not a TH price source)
TH_SCOPE = {
    "Porsche": r"(pap/_thailand_|/th/|en-TH|/thailand|_thailand_)",
    "Kia": r"(/th/)", "BMW": r"(\.co\.th)", "Subaru": r"(_th|/th/|brochures/.*th)",
}
MODEL_SLUGS = {
    "Porsche": ["718", "911", "cayenne", "macan", "panamera", "taycan"],
    "Honda": ["accord", "br-v", "cr-v", "city", "civic", "hr-v", "step-wgn", "wr-v"],
    "Nissan": ["almera", "kicks", "navara", "serena", "x-trail"],
    "GWM": ["haval-h6", "tank-300", "tank-500", "poer", "sahar"],
    "MINI": ["cooper", "aceman", "countryman", "convertible", "john-cooper", "jcw"],
    "Lexus": ["lm", "lx", "nx", "rx"],
    "Mazda": ["mazda3", "bt-50", "bt50"],
    "Isuzu": ["d-max", "dmax", "mu-x", "mux"],
    "MG": ["mg3", "mg-3", "urban", "mgs5", "mg5", "ep"],
    "BMW": ["m2", "m3", "m5", "xm"],
    "Changan": ["nevo", "q05"],
    "Deepal": ["e07", "s05", "s07", "deepal"],
    "Mitsubishi": ["triton", "mirage"],
    "Kia": ["ev5"],
    "Toyota": ["yaris"],
    "Subaru": ["brz"],
    "Suzuki": ["xl7"],
}
PRICE_PAT = re.compile(r"(price|pricelist|price-list|price_list|ราคา|all-models-price|"
                       r"shopping-tools|configurator|configure|/buy|/deal|/price)", re.I)
MODEL_PAGE_PAT = re.compile(r"(/models?/|/vehicles/|/cars/|/range/|showroom|"
                            r"/model/|specification|/spec)", re.I)
NEGATIVE_PAT = re.compile(r"(accessor|faq|service|dealer|news|promotion|campaign|career|"
                          r"contact|test-drive|charging|owner|manual|recall|warranty|"
                          r"finance-calculator|brochure-request|request-brochure|"
                          r"comparison|design|feature|after-sales|insurance|"
                          r"how-to|video|parts|policy|privacy|terms|sitemap|\.js|\.css|"
                          r"cdn|tracking|404|search|content-hub|tips-|charging|"
                          r"driving-experience|showroom-locator|find-showroom)", re.I)
FAMILY = (
    ("price_document", r"price|pricelist|ราคา"),
    ("grade_table", r"grade|trim|variant|/deal/|shopping-tools"),
    ("configurator", r"configurator|configure"),
    ("structured_payload", r"\.json|/api/|\.smap|\.xml"),
    ("model_page", r"/models?/|/vehicles/|/cars/|/range/|showroom|specification"),
    ("downloadable_pdf", r"\.pdf"),
)
SITEMAP_HINTS = ("/sitemap.xml", "/sitemap_index.xml", "/robots.txt",
                 "/sitemap.txt", "/sitemap.xml.gz")
# brand-specific structured endpoints discovered by probing (documented channel)
EXPLICIT_SITEMAPS = {
    "Porsche": ["https://www.porsche.com/pap/_thailand_/Sitemap.smap"],
    "MG": ["https://www.mgcars.com/sitemap.xml"],
    "Isuzu": ["https://www.isuzu-tis.com/sitemap.xml"],
    "Changan": ["https://www.changan.co.th/sitemap.xml"],
    "Deepal": ["https://www.changan.co.th/sitemap.xml"],
    "Toyota": ["https://www.toyota.co.th/sitemap.xml",
               "https://www.toyota.co.th/sitemap_index.xml"],
}
# official model URLs that carry grade prices but are not listed in any sitemap
# (each was probed for HTTP 200 before being recorded here)
KNOWN_OFFICIAL_PATTERNS = {
    # Honda has no sitemap; these slugs came from the /en/ page navigation and
    # were each probed for HTTP 200 before being recorded.
    "Honda": ["https://www.honda.co.th/en/models", "https://www.honda.co.th/en/crv",
              "https://www.honda.co.th/en/hrvehev", "https://www.honda.co.th/en/accordehev",
              "https://www.honda.co.th/en/brv", "https://www.honda.co.th/en/cityhatchback",
              "https://www.honda.co.th/en/stepwgnehev", "https://www.honda.co.th/en/wrv",
              "https://www.honda.co.th/en/civic", "https://www.honda.co.th/en/city"],
    "Toyota": ["https://www.toyota.co.th/model/yarisativ"],
    "MG": ["https://www.mgcars.com/th/cars/all-new-mg3",
           "https://www.mgcars.com/th/cars/mg-ep-plus",
           "https://www.mgcars.com/th/cars/mg-hs",
           "https://www.mgcars.com/th/cars/mg-zs",
           "https://www.mgcars.com/th/cars/mg-es",
           "https://www.mgcars.com/th/cars/mg5"],
}


def family(url: str) -> str:
    low = url.lower()
    for name, pat in FAMILY:
        if re.search(pat, low):
            return name
    return "other"


def nrm(url: str):
    m = re.match(r"https?://([^/?#]+)([^?#]*)", url or "")
    if not m:
        return None
    host = m.group(1).lower().replace("www.", "")
    path = re.sub(r"^/(en|th|en_TH|th_TH|th-TH)(?=/)", "", m.group(2).rstrip("/") or "/")
    return host, re.sub(r"-(en|th)$", "", path)


def known_urls() -> set:
    known = set()
    for fn in os.listdir(FIXTURE_DIR):
        if fn.endswith(".prov.json"):
            try:
                u = json.load(open(os.path.join(FIXTURE_DIR, fn), encoding="utf-8"))["source_url"]
                k = nrm(u.split("#")[0])
                if k:
                    known.add(k)
            except Exception:
                continue
    for inv in ("p110_price_reconciliation.json", "p110_price_evidence.json",
                "p109_current_market_inventory.json", "p108_source_inventory.json",
                "p107_source_inventory.json", "p106_capture_log.json"):
        p = os.path.join(OUT, inv)
        if not os.path.exists(p):
            continue
        for u in re.findall(r"https?://[^\"\\\s]+", open(p, encoding="utf-8").read()):
            k = nrm(u.rstrip(","))
            if k:
                known.add(k)
    return known


def brand_of(url: str):
    host = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
    for brand, hosts in HOSTS.items():
        if any(host == h or host.endswith("." + h) for h in hosts):
            return brand
    return None


def in_scope(brand: str, url: str) -> bool:
    pat = TH_SCOPE.get(brand)
    if pat and not re.search(pat, url, re.I):
        # host itself is a country domain (co.th) → already Thai market
        if not re.search(r"\.co\.th$", urllib.parse.urlparse(url).netloc.lower()):
            return False
    return True


def scored(brand: str, url: str):
    path = urllib.parse.urlparse(url).path.lower()
    if NEGATIVE_PAT.search(path):
        return None
    if PRICE_PAT.search(url):
        return "price_url"
    for slug in MODEL_SLUGS.get(brand, []):
        if re.search(r"(^|[-_/])" + re.escape(slug) + r"([-_/]|\.|$)", path):
            return "model_page"
    return None


EXTRA_SITEMAPS: list = []


def sitemap_urls(sess, root: str, budget: int = 600):
    """robots.txt → sitemap indexes (bounded) → <loc> URLs."""
    out = []
    try:
        r = sess.get(root + "/robots.txt", timeout=15)
    except Exception:
        r = None
    maps = []
    if r is not None and r.status_code == 200:
        maps = re.findall(r"(?im)^sitemap:\s*(\S+)", r.text)
    maps = [m for m in maps if m.startswith("http")][:6]
    if not maps:
        maps = [root + h for h in SITEMAP_HINTS[:2]]
    for extra in EXTRA_SITEMAPS:
        if extra not in maps:
            maps.insert(0, extra)
    seen = set()
    for sm in maps:
        if sm in seen or len(out) >= budget:
            continue
        seen.add(sm)
        try:
            resp = sess.get(sm, timeout=20)
        except Exception:
            continue
        if resp.status_code != 200:
            continue
        text = resp.text
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)
        # sitemap index → one level deeper
        if re.search(r"<sitemapindex", text, re.I):
            for child in locs[:8]:
                if len(out) >= budget:
                    break
                try:
                    c = sess.get(child, timeout=20)
                except Exception:
                    continue
                if c.status_code == 200:
                    out.extend(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", c.text))
                time.sleep(POLITENESS_S)
        else:
            out.extend(locs)
        time.sleep(POLITENESS_S)
    # sitemap.txt style
    return out[:budget]


def discover(sess, known) -> list:
    pool = []
    for p in ("/tmp/p108_sitemap_urls.json", "/tmp/p108_discovered_urls.json"):
        if os.path.exists(p):
            try:
                pool.extend(json.load(open(p, encoding="utf-8")))
            except Exception:
                pass
    entries = []
    seen = set()
    for brand in PRIORITY:
        rows = []
        global EXTRA_SITEMAPS
        EXTRA_SITEMAPS = list(EXPLICIT_SITEMAPS.get(brand, []))
        for u in KNOWN_OFFICIAL_PATTERNS.get(brand, []):
            k = nrm(u)
            if k and k not in seen and k not in known:
                seen.add(k)
                rows.append({"brand": brand, "url": u, "source_family": family(u),
                             "discovery_channel": "known_official_pattern",
                             "match": "price_url", "note": "official model URL that "
                             "publishes grade prices (probed HTTP 200)",
                             "unverified_at_baseline": UNVERIFIED[brand]})
        for u in pool:
            if brand_of(u) != brand:
                continue
            if not in_scope(brand, u):
                continue
            tag = scored(brand, u)
            if not tag:
                continue
            k = nrm(u)
            if not k or k in seen or k in known:
                continue
            seen.add(k)
            rows.append({"brand": brand, "url": u, "source_family": family(u),
                         "discovery_channel": "stored_pool_p108", "match": tag,
                         "unverified_at_baseline": UNVERIFIED[brand]})
        # fresh robots/sitemap for hosts whose stored pool yielded little
        if len(rows) < 3 or EXPLICIT_SITEMAPS.get(brand):
            for h in HOSTS[brand]:
                if any(e["brand"] == brand and e.get("channel_root") == h for e in entries):
                    continue
                for root in (f"https://www.{h}", f"https://{h}"):
                    locs = sitemap_urls(sess, root)
                    if not locs:
                        continue
                    added_here = 0
                    for u in locs:
                        if not in_scope(brand, u):
                            continue
                        tag = scored(brand, u)
                        if not tag:
                            continue
                        k = nrm(u)
                        if not k or k in seen or k in known:
                            continue
                        seen.add(k)
                        added_here += 1
                        rows.append({"brand": brand, "url": u, "source_family": family(u),
                                     "discovery_channel": "fresh_sitemap_index",
                                     "channel_root": h, "match": tag,
                                     "unverified_at_baseline": UNVERIFIED[brand]})
                    if added_here:
                        break
        # price_url first, then model pages; deterministic order
        rows.sort(key=lambda r: (0 if r["match"] == "price_url" else 1, r["url"]))
        entries.extend(rows)
    return entries


def pdftext(content: bytes):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        fh.write(content)
        pdf_path = fh.name
    txt_path = pdf_path + ".txt"
    try:
        subprocess.run(["pdftotext", "-layout", pdf_path, txt_path],
                       check=False, capture_output=True, timeout=60)
        if os.path.exists(txt_path):
            with open(txt_path, encoding="utf-8", errors="ignore") as fh:
                return fh.read()
    except Exception:
        pass
    finally:
        for p in (pdf_path, txt_path):
            if os.path.exists(p):
                os.unlink(p)
    return ""


def safe_name(brand: str, url: str) -> str:
    path = urllib.parse.urlparse(url).path.rstrip("/")
    slug = urllib.parse.unquote(path.split("/")[-1] or "index")
    if not slug.lower().endswith((".html", ".pdf", ".json", ".xml")):
        slug = (slug + ".pdf") if url.lower().split("?")[0].endswith(".pdf") else slug + ".html"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", slug).strip("_")[:60] or "page"
    stem, ext = os.path.splitext(slug)
    base = brand.lower().replace("-", "_")
    name = f"{base}_p111_{stem}{ext}"
    n = 1
    while os.path.exists(os.path.join(FIXTURE_DIR, name)):
        n += 1
        name = f"{base}_p111_{stem}_dup{n}{ext}"
    return name


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "th-TH,th;q=0.9"})

    inv_path = os.path.join(OUT, "p111_price_source_inventory.json")
    if phase in ("discover", "all"):
        known = known_urls()
        entries = discover(sess, known)
        # one bounded selection for the batch: price hits first per OEM
        picked, per = [], {}
        for e in entries:
            if per.get(e["brand"], 0) >= PER_OEM_CAP:
                continue
            per[e["brand"]] = per.get(e["brand"], 0) + 1
            picked.append(dict(e, selected=True))
            if len(picked) >= GLOBAL_CAP:
                break
        for e in entries:
            if e not in picked:
                e.update(selected=False,
                         reason="beyond per-OEM/global cap for this bounded batch")
        payload = {"artifact": "p111_price_source_inventory/1", "generated_at": stamp,
                   "session_id": SESSION_ID,
                   "method": "ONE inventory for the P111 price-source batch: stored "
                             "P108 sitemap/search pools + fresh robots/sitemap-index "
                             "fetches, filtered to official TH-market price sources and "
                             "the unverified models, de-duplicated by normalized "
                             "(host, locale-stripped path) against every existing capture",
                   "unverified_baseline": UNVERIFIED,
                   "candidates": len(entries), "selected": len(picked),
                   "entries": sorted(picked + [e for e in entries if e not in picked],
                                     key=lambda e: (e["brand"], not e.get("selected"),
                                                    e["url"]))}
        with open(inv_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"discover: candidates={len(entries)} selected={len(picked)}")
        if phase == "discover":
            return 0

    inv = json.load(open(inv_path, encoding="utf-8"))
    selected = [e for e in inv["entries"] if e.get("selected")]
    known = known_urls()
    results, log = [], []
    for e in selected:
        url = e["url"]
        entry = dict(e)
        if any(b.lower() in url.lower() for b in BLOCKED):
            entry.update(status="BLOCKED_HOST", ok=False,
                         blocker="blocked OEM token in URL; never requested")
            results.append(entry)
            continue
        try:
            resp = sess.get(url, timeout=25, allow_redirects=True)
        except Exception as exc:
            entry.update(status="ERROR", ok=False, blocker=f"{type(exc).__name__}: {exc}")
            results.append(entry)
            log.append({"brand": e["brand"], "url": url, "ok": False,
                        "error": entry["blocker"]})
            time.sleep(POLITENESS_S)
            continue
        entry["http_status"] = resp.status_code
        if resp.status_code != 200:
            entry.update(status="HTTP_ERROR", ok=False,
                         blocker=f"HTTP_{resp.status_code} after redirects")
            results.append(entry)
            log.append({"brand": e["brand"], "url": url, "ok": False,
                        "error": entry["blocker"]})
            time.sleep(POLITENESS_S)
            continue
        final_url, ctype = resp.url, (resp.headers.get("Content-Type") or "").lower()
        is_pdf = "pdf" in ctype or final_url.lower().split("?")[0].endswith(".pdf")
        filename = safe_name(e["brand"], final_url)
        if is_pdf:
            text = pdftext(resp.content)
            if len(text.strip()) < 200:
                entry.update(status="SOURCE_DROPPED", ok=False,
                             blocker="PDF has no usable text layer")
                results.append(entry)
                time.sleep(POLITENESS_S)
                continue
            content, size, method = text, len(text), "http_get_pdf_pdftotext"
        else:
            method = "http_get"
            content = resp.text.replace("\r\n", "\n").replace("\r", "\n")
            size = len(content)
        if nrm(final_url.split("#")[0]) in known and any(
                rr.get("ok") for rr in results if rr.get("final_url")):
            pass  # same URL captured earlier in this batch: allowed, unique filename
        try:
            prov = AcquisitionWriter.write(content=content, source_url=final_url,
                                           acquisition_method=method,
                                           output_dir=FIXTURE_DIR, filename=filename,
                                           session_id=SESSION_ID)
        except Exception as exc:
            entry.update(status="WRITE_ERROR", ok=False,
                         blocker=f"{type(exc).__name__}: {exc}")
            results.append(entry)
            time.sleep(POLITENESS_S)
            continue
        entry.update(status="CAPTURED", ok=True, artifact=filename,
                     sha256=prov.get("sha256"), bytes=size, final_url=final_url,
                     content_type=ctype[:60], blocker="")
        results.append(entry)
        log.append({"brand": e["brand"], "url": url, "final_url": final_url,
                    "source_family": e["source_family"], "filename": filename,
                    "ok": True, "sha256": prov.get("sha256"), "bytes": size})
        time.sleep(POLITENESS_S)

    with open(os.path.join(OUT, "p111_price_capture_log.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"artifact": "p111_price_capture_log/1", "generated_at": stamp,
                   "session_id": SESSION_ID,
                   "new_captures": sum(1 for r in log if r.get("ok")),
                   "results": log,
                   "failures": [r for r in results if not r.get("ok")]},
                  fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    inv["acquisition"] = {"attempted": len(selected),
                          "captured": sum(1 for r in log if r.get("ok")),
                          "failed": sum(1 for r in results if not r.get("ok"))}
    with open(inv_path, "w", encoding="utf-8") as fh:
        json.dump(inv, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    ok = sum(1 for r in log if r.get("ok"))
    print(f"acquire: attempted={len(selected)} captured={ok} failed={len(results) - ok}")
    fam: dict = {}
    for r in log:
        # failure rows carry no source_family/filename (they never captured) —
        # the summary must read them defensively or the run crashes AFTER both
        # artifacts are already written (observed as a post-write KeyError).
        key = r.get("source_family") or "unknown"
        fam.setdefault(key, [0, 0])
        fam[key][0 if r.get("ok") else 1] += 1
    print("families ok/fail:", json.dumps(fam))
    for r in log:
        print(f"  {'ok  ' if r.get('ok') else 'fail'} {r['brand']:11s} "
              f"{(r.get('source_family') or '-'):18s} "
              f"{(r.get('filename') or '-')[:46]:46s} {r['url'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
