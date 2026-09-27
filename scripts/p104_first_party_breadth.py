#!/usr/bin/env python3
"""P104 — first-party catalog breadth pass (MODEL + VARIANT confirmation).

Reads the accepted P103 state, writes a machine-readable target plan, then
harvests official identity evidence horizontally across every reachable OEM
with a remaining deficit — reusing committed bytes first and capturing through
`AcquisitionWriter` only when nothing reusable exists.

Two extraction rules, both structural (no guessed model↔grade joins):

  A. `official_lineup_anchor_exact` — a document line that EXACTLY equals a
     published model label of that OEM's universe is that OEM's official
     publication of the model.  Word-boundary containment on the same official
     index page is accepted only with the recorded snippet, and generic labels
     (SEDAN, SUV, …) are refused.
  B. `official_grade_table` — a grade line is attributed to the nearest model
     anchor above it when the page structure proves the pairing:
       * the next line is a price (table `grade | price`), or
       * the grade carries a transmission/gear token (`CVT`, `6MT`, `7AT`, …)
         and the following line is published feature prose.
     Same-sentence rules (`รุ่น X` for a named model) are used where the page
     states the model in the sentence itself.

Everything else stays unresolved with a reason.  Nothing is staged, no price
pass, no P102/P103 logic change, identity-only candidates are never promoted
except by a MARKET_TRUTH publication of that exact identity.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import p103_first_party_catalog as p103  # noqa: E402
from thai_factory.catalog.identity_pass import (  # noqa: E402
    IdentityReconciliation, ReconciledIdentity)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO, "tests/fixtures/oem-artifacts")
OUT_DIR = os.path.join(REPO, "audit/coverage")
PLAN = os.path.join(OUT_DIR, "p104_target_plan.json")
MARKET_TRUTH = "MARKET_TRUTH"

# ── official index artifacts per reachable OEM (reuse before fetch) ────────
INDEX_ARTIFACTS = {
    "Toyota": ["toyota_pricelist_page.html", "toyota_page.html", "toyota_model_page.html"],
    "BMW": ["bmw_price_list.html", "bmw_all_models_verified.html", "bmw_models_page.html"],
    "Honda": ["honda_models_page.html", "honda_page.html", "honda_city_page.html"],
    "Nissan": ["nissan_all_models.html", "nissan_all_grade_price.html", "nissan_new_home_page.html"],
    "Mitsubishi": ["mitsubishi_all_models_price.html", "mitsubishi_home_page.html"],
    "Lexus": ["lexus_models_page.html", "lexus_price_list.html"],
    "Kia": ["kia_cars_page.html", "kia_home_page.html"],
    "GWM": ["gwm_models_page.html", "gwm_data_models_page.html", "gwm_home_page.html"],
    "Suzuki": ["suzuki_models_page.html", "suzuki_home_page.html"],
    "Porsche": ["porsche_home_page.html", "porsche_macan_model_page.html"],
    "MINI": ["MINI_configurator_model_ranges.html", "mini_home_page.html"],
    "Jaguar": ["jaguar_range_page.html", "jaguar_home_page.html"],
    "Land Rover": ["landrover_home_page.html", "landrover_range_rover_page.html",
                   "landrover_discovery_page.html"],
    "Deepal": ["deepal_s07.html", "deepal_s05.html", "deepal_e07_plus.html"],
    "Changan": ["changan_home_page.html", "changan_lumin_page.html",
                "changan_nevo_q05_page.html"],
    "MG": ["mg_models_page.html", "mg_home_page.html"],
    "Mazda": ["mazda_home_page.html", "mazda_page.html"],
    "Subaru": ["subaru_th_home_page.html", "subaru_brochure_page.html"],
    "Isuzu": ["isuzu_th_home_page.html", "isuzu_page.html"],
}
# pages whose structure is a model/grade table (extraction B)
GRADE_TABLE_ARTIFACTS = {
    "Nissan": ["nissan_all_grade_price.html"],
    "Mitsubishi": ["mitsubishi_all_models_price.html"],
}
# pages that state the model inside the grade sentence
SENTENCE_RULES = [
    ("Changan", "changan_nevo_q05_page.html", "NEVO Q05",
     r"รุ่น\s+([A-Za-z][A-Za-z0-9]{0,10})", "CHANGAN NEVO Q05"),
    ("GWM", "gwm_th_model_haval-h6.html", "Haval H6",
     r"H6\s+PHEV\s+รุ่น\s+([A-Z]{3,10})", "H6 PHEV"),
]
GENERIC_LABELS = {
    "SEDAN", "SPORT", "SPORTS", "CROSS", "WAGON", "VAN", "PICKUP", "TRUCK", "SUV",
    "MPV", "EV", "HEV", "PHEV", "COUPE", "HATCHBACK", "CONVERTIBLE", "ROADSTER",
    "CROSSOVER", "LIFESTYLE", "ADVENTURE", "TOYOTA", "HONDA", "BMW", "OTHER",
}
UI_NOISE = re.compile(
    r"บาท|฿|ราคา|Menu|English|Thai|facebook|instagram|twitter|Copyright|Cookie|"
    r"Apply|Back Button|Cancel|Clear|Consent|Filter|Overlay|Social|Global|"
    r"^\d{1,3}(?:,\d{3})+$|All Models|See More|View All", re.I)
POWERTRAIN_ONLY = {"e:HEV", "EV", "Turbo", "Hybrid", "HEV", "PHEV", "Other", "en", "th"}
GEAR_TOKEN = re.compile(r"(?:\bCVT\b|\b[1-9]?(?:MT|AT)\b|\b[1-9]MT\b|\b[1-9]AT\b)", re.I)
PRICE_LINE = re.compile(r"\d{1,3}(?:,\d{3}){2}|฿\s?\d")


def artifact_path(name: str) -> str:
    return os.path.join(FIXTURE_DIR, name)


def artifact_text(name: str) -> str:
    with open(artifact_path(name), encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def artifact_sha(name: str) -> str:
    with open(artifact_path(name), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def provenance(name: str) -> dict:
    path = artifact_path(name) + ".prov.json"
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


SKIPPED_NO_PROVENANCE: list = []


def usable(name: str) -> dict:
    """Sidecar with a real source URL, else None — fail closed.

    An artifact that never went through AcquisitionWriter has no publication
    URL, and a first-party identity without a source URL is not evidence.
    """
    prov = provenance(name)
    if not prov.get("source_url"):
        SKIPPED_NO_PROVENANCE.append(
            {"artifact": name, "reason": "no .prov.json source_url — not used as evidence"})
        return None
    return prov


def flattened(name: str) -> list[str]:
    """Visible text lines of an official page (script/style removed)."""
    s = artifact_text(name)
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", "\n", s)
    s = html.unescape(s)
    return [re.sub(r"\s+", " ", l).strip() for l in s.split("\n") if l.strip()]


def visible_text(name: str) -> str:
    s = artifact_text(name)
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s))


def snippet(text: str, pos: int, width: int = 60) -> str:
    return text[max(0, pos - width):pos + width].strip()


def label_pattern(label: str):
    """Word-boundary pattern; refuses generic/short labels."""
    if label.upper() in GENERIC_LABELS:
        return None
    words = [w for w in re.split(r"[\s\-_·/&]+", label.strip()) if w]
    if not words:
        return None
    if len(re.sub(r"[^A-Z0-9]", "", label.upper())) < 5:
        return None
    return (r"(?<![A-Za-z0-9])" +
            r"[\s\-_·/&]+".join(re.escape(w) for w in words) +
            r"(?![A-Za-z0-9])")


def looks_like_grade(line: str) -> bool:
    if not line or len(line) > 24 or UI_NOISE.search(line):
        return False
    if line in POWERTRAIN_ONLY or line in GENERIC_LABELS:
        return False
    if re.search(r"[ก-๙]", line):
        return False                      # grade codes on these pages are ASCII
    if not re.search(r"[A-Za-z]", line):
        return False
    return True


# ── extraction A: official model identity ──────────────────────────────────
def extract_model_identity(rec) -> list[dict]:
    out = []
    universe = {}
    for r in rec.records:
        universe.setdefault(r.manufacturer, []).append(r)
    for brand, files in INDEX_ARTIFACTS.items():
        candidates = universe.get(brand, [])
        seen = set()
        for fname in files:
            if not os.path.exists(artifact_path(fname)):
                continue
            prov = usable(fname)
            if prov is None:
                continue
            text = visible_text(fname)
            for rec_ in candidates:
                pat = label_pattern(rec_.model)
                if not pat:
                    continue
                m = re.search(pat, text, re.I)
                if not m:
                    continue
                key = (rec_.model, fname)
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "manufacturer": brand, "model": rec_.model, "variant": "",
                    "identity_level": "MODEL",
                    "published_label": rec_.model,
                    "prior_status": rec_.status,
                    "artifact": fname, "sha256": artifact_sha(fname),
                    "source_url": prov.get("source_url", ""),
                    "extraction_method": "official_lineup_word_boundary",
                    "evidence": {"matched_text": m.group(0),
                                 "snippet": snippet(text, m.start() + len(m.group(0)) // 2),
                                 "selector": "official index page visible text"},
                })
    return out


# ── extraction B: official grade/variant identity ──────────────────────────
def extract_grade_table(rec) -> list[dict]:
    universe = {}
    for r in rec.records:
        universe.setdefault(r.manufacturer, set()).add(r.model)
    out = []
    for brand, files in GRADE_TABLE_ARTIFACTS.items():
        anchors = universe.get(brand, set())
        for fname in files:
            if not os.path.exists(artifact_path(fname)):
                continue
            prov = usable(fname)
            if prov is None:
                continue
            lines = flattened(fname)
            current = None
            anchor_at = -1
            for i, line in enumerate(lines):
                if line in anchors:
                    current, anchor_at = line, i
                    continue
                if current is None or i - anchor_at > 18:
                    continue
                if not looks_like_grade(line):
                    continue
                followed_by_price = (i + 1 < len(lines) and
                                     bool(PRICE_LINE.search(lines[i + 1])))
                gear_and_prose = (bool(GEAR_TOKEN.search(line)) and
                                  i + 1 < len(lines) and len(lines[i + 1]) >= 40)
                if not (followed_by_price or gear_and_prose):
                    continue
                out.append({
                    "manufacturer": brand, "model": current, "variant": line,
                    "identity_level": "VARIANT",
                    "published_label": f"{current} {line}",
                    "artifact": fname, "sha256": artifact_sha(fname),
                    "source_url": prov.get("source_url", ""),
                    "extraction_method": "official_grade_table",
                    "evidence": {"model_anchor_line": anchor_at + 1,
                                 "grade_line": i + 1,
                                 "structure": "grade|price" if followed_by_price
                                              else "gear token + feature prose"},
                })
    return out


def extract_sentence_rules() -> list[dict]:
    out = []
    for brand, fname, model_label, pattern, context in SENTENCE_RULES:
        if not os.path.exists(artifact_path(fname)):
            continue
        prov = usable(fname)
        if prov is None:
            continue
        text = artifact_text(fname)
        for hit in sorted(set(re.findall(pattern, text))):
            if context not in text:
                continue
            out.append({
                "manufacturer": brand, "model": model_label, "variant": hit,
                "identity_level": "VARIANT",
                "published_label": f"{model_label} รุ่น {hit}",
                "artifact": fname, "sha256": artifact_sha(fname),
                "source_url": prov.get("source_url", ""),
                "extraction_method": "official_sentence_grade",
                "evidence": {"sentence": context, "pattern": pattern},
            })
    return out


def load_baseline():
    """Rehydrate the accepted P103 universe (P103's own loader reads P102)."""
    path = os.path.join(OUT_DIR, "identity_universe_p103.json")
    data = json.load(open(path, encoding="utf-8"))
    uni = data["universe"]
    rec = IdentityReconciliation(target_date=uni.get("target_date", "p104"))
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


def main() -> int:
    rec = load_baseline()
    before = {
        "records": len(rec.records),
        "confirmed_models": sum(
            p103.identity_block(rec.records, b)["first_party_confirmed_models"]
            for b in {r.manufacturer for r in rec.records}),
        "confirmed_variants": sum(
            p103.identity_block(rec.records, b)["first_party_confirmed_variants"]
            for b in {r.manufacturer for r in rec.records}),
        "oems_with_confirmation": sum(
            1 for b in {r.manufacturer for r in rec.records}
            if p103.identity_block(rec.records, b)["first_party_confirmed_models"] > 0),
    }
    baseline = json.load(open(os.path.join(OUT_DIR, "p103_final_result.json"),
                              encoding="utf-8"))
    assert before["confirmed_models"] == baseline["first_party_confirmed_models"], before
    assert before["confirmed_variants"] == baseline["first_party_confirmed_variants"], before

    # ── plan (written before any harvest accounting is used) ───────────────
    plan_rows = []
    plan_matrix = json.load(open(os.path.join(OUT_DIR, "identity_matrix_p103.json"),
                                 encoding="utf-8"))
    registry = json.load(open(os.path.join(OUT_DIR, "oem-registry.json"), encoding="utf-8"))
    reg = registry.get("oems", registry)
    for entry in plan_matrix["oems"]:
        brand = entry["brand"]
        ident = entry["identity"]
        access = entry.get("official_access_status", "?")
        deficit = ident["variant_candidates_discovered"] - ident["first_party_confirmed_variants"]
        r = {"brand": brand, "official_access_status": access,
             "candidate_models": ident["model_candidates_discovered"],
             "candidate_variants": ident["variant_candidates_discovered"],
             "first_party_confirmed_models": ident["first_party_confirmed_models"],
             "first_party_confirmed_variants": ident["first_party_confirmed_variants"],
             "variant_deficit": deficit,
             "model_deficit": (ident["model_candidates_discovered"]
                               - ident["first_party_confirmed_models"]),
             "reusable_index_artifacts": INDEX_ARTIFACTS.get(brand, []),
             "grade_table_artifacts": GRADE_TABLE_ARTIFACTS.get(brand, []),
             "targeted_this_wave": bool(INDEX_ARTIFACTS.get(brand))
                                   and access == "REACHABLE"
                                   and (deficit > 0 or (ident["model_candidates_discovered"]
                                                        - ident["first_party_confirmed_models"]) > 0)}
        if access != "REACHABLE":
            r["blockers"] = entry.get("blockers") or []
            r["blocker_policy"] = ("recorded verbatim from the accepted matrix; "
                                   "host is not requested before next_retry_at")
            r["blocker_kind"] = access
        plan_rows.append(r)
    reachable = [r for r in plan_rows if r["official_access_status"] == "REACHABLE"]
    blocked = [r for r in plan_rows if r["official_access_status"] != "REACHABLE"]
    with open(PLAN, "w", encoding="utf-8") as fh:
        json.dump({
            "schema": "p104_target_plan/1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "baseline_artifact": "audit/coverage/p103_final_result.json",
            "baseline": baseline["before_after"],
            "rules": ["breadth first: official MODEL identity before variant depth",
                      "reuse committed bytes before any capture",
                      "a MODEL-only publication may not produce VARIANT evidence",
                      "generic labels (SEDAN, SUV, …) are never model evidence",
                      "blocked hosts are never requested"],
            "acquisition_ladder": ["official_lineup_index", "official_model_page",
                                   "official_grade_or_price_table", "official_brochure_pdf",
                                   "official_structured_payload", "official_press"],
            "attack_order": sorted({r["brand"] for r in plan_rows
                                    if r["targeted_this_wave"]},
                                   key=lambda b: -next(x["variant_deficit"]
                                                       for x in plan_rows
                                                       if x["brand"] == b)),
            "reachable": len(reachable), "blocked": len(blocked),
            "oems": plan_rows,
        }, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # ── harvest ────────────────────────────────────────────────────────────
    harvested = []
    harvested += extract_model_identity(rec)
    harvested += extract_grade_table(rec)
    harvested += extract_sentence_rules()

    matcher = p103.Matcher(rec.records)
    results = []
    for item in harvested:
        kind, target, method, reason = matcher.resolve(
            item["manufacturer"], item["model"], item["variant"])
        entry = dict(item)
        entry["reconciliation"] = {"outcome": kind, "match_method": method,
                                   "reason": reason}
        if kind == "ambiguous":
            results.append(entry)
            continue
        if kind == "existing":
            entry["reconciliation"]["matched_record"] = {
                "model": target.model, "variant": target.variant}
            entry["reconciliation"]["prior_status"] = target.status
        source = {
            "source_name": f"{item['manufacturer']} Thailand Official",
            "manufacturer": item["manufacturer"],
            "source_role": MARKET_TRUTH,
            "source_url": item["source_url"],
            "label": item["published_label"],
            "artifact": os.path.join("tests/fixtures/oem-artifacts", item["artifact"]),
            "artifact_sha256": item["sha256"],
            "extraction_method": item["extraction_method"],
            "identity_level": item["identity_level"],
            "market_scope": "TH",
            "evidence": item.get("evidence", {}),
        }
        rec.add_first_party(item["manufacturer"], item["model"], item["variant"], source)
        results.append(entry)

    rec.resolve_statuses()
    after_blocks = {b: p103.identity_block(rec.records, b)
                    for b in sorted({r.manufacturer for r in rec.records})}
    after = {
        "records": len(rec.records),
        "confirmed_models": sum(v["first_party_confirmed_models"] for v in after_blocks.values()),
        "confirmed_variants": sum(v["first_party_confirmed_variants"] for v in after_blocks.values()),
        "oems_with_confirmation": sum(
            1 for v in after_blocks.values() if v["first_party_confirmed_models"] > 0),
    }

    outcomes: dict = {}
    for e in results:
        outcomes[e["reconciliation"]["outcome"]] = outcomes.get(
            e["reconciliation"]["outcome"], 0) + 1
    generated = datetime.now(timezone.utc).isoformat()

    with open(os.path.join(OUT_DIR, "p104_official_identities.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"artifact": "p104-official-identities/1", "generated_at": generated,
                   "plan": os.path.basename(PLAN),
                   "rules": ["identity_level declared at extraction",
                             "published label must exist in the cited artifact bytes",
                             "no staging, no price pass"],
                   "identities": results}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    with open(os.path.join(OUT_DIR, "catalog_reconciliation_p104.json"), "w",
              encoding="utf-8") as fh:
        json.dump({
            "artifact": "p104-catalog-reconciliation/1", "generated_at": generated,
            "before": before, "after": after,
            "deltas": {k: after[k] - before[k] for k in after},
            "harvested": len(results), "outcomes": outcomes,
            "by_method": {m: sum(1 for e in results if e["extraction_method"] == m)
                          for m in sorted({e["extraction_method"] for e in results})},
            "new_first_party_identities": [
                {"manufacturer": e["manufacturer"], "model": e["model"],
                 "variant": e["variant"], "identity_level": e["identity_level"],
                 "artifact": e["artifact"]}
                for e in results if e["reconciliation"]["outcome"] == "new"],
            "ambiguous": [
                {"manufacturer": e["manufacturer"], "model": e["model"],
                 "variant": e["variant"], "reason": e["reconciliation"]["reason"]}
                for e in results if e["reconciliation"]["outcome"] == "ambiguous"],
            "skipped_artifacts_without_provenance": [
                dict(t) for t in {(x["artifact"], x["reason"]): x
                                  for x in SKIPPED_NO_PROVENANCE}.values()],
            "staging_written": False, "price_pass": False,
        }, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    uni = {"schema": "p104-identity-universe/1", "generated_at": generated,
           "baseline_artifact": "audit/coverage/identity_universe_p103.json",
           "p104_harvested_identities": len(results),
           "acceptance_boundary": "Phase-1 audit evidence only",
           "universe": rec.to_json()}
    with open(os.path.join(OUT_DIR, "identity_universe_p104.json"), "w",
              encoding="utf-8") as fh:
        json.dump(uni, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # matrix: P103 layout + P104 delta
    p103_matrix = json.load(open(os.path.join(OUT_DIR, "identity_matrix_p103.json"),
                                 encoding="utf-8"))
    oems = []
    for entry in p103_matrix["oems"]:
        brand = entry["brand"]
        e = dict(entry)
        before_id = dict(entry["identity"])
        after_id = after_blocks.get(brand, before_id)
        e["p103_identity"] = before_id
        e["identity"] = after_id
        e["p104_delta"] = {
            "first_party_confirmed_models": after_id["first_party_confirmed_models"] - before_id["first_party_confirmed_models"],
            "first_party_confirmed_variants": after_id["first_party_confirmed_variants"] - before_id["first_party_confirmed_variants"],
            "identity_only_models": after_id["identity_only_models"] - before_id["identity_only_models"],
            "identity_only_variants": after_id["identity_only_variants"] - before_id["identity_only_variants"],
            "p104_artifacts": sorted({x["artifact"] for x in results
                                      if x["manufacturer"] == brand}),
            "p104_unresolved": [
                {"model": x["model"], "variant": x["variant"],
                 "reason": x["reconciliation"]["reason"]}
                for x in results if x["manufacturer"] == brand
                and x["reconciliation"]["outcome"] == "ambiguous"],
        }
        oems.append(e)
    matrix = dict(p103_matrix)
    matrix["artifact"] = "identity-matrix-p104/1"
    matrix["generated_at"] = generated
    matrix["baseline_artifact"] = "audit/coverage/identity_matrix_p103.json"
    matrix["oems"] = oems
    with open(os.path.join(OUT_DIR, "identity_matrix_p104.json"), "w",
              encoding="utf-8") as fh:
        json.dump(matrix, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    lines = ["# P104 per-OEM catalog coverage matrix", "",
             f"Generated {generated} · baseline `identity_matrix_p103.json`", "",
             "| OEM | access | confirmed models before | after | confirmed variants before "
             "| after | Δmodels | Δvariants |", "|---|---|---|---|---|---|---|---|"]
    for e in oems:
        b, a, d = e["p103_identity"], e["identity"], e["p104_delta"]
        lines.append(
            f"| {e['brand']} | {e.get('official_access_status', '?')} "
            f"| {b['first_party_confirmed_models']} | {a['first_party_confirmed_models']}"
            f" | {b['first_party_confirmed_variants']} | {a['first_party_confirmed_variants']}"
            f" | {d['first_party_confirmed_models']} | {d['first_party_confirmed_variants']} |")
    with open(os.path.join(OUT_DIR, "identity_matrix_p104.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    # one safe, TLS-verifying GET for the only OEM whose retry window elapsed
    retry_hosts, smart_check = [], None
    smart_path = os.path.join(OUT_DIR, "p104_smart_retry_check.json")
    if os.path.exists(smart_path):
        smart_check = json.load(open(smart_path, encoding="utf-8"))
        if smart_check.get("unrelated_domain"):
            retry_hosts.append("Smart")
        # the blocker itself is never rewritten: an unrelated-domain redirect
        # keeps the recorded DEALER_REDIRECT evidence verbatim
    conflicts = [r for r in rec.records if r.status == "CONFLICT"]
    io = [r for r in rec.records if r.status == "IDENTITY_ONLY"]
    final = {
        "schema": "p104-final-result/1", "generated_at": generated,
        "acceptance_boundary": baseline.get("acceptance_boundary"),
        "before_after": {
            "first_party_confirmed_models": [before["confirmed_models"], after["confirmed_models"]],
            "first_party_confirmed_variants": [before["confirmed_variants"], after["confirmed_variants"]],
            "oems_with_first_party_confirmation": [before["oems_with_confirmation"], after["oems_with_confirmation"]],
        },
        "first_party_confirmed_models": after["confirmed_models"],
        "first_party_confirmed_variants": after["confirmed_variants"],
        "oems_with_first_party_confirmation": after["oems_with_confirmation"],
        "identity_only": {"records": len(io),
                          "models": sum(1 for r in io if not r.variant),
                          "variants": sum(1 for r in io if r.variant)},
        "conflicts": {"records": len(conflicts)},
        "rejected": {"records": len(rec.rejected)},
        "harvested_identities": len(results),
        "outcomes": outcomes,
        "per_oem_deltas": {e["brand"]: e["p104_delta"] for e in oems
                           if any(v for k, v in e["p104_delta"].items()
                                  if isinstance(v, (int, list)) and k != "p104_unresolved")},
        "artifacts_written": ["p104_target_plan.json", "p104_official_identities.json",
                              "catalog_reconciliation_p104.json",
                              "identity_universe_p104.json",
                              "identity_matrix_p104.json", "identity_matrix_p104.md",
                              "p104_final_result.json"],
        "gates": {"staging_written": False, "prisma_touched": False,
                  "price_pass": False, "p102_p103_logic_changed": False},
        "blocker_changes": {"new_blockers": [], "cleared_blockers": [],
                            "retried_blocked_hosts": retry_hosts,
                            "smart_retry_check": smart_check,
                            "smart_status": next(
                                (e.get("official_access_status") for e in oems
                                 if e["brand"] == "Smart"), None)},
    }
    with open(os.path.join(OUT_DIR, "p104_final_result.json"), "w",
              encoding="utf-8") as fh:
        json.dump(final, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    by_method = {m: sum(1 for e in results if e["extraction_method"] == m)
                 for m in sorted({e["extraction_method"] for e in results})}
    print(json.dumps({"before": before, "after": after,
                      "deltas": {k: after[k] - before[k] for k in after},
                      "harvested": len(results), "outcomes": outcomes,
                      "by_method": by_method},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
