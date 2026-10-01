#!/usr/bin/env python3
"""Rebuild audit/data-staging/multi_source_joins.json from staging.

Deliberately re-derives every join from `vehicle_observations.jsonl` — the file
is a computed artifact, never hand-edited, so `tests/test_p98_semantic_audit.
test_joins_artifact_recomputes_exactly` can always reproduce it.

Join rule (unchanged): the same (brand_normalized, model_normalized, price_thb)
must be published by >= 2 DISTINCT captured artifacts. No inferred joins, no
third-party corroboration, every supporting record must be ACQUISITION_VERIFIED.
"""
import collections
import json
import os
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
OUT = os.path.join(REPO, "audit", "data-staging", "multi_source_joins.json")
FIXTURE_DIR = os.path.join(REPO, "tests", "fixtures", "oem-artifacts")

SIDE_CACHE = {}


def _sidecar(artifact_path):
    if artifact_path in SIDE_CACHE:
        return SIDE_CACHE[artifact_path]
    p = artifact_path if os.path.isabs(artifact_path) else os.path.join(REPO, artifact_path)
    sc = p + ".prov.json"
    data = json.load(open(sc, encoding="utf-8")) if os.path.exists(sc) else {}
    SIDE_CACHE[artifact_path] = data
    return data


def _level(r):
    return r["identity"].get("identity_level") or r["identity"].get("level")


def _ptype(r):
    return r["price"].get("type") or r["price"].get("price_type")


def _oid(r):
    return r.get("observation_id")


def _loc(r):
    if r.get("evidence_locator"):
        return r["evidence_locator"]
    return (r.get("evidence") or {}).get("evidence_locator") or {}


def main():
    rows = [json.loads(l) for l in open(STAGING, encoding="utf-8") if l.strip()]

    groups = collections.defaultdict(list)
    for r in rows:
        i = r["identity"]
        groups[(i.get("brand_normalized"), i.get("model_normalized"),
                r["price"].get("value_thb"))].append(r)

    joins = []
    for (brand, model, price), members in groups.items():
        artifacts = {m["source"]["artifact_path"] for m in members}
        if len(artifacts) < 2:
            continue
        members = [m for m in members
                   if m["source"].get("provenance_state") == "ACQUISITION_VERIFIED"]
        artifacts = {m["source"]["artifact_path"] for m in members}
        if len(artifacts) < 2:
            continue

        ptypes = sorted({_ptype(m) for m in members})
        levels = sorted({_level(m) for m in members})
        if len(levels) > 1:
            note = ("levels differ: one source prices the model, the other prices "
                    "a named variant at the same figure — consistent, not conflicting")
        else:
            note = f"identity level {levels[0]} across every supporting artifact"
        if len(ptypes) > 1:
            note += ("; publication framing differs (" + ", ".join(ptypes) +
                     ") while the figure itself is identical")

        supports = []
        for m in sorted(members, key=lambda x: _oid(x) or ""):
            art = m["source"]["artifact_path"]
            sc = _sidecar(art)
            loc = _loc(m)
            supports.append({
                "observation_id": _oid(m),
                "source_name": m["source"]["name"],
                "source_url": m["source"].get("url"),
                "artifact_path": art,
                "artifact_sha256": m["source"].get("artifact_sha256"),
                "captured_at": sc.get("captured_at"),
                "provenance_state": m["source"].get("provenance_state"),
                "source_class": m["source"].get("class"),
                "identity_level": _level(m),
                "model_raw": m["identity"].get("model_raw"),
                "variant_raw": m["identity"].get("variant_raw"),
                "price_type": _ptype(m),
                "price_thb": m["price"].get("value_thb"),
                "locator": {
                    "artifact_path": loc.get("artifact_path", art),
                    "selector": loc.get("selector"),
                    "method": loc.get("method"),
                },
                "evidence_excerpt": m.get("evidence_excerpt", ""),
            })

        joins.append({
            "join_key": {"brand": brand, "model": model, "price_thb": price},
            "field_agreement": {
                "price_thb": "AGREE",
                "price_types": ptypes,
                "identity_levels": levels,
                "note": note,
            },
            "support_count": len(supports),
            "distinct_artifacts": len(artifacts),
            "distinct_urls": len({s["source_url"] for s in supports}),
            "supporting_records": supports,
        })

    joins.sort(key=lambda j: (j["join_key"]["brand"], j["join_key"]["model"],
                              j["join_key"]["price_thb"]))
    classes = sorted({r["source"].get("class") for r in rows})
    if classes == ["OEM_OFFICIAL"]:
        caveat = ("all staged rows are class OEM_OFFICIAL — there is currently NO "
                  "second source class in staging, so >=2 independent source classes "
                  "is not achievable yet; these joins are cross-ARTIFACT (independent "
                  "official pages) rather than cross-class")
    else:
        caveat = ("source classes present: " + ", ".join(classes) +
                  "; joins below are cross-ARTIFACT unless a join_key is supported "
                  "by rows of different source_class")

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "staged_rows": len(rows),
        "join_rule": "same (brand_normalized, model_normalized, price_thb) supported "
                     "by >=2 DISTINCT captured artifacts, each ACQUISITION_VERIFIED; "
                     "no inferred joins",
        "source_classes_present_in_staging": classes,
        "source_class_caveat": caveat,
        "distinct_source_urls": len({r["source"].get("url") for r in rows}),
        "join_count": len(joins),
        "target_was": ">=10 examples only when evidence genuinely supports them",
        "joins": joins,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"staged_rows={len(rows)} joins={len(joins)} -> {OUT}")
    for j in joins:
        print(f"  {j['join_key']} x{j['support_count']} "
              f"({j['distinct_artifacts']} artifacts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
