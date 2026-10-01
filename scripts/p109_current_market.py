#!/usr/bin/env python3
"""P109 — current Thai-market canonical catalog (one bounded pass).

P102–P108 are frozen audit history: this driver never rewrites them and never
chases the enumerator deficit.  It answers one question instead — for the
*current* Thai market, what does first-party MARKET_TRUTH actually publish —
and classifies every candidate as

    CURRENT_CONFIRMED | HISTORICAL_OR_STALE_CANDIDATE
    UNRESOLVED_IDENTITY_ONLY | CONFLICT

with the evidence and reason for each decision stored in Phase-1 audit
artifacts.  A P109-only evidence tier (`CURRENT_SEMANTIC_GRADE` /
`CURRENT_SEMANTIC_MODEL`) is allowed when a *current* official page publishes
model + exact label as a heading/card but the accepted extractor found no
table row; those rows are recorded here and never enter the accepted ledger
(P108 stays 488), never touch the verifier, Prisma, API or production DB, and
a price is never read, stored or verified (price_pass stays false).

Boundaries: blocked hosts are never contacted, no new network access happens
in this driver, ambiguous prose / shared generic tokens / cross-model labels /
historical articles / image-only scans are never accepted as identity proof.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "audit/coverage")
FIXTURE_DIR = os.path.join(REPO, "tests/fixtures/oem-artifacts")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ACCEPTED_LEDGER = 488          # P108 — frozen, never changed by this wave
ACCEPTED_BASELINE_ARTIFACT = "audit/coverage/p108_final_result.json"
BLOCKED_ACCESS = {"BLOCKED_HTTP_403", "BLOCKED_HTTP_404", "BLOCKED_DNS",
                  "BLOCKED_TLS", "DEALER_REDIRECT"}

STALE_MARK = re.compile(
    r"(discontinued|no longer available|เลิกจำหน้าง|รุ่นเก่า|previous generation|"
    r"archived|ยกเลิกการผลิต|model year 202[0-4]\b)", re.I)
GENERIC_LABEL = re.compile(
    r"^(max|hev|phev|ev|gt|rs|plus|ultra|sport|eco|diesel|petrol|turbo|smart|"
    r"premium|exclusive|eloquent|excite|technic|elite|essence|essential|el|e|"
    r"l|s|x|v|d|swb|lwb|single cab|king cab|double cab)$", re.I)
PROMO_MARK = re.compile(r"(\d+\s*%|promotion|โปรโมช|ฟรี|ของแถม|ส่วนลด)", re.I)

HOST2BRAND = {"mazda.co.th": "Mazda", "nissan.co.th": "Nissan", "porsche.co.th": "Porsche",
              "porsche.com": "Porsche", "mgcars.com": "MG", "honda.co.th": "Honda",
              "mitsubishi-motors.co.th": "Mitsubishi", "subaru.asia": "Subaru",
              "gwm.co.th": "GWM", "changan.co.th": "Changan", "deepal.co.th": "Deepal",
              "toyota.co.th": "Toyota", "mini.co.th": "MINI", "jaguar.co.th": "Jaguar",
              "landrover.co.th": "Land Rover", "isuzu.co.th": "Isuzu", "isuzu-tis.com": "Isuzu",
              "suzuki.co.th": "Suzuki", "lexus.co.th": "Lexus", "kia.com": "Kia",
              "bmw.co.th": "BMW", "cdn-jaguarlandrover.com": "Land Rover",
              "smart.co.th": "Smart", "avance.co.th": "Avance",
              "cdn-jaguarlandrover.com": "Land Rover"}
FILE_PREFIX = {"bmw": "BMW", "byd": "BYD", "audi": "Audi", "ford": "Ford", "smart": "Smart",
               "avance": "Avance", "tesla": "Tesla", "peugeot": "Peugeot", "volvo": "Volvo",
               "chery": "Chery", "haval": "Haval", "neta": "NETA", "chevrolet": "Chevrolet",
               "mercedes": "Mercedes-Benz", "gwm": "GWM", "toyota": "Toyota", "honda": "Honda",
               "mazda": "Mazda", "nissan": "Nissan", "mg": "MG", "kia": "Kia", "subaru": "Subaru",
               "suzuki": "Suzuki", "isuzu": "Isuzu", "lexus": "Lexus", "mini": "MINI",
               "jaguar": "Jaguar", "changan": "Changan", "deepal": "Deepal",
               "mitsubishi": "Mitsubishi", "porsche": "Porsche", "landrover": "Land Rover"}
CURRENT_FAMILIES = {"model_lineup", "price_document", "configurator", "spec_page", "brochure_spec"}
# domain ownership: some official domains serve more than one OEM brand
DOMAIN_OWNERS = {}
for _k, _v in HOST2BRAND.items():
    DOMAIN_OWNERS.setdefault(_k, set()).add(_v)
DOMAIN_OWNERS["changan.co.th"] |= {"Deepal"}
DOMAIN_OWNERS["cdn-jaguarlandrover.com"] |= {"Jaguar", "Land Rover"}
# first-party asset/CDN hosts that are official properties of an OEM
EXTRA_OFFICIAL_HOSTS = {"mg-upload.sgp1.cdn.digitaloceanspaces.com",
                        "cdn-jaguarlandrover.com", "assets.honda.co.th",
                        "assets.isuzu-tis.com", "api.changan.co.th",
                        "api.www.changan.co.th", "configurator.porsche.com",
                        "configure.bmw.co.th", "configure.mini.co.th",
                        "newsroom.porsche.com"}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def artifact_rows() -> list:
    """Every captured artifact with its current-market signal."""
    rows = []
    for fn in sorted(os.listdir(FIXTURE_DIR)):
        if fn.endswith(".prov.json") or "." not in fn:
            continue
        prov = os.path.join(FIXTURE_DIR, fn + ".prov.json")
        if not os.path.exists(prov):
            continue
        side = json.load(open(prov, encoding="utf-8"))
        url = side.get("source_url", "")
        if not url.startswith("https"):
            continue
        try:
            text = open(os.path.join(FIXTURE_DIR, fn), encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        rows.append({"artifact": fn, "url": url, "sha256": side.get("sha256"),
                     "captured_at": side.get("captured_at"),
                     "session_id": side.get("session_id", ""), "text": text})
    return rows


def family_of(url: str) -> str:
    low = url.lower()
    if re.search(r"(privacy|contact|career|job|login|terms|sitemap|about-us|/app|form|"
                 r"elearning|policy|shareholder|shareholder|\/ir\/|\/en\/home$|\/th$|"
                 r"\/index|404|\/error|\/dealer|\/locator)", low):
        return "utility"
    if re.search(r"(promo|/deal|/offer|/campaign|/promotion|discount)", low):
        return "promotion"
    if re.search(r"(/models?/|/vehicles/|/lineup|/range|/cars/|pap/_)", low):
        return "model_lineup"
    if re.search(r"(price|pricelist|price-list|ราคา)", low):
        return "price_document"
    if re.search(r"(configurator|configure|grade)", low):
        return "configurator"
    if re.search(r"(\.pdf|brochure|catalog)", low):
        return "brochure_spec"
    if re.search(r"(news|press|article|newsroom)", low):
        return "press"
    if re.search(r"(spec|equipment|feature)", low):
        return "spec_page"
    return "official_page"


def official_host(url: str, brand: str) -> bool:
    host = re.match(r"https?://([^/]+)", url or "")
    host = host.group(1).lower() if host else ""
    if host in EXTRA_OFFICIAL_HOSTS:
        return True
    for key, owners in DOMAIN_OWNERS.items():
        if brand in owners and (host == key or host.endswith("." + key)):
            return True
    return False


def currentness(url: str, text: str, brand: str = "") -> tuple:
    """(signal, family, reason) — separates current from historical/stale."""
    if brand and not official_host(url, brand):
        return "NOT_A_CURRENTNESS_SOURCE", "third_party", (
            "host is not an official first-party domain for this OEM "
            "(dealer-redirect / third-party mirror)")
    fam = family_of(url)
    head = (text or "")[:40000]
    if STALE_MARK.search(head):
        return "HISTORICAL", fam, "stale/discontinued marker in page text"
    if fam == "press":
        m = re.search(r"(20[0-2][0-9])", url.lower()) or re.search(r"(20[0-2][0-9])", head[:3000])
        if not m:
            return "UNDETERMINED", fam, "press item without a parseable publication date"
        year = int(m.group(1))
        return ("CURRENT" if year >= 2025 else "HISTORICAL"), fam, f"press publication year {year}"
    if fam in ("utility", "promotion"):
        return "NOT_A_CURRENTNESS_SOURCE", fam, (
            "utility page" if fam == "utility" else
            "promotional/campaign page — promotional residue, not catalog currentness")
    if fam in CURRENT_FAMILIES:
        return "CURRENT", fam, f"{fam} source (live official page/document)"
    return "CURRENT", fam, "live official site page with no stale/discontinued marker"


def brand_of(url: str, filename: str) -> str:
    stem = filename.lower()
    for key, name in FILE_PREFIX.items():
        if re.match(rf"^{re.escape(key)}(_p\d+)?[_-]", stem):
            return name
    host = re.match(r"https?://([^/]+)", url or "")
    host = host.group(1).lower() if host else ""
    for key, name in HOST2BRAND.items():
        if host == key or host.endswith("." + key):
            return name
    for key, name in FILE_PREFIX.items():
        if key in stem:
            return name
    return "?"


def lines_of(text: str) -> list:
    out = []
    for raw in (text or "").split("\n"):
        line = re.sub(r"<[^>]+>", " ", raw)
        line = re.sub(r"\s+", " ", line).strip()
        if 2 <= len(line) <= 160:
            out.append(line)
    return out


def model_slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (model or "").casefold()).strip("-")


def page_matches(url: str, model: str) -> bool:
    slug = model_slug(model)
    if not slug:
        return False
    path = (re.sub(r"https?://[^/]+", "", url) or "").casefold()
    compact_path = re.sub(r"[^a-z0-9]+", "", path)
    compact_model = re.sub(r"[^a-z0-9]+", "", model.casefold())
    return compact_model and compact_model in compact_path


def main() -> int:
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    universe = json.load(open(os.path.join(OUT_DIR, "identity_universe_p108.json"),
                              encoding="utf-8"))
    matrix0 = json.load(open(os.path.join(OUT_DIR, "identity_matrix_p108.json"),
                             encoding="utf-8"))
    records = universe["universe"]["records"]

    # ── A. artifact currentness + per-OEM source inventory ──────────────────
    art_meta = []
    for row in artifact_rows():
        brand = brand_of(row["url"], row["artifact"])
        signal, fam, reason = currentness(row["url"], row["text"], brand)
        art_meta.append({"artifact": row["artifact"], "brand": brand, "source_url": row["url"],
                         "family": fam, "currentness": signal, "currentness_reason": reason,
                         "captured_at": row["captured_at"], "sha256": row["sha256"],
                         "text": row["text"]})
    by_url_current = {}
    for a in art_meta:
        if a["currentness"] == "CURRENT":
            by_url_current.setdefault(a["source_url"].split("#")[0], a)
            # redirects/aliases: also index the captured artifact url form
            by_url_current.setdefault(a["source_url"], a)

    oem_sources = {}
    for a in art_meta:
        if a["brand"] == "?":
            continue
        bucket = oem_sources.setdefault(a["brand"], [])
        bucket.append({k: v for k, v in a.items() if k != "text"})
    for brand in oem_sources:
        oem_sources[brand].sort(key=lambda r: (r["currentness"] != "CURRENT", r["source_url"]))

    # url → currentness lookup used for record classification
    def url_signal(url: str):
        key = (url or "").split("#")[0]
        hit = by_url_current.get(key)
        if hit:
            return "CURRENT", hit["currentness_reason"]
        for a in art_meta:
            if a["source_url"].split("#")[0] == key:
                return a["currentness"], a["currentness_reason"]
        return "NO_LOCAL_ARTIFACT", "source URL has no captured artifact in this repository"

    # ── B. P109-only semantic evidence tier (current official pages) ────────
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p108harvest", os.path.join(REPO, "scripts/p108_variant_harvest.py"))
    p108 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p108)

    identity_only_variants = [r for r in records if r["status"] == "IDENTITY_ONLY" and r["variant"]]
    identity_only_models = [r for r in records if r["status"] == "IDENTITY_ONLY" and not r["variant"]]
    confirmed_pairs = {(norm(r["manufacturer"]), norm(r["model"]), norm(r["variant"]))
                       for r in records if r["status"] == "CONFIRMED_VARIANT"}
    model_owner = {}
    for r in records:
        model_owner.setdefault((norm(r["manufacturer"]), norm(r["model"])), set()).add(norm(r["variant"]))

    def candidate_variants_by_brand(brand):
        return [r for r in identity_only_variants if r["manufacturer"] == brand]

    semantic_rows = []
    semantic_models = []
    seen_sem = set()
    seen_sem_m = set()
    for a in art_meta:
        if a["currentness"] != "CURRENT" or a["brand"] == "?":
            continue
        brand_models = sorted({r["model"] for r in records if r["manufacturer"] == a["brand"]})
        _kind, page_models = p108.page_model_set(a["brand"], a["source_url"], brand_models)
        lines = lines_of(a["text"])
        # model-level: model name published on its own current page
        for rec in identity_only_models:
            if rec["manufacturer"] != a["brand"]:
                continue
            key = (norm(rec["manufacturer"]), norm(rec["model"]))
            if key in seen_sem_m:
                continue
            if page_matches(a["source_url"], rec["model"]) or \
               any(norm(rec["model"]) == norm(l) or norm(rec["model"]) in norm(l) for l in lines[:400]):
                if PROMO_MARK.search(rec["model"]):
                    continue
                seen_sem_m.add(key)
                semantic_models.append(
                    {"manufacturer": rec["manufacturer"], "model": rec["model"],
                     "published_label": rec["model"], "evidence_tier": "CURRENT_SEMANTIC_MODEL",
                     "artifact": a["artifact"], "source_url": a["source_url"],
                     "sha256": a["sha256"], "identity_level": "MODEL",
                     "currentness": "CURRENT", "currentness_reason": a["currentness_reason"],
                     "binding": "current official page publishes the model name "
                                "(URL slug match or published label on its own current page)"})
        # variant-level: model + exact label composite on a model-bound current page
        for rec in candidate_variants_by_brand(a["brand"]):
            key = (norm(rec["manufacturer"]), norm(rec["model"]), norm(rec["variant"]))
            if key in seen_sem or key in confirmed_pairs:
                continue
            if GENERIC_LABEL.match(rec["variant"].strip()):
                continue
            owners = model_owner.get((norm(rec["manufacturer"]), norm(rec["model"])), set())
            # same-model binding comes from the published line itself: it must
            # start with this model's name (composite), or the page URL must be
            # this model's dedicated page
            want = norm(rec["variant"])
            hit = None
            for line in lines:
                lnorm = norm(line)
                if PROMO_MARK.search(line):
                    continue
                if lnorm.startswith(norm(rec["model"]) + " "):
                    tail = lnorm[len(norm(rec["model"])):].strip()
                    if tail == want:
                        hit = line
                        break
                if lnorm == norm(rec["model"]) + " " + want:
                    hit = line
                    break
            if not hit:
                continue
            seen_sem.add(key)
            semantic_rows.append(
                {"manufacturer": rec["manufacturer"], "model": rec["model"], "variant": rec["variant"],
                 "published_label": hit, "evidence_tier": "CURRENT_SEMANTIC_GRADE",
                 "artifact": a["artifact"], "source_url": a["source_url"], "sha256": a["sha256"],
                 "identity_level": "VARIANT", "currentness": "CURRENT",
                 "currentness_reason": a["currentness_reason"],
                 "binding": "same-model-bound composite published by first-party: the current "
                            "official line itself starts with the model name and ends with the "
                            "exact label (URL slug match: "
                            f"{page_matches(a['source_url'], rec['model'])})",
                 "blocked_by_grade_label_blocker": bool(
                     p108.grade_label_blocker(hit, rec["variant"]))})
            if semantic_rows[-1]["blocked_by_grade_label_blocker"]:
                semantic_rows.pop()
                seen_sem.discard(key)

    semantic_pairs = {(norm(r["manufacturer"]), norm(r["model"]), norm(r["variant"]))
                      for r in semantic_rows}
    semantic_model_keys = {(norm(r["manufacturer"]), norm(r["model"])) for r in semantic_models}

    # ── C. classify every candidate (evidence + reason, no promotion) ───────
    classification = []
    for rec in records:
        key = (norm(rec["manufacturer"]), norm(rec["model"]), norm(rec["variant"]))
        sources = rec.get("sources") or []
        roles = {s.get("source_role") for s in sources}
        sigs = [url_signal(s.get("source_url", "")) for s in sources] if sources else []
        first_party_urls = [s for s in sources if s.get("source_role") == "MARKET_TRUTH"]
        current_fp = [s for s in first_party_urls
                      if url_signal(s.get("source_url", ""))[0] == "CURRENT"]
        entry = {"manufacturer": rec["manufacturer"], "model": rec["model"],
                 "variant": rec["variant"], "identity_level": rec["identity_level"],
                 "accepted_status": rec["status"], "sources": [
                     {"role": s.get("source_role"), "url": s.get("source_url")} for s in sources]}

        if rec["status"] == "CONFLICT":
            entry.update(status="CONFLICT",
                         reason="conflicting identity evidence retained as CONFLICT; "
                                "never resolved by assumption")
        elif key in semantic_pairs:
            entry.update(status="CURRENT_CONFIRMED", evidence_tier="CURRENT_SEMANTIC_GRADE",
                         reason="current official first-party page publishes this model + exact "
                                "label as a composite line (P109-only tier; accepted ledger "
                                "unchanged)")
        elif not rec["variant"] and (key[0], key[1]) in semantic_model_keys:
            entry.update(status="CURRENT_CONFIRMED", evidence_tier="CURRENT_SEMANTIC_MODEL",
                         reason="current official first-party page publishes this model name "
                                "(P109-only tier; accepted ledger unchanged)")
        elif rec["status"] in ("CONFIRMED_VARIANT", "CONFIRMED_MODEL"):
            if current_fp:
                entry.update(status="CURRENT_CONFIRMED", evidence_tier="MARKET_TRUTH_ROW",
                             reason=f"accepted first-party row whose source is current: "
                                    f"{url_signal(current_fp[0].get('source_url', ''))[1]}")
            else:
                stale_fp = [s for s in first_party_urls
                            if url_signal(s.get("source_url", ""))[0] == "HISTORICAL"]
                if stale_fp:
                    sig = url_signal(stale_fp[0].get("source_url", ""))
                    entry.update(status="HISTORICAL_OR_STALE_CANDIDATE",
                                 reason=f"first-party source is stale/historical: {sig[1]}")
                elif first_party_urls:
                    sig = url_signal(first_party_urls[0].get("source_url", ""))
                    entry.update(status="CURRENT_UNVERIFIED",
                                 reason="accepted first-party row, but currentness cannot be "
                                        f"established from its source ({sig[1]}); not counted as "
                                        "stale and not counted as current")
                else:
                    entry.update(status="CURRENT_UNVERIFIED",
                                 reason="accepted row without a local MARKET_TRUTH artifact to "
                                        "re-verify currentness")
        else:  # IDENTITY_ONLY
            if first_party_urls:
                entry.update(status="UNRESOLVED_IDENTITY_ONLY",
                             reason="first-party source confirms the identity context but does not "
                                    "publish this exact label as a bound grade row")
            elif roles & {"MEDIA_DISCOVERY", "REFERENCE", "IDENTITY_ENUMERATOR", None}:
                entry.update(status="UNRESOLVED_IDENTITY_ONLY",
                             reason="enumerator/media candidate only — no first-party grade proof; "
                                    "never treated as a missing market variant")
            else:
                entry.update(status="UNRESOLVED_IDENTITY_ONLY",
                             reason="no first-party evidence captured for this candidate")
        classification.append(entry)

    counts = {}
    for e in classification:
        counts[e["status"]] = counts.get(e["status"], 0) + 1

    # ── D. per-OEM current-market metrics ──────────────────────────────────
    mat_by_brand = {o["brand"]: o for o in matrix0["oems"]}
    oem_rows = []
    for oem in matrix0["oems"]:
        brand = oem["brand"]
        cls = [e for e in classification if e["manufacturer"] == brand]
        recs = [r for r in records if r["manufacturer"] == brand]
        sources = oem_sources.get(brand, [])
        current_sources = [s for s in sources if s["currentness"] == "CURRENT"]
        # a model is "published by first-party, current" when the current sources
        # confirm the model itself or any of its grades
        current_models = sorted({c["model"] for c in cls
                                 if c["status"] == "CURRENT_CONFIRMED"})
        current_grades = sorted({(c["model"], c["variant"]) for c in cls
                                 if c["status"] == "CURRENT_CONFIRMED" and c["variant"]})
        confirmed_current = [c for c in cls if c["status"] == "CURRENT_CONFIRMED"]
        stale = [c for c in cls if c["status"] == "HISTORICAL_OR_STALE_CANDIDATE"]
        unresolved = [c for c in cls if c["status"] == "UNRESOLVED_IDENTITY_ONLY"]
        conflicts = [c for c in cls if c["status"] == "CONFLICT"]
        access = oem.get("official_access_status", "?")
        blockers = [{"layer": b.get("layer"), "blocker": b.get("blocker")}
                    for b in (oem.get("blockers") or [])]
        if access in BLOCKED_ACCESS:
            closure = "CLOSED_BLOCKED_NO_BYPASS"
            gap = ("official Thai site unreachable by policy (no bypass); current-market "
                   "classification cannot be produced beyond enumerator/media candidates")
        elif not current_sources:
            closure = "CLOSED_NO_CURRENT_FIRST_PARTY_SOURCE"
            gap = "no current official first-party source captured for this OEM"
        elif not current_grades and not current_models:
            closure = "CLOSED_SOURCE_GAP_GRADES_NOT_PUBLISHED"
            gap = ("current official sources are captured but publish no exact "
                   "model-bound label that survives the identity rules")
        else:
            closure = "CLOSED_CURRENT_FIRST_PARTY_AS_PUBLISHED"
            gap = "classification complete for what current first-party sources publish"
        oem_rows.append({
            "brand": brand, "official_access_status": access, "closure_status": closure,
            "source_gap": gap,
            "current_sources": len(current_sources),
            "current_models_published_first_party": len(current_models),
            "current_grades_published_first_party": len(current_grades),
            "first_party_confirmed_current_rows": len(confirmed_current),
            "confirmed_current_by_tier": {
                "MARKET_TRUTH_ROW": sum(1 for c in confirmed_current
                                        if c.get("evidence_tier") == "MARKET_TRUTH_ROW"),
                "CURRENT_SEMANTIC_GRADE": sum(1 for c in confirmed_current
                                              if c.get("evidence_tier") == "CURRENT_SEMANTIC_GRADE"),
                "CURRENT_SEMANTIC_MODEL": sum(1 for c in confirmed_current
                                              if c.get("evidence_tier") == "CURRENT_SEMANTIC_MODEL")},
            "stale_historical_candidates": len(stale),
            "unresolved_candidates": len(unresolved),
            "conflicts": len(conflicts),
            "blockers": blockers,
            "current_models": current_models,
            "current_grades": [f"{m} | {v}" for m, v in current_grades],
        })

    # ── E. outputs ─────────────────────────────────────────────────────────
    def dump(name, payload):
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=False)
            fh.write("\n")

    dump("p109_current_market_inventory.json", {
        "schema": "p109_current_market_inventory/1", "generated_at": stamp,
        "frozen_baseline": ACCEPTED_BASELINE_ARTIFACT,
        "method": "currentness classification of every already-captured first-party artifact "
                  "(current model/lineup page, configurator/grade selector, current price/grade "
                  "document, current brochure/spec/press) with explicit stale/discontinued and "
                  "press-date signals; no bulk re-fetching",
        "oems": [{"brand": b, "sources": s} for b, s in sorted(oem_sources.items())],
        "totals": {
            "artifacts": len(art_meta),
            "current": sum(1 for a in art_meta if a["currentness"] == "CURRENT"),
            "historical": sum(1 for a in art_meta if a["currentness"] == "HISTORICAL"),
            "undetermined": sum(1 for a in art_meta if a["currentness"] == "UNDETERMINED"),
            "not_a_currentness_source": sum(1 for a in art_meta
                                            if a["currentness"] == "NOT_A_CURRENTNESS_SOURCE")}})

    dump("p109_current_market_evidence.json", {
        "schema": "p109_current_market_evidence/1", "generated_at": stamp,
        "tier_note": "P109-only evidence tier recorded in Phase-1 audit artifacts; the accepted "
                     "ledger is frozen at P108 (488 confirmed variants) and nothing here is "
                     "written to staging/production, the verifier, Prisma or the API",
        "new_captures_this_wave": 0,
        "rows": sorted(semantic_rows + semantic_models,
                       key=lambda r: (r["manufacturer"], r["model"], r.get("variant") or ""))})

    dump("p109_candidate_classification.json", {
        "schema": "p109_candidate_classification/1", "generated_at": stamp,
        "accepted_ledger_frozen": {"artifact": ACCEPTED_BASELINE_ARTIFACT,
                                   "confirmed_variants": ACCEPTED_LEDGER},
        "status_counts": counts,
        "definitions": {
            "CURRENT_CONFIRMED": "first-party current official page publishes model + exact "
                                 "label (accepted MARKET_TRUTH row, or the P109-only semantic "
                                 "tier on a current model-bound page)",
            "HISTORICAL_OR_STALE_CANDIDATE": "supported only by historical/discontinued/undated "
                                              "or non-current sources",
            "UNRESOLVED_IDENTITY_ONLY": "enumerator/media candidate without first-party grade "
                                         "proof — never counted as a missing market variant",
            "CONFLICT": "conflicting identity evidence retained, never resolved by assumption",
            "CURRENT_UNVERIFIED": "accepted first-party row whose source is a utility/promotional/"
                                   "undated page or has no local artifact — currentness neither "
                                   "confirmed nor claimed stale"},
        "records": classification})

    # matrix (json + md)
    matrix = {"schema": "identity_matrix_p109/1", "generated_at": stamp,
              "baseline_artifact": "audit/coverage/identity_matrix_p108.json",
              "accepted_ledger_frozen": ACCEPTED_LEDGER,
              "totals": {
                  "oems": len(oem_rows),
                  "oems_closed": sum(1 for r in oem_rows if r["closure_status"].startswith("CLOSED")),
                  "current_models_published": sum(r["current_models_published_first_party"] for r in oem_rows),
                  "current_grades_published": sum(r["current_grades_published_first_party"] for r in oem_rows),
                  "first_party_confirmed_current_rows": sum(r["first_party_confirmed_current_rows"] for r in oem_rows),
                  "stale_historical_candidates": sum(r["stale_historical_candidates"] for r in oem_rows),
                  "unresolved_candidates": sum(r["unresolved_candidates"] for r in oem_rows),
                  "conflicts": sum(r["conflicts"] for r in oem_rows),
                  "blocked_oems": sum(1 for r in oem_rows
                                      if r["closure_status"] == "CLOSED_BLOCKED_NO_BYPASS")},
              "oems": oem_rows}
    dump("identity_matrix_p109.json", matrix)

    md = ["# Identity matrix P109 — current Thai-market catalog", "",
          f"Generated {stamp} · accepted ledger frozen at P108 ({ACCEPTED_LEDGER} confirmed "
          "variants) · Phase-1 audit artifact only", "",
          "| OEM | access | closure | current src | models | grades | confirmed-current | stale | "
          "unresolved | conflicts |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(oem_rows, key=lambda x: (-x["first_party_confirmed_current_rows"], x["brand"])):
        md.append(f"| {r['brand']} | {r['official_access_status']} | {r['closure_status']} | "
                  f"{r['current_sources']} | {r['current_models_published_first_party']} | "
                  f"{r['current_grades_published_first_party']} | "
                  f"{r['first_party_confirmed_current_rows']} | {r['stale_historical_candidates']} | "
                  f"{r['unresolved_candidates']} | {r['conflicts']} |")
    md += ["", "## Totals", ""]
    for k, v in matrix["totals"].items():
        md.append(f"- **{k}**: {v}")
    with open(os.path.join(OUT_DIR, "identity_matrix_p109.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")

    evidence_digest = hashlib.sha256(
        json.dumps(sorted(semantic_rows + semantic_models,
                          key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False)),
                   sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    dump("p109_final_result.json", {
        "schema": "p109_final_result/1", "generated_at": stamp,
        "frozen_baseline": ACCEPTED_BASELINE_ARTIFACT,
        "accepted_ledger": {"confirmed_variants": ACCEPTED_LEDGER, "changed_by_p109": False},
        "current_market": {
            "current_models_published_first_party": matrix["totals"]["current_models_published"],
            "current_grades_published_first_party": matrix["totals"]["current_grades_published"],
            "first_party_confirmed_current_rows": matrix["totals"]["first_party_confirmed_current_rows"],
            "confirmed_current_by_tier": {
                "MARKET_TRUTH_ROW": sum(r["confirmed_current_by_tier"]["MARKET_TRUTH_ROW"] for r in oem_rows),
                "CURRENT_SEMANTIC_GRADE": sum(r["confirmed_current_by_tier"]["CURRENT_SEMANTIC_GRADE"] for r in oem_rows),
                "CURRENT_SEMANTIC_MODEL": sum(r["confirmed_current_by_tier"]["CURRENT_SEMANTIC_MODEL"] for r in oem_rows)}},
        "candidate_classification": counts,
        "oems": {"total": len(oem_rows),
                 "closed": sum(1 for r in oem_rows if r["closure_status"].startswith("CLOSED")),
                 "blocked": sum(1 for r in oem_rows if r["closure_status"] == "CLOSED_BLOCKED_NO_BYPASS"),
                 "by_status": dict((s, sum(1 for r in oem_rows if r["closure_status"] == s))
                                   for s in sorted({r["closure_status"] for r in oem_rows}))},
        "identity_only_records_frozen": universe["universe"]["records"] and
                                        sum(1 for r in records if r["status"] == "IDENTITY_ONLY"),
        "universe_records": len(records),
        "new_captures_this_wave": 0,
        "evidence_rows": len(semantic_rows) + len(semantic_models),
        "evidence_digest_sha256": evidence_digest,
        "gates": {"staging_written": False, "price_pass": False, "prisma_touched": False,
                  "production_db_unchanged": True, "p104_p103_p102_logic_changed": False,
                  "verifier_touched": False, "accepted_ledger_frozen": True},
        "no_loop_rule": "one bounded pass; no follow-up wave is implied by remaining "
                        "UNRESOLVED/IDENTITY_ONLY records",
    })
    print(json.dumps({"classification": counts,
                      "current_market": matrix["totals"],
                      "oems": matrix["totals"]["oems"],
                      "evidence_rows": len(semantic_rows) + len(semantic_models),
                      "new_captures": 0}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
