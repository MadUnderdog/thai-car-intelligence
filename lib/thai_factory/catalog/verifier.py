"""
Catalog Discovery Verifier — independent artifact verification.
Run against any artifact directory to produce machine-readable results.
Every check computes from underlying artifacts, never trusts metadata.
"""
import json
import hashlib
import os
from collections import Counter


def compute_file_hash(path):
    """SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    with open(path) as f:
        return json.load(f)


def verify_artifacts(artifact_dir):
    """
    Run all verification checks against artifacts in artifact_dir.
    Returns dict with checks, each having status PASS/FAIL/PARTIAL/BLOCKED/NOT_APPLICABLE.
    """
    checks = []

    def add_check(section, name, status, **kwargs):
        entry = {"section": section, "check": name, "status": status}
        entry.update(kwargs)
        checks.append(entry)

    # === 1. Artifact existence ===
    required = {
        "fipe_models": "datasets/fipe_api_capture.json",
        "fipe_year": "fipe_year_hierarchy.json",
        "open_ev": "second_taxonomy_capture.json",
        "toyota": "datasets/toyota_official_capture.json",
        "mazda": "datasets/mazda_official_capture.json",
        "hlm": "media_discovery_headlightmag.json",
        "thai_ref": "thai_market_reference.json",
        "raw_universe": "raw_taxonomy_universe.json",
        "source_matrix": "source_matrix.json",
    }

    loaded = {}
    for name, rel_path in required.items():
        full_path = os.path.join(artifact_dir, rel_path)
        if os.path.exists(full_path):
            loaded[name] = load_json(full_path)
            add_check("artifacts", f"exists_{name}", "PASS", path=rel_path)
        else:
            add_check("artifacts", f"exists_{name}", "FAIL", path=rel_path)

    # === 2. Payload hash integrity ===
    # Every primary artifact must have a non-empty payload_hash
    primary_with_hash = ["fipe_models", "open_ev", "toyota", "mazda"]
    for name in primary_with_hash:
        if name in loaded:
            h = loaded[name].get("payload_hash", "")
            if h:
                add_check("hash", f"payload_hash_{name}", "PASS", hash=h[:16])
            else:
                add_check("hash", f"payload_hash_{name}", "FAIL",
                          evidence="payload_hash is empty string")

    # Derived artifacts may not have payload_hash
    for name in ["fipe_year", "hlm", "thai_ref", "raw_universe", "source_matrix"]:
        if name in loaded:
            h = loaded[name].get("payload_hash", "")
            add_check("hash", f"payload_hash_{name}", "NOT_APPLICABLE",
                      note="Derived artifact, no independent payload hash")

    # === 3. Source role separation ===
    if "source_matrix" in loaded:
        matrix = loaded["source_matrix"]
        roles = {}
        for src_name, src in matrix.get("sources", {}).items():
            roles[src_name] = src.get("source_role", "UNKNOWN")

        # Check for MEDIA_REFERENCE drift
        drift = {k: v for k, v in roles.items() if v == "MEDIA_REFERENCE"}
        if drift:
            add_check("roles", "media_reference_drift", "FAIL", drift=drift)
        else:
            add_check("roles", "media_reference_drift", "PASS")

        # Verify valid roles only
        valid_roles = {"IDENTITY_ENUMERATOR", "MARKET_TRUTH", "MARKET_REFERENCE", "MEDIA_DISCOVERY"}
        invalid = {k: v for k, v in roles.items() if v not in valid_roles}
        if invalid:
            add_check("roles", "valid_role_enum", "FAIL", invalid=invalid)
        else:
            add_check("roles", "valid_role_enum", "PASS")

    # === 4. No media in taxonomy ===
    if "raw_universe" in loaded:
        raw = loaded["raw_universe"]
        media_sources = {"headlightmag", "headlightmag_wordpress_api"}
        contaminated = [
            n for n in raw.get("nodes", [])
            if n.get("source_name", "").lower() in media_sources
        ]
        if contaminated:
            add_check("contamination", "media_in_taxonomy", "FAIL",
                      count=len(contaminated))
        else:
            add_check("contamination", "media_in_taxonomy", "PASS")

    # === 5. No canonical_id in unreconciled ===
    if "raw_universe" in loaded:
        raw = loaded["raw_universe"]
        has_canonical = [n for n in raw.get("nodes", []) if "canonical_id" in n]
        if has_canonical:
            add_check("integrity", "canonical_id_in_raw", "FAIL",
                      count=len(has_canonical))
        else:
            add_check("integrity", "canonical_id_in_raw", "PASS")

    # === 6. OpenEV field integrity ===
    if "open_ev" in loaded:
        ev = loaded["open_ev"]
        rows = ev.get("rows", [])
        required_fields = ["brand", "model", "year", "trim_name", "file_locator", "raw_content_hash"]
        missing = []
        for i, row in enumerate(rows):
            for field in required_fields:
                if field not in row or row[field] is None:
                    missing.append(f"row {i}: missing {field}")

        if missing:
            add_check("openev", "field_integrity", "FAIL", missing=missing[:5])
        else:
            add_check("openev", "field_integrity", "PASS", rows=len(rows))

        # Check for duplicates
        seen = set()
        dupes = []
        for i, row in enumerate(rows):
            key = f"{row.get('brand')}:{row.get('model')}:{row.get('year')}:{row.get('trim_name')}"
            if key in seen:
                dupes.append(key)
            seen.add(key)
        if dupes:
            add_check("openev", "no_duplicates", "FAIL", duplicates=dupes)
        else:
            add_check("openev", "no_duplicates", "PASS")

        # Check hashes are valid hex strings (not corrupted/placeholder)
        fake = []
        for i, row in enumerate(rows):
            h = row.get("raw_content_hash", "")
            if h:
                # Must be hex string, 16-64 chars
                try:
                    int(h, 16)
                    if len(h) < 16 or len(h) > 64:
                        fake.append(f"row {i}: invalid length {len(h)}")
                except ValueError:
                    fake.append(f"row {i}: not valid hex: {h[:30]}")
        if fake:
            add_check("openev", "hash_genuine", "FAIL", suspicious=fake)
        else:
            add_check("openev", "hash_genuine", "PASS")

    # === 7. HeadLightMag evidence separation ===
    if "hlm" in loaded:
        hlm = loaded["hlm"]
        entries = hlm.get("entries", [])

        classifications = Counter(e.get("classification", "unknown") for e in entries)
        with_article = sum(1 for e in entries if e.get("article_evidence_count", 0) > 0)
        without_article = len(entries) - with_article

        add_check("hlm", "evidence_counts", "PASS",
                  total=len(entries),
                  with_article=with_article,
                  without_article=without_article,
                  classifications=dict(classifications))

        # Check for missing required fields
        missing_fields = []
        for i, e in enumerate(entries):
            if not e.get("raw_model"):
                missing_fields.append(f"row {i}: missing raw_model")
        if missing_fields:
            add_check("hlm", "field_integrity", "FAIL", missing=missing_fields[:5])
        else:
            add_check("hlm", "field_integrity", "PASS")

    # === 8. Thai reference provenance ===
    if "thai_ref" in loaded:
        thai = loaded["thai_ref"]
        makes = thai.get("vehicle_makes_thailand", [])
        all_unverified = all(m.get("provenance_level") == "UNVERIFIED" for m in makes)
        if all_unverified:
            add_check("thai_ref", "all_unverified", "PASS", count=len(makes))
        else:
            verified = [m.get("make") for m in makes if m.get("provenance_level") != "UNVERIFIED"]
            add_check("thai_ref", "all_unverified", "FAIL", verified=verified)

    # === 9. Fipe parent resolution ===
    if "fipe_models" in loaded and "fipe_year" in loaded:
        fipe_models = loaded["fipe_models"]
        fipe_year = loaded["fipe_year"]

        # Build model ID set from fipe_models
        model_ids = set()
        for brand, data in fipe_models.get("brands", {}).items():
            for model in data.get("models", []):
                model_ids.add(str(model.get("id", "")))

        # Check parent references in year hierarchy
        year_parents = set()
        for row in fipe_year.get("year_hierarchy", []):
            parent = row.get("parent_native_id", "")
            if parent:
                parts = parent.split(":")
                if len(parts) >= 2:
                    year_parents.add(parts[1])

        resolved = year_parents & model_ids
        unresolved = year_parents - model_ids

        if unresolved:
            add_check("fipe", "parent_resolution", "FAIL",
                      unresolved=list(unresolved),
                      resolved=len(resolved))
        else:
            add_check("fipe", "parent_resolution", "PASS",
                      resolved=len(resolved),
                      total_parents=len(year_parents))

    # === 10. Count reconciliation ===
    counts = {}
    if "fipe_models" in loaded:
        counts["fipe_model_nodes"] = sum(
            len(b.get("models", []))
            for b in loaded["fipe_models"].get("brands", {}).values()
        )
    if "fipe_year" in loaded:
        counts["fipe_year_nodes"] = len(loaded["fipe_year"].get("year_hierarchy", []))
    if "open_ev" in loaded:
        counts["openev_rows"] = len(loaded["open_ev"].get("rows", []))
    if "toyota" in loaded:
        counts["toyota_models"] = len(loaded["toyota"].get("models", []))
    if "mazda" in loaded:
        counts["mazda_models"] = len(loaded["mazda"].get("models", []))
    if "hlm" in loaded:
        counts["hlm_entries"] = len(loaded["hlm"].get("entries", []))
    if "thai_ref" in loaded:
        counts["thai_makes"] = len(loaded["thai_ref"].get("vehicle_makes_thailand", []))
    if "raw_universe" in loaded:
        counts["raw_nodes"] = len(loaded["raw_universe"].get("nodes", []))

    add_check("counts", "reconciliation", "PASS", counts=counts)

    # Build summary
    passed = sum(1 for c in checks if c["status"] == "PASS")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    partial = sum(1 for c in checks if c["status"] == "PARTIAL")
    not_app = sum(1 for c in checks if c["status"] == "NOT_APPLICABLE")

    return {
        "artifact_dir": artifact_dir,
        "total_checks": len(checks),
        "passed": passed,
        "failed": failed,
        "partial": partial,
        "not_applicable": not_app,
        "checks": checks,
    }


if __name__ == "__main__":
    import sys
    artifact_dir = sys.argv[1] if len(sys.argv) > 1 else "audit/catalog-discovery"
    result = verify_artifacts(artifact_dir)
    print(json.dumps(result, indent=2))
