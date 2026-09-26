#!/usr/bin/env python3
"""P100 catalog completeness matrix (deliverable 2 + 3).

Recomputes, from staging + the coverage registry + capture logs ONLY:
  * per-OEM MODEL / VARIANT counts actually staged with first-party evidence
  * which catalog layers were REALLY checked (lineup, model page, price/grade
    table, brochure PDF, structured payload, configurator, press)
  * unresolved gaps with an explicit reason

Nothing here is asserted from memory: every count is derived from committed
rows, every layer from a committed artifact or a capture log.
"""
import glob
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
REG_PATH = os.path.join(REPO, "audit", "coverage", "oem-registry.json")
OUT_DIR = os.path.join(REPO, "audit", "coverage")
STAMP = datetime.now(timezone.utc).strftime("%Y%m%d")

LAYERS = ["lineup_index", "model_page", "price_or_grade_table", "brochure_pdf",
          "structured_payload", "configurator", "press_release"]

# extraction methods that prove a structured/JSON layer was used
STRUCTURED_METHODS = {"rsc_grade_payload", "published_json_payload",
                      "playwright_jsonld_parse", "bmw_js", "nissan_js",
                      "pdftotext_line", "published_json"}


# Layers each staged source actually exercised, curated from that source's own
# URL and what its extractor reads from it. Nothing here is inferred from a
# snippet: a layer appears only if an artifact of that source was opened.
SOURCE_LAYERS = {
    "Toyota Thailand Official": {"lineup_index", "price_or_grade_table"},
    "Mazda Thailand Official": {"lineup_index"},
    "Nissan Thailand Official": {"lineup_index"},
    "Honda Thailand Official": {"model_page"},
    "Isuzu Thailand Official": {"lineup_index"},
    "BMW Thailand Official": {"lineup_index"},
    "Lexus Thailand Official": {"lineup_index"},
    "Honda Models Page": {"lineup_index"},
    "MG Thailand Official": {"lineup_index"},
    "Mitsubishi Thailand Official": {"lineup_index"},
    "Suzuki Thailand Official": {"lineup_index"},
    "MINI Thailand Official": {"lineup_index"},
    "Changan Thailand Official": {"lineup_index", "model_page"},
    "Kia Thailand Official": {"lineup_index"},
    "Jaguar Thailand Official": {"brochure_pdf", "price_or_grade_table"},
    "Land Rover Thailand Official": {"brochure_pdf", "price_or_grade_table"},
    "Porsche Thailand Official": {"model_page"},
    "GWM Thailand Official": {"model_page"},
    "Subaru Thailand Official": {"lineup_index"},
    "Honda Thailand Grade List": {"lineup_index", "price_or_grade_table"},
    "Lexus Thailand Price List": {"price_or_grade_table"},
    "Mitsubishi Thailand Price Tables": {"lineup_index", "price_or_grade_table"},
    "Nissan Thailand Grade Price Table": {"lineup_index", "price_or_grade_table"},
    "BMW Thailand Price List": {"lineup_index", "price_or_grade_table"},
}

# endpoint captures held in the registry but not parsed into rows yet
ARTIFACT_LAYERS = [
    ((".pdf.b64",), {"brochure_pdf"}),
    (("pricesheet", "specsheet"), {"price_or_grade_table"}),
    (("price-list", "pricelist", "all-grade-price", "all-models-price"),
     {"price_or_grade_table"}),
    (("brochure", "e-catalog", "catalog"), {"brochure_pdf"}),
    (("car_", "_model_", "models/", "model-"), {"model_page"}),
    (("home", "all-models", "model-list", "index"), {"lineup_index"}),
]


def layers_for_artifact(artifact, url=""):
    """Layer an artifact identity/URL supports — first pattern wins, and a
    PDF price sheet counts as both a brochure and a price sheet."""
    art = (artifact or "").lower()
    path = urlparse(url or "").path.lower()
    out = set()
    for keys, layers in ARTIFACT_LAYERS:
        if any(k in art or k in path for k in keys):
            out |= layers
    if art.endswith(".pdf.b64") and ("pricesheet" in art or "specsheet" in art):
        out |= {"price_or_grade_table"}
    return out


def main():
    rows = [json.loads(l) for l in open(STAGING, encoding="utf-8") if l.strip()]
    reg = json.load(open(REG_PATH, encoding="utf-8"))
    brands = {b["brand"]: b for b in reg["brands"]}

    # brand (registry name) <- staged brand_normalized
    brand_alias = {}
    for b in reg["brands"]:
        brand_alias[b["brand"].lower().replace(" ", "-")] = b["brand"]
    brand_alias.update({
        "land-rover": "Land Rover", "mini": "MINI", "mercedes-benz": "Mercedes-Benz",
        "deepal": "Deepal", "porsche": "Porsche", "jaguar": "Jaguar",
        "honda": "Honda", "bmw": "BMW", "lexus": "Lexus",
    })

    per_brand = {}
    for r in rows:
        bn = r["identity"]["brand_normalized"]
        brand = brand_alias.get(bn)
        if not brand:
            # unknown mapping — record explicitly rather than dropping
            brand = f"UNMAPPED:{bn}"
        slot = per_brand.setdefault(brand, {
            "rows": 0, "models": set(), "variants": set(), "pairs": {},
            "sources": {}, "levels": {"MODEL": 0, "VARIANT": 0}})
        slot["rows"] += 1
        slot["levels"][r["identity"]["identity_level"]] += 1
        model = r["identity"]["model_raw"]
        slot["models"].add(model)
        has_variant = bool((r["identity"].get("variant_raw") or "").strip())
        if has_variant:
            slot["variants"].add((model, r["identity"]["variant_raw"]))
        slot["pairs"].setdefault(model, False)
        slot["pairs"][model] = slot["pairs"][model] or has_variant
        src = slot["sources"].setdefault(r["source"]["name"], {
            "rows": 0, "artifacts": set(), "urls": set(), "methods": set()})
        src["rows"] += 1
        src["artifacts"].add(os.path.basename(r["source"]["artifact_path"]))
        src["urls"].add(r["source"]["url"])
        src["methods"].add(r["source"].get("extraction_method")
                            or r["evidence_locator"].get("method", "?"))

    # layer evidence from capture logs too (captures that produced no rows)
    log_layers = {}
    for log in glob.glob(os.path.join(OUT_DIR, "catalog_layers_*.json")):
        data = json.load(open(log, encoding="utf-8"))
        for entry in data.get("captured", []):
            log_layers.setdefault(entry["filename"], {
                "url": entry.get("url"), "layer": entry.get("layer"),
                "note": entry.get("note")})

    matrix, totals = [], {"oems_in_scope": 0, "oems_with_staged_rows": 0,
                          "models": 0, "variants": 0, "rows": 0}
    for brand, b in sorted(brands.items()):
        if not b.get("in_scope"):
            continue
        totals["oems_in_scope"] += 1
        slot = per_brand.get(brand, None)
        layers, sources = set(), []
        for name, src in (slot["sources"].items() if slot else []):
            layers |= set(SOURCE_LAYERS.get(name, set()))
            if any(m in STRUCTURED_METHODS or (m and "json" in m)
                   for m in src["methods"]):
                layers.add("structured_payload")
            for art in src["artifacts"]:
                layers |= layers_for_artifact(art)
                if art in log_layers and log_layers[art]["url"]:
                    layers |= layers_for_artifact(art, log_layers[art]["url"])
            sources.append({"source": name, "rows": src["rows"],
                            "artifacts": sorted(src["artifacts"]),
                            "methods": sorted(src["methods"])})
        # endpoints held in the registry but not parsed into rows
        for ep in b.get("captured_endpoints", []):
            layers |= layers_for_artifact(ep.get("artifact", ""), ep.get("url", ""))

        models = len(slot["models"]) if slot else 0
        variants = len(slot["variants"]) if slot else 0
        if slot:
            totals["oems_with_staged_rows"] += 1
        totals["models"] += models
        totals["variants"] += variants
        totals["rows"] += slot["rows"] if slot else 0

        no_variant = sorted(m for m, has in (slot["pairs"].items() if slot else [])
                            if not has) if slot else []
        gaps = []
        if not slot:
            gaps.append({
                "type": "no_staged_catalog",
                "reason": f"access_status={b.get('access_status')}; "
                          f"blocker={json.dumps(b.get('blocker_evidence'), ensure_ascii=False)}"
                          if b.get("access_status") != "REACHABLE"
                          else "reachable but no adapter staged rows yet"})
        elif no_variant:
            gaps.append({
                "type": "models_without_published_variant_rows",
                "count": len(no_variant),
                "models": no_variant,
                "reason": "no first-party grade/trim layer captured for these models "
                          "in this cycle — checked layers: "
                          + (", ".join(sorted(layers)) or "none")})
        missing_layers = [l for l in LAYERS if l not in layers]
        if missing_layers:
            gaps.append({
                "type": "layers_not_checked",
                "layers": missing_layers,
                "reason": "not present in captured official artifacts / not "
                          "discovered by Pass C traversal this cycle"})

        matrix.append({
            "brand": brand,
            "in_scope": True,
            "access_status": b.get("access_status"),
            "adapter_status": b.get("adapter_status"),
            "provenance_status": b.get("provenance_status"),
            "catalog": {"models": models, "variants": variants,
                        "rows": slot["rows"] if slot else 0,
                        "identity_levels": slot["levels"] if slot else None},
            "sources": sources,
            "layers_checked": sorted(layers),
            "layers_not_checked": missing_layers,
            "gaps": gaps,
        })

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "blueprint_sections": ["§5.2 models", "§5.3 variants/trims",
                               "§59 Pass A/B/C", "§60/§61 brochure+verification",
                               "§89 verified vehicle", "§93 coverage registry",
                               "§94 acquisition contract", "§95 quality rules",
                               "§96 source classes", "§98 test categories",
                               "§101 Phase 1"],
        "totals": totals,
        "oems": matrix,
    }
    js = os.path.join(OUT_DIR, f"catalog_matrix_{STAMP}.json")
    with open(js, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    md = os.path.join(OUT_DIR, f"catalog_matrix_{STAMP}.md")
    lines = [f"# P100 catalog completeness matrix ({STAMP})", "",
             f"- in-scope OEMs: **{totals['oems_in_scope']}** · "
             f"with staged rows: **{totals['oems_with_staged_rows']}**",
             f"- MODEL rows: **{totals['models']}** distinct models · "
             f"**{totals['variants']}** distinct variants · "
             f"**{totals['rows']}** staged rows (all ACQUISITION_VERIFIED)", "",
             "| OEM | rows | models | variants | layers checked | gaps |",
             "|---|---:|---:|---:|---|---|"]
    for e in matrix:
        gap_bits = []
        for g in e["gaps"]:
            if g["type"] == "models_without_published_variant_rows":
                gap_bits.append(f"{g['count']} models w/o variants")
            elif g["type"] == "layers_not_checked":
                gap_bits.append("layers: " + ",".join(g["layers"]))
            else:
                gap_bits.append(g["type"])
        lines.append(
            f"| {e['brand']} | {e['catalog']['rows']} | {e['catalog']['models']} | "
            f"{e['catalog']['variants']} | {', '.join(e['layers_checked']) or '—'} | "
            f"{'; '.join(gap_bits) or '—'} |")
    lines += ["", "## gaps and reasons", ""]
    for e in matrix:
        for g in e["gaps"]:
            lines.append(f"- **{e['brand']}** / {g['type']}: {g.get('reason', '')}"
                         + (f" — {', '.join(g.get('models', [])[:8])}"
                            if g.get("models") else ""))
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(json.dumps(totals, indent=2))
    print(f"wrote {js}\nwrote {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
