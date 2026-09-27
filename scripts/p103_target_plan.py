#!/usr/bin/env python3
"""P103 — machine-readable first-party catalog target plan.

Reads the accepted P102 identity matrix and emits the acquisition/reconciliation
targets for this wave BEFORE anything is harvested.  Every target carries the
measured deficit it exists to close, so later metrics cannot be re-derived from
whatever happened to be collected.

Rules honoured here (P103 work order §2):
  * reachable official access first; blocked hosts are listed with their exact
    blocker and `next_retry_at`, and are never targeted for a request
  * deficit = official first-party gap, never "candidate rows we could add"
  * identity levels are named per target (MODEL / VARIANT) so a loader that
    cannot publish that level is not silently used
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATRIX = os.path.join(REPO, "audit/coverage/identity_matrix_p102.json")
FINAL = os.path.join(REPO, "audit/coverage/p102_final_result.json")
REGISTRY = os.path.join(REPO, "audit/coverage/oem-registry.json")
OUT = os.path.join(REPO, "audit/coverage/p103_target_plan.json")

# Order of the first-party acquisition ladder (P103 work order §3).
LADDER = ["lineup_index", "model_pages", "grade_variant_pages",
          "brochure_pdf", "structured_payload", "press_release"]

# Official surfaces already captured in tests/fixtures/oem-artifacts with a
# .prov.json sidecar — these are reused bytes, never re-fetched.
EXISTING_OFFICIAL = {
    "Mazda": ["mazda_car_mazda-cx5.html", "mazda_car_mazda2-essential.html",
              "mazda_car_mazda3-sedan.html", "mazda_car_mazda-cx30-essential.html",
              "mazda_car_new-mazda-bt50.html"],
    "MG": ["mg_home_page.html", "mg_models_page.html"],
    "Isuzu": ["isuzu_page.html", "isuzu_th_home_page.html"],
    "Subaru": ["subaru_th_home_page.html"],
    "Toyota": ["toyota_pricelist_page.html", "toyota_model_page.html"],
    "Honda": ["honda_models_page.html", "honda_city_recapture.html"],
    "BMW": ["bmw_price_list.html", "bmw_configurator_3series.html",
            "bmw_all_models_verified.html"],
    "GWM": ["gwm_th_model_tank-300.html", "gwm_th_model_ora-5-ev.html"],
    "Mitsubishi": ["mitsubishi_all_models_price.html"],
    "Nissan": ["nissan_all_grade_price.html", "nissan_all_models.html"],
    "Changan": ["changan_lumin_page.html", "changan_nevo_q05_page.html"],
    "Lexus": ["lexus_price_list.html", "lexus_models_page.html"],
    "MINI": ["MINI_PriceSheet_20260327.pdf.b64",
             "MINI_configurator_model_ranges.html"],
    "Porsche": ["porsche_home_page.html", "porsche_macan_model_page.html"],
    "Suzuki": ["suzuki_models_page.html", "suzuki_fronx_equipment.html"],
    "Land Rover": ["TH_LandRover_PriceSheet.pdf.b64",
                   "landrover_range_rover_page.html"],
}


def main() -> int:
    matrix = json.load(open(MATRIX, encoding="utf-8"))
    final = json.load(open(FINAL, encoding="utf-8"))
    registry = json.load(open(REGISTRY, encoding="utf-8"))

    by_brand = {e["brand"]: e for e in matrix["oems"]}
    baseline = {e["brand"]: e["identity"] for e in matrix["oems"]}

    targets, blocked = [], []
    for brand, ident in sorted(baseline.items()):
        entry = by_brand[brand]
        status = entry["official_access_status"]
        cand_m = ident.get("model_candidates_discovered") or 0
        cand_v = ident.get("variant_candidates_discovered") or 0
        conf_m = ident.get("first_party_confirmed_models") or 0
        conf_v = ident.get("first_party_confirmed_variants") or 0
        row = {
            "brand": brand,
            "official_access_status": status,
            "candidate_models": cand_m,
            "candidate_variants": cand_v,
            "first_party_confirmed_models": conf_m,
            "first_party_confirmed_variants": conf_v,
            "model_deficit_vs_candidates": max(cand_m - conf_m, 0),
            "variant_deficit_vs_candidates": max(cand_v - conf_v, 0),
            "reusable_official_artifacts": EXISTING_OFFICIAL.get(brand, []),
        }
        if status != "REACHABLE":
            row["blockers"] = [
                {"layer": b["layer"], "blocker": b["blocker"],
                 "detail": b.get("detail", ""),
                 "next_retry_at": b.get("next_retry_at")}
                for b in entry.get("blockers", [])
            ]
            row["targeted_this_wave"] = False
            row["reason_not_targeted"] = (
                "official host is not reachable; no request before "
                "next_retry_at, and secondary enumerators stay discovery-only")
            blocked.append(row)
            continue

        gaps = []
        if conf_v == 0 and cand_v > 0:
            gaps.append("VARIANT")
        if conf_m == 0 and cand_m > 0:
            gaps.append("MODEL")
        if conf_v and conf_v < cand_v:
            gaps.append("VARIANT")
        if conf_m and conf_m < cand_m:
            gaps.append("MODEL")
        # de-duplicate, keep order
        gaps = list(dict.fromkeys(gaps))
        row["identity_levels_targeted"] = gaps
        row["targeted_this_wave"] = bool(gaps)
        if not gaps:
            row["reason_not_targeted"] = (
                "every candidate identity already first-party confirmed")
        row["acquisition_ladder"] = LADDER
        targets.append(row)

    # Work order §6 — explicit priority list, ordered by the size of the hole.
    priority = ["Mazda", "MG", "Subaru", "Isuzu", "BMW", "Toyota", "Honda",
                "GWM", "Mitsubishi", "Nissan", "Changan", "Lexus", "MINI",
                "Porsche", "Suzuki", "Land Rover"]
    reachable_targeted = {t["brand"] for t in targets if t["targeted_this_wave"]}
    ordered = [b for b in priority if b in reachable_targeted]
    ordered += sorted(reachable_targeted - set(ordered),
                      key=lambda b: -(next(t for t in targets if t["brand"] == b)
                                      ["variant_deficit_vs_candidates"]))

    plan = {
        "artifact": "p103_target_plan/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_artifact": "audit/coverage/p102_final_result.json",
        "baseline_sha": None,
        "baseline": {
            "in_scope_oems": len(matrix["oems"]),
            "oems_with_first_party_confirmation": sum(
                1 for e in matrix["oems"]
                if (e["identity"].get("first_party_confirmed_models") or 0) > 0),
            "first_party_confirmed_models": final["first_party_confirmed_models"],
            "first_party_confirmed_variants": final["first_party_confirmed_variants"],
            "candidate_models": final["enumerator_candidates"]["models"],
            "candidate_variants": final["enumerator_candidates"]["variants"],
            "identity_only_records": final["identity_only_candidates"][
                "records_with_identity_only_status"],
        },
        "rules": [
            "first-party identity coverage is the objective; price collection is not",
            "a MODEL-only official source may only produce MODEL evidence",
            "a grade/variant official source may only produce VARIANT evidence",
            "blocked hosts are never requested before next_retry_at",
            "identity-only candidates are never promoted into staging or the "
            "accepted/production set",
            "reuse captured bytes (AcquisitionWriter artifacts + .prov.json) "
            "before fetching anything new",
        ],
        "acquisition_ladder": LADDER,
        "attack_order": ordered,
        "targets": [t for t in targets if t["targeted_this_wave"]],
        "not_targeted": [t for t in targets if not t["targeted_this_wave"]],
        "blocked_oems": blocked,
        "registry_retry_windows": {
            b: {"access_status": v.get("access_status"),
                "next_retry_at": v.get("next_retry_at")}
            for b, v in (registry.get("oems") or registry).items()
            if isinstance(v, dict) and v.get("access_status") != "REACHABLE"
        } if isinstance(registry.get("oems") or registry, dict) else {},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {OUT}")
    print(f"targets={len(plan['targets'])} blocked={len(blocked)} "
          f"attack_order={len(ordered)}")
    for t in plan["targets"]:
        print(f"  {t['brand']:12s} {t['identity_levels_targeted']} "
              f"model_deficit={t['model_deficit_vs_candidates']} "
              f"variant_deficit={t['variant_deficit_vs_candidates']} "
              f"reuse={len(t['reusable_official_artifacts'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
