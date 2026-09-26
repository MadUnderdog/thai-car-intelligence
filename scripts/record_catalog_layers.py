#!/usr/bin/env python3
"""Record P100 catalog-layer captures in the coverage registry (§93).

Reads the capture logs written by scripts/acquire_catalog_layers.py, verifies
each artifact + sidecar on disk (hash recomputed, never trusted from the log),
then adds the endpoint to the owning brand's captured_endpoints and re-derives
last_success_* from the promoted (ACQUISITION_VERIFIED + parsed) endpoint.

Registry invariants enforced afterwards (tests/test_registry_invariants.py):
  * every endpoint sha256 matches the bytes on disk
  * last_success_sha256 == promoted artifact sha, never a LEGACY artifact
  * last_success_at >= capture time of the promoted artifact
  * generated_at >= every last_success_at
"""
import glob
import hashlib
import json
import os
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO, "tests", "fixtures", "oem-artifacts")
REG_PATH = os.path.join(REPO, "audit", "coverage", "oem-registry.json")

# artifacts an adapter actually parses into staged rows in this work unit.
# Everything else captured by the wave is stored as evidence with parsed=False:
# §93 defines last_success_* as "last capture that PRODUCED PARSEABLE DATA".
PARSED_ARTIFACTS = {
    "nissan_all_grade_price.html",
    "mitsubishi_all_models_price.html",
    "lexus_price_list.html",
    "bmw_price_list.html",
}

# artifact filename prefix -> registry brand
BRAND_OF = {
    "nissan_": "Nissan",
    "mitsubishi_": "Mitsubishi",
    "lexus_": "Lexus",
    "bmw_": "BMW",
    "MINI_": "MINI",
    "kia_": "Kia",
    "isuzu_": "Isuzu",
    "mazda_": "Mazda",
    "mg_": "MG",
    "suzuki_": "Suzuki",
    "Suzuki_": "Suzuki",
    "Changan_": "Changan",
    "GWM_": "GWM",
}


def brand_for(filename):
    for prefix, brand in BRAND_OF.items():
        if filename.startswith(prefix):
            return brand
    return None


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _captured_at(artifact):
    sc = os.path.join(FIXTURE_DIR, artifact + ".prov.json")
    if not os.path.exists(sc):
        return None
    return json.load(open(sc, encoding="utf-8"))["captured_at"]


def main():
    reg = json.load(open(REG_PATH, encoding="utf-8"))
    by_brand = {b["brand"]: b for b in reg["brands"]}

    added, skipped, rejected = [], [], []
    for log in sorted(glob.glob(os.path.join(REPO, "audit", "coverage",
                                              "catalog_layers_*.json"))):
        data = json.load(open(log, encoding="utf-8"))
        for entry in data.get("captured", []):
            filename = entry["filename"]
            brand = brand_for(filename)
            path = os.path.join(FIXTURE_DIR, filename)
            if not brand or brand not in by_brand:
                skipped.append((filename, brand))
                continue
            if not os.path.exists(path) or not os.path.exists(path + ".prov.json"):
                rejected.append((filename, "missing artifact or sidecar"))
                continue
            sidecar = json.load(open(path + ".prov.json", encoding="utf-8"))
            if sidecar["provenance_state"] != "ACQUISITION_VERIFIED":
                rejected.append((filename, f"provenance {sidecar['provenance_state']}"))
                continue
            sha = _sha(path)
            if sha != sidecar["sha256"]:
                rejected.append((filename, "sha mismatch artifact vs sidecar"))
                continue
            if entry.get("sha256") and entry["sha256"] != sha:
                rejected.append((filename, "sha mismatch log vs artifact"))
                continue
            row = by_brand[brand]
            endpoints = row.setdefault("captured_endpoints", [])
            existing = [e for e in endpoints if e.get("artifact") == filename]
            is_parsed = filename in PARSED_ARTIFACTS
            layer_note = entry.get("note", "")
            record = {
                "url": sidecar["source_url"],
                "artifact": filename,
                "sha256": sha,
                "provenance_state": "ACQUISITION_VERIFIED",
                "parsed": is_parsed,
                "note": (f"P100 catalog layer ({entry.get('layer', 'capture')}): "
                         f"{layer_note}"
                         + ("" if is_parsed else " — captured as evidence, not parsed")),
            }
            if existing:
                existing[0].update(record)
            else:
                endpoints.append(record)
            added.append((brand, filename))

    now = datetime.now(timezone.utc).isoformat()
    # re-derive last_success_* for every brand we touched (and verify others)
    for row in reg["brands"]:
        promoted = [e for e in row.get("captured_endpoints", [])
                    if e.get("provenance_state") == "ACQUISITION_VERIFIED"
                    and e.get("parsed") is True and e.get("artifact")]
        if not promoted:
            continue
        promoted.sort(key=lambda e: _captured_at(e["artifact"]) or "", reverse=True)
        top = promoted[0]
        row["last_success_sha256"] = top["sha256"]
        row["last_success_at"] = _captured_at(top["artifact"])

    gen = datetime.fromisoformat(reg["generated_at"])
    latest = max((datetime.fromisoformat(r["last_success_at"])
                  for r in reg["brands"] if r.get("last_success_at")),
                 default=gen)
    if latest > gen:
        reg["generated_at"] = now
    else:
        reg["generated_at"] = max(reg["generated_at"], now)

    with open(REG_PATH, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)
    os.chmod(REG_PATH, 0o600)

    print(f"added/updated endpoints: {len(added)}")
    for b, a in added:
        print(f"  {b:14} {a}")
    if skipped:
        print(f"skipped (no brand mapping): {skipped}")
    if rejected:
        print(f"REJECTED: {rejected}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
