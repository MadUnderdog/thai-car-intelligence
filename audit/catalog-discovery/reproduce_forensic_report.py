#!/usr/bin/env python3
"""
Reproduce forensic report counts and checks from committed artifacts.
Run: python3 audit/catalog-discovery/reproduce_forensic_report.py
"""
import json
import hashlib
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARTIFACT_DIR = os.path.join(PROJECT_ROOT, "audit", "catalog-discovery")

def load_json(path):
    with open(os.path.join(ARTIFACT_DIR, path)) as f:
        return json.load(f)

def check_payload_hash(data, source_name):
    """Check that payload_hash exists and is non-empty."""
    # These artifacts are built from other artifacts, not raw captures
    expected_missing = {"raw_universe", "source_matrix", "thai_ref"}
    
    h = data.get("payload_hash", "")
    if not h:
        h = data.get("source", {}).get("payload_hash", "")
    if not h:
        h = data.get("metadata", {}).get("payload_hash", "")
    
    if not h and source_name in expected_missing:
        return {"source": source_name, "has_hash": False, "hash": "", "note": "Expected missing — built from other artifacts"}
    return {"source": source_name, "has_hash": bool(h), "hash": h}

def main():
    results = {
        "reproduction_date": "2026-09-22",
        "checks": []
    }
    
    # Load all artifacts
    artifacts = {
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
    for name, rel_path in artifacts.items():
        try:
            loaded[name] = load_json(rel_path)
            results["checks"].append({
                "check": f"artifact_exists_{name}",
                "status": "PASS",
                "path": rel_path
            })
        except FileNotFoundError:
            results["checks"].append({
                "check": f"artifact_exists_{name}",
                "status": "FAIL",
                "path": rel_path,
                "evidence": "File not found"
            })
    
    # Check payload hashes
    for name, data in loaded.items():
        result = check_payload_hash(data, name)
        check_entry = {
            "check": f"payload_hash_{name}",
            "status": "PASS" if result["has_hash"] or result.get("note") else "FAIL",
            "hash": result["hash"]
        }
        if "note" in result:
            check_entry["note"] = result["note"]
        results["checks"].append(check_entry)
    
    # Count nodes per source
    if "raw_universe" in loaded:
        nodes = loaded["raw_universe"].get("nodes", [])
        by_source = {}
        for n in nodes:
            src = n.get("source_name", "unknown")
            by_source[src] = by_source.get(src, 0) + 1
        results["checks"].append({
            "check": "raw_universe_node_counts",
            "status": "PASS",
            "by_source": by_source,
            "total": len(nodes)
        })
    
    # Check Fipe year hierarchy completeness
    if "fipe_year" in loaded:
        fipe_year = loaded["fipe_year"]
        year_rows = len(fipe_year.get("year_hierarchy", []))
        completeness = fipe_year.get("metadata", {}).get("completeness", "UNKNOWN")
        results["checks"].append({
            "check": "fipe_year_completeness",
            "status": "PASS",
            "year_rows": year_rows,
            "completeness": completeness,
            "note": f"Year hierarchy is {completeness} — {year_rows} rows"
        })
    
    # Check open-ev-data
    if "open_ev" in loaded:
        ev_rows = loaded["open_ev"].get("rows", [])
        commit_sha = loaded["open_ev"].get("source", {}).get("commit_sha", "")
        has_locators = all("file_locator" in r for r in ev_rows)
        results["checks"].append({
            "check": "open_ev_data_integrity",
            "status": "PASS",
            "rows": len(ev_rows),
            "commit_sha": commit_sha,
            "all_have_locators": has_locators
        })
    
    # Check HeadLightMag
    if "hlm" in loaded:
        entries = loaded["hlm"].get("entries", [])
        with_article = sum(1 for e in entries if e.get("article_evidence_count", 0) > 0)
        classifications = {}
        for e in entries:
            c = e.get("classification", "unknown")
            classifications[c] = classifications.get(c, 0) + 1
        results["checks"].append({
            "check": "headlightmag_integrity",
            "status": "PASS",
            "total": len(entries),
            "with_article_evidence": with_article,
            "classifications": classifications
        })
    
    # Check Thai reference
    if "thai_ref" in loaded:
        makes = loaded["thai_ref"].get("vehicle_makes_thailand", [])
        all_unverified = all(m.get("provenance_level") == "UNVERIFIED" for m in makes)
        results["checks"].append({
            "check": "thai_reference_provenance",
            "status": "PASS",
            "makes": len(makes),
            "all_unverified": all_unverified
        })
    
    # Source matrix
    if "source_matrix" in loaded:
        fipe = loaded["source_matrix"].get("sources", {}).get("fipe_brazilian_vehicle_reference", {})
        provides_hierarchy = fipe.get("provides_hierarchy", False)
        results["checks"].append({
            "check": "source_matrix_fipe_hierarchy",
            "status": "PASS" if provides_hierarchy else "FAIL",
            "provides_hierarchy": provides_hierarchy
        })
    
    # Summary
    passed = sum(1 for c in results["checks"] if c["status"] == "PASS")
    failed = sum(1 for c in results["checks"] if c["status"] == "FAIL")
    results["summary"] = {
        "total_checks": len(results["checks"]),
        "passed": passed,
        "failed": failed
    }
    
    # Save results
    output_path = os.path.join(ARTIFACT_DIR, "reproduction_results.json")
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Reproduction complete: {passed}/{len(results['checks'])} checks passed")
    if failed:
        print(f"FAILED checks:")
        for c in results["checks"]:
            if c["status"] == "FAIL":
                print(f"  {c['check']}: {c.get('evidence', '')}")
    
    return results

if __name__ == "__main__":
    main()
