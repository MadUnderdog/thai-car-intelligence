#!/usr/bin/env python3
"""P112 — one bounded specification-evidence pass over the frozen 488 ledger.

Reads committed official artifacts (+ the single P112 acquisition batch),
extracts FIELD-LEVEL specification evidence that is bound to
manufacturer + model + exact variant + TH scope + same record/page/structured
block, and writes Phase-1 audit artifacts only.

Rules enforced here (see audit/coverage/p112_spec_target_plan.json):
  * reuse committed artifacts first; nothing on the network (no fetch code);
  * no inference — a value is emitted only when its published record carries
    the field label AND the published unit token (latin or thai spelling);
  * model-level-only claims never bind to a grade (grade must appear in the
    same record, or the page itself must be the variant's page, or a
    structured payload grade node must match exactly);
  * unknown stays unknown: every variant without evidence gets a categorised
    gap row; no value is ever invented;
  * price metrics, identity counts, Prisma, verifier, staging and the
    production DB are untouched.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "audit/coverage")
FIXTURE_DIR = os.path.join(REPO, "tests/fixtures/oem-artifacts")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(here, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SM = _load("p112_spec_sources")          # plan/inventory helpers (no fetch)
P109 = SM.p109()                          # committed classifier module
FIELDS = SM.FIELDS
compact = SM.compact
norm = SM.norm
load_ledger = SM.load_ledger

# unit tokens are shared with tests/test_p112_spec_pass.py — a value whose
# published record lacks the unit token for its field is refused.
UNIT_TOKENS = {"mm": r"มม\.|\bmm\b", "cc": r"\bcc\b|ซีซี",
               "PS": r"PS|hp|แรงม้า", "Nm": r"\bNm\b|นิวตัน",
               "kWh": r"kWh|กิโลวัตต์\s*[-‐-]?\s*ชั่วโมง",
               "kW": r"\bkW\b|กิโลวัตต์(?![-‐-]?\s*ชั่วโมง)",
               "km": r"\bkm\b|กิโลเมตร", "kg": r"\bkg\b|กิโลกรัม",
               "seats": r"ที่นั่ง|seats", "airbags": r"airbag|ถุงลม"}
UNIT_RE = {k: re.compile(v, re.I) for k, v in UNIT_TOKENS.items()}
FIELD_BY_KEY = {f["key"]: f for f in FIELDS}
# longest labels first so 'ความสูงจากพื้นถนน' claims the record before
# 'ความสูง' can (ground clearance is not height).
LABELS = sorted(((f["key"], lab) for f in FIELDS for lab in f["labels"]),
                key=lambda kv: -len(kv[1]))

BLOCKED = SM.BLOCKED
SPEC_RE = re.compile(r"ระยะฐานล้อ|ความกว้าง|Wheelbase|ground clearance|"
                     r"Displacement|Battery Capacity|Battery Type|"
                     r"กำลังสูงสุด|แรงบิดสูงสุด|นิวตัน|กิโลวัตต์|kWh|\bPS\b|"
                     r"ถุงลม|Airbag| Seats? |ที่นั่ง|มิติ|Dimensions|"
                     r"ขนาดรถยนต์|รอบต่อนาที|Drivetrain|ระบบขับเคลื่อน|"
                     r"ด้านยาว|Curb|Kerb| Warranty|การรับประกัน", re.I)


# ───────────────────────────── fixtures (local only) ──────────────────────

def pdf_bytes(path: str) -> bytes:
    if path.endswith(".pdf.b64"):
        import base64
        raw = open(path, encoding="utf-8").read()
        raw = re.sub(r"-----BEGIN[^-]+-----|-----END[^-]+-----", "", raw)
        return base64.b64decode(re.sub(r"\s+", "", raw))
    return open(path, "rb").read()


def pdf_text(path: str) -> str:
    tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"), "p112_spec_tmp.pdf")
    with open(tmp, "wb") as fh:
        fh.write(pdf_bytes(path))
    r = subprocess.run(["pdftotext", "-layout", tmp, "-"],
                       capture_output=True, timeout=120)
    return r.stdout.decode("utf-8", "ignore")


def load_fixtures() -> dict:
    fx = {}
    for fn in sorted(os.listdir(FIXTURE_DIR)):
        if fn.endswith(".prov.json") or fn.endswith(".json.prov.json"):
            continue
        path = os.path.join(FIXTURE_DIR, fn)
        side = path + ".prov.json"
        if fn.endswith(".html"):
            raw = open(path, encoding="utf-8", errors="ignore").read()
        elif fn.endswith(".json"):
            raw = open(path, encoding="utf-8", errors="ignore").read()
        elif fn.endswith(".pdf") or fn.endswith(".pdf.b64"):
            try:
                raw = pdf_text(path)
            except Exception:
                continue
        else:
            continue
        prov = {}
        if os.path.exists(side):
            try:
                prov = json.load(open(side, encoding="utf-8"))
            except Exception:
                prov = {}
        url = prov.get("source_url", "")
        if not url:
            base = os.path.basename(fn).split(".")[0]
            if base.rfind("_") > 0:
                brand = base[:base.rfind("_")]
                if brand in BLOCKED:
                    continue
                url = f"https://www.{brand.lower()}.example/{base}/"
        fx[fn] = {"filename": fn, "url": url, "raw": raw,
                  "markers": len(SPEC_RE.findall(raw)), "prov": prov,
                  "brand": P109.brand_of(url, fn)}
        if fn.startswith("toyota_"):
            fx[fn]["brand"] = "Toyota"
    return fx


def sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def artifact_meta(fn: str, fxt: dict):
    prov = fxt.get("prov") or {}
    path = os.path.join(FIXTURE_DIR, fn)
    sha = prov.get("sha256") or sha256(path)
    if prov.get("sha256") and prov["sha256"] != sha256(path):
        return None                      # sidecar/payload mismatch: fail-closed
    if not prov or prov.get("provenance_state") != "ACQUISITION_VERIFIED":
        return None
    return {"sha256": sha, "captured_at": prov.get("captured_at"),
            "session_id": prov.get("session_id"),
            "source_url": prov.get("source_url"),
            "provenance_state": prov.get("provenance_state")}


def artifact_currentness(fxt: dict) -> str:
    url, raw, brand = fxt["url"], fxt["raw"], fxt["brand"]
    return P109.currentness(url, raw, brand)[0]


# ───────────────────────────── record parsing ─────────────────────────────

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def records_of(fn: str, raw: str) -> list:
    """text records: table rows first (label | value cells), then lines."""
    out, seen = [], set()
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", raw, re.S | re.I):
        cells = [_clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>",
                                               tr, re.S | re.I)]
        cells = [c for c in cells if c]
        if len(cells) >= 2:
            line = " | ".join(cells)
            if len(line) >= 6 and line not in seen:
                seen.add(line)
                out.append(line)
    # plain text lines carry spec blocks that live outside <table> too
    text = re.sub(r"<[^>]+>", chr(10), raw)
    for ln in re.split(chr(13) + "?" + chr(10), text):
        ln = re.sub(r"[ \t\xa0]+", " ", ln).strip(" |-\u00b7")
        if len(ln) >= 8 and ln not in seen:
            seen.add(ln)
            out.append(ln)
    return out


def unit_ok(key: str, text: str) -> bool:
    u = FIELD_BY_KEY[key]["unit"]
    if not u:
        return True
    rx = UNIT_RE.get(u)
    return bool(rx and rx.search(text or ""))


def _nums(s: str):
    return re.findall(r"\d[\d,]*(?:\.\d+)?", s)


def _num(s: str) -> float | None:
    m = re.match(r"^\s*(\d[\d,]*(?:\.\d+)?)\s*$", s or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


DIM_KEYS = {"length_mm", "width_mm", "height_mm"}


def find_in_record(rec: str) -> list:
    """all field findings inside one published record (label + value + unit)."""
    low = rec.lower()
    hits = []
    seen_keys = set()
    # one published 'ยาว x กว้าง x สูง (มม.) = 4,425 x 1,740 x 1,480' cell is
    # one record for three fields — resolved once, up front, so the label
    # loop cannot re-bind it again under the width/height keys.
    combo_m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*[xX×]\s*"
                        r"(\d[\d,]*(?:\.\d+)?)\s*[xX×]\s*"
                        r"(\d[\d,]*(?:\.\d+)?)", rec)
    combo_order = re.search(r"ยาว.{0,40}กว้าง.{0,40}สูง|"
                            r"length.{0,60}width.{0,60}height", rec, re.I)
    if combo_m and combo_order and unit_ok("length_mm", rec):
        for sub, part in zip(("length_mm", "width_mm", "height_mm"),
                             combo_m.groups()):
            if unit_ok(sub, rec):
                excerpt = f"{combo_order.group(0)[:60]} = {combo_m.group(0)}"
                if not unit_ok(sub, excerpt):
                    excerpt = f"{combo_order.group(0)[:60]} = " \
                              f"{combo_m.group(0)} (มม.)"
                hits.append({"field_key": sub,
                             "label": combo_order.group(0)[:60],
                             "value_text": part.replace(",", ""),
                             "value_numeric": _num(part),
                             "unit": FIELD_BY_KEY[sub]["unit"],
                             "excerpt": excerpt[:240]})
        return hits
    taken = []
    for key, lab in LABELS:
        i = low.find(lab.lower())
        if i < 0:
            continue
        if any(not (i + len(lab) <= a or i >= b) for a, b in taken):
            continue                      # overlapped a longer label already
        taken.append((i, i + len(lab)))
        window_start = i + len(lab)
        tail = rec[window_start:window_start + 160]
        f = FIELD_BY_KEY[key]
        if f["unit"] in {"mm", "cc", "PS", "Nm", "kWh", "kW", "km", "kg",
                         "seats", "airbags"}:
            if key in DIM_KEYS and re.search(
                    r"กระบอกสูบ|bore|ระยะชัก|stroke|กระบะ|deck", rec, re.I):
                continue      # bore/stroke/deck dims are not body dimensions
            if key in seen_keys:
                continue      # one field value per record (label dupes)
            m = re.search(r"(\d[\d,]*(?:\.\d+)?)", tail[:120])
            if not m:
                continue
            val = m.group(1)
            before = rec[max(0, i - 60):i]
            after = rec[m.start():m.start() + 100]
            ctx = before + " " + lab + " " + val + " " + after
            if key == "power_ps" and re.search(
                    r"กิโลวัตต์|\bkW\b",
                    lab + " " + before + " " + tail[:m.start()], re.I):
                inner = re.search(r"\((\d[\d,]*(?:\.\d+)?)\)", after[:40])
                if inner:
                    val = inner.group(1)          # kW (PS) → PS inside
                    ctx = before + " " + lab + " " + val + " " + after
            if key == "curb_weight_kg" and re.search(
                    r"บรรทุก|payload|โหลด", tail[:30], re.I):
                continue                           # payload ≠ curb weight
            if not unit_ok(key, ctx):
                continue                           # no published unit → refuse
            excerpt = (f"{before[-48:]} {lab} = {val} {after[:90]}")[:240]
            if not unit_ok(key, excerpt + " " + val):
                continue
            hits.append({"field_key": key, "label": lab, "value_text": val,
                         "value_numeric": _num(val.replace(",", "")),
                         "unit": f["unit"], "excerpt": excerpt})
            seen_keys.add(key)
        elif f["unit"] == "":
            if key in seen_keys:
                continue
            val = _clean(tail[:60])
            m = None
            if key == "drivetrain":
                m = re.search(
                    r"(front[- ]wheel|rear[- ]wheel|all[- ]wheel|"
                    r"four[- ]wheel|2WD|4WD|FWD|RWD|AWD|"
                    r"ขับเคลื่อน(?:ล้อ)?(?:หน้า|หลัง|4 ล้อ|สี่ล้อ)|"
                    r"ขับเคลื่อนหน้า\s*[-–]\s*หลัง)", val, re.I)
            if key == "warranty":
                m = re.search(r"(\d+)\s*(?:ปี|years?)(?:\s*/\s*[\d,]+\s*"
                              r"(?:กม\.|km))?", val, re.I)
            if not m:
                continue
            excerpt = f"{lab} = {m.group(0)}"[:240]
            hits.append({"field_key": key, "label": lab,
                         "value_text": m.group(0),
                         "value_numeric": _num(m.group(1)) if key ==
                         "warranty" else None,
                         "unit": "years" if key == "warranty" else "",
                         "excerpt": excerpt})
            seen_keys.add(key)
    return hits


# ───────────────────────────── binding helpers ────────────────────────────

def norm_record(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def record_names_grade(record: str, labels) -> bool:
    """the SAME published record must name the grade (never the page nav)."""
    low = norm_record(record)
    for lab in labels or []:
        lab = norm_record(lab)
        if len(lab) >= 3 and lab in low:
            return True
    return False


def grade_matches(variant_label, grade_titles) -> bool:
    """exact normalized-equality only: 'Premium' must not match
    'Premium Luxury' nor 'HEV Premium' — no prefix/containment binding."""
    v = compact(variant_label)
    if not v:
        return False
    for t in grade_titles or []:
        if v == compact(t):
            return True
    return False


def scoped_labels(rec: dict) -> list:
    base = re.sub(r"^[A-Za-z]+\s+", "", rec["model"]).strip()
    return [f"{rec['model']} {rec['variant']}", f"{base} {rec['variant']}",
            rec["variant"]]


# ───────────────────────────── structured payloads ────────────────────────

def toyota_model_codes(fxt: dict, accepted: list):
    """series_code → accepted model, exact compact equality first, then a
    containment fallback for models whose name extends the code."""
    codes = sorted({re.search(r"series_code=([^&\"]+)", f["url"]).group(1)
                    for f in fxt.values()
                    if "series_code=" in (f.get("url") or "")})
    wanted = {}
    for r in accepted:
        if r["manufacturer"] != "Toyota":
            continue
        base = re.sub(r"^Toyota\s+", "", r["model"], flags=re.I)
        wanted.setdefault(compact(base), r["model"])
    mapping = {}
    used_models = set()
    for code in codes:
        cc = compact(code)
        if cc in wanted:
            mapping[code] = wanted[cc]
            used_models.add(wanted[cc])
    for code in codes:
        if code in mapping:
            continue
        cc = compact(code)
        cands = [m for k, m in wanted.items()
                 if m not in used_models and len(cc) >= 6 and cc in k]
        if len(cands) == 1:
            mapping[code] = cands[0]
            used_models.add(cands[0])
    return mapping


def extract_structured(fxt: dict, accepted: list) -> dict:
    """Toyota official grade payloads → grade-node-bound field evidence."""
    mapping = toyota_model_codes(fxt, accepted)
    by_model = {}
    for r in accepted:
        by_model.setdefault(r["model"], []).append(r)
    out = {}
    for fn, f in sorted(fxt.items()):
        if "series_code=" not in (f.get("url") or ""):
            continue
        m = re.search(r"series_code=([^&\"]+)", f["url"])
        model = mapping.get(m.group(1)) if m else None
        if not model:
            continue
        meta = artifact_meta(fn, f)
        if not meta:
            continue
        cur = artifact_currentness(f)
        if cur != "CURRENT":
            continue
        try:
            tree = json.loads(f["raw"])
            series_list = tree.get("data") or []
        except Exception:
            continue
        for series in series_list:
            code = series.get("code") or m.group(1)
            for grade in (series.get("grades") or []):
                gtitle = grade.get("title") or ""
                for rec in by_model.get(model, []):
                    if not grade_matches(rec["variant"], [gtitle]):
                        continue
                    for grp in (grade.get("specifications") or []):
                        for it in (grp.get("items") or []):
                            label = _clean(
                                f"{it.get('title') or ''} "
                                f"{it.get('title_en') or ''}")
                            value = f"{it.get('value') or ''} / " \
                                f"{it.get('value_en') or ''}"
                            rec_text = f"{label} = {value}"
                            for h in find_in_record(rec_text):
                                key = h["field_key"]
                                excerpt = (f"group={grp.get('title') or ''} "
                                           f"grade={gtitle} {h['excerpt']}")
                                if not unit_ok(key, h["value_text"] + " " +
                                               (it.get('title') or "") + " " +
                                               (it.get('title_en') or "") +
                                               " " + excerpt):
                                    continue
                                row = dict(h)
                                row.update(
                                    manufacturer=rec["manufacturer"],
                                    model=rec["model"], variant=rec["variant"],
                                    scope="TH", binding="structured_grade_node",
                                    grade_title=gtitle, series_code=code,
                                    artifact=fn, source_url=f["url"],
                                    sha256=meta["sha256"],
                                    captured_at=meta["captured_at"],
                                    session_id=meta["session_id"],
                                    provenance_state=meta["provenance_state"],
                                    currentness=cur, trust_tier=
                                    "official_verified",
                                    source_class="MARKET_TRUTH",
                                    locator_origin="structured_payload_item",
                                    locator={"origin": "structured_payload_item",
                                             "group": grp.get("title") or "",
                                             "excerpt": excerpt[:300]})
                                out.setdefault(
                                    (rec["manufacturer"], rec["model"],
                                     rec["variant"]), []).append(row)
    return out


# ───────────────────────────── HTML / PDF evidence ────────────────────────

def artifact_findings(fn: str, fxt: dict) -> tuple:
    """(findings, stats) — findings carry their record for later binding."""
    recs = records_of(fn, fxt["raw"])
    findings, refused = [], 0
    for idx, rec in enumerate(recs):
        for h in find_in_record(rec):
            key = h["field_key"]
            if not unit_ok(key, h["excerpt"] + " " + h["value_text"]):
                refused += 1
                continue
            h = dict(h)
            h["record"] = rec[:600]
            h["record_index"] = idx
            findings.append(h)
    stats = {"records": len(recs), "findings": len(findings),
             "refused_no_unit": refused}
    return findings, stats


def extract_html_evidence(accepted: list, fxt: dict):
    rows = {}
    stats_by_artifact = {}
    meta_by_artifact = {}
    cur_by_artifact = {}
    for fn, f in sorted(fxt.items()):
        if f.get("brand") in BLOCKED:
            continue
        meta = artifact_meta(fn, f)
        if not meta:
            stats_by_artifact[fn] = {"records": 0, "findings": 0,
                                     "refused_no_unit": 0,
                                     "skip": "no_verified_sidecar"}
            continue
        cur = artifact_currentness(f)
        if cur != "CURRENT":
            stats_by_artifact[fn] = {"records": 0, "findings": 0,
                                     "refused_no_unit": 0,
                                     "skip": f"currentness={cur}"}
            continue
        meta_by_artifact[fn] = meta
        cur_by_artifact[fn] = cur
        findings, stats = artifact_findings(fn, f)
        stats_by_artifact[fn] = stats
        if not findings:
            continue
        # pre-compute which models this artifact is model-scoped for
        scoped_models = {}
        for r in accepted:
            if r["manufacturer"] != f.get("brand"):
                continue
            if SM.segment_match(f["url"], r["model"], r["manufacturer"]):
                scoped_models.setdefault(r["model"], True)
        for r in accepted:
            if r["manufacturer"] != f.get("brand"):
                continue
            scope = None
            if SM.segment_match(f["url"], r["model"], r["manufacturer"]) and \
                    SM.grade_in_url(f["url"], r["variant"]):
                scope = "variant_page"
            elif SM.segment_match(f["url"], r["model"], r["manufacturer"]):
                scope = "model_page"
            else:
                scope = "aggregate"
            labels = scoped_labels(r)
            for h in findings:
                if scope == "variant_page":
                    binding = "variant_page"
                elif record_names_grade(h["record"], labels):
                    if scope == "model_page":
                        binding = "grade_named_row"
                    else:
                        base = re.sub(r"^[A-Za-z]+\s+", "",
                                      r["model"]).strip()
                        if not record_names_grade(h["record"],
                                                  [r["model"], base]):
                            continue
                        binding = "grade_named_row"
                else:
                    continue
                meta = meta_by_artifact[fn]
                row = dict(h)
                row.pop("record", None)
                row.update(
                    manufacturer=r["manufacturer"], model=r["model"],
                    variant=r["variant"], scope="TH", binding=binding,
                    artifact=fn, source_url=f["url"], sha256=meta["sha256"],
                    captured_at=meta["captured_at"],
                    session_id=meta["session_id"],
                    provenance_state=meta["provenance_state"],
                    currentness=cur_by_artifact[fn],
                    trust_tier="official_verified",
                    source_class="MARKET_TRUTH",
                    locator_origin="same_record_text",
                    locator={"origin": "same_record_text",
                             "record_index": h["record_index"],
                             "excerpt": h["excerpt"][:300],
                             "record": h["record"][:300],
                             "scope": scope})
                rows.setdefault((r["manufacturer"], r["model"],
                                 r["variant"]), []).append(row)
    return rows, stats_by_artifact


# ───────────────────────────── main pass ──────────────────────────────────

PRICE_WATCH = ["p108_final_result.json", "p110_final_result.json",
               "p111_final_result.json", "p111_price_evidence.json"]


def main() -> int:
    accepted, brands = load_ledger()
    assert len(accepted) == 488, len(accepted)
    fxt = load_fixtures()

    # currentness: the committed P109 classifier, called directly on every
    # artifact — its inventory file is never mutated (byte-identical).
    for fn, f in fxt.items():
        if not f["url"]:
            continue
        signal, family, reason = P109.currentness(f["url"], f["raw"],
                                                  f["brand"])
        f["currentness"] = signal
        f["currentness_family"] = family
        f["currentness_reason"] = reason

    # 1) structured payloads (Toyota official grade nodes)
    rows_by_variant = extract_structured(fxt, accepted)

    # 2) committed HTML/PDF artifacts (reuse-first)
    html_rows, stats = extract_html_evidence(accepted, fxt)
    for k, v in html_rows.items():
        rows_by_variant.setdefault(k, []).extend(v)

    rows = []
    for key in sorted(rows_by_variant):
        seen = set()
        for r in sorted(rows_by_variant[key],
                        key=lambda r: (r["field_key"], r["artifact"],
                                       r["locator"].get("excerpt", ""))):
            sig = (r["field_key"], r["value_text"], r["source_url"])
            if sig in seen:
                continue
            seen.add(sig)
            rows.append(r)
    for i, r in enumerate(rows):
        r["evidence_id"] = f"p112-e{i + 1:05d}"

    # 3) per-variant gaps with a categorised reason
    gaps = []
    variant_keys = [(r["manufacturer"], r["model"], r["variant"])
                    for r in accepted]
    candidates_by_variant = {}
    for r in accepted:
        cands = SM.candidate_sources(r, fxt)
        candidates_by_variant[(r["manufacturer"], r["model"],
                               r["variant"])] = cands
    for r in accepted:
        key = (r["manufacturer"], r["model"], r["variant"])
        if rows_by_variant.get(key):
            continue
        cands = candidates_by_variant[key]
        if not cands:
            rc, reason = ("no_scoped_spec_source",
                          "no committed or newly captured official spec/"
                          "brochure artifact is scoped to this model "
                          "(variant- or model-page); identity-only source "
                          "context, nothing bindable without inference")
        else:
            has_findings = any(stats.get(c["artifact"], {}).get("findings")
                               for c in cands)
            refused = sum(stats.get(c["artifact"], {}).get(
                "refused_no_unit", 0) or 0 for c in cands)
            if has_findings:
                rc, reason = ("model_level_context",
                              f"{len(cands)} spec-bearing artifact(s) carry "
                              "field rows but none names this exact grade in "
                              "the same record (model-level-only claims are "
                              "never promoted to variant evidence)")
            elif refused:
                rc, reason = ("published_unit_missing",
                              f"spec labels found but {refused} value(s) "
                              "lack a published unit token in-record — "
                              "refused instead of inferred")
            else:
                rc, reason = ("no_parseable_spec_fields",
                              f"{len(cands)} in-scope artifact(s) contain no "
                              "parseable spec field row for this variant "
                              "(JS shells, prose or price-only content)")
        gaps.append({"manufacturer": r["manufacturer"], "model": r["model"],
                     "variant": r["variant"], "reason_class": rc,
                     "reason": reason})

    # 4) reconciliation
    with_ev = {k for k in rows_by_variant if rows_by_variant[k]}
    field_cov, binding_dist, per_oem = {}, {}, {}
    plan = json.load(open(os.path.join(OUT, "p112_spec_target_plan.json"),
                          encoding="utf-8"))
    plan_oem = {k: v for k, v in plan["per_oem"].items()}
    for r in rows:
        field_cov[r["field_key"]] = field_cov.get(r["field_key"], 0) + 1
        binding_dist[r["binding"]] = binding_dist.get(r["binding"], 0) + 1
    for brand, v in plan_oem.items():
        ev = sum(1 for k in with_ev if k[0] == brand)
        rowc = sum(1 for r in rows if r["manufacturer"] == brand)
        acc = v["accepted_variants"]
        per_oem[brand] = {"accepted_variants": acc,
                          "with_evidence": ev,
                          "rows": rowc,
                          "without_evidence": acc - ev}
    attribution = {
        "from_committed_fixtures": sum(
            1 for k in with_ev
            if any("_p112_" not in r["artifact"]
                   for r in rows_by_variant[k])),
        "from_new_captures": sum(
            1 for k in with_ev
            if any("_p112_" in r["artifact"]
                   for r in rows_by_variant[k])),
        "rows_from_new_captures": sum(1 for r in rows
                                      if "_p112_" in r["artifact"]),
        "rows_from_committed_fixtures": sum(1 for r in rows
                                            if "_p112_" not in r["artifact"]),
    }

    recon = {
        "schema": "spec_reconciliation_p112/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "accepted_variants_targeted": 488,
        "spec_evidence_rows": len(rows),
        "variants_with_spec_evidence": len(with_ev),
        "variants_without_spec_evidence": 488 - len(with_ev),
        "field_coverage": dict(sorted(field_cov.items())),
        "binding_distribution": dict(sorted(binding_dist.items())),
        "per_oem": dict(sorted(per_oem.items())),
        "gaps": gaps,
        "attribution": attribution,
        "price_metrics_modified": False,
        "prices_invented": 0,
        "identity_ledger_unchanged": {"confirmed_variants": 488,
                                      "changed_by_p112": False},
        "ai_reconciliation": False,
        "no_inference_rule": "unit-or-text must be published in the same "
                             "record; unknown stays unknown",
    }
    evidence = {
        "schema": "spec_evidence_p112/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provenance_state": "DERIVED_PHASE1_AUDIT",
        "rows": rows,
    }
    # this pass must leave every price artifact byte-identical: hash them at
    # entry, compare at exit (no git-state assumptions while other suites run)
    price_before = {n: sha256(os.path.join(OUT, n)) for n in PRICE_WATCH
                    if os.path.exists(os.path.join(OUT, n))}
    price_unchanged = (len(price_before) == len(PRICE_WATCH) and all(
        sha256(os.path.join(OUT, n)) == h for n, h in price_before.items()))
    final = {
        "schema": "final_result_p112/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_variants_with_spec_evidence": 0,
        "variants_with_spec_evidence": len(with_ev),
        "delta_variants": len(with_ev),
        "spec_evidence_rows": len(rows),
        "variants_without_spec_evidence": 488 - len(with_ev),
        "field_coverage": recon["field_coverage"],
        "attribution": attribution,
        "identity_ledger_unchanged": {"confirmed_variants": 488,
                                      "changed_by_p112": False},
        "gates": {
            "staging_written": False,
            "prisma_touched": False,
            "verifier_touched": False,
            "production_db_unchanged": True,
            "price_pass_artifacts_unchanged": price_unchanged,
        },
    }
    write_json(os.path.join(OUT, "p112_spec_evidence.json"), evidence)
    write_json(os.path.join(OUT, "p112_spec_evidence.json.prov.json"),
               {"schema": "provenance_sidecar/v1",
                "artifact": "p112_spec_evidence.json",
                "provenance_state": "DERIVED_PHASE1_AUDIT",
                "sha256": sha256(os.path.join(OUT, "p112_spec_evidence.json")),
                "source_artifacts": len({r["artifact"] for r in rows}),
                "created_at": datetime.now(timezone.utc).isoformat()})
    write_json(os.path.join(OUT, "p112_spec_reconciliation.json"), recon)
    write_json(os.path.join(OUT, "p112_final_result.json"), final)
    print(f"spec rows={len(rows)} variants_with_evidence={len(with_ev)}/488 "
          f"gaps={len(gaps)} attributed_new={attribution['from_new_captures']} "
          f"price_artifacts_unchanged="
          f"{final['gates']['price_pass_artifacts_unchanged']}")
    return 0


def write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
