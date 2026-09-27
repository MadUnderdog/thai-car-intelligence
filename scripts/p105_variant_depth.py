#!/usr/bin/env python3
"""P105 — first-party VARIANT / grade depth pass.

Rules (all structural, model-bound, provenance-verified):

  A  official_name_price_row     the official page publishes the composite
                                 identity on a name line immediately followed
                                 by a published price line
  B  official_grade_list_row     the same composite identity appears in a
                                 page that lists ≥2 distinct grades of that
                                 same model (a grade list), so the row is a
                                 grade row and not prose

Both rules require the published line to *start with the record's model label*
(brand prefix optional), so a variant can never be attributed to another model,
to a sibling brand or to another generation.  Text that only exists inside
navigation / footer / meta / style regions is rejected and recorded.
No price is read, stored or verified: this is an identity pass.
"""
from __future__ import annotations

import collections
import datetime
import glob
import html
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "lib"))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from thai_factory.catalog.identity_pass import (  # noqa: E402
    IdentityReconciliation, ReconciledIdentity, match_key)
import p104_first_party_breadth as p104  # noqa: E402
import p103_first_party_catalog as p103  # noqa: E402
from p104_first_party_breadth import (  # noqa: E402
    BoundMatcher, artifact_path, artifact_sha, artifact_text, flattened,
    looks_like_grade, verify_artifact, PRICE_LINE, GENERIC_LABELS)

OUT_DIR = os.path.join(REPO, "audit", "coverage")
PLAN = os.path.join(OUT_DIR, "p105_target_plan.json")
PRICE_ROW = re.compile(r"(?:฿\s?[\d,]|THB|บาท|^\s*(?:ราคา|เริ่มต้น))")

# filename prefix → manufacturer (only artifacts with a verified sidecar are used)
PREFIX_MAP = [("landrover", "Land Rover"), ("mercedes", "Mercedes-Benz"), ("mini", "MINI"),
              ("bmw", "BMW"), ("toyota", "Toyota"), ("mazda", "Mazda"), ("lexus", "Lexus"),
              ("porsche", "Porsche"), ("subaru", "Subaru"), ("suzuki", "Suzuki"),
              ("changan", "Changan"), ("jaguar", "Jaguar"), ("isuzu", "Isuzu"),
              ("deepal", "Deepal"), ("nissan", "Nissan"), ("honda", "Honda"),
              ("mitsubishi", "Mitsubishi"), ("gwm", "GWM"), ("kia", "Kia"), ("mg", "MG"),
              ("smart", "Smart"), ("byd", "BYD"), ("ford", "Ford"), ("chevrolet", "Chevrolet"),
              ("audi", "Audi"), ("volvo", "Volvo"), ("peugeot", "Peugeot")]
NAMED_MAP = {"MINI_": "MINI", "GWM_": "GWM", "Suzuki_": "Suzuki", "Changan_": "Changan",
             "TH_Jaguar": "Jaguar", "TH_LandRover": "Land Rover"}


def brand_of(fname: str):
    for prefix, brand in NAMED_MAP.items():
        if fname.startswith(prefix):
            return brand
    low = fname.lower()
    for prefix, brand in PREFIX_MAP:
        if low.startswith(prefix):
            return brand
    return None


def norm(text: str) -> str:
    return re.sub(r"[^0-9a-zก-๙]+", "", (text or "").casefold())


def artifact_files() -> dict:
    """brand → [artifacts] for every committed artifact that verifies."""
    out = collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(REPO, "tests", "fixtures", "oem-artifacts",
                                               "*.prov.json"))):
        fname = os.path.basename(path)[:-len(".prov.json")]
        brand = brand_of(fname)
        full = artifact_path(fname)
        if not brand or not os.path.exists(full):
            continue
        prov, _reason = verify_artifact(full)
        if prov is None:
            continue
        out[brand].append(fname)
    return out


def url_model(brand: str, fname: str, wanted: dict):
    """Model the official URL slug names — page-level model binding."""
    sidecar = artifact_path(fname) + ".prov.json"
    if not os.path.exists(sidecar):
        return None
    try:
        url = json.load(open(sidecar, encoding="utf-8")).get("source_url", "")
    except Exception:
        return None
    segs = [s for s in url.split("?")[0].split("/") if s]
    if not segs:
        return None
    tail = re.sub(r"\.(html?|pdf)$", "", segs[-1], flags=re.I)
    from thai_factory.catalog.identity_pass import match_key
    for model in wanted:
        if match_key(brand, model) == match_key(brand, tail):
            return model
    return None


def body_text(fname: str) -> str:
    """Page text with navigation/footer/meta/style regions removed."""
    src = artifact_text(fname)
    for noise in p104.NOISE_REGIONS:
        src = noise.sub(" ", src)
    src = re.sub(r"<script\b.*?</script>", " ", src, flags=re.S | re.I)
    src = re.sub(r"<style\b.*?</style>", " ", src, flags=re.S | re.I)
    src = re.sub(r"<meta\b[^>]*>", " ", src, flags=re.I)
    src = re.sub(r"<[^>]+>", " ", src)
    return re.sub(r"\s+", " ", html.unescape(src))


def model_bases(brand: str, models) -> list:
    """(prefix, model) pairs, longest prefix first, ties broken by name.

    Ordering must be deterministic: set iteration order changes with the
    interpreter's hash seed, and a different tie winner picks a different
    model for the same published line.
    """
    pairs = []
    for model in sorted(models):
        bases = {model}
        if model.startswith(brand + " "):
            bases.add(model[len(brand) + 1:])
        elif " " in model:
            bases.add(model.split(" ", 1)[1])
        for base in bases:
            pairs.append((base, model))
    pairs.sort(key=lambda x: (-len(x[0]), x[1], x[0]))
    return pairs


def extract_variant_rows(rec) -> list:
    universe_models = collections.defaultdict(set)
    variant_labels = collections.defaultdict(set)
    owner = collections.defaultdict(set)      # (brand, variant-norm) → models
    for r in rec.records:
        universe_models[r.manufacturer].add(r.model)
        if r.variant and not r.first_party:
            variant_labels[(r.manufacturer, r.model)].add(r.variant)
            owner[(r.manufacturer, norm(r.variant))].add(r.model)
    out, rejected = [], []
    for brand, files in artifact_files().items():
        if not variant_labels.get((brand,)) and not any(
                k[0] == brand for k in variant_labels):
            continue
        pairs = model_bases(brand, universe_models.get(brand, set()))
        if not pairs:
            continue
        wanted = {m: sorted(vs) for (b, m), vs in variant_labels.items() if b == brand}
        if not wanted:
            continue
        for fname in files:
            prov, reason = verify_artifact(artifact_path(fname))
            if prov is None:
                continue
            lines = flattened(fname)
            body = body_text(fname)
            # grade-list support: distinct suffixes published per (prefix, model)
            suffixes = collections.defaultdict(set)
            for line in lines:
                for base, model in pairs:
                    if line.casefold().startswith(base.casefold() + " ") and \
                            len(line) > len(base) + 1:
                        suffixes[(base, model)].add(line[len(base):].strip())
                        break
            multi = {k for k, v in suffixes.items() if len(v) >= 2}
            seen_rows = set()
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                for base, model in pairs:
                    if not line.casefold().startswith(base.casefold() + " "):
                        continue
                    tail = line[len(base):].strip()
                    if norm(tail) not in {norm(v) for v in wanted.get(model, set())}:
                        continue                     # composite must match a candidate
                    published = [v for v in wanted.get(model, set())
                                 if norm(v) == norm(tail)][0]
                    price_adj = bool(PRICE_ROW.search(nxt))
                    in_grade_list = (base, model) in multi
                    if not (price_adj or in_grade_list):
                        break
                    if norm(published) in {norm(x) for x in GENERIC_LABELS}:
                        rejected.append({"model": model, "variant": published,
                                         "artifact": fname, "line": i + 1,
                                         "reason": "generic label — never a variant"})
                        break
                    if norm(line) not in norm(body):
                        rejected.append({"model": model, "variant": published,
                                         "artifact": fname, "line": i + 1,
                                         "text": line[:120],
                                         "reason": "occurs only in navigation / footer / "
                                                   "meta / style regions — not variant evidence"})
                        break
                    if (model, published, fname, i) in seen_rows:
                        break
                    seen_rows.add((model, published, fname, i))
                    out.append({
                        "manufacturer": brand, "model": model, "variant": published,
                        "identity_level": "VARIANT",
                        "published_label": f"{model} {published}",
                        "artifact": fname, "sha256": artifact_sha(fname),
                        "source_url": prov.get("source_url", ""),
                        "source_generation_context": "",
                        "extraction_method": ("official_name_price_row" if price_adj
                                              else "official_grade_list_row"),
                        "evidence": {
                            "composite_line": line[:160], "line": i + 1,
                            "model_prefix": base,
                            "structure": ("name row immediately followed by a published "
                                          "price line" if price_adj else
                                          f"grade list of {model} "
                                          f"({len(suffixes[(base, model)])} grades on this page)"),
                            "selector": "official page body (navigation/footer/meta/style "
                                        "regions removed)",
                        },
                        "reconciliation_note": "",
                    })
                    break
            # rule C — the official URL names the model, and the page lists ≥2
            # distinct candidate grades of that model (a grade list on its own page)
            page_model = url_model(brand, fname, wanted)
            if page_model:
                wanted_here = sorted(wanted.get(page_model, set()))
                hits = [(i, l) for i, l in enumerate(lines)
                        if norm(l) in {norm(v) for v in wanted_here}]
                if len({norm(l) for _, l in hits}) >= 2:
                    for i, line in hits:
                        if norm(line) in {norm(x) for x in GENERIC_LABELS}:
                            rejected.append({"model": page_model, "variant": line,
                                             "artifact": fname, "line": i + 1,
                                             "reason": "generic label — never a variant"})
                            continue
                        if norm(line) not in norm(body):
                            rejected.append({"model": page_model, "variant": line,
                                             "artifact": fname, "line": i + 1,
                                             "text": line[:120],
                                             "reason": "occurs only in navigation / footer / "
                                                       "meta / style regions"})
                            continue
                        cands = sorted(v for v in wanted_here if norm(v) == norm(line))
                        if not cands:
                            continue
                        published = cands[0]
                        if (page_model, published, fname, i) in seen_rows:
                            continue
                        seen_rows.add((page_model, published, fname, i))
                        prov2, _r = verify_artifact(artifact_path(fname))
                        out.append({
                            "manufacturer": brand, "model": page_model,
                            "variant": published, "identity_level": "VARIANT",
                            "published_label": f"{page_model} {published}",
                            "artifact": fname, "sha256": artifact_sha(fname),
                            "source_url": prov2.get("source_url", ""),
                            "source_generation_context": "",
                            "extraction_method": "official_page_bound_grade_list",
                            "evidence": {
                                "composite_line": line[:160], "line": i + 1,
                                "model_prefix": page_model,
                                "structure": (f"page URL names {page_model} and lists "
                                              f"{len({norm(l) for _, l in hits})} distinct "
                                              f"grades of it"),
                                "selector": "official model page body (navigation/footer/"
                                            "meta/style regions removed)",
                            },
                            "reconciliation_note": "",
                        })
            # rule D — the page lists grades as bare rows (Mitsubishi / Isuzu /
            # Mazda / Nissan price tables): accept only labels owned by exactly one
            # model, when that model has ≥2 of its labels on this page
            hits = collections.defaultdict(dict)
            for i, line in enumerate(lines):
                key = (brand, norm(line))
                if not line.strip() or len(line) > 70 or key not in owner:
                    continue
                if len(owner[key]) != 1:
                    continue                    # label could belong to two models
                model = next(iter(owner[key]))
                if model not in wanted:
                    continue
                published = [v for v in wanted[model] if norm(v) == norm(line)][0]
                hits[model][norm(published)] = (i, line, published)
            for model, labels in hits.items():
                if len(labels) < 2:
                    continue                    # not a grade list of this model
                for _k, (i, line, published) in labels.items():
                    if norm(line) in {norm(x) for x in GENERIC_LABELS}:
                        rejected.append({"model": model, "variant": published,
                                         "artifact": fname, "line": i + 1,
                                         "reason": "generic label — never a variant"})
                        continue
                    if norm(line) not in norm(body):
                        rejected.append({"model": model, "variant": published,
                                         "artifact": fname, "line": i + 1,
                                         "text": line[:120],
                                         "reason": "occurs only in navigation / footer / "
                                                   "meta / style regions"})
                        continue
                    nxt = lines[i + 1] if i + 1 < len(lines) else ""
                    if (model, published, fname, i) in seen_rows:
                        continue
                    seen_rows.add((model, published, fname, i))
                    prov3, _r = verify_artifact(artifact_path(fname))
                    out.append({
                        "manufacturer": brand, "model": model, "variant": published,
                        "identity_level": "VARIANT",
                        "published_label": f"{model} {published}",
                        "artifact": fname, "sha256": artifact_sha(fname),
                        "source_url": prov3.get("source_url", ""),
                        "source_generation_context": "",
                        "extraction_method": ("official_grade_table_row" if
                                              PRICE_ROW.search(nxt)
                                              else "official_grade_list_bare_row"),
                        "evidence": {
                            "composite_line": line[:160], "line": i + 1,
                            "model_prefix": model,
                            "structure": (f"bare grade row of {model}; the page lists "
                                          f"{len(labels)} grades that only {model} owns"
                                          + (" and the next line is a published price"
                                             if PRICE_ROW.search(nxt) else "")),
                            "selector": "official page body (navigation/footer/meta/style "
                                        "regions removed)",
                        },
                        "reconciliation_note": "",
                    })
    return out, rejected


def load_baseline():
    """Rehydrate the accepted P104 universe."""
    path = os.path.join(OUT_DIR, "identity_universe_p104.json")
    uni = json.load(open(path, encoding="utf-8"))["universe"]
    rec = IdentityReconciliation(target_date=uni.get("target_date", "p105"))
    for r in uni["records"]:
        obj = ReconciledIdentity(manufacturer=r["manufacturer"], model=r["model"],
                                 variant=r.get("variant") or "",
                                 generation=r.get("generation") or "")
        obj.sources = [dict(x) for x in r.get("sources", [])]
        obj.first_party = [dict(x) for x in r.get("first_party", [])]
        obj.rejection_reasons = list(r.get("rejection_reasons", []))
        obj.notes = list(r.get("notes", []))
        obj.status = r["status"]
        obj.match_method = r.get("match_method", "")
        obj.published_price_thb = r.get("published_price_thb")
        obj.published_price_role = r.get("published_price_role") or ""
        obj.scope = r.get("scope", "TH")
        rec.records.append(obj)
    rec.rejected = [dict(x) for x in uni.get("rejected", [])]
    rec.sources_used = [dict(x) for x in uni.get("sources_used", [])]
    return rec


def identity_block(records, brand):
    """Same counter the accepted P103/P104 reports use — never a second one."""
    block = p103.identity_block(records, brand)
    cand_v = [r for r in records if r.manufacturer == brand and r.variant]
    block["identity_only_variants"] = len([r for r in cand_v if not r.first_party])
    return block


def main() -> int:
    rec = load_baseline()
    p104_result = json.load(open(os.path.join(OUT_DIR, "p104_final_result.json"),
                                 encoding="utf-8"))
    brands = sorted({r.manufacturer for r in rec.records})
    before = {b: identity_block(rec.records, b) for b in brands}
    assert sum(v["first_party_confirmed_variants"] for v in before.values()) == 404, \
        [v for v in before.values() if v["first_party_confirmed_variants"] != 404][:3]
    assert sum(v["first_party_confirmed_models"] for v in before.values()) == 243

    # ── plan written BEFORE any harvest accounting ──────────────────────────
    matrix = json.load(open(os.path.join(OUT_DIR, "identity_matrix_p104.json"),
                            encoding="utf-8"))
    plan_rows = []
    for entry in matrix["oems"]:
        ident = entry["identity"]
        access = entry.get("official_access_status", "?")
        deficit = ident["variant_candidates_discovered"] - ident["first_party_confirmed_variants"]
        row = {"brand": entry["brand"], "official_access_status": access,
               "candidate_variants": ident["variant_candidates_discovered"],
               "confirmed_variants": ident["first_party_confirmed_variants"],
               "variant_deficit": deficit,
               "targeted_this_wave": bool(access == "REACHABLE" and deficit > 0)}
        if access != "REACHABLE":
            row["blockers"] = entry.get("blockers") or []
            row["blocker_kind"] = access
            row["blocker_policy"] = ("recorded verbatim from the accepted matrix; "
                                     "host is never requested before next_retry_at")
        plan_rows.append(row)
    plan_rows.sort(key=lambda r: -r["variant_deficit"])
    with open(PLAN, "w", encoding="utf-8") as fh:
        json.dump({
            "schema": "p105_target_plan/1",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "baseline_artifact": "audit/coverage/p104_final_result.json",
            "objective": "first-party VARIANT / grade depth",
            "rules": ["VARIANT evidence must be model-bound in the published line",
                      "name row + published price row, or a grade list of that model",
                      "no price verification — a price line only proves a row boundary",
                      "navigation / footer / meta / style text is never evidence",
                      "no model promotion, no sibling brand, no cross-generation fallback",
                      "provenance verified before any evidence is used"],
            "priority_order": [r["brand"] for r in plan_rows
                               if r["targeted_this_wave"]][:12],
            "oems": plan_rows,
            "totals": {"rows": len(plan_rows),
                       "targeted": sum(1 for r in plan_rows if r["targeted_this_wave"]),
                       "blocked": sum(1 for r in plan_rows if r["official_access_status"]
                                      != "REACHABLE"),
                       "variant_deficit": sum(r["variant_deficit"] for r in plan_rows)},
        }, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # ── harvest ─────────────────────────────────────────────────────────────
    rows, rejected_rows = extract_variant_rows(rec)
    matcher = BoundMatcher(rec.records)
    results = []
    for item in rows:
        kind, target, method, reason = matcher.resolve(
            item["manufacturer"], item["model"], item["variant"],
            context=item.get("source_generation_context", ""))
        entry = dict(item)
        entry["reconciliation"] = {"outcome": kind, "match_method": method, "reason": reason}
        if kind == "ambiguous":
            results.append(entry)
            continue
        if kind == "existing":
            entry["reconciliation"]["matched_record"] = {"model": target.model,
                                                         "variant": target.variant}
            entry["reconciliation"]["prior_status"] = target.status
        source = {
            "source_name": f"{item['manufacturer']} Thailand Official",
            "manufacturer": item["manufacturer"],
            "source_role": "MARKET_TRUTH",
            "source_url": item["source_url"],
            "label": item["published_label"],
            "artifact": os.path.join("tests/fixtures/oem-artifacts", item["artifact"]),
            "artifact_sha256": item["sha256"],
            "extraction_method": item["extraction_method"],
            "identity_level": "VARIANT",
            "market_scope": "TH",
            "evidence": item.get("evidence", {}),
        }
        rec.add_first_party(item["manufacturer"], item["model"], item["variant"], source)
        results.append(entry)
    rec.resolve_statuses()

    after = {b: identity_block(rec.records, b) for b in brands}
    outcomes = collections.Counter(e["reconciliation"]["outcome"] for e in results)
    generated = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with open(os.path.join(OUT_DIR, "p105_variant_evidence.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"artifact": "p105-variant-evidence/1", "generated_at": generated,
                   "plan": os.path.basename(PLAN),
                   "rules": ["model-bound composite label",
                             "name|price row or grade list",
                             "provenance verified before use"],
                   "evidence": results}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    with open(os.path.join(OUT_DIR, "catalog_reconciliation_p105.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"artifact": "p105-catalog-reconciliation/1", "generated_at": generated,
                   "before": {"confirmed_variants":
                              sum(v["first_party_confirmed_variants"] for v in before.values()),
                              "confirmed_models":
                              sum(v["first_party_confirmed_models"] for v in before.values())},
                   "after": {"confirmed_variants":
                             sum(v["first_party_confirmed_variants"] for v in after.values()),
                             "confirmed_models":
                             sum(v["first_party_confirmed_models"] for v in after.values())},
                   "harvested": len(results), "outcomes": dict(outcomes),
                   "by_method": dict(collections.Counter(
                       e["extraction_method"] for e in results)),
                   "per_oem_before_after": {
                       b: {"confirmed_variants": [before[b]["first_party_confirmed_variants"],
                                                  after[b]["first_party_confirmed_variants"]],
                           "identity_only_variants": [before[b]["identity_only_variants"],
                                                      after[b]["identity_only_variants"]]}
                       for b in brands if before[b]["variant_candidates_discovered"]},
                   "new_identities": [
                       {"manufacturer": e["manufacturer"], "model": e["model"],
                        "variant": e["variant"], "artifact": e["artifact"],
                        "reason": e["reconciliation"]["reason"]}
                       for e in results if e["reconciliation"]["outcome"] == "new"],
                   "ambiguous": [
                       {"manufacturer": e["manufacturer"], "model": e["model"],
                        "variant": e["variant"], "reason": e["reconciliation"]["reason"]}
                       for e in results if e["reconciliation"]["outcome"] == "ambiguous"],
                   "rejected_rows": rejected_rows,
                   "staging_written": False, "price_pass": False},
                  fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    uni = {"schema": "p105-identity-universe/1", "generated_at": generated,
           "baseline_artifact": "audit/coverage/identity_universe_p104.json",
           "p105_harvested_rows": len(results),
           "acceptance_boundary": "Phase-1 audit evidence only",
           "universe": rec.to_json()}
    with open(os.path.join(OUT_DIR, "identity_universe_p105.json"), "w",
              encoding="utf-8") as fh:
        json.dump(uni, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # ── matrix ──────────────────────────────────────────────────────────────
    oem_rows = []
    for entry in matrix["oems"]:
        b = entry["brand"]
        ident = dict(entry["identity"])
        ident.update(after.get(b, {}))
        oem_rows.append({"brand": b, "official_access_status": entry.get("official_access_status"),
                         "blockers": entry.get("blockers") or [],
                         "identity": ident,
                         "p105_delta": {
                             "confirmed_variants": (after.get(b, {}).get(
                                 "first_party_confirmed_variants", 0) -
                             before.get(b, {}).get("first_party_confirmed_variants", 0)),
                             "rows": sum(1 for e in results if e["manufacturer"] == b)}})
    with open(os.path.join(OUT_DIR, "identity_matrix_p105.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"schema": "p105-identity-matrix/1", "generated_at": generated,
                   "baseline_artifact": "audit/coverage/identity_matrix_p104.json",
                   "oems": oem_rows}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    lines = ["# P105 identity matrix — VARIANT depth", "",
             f"Generated {generated} · baseline `identity_matrix_p104.json`", "",
             "| OEM | access | candidate V | confirmed V (before) | confirmed V (after) | delta | P105 rows |",
             "|---|---|---|---|---|---|---|"]
    for row in oem_rows:
        i = row["identity"]
        b = row["brand"]
        lines.append(f"| {b} | {row['official_access_status']} | "
                     f"{i['variant_candidates_discovered']} | "
                     f"{before.get(b, {}).get('first_party_confirmed_variants', 0)} | "
                     f"{i['first_party_confirmed_variants']} | "
                     f"{row['p105_delta']['confirmed_variants']:+d} | "
                     f"{row['p105_delta']['rows']} |")
    with open(os.path.join(OUT_DIR, "identity_matrix_p105.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    total_before_v = sum(v["first_party_confirmed_variants"] for v in before.values())
    total_after_v = sum(v["first_party_confirmed_variants"] for v in after.values())
    total_before_m = sum(v["first_party_confirmed_models"] for v in before.values())
    total_after_m = sum(v["first_party_confirmed_models"] for v in after.values())
    identity_only_before = len([r for r in rec.records if r.status == "IDENTITY_ONLY"])
    io_rows = [r for r in rec.records if r.status == "IDENTITY_ONLY"]
    result = {
        "schema": "p105-final-result/1", "generated_at": generated,
        "before_after": {
            "first_party_confirmed_variants": [total_before_v, total_after_v],
            "first_party_confirmed_models": [total_before_m, total_after_m],
            "oems_with_variant_confirmation": [
                sum(1 for v in before.values() if v["first_party_confirmed_variants"] > 0),
                sum(1 for v in after.values() if v["first_party_confirmed_variants"] > 0)],
            "universe_records": [len(rec.records), len(rec.records)]},
        "harvested_rows": len(results), "outcomes": dict(outcomes),
        "by_method": dict(collections.Counter(e["extraction_method"] for e in results)),
        "identity_only": {"records": len(io_rows),
                          "models": len([r for r in io_rows if not r.variant]),
                          "variants": len([r for r in io_rows if r.variant])},
        "conflicts": {"records": len([r for r in rec.records if r.status == "CONFLICT"])},
        "rejected": {"records": len(rec.rejected)},
        "per_oem_delta": {r["brand"]: r["p105_delta"] for r in oem_rows
                          if r["p105_delta"]["rows"] or r["p105_delta"]["confirmed_variants"]},
        "blocked_oems": [r["brand"] for r in plan_rows if r["official_access_status"]
                         != "REACHABLE"],
        "gates": {"staging_written": False, "price_pass": False, "prisma_touched": False,
                  "p104_p103_p102_logic_changed": False,
                  "production_db_unchanged": True},
        "p104_baseline_result": {"first_party_confirmed_variants":
                                 p104_result["before_after"]["first_party_confirmed_variants"]},
    }
    with open(os.path.join(OUT_DIR, "p105_final_result.json"), "w",
              encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(json.dumps({"harvested": len(results), "outcomes": dict(outcomes),
                      "by_method": result["by_method"],
                      "variants": [total_before_v, total_after_v],
                      "models": [total_before_m, total_after_m],
                      "identity_only_variants": [len([r for r in rec.records
                                                     if r.status == "IDENTITY_ONLY"
                                                     and r.variant]),
                                                 result["identity_only"]["variants"]],
                      "conflicts": result["conflicts"],
                      "rejected_rows": len(rejected_rows),
                      "per_oem": result["per_oem_delta"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
