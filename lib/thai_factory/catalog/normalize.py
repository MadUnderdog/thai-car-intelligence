"""
Taxonomy Normalizer — decomposes source labels into model/variant hierarchy.
Produces normalized identity graph from raw taxonomy tree.
"""
import json
import re
from typing import List, Dict, Tuple
from .taxonomy_tree import (
    RawTaxonomyTree, TaxonomyNode, NormalizedCandidate,
    TaxonomyNormalizer, NodeType,
)


def normalize_tree(tree: RawTaxonomyTree) -> List[NormalizedCandidate]:
    """Normalize a raw taxonomy tree into candidates with decomposition."""
    normalizer = TaxonomyNormalizer()
    candidates = []
    
    for node in tree.nodes:
        # Decompose the source label
        decomp = normalizer.decompose_label(node.raw_label)
        
        # Create normalized candidate
        candidate = NormalizedCandidate(
            manufacturer="",  # Will be set from context
            model=decomp["model"],
            generation=decomp.get("generation", ""),
            body=decomp.get("body", ""),
            variant=decomp.get("variant", ""),
            trim=decomp.get("trim", ""),
            powertrain=decomp.get("powertrain", ""),
            price_thb=node.price_thb,
            price_level="UNKNOWN",
            price_source=tree.source_name,
            source_representations=[{
                "source_name": tree.source_name,
                "source_label": node.source_native_label,
                "source_id": node.source_native_id,
                "decomposition_confidence": decomp["confidence"],
            }],
            source_count=1,
            decompositions=[decomp],
        )
        candidate.compute_id()
        candidates.append(candidate)
    
    return candidates


def merge_candidates(candidates: List[NormalizedCandidate]) -> List[NormalizedCandidate]:
    """Merge candidates with same canonical_id."""
    by_id = {}
    for c in candidates:
        if c.canonical_id not in by_id:
            by_id[c.canonical_id] = c
        else:
            existing = by_id[c.canonical_id]
            # Merge source representations
            existing.source_representations.extend(c.source_representations)
            existing.source_count = len(existing.source_representations)
            # Keep higher confidence decomposition
            if c.decompations and not existing.decompations:
                existing.decompations = c.decompations
    
    return list(by_id.values())


def normalize_all_trees(trees: List[RawTaxonomyTree]) -> Dict:
    """Normalize all trees and produce the normalized identity graph."""
    all_candidates = []
    raw_trees = []
    
    for tree in trees:
        # Save raw tree
        raw_trees.append({
            "source_name": tree.source_name,
            "source_url": tree.source_url,
            "source_role": tree.source_role,
            "observed_at": tree.observed_at,
            "acquisition_method": tree.acquisition_method,
            "node_count": len(tree.nodes),
            "nodes": [asdict(n) for n in tree.nodes],
        })
        
        # Normalize
        candidates = normalize_tree(tree)
        all_candidates.extend(candidates)
    
    # Merge duplicates
    merged = merge_candidates(all_candidates)
    
    # Build output
    return {
        "raw_trees": raw_trees,
        "normalized_candidates": [asdict(c) for c in merged],
        "summary": {
            "raw_tree_count": len(raw_trees),
            "total_raw_nodes": sum(t["node_count"] for t in raw_trees),
            "normalized_candidate_count": len(merged),
            "sources": [t.source_name for t in trees],
        }
    }


# Import asdict
from dataclasses import asdict
