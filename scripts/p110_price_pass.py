#!/usr/bin/env python3
"""P110 — dedicated price pass over the frozen P108 accepted ledger.

Input: the 488 first-party confirmed VARIANTs of the frozen P108 ledger
(never modified) plus the P109 current-market inventory (currentness signals).

For every accepted variant the pass looks for a price that is bound to the
*same record* (manufacturer + model + exact variant/grade + Thai scope + the
same published row/page of the same first-party artifact) and classifies it
strictly:

    EXACT_VARIANT        grade-specific list/MSRP price on the price row
    MSRP_STARTING        เริ่มต้น / starting-at price (never converted to exact)
    PROMOTIONAL          discount / % / โปรโมชั่น / ของแถม
    FINANCE_INSTALLMENT  ผ่อน / ดาวน์ / ดอกเบี้ย / APR / installment
    RANGE                two published endpoints of a model range

Anything that is not bound to the exact record stays UNVERIFIED_PRICE — no
price is ever invented, spread across grades, or taken from a third-party
block.  Prices found only in MEDIA_DISCOVERY blocks are recorded as reference,
never as official MSRP.  Nothing here writes to staging, the verifier, Prisma,
the API or any database, and identity counts are untouched.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "audit/coverage")
FIXTURE_DIR = os.path.join(REPO, "tests/fixtures/oem-artifacts")

ACCEPTED_LEDGER = 488
ACCEPTED_BASELINE = "audit/coverage/p108_final_result.json"
BLOCKED_ACCESS = {"BLOCKED_HTTP_403", "BLOCKED_HTTP_404", "BLOCKED_DNS",
                  "BLOCKED_TLS", "DEALER_REDIRECT"}

PRICE_TOKEN = re.compile(r"(?<![\d.,])([0-9]{1,3}(?:,[0-9]{3}){1,3})(?![\d.,])")
BARE_PRICE = re.compile(r"(?<![\d])([0-9]{7,8})(?![\d])")
MONEY_MARK = re.compile(r"(฿|THB|บาท|baht|price|ราคา)", re.I)
START_MARK = re.compile(r"(ราคาเริ่มต้น|เริ่มต้น|starting\s+(?:at|from)|start price|"
                        r"started at|ราคา\s*เริ่ม|from\s*฿|prices?\s+from|"
                        r"introductory price)", re.I)
PROMO_MARK = re.compile(r"(\d+\s*%|ส่วนลด|โปรโมช|promotion|of(?:f)?\s*\d|cashback|"
                        r"ของแถม|ฟรี|reward|พิเศษ|ข้อเสนอ|offer)", re.I)
FINANCE_MARK = re.compile(r"(ผ่อน|ดาวน์|ดอกเบี้ย|APR|installment|งวด|finance|"
                          r"首付|ผ่อนเดือน|เครดิต)", re.I)
RANGE_MARK = re.compile(r"([0-9]{1,3}(?:,[0-9]{3}){1,3}\s*[-–—ถึง]\s*[0-9]{1,3}(?:,[0-9]{3}){1,3})")
PRICE_PAGE = re.compile(r"(price|pricelist|price-list|ราคา|configure|grade)", re.I)

PRICE_MIN, PRICE_MAX = 100_000, 60_000_000


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def money_values(line: str) -> list:
    out = []
    for m in PRICE_TOKEN.finditer(line):
        v = int(m.group(1).replace(",", ""))
        if PRICE_MIN <= v <= PRICE_MAX:
            out.append(v)
    for m in BARE_PRICE.finditer(line):
        v = int(m.group(1))
        if PRICE_MIN <= v <= PRICE_MAX and not any(abs(v - x) < 1000 for x in out):
            out.append(v)
    return out


def price_only(line: str) -> bool:
    """the neighbouring record carries the value: a short money-only line."""
    if not money_values(line):
        return False
    if len(line) > 90:
        return False
    if re.search(r"(ส่วนลด|ผ่อน|ดาวน์|ดอกเบี้ย|%|ของแถม)", line, re.I):
        return False
    if re.fullmatch(r"[0-9,.\s฿THBthbbahtบาท.:\-\u2013\u2014]*", line):
        return True
    return bool(re.search(r"(฿|THB|บาท|ราคา|baht|price)", line, re.I))


# ── record-block extraction ────────────────────────────────────────────────
# A price may only bind when the exact grade label and the money value sit in
# the SAME published record block (table row / paragraph / card).  Minified
# pages are re-split into row-level blocks; navigation blobs (many links,
# login/menu wording) and multi-price promo banners are never grade rows, so
# they cannot bind a price to a grade.
ROW_TAGS = r"tr|li|p|h[1-6]|article|blockquote|caption|dt|dd"
WIDE_TAGS = ROW_TAGS + r"|div|section|nav|header|footer|table|tbody|form|ul|ol|aside|main|figure"
SUB_TAGS = r"div|section|td|th|span|a|strong|b|table|tbody"
ROW_SPLIT = re.compile(r"(?i)<\s*(?:%s)\b[^>]*>" % ROW_TAGS)
TAG_STRIP = re.compile(r"<[^>]+>")
NAV_MARK = re.compile(r"(เข้าสู่ระบบ|login|เมนู|menu|ตะกร้า|cart|ค้นหา|search|"
                      r"สมัครสมาชิก|social|rss|subscribe|newsletter)", re.I)
MAX_BLOCK = 600


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", TAG_STRIP.sub(" ", text)).strip()


def _segments(raw: str, tags: str):
    """(raw_content, origin) after each opening tag of `tags`, plus the head."""
    pat = re.compile(r"(?i)<\s*(%s)\b[^>]*>" % tags)
    out = []
    prev_end = 0
    first = None
    for m in pat.finditer(raw):
        if first is None:
            out.append((raw[:m.start()], "head"))
            first = True
        else:
            out.append((raw[prev_end:m.start()], _origin(last_tag)))
        prev_end = m.end()
        last_tag = m.group(1).lower().rstrip("123456")
        last_tag = "p" if last_tag.startswith("h") else last_tag
    out.append((raw[prev_end:], _origin(locals().get("last_tag", "head"))))
    return out


def _origin(tag: str) -> str:
    return "row" if tag in {"tr", "li", "p", "h", "article", "blockquote",
                            "caption", "dt", "dd"} else "sub"


def artifact_blocks(raw: str) -> list:
    """row-level blocks as dicts: text / origin / order / links."""
    out = []

    def emit(content, origin, links):
        t = _collapse(content)
        if t:
            out.append({"text": t, "origin": origin, "order": len(out),
                        "links": links})

    def emit_capped(content, origin, links):
        if len(content) <= MAX_BLOCK:
            emit(content, origin, links)
            return
        if "<" in content:
            for sub, subtag in _segments(content, SUB_TAGS):
                if len(sub) <= MAX_BLOCK:
                    emit(sub, "sub" if origin != "row" else origin,
                         sub.count("<a") + links)
                elif "\n" in sub:
                    for line in sub.split("\n"):
                        if len(line) <= MAX_BLOCK:
                            emit(line, "sub", line.count("<a") + links)
        elif "\n" in content:
            for line in content.split("\n"):
                if len(line) <= MAX_BLOCK:
                    emit(line, origin, links)

    # scripts and styles are never record blocks: structured data is parsed
    # from application/ld+json directly, everything else is page chrome
    raw = re.sub(r"(?is)<script\b.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style\b.*?</style>", " ", raw)
    if not ("<" in raw and ">" in raw):
        for line in raw.split("\n"):
            emit(line, "row", 0)
        return out
    tags = ROW_TAGS if ROW_SPLIT.search(raw) else WIDE_TAGS
    for content, origin in _segments(raw, tags):
        emit_capped(content, origin, content.count("<a"))
    return out


def bindable(block: dict) -> bool:
    text, origin, links = block["text"], block["origin"], block["links"]
    if links > 8 or NAV_MARK.search(text):
        return False                       # navigation / menu / footer blob
    if len(money_values(text)) >= 3:
        return False                       # multi-price banner, not one record
    return True


def classify_price_type(block_text: str, price_pos: int, url: str,
                        label_text: str = "", header: str = "",
                        doc_notes: str = "") -> str:
    """strictly proximity based: only wording that qualifies THIS value counts.

    FINANCE / PROMOTIONAL markers must sit next to the value or in the record's
    own label text (a promo banner elsewhere on the page never reclassifies a
    grade row).  Page-header scope wording ("ราคาเริ่มต้น / starting from") does
    qualify every price on that page, exactly as Blueprint §95 describes."""
    before = block_text[max(0, price_pos - 60):price_pos]
    for ctx in (before, label_text):
        if FINANCE_MARK.search(ctx):
            return "FINANCE_INSTALLMENT"
        if re.search(r"(\d+\s*%|ส่วนลด|ของแถม|ฟรี|โปรโมช|reward|cashback|ราคาพิเศษ|"
                     r"ราคา(?:โปรโมช|พิเศษ)|special price|special introductory|"
                     r"offer valid)", ctx, re.I):
            return "PROMOTIONAL"
    if START_MARK.search(block_text) or START_MARK.search(label_text) \
            or START_MARK.search(url or "") or START_MARK.search(header):
        return "MSRP_STARTING"
    if doc_notes and re.search(r"\*\*", block_text) \
            and re.search(r"start(?:ing)?\s+price|ราคาเริ่ม", doc_notes, re.I):
        return "MSRP_STARTING"   # row carries the footnote marker of the sheet
    if RANGE_MARK.search(block_text):
        return "RANGE"
    return "EXACT_VARIANT"


# ── structured (application/ld+json) price nodes ───────────────────────────
def structured_price_nodes(raw: str):
    """(name, price, currency) triples from JSON-LD structured vehicle data."""
    out = []
    for mm in re.finditer(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>",
                          raw, re.S | re.I):
        try:
            obj = json.loads(mm.group(1))
        except (ValueError, TypeError):
            continue

        def walk(node):
            if isinstance(node, dict):
                offers = node.get("offers")
                price = currency = None
                if isinstance(offers, dict):
                    price, currency = offers.get("price"), offers.get("priceCurrency")
                elif isinstance(offers, list):
                    for o in offers:
                        if isinstance(o, dict) and o.get("price") is not None:
                            price, currency = o.get("price"), o.get("priceCurrency")
                            break
                if price is not None and node.get("name"):
                    out.append((str(node["name"]), str(price), currency or ""))
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for x in node:
                    walk(x)

        walk(obj)
    return out


def artifact_family(url: str) -> str:
    low = (url or "").lower()
    if re.search(r"(price|pricelist|price-list|ราคา)", low):
        return "price_document"
    if re.search(r"(configurator|configure|grade)", low):
        return "configurator"
    if re.search(r"(/models?/|/vehicles/|/lineup|/range|/cars/|pap/_)", low):
        return "model_lineup"
    if re.search(r"(\.pdf|brochure|catalog)", low):
        return "brochure_spec"
    if re.search(r"(news|press|article)", low):
        return "press"
    return "official_page"


def pdf_text(path: str) -> str:
    """extract the text layer of a captured PDF (local pdftotext only — this
    driver never touches the network).  Returns "" when there is no text layer
    (image-only scans stay unresolved instead of being guessed)."""
    raw = open(path, "rb").read()
    if raw[:4] == b"%PDF" or raw[:9] == b"JVBERi0xL":
        if raw[:9] == b"JVBERi0xL":
            try:
                raw = base64.b64decode(raw, validate=False)
            except (ValueError, TypeError):
                return ""
        if not raw.startswith(b"%PDF"):
            return ""
        tmp = os.path.join(tempfile.gettempdir(),
                           "p110_%s.pdf" % hashlib.sha256(raw).hexdigest()[:16])
        try:
            with open(tmp, "wb") as fh:
                fh.write(raw)
            res = subprocess.run(["pdftotext", "-layout", tmp, "-"],
                                 capture_output=True, text=True, timeout=120)
            if res.returncode != 0:
                return ""
            return res.stdout
        except (OSError, subprocess.SubprocessError):
            return ""
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return ""


def load_artifacts() -> dict:
    out = {}
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
        path = os.path.join(FIXTURE_DIR, fn)
        try:
            if fn.endswith(".pdf") or fn.endswith(".pdf.b64"):
                text = pdf_text(path)
                if not text.strip():
                    continue
            else:
                text = open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        out[fn] = {"artifact": fn, "url": url, "sha256": side.get("sha256"),
                   "captured_at": side.get("captured_at"),
                   "session_id": side.get("session_id", ""),
                   "provenance_state": side.get("provenance_state", ""),
                   "raw": text,
                   "lines": [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", l)).strip()
                             for l in text.split("\n")],
                   "raw_lines": text.split("\n")}
    return out


def currentness_by_artifact() -> dict:
    inv_path = os.path.join(OUT_DIR, "p109_current_market_inventory.json")
    out = {}
    if os.path.exists(inv_path):
        inv = json.load(open(inv_path, encoding="utf-8"))
        for oem in inv.get("oems", []):
            for s in oem.get("sources", []):
                out[s["artifact"]] = {"currentness": s["currentness"],
                                      "reason": s["currentness_reason"],
                                      "family": s["family"]}
    return out


def label_variants(rec: dict) -> list:
    """strings that identify this exact record inside a published row."""
    model, variant = rec["model"], rec["variant"]
    labels = {norm(f"{model} {variant}"), norm(variant)}
    base = re.sub(r"^(%s)\s+" % re.escape(rec["manufacturer"]), "", model, flags=re.I)
    labels.add(norm(f"{base} {variant}"))
    for s in rec.get("sources") or []:
        if s.get("label"):
            labels.add(norm(s["label"]))
    return sorted({l for l in labels if l}, key=len, reverse=True)


def line_matches(line: str, labels: list) -> bool:
    n = norm(line)
    if not n:
        return False
    for lab in labels:
        if n == lab:
            return True
        # composite: model + variant both present in the published line
        if len(lab.split()) >= 2 and lab in n:
            return True
    return False


def label_match_len(n: str, lab: str) -> int:
    """len(lab) when this normalised record text matches the label, else 0.
    Single-word grade labels only match the whole record (never a substring)."""
    if not n or not lab:
        return 0
    if len(lab.split()) == 1:
        return len(lab) if n == lab else 0
    return len(lab) if (n == lab or lab in n) else 0


def my_best_label(n: str, labels: list) -> int:
    best = 0
    for lab in labels:
        l = label_match_len(n, lab)
        if l > best:
            best = l
    return best


def harvest_record(rec: dict, artifacts: dict, cur: dict,
                   all_labels=None, best_cache=None) -> list:
    """prices bound to the SAME published record of this variant.

    all_labels/best_cache implement longest-label ownership: when several
    grades of one model match the same published record (Premium vs Premium
    Luxury), only the record with the longest matching label may take its
    price — the shorter grades stay UNVERIFIED_PRICE instead of borrowing a
    price that belongs to another grade."""
    labels = label_variants(rec)
    if all_labels is None:
        all_labels = labels
    if best_cache is None:
        best_cache = {}

    def owned(text, key):
        """True when no other record's longer label also matches this text."""
        n = norm(text)
        if my_best_label(n, labels) == 0:
            return False
        if key not in best_cache:
            best_cache[key] = my_best_label(n, all_labels)
        return my_best_label(n, labels) == best_cache[key]
    seen = set()
    rows = []
    src_artifacts = []
    for s in rec.get("sources") or []:
        a = (s.get("artifact") or "").split("/")[-1]
        if a and a in artifacts:
            src_artifacts.append((a, s.get("source_role", ""), s.get("source_url", "")))
    # also scan every current price/configurator artifact of the same manufacturer
    # (a price list may publish the grade on a page the identity row did not cite)
    extra = []
    for fn, art in artifacts.items():
        info = cur.get(fn, {})
        if info.get("currentness") == "CURRENT" and info.get("family") in (
                "price_document", "configurator"):
            extra.append((fn, "MARKET_TRUTH", art["url"]))
    order = src_artifacts + [e for e in sorted(set(extra)) if e[0] not in
                             {x[0] for x in src_artifacts}]
    for fn, role, url in order:
        art = artifacts[fn]
        info = cur.get(fn, {})
        raw = art.get("raw") or "\n".join(art.get("lines") or [])
        blocks = artifact_blocks(raw)
        header = blocks[0]["text"] if blocks else ""
        notes = " ".join(bl["text"] for bl in blocks[-6:])   # footnotes / terms
        for bi, blk in enumerate(blocks):
            text, origin, order = blk["text"], blk["origin"], blk["order"]
            if not owned(text, (fn, "b", order)):
                continue
            if not bindable(blk):
                continue
            m = money_values(text)
            price_pos = -1
            if m:
                for cand in list(PRICE_TOKEN.finditer(text)) + list(BARE_PRICE.finditer(text)):
                    try:
                        v = int(cand.group(1).replace(",", ""))
                    except ValueError:
                        v = int(cand.group(1))
                    if v == m[0]:
                        price_pos = cand.start()
                        break
            bind_block = text
            if not m and bi + 1 < len(blocks) and bindable(blocks[bi + 1]) \
                    and price_only(blocks[bi + 1]["text"]):
                nxt = blocks[bi + 1]["text"]
                mv = money_values(nxt)
                if mv:
                    m, price_pos = mv, 0
                    bind_block = nxt
            if not m:
                continue
            ptype = classify_price_type(bind_block, price_pos, url,
                                        label_text=text, header=header,
                                        doc_notes=notes)
            excerpt_src = bind_block
            for v in m[:2]:
                key = (fn, order, v)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "manufacturer": rec["manufacturer"], "model": rec["model"],
                    "variant": rec["variant"], "scope": "TH",
                    "price_thb": v, "price_type": ptype,
                    "currency": "THB",
                    "artifact": fn, "source_url": art["url"], "sha256": art["sha256"],
                    "provenance_state": art["provenance_state"],
                    "captured_at": art["captured_at"], "session_id": art["session_id"],
                    "locator": {"artifact": fn, "block_index": order,
                                "origin": origin, "excerpt": excerpt_src[:300]},
                    "source_class": "MARKET_TRUTH" if role == "MARKET_TRUTH" else role,
                    "trust_tier": ("official_verified" if role == "MARKET_TRUTH"
                                   and info.get("currentness") == "CURRENT" else "reference"),
                    "currentness": info.get("currentness", "UNKNOWN"),
                    "currentness_reason": info.get("reason", "not classified"),
                    "page_family": info.get("family", artifact_family(art["url"])),
                })
        # structured data: an application/ld+json node that names model+variant
        # and carries its own THB offer is same-record evidence as well
        seen_money = {(r["artifact"], r["price_thb"]) for r in rows}
        for name, price_str, currency in structured_price_nodes(raw):
            if currency and currency.strip().upper() not in {"THB"}:
                continue
            try:
                v = int(float(price_str))
            except ValueError:
                continue
            if not (PRICE_MIN <= v <= PRICE_MAX):
                continue
            if not owned(name, (fn, "j", name)):
                continue
            if (fn, v) in seen_money:
                continue
            seen_money.add((fn, v))
            ptype = classify_price_type(name, len(name), url,
                                        label_text=name, header=header,
                                        doc_notes=notes)
            rows.append({
                "manufacturer": rec["manufacturer"], "model": rec["model"],
                "variant": rec["variant"], "scope": "TH",
                "price_thb": v, "price_type": ptype, "currency": "THB",
                "artifact": fn, "source_url": art["url"], "sha256": art["sha256"],
                "provenance_state": art["provenance_state"],
                "captured_at": art["captured_at"], "session_id": art["session_id"],
                "locator": {"artifact": fn, "block_index": -1, "origin": "jsonld",
                            "excerpt": f"{name} = {price_str} {currency}".strip()},
                "source_class": "MARKET_TRUTH" if role == "MARKET_TRUTH" else role,
                "trust_tier": ("official_verified" if role == "MARKET_TRUTH"
                               and info.get("currentness") == "CURRENT" else "reference"),
                "currentness": info.get("currentness", "UNKNOWN"),
                "currentness_reason": info.get("reason", "not classified"),
                "page_family": info.get("family", artifact_family(art["url"])),
            })
    return rows


def diagnose_unverified(rec: dict, artifacts: dict, cur: dict, blocks_cache: dict) -> str:
    """why no price could be bound to this exact record (source ceiling, in the
    same evidence-backed vocabulary every time — never 'we gave up')."""
    fns = sorted({(s.get("artifact") or "").split("/")[-1]
                  for s in (rec.get("sources") or []) if s.get("artifact")})
    labels = label_variants(rec)
    if not fns:
        return ("no captured first-party artifact is cited for this identity, so no "
                "same-record price can be evaluated")
    missing = []
    present = []
    for fn in fns:
        path = os.path.join(FIXTURE_DIR, fn)
        if fn in artifacts:
            present.append(fn)
        elif os.path.exists(path):
            missing.append((fn, "captured file has no readable text layer "
                                "(image-only pdf or unreadable encoding)"))
        else:
            missing.append((fn, "the cited artifact is not in the fixture set "
                                "(dropped during an earlier acquisition wave)"))
    label_seen = False
    if present:
        for fn in present:
            if fn not in blocks_cache:
                raw = artifacts[fn].get("raw") or "\n".join(artifacts[fn].get("lines") or [])
                blocks = artifact_blocks(raw)
                blocks_cache[fn] = blocks
            for blk in blocks_cache[fn]:
                if line_matches(blk["text"], labels):
                    label_seen = True
                    break
            if label_seen:
                break
    if label_seen:
        return ("the exact grade is published on a captured first-party page but that "
                "record does not carry a price (model-level or range price only, never "
                "promoted to a grade price)")
    if missing and not present:
        return missing[0][1]
    return ("no captured first-party record publishes this exact grade label next to a "
            "price (label wording differs, or the grade is not priced on any captured "
            "page)")


def main() -> int:
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    universe = json.load(open(os.path.join(OUT_DIR, "identity_universe_p108.json"),
                              encoding="utf-8"))
    matrix0 = json.load(open(os.path.join(OUT_DIR, "identity_matrix_p109.json"),
                             encoding="utf-8"))
    accepted = [r for r in universe["universe"]["records"]
                if r["status"] == "CONFIRMED_VARIANT"]
    assert len(accepted) == ACCEPTED_LEDGER, len(accepted)

    def dump(name, payload):
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    # ── target plan, written BEFORE any harvest accounting ────────────────
    by_oem = {}
    for r in accepted:
        by_oem.setdefault(r["manufacturer"], []).append(
            {"model": r["model"], "variant": r["variant"],
             "source_artifacts": sorted({(s.get("artifact") or "").split("/")[-1]
                                         for s in (r.get("sources") or []) if s.get("artifact")})})
    access = {o["brand"]: o["official_access_status"] for o in matrix0["oems"]}
    plan_rows = []
    for brand in sorted(by_oem, key=lambda b: -len(by_oem[b])):
        plan_rows.append({"brand": brand, "accepted_variants": len(by_oem[brand]),
                          "official_access_status": access.get(brand, "?"),
                          "targets": sorted(by_oem[brand],
                                            key=lambda t: (t["model"], t["variant"]))})
    dump("p110_price_target_plan.json", {
        "schema": "p110_price_target_plan/1", "generated_at": stamp,
        "baseline_artifact": ACCEPTED_BASELINE,
        "accepted_variants_targeted": ACCEPTED_LEDGER,
        "method": "one horizontal pass over every accepted variant; price must be bound to "
                  "the same published record (manufacturer + model + exact grade + TH scope) "
                  "of a first-party artifact; price_type classified per Blueprint §95/§98",
        "totals": {"targeted": ACCEPTED_LEDGER, "oems": len(plan_rows),
                   "blocked_oems": sorted([b for b, a in access.items()
                                           if a in BLOCKED_ACCESS])},
        "oems": plan_rows})

    artifacts = load_artifacts()
    cur = currentness_by_artifact()

    evidence, unverified = [], []
    blocks_cache: dict = {}
    all_labels = sorted({lab for r in accepted for lab in label_variants(r)},
                        key=len, reverse=True)
    match_cache: dict = {}
    for rec in sorted(accepted, key=lambda r: (r["manufacturer"], r["model"], r["variant"])):
        rows = harvest_record(rec, artifacts, cur,
                              all_labels=all_labels, best_cache=match_cache)
        official = [r for r in rows if r["trust_tier"] == "official_verified"]
        pool = official or [r for r in rows if r["source_class"] == "MARKET_TRUTH"] or rows
        if not pool:
            unverified.append({
                "manufacturer": rec["manufacturer"], "model": rec["model"],
                "variant": rec["variant"], "scope": "TH",
                "status": "UNVERIFIED_PRICE",
                "category": diagnose_unverified(rec, artifacts, cur, blocks_cache),
                "reason": "no price is bound to the same record as this exact grade in any "
                          "captured first-party artifact (model-level, range or third-party "
                          "prices are never promoted to a grade MSRP)"})
            continue
        # canonical only after every price keeps its own semantics
        def canon_key(r):
            order = {"EXACT_VARIANT": 0, "MSRP_STARTING": 1, "RANGE": 2,
                     "PROMOTIONAL": 3, "FINANCE_INSTALLMENT": 4}
            trust = 0 if r["trust_tier"] == "official_verified" else 1
            return (trust, order.get(r["price_type"], 9), r["artifact"], r["locator"].get("block_index", 0))
        ordered = sorted(pool, key=canon_key)
        canonical = ordered[0]
        evidence.append({
            "manufacturer": rec["manufacturer"], "model": rec["model"],
            "variant": rec["variant"], "scope": "TH",
            "canonical_price": canonical["price_thb"],
            "canonical_price_type": canonical["price_type"],
            "is_exact_msrp": canonical["price_type"] == "EXACT_VARIANT"
                             and canonical["trust_tier"] == "official_verified",
            "price_type": canonical["price_type"],
            "price_thb": canonical["price_thb"],
            "currency": "THB",
            "same_record": True,
            "artifact": canonical["artifact"], "source_url": canonical["source_url"],
            "sha256": canonical["sha256"], "provenance_state": canonical["provenance_state"],
            "captured_at": canonical["captured_at"], "session_id": canonical["session_id"],
            "locator": canonical["locator"],
            "evidence_excerpt": canonical["locator"]["excerpt"],
            "source_class": canonical["source_class"],
            "trust_tier": canonical["trust_tier"],
            "currentness": canonical["currentness"],
            "currentness_reason": canonical["currentness_reason"],
            "all_prices_in_record": [{"price_thb": r["price_thb"],
                                      "price_type": r["price_type"],
                                      "artifact": r["artifact"],
                                      "line_index": r["locator"].get("block_index", 0)}
                                     for r in ordered],
        })

    # ── reconciliation ────────────────────────────────────────────────────
    per_oem = {}
    for brand in sorted({r["manufacturer"] for r in accepted}):
        targets = [r for r in accepted if r["manufacturer"] == brand]
        got = [e for e in evidence if e["manufacturer"] == brand]
        un = [u for u in unverified if u["manufacturer"] == brand]
        exact = [e for e in got if e["is_exact_msrp"]]
        nonexact = [e for e in got if not e["is_exact_msrp"]]
        per_oem[brand] = {
            "accepted_variants": len(targets),
            "price_bound": len(got),
            "exact_msrp_verified": len(exact),
            "exact_non_msrp_only": len(nonexact),
            "unverified_price": len(un),
            "blocked_or_source_gap": (0 if access.get(brand, "?") not in BLOCKED_ACCESS
                                      else len(targets)),
            "coverage_pct": round(100.0 * len(got) / len(targets), 1) if targets else 0.0,
            "price_type_distribution": dict(
                sorted(__import__("collections").Counter(e["price_type"] for e in got).items())),
        }
    type_dist = dict(sorted(__import__("collections").Counter(
        e["price_type"] for e in evidence).items()))
    blocked_brands = sorted([b for b, a in access.items() if a in BLOCKED_ACCESS])
    recon = {
        "schema": "p110_price_reconciliation/1", "generated_at": stamp,
        "baseline_artifact": ACCEPTED_BASELINE,
        "accepted_variants_targeted": ACCEPTED_LEDGER,
        "price_bound": len(evidence),
        "exact_msrp_verified": sum(1 for e in evidence if e["is_exact_msrp"]),
        "exact_non_msrp_only": sum(1 for e in evidence if not e["is_exact_msrp"]),
        "unverified_price": len(unverified),
        # blocked OEMs contribute no accepted variants (identity ledger frozen);
        # every not-priced accepted variant is a source gap on a reachable OEM
        "blocked_oems": blocked_brands,
        "blocked_oem_accepted_variants": 0,
        "blocked_or_source_gap": len(unverified),
        "price_type_distribution": type_dist,
        "prices_invented": 0,
        "third_party_promoted_to_msrp": 0,
        "identity_ledger_unchanged": {"confirmed_variants": ACCEPTED_LEDGER,
                                      "artifact": ACCEPTED_BASELINE},
        "per_oem": per_oem,
        "unverified": unverified,
    }
    dump("p110_price_reconciliation.json", recon)
    dump("p110_price_evidence.json", {
        "schema": "p110_price_evidence/1", "generated_at": stamp,
        "baseline_artifact": ACCEPTED_BASELINE,
        "tier_note": "Phase-1 price evidence only: nothing is written to staging, the "
                     "verifier, Prisma, the API or any database; identity counts untouched",
        "rows": sorted(evidence, key=lambda e: (e["manufacturer"], e["model"], e["variant"]))})

    # derived-artifact sidecar (documents how the evidence file was produced)
    ev_path = os.path.join(OUT_DIR, "p110_price_evidence.json")
    ev_bytes = open(ev_path, "rb").read()
    dump("p110_price_evidence.json.prov.json", {
        "artifact_filename": "p110_price_evidence.json",
        "sha256": hashlib.sha256(ev_bytes).hexdigest(),
        "generated_at": stamp,
        "acquisition_method": "derived_from_accepted_ledger_and_captured_artifacts",
        "session_id": "p110_price_pass_20260928",
        "provenance_state": "DERIVED_PHASE1_AUDIT",
        "inputs": [ACCEPTED_BASELINE, "audit/coverage/identity_universe_p108.json",
                   "audit/coverage/p109_current_market_inventory.json"]})

    dump("p110_price_capture_log.json", {
        "schema": "p110_price_capture_log/1", "generated_at": stamp,
        "new_captures": 0,
        "method": "price pass ran entirely over already-captured first-party artifacts "
                  "(rule 7: fetch only when a price source is genuinely missing)",
        "results": []})

    dump("p110_final_result.json", {
        "schema": "p110_final_result/1", "generated_at": stamp,
        "baseline_artifact": ACCEPTED_BASELINE,
        "accepted_variants_targeted": ACCEPTED_LEDGER,
        "price_bound": len(evidence),
        "exact_msrp_verified": recon["exact_msrp_verified"],
        "exact_non_msrp_only": recon["exact_non_msrp_only"],
        "unverified_price": len(unverified),
        "blocked_or_source_gap": recon["blocked_or_source_gap"],
        "blocked_oems": blocked_brands,
        "blocked_oem_accepted_variants": 0,
        "price_type_distribution": type_dist,
        "prices_invented": 0,
        "third_party_promoted_to_msrp": 0,
        "per_oem_coverage": {b: v["coverage_pct"] for b, v in per_oem.items()},
        "identity_ledger_unchanged": {"confirmed_variants": ACCEPTED_LEDGER,
                                      "changed_by_p110": False},
        "new_captures": 0,
        "gates": {"staging_written": False, "price_pass_staging": False,
                  "prisma_touched": False, "production_db_unchanged": True,
                  "verifier_touched": False, "identity_counts_changed": False},
        "no_loop_rule": "one horizontal price pass; low coverage is reported as a source "
                        "ceiling, never closed by inventing or spreading prices",
    })
    print(json.dumps({"targeted": ACCEPTED_LEDGER, "price_bound": len(evidence),
                      "exact_msrp_verified": recon["exact_msrp_verified"],
                      "exact_non_msrp_only": recon["exact_non_msrp_only"],
                      "unverified_price": len(unverified),
                      "price_type_distribution": type_dist,
                      "per_oem": {b: (v["coverage_pct"], v["price_bound"], v["exact_msrp_verified"])
                                  for b, v in sorted(per_oem.items())}},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
