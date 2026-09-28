#!/usr/bin/env python3
"""P111 — ONE bounded price fix + source-expansion pass.

Two jobs, one pass:

A) The audit's known semantic edge: the MG EP / PLUS row binds an exact price
   (`price_type=EXACT_VARIANT`) from a *reference* source that is
   `NOT_A_CURRENTNESS_SOURCE`.  Every bound row now carries an explicit
   `msrp_status` so `EXACT_CURRENT_MSRP_VERIFIED` is mutually exclusive from
   `EXACT_BINDING_NOT_VERIFIED_CURRENT` / `MSRP_STARTING_NOT_EXACT` /
   `NON_MSRP_TYPE`.  Evidence and price values are preserved verbatim; only
   the classification/reporting changes.  The identity ledger, verifier,
   Prisma, API, staging and the production DB are never touched.

B) Source expansion for the P110 UNVERIFIED_PRICE rows: the harvest runs over
   the whole artifact pool including the `p111_price_sources.py` batch
   captures (AcquisitionWriter + .prov.json + SHA).  Same-record binding
   rules, price_type strictness and the blocked-OEM boundary are unchanged:
   if a source only exposes model-level/range/prose prices the row stays
   UNVERIFIED and is reported as a source ceiling — never repaired by
   inventing or spreading prices.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "audit/coverage")
SESSION_ID = "p111_price_pass_20260928"
ACCEPTED_LEDGER = 488
ACCEPTED_BASELINE = "audit/coverage/p108_final_result.json"
P110_RECON = os.path.join(OUT_DIR, "p110_price_reconciliation.json")

_SPEC = importlib.util.spec_from_file_location(
    "p110_price_pass", os.path.join(REPO, "scripts/p110_price_pass.py"))
P110 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(P110)
_SPEC9 = importlib.util.spec_from_file_location(
    "p109_current_market", os.path.join(REPO, "scripts/p109_current_market.py"))
P109 = importlib.util.module_from_spec(_SPEC9)
_SPEC9.loader.exec_module(P109)

BLOCKED_ACCESS = P110.BLOCKED_ACCESS


# ─────────────────────── A. msrp_status classification ─────────────────────

def msrp_status(row: dict) -> str:
    """Mutually exclusive bucket for one bound price row.

    Derived from evidence only: price_type decides *what* the price is,
    trust tier + currentness decide whether it can be called a *verified
    current official MSRP*.
    """
    if row.get("price_type") == "EXACT_VARIANT":
        if (row.get("trust_tier") == "official_verified"
                and row.get("currentness") == "CURRENT"):
            return "EXACT_CURRENT_MSRP_VERIFIED"
        return "EXACT_BINDING_NOT_VERIFIED_CURRENT"
    if row.get("price_type") == "MSRP_STARTING":
        return "MSRP_STARTING_NOT_EXACT"
    return "NON_MSRP_TYPE"


def msrp_status_reason(row: dict) -> str:
    status = msrp_status(row)
    tier = row.get("trust_tier", "?")
    cur = row.get("currentness", "?")
    if status == "EXACT_CURRENT_MSRP_VERIFIED":
        return (f"EXACT_VARIANT bound on the same published record; trust_tier="
                f"{tier}, currentness={cur} — counted as verified current official MSRP")
    if status == "EXACT_BINDING_NOT_VERIFIED_CURRENT":
        return (f"exact price bound and preserved, but NOT a verified current MSRP: "
                f"trust_tier={tier}, currentness={cur} "
                f"({row.get('currentness_reason') or 'no currentness'}); "
                f"excluded from exact_msrp_verified and reported separately")
    if status == "MSRP_STARTING_NOT_EXACT":
        return (f"price_type=MSRP_STARTING is a starting-from figure, not an exact "
                f"variant MSRP: trust_tier={tier}, currentness={cur}; counted as "
                f"starting-price evidence only")
    return (f"price_type={row.get('price_type')} is promotional/finance/range and can "
            f"never be counted as exact MSRP: trust_tier={tier}, currentness={cur}")


def model_page_match(url: str, model: str, manufacturer: str) -> bool:
    """True when a captured official URL names this model.

    P109's page_matches() needs the full model string inside the path, which
    never happens when the model string carries the OEM name ("Toyota Yaris
    Ativ" vs /model/yarisativ), so the manufacturer tokens are stripped
    first.  Over-matching only costs scan time: a row binds only when the
    variant's own published label appears in the same record, so a wrongly
    attached page can never move a price onto the wrong grade.
    """
    if P109.page_matches(url, model):
        return True
    path = re.sub(r"https?://[^/]+", "", url or "").casefold()
    if not path.strip("/"):
        return False
    words = [w for w in re.split(r"[^a-z0-9]+", (model or "").casefold()) if w]
    brand_words = {w for w in re.split(r"[^a-z0-9]+",
                                      (manufacturer or "").casefold()) if w}
    stripped = [w for w in words if w not in brand_words]
    compact_model = re.sub(r"[^a-z0-9]+", "", "".join(stripped or words))
    if not compact_model:
        return False
    # path-segment prefix relation: "…/en/crv" ↔ model "CR-V e:HEV" (crv is a
    # prefix of crvehev), while "/accessories" is neither prefix of nor from
    # "accordehev" — substring-on-whole-path would attach nav-only mentions.
    for seg in path.strip("/").split("/"):
        s = re.sub(r"[^a-z0-9]+", "", seg)
        if not s:
            continue
        if len(s) >= 3 and (compact_model.startswith(s) or s.startswith(compact_model)):
            return True
    return False


def scoped_labels(rec: dict) -> list:
    """Model-scoped published labels of this exact record.

    Only these may drive the scan-scope match: bare grade labels
    ("e:HEV E") are shared across models (Accord/CR-V/HR-V all publish one),
    so matching on them would let one model's page price another model's
    grade — the contamination the longest-label rule does not cover.
    """
    model, variant = rec["model"], rec["variant"]
    base = re.sub(r"^(%s)\s+" % re.escape(rec["manufacturer"]), "", model,
                  flags=re.I)
    # model-scoped composites only: a bare model mention can sit in the site
    # navigation of every page, and a bare grade label ("e:HEV E") is shared
    # across models — neither may widen the scan scope on its own.
    return [lab for lab in (P110.norm(f"{model} {variant}"),
                            P110.norm(f"{base} {variant}")) if lab]


def all_labels_for(rec: dict) -> list:
    """published labels of this exact record (model + grade combinations)."""
    return P110.label_variants(rec)


def _dump(name: str, payload) -> None:
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main() -> int:
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    universe = json.load(open(os.path.join(OUT_DIR, "identity_universe_p108.json"),
                              encoding="utf-8"))
    matrix0 = json.load(open(os.path.join(OUT_DIR, "identity_matrix_p109.json"),
                             encoding="utf-8"))
    accepted = [r for r in universe["universe"]["records"]
                if r["status"] == "CONFIRMED_VARIANT"]
    assert len(accepted) == ACCEPTED_LEDGER, len(accepted)
    p110_recon = json.load(open(P110_RECON, encoding="utf-8"))
    p111_capture = json.load(open(os.path.join(OUT_DIR, "p111_price_capture_log.json"),
                                  encoding="utf-8"))

    artifacts = P110.load_artifacts()
    cur = P110.currentness_by_artifact()

    # New captures from the P111 batch are classified with the SAME P109
    # currentness/family classifier the project already trusts — the p109
    # inventory itself is never rewritten (it stays byte-identical).
    new_captures = {}
    for fn, art in artifacts.items():
        if "_p111_" not in fn:
            continue
        brand = P109.brand_of(art["url"], fn)
        signal, family, reason = P109.currentness(art["url"], art.get("raw") or "",
                                                  brand)
        cur[fn] = {"currentness": signal, "reason": reason, "family": family}
        path = (art["url"].split("?", 1)[0].rstrip("/") or "").lower()
        new_captures[fn] = {
            "brand": brand, "url": art["url"], "family": family,
            "currentness": signal, "reason": reason,
            "model_index": path.endswith("/models"),
            "text": (art.get("raw") or "").casefold(),
            "ntext": P110.norm(art.get("raw") or ""),
        }
    assert new_captures, "the P111 batch captures must be visible to the pass"

    evidence, unverified = [], []
    blocks_cache: dict = {}
    all_labels = sorted({lab for r in accepted for lab in P110.label_variants(r)},
                        key=len, reverse=True)
    match_cache: dict = {}
    for rec in sorted(accepted, key=lambda r: (r["manufacturer"], r["model"],
                                               r["variant"])):
        extra_sources = []
        for fn, meta in new_captures.items():
            if meta["brand"] != rec["manufacturer"]:
                continue
            matched = (meta["model_index"]
                       or model_page_match(meta["url"], rec["model"],
                                           rec["manufacturer"]))
            if not matched:
                # Thai-published model names rarely appear in the URL slug
                # ("นิสสัน คิกส์" vs /kicks-e-power), so a captured official page
                # that publishes this record's own published label also counts
                # as a scan-scope match.  Binding still needs the label AND its
                # price in the same record, so a false attach cannot move money.
                matched = any(len(lab) >= 4 and lab in meta["ntext"]
                              for lab in scoped_labels(rec))
            if matched:
                extra_sources.append({
                    "artifact": f"tests/fixtures/oem-artifacts/{fn}",
                    "source_role": "MARKET_TRUTH",
                    "source_url": meta["url"],
                    "note": "P111 batch capture: first-party official page for this "
                            "model (identity ledger untouched; scan scope only)"})
        rec2 = dict(rec, sources=list(rec.get("sources") or []) + extra_sources)
        rows = P110.harvest_record(rec2, artifacts, cur,
                                   all_labels=all_labels, best_cache=match_cache)
        official = [r for r in rows if r["trust_tier"] == "official_verified"]
        pool = official or [r for r in rows if r["source_class"] == "MARKET_TRUTH"] or rows
        if not pool:
            unverified.append({
                "manufacturer": rec["manufacturer"], "model": rec["model"],
                "variant": rec["variant"], "scope": "TH",
                "status": "UNVERIFIED_PRICE",
                "category": P110.diagnose_unverified(rec, artifacts, cur, blocks_cache),
                "reason": "no price is bound to the same record as this exact grade in "
                          "any captured first-party artifact (model-level, range or "
                          "third-party prices are never promoted to a grade MSRP)"})
            continue

        def canon_key(r):
            order = {"EXACT_VARIANT": 0, "MSRP_STARTING": 1, "RANGE": 2,
                     "PROMOTIONAL": 3, "FINANCE_INSTALLMENT": 4}
            trust = 0 if r["trust_tier"] == "official_verified" else 1
            return (trust, order.get(r["price_type"], 9), r["artifact"],
                    r["locator"].get("block_index", 0))
        ordered = sorted(pool, key=canon_key)
        canonical = ordered[0]
        row = {
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
        }
        row["msrp_status"] = msrp_status(row)
        row["msrp_status_reason"] = msrp_status_reason(row)
        evidence.append(row)

    # ── A. mutually exclusive buckets ─────────────────────────────────────
    buckets = ["EXACT_CURRENT_MSRP_VERIFIED", "EXACT_BINDING_NOT_VERIFIED_CURRENT",
               "MSRP_STARTING_NOT_EXACT", "NON_MSRP_TYPE"]
    status_dist = {b: sum(1 for e in evidence if e["msrp_status"] == b)
                   for b in buckets}
    exact_msrp = status_dist["EXACT_CURRENT_MSRP_VERIFIED"]
    binding_not_verified = status_dist["EXACT_BINDING_NOT_VERIFIED_CURRENT"]
    starting = status_dist["MSRP_STARTING_NOT_EXACT"]
    non_msrp = status_dist["NON_MSRP_TYPE"]
    assert sum(status_dist.values()) == len(evidence)
    assert exact_msrp + binding_not_verified + starting + non_msrp == len(evidence)

    # third-party / non-current rows are structurally excluded from verified MSRP
    promoted = [e for e in evidence
                if e["msrp_status"] == "EXACT_CURRENT_MSRP_VERIFIED"
                and (e["source_class"] != "MARKET_TRUTH" or e["trust_tier"] != "official_verified"
                     or e["currentness"] != "CURRENT")]
    assert not promoted, promoted

    # ── per-OEM ───────────────────────────────────────────────────────────
    import collections
    per_oem = {}
    for brand in sorted({r["manufacturer"] for r in accepted}):
        targets = [r for r in accepted if r["manufacturer"] == brand]
        got = [e for e in evidence if e["manufacturer"] == brand]
        un = [u for u in unverified if u["manufacturer"] == brand]
        per_oem[brand] = {
            "accepted_variants": len(targets),
            "price_bound": len(got),
            "exact_msrp_verified": sum(1 for e in got
                                       if e["msrp_status"] == "EXACT_CURRENT_MSRP_VERIFIED"),
            "exact_binding_not_verified_current": sum(
                1 for e in got if e["msrp_status"] == "EXACT_BINDING_NOT_VERIFIED_CURRENT"),
            "msrp_starting_not_exact": sum(
                1 for e in got if e["msrp_status"] == "MSRP_STARTING_NOT_EXACT"),
            "unverified_price": len(un),
            "coverage_pct": round(100.0 * len(got) / len(targets), 1) if targets else 0.0,
            "price_type_distribution": dict(sorted(collections.Counter(
                e["price_type"] for e in got).items())),
        }
    type_dist = dict(sorted(collections.Counter(e["price_type"]
                                                for e in evidence).items()))
    matrix_access = {o["brand"]: o["official_access_status"] for o in matrix0["oems"]}
    blocked_brands = sorted([b for b, a in matrix_access.items()
                             if a in BLOCKED_ACCESS])
    before = {
        "price_bound": p110_recon["price_bound"],
        "exact_msrp_verified": p110_recon["exact_msrp_verified"],
        "exact_non_msrp_only": p110_recon["exact_non_msrp_only"],
        "unverified_price": p110_recon["unverified_price"],
        "artifact": "audit/coverage/p110_price_reconciliation.json",
    }
    delta_price_bound = len(evidence) - before["price_bound"]

    recon = {
        "schema": "p111_price_reconciliation/1", "generated_at": stamp,
        "baseline_artifact": ACCEPTED_BASELINE,
        "accepted_variants_targeted": ACCEPTED_LEDGER,
        "price_bound": len(evidence),
        # mutually exclusive buckets — every bound row lands in exactly one
        "exact_msrp_verified": exact_msrp,
        "exact_binding_not_verified_current": binding_not_verified,
        "msrp_starting_not_exact": starting,
        "non_msrp_type_rows": non_msrp,
        "msrp_status_distribution": status_dist,
        # derived views (kept for continuity with the P110 report)
        "exact_non_msrp_only": binding_not_verified + starting + non_msrp,
        "unverified_price": len(unverified),
        "before": before,
        "delta_price_bound": delta_price_bound,
        "delta_exact_msrp_verified": exact_msrp - before["exact_msrp_verified"],
        "delta_unverified_price": len(unverified) - before["unverified_price"],
        "blocked_oems": blocked_brands,
        "blocked_oem_accepted_variants": 0,
        "blocked_or_source_gap": len(unverified),
        "price_type_distribution": type_dist,
        "prices_invented": 0,
        "third_party_promoted_to_msrp": 0,
        "mg_reference_row": next(
            {"status": e["msrp_status"], "reason": e["msrp_status_reason"],
             "price_thb": e["price_thb"], "artifact": e["artifact"],
             "trust_tier": e["trust_tier"], "currentness": e["currentness"],
             "price_preserved": True}
            for e in evidence if e["manufacturer"] == "MG"
            and e["model"] == "Mg Ep" and e["variant"] == "PLUS"),
        "identity_ledger_unchanged": {"confirmed_variants": ACCEPTED_LEDGER,
                                      "artifact": ACCEPTED_BASELINE},
        "per_oem": per_oem,
        "unverified": unverified,
    }
    _dump("p111_price_reconciliation.json", recon)
    _dump("p111_price_evidence.json", {
        "schema": "p111_price_evidence/1", "generated_at": stamp,
        "baseline_artifact": ACCEPTED_BASELINE,
        "tier_note": "Phase-1 price evidence only: nothing is written to staging, the "
                     "verifier, Prisma, the API or any database; identity counts "
                     "untouched. msrp_status separates exact binding from verified "
                     "current official MSRP.",
        "rows": sorted(evidence, key=lambda e: (e["manufacturer"], e["model"],
                                                e["variant"]))})
    ev_path = os.path.join(OUT_DIR, "p111_price_evidence.json")
    _dump("p111_price_evidence.json.prov.json", {
        "artifact_filename": "p111_price_evidence.json",
        "sha256": hashlib.sha256(open(ev_path, "rb").read()).hexdigest(),
        "generated_at": stamp,
        "acquisition_method": "derived_from_accepted_ledger_and_captured_artifacts",
        "session_id": SESSION_ID,
        "provenance_state": "DERIVED_PHASE1_AUDIT",
        "inputs": [ACCEPTED_BASELINE, "audit/coverage/identity_universe_p108.json",
                   "audit/coverage/p110_price_evidence.json",
                   "audit/coverage/p111_price_source_inventory.json",
                   "audit/coverage/p111_price_capture_log.json"]})

    new_captures_count = p111_capture.get("new_captures", 0)
    _dump("p111_final_result.json", {
        "schema": "p111_final_result/1", "generated_at": stamp,
        "baseline_artifact": ACCEPTED_BASELINE,
        "accepted_variants_targeted": ACCEPTED_LEDGER,
        "price_bound": len(evidence),
        "exact_msrp_verified": exact_msrp,
        "exact_binding_not_verified_current": binding_not_verified,
        "msrp_starting_not_exact": starting,
        "non_msrp_type_rows": non_msrp,
        "msrp_status_distribution": status_dist,
        "exact_non_msrp_only": recon["exact_non_msrp_only"],
        "unverified_price": len(unverified),
        "blocked_or_source_gap": len(unverified),
        "blocked_oems": blocked_brands,
        "blocked_oem_accepted_variants": 0,
        "price_type_distribution": type_dist,
        "prices_invented": 0,
        "third_party_promoted_to_msrp": 0,
        "delta_vs_p110": {"price_bound": delta_price_bound,
                          "exact_msrp_verified": exact_msrp - before["exact_msrp_verified"],
                          "unverified_price": len(unverified) - before["unverified_price"],
                          "baseline": before["artifact"]},
        "mg_reference_row": recon["mg_reference_row"],
        "new_captures": new_captures_count,
        "new_capture_classification": {
            "count": len(new_captures),
            "by_currentness": dict(sorted(__import__("collections").Counter(
                m["currentness"] for m in new_captures.values()).items())),
            "by_family": dict(sorted(__import__("collections").Counter(
                m["family"] for m in new_captures.values()).items())),
            "classifier": "scripts/p109_current_market.py family_of/currentness "
                          "(the p109 inventory artifact itself is untouched)"},
        "source_expansion": {
            "inventory": "audit/coverage/p111_price_source_inventory.json",
            "capture_log": "audit/coverage/p111_price_capture_log.json",
            "candidates": json.load(open(os.path.join(
                OUT_DIR, "p111_price_source_inventory.json"), encoding="utf-8"))["candidates"],
        },
        "identity_ledger_unchanged": {"confirmed_variants": ACCEPTED_LEDGER,
                                      "changed_by_p111": False},
        "gates": {"staging_written": False, "price_pass_staging": False,
                  "prisma_touched": False, "production_db_unchanged": True,
                  "verifier_touched": False, "identity_counts_changed": False},
        "no_loop_rule": "one bounded pass: exact-MSRP delta and the remaining source "
                        "ceiling are reported as they are; no repair loop chases the "
                        "number, no model-level price is spread to a grade",
    })
    print(json.dumps({"targeted": ACCEPTED_LEDGER, "price_bound": len(evidence),
                      "exact_msrp_verified": exact_msrp,
                      "exact_binding_not_verified_current": binding_not_verified,
                      "msrp_starting_not_exact": starting,
                      "non_msrp_type_rows": non_msrp,
                      "unverified_price": len(unverified),
                      "delta_vs_p110": {"exact_msrp_verified": exact_msrp - before["exact_msrp_verified"],
                                        "unverified_price": len(unverified) - before["unverified_price"]},
                      "new_captures": new_captures_count,
                      "per_oem": {b: (v["coverage_pct"], v["price_bound"],
                                      v["exact_msrp_verified"], v["unverified_price"])
                                  for b, v in sorted(per_oem.items())}},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
