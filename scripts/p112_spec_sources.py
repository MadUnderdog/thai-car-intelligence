#!/usr/bin/env python3
"""P112 — target plan, source inventory and one bounded acquisition batch.

Phases (run in this order; the plan MUST exist before any harvest):

  python3 scripts/p112_spec_sources.py plan       → p112_spec_target_plan.json
  python3 scripts/p112_spec_sources.py inventory  → p112_spec_source_inventory.json
  python3 scripts/p112_spec_sources.py acquire    → p112_spec_capture_log.json

plan      — read-only audit: frozen ledger × field dictionary × candidate
            spec sources among the already-committed fixtures, classified per
            variant into P1 (variant/grade-scoped candidate exists), P2
            (model-scoped only) and P3 (no spec-bearing candidate at all).
inventory — ONE inventory: reuse candidates are pinned, and P3 gaps get a
            bounded discovery round (documented official endpoints; Toyota's
            documented grade-spec API chain is the only programmatic
            expansion: one list call → series codes that map to accepted
            models → their grade-spec payloads, all inside the same batch).
acquire   — ONE batch: one polite GET per selected URL, AcquisitionWriter +
            .prov.json + SHA + HTTPS, PDF → pdftotext -layout, blocked OEMs
            never requested, no retry.

Nothing here writes staging/Prisma/verifier/API/DB or the identity ledger.
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
SESSION_ID = "p112_spec_sources_20260928"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
POLITENESS_S = 0.4
GLOBAL_CAP = 60
ACCEPTED_LEDGER = 488
ACCEPTED_BASELINE = "audit/coverage/p108_final_result.json"

BLOCKED = {"BYD", "Audi", "Chevrolet", "Ford", "Tesla", "Chery", "Haval", "NETA",
           "Peugeot", "Volvo", "Avance", "Mercedes-Benz", "Smart"}

# Field dictionary mirrors the read-only Prisma spec models
# (VariantSpec.key / DimensionsSpec columns) — Phase-1 keys only.
FIELDS = [
    {"key": "length_mm", "unit": "mm", "numeric": True,
     "labels": ["ความยาว", "ยาว x", "ด้านยาว", "Length", "Length x",
                "Overall Length"]},
    {"key": "width_mm", "unit": "mm", "numeric": True,
     "labels": ["ความกว้าง", "กว้าง x", "Width", "Width x",
                "Overall Width"]},
    {"key": "height_mm", "unit": "mm", "numeric": True,
     "labels": ["ความสูง", "สูง x", "Height", "Height x",
                "Overall Height"]},
    {"key": "wheelbase_mm", "unit": "mm", "numeric": True,
     "labels": ["ระยะฐานล้อ", "Wheelbase"]},
    {"key": "ground_clearance_mm", "unit": "mm", "numeric": True,
     "labels": ["ความสูงจากพื้นถนน", "ระยะต่ำสุด", "Ground Clearance"]},
    {"key": "curb_weight_kg", "unit": "kg", "numeric": True,
     "labels": ["น้ำหนักรถ", "น้ำหนักตัวรถ", "Curb Weight", "Kerb Weight"]},
    {"key": "seats", "unit": "seats", "numeric": True,
     "labels": ["ที่นั่ง", "จำนวนที่นั่ง", "Seats", "Seating"]},
    {"key": "displacement_cc", "unit": "cc", "numeric": True,
     "labels": ["ความจุกระบอกสูบ", "กระบอกสูบ", "Displacement"]},
    {"key": "power_ps", "unit": "PS", "numeric": True,
     "labels": ["กำลังสูงสุด", "กำลังเครื่องยนต์", "Maximum Output", "Max Power"]},
    {"key": "torque_nm", "unit": "Nm", "numeric": True,
     "labels": ["แรงบิดสูงสุด", "แรงบิด", "Max Torque", "Torque"]},
    {"key": "battery_kwh", "unit": "kWh", "numeric": True,
     "labels": ["ความจุแบตเตอรี่", "ความจุแบต", "Battery Capacity"]},
    {"key": "charging_kw", "unit": "kW", "numeric": True,
     "labels": ["กำลังชาร์จ", "Charging Power"]},
    {"key": "range_km", "unit": "km", "numeric": True,
     "labels": ["ระยะทางขับเคลื่อนไฟฟ้า", "ระยะทางวิ่ง", "Electric Range", "Driving Range"]},
    {"key": "drivetrain", "unit": "", "numeric": False,
     "labels": ["ระบบขับเคลื่อน", "Drivetrain"]},
    {"key": "warranty", "unit": "", "numeric": False,
     "labels": ["การรับประกัน", "ระยะเวลาการรับประกัน", "Warranty"]},
]

SPEC_MARKER = re.compile(
    r"ระยะฐานล้อ|ความกว้าง|Wheelbase|ground clearance|Displacement|"
    r"Battery Capacity|กำลังสูงสุด|แรงบิด|ที่นั่ง|Seating|Specifications|สเปค",
    re.I)
SPEC_FAMILY_PAT = re.compile(
    r"(spec|brochure|catalog|equipment|feature|dimensions|technical|"
    r"คู่มือ|สมรรถนะ)", re.I)

_spec_spec = None


def p109():
    global _spec_spec
    if _spec_spec is None:
        import importlib.util
        s = importlib.util.spec_from_file_location(
            "p109_current_market",
            os.path.join(REPO, "scripts/p109_current_market.py"))
        m = importlib.util.module_from_spec(s)
        s.loader.exec_module(m)
        _spec_spec = m
    return _spec_spec


def norm(s: str) -> str:
    return re.sub(r"\s+", " ",
                  re.sub(r"[^0-9a-zก-๙]+", " ", (s or "").casefold())).strip()


def compact(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").casefold())


_p110 = None


def p110():
    global _p110
    if _p110 is None:
        import importlib.util
        s = importlib.util.spec_from_file_location(
            "p110_price_pass", os.path.join(REPO, "scripts/p110_price_pass.py"))
        m = importlib.util.module_from_spec(s)
        s.loader.exec_module(m)
        _p110 = m
    return _p110


def load_fixtures() -> dict:
    """committed artifacts (https sidecar) with their text — brochures are
    decoded through the accepted pdftotext path, never re-fetched."""
    out = {}
    pdf_text = p110().pdf_text
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
            if fn.endswith((".pdf", ".pdf.b64")):
                raw = pdf_text(os.path.join(FIXTURE_DIR, fn))
                if not raw.strip():
                    continue
            else:
                raw = open(os.path.join(FIXTURE_DIR, fn), encoding="utf-8",
                           errors="ignore").read()
        except Exception:
            continue
        out[fn] = {"artifact": fn, "url": url, "sha256": side.get("sha256"),
                   "captured_at": side.get("captured_at"),
                   "session_id": side.get("session_id", ""),
                   "provenance_state": side.get("provenance_state", ""),
                   "is_pdf": fn.endswith((".pdf", ".pdf.b64")),
                   "markers": len(SPEC_MARKER.findall(raw)), "raw": raw}
    return out


def segment_match(url: str, target: str, manufacturer: str) -> bool:
    """path-segment prefix relation between target (model or model+grade)
    and the URL — same rule P111 settled on after the contamination diff."""
    path = re.sub(r"https?://[^/]+", "", url or "").casefold()
    if not path.strip("/"):
        return False
    words = [w for w in re.split(r"[^a-z0-9]+", (target or "").casefold()) if w]
    brand_words = {w for w in re.split(r"[^a-z0-9]+",
                                      (manufacturer or "").casefold()) if w}
    stripped = [w for w in words if w not in brand_words]
    tgt = compact("".join(stripped or words))
    if not tgt:
        return False
    for seg in path.strip("/").split("/"):
        s = compact(seg)
        if s and len(s) >= 3 and (tgt.startswith(s) or s.startswith(tgt)):
            return True
    return False


def grade_in_url(url: str, variant: str) -> bool:
    """True when the URL itself names the grade (variant-scoped page)."""
    v = compact(variant)
    if len(v) < 4:
        return False
    return v in compact(re.sub(r"https?://[^/]+", "", url or ""))


def load_ledger() -> tuple:
    uni = json.load(open(os.path.join(OUT, "identity_universe_p108.json"),
                         encoding="utf-8"))
    accepted = [r for r in uni["universe"]["records"]
                if r["status"] == "CONFIRMED_VARIANT"]
    assert len(accepted) == ACCEPTED_LEDGER, len(accepted)
    matrix = json.load(open(os.path.join(OUT, "identity_matrix_p109.json"),
                            encoding="utf-8"))
    access = {o["brand"]: o["official_access_status"] for o in matrix["oems"]}
    return accepted, access


def candidate_sources(rec: dict, fixtures: dict) -> list:
    """existing committed artifacts that could carry spec evidence for rec."""
    m9 = p109()
    brand = rec["manufacturer"]
    out = []
    for fn, art in fixtures.items():
        if m9.brand_of(art["url"], fn) != brand:
            continue
        url = art["url"]
        specish = art["markers"] >= 3 or bool(
            SPEC_FAMILY_PAT.search(urllib.parse.urlparse(url).path))
        if not specish:
            continue
        if grade_in_url(url, rec["variant"]):
            scope = "variant_page"
        elif segment_match(url, rec["model"], brand):
            scope = "model_page"
        else:
            # same-brand aggregate (price/compare/index pages) may still carry
            # grade-named spec rows; the extraction pass binds row-by-row
            scope = "aggregate_page"
        out.append({
            "artifact": fn, "url": url,
            "scope": scope,
            "markers": art["markers"],
            "family_hint": ("variant_scoped_spec" if scope == "variant_page"
                            else "model_scoped_spec_or_brochure"
                            if scope == "model_page"
                            else "aggregate_with_possible_grade_rows"),
        })
    out.sort(key=lambda c: (c["scope"] != "variant_page", -c["markers"],
                            c["artifact"]))
    return out


def write_json(name: str, payload) -> None:
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


# ───────────────────────────── plan phase ─────────────────────────────────

def phase_plan() -> int:
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    accepted, access = load_ledger()
    fixtures = load_fixtures()
    rows, per_oem = [], {}
    for rec in sorted(accepted, key=lambda r: (r["manufacturer"], r["model"],
                                               r["variant"])):
        cands = candidate_sources(rec, fixtures)
        grade = [c for c in cands if c["scope"] == "variant_page"]
        model = [c for c in cands if c["scope"] == "model_page"]
        # P3 = no variant- or model-scoped page (aggregate-only or nothing):
        # only row-level grade binding could ever price spec rows there, so
        # these are the "obvious source gap" class the wave must report.
        prio = ("P1_variant_scoped_candidate" if grade else
                "P2_model_scoped_candidate" if model else
                "P3_no_scoped_spec_candidate")
        row = {"manufacturer": rec["manufacturer"], "model": rec["model"],
               "variant": rec["variant"], "priority": prio,
               "candidate_count": len(cands),
               "variant_scoped_count": len(grade),
               "model_scoped_count": len(model),
               "aggregate_only_count": len(cands) - len(grade) - len(model),
               "top_candidates": [c["artifact"] for c in cands[:6]]}
        rows.append(row)
        b = per_oem.setdefault(rec["manufacturer"],
                               {"accepted_variants": 0, "P1": 0, "P2": 0,
                                "P3": 0})
        b["accepted_variants"] += 1
        b[prio.split("_")[0]] += 1
    blocked = sorted([b for b, a in access.items() if a != "REACHABLE"])
    payload = {
        "schema": "p112_spec_target_plan/1", "generated_at": stamp,
        "session_id": SESSION_ID,
        "audit_snapshot": {
            "head": os.popen("git -C " + REPO + " rev-parse HEAD").read().strip(),
            "pr": "3 (OPEN/UNMERGED, verified before this wave)",
            "existing_spec_surface": [
                "audit/spec-coverage-plan.json = pytest coverage plan, NOT spec evidence",
                "no prior p1xx spec-evidence artifacts or spec tests exist",
                "prisma VariantSpec / DimensionsSpec / VariantSpecExtra / "
                "VariantFeature read as the field model only (read-only; never written)"],
            "fixtures_committed": len(fixtures),
            "fixtures_with_spec_markers": sum(
                1 for a in fixtures.values() if a["markers"] >= 3)},
        "baseline_artifact": ACCEPTED_BASELINE,
        "accepted_variants_targeted": ACCEPTED_LEDGER,
        "method": "ONE plan → ONE inventory → ONE acquisition batch → ONE "
                  "extraction/reconciliation → ONE validation; reuse committed "
                  "bytes first; every accepted field binds manufacturer + model "
                  + "exact variant/grade + TH scope on the same record",
        "field_dictionary": FIELDS,
        "binding_rules": [
            "variant_page: URL names model AND grade → page/section is the record",
            "grade-named table row/header: model page + grade label inside the "
            "same row/structured node is the record",
            "model-level-only spec sets are never bound to a grade (no inference)",
            "generic prose/nav/marketing/sibling models/other generations: never",
            "unit must parse for the field (mm/cc/PS/Nm/kWh/kW/km) or the row is refused",
            "a source proves only the fields it publishes; the rest stay unknown"],
        "supported_families": ["official_spec_page", "official_brochure_pdf",
                               "official_configurator_or_structured_payload",
                               "official_grade_equipment_table",
                               "official_press_with_explicit_thai_spec_identity"],
        "blocked_oems": blocked,
        "priority_counts": {k: sum(1 for r in rows if r["priority"] == k)
                            for k in ("P1_variant_scoped_candidate",
                                      "P2_model_scoped_candidate",
                                      "P3_no_scoped_spec_candidate")},
        "per_oem": per_oem,
        "variants": rows,
        "boundaries": {"staging_written": False, "prisma_touched": False,
                       "verifier_touched": False, "identity_counts_changed": False,
                       "production_db_unchanged": True,
                       "price_metrics_modified": False,
                       "ai_reconciliation": False},
    }
    write_json("p112_spec_target_plan.json", payload)
    print("plan:", payload["priority_counts"], "per_oem oems:",
          len(per_oem), "blocked:", len(blocked))
    return 0


# ─────────────────────────── inventory phase ──────────────────────────────

# documented first-party spec endpoints for gaps (probed before recording).
KNOWN_ENDPOINTS = {
    "Toyota": [
        "https://www.toyota.co.th/en/model/api/car-series/",
        "https://www.toyota.co.th/component/api/tcoth/web-init",
    ],
}


def phase_inventory() -> int:
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    plan = json.load(open(os.path.join(OUT, "p112_spec_target_plan.json"),
                          encoding="utf-8"))
    accepted, access = load_ledger()
    fixtures = load_fixtures()
    entries = []
    seen = set()

    # 1) reuse candidates pinned from the plan (no fetch, acquisition only lists)
    for rec, prow in zip(sorted(accepted, key=lambda r: (r["manufacturer"],
                                                         r["model"],
                                                         r["variant"])),
                         plan["variants"]):
        assert (rec["manufacturer"], rec["model"], rec["variant"]) == (
            prow["manufacturer"], prow["model"], prow["variant"]), "plan/ledger order"
        for c in candidate_sources(rec, fixtures):
            key = (c["artifact"],)
            if key in seen:
                continue
            seen.add(key)
            entries.append({"brand": rec["manufacturer"],
                            "artifact": c["artifact"], "url": c["url"],
                            "source_family": c["scope"],
                            "discovery_channel": "reuse_committed_fixture",
                            "selected": True, "fetch": False,
                            "reason": "committed artifact already in the pool; "
                                      "listed for the extraction pass"})

    # 2) bounded discovery for P3 gaps: documented endpoints only
    p3_brands = sorted({r["manufacturer"] for r in plan["variants"]
                        if r["priority"] == "P3_no_scoped_spec_candidate"})
    print("P3 brands:", p3_brands)
    for brand in p3_brands:
        for url in KNOWN_ENDPOINTS.get(brand, []):
            entries.append({"brand": brand, "url": url,
                            "source_family": "structured_payload",
                            "discovery_channel": "documented_official_endpoint",
                            "selected": True, "fetch": True,
                            "reason": "grade-level spec payload documented for "
                                      "this OEM; brand has P3-gap variants with "
                                      "no committed scoped spec page"})
    # brands with P3 gaps but no documented endpoint → explicit ceiling row
    for brand in p3_brands:
        if brand not in KNOWN_ENDPOINTS:
            entries.append({"brand": brand, "url": "",
                            "source_family": "gap",
                            "discovery_channel": "no_documented_endpoint",
                            "selected": False, "fetch": False,
                            "reason": "P3 gap: no committed variant- or "
                                      "model-scoped spec page for at least one "
                                      "accepted variant and no documented "
                                      "official spec endpoint — recorded as "
                                      "source ceiling, never guessed or bypassed"})

    to_fetch = [e for e in entries if e.get("fetch")]
    assert len(to_fetch) <= GLOBAL_CAP, len(to_fetch)
    payload = {
        "schema": "p112_spec_source_inventory/1", "generated_at": stamp,
        "session_id": SESSION_ID,
        "method": "ONE inventory: reuse candidates pinned from committed "
                  "fixtures first; new fetches limited to documented official "
                  "spec endpoints for P3-gap OEMs; everything else is an "
                  "explicit source-ceiling row",
        "totals": {"entries": len(entries),
                   "reuse_entries": sum(1 for e in entries
                                        if e["discovery_channel"] ==
                                        "reuse_committed_fixture"),
                   "fetch_selected": len(to_fetch),
                   "ceiling_rows": sum(1 for e in entries
                                       if e["source_family"] == "gap")},
        "entries": entries}
    write_json("p112_spec_source_inventory.json", payload)
    print("inventory:", payload["totals"])
    return 0


# ─────────────────────────── acquire phase ────────────────────────────────

def pdftext(content: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        fh.write(content)
        pdf = fh.name
    txt = pdf + ".txt"
    try:
        subprocess.run(["pdftotext", "-layout", pdf, txt],
                       check=False, capture_output=True, timeout=60)
        if os.path.exists(txt):
            return open(txt, encoding="utf-8", errors="ignore").read()
    except Exception:
        pass
    finally:
        for p in (pdf, txt):
            if os.path.exists(p):
                os.unlink(p)
    return ""


def safe_name(brand: str, url: str) -> str:
    up = urllib.parse.urlparse(url)
    path = up.path.rstrip("/")
    slug = urllib.parse.unquote(path.split("/")[-1] or "index")
    qs = urllib.parse.parse_qs(up.query)
    if qs:
        tag = "_".join(f"{k}_{v[0]}" for k, v in sorted(qs.items()))
        slug = f"{slug}_{tag}"
    if not slug.lower().endswith((".html", ".pdf", ".json", ".xml")):
        slug += ".json" if url.lower().split("?")[0].endswith((".json", "/")) \
            and "/api/" in url else ".html"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", slug).strip("_")[:60] or "page"
    stem, ext = os.path.splitext(slug)
    base = brand.lower().replace("-", "_")
    name = f"{base}_p112_{stem}{ext}"
    n = 1
    while os.path.exists(os.path.join(FIXTURE_DIR, name)):
        n += 1
        name = f"{base}_p112_{stem}_dup{n}{ext}"
    return name


def _url_key(url: str):
    """identity of an official resource: host + locale-stripped path + QUERY.

    Dropping the query (as a page-URL dedupe does) makes
    ``…/api/car/?series_code=alphard`` and ``…?series_code=camry`` look like
    one resource — a batch would then 'reuse' a single payload for thirty
    different series.  API resources keep their query."""
    m = re.match(r"https?://([^/?#]+)([^?#]*)\?(.*)$", url or "")
    if m:
        path = re.sub(r"^/(en|th)(?=/)", "", m.group(2).rstrip("/") or "/")
        return (m.group(1).lower().replace("www.", ""), path, m.group(3))
    m = re.match(r"https?://([^/?#]+)([^?#]*)", url or "")
    if m:
        path = re.sub(r"^/(en|th)(?=/)", "", m.group(2).rstrip("/") or "/")
        return (m.group(1).lower().replace("www.", ""), path, "")
    return None


def already_captured(url: str):
    """normalized (host, locale-stripped path) match against every committed
    sidecar — a re-run of this batch must never mint duplicate fixtures."""
    import hashlib
    target = _url_key(url)
    if not target:
        return None
    for fn in os.listdir(FIXTURE_DIR):
        if not fn.endswith(".prov.json"):
            continue
        try:
            u = json.load(open(os.path.join(FIXTURE_DIR, fn),
                               encoding="utf-8"))["source_url"]
            if _url_key(u) == target:
                return fn[:-len(".prov.json")]
        except Exception:
            continue
    return None


def fetch_one(sess, brand: str, url: str, log: list, results: list) -> None:
    entry = {"brand": brand, "url": url, "source_family": "structured_payload"}
    prev = already_captured(url)
    if prev:
        entry.update(status="ALREADY_CAPTURED", ok=True, artifact=prev,
                     skipped="idempotent re-run: committed fixture reused")
        results.append(entry)
        log.append({"brand": brand, "url": url, "final_url": url,
                    "filename": prev, "ok": True, "new_capture": False,
                    "sha256": json.load(open(os.path.join(
                        FIXTURE_DIR, prev + ".prov.json"),
                        encoding="utf-8")).get("sha256"), "bytes": 0})
        return
    if any(b.lower() in url.lower() for b in BLOCKED):
        entry.update(status="BLOCKED_HOST", ok=False,
                     blocker="blocked OEM token in URL; never requested")
        results.append(entry)
        return
    try:
        resp = sess.get(url, timeout=30, allow_redirects=True)
    except Exception as exc:
        entry.update(status="ERROR", ok=False,
                     blocker=f"{type(exc).__name__}: {exc}")
        results.append(entry)
        log.append({"brand": brand, "url": url, "ok": False,
                    "error": entry["blocker"]})
        time.sleep(POLITENESS_S)
        return
    entry["http_status"] = resp.status_code
    if resp.status_code != 200:
        entry.update(status="HTTP_ERROR", ok=False,
                     blocker=f"HTTP_{resp.status_code} after redirects")
        results.append(entry)
        log.append({"brand": brand, "url": url, "ok": False,
                    "error": entry["blocker"]})
        time.sleep(POLITENESS_S)
        return
    final = resp.url
    if not final.startswith("https://"):
        entry.update(status="NOT_HTTPS", ok=False,
                     blocker="final URL is not https; refused")
        results.append(entry)
        time.sleep(POLITENESS_S)
        return
    ctype = (resp.headers.get("Content-Type") or "").lower()
    is_pdf = "pdf" in ctype or final.lower().split("?")[0].endswith(".pdf")
    if is_pdf:
        text = pdftext(resp.content)
        if len(text.strip()) < 200:
            entry.update(status="SOURCE_DROPPED", ok=False,
                         blocker="PDF has no usable text layer")
            results.append(entry)
            time.sleep(POLITENESS_S)
            return
        content, method, size = text, "http_get_pdf_pdftotext", len(text)
    else:
        method = "http_get"
        content = resp.text.replace("\r\n", "\n").replace("\r", "\n")
        size = len(content)
    filename = safe_name(brand, final)
    try:
        prov = AcquisitionWriter.write(content=content, source_url=final,
                                       acquisition_method=method,
                                       output_dir=FIXTURE_DIR,
                                       filename=filename,
                                       session_id=SESSION_ID)
    except Exception as exc:
        entry.update(status="WRITE_ERROR", ok=False,
                     blocker=f"{type(exc).__name__}: {exc}")
        results.append(entry)
        time.sleep(POLITENESS_S)
        return
    entry.update(status="CAPTURED", ok=True, artifact=filename,
                 sha256=prov.get("sha256"), bytes=size, final_url=final)
    results.append(entry)
    log.append({"brand": brand, "url": url, "final_url": final,
                "filename": filename, "ok": True, "new_capture": True,
                "sha256": prov.get("sha256"), "bytes": size})
    time.sleep(POLITENESS_S)


def phase_acquire() -> int:
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    inv = json.load(open(os.path.join(OUT, "p112_spec_source_inventory.json"),
                         encoding="utf-8"))
    to_fetch = [e for e in inv["entries"] if e.get("fetch")]
    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT,
                         "Accept": "application/json,text/html,*/*"})
    log, results = [], []

    # Toyota documented chain: ONE list call → series codes that map to the
    # accepted models → their grade-spec payloads, inside this same batch.
    for e in [x for x in to_fetch if "/car-series/" in x["url"]]:
        fetch_one(sess, e["brand"], e["url"], log, results)
        captured = [r for r in log if r.get("ok") and
                    "/car-series/" in r["url"]]
        if not captured:
            continue
        raw = open(os.path.join(FIXTURE_DIR, captured[-1]["filename"]),
                   encoding="utf-8", errors="ignore").read()
        try:
            tree = json.loads(raw)
            series = [s for cat in (tree.get("data") or [])
                      for s in (cat.get("series") or [])]
            codes = sorted({s.get("code") for s in series if s.get("code")})
        except Exception:
            codes, series = [], []
        accepted, _ = load_ledger()
        wanted = {}
        for r in accepted:
            if r["manufacturer"] != "Toyota":
                continue
            base = re.sub(r"^Toyota\s+", "", r["model"], flags=re.I)
            wanted.setdefault(compact(base), r["model"])
        pairs = []
        for code in codes:
            cc = compact(code)
            for ws, model in wanted.items():
                if len(ws) >= 5 and (ws in cc or cc in ws):
                    pairs.append((code, model))
                    break
        picked = sorted({c for c, _ in pairs})
        inv["programmatic_expansion"] = [{
            "list_url": e["url"], "series_codes_seen": len(codes),
            "matched_model_to_code": [{"model": m, "code": c}
                                      for c, m in sorted(pairs, key=lambda x: x[1])],
            "codes_fetched": picked[:40]}]
        for code in picked[:40]:
            fetch_one(sess, "Toyota",
                      f"https://www.toyota.co.th/en/model/api/car/?series_code={code}",
                      log, results)

    for e in [x for x in to_fetch if "/car-series/" not in x["url"]]:
        fetch_one(sess, e["brand"], e["url"], log, results)

    payload = {
        "schema": "p112_spec_capture_log/1", "generated_at": stamp,
        "session_id": SESSION_ID,
        "new_captures": sum(1 for r in log
                             if r.get("ok") and r.get("new_capture") is not False),
        "reused_captures": sum(1 for r in log
                               if r.get("ok") and r.get("new_capture") is False),
        "results": log,
        "failures": [r for r in results if not r.get("ok")]}
    write_json("p112_spec_capture_log.json", payload)
    inv["acquisition"] = {"fetch_selected": len(to_fetch),
                          "captured": payload["new_captures"],
                          "reused": payload["reused_captures"],
                          "failed": len(payload["failures"])}
    write_json("p112_spec_source_inventory.json", inv)
    print(f"acquire: selected_fetch={len(to_fetch)} captured={payload['new_captures']} "
          f"failed={len(payload['failures'])}")
    for r in log:
        print(f"  ok   {r['brand']:9s} {(r.get('filename') or '-')[:50]:50s} "
              f"{'NEW' if r.get('new_capture', True) else 'reuse':5s} {r['url'][:64]}")
    for r in payload["failures"]:
        print(f"  fail {r['brand']:9s} {r.get('status', '?'):14s} "
              f"{(r.get('blocker') or '')[:60]} {r['url'][:60]}")
    return 0


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else ""
    if phase == "plan":
        return phase_plan()
    if phase == "inventory":
        return phase_inventory()
    if phase == "acquire":
        return phase_acquire()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
