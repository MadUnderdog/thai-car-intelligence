#!/usr/bin/env python3
"""
Integration tests: source-role separation and artifact integrity.

Validates that taxonomy artifacts in audit/catalog-discovery/ maintain
provenance contracts — no synthetic IDs, no fake edges, no ungrounded
decomposition, no payload-hash gaps, no phantom canonical IDs, and
taxonomy counts that account for media sources.
"""
import json
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest

# ── paths ──────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent
ARTIFACTS = BASE / "audit" / "catalog-discovery"
DATASETS = ARTIFACTS / "datasets"

RAW_TAXONOMY = ARTIFACTS / "raw_taxonomy_universe.json"
TAXONOMY_NORMALIZED = ARTIFACTS / "taxonomy_normalized.json"
IDENTITY_UNIVERSE = ARTIFACTS / "identity_universe.json"
RECONCILED = ARTIFACTS / "reconciled_identity_universe.json"
TAXONOMY_HARVEST = ARTIFACTS / "taxonomy_harvest.json"
CATALOG_INVENTORY = ARTIFACTS / "catalog_inventory.json"
CATALOG_CENSUS = ARTIFACTS / "catalog_census.json"
REAL_TAXONOMY = ARTIFACTS / "real_taxonomy_data.json"
HEADLIGHTMAG_MODELS = ARTIFACTS / "headlightmag_models.json"


# ── loaders (cached per test session) ──────────────────────────────────
def _load(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def raw_taxonomy():
    return _load(RAW_TAXONOMY)


@pytest.fixture(scope="session")
def normalized():
    return _load(TAXONOMY_NORMALIZED)


@pytest.fixture(scope="session")
def identity():
    return _load(IDENTITY_UNIVERSE)


@pytest.fixture(scope="session")
def reconciled():
    return _load(RECONCILED)


@pytest.fixture(scope="session")
def harvest():
    return _load(TAXONOMY_HARVEST)


@pytest.fixture(scope="session")
def catalog_inventory():
    return _load(CATALOG_INVENTORY)


@pytest.fixture(scope="session")
def catalog_census():
    return _load(CATALOG_CENSUS)


@pytest.fixture(scope="session")
def real_taxonomy():
    return _load(REAL_TAXONOMY)


@pytest.fixture(scope="session")
def headlightmag_models():
    return _load(HEADLIGHTMAG_MODELS)


# ── helpers ────────────────────────────────────────────────────────────
def _all_nodes(raw_taxonomy) -> list[dict]:
    """Flat list of every node in raw_taxonomy_universe."""
    return raw_taxonomy.get("nodes", [])


def _census_mfr_names(census: dict) -> set[str]:
    """Manufacturer names from catalog_census.json by_manufacturer list."""
    return {m.get("name", "") for m in census.get("by_manufacturer", [])}


def _inventory_mfr_names(inv: dict) -> set[str]:
    """Manufacturer names from catalog_inventory.json by_manufacturer list."""
    return {m.get("name", "") for m in inv.get("by_manufacturer", [])}


# ────────────────────────────────────────────────────────────────────────
# 1. PAYLOAD HASH — datasets that claim a payload_hash must carry one
# ────────────────────────────────────────────────────────────────────────
class TestPayloadHash:
    """Every dataset file that has an `acquisition_method` must also
    declare a `payload_hash` so downstream consumers can verify
    integrity.  A missing hash means the raw bytes were never fingerprinted."""

    DATASET_FILES = sorted(DATASETS.glob("*.json"))

    @pytest.mark.parametrize(
        "ds_path", DATASET_FILES, ids=[p.stem for p in DATASET_FILES]
    )
    def test_dataset_has_payload_hash(self, ds_path: Path):
        data = _load(ds_path)
        # If it has acquisition_method it is a raw capture — must have hash
        if "acquisition_method" in data:
            assert "payload_hash" in data, (
                f"{ds_path.name}: raw capture has no payload_hash. "
                f"Integrity cannot be verified."
            )
            h = data["payload_hash"]
            assert isinstance(h, str) and len(h) >= 8, (
                f"{ds_path.name}: payload_hash is not a valid digest: {h!r}"
            )

    def test_raw_taxonomy_universe_has_observed_at(self, raw_taxonomy):
        """Each tree in raw_taxonomy_universe must have observed_at
        and source_role for audit trail."""
        for tree in raw_taxonomy.get("trees", []):
            assert "observed_at" in tree, (
                f"Tree {tree.get('source_name', '?')} missing observed_at"
            )
            assert "source_role" in tree, (
                f"Tree {tree.get('source_name', '?')} missing source_role"
            )


# ────────────────────────────────────────────────────────────────────────
# 2. SOURCE-NATIVE IDS — must not be synthetic/re-indexed
# ────────────────────────────────────────────────────────────────────────
class TestSourceNativeIds:
    """source_native_id must come from the upstream source, not be a
    sequential re-index.  OEM pricelist sources (toyota_official,
    mazda_official) legitimately omit source_native_id — they use flat
    source_id instead.  This test focuses on structured sources like fipe."""

    def test_no_synthetic_sequential_native_ids(self, raw_taxonomy):
        """Native IDs should be source-originated, not 0,1,2,3...
        Only checks nodes that HAVE a non-null source_native_id."""
        bad_ids = []
        for node in _all_nodes(raw_taxonomy):
            nid = node.get("source_native_id")
            if nid is None:
                continue  # OEM pricelists legitimately omit native_id
            # Flag short sequential IDs from non-fipe sources
            if re.match(r"^\d{1,2}$", str(nid)) and str(nid) in ("0", "1", "2", "3", "4"):
                src = node.get("source_name", "")
                if "fipe" not in src:
                    bad_ids.append((node.get("source_id"), nid, src))
        assert not bad_ids, (
            f"Found synthetic sequential native IDs from non-fipe sources: {bad_ids}"
        )

    def test_oem_nodes_without_native_id_have_source_id(self, raw_taxonomy):
        """Nodes without source_native_id must at least have a
        meaningful source_id (not just a sequential index)."""
        bad = []
        for n in _all_nodes(raw_taxonomy):
            if n.get("source_native_id") is None:
                sid = n.get("source_id", "")
                # source_id like "toyota_0" is acceptable — it encodes source
                # but a bare "0" would be synthetic
                if not any(
                    src in sid
                    for src in ("toyota", "mazda", "honda", "bmw", "fipe")
                ):
                    bad.append(sid)
        # No bare synthetic source_ids without source context
        # (This catches pipeline re-indexing that drops source prefix)
        assert not bad, f"Nodes without source_native_id have bare source_ids: {bad}"

    def test_source_native_id_preserved_across_pipeline(self, raw_taxonomy):
        """Native IDs in raw nodes must be strings (preserve upstream type)."""
        bad = []
        for n in _all_nodes(raw_taxonomy):
            nid = n.get("source_native_id")
            if nid is not None and not isinstance(nid, str):
                bad.append((n.get("source_id"), type(nid).__name__))
        assert not bad, (
            f"Native IDs coerced to non-string types: {bad[:5]}"
        )


# ────────────────────────────────────────────────────────────────────────
# 3. PARENT-CHILD EDGES — must reference real nodes
# ────────────────────────────────────────────────────────────────────────
class TestParentChildEdges:
    """parent_native_id, when present, must point to a node that actually
    exists in the same tree.  Detects fabricated hierarchy."""

    def test_parent_edges_reference_existing_nodes(self, raw_taxonomy):
        nodes = _all_nodes(raw_taxonomy)
        # Build lookup: source_name → set of native_ids
        by_source = {}
        for n in nodes:
            src = n.get("source_name", "")
            by_source.setdefault(src, set()).add(n.get("source_native_id"))

        orphans = []
        for n in nodes:
            parent = n.get("parent_native_id")
            if parent:
                src = n.get("source_name", "")
                if parent not in by_source.get(src, set()):
                    orphans.append(
                        (n.get("source_id"), n.get("source_native_id"), parent, src)
                    )
        assert not orphans, (
            f"{len(orphans)} nodes reference non-existent parents: {orphans[:5]}"
        )

    def test_no_circular_parent_edges(self, raw_taxonomy):
        """Parent chain must not form a cycle."""
        nodes = _all_nodes(raw_taxonomy)
        by_source = {}
        for n in nodes:
            src = n.get("source_name", "")
            by_source.setdefault(src, {})[n.get("source_native_id")] = n

        cycles = []
        for n in nodes:
            parent = n.get("parent_native_id")
            if not parent:
                continue
            src = n.get("source_name", "")
            visited = {n.get("source_native_id")}
            current = parent
            while current and current in by_source.get(src, {}):
                if current in visited:
                    cycles.append(
                        (n.get("source_id"), n.get("source_native_id"), current)
                    )
                    break
                visited.add(current)
                current = by_source[src][current].get("parent_native_id")
        assert not cycles, (
            f"{len(cycles)} circular parent chains detected: {cycles[:3]}"
        )

    def test_flat_sources_have_no_children(self, raw_taxonomy):
        """Sources with node_type FLAT_ROW should not declare children."""
        nodes = _all_nodes(raw_taxonomy)
        # Build parent→children map
        children_of = {}
        for n in nodes:
            pid = n.get("parent_native_id")
            if pid:
                children_of.setdefault(pid, []).append(n.get("source_native_id"))

        flat_with_children = []
        for n in nodes:
            if n.get("node_type") == "FLAT_ROW" and n.get("source_native_id") in children_of:
                flat_with_children.append(
                    (n.get("source_id"), n.get("source_native_id"), n.get("source_name"))
                )
        # Currently passes — no FLAT_ROWs have children in the pipeline
        # This test catches a future regression where flat data is wired into trees
        assert not flat_with_children, f"FLAT_ROWs with children: {flat_with_children}" 


# ────────────────────────────────────────────────────────────────────────
# 4. DECOMPOSITION WITHOUT EVIDENCE — HIGH confidence needs backing
# ────────────────────────────────────────────────────────────────────────
class TestDecompositionEvidence:
    """decomposition_confidence of 'high' requires non-trivial decomposition
    evidence.  A confidence claim without decomposition_evidence or with
    'Source is flat; no hierarchy declared' is fraudulent."""

    def test_high_confidence_has_evidence(self, identity):
        """Candidates with high decomposition confidence must have
        decomposition_evidence that is NOT the generic flat-source excuse."""
        BAD_EVIDENCE = "Source is flat; no hierarchy declared"
        violations = []
        candidates = identity.get("candidates", [])
        for c in candidates:
            conf = c.get("decomposition_confidence", "none")
            evidence = c.get("decomposition_evidence", "")
            if conf == "high" and (not evidence or evidence == BAD_EVIDENCE):
                violations.append({
                    "candidate_id": c.get("candidate_id"),
                    "model": c.get("model"),
                    "decomposition_evidence": evidence,
                })
        assert not violations, (
            f"{len(violations)} candidates claim HIGH decomposition without evidence: "
            f"{json.dumps(violations[:3], indent=2)}"
        )

    def test_medium_confidence_has_at_least_method(self, identity):
        """Medium confidence should have a decomposition_method that is not 'none'."""
        violations = []
        for c in identity.get("candidates", []):
            conf = c.get("decomposition_confidence", "none")
            method = c.get("decomposition_method", "none")
            if conf in ("medium", "high") and method == "none":
                violations.append(
                    (c.get("candidate_id"), c.get("model"), conf, method)
                )
        assert not violations, (
            f"{len(violations)} candidates claim non-trivial confidence "
            f"but decomposition_method is 'none': {violations[:5]}"
        )

    def test_normalized_decomposition_confidence_values(self, normalized):
        """Every decomposition confidence in taxonomy_normalized must be
        one of the valid enum values."""
        VALID = {"none", "low", "medium", "high"}
        violations = []
        for mfr, models in normalized.items():
            if not isinstance(models, list):
                continue
            for m in models:
                for decomp in m.get("decompositions", []):
                    conf = decomp.get("confidence")
                    if conf not in VALID:
                        violations.append(
                            (m.get("canonical_id"), m.get("model"), conf)
                        )
        assert not violations, (
            f"{len(violations)} invalid confidence values: {violations[:5]}"
        )


# ────────────────────────────────────────────────────────────────────────
# 5. CANONICAL ID ON UNRECONCILED CANDIDATES
# ────────────────────────────────────────────────────────────────────────
class TestCanonicalIdIntegrity:
    """Candidates in identity_universe.json should NOT carry a canonical_id
    unless they also appear in reconciled_identity_universe.json.
    The canonical_id is a post-reconciliation artifact — its presence
    in pre-reconciliation data indicates data leakage."""

    def test_no_canonical_id_in_unreconciled(self, identity, reconciled):
        """identity_universe candidates must not have canonical_id unless
        they also exist in the reconciled universe."""
        reconciled_ids = set()
        for mfr, models in reconciled.items():
            if not isinstance(models, list):
                continue
            for m in models:
                rid = m.get("canonical_id")
                if rid:
                    reconciled_ids.add(rid)

        violations = []
        for c in identity.get("candidates", []):
            cid = c.get("canonical_id")
            if cid and cid not in reconciled_ids:
                violations.append({
                    "candidate_id": c.get("candidate_id"),
                    "model": c.get("model"),
                    "phantom_canonical_id": cid,
                })
        assert not violations, (
            f"{len(violations)} unreconciled candidates have phantom canonical_ids: "
            f"{json.dumps(violations[:3], indent=2)}"
        )

    def test_reconciled_canonical_ids_are_hex(self, normalized):
        """All canonical_ids in taxonomy_normalized must be hex hashes
        (not UUIDs, not names, not sequential)."""
        bad = []
        for mfr, models in normalized.items():
            if not isinstance(models, list):
                continue
            for m in models:
                cid = m.get("canonical_id", "")
                if not re.match(r"^[0-9a-f]{12,}$", cid):
                    bad.append((mfr, m.get("model"), cid))
        assert not bad, (
            f"{len(bad)} canonical_ids are not hex hashes: {bad[:5]}"
        )

    def test_reconciled_entries_have_required_fields(self, normalized):
        """Every reconciled entry must have source_representations with
        source_name, source_label, and source_id."""
        REQUIRED_SR_FIELDS = {"source_name", "source_label", "source_id"}
        violations = []
        for mfr, models in normalized.items():
            if not isinstance(models, list):
                continue
            for m in models:
                for sr in m.get("source_representations", []):
                    missing = REQUIRED_SR_FIELDS - set(sr.keys())
                    if missing:
                        violations.append(
                            (m.get("canonical_id"), m.get("model"), missing)
                        )
        assert not violations, (
            f"{len(violations)} source_representations missing required fields: "
            f"{violations[:5]}"
        )


# ────────────────────────────────────────────────────────────────────────
# 6. TAXONOMY COUNTS INCLUDING MEDIA SOURCES
# ────────────────────────────────────────────────────────────────────────
class TestTaxonomyCounts:
    """Cross-validate that taxonomy counts across artifacts are consistent
    and that media sources (headlightmag, 9carthai) are properly excluded
    from vehicle taxonomy counts but tracked in source inventories."""

    def test_harvest_tree_counts_match_node_totals(self, harvest):
        """Sum of tree.node_count must equal total_raw_nodes."""
        tree_total = sum(t.get("node_count", 0) for t in harvest.get("trees", []))
        total_raw = harvest.get("total_raw_nodes", 0)
        assert tree_total == total_raw, (
            f"Tree node_counts sum ({tree_total}) != total_raw_nodes ({total_raw})"
        )

    def test_census_by_manufacturer_model_count_matches_inventory(
        self, catalog_census, catalog_inventory
    ):
        """catalog_census and catalog_inventory use the same by_manufacturer
        format.  Each manufacturer's model_count must match the length of
        its models array."""
        for source_label, artifact in [
            ("census", catalog_census),
            ("inventory", catalog_inventory),
        ]:
            violations = []
            for mfr in artifact.get("by_manufacturer", []):
                declared = mfr.get("model_count", 0)
                actual = len(mfr.get("models", []))
                if declared != actual:
                    violations.append(
                        f"{mfr.get('name')}: model_count={declared} len(models)={actual}"
                    )
            assert not violations, (
                f"{source_label}: model_count vs models array mismatch: {violations}"
            )

    def test_census_model_count_consistency(self, catalog_census):
        """catalog_census summary should have total_candidates == 0
        OR total_candidates == sum of by_manufacturer model_counts.
        A zero total with non-zero by_manufacturer is a stale summary."""
        total = catalog_census.get("summary", {}).get("total_candidates", 0)
        mfr_sum = sum(m.get("model_count", 0) for m in catalog_census.get("by_manufacturer", []))
        if total == 0 and mfr_sum > 0:
            assert False, (
                f"catalog_census summary.total_candidates is 0 but "
                f"by_manufacturer sums to {mfr_sum} — stale summary"
            )
        elif total != 0 and total != mfr_sum:
            assert False, (
                f"catalog_census total_candidates ({total}) != "
                f"sum of by_manufacturer model_counts ({mfr_sum})"
            )

    def test_media_sources_not_in_vehicle_taxonomy_counts(self, catalog_inventory):
        """Media sources like headlightmag should not appear as
        official vehicle taxonomy sources in catalog_inventory."""
        MEDIA_SOURCES = {"headlightmag", "9carthai", "pantip", "youtube"}
        violations = []
        for mfr in catalog_inventory.get("by_manufacturer", []):
            for model in mfr.get("models", []):
                src = model.get("source", "")
                if any(media in src.lower() for media in MEDIA_SOURCES):
                    violations.append((mfr.get("name"), model.get("name"), src))
        assert not violations, (
            f"Media sources used as model data sources: {violations[:5]}"
        )

    def test_real_taxonomy_carrier_vs_census(self, real_taxonomy, catalog_census):
        """real_taxonomy_data.json manufacturers should be a subset of
        what catalog_census has discovered."""
        real_mfrs = set(real_taxonomy.keys())
        census_mfrs = _census_mfr_names(catalog_census)
        # real_taxonomy keys (Toyota, Mazda) must be in census
        violations = real_mfrs - census_mfrs
        assert not violations, (
            f"real_taxonomy has manufacturers not in census: {violations}"
        )

    def test_headlightmag_models_are_empty_or_media_tagged(self, headlightmag_models):
        """headlightmag_models.json should either be empty per-brand
        or clearly tagged as media, not official taxonomy data."""
        for brand, models in headlightmag_models.items():
            if models:
                for m in models:
                    assert "source" in m or "url" in m, (
                        f"headlightmag model {brand}/{m} has no "
                        f"provenance marker (source/url)"
                    )

    def test_harvest_trees_declare_valid_roles(self, harvest):
        """Every tree in taxonomy_harvest must declare a known source_role."""
        VALID_ROLES = {"IDENTITY_ENUMERATOR", "MARKET_TRUTH", "MARKET_REFERENCE", "MEDIA_DISCOVERY"}
        violations = []
        for tree in harvest.get("trees", []):
            role = tree.get("source_role", "")
            if role not in VALID_ROLES:
                violations.append((tree.get("source_name"), role))
        assert not violations, (
            f"Invalid source_roles in harvest: {violations}"
        )

    def test_identity_universe_candidate_count_matches(self, identity):
        """identity_universe.json declared candidate_count must match actual."""
        declared = identity.get("candidate_count", 0)
        actual = len(identity.get("candidates", []))
        assert declared == actual, (
            f"candidate_count declaration ({declared}) != "
            f"actual array length ({actual})"
        )

    def test_raw_taxonomy_node_count_matches_actual(self, raw_taxonomy):
        """raw_taxonomy_universe total_raw_nodes must match the actual
        length of the nodes array."""
        declared = raw_taxonomy.get("total_raw_nodes", 0)
        actual = len(raw_taxonomy.get("nodes", []))
        assert declared == actual, (
            f"raw_taxonomy total_raw_nodes declaration ({declared}) != "
            f"actual nodes array length ({actual})"
        )


# ────────────────────────────────────────────────────────────────────────
# 7. SOURCE-ROLE SEPARATION — cross-cutting invariants
# ────────────────────────────────────────────────────────────────────────
class TestSourceRoleSeparation:
    """IDENTITY_ENUMERATOR sources provide name-space coverage.
    MARKET_TRUTH sources provide prices.
    The pipeline must never use a source in the wrong role."""

    def test_identity_enum_nodes_have_no_price(self, raw_taxonomy):
        """IDENTITY_ENUMERATOR nodes should not carry price_thb > 0
        unless the source also provides market data."""
        violations = []
        for n in _all_nodes(raw_taxonomy):
            if n.get("source_role") == "IDENTITY_ENUMERATOR":
                if n.get("price_thb", 0) > 0:
                    violations.append(
                        (n.get("source_id"), n.get("source_name"), n.get("price_thb"))
                    )
        # FIPE is purely an identity enumerator; prices are from OEM sites
        assert not violations, (
            f"IDENTITY_ENUMERATOR nodes carry unexpected prices: {violations[:5]}"
        )

    def test_market_truth_nodes_have_observed_at(self, raw_taxonomy):
        """MARKET_TRUTH nodes must carry observed_at for audit trail."""
        missing = []
        for n in _all_nodes(raw_taxonomy):
            if n.get("source_role") == "MARKET_TRUTH":
                if not n.get("observed_at"):
                    missing.append(n.get("source_id"))
        assert not missing, (
            f"{len(missing)} MARKET_TRUTH nodes missing observed_at: {missing[:5]}"
        )

    def test_source_roles_are_consistent_within_tree(self, raw_taxonomy):
        """All nodes from the same source_name must share the same source_role."""
        role_by_source = {}
        for n in _all_nodes(raw_taxonomy):
            src = n.get("source_name", "")
            role = n.get("source_role", "")
            role_by_source.setdefault(src, set()).add(role)

        violations = []
        for src, roles in role_by_source.items():
            if len(roles) > 1:
                violations.append((src, roles))
        assert not violations, (
            f"Sources with mixed roles: {violations}"
        )


class TestMutationDetection:
    """Adversarial tests: corrupt fixtures → run verifier → assert FAIL/PARTIAL.

    Per GLOBAL WORK RULE #5: each test must:
    1. Copy artifacts to isolated temp tree
    2. Corrupt a specific field
    3. Run verifier against corrupted tree
    4. Assert verifier status is FAIL or PARTIAL
    """

    def _run_verifier(self, artifact_dir):
        """Run the verifier against a given artifact directory."""
        from lib.thai_factory.catalog.verifier import verify_artifacts
        return verify_artifacts(str(artifact_dir))

    def _copy_artifacts(self, src_dir, dst_dir):
        """Copy all artifacts to isolated temp tree."""
        import shutil
        shutil.copytree(src_dir, dst_dir)

    def test_corrupt_openev_empty_payload_hash_verifier_catches(self, tmp_path):
        """Empty OpenEV payload_hash → verifier must detect FAIL."""
        src_dir = "audit/catalog-discovery"
        dst_dir = tmp_path / "audit" / "catalog-discovery"
        self._copy_artifacts(src_dir, dst_dir)

        # Set payload_hash to empty
        ev_path = dst_dir / "second_taxonomy_capture.json"
        with open(ev_path) as f:
            data = json.load(f)
        data["payload_hash"] = ""
        with open(ev_path, 'w') as f:
            json.dump(data, f)

        result = self._run_verifier(dst_dir)

        # Verifier must detect empty payload_hash
        hash_check = [c for c in result["checks"]
                     if c["check"] == "payload_hash_open_ev" and c["section"] == "hash_integrity"]
        assert hash_check, f"Verifier missing payload_hash_open_ev check"
        assert hash_check[0]["status"] == "FAIL", \
            f"Verifier should FAIL on empty payload_hash, got {hash_check[0]['status']}"

    def test_corrupt_openev_invalid_hash_format_verifier_catches(self, tmp_path):
        """Invalid OpenEV payload_hash format → verifier must detect FAIL."""
        src_dir = "audit/catalog-discovery"
        dst_dir = tmp_path / "audit" / "catalog-discovery"
        self._copy_artifacts(src_dir, dst_dir)

        # Set payload_hash to invalid format (not hex)
        ev_path = dst_dir / "second_taxonomy_capture.json"
        with open(ev_path) as f:
            data = json.load(f)
        data["payload_hash"] = "NOT_A_VALID_HASH"
        with open(ev_path, 'w') as f:
            json.dump(data, f)

        result = self._run_verifier(dst_dir)

        hash_check = [c for c in result["checks"]
                     if c["check"] == "payload_hash_open_ev" and c["section"] == "hash_integrity"]
        assert hash_check, f"Verifier missing payload_hash_open_ev check"
        assert hash_check[0]["status"] == "FAIL", \
            f"Verifier should FAIL on invalid hash format, got {hash_check[0]['status']}"

    def test_corrupt_headlightmag_verifier_catches(self, tmp_path):
        """Removed HLM article evidence → verifier must detect via evidence accounting."""
        src_dir = "audit/catalog-discovery"
        dst_dir = tmp_path / "audit" / "catalog-discovery"
        self._copy_artifacts(src_dir, dst_dir)

        # Remove all article evidence
        hlm_path = dst_dir / "media_discovery_headlightmag.json"
        with open(hlm_path) as f:
            data = json.load(f)
        for e in data.get("entries", []):
            e["article_evidence"] = []
            e["article_evidence_count"] = 0
        with open(hlm_path, 'w') as f:
            json.dump(data, f)

        result = self._run_verifier(dst_dir)

        # Verifier must detect zero article evidence and return PARTIAL
        evidence_check = [c for c in result["checks"]
                         if c["check"] == "evidence_accounting" and c["section"] == "hlm"]
        assert evidence_check, f"Verifier missing hlm evidence_accounting check"
        assert evidence_check[0]["with_article"] == 0, \
            f"Expected 0 with_article after corruption, got {evidence_check[0]['with_article']}"
        # With 0% evidence, status should be PARTIAL (not PASS)
        assert evidence_check[0]["status"] == "PARTIAL", \
            f"Expected PARTIAL status with 0% evidence, got {evidence_check[0]['status']}"

    def test_corrupt_fipe_parent_verifier_catches(self, tmp_path):
        """Corrupted Fipe parent_native_id → verifier must detect FAIL."""
        src_dir = "audit/catalog-discovery"
        dst_dir = tmp_path / "audit" / "catalog-discovery"
        self._copy_artifacts(src_dir, dst_dir)

        # Corrupt parent_native_id to invalid format
        fipe_path = dst_dir / "fipe_year_hierarchy.json"
        with open(fipe_path) as f:
            data = json.load(f)
        for row in data.get("year_hierarchy", []):
            row["parent_native_id"] = "99:9999"  # invalid brand:model
        with open(fipe_path, 'w') as f:
            json.dump(data, f)

        result = self._run_verifier(dst_dir)

        parent_check = [c for c in result["checks"]
                       if c["check"] == "parent_resolution" and c["section"] == "fipe"]
        assert parent_check, f"Verifier missing parent_resolution check"
        assert parent_check[0]["status"] == "FAIL", \
            f"Verifier should FAIL on corrupted parents, got {parent_check[0]['status']}"

    def test_inject_canonical_id_verifier_catches(self, tmp_path):
        """Injected canonical_id → verifier must detect FAIL."""
        src_dir = "audit/catalog-discovery"
        dst_dir = tmp_path / "audit" / "catalog-discovery"
        self._copy_artifacts(src_dir, dst_dir)

        # Inject canonical_id into raw nodes
        raw_path = dst_dir / "raw_taxonomy_universe.json"
        with open(raw_path) as f:
            data = json.load(f)
        for node in data.get("nodes", [])[:10]:
            node["canonical_id"] = "FAKE_CANONICAL_ID"
        with open(raw_path, 'w') as f:
            json.dump(data, f)

        result = self._run_verifier(dst_dir)

        canonical_check = [c for c in result["checks"]
                          if c["check"] == "canonical_id_in_raw" and c["section"] == "integrity"]
        assert canonical_check, f"Verifier missing canonical_id check"
        assert canonical_check[0]["status"] == "FAIL", \
            f"Verifier should FAIL on injected canonical_id, got {canonical_check[0]['status']}"

    def test_media_contamination_detected(self, tmp_path):
        """Injected media nodes → verifier must detect FAIL."""
        src_dir = "audit/catalog-discovery"
        dst_dir = tmp_path / "audit" / "catalog-discovery"
        self._copy_artifacts(src_dir, dst_dir)

        # Inject media nodes into raw universe
        raw_path = dst_dir / "raw_taxonomy_universe.json"
        with open(raw_path) as f:
            data = json.load(f)
        data["nodes"].append({
            "source_name": "headlightmag",
            "source_id": "media_1",
            "label": "Fake Media Node",
            "node_type": "MODEL",
        })
        with open(raw_path, 'w') as f:
            json.dump(data, f)

        result = self._run_verifier(dst_dir)

        media_check = [c for c in result["checks"]
                      if c["check"] == "media_in_taxonomy" and c["section"] == "contamination"]
        assert media_check, f"Verifier missing media contamination check"
        assert media_check[0]["status"] == "FAIL", \
            f"Verifier should FAIL on media contamination, got {media_check[0]['status']}"

    def test_corrupt_openev_row_anchoring_verifier_catches(self, tmp_path):
        """Corrupted OpenEV row commit_sha → verifier must detect FAIL."""
        src_dir = "audit/catalog-discovery"
        dst_dir = tmp_path / "audit" / "catalog-discovery"
        self._copy_artifacts(src_dir, dst_dir)

        # Corrupt row commit_sha to wrong value
        ev_path = dst_dir / "second_taxonomy_capture.json"
        with open(ev_path) as f:
            data = json.load(f)
        for row in data.get("rows", []):
            row["commit_sha"] = "0000000000000000000000000000000000000000"
        with open(ev_path, 'w') as f:
            json.dump(data, f)

        result = self._run_verifier(dst_dir)

        anchoring_check = [c for c in result["checks"]
                          if c["check"] == "row_anchoring" and c["section"] == "openev"]
        assert anchoring_check, f"Verifier missing row_anchoring check"
        assert anchoring_check[0]["status"] == "FAIL", \
            f"Verifier should FAIL on corrupted row anchoring, got {anchoring_check[0]['status']}"