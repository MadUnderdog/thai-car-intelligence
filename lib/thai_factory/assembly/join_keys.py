"""
P119 — join keys (§96): manufacturer_slug + model_slug + variant_slug +
model_year, resolved through an EVIDENCE-BACKED alias path:

  packet candidate_key  →  identity universe records (CONFIRMED_* with their
  source evidence: label / artifact / role — audit/coverage/
  identity_universe_p108.json, the frozen identity ledger's own artifact)
  → canonical join key, enriched by the alias catalog (P110,
  storage/thai-alias-catalog.json) where the model exists there.

Joins never match on display strings alone: a key that matches NEITHER the
evidence-backed identity universe NOR the alias catalog is REJECTED with an
explicit reason instead of being fuzzy-matched. candidate_id (packet-level)
is retained everywhere; canonical_id only appears via reconcile().
"""
import hashlib
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_UNIVERSE = REPO_ROOT / "audit" / "coverage" / "identity_universe_p108.json"


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", str(text)).casefold().strip()
    t = re.sub(r"[\s_]+", " ", t)
    return t


def _slug_norm(text: str) -> str:
    return _norm(text).replace(" ", "-")


def _key4(manufacturer: Any, model: Any, generation: Any, variant: Any) -> str:
    return "|".join(_norm(v) for v in (manufacturer, model, generation, variant))


@lru_cache(maxsize=4)
def _universe_index(path_str: str) -> Dict[str, Dict[str, Any]]:
    """CONFIRMED identity records keyed by normalised 4-part identity key."""
    path = Path(path_str)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    universe = payload.get("universe") or {}
    index: Dict[str, Dict[str, Any]] = {}
    for record in universe.get("records") or []:
        status = str(record.get("status") or "")
        if not status.startswith("CONFIRMED"):
            continue
        key = _key4(record.get("manufacturer", ""), record.get("model", ""),
                    record.get("generation", ""), record.get("variant", ""))
        index.setdefault(key, record)
    return index


def _catalog_index(catalog: Dict[str, Any]) -> Dict[str, Any]:
    """Build slug/name/alias lookup over the catalog's models dict."""
    by_slug: Dict[str, Any] = {}
    by_name: Dict[str, Any] = {}
    by_alias: Dict[str, Any] = {}
    models = catalog.get("models") or {}
    items = models.items() if isinstance(models, dict) else [(m.get("slug"), m) for m in models]
    for key, entry in items:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug") or key
        by_slug[_slug_norm(slug)] = entry
        for name_field in ("nameEn", "nameTh"):
            if entry.get(name_field):
                by_name.setdefault(_norm(entry[name_field]), entry)
        for alias in entry.get("aliases") or []:
            by_alias.setdefault(_norm(alias), entry)
            by_alias.setdefault(_slug_norm(alias), entry)
    return {"by_slug": by_slug, "by_name": by_name, "by_alias": by_alias}


def _catalog_lookup(model_display: str, catalog: Dict[str, Any]) -> Optional[tuple]:
    """Return (entry, matched_via) or None."""
    index = _catalog_index(catalog)
    entry = index["by_slug"].get(_slug_norm(model_display))
    if entry:
        return entry, "slug"
    entry = index["by_name"].get(_norm(model_display))
    if entry:
        return entry, "nameEn"
    entry = index["by_alias"].get(_norm(model_display))
    if entry:
        return entry, "alias"
    return None


def _brand_agrees(mfr: str, entry: Dict[str, Any], catalog: Dict[str, Any]) -> bool:
    """Prove a catalog entry belongs to the packet's manufacturer (§96
    manufacturer_slug join key / sibling-brand separation)."""
    mfr_n = _norm(mfr)
    entry_brand = str(entry.get("brandSlug") or "")
    if _norm(entry_brand) == mfr_n or _slug_norm(entry_brand) == _slug_norm(mfr):
        return True
    for field in ("brandEn", "brandTh", "brandName"):
        if entry.get(field) and _norm(str(entry[field])) == mfr_n:
            return True
    brands = catalog.get("brands")
    brand_entry = brands.get(entry_brand) if isinstance(brands, dict) else None
    if isinstance(brand_entry, dict):
        for field in ("slug", "nameEn", "nameTh"):
            if brand_entry.get(field) and _norm(str(brand_entry[field])) == mfr_n:
                return True
        for alias in brand_entry.get("aliases") or []:
            if _norm(str(alias)) == mfr_n:
                return True
    return False


def resolve_join_key(packet: Dict[str, Any], catalog: Dict[str, Any],
                     universe_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Resolve one packet's candidate_key into the canonical join key.

    Returns {ok: True, join_key, matched_via, alias_evidence, candidate_id} or
            {ok: False, reason, candidate_id} (→ join_errors, no assembly row).
    """
    candidate_key = packet.get("candidate_key") or ""
    packet_id = packet.get("packet_id")
    parts = [p.strip() for p in str(candidate_key).split("|")]
    while len(parts) < 4:
        parts.append("")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return {"ok": False, "reason": "malformed_candidate_key", "candidate_id": packet_id}

    mfr, model_display, generation, variant_slug = parts[0], parts[1], parts[2], parts[3]
    u_path = universe_path or str(DEFAULT_UNIVERSE)
    universe_record = _universe_index(u_path).get(_key4(mfr, model_display, generation, variant_slug))
    catalog_hit = _catalog_lookup(model_display, catalog)

    if universe_record is None and catalog_hit is None:
        # display-string-only: matches neither evidence universe nor alias catalog
        return {
            "ok": False,
            "reason": f"display_string_only: '{model_display}' absent from identity universe (CONFIRMED_*) and alias catalog",
            "candidate_id": packet_id,
        }

    if universe_record is None and catalog_hit is not None:
        entry_hit, _via_hit = catalog_hit
        if not _brand_agrees(mfr, entry_hit, catalog):
            # sibling-brand collision: same display/alias under another OEM
            return {
                "ok": False,
                "reason": (
                    f"cross_brand_collision: display '{model_display}' maps to catalog brand "
                    f"'{entry_hit.get('brandSlug')}' but packet manufacturer is '{mfr}'"
                ),
                "candidate_id": packet_id,
            }

    matched_via = "identity_universe" if universe_record else "alias_catalog"
    alias_evidence = None
    if universe_record is not None:
        alias_evidence = {
            "universe_record": {
                "manufacturer": universe_record.get("manufacturer"),
                "model": universe_record.get("model"),
                "variant": universe_record.get("variant"),
                "identity_level": universe_record.get("identity_level"),
                "status": universe_record.get("status"),
            },
            "sources": universe_record.get("sources") or [],
        }

    # canonical slugs: identity universe record is canonical; alias catalog
    # enriches where present (and is the fallback when only the catalog hit)
    if universe_record is not None:
        manufacturer_slug = _slug_norm(universe_record.get("manufacturer") or mfr)
        model_slug = _slug_norm(universe_record.get("model") or model_display)
        variant_out = _slug_norm(universe_record.get("variant") or "") or None
        if variant_out is None and variant_slug:
            variant_out = _slug_norm(variant_slug)
    else:
        entry, via = catalog_hit or ({}, "slug")
        manufacturer_slug = entry.get("brandSlug") or _slug_norm(mfr)
        model_slug = entry.get("slug")
        variant_out = _slug_norm(variant_slug) or None
        matched_via = f"alias_catalog+{via}"

    # alias catalog enrichment on top of the identity record — ONLY when the
    # catalog entry provably belongs to the packet's manufacturer; a
    # cross-brand hit is recorded as a rejected enrichment, never applied
    if universe_record is not None and catalog_hit is not None:
        entry, via = catalog_hit
        if _brand_agrees(mfr, entry, catalog):
            if entry.get("slug"):
                model_slug = entry.get("slug")
            matched_via = f"identity_universe+{via}"
        elif alias_evidence is not None:
            alias_evidence["catalog_enrichment"] = (
                f"rejected_cross_brand:{entry.get('brandSlug')}"
            )

    join_key = {
        "manufacturer_slug": manufacturer_slug,
        "model_slug": model_slug,
        "variant_slug": variant_out,
        "model_year": None,  # packets carry no year (generation_context empty) — disclosed
    }
    return {
        "ok": True,
        "join_key": join_key,
        "matched_via": matched_via,
        "alias_evidence": alias_evidence,
        "candidate_id": packet_id,
    }


def join_key_string(join_key: Dict[str, Any]) -> str:
    return "|".join(
        str(join_key.get(k) or "")
        for k in ("manufacturer_slug", "model_slug", "variant_slug", "model_year")
    )


def canonical_id_for(join_key: Dict[str, Any]) -> str:
    """Deterministic canonical id derived ONLY from the resolved join key."""
    return "CAN-" + hashlib.sha256(join_key_string(join_key).encode("utf-8")).hexdigest()[:16]
