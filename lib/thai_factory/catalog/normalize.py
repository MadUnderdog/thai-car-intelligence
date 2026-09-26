"""
Taxonomy Normalizer — evidence-based decomposition.
Does NOT infer hierarchy from suffixes alone.
For flat source rows, keeps source label intact and leaves fields nullable.
"""
import hashlib
import json
import re
from dataclasses import asdict
from typing import List, Dict, Tuple, Optional
from .taxonomy_tree import RawTaxonomyTree, TaxonomyNode, ReconciledCandidate


# Known trim/grade suffixes — used ONLY when source structure supports decomposition
TRIM_EVIDENCE = {
    "GR Sport": "trim grade",
    "Nightshade": "trim grade",
    "Leader": "trim grade",
    "Legender": "trim grade",
    "Essential": "trim grade",
    "Standard Cab": "body type",
    "Double Cab": "body type",
    "Smart Cab": "body type",
    "Fastback": "body type",
    "Sedan": "body type",
    "Overland": "trim grade",
    "Champ": "trim grade",
    "Z Edition": "trim grade",
}


def decompose_with_evidence(node: TaxonomyNode) -> ReconciledCandidate:
    """Decompose a flat row into model/variant ONLY with evidence.
    
    Rules:
    1. If source structure explicitly declares parent-child, use it.
    2. If multiple rows share a common prefix, that prefix may be the model.
    3. Suffix patterns are hints, not proof.
    4. For flat rows, keep source_label intact and leave decomposition nullable.
    """
    label = node.source_native_label
    
    candidate = ReconciledCandidate(
        manufacturer="",
        model=label,  # Default: entire label is model
        raw_node_ids=[node.source_id],
        source_representations=[{
            "source_name": node.source_name,
            "source_label": label,
            "source_id": node.source_native_id,
            "node_type": node.node_type,
        }],
        source_count=1,
        price_thb=node.price_thb,
        price_evidence_level=node.price_evidence_level,
        price_source=node.source_name,
        decomposition_method="none",
        decomposition_confidence="none",
        decomposition_evidence="Source is flat; no hierarchy declared",
    )
    
    return candidate


def infer_hierarchy_from_prefixes(candidates: List[ReconciledCandidate]) -> List[ReconciledCandidate]:
    """Infer model/variant hierarchy from shared prefixes.
    
    CRITICAL: Only decompose when:
    1. The prefix is a complete, standalone model (appears as its own row)
    2. The remainder is a recognized trim/grade/body pattern
    3. The decomposition makes semantic sense
    
    Do NOT decompose:
    - "Yaris ATIV" → "Yaris" + "ATIV" (ATIV is part of model name, not variant)
    - "GR 86" → "GR" + "86" (GR 86 is the model name)
    - "MAZDA3 FASTBACK" → "MAZDA3" + "FASTBACK" (FASTBACK is body type, but MAZDA3 is the model)
    """
    by_source = {}
    for c in candidates:
        for rep in c.source_representations:
            source = rep["source_name"]
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(c)
    
    for source, group in by_source.items():
        labels = [c.model for c in group]
        
        # Find complete model names (rows that appear exactly)
        complete_models = set(labels)
        
        # Find candidate decompositions
        for c in group:
            label = c.model
            
            # Try each known trim suffix
            for trim, trim_type in TRIM_EVIDENCE.items():
                if label.endswith(" " + trim):
                    prefix = label[:-(len(trim) + 1)].strip()
                    
                    # CRITICAL: Only decompose if prefix is a complete model in the source
                    if prefix in complete_models:
                        c.model = prefix
                        c.variant = trim
                        c.decomposition_method = "source_structure"
                        c.decomposition_confidence = "high"
                        c.decomposition_evidence = (
                            f"Source lists both '{prefix}' and '{label}' as separate rows; "
                            f"'{trim}' is a recognized {trim_type}"
                        )
                        break
                    else:
                        # Prefix not a standalone model — keep as-is
                        pass
    
    return candidates


def set_manufacturer(candidates: List[ReconciledCandidate], manufacturer: str):
    """Set manufacturer for all candidates from a source."""
    for c in candidates:
        c.manufacturer = manufacturer


def merge_candidates(candidates: List[ReconciledCandidate]) -> List[ReconciledCandidate]:
    """Merge candidates with same canonical_id."""
    for c in candidates:
        c.compute_id()
    
    by_id = {}
    for c in candidates:
        if c.canonical_id not in by_id:
            by_id[c.canonical_id] = c
        else:
            existing = by_id[c.canonical_id]
            existing.raw_node_ids.extend(c.raw_node_ids)
            existing.source_representations.extend(c.source_representations)
            existing.source_count = len(existing.source_representations)
    
    return list(by_id.values())


def normalize_tree(tree: RawTaxonomyTree, manufacturer: str = "") -> List[ReconciledCandidate]:
    """Normalize a raw taxonomy tree into candidates."""
    # Step 1: Create candidates from flat rows
    candidates = []
    for node in tree.nodes:
        candidate = decompose_with_evidence(node)
        candidates.append(candidate)
    
    # Step 2: Set manufacturer
    if manufacturer:
        set_manufacturer(candidates, manufacturer)
    
    # Step 3: Infer hierarchy from shared prefixes
    candidates = infer_hierarchy_from_prefixes(candidates)
    
    return candidates


def build_raw_universe(trees: List[RawTaxonomyTree]) -> Dict:
    """Build raw_taxonomy_universe.json from raw trees."""
    raw_nodes = []
    for tree in trees:
        for node in tree.nodes:
            raw_nodes.append(asdict(node))
    
    return {
        "version": "1.0",
        "target_date": "2026-09-22",
        "trees": [
            {
                "source_name": t.source_name,
                "source_url": t.source_url,
                "source_role": t.source_role,
                "observed_at": t.observed_at,
                "acquisition_method": t.acquisition_method,
                "node_count": len(t.nodes),
            }
            for t in trees
        ],
        "total_raw_nodes": len(raw_nodes),
        "nodes": raw_nodes,
    }


def build_reconciled_universe(candidates: List[ReconciledCandidate]) -> Dict:
    """Build reconciled_identity_universe.json from candidates."""
    return {
        "version": "1.0",
        "target_date": "2026-09-22",
        "candidate_count": len(candidates),
        "candidates": [asdict(c) for c in candidates],
    }
