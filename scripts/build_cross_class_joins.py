#!/usr/bin/env python3
"""Cross-source-class joins: the same model + field supported independently by
OEM_OFFICIAL and AUTOMOTIVE_MEDIA.

Every join keeps BOTH sides' own provenance — artifact SHA, locator, excerpt,
captured_at, source class, trust state — so a media figure can never lend its
locator (or its trust) to an official row, and vice versa.

A join is only emitted when the two classes agree on the exact figure for the
same normalized model. Nothing is inferred, no target count is chased.
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OFFICIAL = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
MEDIA = os.path.join(REPO, "audit", "data-staging", "media_observations.jsonl")
OUT = os.path.join(REPO, "audit", "data-staging", "cross_class_joins.json")


def side_official(r):
    loc = r.get("evidence_locator") or (r.get("evidence") or {}).get("evidence_locator") or {}
    src = r["source"]
    return {
        "observation_id": r.get("observation_id"),
        "source_class": "OEM_OFFICIAL",
        "trust_state": src["provenance_state"],
        "source_name": src.get("name"),
        "source_url": src.get("url") or (loc.get("url")),
        "artifact_path": src.get("artifact_path"),
        "artifact_sha256": src.get("artifact_sha256"),
        "captured_at": src.get("captured_at"),
        "locator": loc,
        "excerpt": r.get("evidence_excerpt"),
        "variant_raw": (r.get("identity") or {}).get("variant_raw"),
        "identity_scope": (r.get("identity") or {}).get("identity_scope"),
        "field": "price",
        "value_thb": r["price"]["value_thb"],
        "price_type": r["price"].get("type"),
    }


def side_media(r):
    loc = (r.get("evidence") or {}).get("locator") or {}
    src = r["source"]
    return {
        "observation_id": r["observation_id"],
        "source_class": r["source_class"],
        "trust_state": r["trust_state"],
        "source_name": src["name"],
        "source_url": src["url"],
        "artifact_path": src["artifact_path"],
        "artifact_sha256": src["artifact_sha256"],
        "captured_at": src["captured_at"],
        "locator": loc,
        "excerpt": (r.get("evidence") or {}).get("excerpt"),
        "variant_raw": (r.get("identity") or {}).get("variant_raw"),
        "identity_scope": (r.get("identity") or {}).get("identity_scope"),
        "field": "price",
        "value_thb": r["field"]["value_thb"],
        "price_type": r["field"].get("price_type"),
    }


def norm_variant(v):
    if not v:
        return ""
    return "".join(ch for ch in v.lower() if ch.isalnum())


def variant_alignment(a, b):
    na, nb = norm_variant(a), norm_variant(b)
    if not na or not nb:
        return "unscoped"
    if na == nb:
        return "exact"
    if na in nb or nb in na:
        return "substring"
    return "none"


def main() -> int:
    official = [json.loads(l) for l in open(OFFICIAL, encoding="utf-8")]
    media = [json.loads(l) for l in open(MEDIA, encoding="utf-8")]

    by_official = {}
    for r in official:
        key = (r["identity"]["brand_normalized"], r["identity"]["model_normalized"])
        by_official.setdefault(key, []).append(r)

    joins = []
    for m in media:
        key = (m["identity"]["brand_normalized"], m["identity"]["model_normalized"])
        for o in by_official.get(key, []):
            if o["price"]["value_thb"] != m["field"]["value_thb"]:
                continue
            so, sm = side_official(o), side_media(m)
            # both sides must be independently evidenced
            if not so["locator"] or not sm["locator"]:
                continue
            if not so["excerpt"] or not sm["excerpt"]:
                continue
            if not so["artifact_sha256"] or not sm["artifact_sha256"]:
                continue
            joins.append({
                "join_key": f"{key[0]}/{key[1]}/{so['value_thb']}",
                "model": {"brand": key[0], "normalized": key[1],
                          "official_name": o["identity"]["model_raw"],
                          "media_name": m["identity"]["model_raw"]},
                "field": "price",
                "value_thb": so["value_thb"],
                "classes": ["OEM_OFFICIAL", "AUTOMOTIVE_MEDIA"],
                "variant_alignment": variant_alignment(so["variant_raw"], sm["variant_raw"]),
                "official": so,
                "media": sm,
            })

    # stable ordering + dedupe on join_key
    joins.sort(key=lambda j: (j["model"]["brand"], j["model"]["normalized"], j["value_thb"]))
    seen, unique = set(), []
    for j in joins:
        if j["join_key"] in seen:
            continue
        seen.add(j["join_key"])
        unique.append(j)

    out = {
        "purpose": "cross-source-class corroboration; media never promotes to official",
        "generated_by": "scripts/build_cross_class_joins.py",
        "official_file": "audit/data-staging/vehicle_observations.jsonl",
        "media_file": "audit/data-staging/media_observations.jsonl",
        "join_rule": "same brand_normalized+model_normalized and exact price value, "
                     "both sides independently evidenced (artifact SHA + locator + excerpt)",
        "join_count": len(unique),
        "by_class_pair": {},
        "joins": unique,
    }
    for j in unique:
        pair = "+".join(j["classes"])
        out["by_class_pair"][pair] = out["by_class_pair"].get(pair, 0) + 1

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({"join_count": out["join_count"],
                      "by_class_pair": out["by_class_pair"],
                      "models": sorted({j["join_key"].rsplit("/", 1)[0] for j in unique}),
                      "variant_alignment": {k: sum(1 for j in unique if j["variant_alignment"] == k)
                                            for k in ("exact", "substring", "none", "unscoped")}},
                     ensure_ascii=False, indent=2))
    return 0 if unique else 1


if __name__ == "__main__":
    raise SystemExit(main())
