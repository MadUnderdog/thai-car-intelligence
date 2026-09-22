"""Thai market catalog discovery and reconciliation."""
from .contracts import (
    CatalogCandidate, CanonicalCatalogEntry, CatalogInventory,
    MarketStatus, CandidateStatus, EvidenceLink, EvidenceStrength,
    Relationship, RelationshipType,
)
from .discovery import CatalogDiscovery
from .reconciler import CatalogReconciler
from .sources import MANUFACTURER_SOURCE_MAPS

__all__ = [
    "CatalogCandidate", "CanonicalCatalogEntry", "CatalogInventory",
    "MarketStatus", "CandidateStatus", "EvidenceLink", "EvidenceStrength",
    "Relationship", "RelationshipType",
    "CatalogDiscovery", "CatalogReconciler", "MANUFACTURER_SOURCE_MAPS",
]
