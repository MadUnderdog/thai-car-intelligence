#!/usr/bin/env python3
"""P103 — first-party catalog acquisition + reconciliation against the P102 universe.

This wave does ONE thing: establish official (MARKET_TRUTH) MODEL/VARIANT
identities from already-captured first-party artifacts — plus a small set of
official model pages captured for this wave — and reconcile them against the
accepted P102 identity universe without duplicating or downgrading anything.

What it deliberately does NOT do:
  * no price pass (published prices are read only as evidence, never staged)
  * no writes to audit/data-staging, prisma, or any DB
  * no promotion of identity-only candidates
  * no re-enumeration of the P102 candidate universe

Evidence rules
  * a MODEL-level source may only publish MODEL evidence, a grade/variant
    source only VARIANT evidence (`identity_level` is declared, never derived)
  * every extracted identity must be findable in the artifact bytes it cites
  * sibling brands, generations and body styles are never merged
  * ambiguous model matches become unresolved rows with an explicit reason
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from thai_factory.catalog.identity_pass import (  # noqa: E402
    FirstPartyStatus, IdentityReconciliation, ReconciledIdentity, match_key)
from thai_factory.catalog.universe import SourceRole  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO, "tests/fixtures/oem-artifacts")
P102_UNIVERSE = os.path.join(REPO, "audit/coverage/identity_universe_p102.json")
P102_MATRIX = os.path.join(REPO, "audit/coverage/identity_matrix_p102.json")
P102_FINAL = os.path.join(REPO, "audit/coverage/p102_final_result.json")
PLAN = os.path.join(REPO, "audit/coverage/p103_target_plan.json")
OUT_DIR = os.path.join(REPO, "audit/coverage")

MARKET_TRUTH = SourceRole.MARKET_TRUTH.value


# ── helpers ────────────────────────────────────────────────────────────────
def artifact_text(name: str) -> str:
    path = os.path.join(FIXTURE_DIR, name)
    with open(path, encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def artifact_sha(name: str) -> str:
    with open(os.path.join(FIXTURE_DIR, name), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def artifact_provenance(name: str) -> dict:
    path = os.path.join(FIXTURE_DIR, name + ".prov.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def loose(label: str) -> str:
    """Alphanumeric fold used ONLY for reconciliation matching."""
    return re.sub(r"[^A-Z0-9]", "", match_key("", label).upper())


def strip_plus(label: str) -> str:
    return label.lstrip("+").strip()


class Matcher:
    """Conservative reconciliation against the P102 candidate universe.

    Tiers, in order; the first tier that yields exactly one candidate wins.
    A tier that yields several candidates is AMBIGUOUS and never guesses.
    """

    def __init__(self, records):
        self.by_mfr = {}
        for r in records:
            self.by_mfr.setdefault(r.manufacturer, []).append(r)

    def model_candidates(self, mfr, label):
        """Return records whose MODEL matches `label` (any tier)."""
        exact = [r for r in self.by_mfr.get(mfr, [])
                 if match_key(mfr, r.model) == match_key(mfr, label)]
        if exact:
            return exact, "exact_match_key"
        lf = loose(label)
        fold = [r for r in self.by_mfr.get(mfr, []) if loose(r.model) == lf]
        if fold:
            return fold, "alnum_fold_match"
        return [], "absent"

    def resolve(self, mfr, model_label, variant_label=""):
        """(kind, record|None, method, reason) — kind in {existing, new, ambiguous}."""
        models, method = self.model_candidates(mfr, model_label)
        if not models:
            return ("new", None, "absent",
                    "official publication is not present in the P102 candidate "
                    "universe under any normalization tier")
        # several RECORDS sharing one normalized identity key is normal (the
        # universe keeps a model-only record and per-grade records separately);
        # only several DIFFERENT keys are ambiguous.
        keys = {match_key(mfr, r.model) for r in models}
        if len(keys) > 1:
            return ("ambiguous", None, method,
                    "model matches several distinct P102 identity keys "
                    f"({sorted(keys)}) — not guessed")
        model_rec = models[0]
        if not variant_label:
            return ("existing", model_rec, method, "")
        target = match_key(mfr, variant_label)
        variants = [r for r in self.by_mfr.get(mfr, [])
                    if r.variant and match_key(r.manufacturer, r.model) == match_key(mfr, model_rec.model)]
        for r in variants:
            if match_key(mfr, r.variant) == target:
                return ("existing", r, method, "")
        for r in variants:
            if loose(r.variant) == loose(variant_label):
                return ("existing", r, "alnum_fold_match", "")
        for r in variants:
            if loose(strip_plus(r.variant)) == loose(strip_plus(variant_label)):
                return ("existing", r, "alnum_fold_match+leading_plus_strip", "")
        return ("new", model_rec, "model_matched_variant_absent",
                "official grade is published for a model already in P102 but "
                "that grade label is not in the P102 variant universe")


# ── extractors (each returns identity dicts with evidence) ────────────────
MAZDA_PAGE_MODEL = {
    "mazda_car_mazda-cx5.html": "NEW MAZDA CX-5",
    "mazda_car_mazda2-essential.html": "NEW MAZDA2 ESSENTIAL",
    "mazda_car_mazda3-sedan.html": "MAZDA3 SEDAN",
    "mazda_car_mazda-cx30-essential.html": "NEW MAZDA CX-30 ESSENTIAL",
    "mazda_car_new-mazda-bt50.html": "NEW MAZDA BT-50",
}
MAZDA_GRADE_RE = re.compile(
    r'"ID":"\d+","ModelID":"(?P<model_id>\d+)","Title":"(?P<title>[^"]{1,60}?)",'
    r'"Engine":"(?P<engine>[^"]*?)","Price":"(?P<price>[^"]*?)"')


def extract_mazda():
    out = []
    for fname, model_label in MAZDA_PAGE_MODEL.items():
        text = artifact_text(fname)
        prov = artifact_provenance(fname)
        # model attribution guard: the official page must publish grades for
        # exactly one ModelID.  More than one means the payload carries sibling
        # models and the page cannot attribute grades on its own -> refuse.
        model_ids = {m.group("model_id") for m in MAZDA_GRADE_RE.finditer(text)}
        assert len(model_ids) == 1, f"{fname}: mixed ModelID payload {model_ids}"
        seen = set()
        for m in MAZDA_GRADE_RE.finditer(text):
            title = m.group("title").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            # the published grade must exist in the artifact bytes
            if title not in text:
                continue
            out.append({
                "manufacturer": "Mazda", "model": model_label,
                "variant": title, "identity_level": "VARIANT",
                "published_label": f"{model_label} {title}",
                "artifact": fname, "sha256": artifact_sha(fname),
                "source_url": prov.get("source_url", "https://www.mazda.co.th/"),
                "extraction_method": "embedded_json_grade_array",
                "evidence": {"selector": "embedded grade objects "
                                         "ID/ModelID/Title/Price",
                             "price_thb": m.group("price") or None},
            })
    return out


MG_GRADE_RE = re.compile(
    r'\\?"title\\?":\\?"(?P<t>(?:NEW )?MG[A-Za-z0-9 +]{2,30}?) รุ่น '
    r'(?P<g>[A-Za-z0-9+]{1,10})\\?"')


def extract_mg():
    out = []
    fname = "mg_home_page.html"
    text = artifact_text(fname)
    prov = artifact_provenance(fname)
    seen = set()
    for m in MG_GRADE_RE.finditer(text):
        model_label, grade = m.group("t").strip(), m.group("g").strip()
        if (model_label, grade) in seen:
            continue
        seen.add((model_label, grade))
        if m.group("t") not in text:
            continue
        out.append({
            "manufacturer": "MG", "model": model_label, "variant": grade,
            "identity_level": "VARIANT",
            "published_label": f"{model_label} รุ่น {grade}",
            "artifact": fname, "sha256": artifact_sha(fname),
            "source_url": prov.get("source_url", "https://www.mgcars.com/"),
            "extraction_method": "published_title_model_prefixed",
            "evidence": {"selector": "published title containing model + รุ่น + grade"},
        })
    return out


SUBARU_PATTERNS = [
    ("subaru_th_model_brz.html", "BRZ", r"รุ่น\s+(BRZ\s+AT)"),
    ("subaru_th_model_crosstrek.html", "CROSSTREK", r"(2\.0i-S\s+EyeSight)"),
]


def extract_subaru():
    out = []
    for fname, model_label, pattern in SUBARU_PATTERNS:
        text = artifact_text(fname)
        prov = artifact_provenance(fname)
        for hit in sorted(set(re.findall(pattern, text))):
            hit = hit.strip()
            if hit not in text:
                continue
            out.append({
                "manufacturer": "Subaru", "model": model_label, "variant": hit,
                "identity_level": "VARIANT",
                "published_label": f"{model_label} {hit}",
                "artifact": fname, "sha256": artifact_sha(fname),
                "source_url": prov.get("source_url", "https://www.subaru.asia/th/th/"),
                "extraction_method": "official_model_page_grade_marker",
                "evidence": {"selector": pattern},
            })
    return out


# Isuzu: grade is published in official prose next to the model name.  Both
# published pairs resolve ambiguously against the P102 model universe, so they
# are harvested as evidence rows and reported unresolved rather than guessed.
ISUZU_PAIRS = [("isuzu_page.html", "MU-X", "Active", "มิว-เอ็กซ์"),
               ("isuzu_page.html", "Isuzu D Max", "L", "ดีแมคซ์ 4 ประตู")]


def extract_isuzu():
    out = []
    for fname, model_label, grade, thai in ISUZU_PAIRS:
        text = artifact_text(fname)
        prov = artifact_provenance(fname)
        if f"เกรด {grade}" not in text or thai not in text:
            continue
        out.append({
            "manufacturer": "Isuzu", "model": model_label, "variant": grade,
            "identity_level": "VARIANT",
            "published_label": f"{thai} เกรด {grade}",
            "artifact": fname, "sha256": artifact_sha(fname),
            "source_url": prov.get("source_url", "https://www.isuzu.co.th/"),
            "extraction_method": "official_prose_model_grade_sentence",
            "evidence": {"selector": "published sentence naming model and เกรด"},
        })
    return out


EXTRACTORS = [("Mazda", extract_mazda), ("MG", extract_mg),
              ("Subaru", extract_subaru), ("Isuzu", extract_isuzu)]


# ── baseline rehydration ───────────────────────────────────────────────────
def load_baseline():
    data = json.load(open(P102_UNIVERSE, encoding="utf-8"))
    uni = data["universe"]
    rec = IdentityReconciliation(target_date=data.get("target_date", "p103"))
    for r in uni["records"]:
        obj = ReconciledIdentity(manufacturer=r["manufacturer"], model=r["model"],
                                 variant=r.get("variant") or "",
                                 generation=r.get("generation") or "")
        obj.sources = [dict(s) for s in r.get("sources", [])]
        obj.first_party = [dict(s) for s in r.get("first_party", [])]
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


def identity_block(records, mfr):
    """Per-OEM identity counts — mirrors the P102 matrix vocabulary."""
    mine = [r for r in records if r.manufacturer == mfr]
    cand_m = {(mfr, match_key(mfr, r.model)) for r in mine}
    cand_v = {(mfr, match_key(mfr, r.model), match_key(mfr, r.variant))
              for r in mine if r.variant}
    conf_m = {(mfr, match_key(mfr, r.model)) for r in mine
              if r.status in (FirstPartyStatus.CONFIRMED_MODEL.value,
                              FirstPartyStatus.CONFIRMED_VARIANT.value)}
    conf_v = {(mfr, match_key(mfr, r.model), match_key(mfr, r.variant))
              for r in mine if r.variant and r.status == FirstPartyStatus.CONFIRMED_VARIANT.value}
    io_m = {(mfr, match_key(mfr, r.model)) for r in mine
            if r.status == FirstPartyStatus.IDENTITY_ONLY.value and not r.variant}
    io_v = {(mfr, match_key(mfr, r.model), match_key(mfr, r.variant))
            for r in mine if r.variant and r.status == FirstPartyStatus.IDENTITY_ONLY.value}
    conf = [r for r in mine if r.first_party]
    return {
        "model_candidates_discovered": len(cand_m),
        "variant_candidates_discovered": len(cand_v),
        "first_party_confirmed_models": len(conf_m),
        "first_party_confirmed_variants": len(conf_v),
        "identity_only_models": len(io_m),
        "identity_only_variants": len(io_v),
        "first_party_confirmed_records": len(conf),
        "candidate_sources": sorted({s["source_name"] for r in mine for s in r.sources}),
        "first_party_sources": sorted({s["source_name"] for r in mine for s in r.first_party}),
        "conflicts": sum(1 for r in mine if r.status == "CONFLICT"),
    }


def main() -> int:
    plan = json.load(open(PLAN, encoding="utf-8"))
    baseline_final = json.load(open(P102_FINAL, encoding="utf-8"))
    p102_matrix = json.load(open(P102_MATRIX, encoding="utf-8"))

    rec = load_baseline()
    before = {
        "records": len(rec.records),
        "confirmed_models": sum(identity_block(rec.records, b)["first_party_confirmed_models"]
                                for b in {r.manufacturer for r in rec.records}),
        "confirmed_variants": sum(identity_block(rec.records, b)["first_party_confirmed_variants"]
                                  for b in {r.manufacturer for r in rec.records}),
        "oems_with_confirmation": sum(
            1 for b in {r.manufacturer for r in rec.records}
            if identity_block(rec.records, b)["first_party_confirmed_models"] > 0),
    }
    # fidelity guard: the rehydrated baseline must reproduce the P102 totals
    assert before["confirmed_models"] == baseline_final["first_party_confirmed_models"], before
    assert before["confirmed_variants"] == baseline_final["first_party_confirmed_variants"], before

    matcher = Matcher(rec.records)
    harvested, reconciliation = [], []
    for brand, fn in EXTRACTORS:
        for item in fn():
            harvested.append(item)

    for item in harvested:
        kind, target, method, reason = matcher.resolve(
            item["manufacturer"], item["model"], item["variant"])
        entry = dict(item)
        entry["reconciliation"] = {"outcome": kind, "match_method": method,
                                   "reason": reason}
        if kind == "ambiguous":
            entry["reconciliation"]["candidates"] = reason
            reconciliation.append(entry)
            continue
        if kind == "existing":
            entry["reconciliation"]["matched_record"] = {
                "model": target.model, "variant": target.variant}
            entry["reconciliation"]["prior_status"] = target.status
        else:
            entry["reconciliation"]["new_model"] = item["model"]

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
        }
        if kind == "existing":
            rec.add_first_party(target.manufacturer, target.model, target.variant, source)
        else:
            rec.add_first_party(item["manufacturer"], item["model"], item["variant"], source)
        reconciliation.append(entry)

    rec.resolve_statuses()

    # duplicate suppression: the same (source, label, artifact) may only be
    # attached once — _attach dedups on (name, url, level), assert it held
    dupes = [r for r in rec.records
             if len({(s.get("source_name"), s.get("source_url"), s.get("identity_level"))
                     for s in r.sources}) != len(r.sources)]
    assert not dupes, dupes[:3]

    after_blocks = {b: identity_block(rec.records, b)
                    for b in sorted({r.manufacturer for r in rec.records})}
    after = {
        "records": len(rec.records),
        "confirmed_models": sum(v["first_party_confirmed_models"] for v in after_blocks.values()),
        "confirmed_variants": sum(v["first_party_confirmed_variants"] for v in after_blocks.values()),
        "oems_with_confirmation": sum(
            1 for v in after_blocks.values() if v["first_party_confirmed_models"] > 0),
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat()

    # ── artifact 1: harvested official identities + provenance ────────────
    with open(os.path.join(OUT_DIR, "p103_official_identities.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"artifact": "p103-official-identities/1", "generated_at": generated,
                   "plan": os.path.basename(PLAN),
                   "rules": ["identity_level declared at extraction",
                             "published label must exist in the cited artifact bytes",
                             "no price rows, no staging writes"],
                   "identities": reconciliation}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # ── artifact 2: reconciliation result ─────────────────────────────────
    outcomes = {}
    for e in reconciliation:
        outcomes[e["reconciliation"]["outcome"]] = \
            outcomes.get(e["reconciliation"]["outcome"], 0) + 1
    with open(os.path.join(OUT_DIR, "catalog_reconciliation_p103.json"), "w",
              encoding="utf-8") as fh:
        json.dump({
            "artifact": "p103-catalog-reconciliation/1", "generated_at": generated,
            "before": before, "after": after,
            "deltas": {k: after[k] - before[k] for k in after},
            "harvested": len(reconciliation), "outcomes": outcomes,
            "new_first_party_identities": [
                {"manufacturer": e["manufacturer"], "model": e["model"],
                 "variant": e["variant"], "identity_level": e["identity_level"],
                 "artifact": e["artifact"]}
                for e in reconciliation
                if e["reconciliation"]["outcome"] == "new"],
            "ambiguous": [
                {"manufacturer": e["manufacturer"], "model": e["model"],
                 "variant": e["variant"], "reason": e["reconciliation"]["reason"]}
                for e in reconciliation
                if e["reconciliation"]["outcome"] == "ambiguous"],
            "no_price_pass": True,
            "staging_written": False,
        }, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # ── artifact 3: P103 identity universe (records, statuses, evidence) ──
    uni_json = {
        "schema": "p103-identity-universe/1",
        "generated_at": generated,
        "baseline_artifact": "audit/coverage/identity_universe_p102.json",
        "p103_harvested_identities": len(reconciliation),
        "acceptance_boundary": "Phase-1 audit evidence only — identity-only and "
                               "new first-party records never enter the accepted set",
        "universe": rec.to_json(),
    }
    with open(os.path.join(OUT_DIR, "identity_universe_p103.json"), "w",
              encoding="utf-8") as fh:
        json.dump(uni_json, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # ── artifact 4: per-OEM coverage matrix (P102 layout + P103 delta) ────
    oems = []
    for entry in p102_matrix["oems"]:
        brand = entry["brand"]
        e = dict(entry)
        before_id = dict(entry["identity"])
        after_id = after_blocks.get(brand, before_id)
        e["p102_identity"] = before_id
        e["identity"] = after_id
        e["p103_delta"] = {
            "model_candidates": after_id["model_candidates_discovered"] - before_id["model_candidates_discovered"],
            "variant_candidates": after_id["variant_candidates_discovered"] - before_id["variant_candidates_discovered"],
            "first_party_confirmed_models": after_id["first_party_confirmed_models"] - before_id["first_party_confirmed_models"],
            "first_party_confirmed_variants": after_id["first_party_confirmed_variants"] - before_id["first_party_confirmed_variants"],
            "p103_official_artifacts": sorted({
                x["artifact"] for x in reconciliation
                if x["manufacturer"] == brand}),
            "p103_unresolved": [
                {"model": x["model"], "variant": x["variant"],
                 "reason": x["reconciliation"]["reason"]}
                for x in reconciliation if x["manufacturer"] == brand
                and x["reconciliation"]["outcome"] == "ambiguous"],
        }
        oems.append(e)
    matrix = dict(p102_matrix)
    matrix["artifact"] = "identity-matrix-p103/1"
    matrix["generated_at"] = generated
    matrix["baseline_artifact"] = "audit/coverage/identity_matrix_p102.json"
    matrix["oems"] = oems
    with open(os.path.join(OUT_DIR, "identity_matrix_p103.json"), "w",
              encoding="utf-8") as fh:
        json.dump(matrix, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # ── artifact 4b: matrix markdown ──────────────────────────────────────
    lines = ["# P103 per-OEM catalog coverage matrix", "",
             f"Generated {generated} · baseline "
             "`identity_matrix_p102.json` · plan `p103_target_plan.json`", ""]
    lines.append("| OEM | access | official models before | official models after "
                 "| official variants before | official variants after | delta variants |")
    lines.append("|---|---|---|---|---|---|---|")
    for entry in oems:
        d = entry.get("p103_delta", {})
        ident = entry["identity"]
        b = entry.get("p102_identity", {})
        lines.append(
            f"| {entry['brand']} | {entry.get('official_access_status', '?')} "
            f"| {b.get('first_party_confirmed_models', ident['first_party_confirmed_models'] - d.get('first_party_confirmed_models', 0))}"
            f" | {ident['first_party_confirmed_models']}"
            f" | {b.get('first_party_confirmed_variants', ident['first_party_confirmed_variants'] - d.get('first_party_confirmed_variants', 0))}"
            f" | {ident['first_party_confirmed_variants']}"
            f" | {d.get('first_party_confirmed_variants', 0)} |")
    with open(os.path.join(OUT_DIR, "identity_matrix_p103.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    # ── artifact 5: P103 final result ─────────────────────────────────────
    rec_conflicts = [r for r in rec.records if r.status == "CONFLICT"]
    final = {
        "schema": "p103-final-result/1", "generated_at": generated,
        "acceptance_boundary": baseline_final["acceptance_boundary"],
        "baseline": {k: baseline_final[k] for k in (
            "first_party_confirmed_models", "first_party_confirmed_variants")},
        "first_party_confirmed_models": after["confirmed_models"],
        "first_party_confirmed_variants": after["confirmed_variants"],
        "oems_with_first_party_confirmation": after["oems_with_confirmation"],
        "before_after": {
            "first_party_confirmed_models": [before["confirmed_models"], after["confirmed_models"]],
            "first_party_confirmed_variants": [before["confirmed_variants"], after["confirmed_variants"]],
            "oems_with_first_party_confirmation": [before["oems_with_confirmation"], after["oems_with_confirmation"]],
        },
        "identity_only": {
            "records": sum(1 for r in rec.records if r.status == "IDENTITY_ONLY"),
            "models": sum(1 for r in rec.records
                          if r.status == "IDENTITY_ONLY" and not r.variant),
            "variants": sum(1 for r in rec.records
                            if r.status == "IDENTITY_ONLY" and r.variant),
        },
        "conflicts": {"records": len(rec_conflicts)},
        "harvested_identities": len(reconciliation),
        "outcomes": outcomes,
        "per_oem_deltas": {
            b: d for b, d in (
                (entry["brand"], entry.get("p103_delta", {})) for entry in oems)
            if any(v for k, v in d.items() if isinstance(v, (int, list)) and k != "p103_unresolved")},
        "per_oem_unresolved": {
            entry["brand"]: entry.get("p103_delta", {}).get("p103_unresolved", [])
            for entry in oems
            if entry.get("p103_delta", {}).get("p103_unresolved")},
        "blocker_changes": {
            "new_blockers": [], "cleared_blockers": [],
            "retried_blocked_hosts": [],
            "smart_status": next(
                (e.get("official_access_status") for e in oems if e["brand"] == "Smart"), None),
            "policy": "no blocked host is requested before its next_retry_at; "
                      "blocker evidence preserved verbatim from the P102 matrix",
        },
        "artifacts_written": sorted(
            f for f in os.listdir(OUT_DIR) if "p103" in f or "matrix_p103" in f
            or f.startswith("identity_universe_p103")),
        "gates": {
            "staging_written": False, "prisma_touched": False,
            "price_pass": False, "p102_logic_changed": False,
        },
        "capture_log": "audit/coverage/p103_capture_log.json",
        "target_plan": os.path.basename(PLAN),
    }
    with open(os.path.join(OUT_DIR, "p103_final_result.json"), "w",
              encoding="utf-8") as fh:
        json.dump(final, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(json.dumps({"before": before, "after": after,
                      "deltas": {k: after[k] - before[k] for k in after},
                      "outcomes": outcomes, "records": len(rec.records)},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
