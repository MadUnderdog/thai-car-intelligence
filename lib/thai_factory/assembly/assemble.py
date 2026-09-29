"""
P119 — field-level multi-source assembly (§96) over ACCEPTED EvidencePackets.

Pipeline (deterministic, offline, packet-only):

  ACCEPTED packets
    → join_keys.resolve_join_key (alias-backed; display-string-only rejected)
    → per-observation provenance mapping (§96 field-level shape)
    → contamination guard (fail closed):
         R2 within-packet artifact↔sha coherence
         R4 artifact sidecar sha256 must equal the observation's sha
         R5 price locator quote must re-resolve to the value
    → per (join_key, field) trust policy:
         ≥2 distinct values → ConflictRecord with EVERY side's full evidence;
           same tier + strictly newest date → SELECTED_SAME_TIER_NEWEST
           different tiers → SELECTED_HIGHER_TIER (lower tier retained)
           tie (same tier+date) → QUARANTINED (no value emitted)
    → assembled records {candidate_id, candidate_ids, canonical_id: None,
         join_key, fields{field → FieldProvenance}, unresolved_fields}

reconcile() adds canonical_id (deterministic from the join key) WITHOUT ever
replacing candidate_id. Output JSONL is sorted + sort_keys → byte-identical
reruns (A/K).
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .join_keys import canonical_id_for, join_key_string, resolve_join_key
from .models import TIER_RANK, field_name, observation_to_provenance, obs_value
from .report import write_report  # noqa: F401  (re-exported for callers/tests)

CATEGORIES = ("identity", "price", "spec")


class AssemblyResult:
    def __init__(self):
        self.records: List[Dict[str, Any]] = []
        self.conflicts: List[Dict[str, Any]] = []
        self.join_errors: List[Dict[str, Any]] = []
        self.failures: List[Dict[str, Any]] = []
        self.stats: Dict[str, Any] = {}


# ── contamination guard ─────────────────────────────────────────────────────
def _resolve_artifact_file(artifact: str, fixtures_dir: str) -> Optional[Path]:
    if not artifact or not fixtures_dir:
        return None
    root = Path(fixtures_dir)
    if not root.exists():
        return None
    for candidate in (root / "oem-artifacts" / artifact, root / "media-artifacts" / artifact, root / artifact):
        if candidate.exists():
            return candidate
    # basename search (one level of subdirectories)
    for sub in root.iterdir() if root.is_dir() else []:
        if sub.is_dir():
            hit = sub / artifact
            if hit.exists():
                return hit
    return None


def _sidecar_sha(artifact_file: Path) -> Optional[str]:
    side = Path(str(artifact_file) + ".prov.json")
    if not side.exists():
        return None
    try:
        return json.loads(side.read_text(encoding="utf-8")).get("sha256")
    except json.JSONDecodeError:
        return None


def validate_observation(category: str, obs: Dict[str, Any], packet: Dict[str, Any],
                         packet_artifact_shas: Dict[str, str], fixtures_dir: str) -> List[str]:
    """Return a list of reasons; empty list = observation passes (fail-closed contract)."""
    reasons: List[str] = []
    if not obs.get("sha256"):
        reasons.append("missing_sha256")
    if not obs.get("artifact"):
        reasons.append("missing_artifact")
    if not obs.get("source_url"):
        reasons.append("missing_source_url")
    if obs.get("locator") is None:
        reasons.append("missing_locator")

    artifact = obs.get("artifact")
    sha = obs.get("sha256")
    # R2: within one packet the same artifact must carry ONE sha
    if artifact and sha:
        known = packet_artifact_shas.get(artifact)
        if known is None:
            packet_artifact_shas[artifact] = sha
        elif known != sha:
            reasons.append("packet_artifact_sha_incoherent")

    # R4: sidecar of the declared artifact must match the observation sha
    if artifact and sha:
        artifact_file = _resolve_artifact_file(artifact, fixtures_dir)
        if artifact_file is not None:
            side = _sidecar_sha(artifact_file)
            if side is not None and side != sha:
                reasons.append("artifact_sidecar_sha_mismatch")

    # R5: price locator quote must re-resolve to the value (normalised:
    # real quotes are formatted, e.g. "฿3,499,000 +")
    if category == "price":
        quote = str((obs.get("locator") or {}).get("quote") or "")
        value = obs_value("price", obs)
        if quote and value is not None:
            if isinstance(value, float) and value.is_integer():
                value_str = str(int(value))
            else:
                value_str = str(value)
            normalised_quote = quote.replace(",", "").replace(" ", "")
            if value_str not in normalised_quote:
                reasons.append("locator_quote_does_not_resolve_value")

    return reasons


# ── trust policy ────────────────────────────────────────────────────────────
def _rank(prov: Dict[str, Any]):
    return (
        TIER_RANK.get(prov.get("trust_tier"), 0),
        1 if prov.get("verified") else 0,
        _date_key(prov.get("observed_at")),
        str(prov.get("packet_id") or ""),
        str(prov.get("obs_id") or ""),
    )


def _date_key(observed_at: Any) -> datetime:
    if not observed_at:
        return datetime.min
    try:
        return datetime.fromisoformat(str(observed_at).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.min


def _conflict_sides(provs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Full evidence per side, deterministically ordered."""
    return sorted(
        [
            {
                "packet_id": p["packet_id"],
                "obs_id": p["obs_id"],
                "value": p["value"],
                "trust_tier": p["trust_tier"],
                "source_id": p["source_id"],
                "artifact_sha256": p["artifact_sha256"],
                "locator": p["locator"],
                "observed_at": p["observed_at"],
            }
            for p in provs
        ],
        key=lambda s: (str(s["packet_id"]), str(s["obs_id"])),
    )


def resolve_field(group: List[Dict[str, Any]], join_key: Dict[str, Any], field: str):
    """
    Returns (selected_or_None, conflict_or_None).
    Conflict ALWAYS retains every side; QUARANTINED selects nothing.
    """
    distinct_values = {json.dumps(p["value"], sort_keys=True, default=str) for p in group}
    ordered = sorted(group, key=_rank, reverse=True)

    if len(distinct_values) == 1:
        return ordered[0], None

    tiers = {p["trust_tier"] for p in group}
    cross_tier = len(tiers) > 1

    top_tier = max(TIER_RANK.get(p["trust_tier"], 0) for p in group)
    top = [p for p in group if TIER_RANK.get(p["trust_tier"], 0) == top_tier]
    top_values = {json.dumps(p["value"], sort_keys=True, default=str) for p in top}
    top_ordered = sorted(top, key=_rank, reverse=True)

    if len(top_values) == 1:
        selected = top_ordered[0]
        status = "SELECTED_HIGHER_TIER" if cross_tier else "SELECTED_SAME_TIER_NEWEST"
    else:
        # same-tier sub-policy: strictly newest dated observation wins
        dates = [_date_key(p.get("observed_at")) for p in top]
        newest = max(dates)
        if dates.count(newest) > 1 or newest == datetime.min:
            selected = None
            status = "QUARANTINED"
        else:
            winners = [p for p in top if _date_key(p.get("observed_at")) == newest]
            distinct_winners = {json.dumps(p["value"], sort_keys=True, default=str) for p in winners}
            if len(distinct_winners) > 1:
                selected, status = None, "QUARANTINED"
            else:
                selected = sorted(winners, key=_rank, reverse=True)[0]
                status = "SELECTED_HIGHER_TIER" if cross_tier else "SELECTED_SAME_TIER_NEWEST"

    conflict = {
        "join_key": join_key,
        "field": field,
        "status": status,
        "selected": selected,
        "sides": _conflict_sides(group),
        "policy": (
            "same_tier_newest_dated_wins; tie → QUARANTINED; across_tier higher_tier_wins "
            "(official_verified > secondary_verified > reference > inferred); conflict never erased"
        ),
    }
    if status == "QUARANTINED":
        conflict["selected"] = None
    return selected, conflict


# ── main entry ──────────────────────────────────────────────────────────────
def assemble(packets: List[Dict[str, Any]], catalog: Dict[str, Any],
             fixtures_dir: Optional[str] = None) -> AssemblyResult:
    result = AssemblyResult()
    accepted = [p for p in packets if p.get("status") == "ACCEPTED"]
    quarantined_packets = [p for p in packets if p.get("status") != "ACCEPTED"]

    groups: Dict[tuple, List[Dict[str, Any]]] = {}
    join_by_key: Dict[tuple, Dict[str, Any]] = {}
    packets_per_key: Dict[tuple, List[str]] = {}

    for packet in accepted:
        join = resolve_join_key(packet, catalog)
        if not join.get("ok"):
            result.join_errors.append({
                "packet_id": packet.get("packet_id"),
                "candidate_key": packet.get("candidate_key"),
                "reason": join.get("reason"),
            })
            continue
        join_key = join["join_key"]
        jkey = join_key_string(join_key)
        join_by_key[jkey] = join_key
        packets_per_key.setdefault(jkey, []).append(packet.get("packet_id"))

        packet_artifact_shas: Dict[str, str] = {}
        observations = packet.get("observations") or {}

        for category in CATEGORIES:
            for obs in observations.get(category) or []:
                field = field_name(category, obs)
                reasons = validate_observation(category, obs, packet, packet_artifact_shas, fixtures_dir or "")
                if reasons:
                    result.failures.append({
                        "packet_id": packet.get("packet_id"),
                        "obs_id": obs.get("obs_id"),
                        "field": field,
                        "reasons": reasons,
                    })
                    continue
                prov = observation_to_provenance(category, obs, packet, field)
                groups.setdefault((jkey, field), []).append(prov)

    # policy per (join_key, field)
    record_fields: Dict[str, Dict[str, Any]] = {}
    unresolved: Dict[str, List[str]] = {}
    for (jkey, field), provs in sorted(groups.items()):
        join_key = join_by_key[jkey]
        selected, conflict = resolve_field(provs, join_key, field)
        if conflict:
            result.conflicts.append(conflict)
        if selected is None:
            unresolved.setdefault(jkey, []).append(str(field))
        else:
            record_fields.setdefault(jkey, {})[field] = selected

    for jkey in sorted(join_by_key):
        join_key = join_by_key[jkey]
        packet_ids = sorted(set(packets_per_key.get(jkey, [])))
        if not record_fields.get(jkey) and not unresolved.get(jkey):
            # every observation of this join failed validation or none existed
            if not any(f["packet_id"] in packet_ids for f in result.failures):
                continue
        result.records.append({
            "candidate_id": packet_ids[0],
            "candidate_ids": packet_ids,
            "canonical_id": None,  # only reconcile() may set it (contract H)
            "join_key": join_key,
            "fields": record_fields.get(jkey, {}),
            "unresolved_fields": sorted(unresolved.get(jkey, [])),
        })

    result.records.sort(key=lambda r: (join_key_string(r["join_key"]), r["candidate_id"]))
    result.conflicts.sort(key=lambda c: (join_key_string(c["join_key"]), c["field"], c["status"]))
    result.join_errors.sort(key=lambda e: str(e.get("packet_id")))
    result.failures.sort(key=lambda f: (str(f.get("packet_id")), str(f.get("obs_id"))))

    result.stats = {
        "packets_in": len(packets),
        "packets_accepted": len(accepted),
        "packets_quarantined_input": len(quarantined_packets),
        "records": len(result.records),
        "fields_assembled": sum(len(r["fields"]) for r in result.records),
        "conflicts": len(result.conflicts),
        "quarantines": sum(1 for c in result.conflicts if c["status"] == "QUARANTINED"),
        "join_errors": len(result.join_errors),
        "validation_failures": len(result.failures),
    }
    return result


def reconcile(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Assign deterministic canonical_id per join key; candidate_id always kept."""
    out = []
    for rec in records:
        new_rec = dict(rec)
        new_rec["canonical_id"] = canonical_id_for(rec["join_key"])
        new_rec["candidate_id"] = rec["candidate_id"]
        out.append(new_rec)
    return out


def write_outputs(result: AssemblyResult, out_dir) -> Dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    def dump(name: str, rows: List[Dict[str, Any]]) -> None:
        path = out_dir / name
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")
        paths[name] = str(path)

    dump("assembled_records.jsonl", result.records)
    dump("conflicts.jsonl", result.conflicts)
    dump("join_errors.jsonl", result.join_errors)
    dump("validation_failures.jsonl", result.failures)
    return paths
