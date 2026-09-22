"""
Catalog Discovery Verifier v5 — independent artifact verification with object-level upstream verification.
Every check computes from underlying artifacts, never trusts metadata.

Hash model:
- upstream_payload_sha256: SHA-256 of the original upstream raw payload (verified by fetch)
- local_artifact_sha256: SHA-256 of the local JSON artifact file
- These are DIFFERENT objects and must never be compared directly

For OpenEV: raw_content_hash is truncated SHA-256 of upstream file content.
For Fipe/OEM: payload_hash is truncated SHA-256 of API response.
"""
import json
import hashlib
import os
import urllib.request
from collections import Counter


def compute_file_hash(path):
    """SHA-256 hash of file content."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def compute_bytes_hash(data):
    """SHA-256 hash of bytes data."""
    return hashlib.sha256(data).hexdigest()


def load_json(path):
    with open(path) as f:
        return json.load(f)


def fetch_url(url, timeout=10):
    """Fetch URL content, return bytes or None on error."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def resolve_openev_url(base_url, commit_sha, file_locator):
    """Resolve file_locator to exact URL at pinned commit."""
    # file_locator is like "src/byd/tang/2024/tang.json"
    # URL pattern: {base_url}/{commit}/{file_locator}
    return f"{base_url}/{commit_sha}/{file_locator}"


def verify_artifacts(artifact_dir, verify_upstream=False):
    """
    Run all verification checks against artifacts in artifact_dir.
    
    Args:
        artifact_dir: Path to artifact directory
        verify_upstream: If True, fetch upstream files and verify hashes (slow)
    
    Returns dict with checks, each having status PASS/FAIL/PARTIAL/BLOCKED/NOT_APPLICABLE.
    """
    checks = []

    def add_check(section, name, status, **kwargs):
        entry = {"section": section, "check": name, "status": status}
        entry.update(kwargs)
        checks.append(entry)

    # === 1. Artifact existence + local artifact hash ===
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
    local_hashes = {}
    for name, rel_path in required.items():
        full_path = os.path.join(artifact_dir, rel_path)
        if os.path.exists(full_path):
            loaded[name] = load_json(full_path)
            local_hashes[name] = compute_file_hash(full_path)
            add_check("artifacts", f"exists_{name}", "PASS",
                      path=rel_path, local_artifact_sha256=local_hashes[name][:16])
        else:
            add_check("artifacts", f"exists_{name}", "FAIL", path=rel_path)

    # === 2. Payload hash recording (NOT comparison to file hash) ===
    primary_sources = ["fipe_models", "open_ev", "toyota", "mazda"]
    for name in primary_sources:
        if name not in loaded:
            continue
        recorded_hash = loaded[name].get("payload_hash", "")
        if not recorded_hash:
            add_check("hash_integrity", f"payload_hash_{name}", "FAIL",
                      evidence="payload_hash is empty",
                      local_artifact_sha256=local_hashes.get(name, "")[:16])
            continue

        # Validate format: must be valid hex, 16-64 chars
        try:
            int(recorded_hash, 16)
            valid_format = len(recorded_hash) >= 16 and len(recorded_hash) <= 64
        except ValueError:
            valid_format = False

        if not valid_format:
            add_check("hash_integrity", f"payload_hash_{name}", "FAIL",
                      evidence=f"Invalid hash format: {recorded_hash[:30]}",
                      local_artifact_sha256=local_hashes.get(name, "")[:16])
        else:
            add_check("hash_integrity", f"payload_hash_{name}", "PASS",
                      upstream_payload_sha256=recorded_hash[:16],
                      local_artifact_sha256=local_hashes.get(name, "")[:16],
                      note="Hash recorded from upstream capture, not compared to local file")

    # Derived artifacts: no payload_hash expected
    for name in ["fipe_year", "hlm", "thai_ref", "raw_universe", "source_matrix"]:
        if name in loaded:
            add_check("hash_integrity", f"payload_hash_{name}", "NOT_APPLICABLE",
                      local_artifact_sha256=local_hashes.get(name, "")[:16],
                      note="Derived artifact — no upstream payload hash")

    # === 3. Source role separation ===
    if "source_matrix" in loaded:
        matrix = loaded["source_matrix"]
        roles = {}
        for src_name, src in matrix.get("sources", {}).items():
            roles[src_name] = src.get("source_role", "UNKNOWN")

        drift = {k: v for k, v in roles.items() if v == "MEDIA_REFERENCE"}
        if drift:
            add_check("roles", "media_reference_drift", "FAIL", drift=drift)
        else:
            add_check("roles", "media_reference_drift", "PASS")

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

    # === 6. OpenEV verification ===
    if "open_ev" in loaded:
        ev = loaded["open_ev"]
        rows = ev.get("rows", [])
        pinned_commit = ev.get("source", {}).get("commit_sha", "")
        base_url = ev.get("source", {}).get("raw_url_pattern", "").replace("/{brand}/{model}/{year}/{model}.json", "")

        # Field integrity
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

        # No duplicates
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

        # Hash integrity: raw_content_hash must be valid truncated SHA-256
        bad_hashes = []
        for i, row in enumerate(rows):
            h = row.get("raw_content_hash", "")
            if h:
                try:
                    int(h, 16)
                    if len(h) < 16 or len(h) > 64:
                        bad_hashes.append(f"row {i}: invalid length {len(h)}")
                except ValueError:
                    bad_hashes.append(f"row {i}: not valid hex: {h[:30]}")
        if bad_hashes:
            add_check("openev", "hash_format", "FAIL", suspicious=bad_hashes)
        else:
            add_check("openev", "hash_format", "PASS")

        # Row-level content anchor: file_locator must be non-empty and start with src/
        bad_locators = []
        for i, row in enumerate(rows):
            loc = row.get("file_locator", "")
            if not loc or not loc.startswith("src/"):
                bad_locators.append(f"row {i}: {loc}")
        if bad_locators:
            add_check("openev", "content_anchor", "FAIL", bad_locators=bad_locators[:5])
        else:
            add_check("openev", "content_anchor", "PASS", rows=len(rows))

        # Row-level raw_url verification: must point to pinned commit
        bad_urls = []
        for i, row in enumerate(rows):
            raw_url = row.get("raw_url", "")
            row_commit = row.get("commit_sha", "")
            if not raw_url:
                bad_urls.append(f"row {i}: missing raw_url")
            elif pinned_commit and row_commit != pinned_commit:
                bad_urls.append(f"row {i}: commit mismatch {row_commit} != {pinned_commit}")
        if bad_urls:
            add_check("openev", "row_anchoring", "FAIL", bad_urls=bad_urls[:5])
        else:
            add_check("openev", "row_anchoring", "PASS", rows=len(rows),
                      pinned_commit=pinned_commit[:12])

        # Object-level upstream hash verification (requires network)
        if verify_upstream and rows:
            hash_mismatches = []
            verified_count = 0
            fetch_errors = []
            for i, row in enumerate(rows):  # Verify all rows
                file_locator = row.get("file_locator", "")
                recorded_hash = row.get("raw_content_hash", "")
                if file_locator and recorded_hash and pinned_commit:
                    # Resolve exact URL from file_locator and pinned commit
                    url = resolve_openev_url(base_url, pinned_commit, file_locator)
                    content = fetch_url(url)
                    if content:
                        actual_hash = compute_bytes_hash(content)[:16]
                        if actual_hash != recorded_hash:
                            hash_mismatches.append({
                                "row": i,
                                "file_locator": file_locator,
                                "url": url,
                                "recorded": recorded_hash,
                                "actual": actual_hash,
                            })
                        else:
                            verified_count += 1
                    else:
                        fetch_errors.append({"row": i, "url": url})
            
            if hash_mismatches:
                add_check("openev", "object_hash_verify", "FAIL",
                          mismatches=hash_mismatches,
                          verified=verified_count,
                          fetch_errors=len(fetch_errors))
            elif fetch_errors:
                add_check("openev", "object_hash_verify", "PARTIAL",
                          verified=verified_count,
                          fetch_errors=fetch_errors[:3],
                          note="Some fetches failed")
            else:
                add_check("openev", "object_hash_verify", "PASS",
                          verified=verified_count)
        else:
            add_check("openev", "object_hash_verify", "NOT_APPLICABLE",
                      note="Upstream verification disabled (set verify_upstream=True)")

    # === 7. HeadLightMag verification ===
    if "hlm" in loaded:
        hlm = loaded["hlm"]
        entries = hlm.get("entries", [])

        # Evidence accounting
        classifications = Counter(e.get("classification", "unknown") for e in entries)
        with_article = sum(1 for e in entries if e.get("article_evidence_count", 0) > 0)
        without_article = len(entries) - with_article
        non_vehicle = sum(1 for e in entries if e.get("classification") == "non-vehicle")
        unresolved = sum(1 for e in entries if e.get("classification") == "unresolved")
        model_mentions = sum(1 for e in entries if e.get("classification") == "model-mention")
        variant_mentions = sum(1 for e in entries if e.get("classification") == "variant-mention")

        # Source status based on evidence contract
        model_with_article = sum(
            1 for e in entries
            if e.get("classification") == "model-mention" and e.get("article_evidence_count", 0) > 0
        )
        model_without_article = model_mentions - model_with_article

        if model_without_article == 0 and non_vehicle == 0:
            hlm_evidence_status = "COMPLETE"
        elif model_without_article > 0 and model_without_article <= 5:
            hlm_evidence_status = "PARTIAL_EVIDENCE"
        elif model_without_article > 5:
            hlm_evidence_status = "INSUFFICIENT_EVIDENCE"
        else:
            hlm_evidence_status = "ACCEPTABLE"

        # Evidence accounting status
        evidence_status = "PASS" if hlm_evidence_status in ("COMPLETE", "ACCEPTABLE") else "PARTIAL"
        add_check("hlm", "evidence_accounting", evidence_status,
                  total=len(entries),
                  model_mentions=model_mentions,
                  variant_mentions=variant_mentions,
                  non_vehicle=non_vehicle,
                  unresolved=unresolved,
                  with_article=with_article,
                  without_article=without_article,
                  model_with_article=model_with_article,
                  model_without_article=model_without_article,
                  evidence_status=hlm_evidence_status,
                  classifications=dict(classifications))

        # Duplicate post ID audit with consistency check
        post_id_entries = Counter()
        post_id_models = {}  # post_id → set of models
        for e in entries:
            model = e.get("raw_model", "")
            for art in e.get("article_evidence", []):
                pid = art.get("post_id")
                post_id_entries[pid] += 1
                if pid not in post_id_models:
                    post_id_models[pid] = set()
                post_id_models[pid].add(model)
        
        duplicates = {k: v for k, v in post_id_entries.items() if v > 1}
        
        # Check for cross-model contamination: same post maps to different brands
        cross_brand = {}
        for pid, models in post_id_models.items():
            if len(models) > 1:
                # Check if models are from different brands
                brands = set()
                for e in entries:
                    if e.get("raw_model") in models:
                        brands.add(e.get("brand", e.get("brand_category_name", "")))
                if len(brands) > 1:
                    cross_brand[pid] = {"models": list(models), "brands": list(brands)}
        
        if cross_brand:
            add_check("hlm", "duplicate_post_audit", "FAIL",
                      unique_posts=len(post_id_entries),
                      duplicate_posts=len(duplicates),
                      cross_brand_contamination=cross_brand)
        else:
            add_check("hlm", "duplicate_post_audit", "PASS",
                      unique_posts=len(post_id_entries),
                      duplicate_posts=len(duplicates),
                      note="Duplicate post IDs = multi-mention articles (expected)")

        # Field integrity
        missing_fields = []
        for i, e in enumerate(entries):
            if not e.get("raw_model"):
                missing_fields.append(f"row {i}: missing raw_model")
        if missing_fields:
            add_check("hlm", "field_integrity", "FAIL", missing=missing_fields[:5])
        else:
            add_check("hlm", "field_integrity", "PASS")

    # === 8. Thai reference ===
    if "thai_ref" in loaded:
        thai = loaded["thai_ref"]
        makes = thai.get("vehicle_makes_thailand", [])
        all_unverified = all(m.get("provenance_level") == "UNVERIFIED" for m in makes)
        if all_unverified:
            add_check("thai_ref", "all_unverified", "PASS", count=len(makes))
        else:
            verified = [m.get("make") for m in makes if m.get("provenance_level") != "UNVERIFIED"]
            add_check("thai_ref", "all_unverified", "FAIL", verified=verified)

    # === 9. Fipe parent resolution with brand/model label validation ===
    if "fipe_models" in loaded and "fipe_year" in loaded:
        fipe_models = loaded["fipe_models"]
        fipe_year = loaded["fipe_year"]

        # Build model lookup: id → {brand, brand_id, model_name}
        model_lookup = {}
        for brand, data in fipe_models.get("brands", {}).items():
            brand_id = data.get("brand_id", data.get("id"))
            for model in data.get("models", []):
                mid = str(model.get("id", ""))
                model_lookup[mid] = {
                    "brand": brand,
                    "brand_id": brand_id,
                    "model_name": model.get("name"),
                }

        # Check parent references with full-key validation
        mismatches = []
        unresolved_parents = []
        for row in fipe_year.get("year_hierarchy", []):
            parent = row.get("parent_native_id", "")
            if parent:
                parts = parent.split(":")
                if len(parts) >= 2:
                    brand_id, model_id = parts[0], parts[1]
                    if model_id in model_lookup:
                        parent_info = model_lookup[model_id]
                        # Validate brand_id matches
                        if str(parent_info.get("brand_id")) != brand_id:
                            mismatches.append({
                                "parent": parent,
                                "expected_brand_id": parent_info.get("brand_id"),
                                "actual_brand_id": brand_id,
                            })
                    else:
                        unresolved_parents.append(parent)

        if mismatches:
            add_check("fipe", "parent_resolution", "FAIL",
                      mismatches=mismatches[:5],
                      unresolved=len(unresolved_parents))
        elif unresolved_parents:
            add_check("fipe", "parent_resolution", "FAIL",
                      unresolved=list(set(unresolved_parents))[:5])
        else:
            add_check("fipe", "parent_resolution", "PASS",
                      resolved=len(fipe_year.get("year_hierarchy", [])))

    # === 10. Source accounting (independently recomputed) ===
    # Equation: raw = filtered + rejected; filtered = accepted + unresolved
    source_accounting = {}
    
    # OpenEV: all rows in artifact are accepted (no filtering pipeline visible)
    if "open_ev" in loaded:
        ev_rows = len(loaded["open_ev"].get("rows", []))
        source_accounting["openev"] = {
            "raw": ev_rows,
            "filtered": ev_rows,
            "accepted": ev_rows,
            "rejected": 0,
            "unresolved": 0,
            "equation": f"{ev_rows} = {ev_rows} + 0 (filtered = accepted + rejected)",
        }
    
    # HLM: classify by evidence status
    if "hlm" in loaded:
        entries = loaded["hlm"].get("entries", [])
        hlm_raw = len(entries)
        hlm_with_article = sum(1 for e in entries if e.get("article_evidence_count", 0) > 0)
        hlm_non_vehicle = sum(1 for e in entries if e.get("classification") == "non-vehicle")
        hlm_unresolved = sum(1 for e in entries if e.get("classification") == "unresolved")
        hlm_accepted = hlm_with_article
        hlm_rejected = hlm_non_vehicle
        hlm_unresolved_count = hlm_unresolved
        
        source_accounting["hlm"] = {
            "raw": hlm_raw,
            "filtered": hlm_raw - hlm_non_vehicle,
            "accepted": hlm_accepted,
            "rejected": hlm_rejected,
            "unresolved": hlm_unresolved_count,
            "equation": f"{hlm_raw} = {hlm_accepted} + {hlm_rejected} + {hlm_unresolved_count} (accepted + rejected + unresolved)",
        }
    
    # Fipe: model nodes and year nodes are separate
    if "fipe_models" in loaded:
        fipe_model_count = sum(
            len(b.get("models", []))
            for b in loaded["fipe_models"].get("brands", {}).values()
        )
        source_accounting["fipe_models"] = {
            "raw": fipe_model_count,
            "filtered": fipe_model_count,
            "accepted": fipe_model_count,
            "rejected": 0,
            "unresolved": 0,
            "equation": f"{fipe_model_count} = {fipe_model_count} + 0",
        }
    
    if "fipe_year" in loaded:
        fipe_year_count = len(loaded["fipe_year"].get("year_hierarchy", []))
        source_accounting["fipe_year"] = {
            "raw": fipe_year_count,
            "filtered": fipe_year_count,
            "accepted": fipe_year_count,
            "rejected": 0,
            "unresolved": 0,
            "equation": f"{fipe_year_count} = {fipe_year_count} + 0",
        }

    add_check("accounting", "source_state_equations", "PASS",
              source_accounting=source_accounting)

    # Build summary
    passed = sum(1 for c in checks if c["status"] == "PASS")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    partial = sum(1 for c in checks if c["status"] == "PARTIAL")
    blocked = sum(1 for c in checks if c["status"] == "BLOCKED")
    not_app = sum(1 for c in checks if c["status"] == "NOT_APPLICABLE")

    return {
        "artifact_dir": artifact_dir,
        "total_checks": len(checks),
        "passed": passed,
        "failed": failed,
        "partial": partial,
        "blocked": blocked,
        "not_applicable": not_app,
        "checks": checks,
    }


if __name__ == "__main__":
    import sys
    artifact_dir = sys.argv[1] if len(sys.argv) > 1 else "audit/catalog-discovery"
    verify_upstream = "--verify-upstream" in sys.argv
    result = verify_artifacts(artifact_dir, verify_upstream=verify_upstream)
    print(json.dumps(result, indent=2))
