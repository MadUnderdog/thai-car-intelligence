#!/usr/bin/env python3
"""Stage the media batch as AUTOMOTIVE_MEDIA / RESEARCH_UNVERIFIED observations.

Every record keeps: artifact SHA + sidecar capture time from the official
AcquisitionWriter sidecar, a resolvable locator (verified unique in the artifact
bytes), the evidence excerpt with its content hash, and the subject-scope proof
that the page's own title/URL declare which brand, and which heading declares
which model, the figure belongs to.

Media records are NEVER promoted to official and are written to their own file
so no official row can pick up a media locator by accident.
"""
import dataclasses
import hashlib
import json
import os
import re
import sys
import unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "lib"))

import importlib.util  # noqa: E402


def import_9carthai():
    """The extractors directory is not a package (hyphenated name), so load the
    maintained parser by path instead of importing it."""
    p = os.path.join(REPO, "scripts", "thai-media-extractors", "9carthai_parser.py")
    spec = importlib.util.spec_from_file_location("n9carthai_parser", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

ART_DIR = os.path.join(REPO, "tests", "fixtures", "media-artifacts")
OUT = os.path.join(REPO, "audit", "data-staging", "media_observations.jsonl")
BASE = "https://www.9carthai.com"
BATCH = ["toyota", "honda", "mazda"]
SOURCE_CLASS = "AUTOMOTIVE_MEDIA"
TRUST = "RESEARCH_UNVERIFIED"


def page_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def heading_for(model: str, html: str) -> str:
    """scope proof: a heading on the page that names this model."""
    pat = re.compile(r"<h[23][^>]*>(.*?)</h[23]>", re.S | re.I)
    for m in pat.finditer(html):
        text = re.sub(r"<[^>]+>", " ", m.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        if model.lower() in text.lower() and len(text) < 200:
            return text
    return ""


def locate(raw: str, artifact_path: str, needle: str | None):
    """Deterministic text locator: the first occurrence of a snippet that is
    verified to occur exactly once in the artifact bytes."""
    if not needle or raw.count(needle) != 1:
        return None
    if raw.count(needle) != 1:
        return None
    return {
        "artifact_path": artifact_path,
        "method": "text_search",
        "selector": needle,
        "text_offset": raw.index(needle),
    }


def evidence_snippet(raw: str, obs) -> str | None:
    """Narrow, unique snippet carrying model + variant + figure."""
    excerpt = (obs.evidence_excerpt or "").strip()
    candidates = []
    if len(excerpt) >= 24:
        candidates.append(excerpt)
    model = obs.model or ""
    variant = obs.variant or ""
    value = obs.raw_value or ""
    if model and value:
        m = re.search(re.escape(model) + r"[^。\n]{0,80}", raw, re.I)
        if m:
            candidates.append(m.group(0).strip())
        if variant and variant != "__MODEL_RANGE__":
            idx = raw.lower().find(model.lower())
            if idx >= 0:
                window = raw[idx:idx + 400]
                if value in window:
                    candidates.append(window.split("\n")[0].strip()[:300])
    for cand in candidates:
        cand = re.sub(r"\s+", " ", cand).strip()
        if cand and raw.count(cand) == 1:
            return cand
    return None


def norm_model(name: str) -> str:
    """Conservative canonical form for cross-source matching only — no merging
    of names beyond case/space/strip normalization."""
    if not name:
        return ""
    s = unicodedata.normalize("NFC", name).lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main() -> int:
    parser_mod = import_9carthai()
    records, skipped = [], []
    for brand in BATCH:
        rel = f"tests/fixtures/media-artifacts/9carthai_{brand}_price.html"
        path = os.path.join(REPO, rel)
        sidecar_path = path + ".prov.json"
        side = json.load(open(sidecar_path, encoding="utf-8"))
        raw = open(path, encoding="utf-8", errors="ignore").read()
        title = page_title(raw)
        url = f"{BASE}/{brand}-price/"

        # subject-scope gate: the artifact must declare its own brand scope
        if brand.lower() not in title.lower():
            skipped.append({"brand": brand, "why": "title lacks brand scope", "title": title[:80]})
            continue

        obs_list, rejections = parser_mod.parse_brand_page(raw, brand, url)
        for n, obs in enumerate(obs_list):
            snippet = evidence_snippet(raw, obs)
            locator = locate(raw, rel, snippet)
            if locator is None:
                skipped.append({"brand": brand, "model": obs.model, "why": "no unique locator"})
                continue
            heading = heading_for(obs.model or "", raw)
            if not heading:
                skipped.append({"brand": brand, "model": obs.model, "why": "no model heading"})
                continue
            value = None
            m = re.search(r"\d+", (obs.normalized_value or "").replace(",", ""))
            if m:
                value = int(m.group(0))
            if value is None:
                skipped.append({"brand": brand, "model": obs.model, "why": "no numeric value"})
                continue
            records.append({
                "observation_id": f"media_9carthai_{brand}_{n:03d}",
                "source_class": SOURCE_CLASS,
                "trust_state": TRUST,
                "source": {
                    "name": obs.source_name or "9CARTHAI",
                    "domain": "9carthai.com",
                    "url": url,
                    "artifact_path": rel,
                    "artifact_sha256": side["sha256"],
                    "sidecar_path": os.path.relpath(sidecar_path, REPO),
                    "captured_at": side["captured_at"],
                    "acquisition_method": side["acquisition_method"],
                    "parser": "9carthai_parser.parse_brand_page",
                    "parser_source_class": obs.source_class,
                },
                "subject_scope": {
                    "url_scope": url,
                    "page_title": title,
                    "title_declares_brand": brand.lower() in title.lower(),
                    "model_heading": heading,
                    "identity_scope": obs.scope,
                },
                "identity": {
                    "brand_normalized": norm_model(obs.brand),
                    "model_raw": obs.model,
                    "model_normalized": norm_model(obs.model),
                    "variant_raw": None if obs.variant == "__MODEL_RANGE__" else obs.variant,
                    "identity_scope": obs.scope,
                },
                "field": {
                    "obs_field": obs.obs_field,
                    "value_thb": value,
                    "raw_value": obs.raw_value,
                    "unit": obs.unit,
                    "price_type": obs.price_type,
                    "price_scope": obs.scope,
                },
                # normalized alias of field.value_thb so the same re-resolution
                # engine can prove media locators too; source_class/trust_state
                # on this record still say media, never official
                "price": {
                    "value_thb": value,
                    "type": obs.price_type,
                    "currency": obs.unit or "THB",
                },
                "evidence": {
                    "locator": locator,
                    "excerpt": snippet,
                    "content_hash": obs.content_hash,
                    "extraction_method": obs.extraction_method,
                    "extraction_method_note": "unchanged parser output; media never promoted",
                },
                "staging_timestamp": None,   # filled below
            })

    stamp = max(r["source"]["captured_at"] for r in records) if records else None
    for r in records:
        r["staging_timestamp"] = stamp

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = {
        "records": len(records),
        "by_brand": {b: sum(1 for r in records if f"_{b}_" in r["observation_id"]) for b in BATCH},
        "skipped": len(skipped),
        "skip_reasons": {},
        "source_class": SOURCE_CLASS,
        "trust_state": TRUST,
        "artifacts": [f"tests/fixtures/media-artifacts/9carthai_{b}_price.html" for b in BATCH],
    }
    for s in skipped:
        summary["skip_reasons"][s["why"]] = summary["skip_reasons"].get(s["why"], 0) + 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if records else 1


if __name__ == "__main__":
    raise SystemExit(main())
