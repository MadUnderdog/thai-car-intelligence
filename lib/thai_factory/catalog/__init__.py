"""Thai market catalog discovery and reconciliation."""
from .contracts import (
    Manufacturer, Model, Variant, Generation, Powertrain,
    MarketStatus, CatalogEntry, CatalogIdentity, EvidenceLink,
)
from .discovery import CatalogDiscovery
from .reconciler import CatalogReconciler

__all__ = [
    "Manufacturer", "Model", "Variant", "Generation", "Powertrain",
    "MarketStatus", "CatalogEntry", "CatalogIdentity", "EvidenceLink",
    "CatalogDiscovery", "CatalogReconciler",
]
