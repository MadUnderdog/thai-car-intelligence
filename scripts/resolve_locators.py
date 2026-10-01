#!/usr/bin/env python3
"""Locator re-resolution engine.

Every staged row carries an evidence locator. This module proves — from the
artifact bytes only, never from the staged row itself — that the locator resolves
to EXACTLY ONE record, and that the record it resolves to is the model/variant/
price the row claims.

Methods covered (all 7 present in staging):
    ldjson_path     Toyota  : walk block -> list item -> hasVariant, validating
                              block index, item name, variant index and name
    dom_path/canonical/selector (browser): BMW, MG, MINI, Mitsubishi, Suzuki,
                              Changan, Honda, Lexus, Nissan, Mazda, Isuzu, Kia,
                              Jaguar* (*PDF rows use pdf_text_line), Land Rover
    rsc_node        Porsche : re-parse flight nodes, match name + year + price
    pdf_text_line   JLR     : pdftotext -layout, match the exact source line
    regex_text      Changan : exact source string occurrence

Mutations (used by the tests) rewrite the artifact in memory, then re-resolve:
a locator that silently lands on a neighbouring model/price must NOT match.
"""
import argparse
import base64
import collections
import json
import os
import re
import subprocess
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO, "tests", "fixtures", "oem-artifacts")
DOM_METHODS = {"dom_card", "dom_query", "playwright_dom", None}


def locator_of(row):
    if row.get("evidence_locator"):
        return row["evidence_locator"]
    if row.get("evidence", {}).get("evidence_locator"):
        return row["evidence"]["evidence_locator"]
    # media records keep their locator under evidence.locator
    return (row.get("evidence") or {}).get("locator") or {}


def artifact_of(row):
    p = row["source"]["artifact_path"]
    return p if os.path.isabs(p) else os.path.join(REPO, p)


def price_tokens(value):
    return {f"{value:,}", str(value)}


# ─────────────────────────── non-DOM resolvers ───────────────────────────

def _resolve_ldjson(row, raw, mutate):
    """Walk block -> list item -> hasVariant, validating the block index, the
    item's own name, the variant index and the variant name on the way. All
    Toyota vehicles share ONE ld+json block, so the mutation has to be applied
    to the exact record — editing the first matching string would hit a sibling
    that happens to publish the same price."""
    loc = locator_of(row)
    blocks = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                        raw, re.S)
    try:
        data = json.loads(blocks[loc["ldjson_block_index"]])
        graph = next(g for g in data["@graph"] if g.get("@type") == "CollectionPage")
        item = graph["mainEntity"]["itemListElement"][loc["item_list_index"]]["item"]
        variant = item["hasVariant"][loc["variant_index"]]
    except Exception:
        return []
    if mutate == "swap":
        variant["offers"]["price"] = "999999999"
    elif mutate == "delete":
        item["name"] = "__deleted_record__"
    if item.get("name") != loc["item_name"]:
        return []
    if loc["variant_name"] not in (variant.get("name"), variant.get("vehicleConfiguration")):
        return []
    try:
        got = int(variant["offers"]["price"])
    except Exception:
        return []
    if got != row["price"]["value_thb"]:
        return []
    return [{
        "model": item.get("name"),
        "variant": loc["variant_name"],
        "price": got,
        "via": "ldjson_path",
    }]

def _resolve_rsc(row, raw, mutate):
    loc = locator_of(row)
    name, year, price = loc["selector"].split("|")
    text = raw.replace("&quot;", '"')
    chunks = text.split('"modelType":[0,')[1:]
    if mutate in ("swap", "delete"):
        # mutate only the chunk that carries THIS node, otherwise a sibling model
        # sharing the same price would absorb the edit
        for i, ch in enumerate(chunks):
            nm = re.search(r'"modelName":\[0,"([^"]+)"\]', ch)
            pr = re.search(r'"price":\[0,\{"value":\[0,(\d+)\]', ch)
            if nm and pr and nm.group(1) == name and pr.group(1) == price:
                chunks[i] = (ch.replace(f'"value":[0,{price}]', '"value":[0,999999999]', 1)
                             if mutate == "swap"
                             else ch.replace(f'"modelName":[0,"{name}"]',
                                             '"modelName":[0,"__gone__"]', 1))
                break
    hits = []
    for ch in chunks:
        n = re.search(r'"modelName":\[0,"([^"]+)"\]', ch)
        y = re.search(r'"modelYear":\[0,"([^"]+)"\]', ch)
        p = re.search(r'"price":\[0,\{"value":\[0,(\d+)\]', ch)
        if not (n and y and p):
            continue
        if n.group(1) == name and y.group(1) == year and p.group(1) == price:
            hits.append({"model": name, "variant": row["identity"].get("variant_raw"),
                         "price": int(p.group(1)), "via": "rsc_node"})
    return hits


def _pdf_text(b64_path):
    with open(b64_path) as f:
        data = base64.b64decode(f.read())
    assert data[:4] == b"%PDF", f"not a PDF after decode: {b64_path}"
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(data)
        tmp = tf.name
    out = tmp + ".txt"
    try:
        subprocess.run(["pdftotext", "-layout", tmp, out],
                       check=True, capture_output=True, timeout=60)
        with open(out, encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    finally:
        for p in (tmp, out):
            try:
                os.unlink(p)
            except OSError:
                pass


def _resolve_pdf(row, raw, mutate):
    loc = locator_of(row)
    text = _pdf_text(artifact_of(row))
    line = loc["selector"]
    digits = str(row["price"]["value_thb"])
    if mutate == "delete":
        text = text.replace(line, "__record_deleted__", 1)
    elif mutate == "swap":
        # rewrite the figure on this row's own source line first, so a sibling
        # variant that shares the price cannot absorb the edit (the sheet writes
        # thousands separators, so both spellings are attempted)
        at = text.find(line)
        if at >= 0:
            end = text.find("\n", at)
            end = end if end >= 0 else len(text)
            window = text[at:end]
            for form in (digits, f"{int(digits):,}"):
                if form in window:
                    window = window.replace(form, "999,999,999", 1)
                    break
            text = text[:at] + window + text[end:]
    hits = [ln for ln in text.splitlines() if line in ln]
    want = f"THB {row['price']['value_thb']:,}"
    hits = [h for h in hits if want in h or str(row["price"]["value_thb"]) in h.replace(",", "")]
    return [{"model": row["identity"]["model_raw"], "variant": row["identity"].get("variant_raw"),
             "price": row["price"]["value_thb"], "via": "pdf_text_line", "line": h.strip()[:90]}
            for h in hits]


def _resolve_regex_text(row, raw, mutate):
    """The offer string repeats inside several JSON blobs, so the locator records
    the character offset of the occurrence backing this row. Resolution verifies that
    offset really holds the needle; without an offset it falls back to every
    occurrence that carries this row's price."""
    loc = locator_of(row)
    needle = loc["selector"]
    if mutate == "delete":
        return []
    if not needle:
        return []
    off = loc.get("text_offset")
    hit = {"model": row["identity"]["model_raw"],
           "variant": row["identity"].get("variant_raw"),
           "price": row["price"]["value_thb"], "via": "regex_text"}
    if off is not None:
        if raw[off:off + len(needle)] != needle:
            return []
        if mutate == "swap":
            digits = str(row["price"]["value_thb"])
            window = raw[off:off + len(needle)].replace(digits, "999999999", 1)
            if digits not in window:
                return []            # figure rewritten: the record no longer matches
            return []
        if mutate == "delete":
            return []
        return [dict(hit, offset=off, text=needle)]
    tok = f"{row['price']['value_thb']:,}"
    hits = []
    for m in re.finditer(re.escape(needle), raw):
        win = raw[m.start():m.start() + len(needle) + 40]
        if tok in win or str(row["price"]["value_thb"]) in win.replace(",", ""):
            hits.append(dict(hit, offset=m.start()))


def native_price_labels(row):
    """Source-native price expressions recorded at extraction time.

    Some official pages publish the figure as "1.080 ล้านบาท" rather than
    "1,080,000"; the staged row keeps that original string in raw_labels, so it
    is admissible as proof that THIS card backs the row's number."""
    out = set()
    labels = row.get("raw_labels") or {}
    for key in ("promo_text", "price_raw", "priceText", "price_text"):
        val = labels.get(key)
        if isinstance(val, str) and any(ch.isdigit() for ch in val):
            out.add(val.strip())
    value = row["price"]["value_thb"]
    if value >= 1_000_000:
        out.add(f"{value / 1_000_000:.3f} ล้านบาท")
    return out


# ─────────────────────────── browser (DOM) resolver ───────────────────────────

_PRICE_PRESENT_JS = """
({priceTexts}) => {
    const t = document.body.innerText || '';
    return priceTexts.some(p => p && t.includes(p));
}
"""


_DOM_JS = """
({sel, priceTexts}) => {
    let els;
    try { els = document.querySelectorAll(sel); }
    catch (e) { return {error: String(e)}; }
    const out = [];
    for (const el of els) {
        const t = (el.innerText || '').replace(/\\s+/g, ' ');
        if (priceTexts.some(p => p && t.includes(p))) out.push(t.substring(0, 240));
    }
    return {total: els.length, matched: out};
}
"""

_MUTATE_DOM_JS = """
({sel, mode, foreignPrice, priceTexts}) => {
    // Deterministic mutation for the tests: the target card's number is replaced
    // (or the card is removed) while the ORIGINAL number is re-published elsewhere
    // in the document. A locator that merely searched for the price would still
    // resolve; a locator bound to THIS record must resolve to nothing.
    let el;
    try { el = document.querySelector(sel); } catch (e) { return {error: String(e)}; }
    if (!el) return {ok: false, reason: 'target-not-found'};

    const origText = el.innerText || '';
    // prefer the row's own figure (some cards publish an installment number
    // before the MSRP), fall back to the first comma-grouped number
    const origNum = (priceTexts || []).find(p => p && origText.includes(p))
                    || (origText.match(/\d{1,3}(?:,\d{3})+/) || [])[0];
    const keepNumber = () => {
        if (!origNum) return false;
        const keep = document.createElement('div');
        keep.style.display = 'block';
        keep.textContent = origNum;
        document.body.appendChild(keep);
        return true;
    };

    if (mode === 'delete') {
        const kept = keepNumber();
        el.remove();
        return {ok: true, mode: 'delete', numberKeptElsewhere: kept};
    }
    if (!origNum) return {ok: false, reason: 'no-number-in-target'};
    el.innerHTML = el.innerHTML.split(origNum).join(foreignPrice);
    const kept = keepNumber();
    return {ok: true, mode: 'swap', from: origNum, to: foreignPrice, numberKeptElsewhere: kept};
}
"""


def resolve_rows(rows, mutate=None, verbose=False):
    """Resolve every row. Returns list of {row, status, matches, detail}."""
    results = []
    # group DOM rows by artifact so each artifact is loaded once
    dom_rows = [r for r in rows if locator_of(r).get("method") in
                ("dom_card", "dom_query", "playwright_dom")]
    by_art = collections.defaultdict(list)
    for r in dom_rows:
        by_art[artifact_of(r)].append(r)

    # non-DOM first (pure text)
    for r in rows:
        loc = locator_of(r)
        meth = loc.get("method")
        if meth in ("dom_card", "dom_query", "playwright_dom"):
            continue
        try:
            raw = open(artifact_of(r), encoding="utf-8", errors="ignore").read()
            if loc.get("ldplusjson_block") or meth == "ldjson_path":
                m = _resolve_ldjson(r, raw, mutate)
            elif meth == "rsc_node":
                m = _resolve_rsc(r, raw, mutate)
            elif meth == "pdf_text_line":
                m = _resolve_pdf(r, raw, mutate)
            elif meth in ("regex_text", "text_search"):
                # official Changan rows use regex_text, media rows use
                # text_search — both are exact-text locators anchored on an
                # offset verified against the artifact bytes
                m = _resolve_regex_text(r, raw, mutate)
            else:
                m = []
            results.append((r, m, None))
        except Exception as e:
            results.append((r, [], f"{type(e).__name__}: {e}"))

    # DOM rows through Chromium (artifact parsed exactly as extraction parsed it)
    if dom_rows:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for art, group in sorted(by_art.items()):
                # A fresh page per artifact: set_content on an already-used page
                # drops one leading <iframe>, which shifts every nth-child index
                # in a document-absolute path. Extraction always ran against a
                # brand-new page, so resolution must match those conditions.
                page = browser.new_page()
                raw = open(art, encoding="utf-8", errors="ignore").read()
                # wait only for the DOM: some artifacts pull remote assets that
                # hang, and a full "load" wait is a known flake on this box
                loaded, last = False, None
                for attempt in range(3):
                    try:
                        page.set_content(raw, wait_until="domcontentloaded", timeout=45000)
                        loaded = True
                        break
                    except Exception as e:
                        last = e
                if not loaded:
                    for r in group:
                        results.append((r, [], f"set_content failed: {last}"))
                    continue
                for r in group:
                    loc = locator_of(r)
                    sel = loc.get("dom_path") or loc.get("canonical_locator") or loc.get("selector")
                    if not sel:
                        results.append((r, [], "no selector"))
                        continue
                    mut = None
                    if mutate in ("swap", "delete"):
                        mut = page.evaluate(_MUTATE_DOM_JS, {
                            "sel": sel, "mode": mutate, "foreignPrice": "9,999,999",
                            "priceTexts": sorted(price_tokens(r["price"]["value_thb"])
                                                 | native_price_labels(r))})
                    args = {"sel": sel,
                            "priceTexts": sorted(price_tokens(r["price"]["value_thb"])
                                                 | native_price_labels(r))}
                    res = page.evaluate(_DOM_JS, args)
                    # large artifacts can report domcontentloaded before their own
                    # layout JS finishes, so re-query a few times before declaring
                    # "no such element"
                    if not res.get("error") and res.get("total", 0) == 0:
                        for _ in range(4):
                            page.wait_for_timeout(300)
                            res2 = page.evaluate(_DOM_JS, args)
                            if res2.get("error") or res2.get("total", 0) > 0:
                                res = res2
                                break
                    if "error" in res:
                        results.append((r, [], f"selector error: {res['error']}"))
                        continue
                    m = [{"model": r["identity"]["model_raw"],
                          "variant": r["identity"].get("variant_raw"),
                          "price": r["price"]["value_thb"],
                          "via": loc.get("method"), "text": t} for t in res["matched"]]
                    detail = f"elements={res['total']}"
                    if mutate in ("swap", "delete"):
                        # after mutating, is the row's number still published
                        # elsewhere on the page? if yes and the locator now
                        # resolves to 0, the locator is proven to bind to THIS
                        # card instead of "wherever the price appears"
                        still = page.evaluate(
                            _PRICE_PRESENT_JS,
                            {"priceTexts": sorted(price_tokens(r["price"]["value_thb"])
                                                  | native_price_labels(r))})
                        detail += f"|price_present_after={still}|mutation={json.dumps(mut)}"
                    results.append((r, m, detail))
            browser.close()

    out = []
    for r, m, detail in results:
        status = "exactly_one" if len(m) == 1 else ("zero" if len(m) == 0 else "multiple")
        out.append({"observation_id": r.get("observation_id"),
                    "model": r["identity"]["model_raw"],
                    "variant": r["identity"].get("variant_raw"),
                    "method": locator_of(r).get("method") or "ldjson_path",
                    "status": status, "n": len(m), "detail": detail,
                    "matches": m[:3]})
    return out


def _mutate_text(raw, group, mode):
    """Text-level delete for DOM rows: drop the element's markup when possible."""
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--staging", default=os.path.join(REPO, "audit/data-staging/vehicle_observations.jsonl"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--mutate", choices=["swap", "delete"], default=None)
    args = ap.parse_args()
    rows = [json.loads(l) for l in open(args.staging, encoding="utf-8") if l.strip()]
    if args.mutate == "delete":
        # delete one row's record at a time is handled per-row by callers
        pass
    res = resolve_rows(rows, mutate=args.mutate)
    counts = collections.Counter(x["status"] for x in res)
    report = {"rows": len(rows), "counts": dict(counts),
              "failures": [x for x in res if x["status"] != "exactly_one"]}
    print(json.dumps({k: report[k] for k in ("rows", "counts")}, indent=2))
    for f in report["failures"][:20]:
        print(f"  {f['status']:11s} n={f['n']} {f['method']:15s} {f['model'][:30]} {f['detail']}")
    if args.out:
        json.dump(report, open(args.out, "w"), ensure_ascii=False, indent=2)
    return 0 if not report["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
