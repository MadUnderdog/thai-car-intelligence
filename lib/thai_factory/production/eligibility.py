"""
P120 — packet eligibility for production promotion (contract 1, 5, 6, G-gates).

Pure function over packets + ledgers + evidence files: NO database access, NO
writes. Every refusal carries an explicit reason; a packet is promotable only
when its status is ACCEPTED, its join resolves through the evidence-backed
identity path without a cross-brand collision, every cited observation is
intact (sha + locator + sidecar hash) and ACQUISITION_VERIFIED, and its facts
are not already promoted (p114 ledger ∪ production ledger).

The frozen AcceptanceRunner stays the acceptance authority: its historical
verdict is the packet status recorded by the packet pass; the worker re-runs
the runner per promoted fact through p114's `record()` (runner.evaluate
before every ledger write).
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

REFUSAL_REASONS = (
    "STATUS_NOT_ACCEPTED",
    "CONFLICT_QUARANTINED",
    "RUNNER_REJECTED",
    "LEGACY_UNVERIFIED",
    "EVIDENCE_TAMPERED",
    "CROSS_BRAND_COLLISION",
    "IDENTITY_NOT_RESOLVABLE",
    "CONFLICT_QUARANTINED",
    "ALREADY_PROMOTED",
    "DB_ROW_QUARANTINED",
)


def _sidecar_sha_ok(artifact: str, obs_sha: str, fixtures_dir: str) -> Optional[bool]:
    """True/False when the artifact file is resolvable, None when not present."""
    if not artifact or not fixtures_dir:
        return None
    root = Path(fixtures_dir)
    for candidate in (root / "oem-artifacts" / artifact,
                      root / "media-artifacts" / artifact,
                      root / artifact):
        if candidate.exists():
            side = Path(str(candidate) + ".prov.json")
            if side.exists():
                try:
                    side_sha = json.loads(side.read_text(encoding="utf-8")).get("sha256")
                except json.JSONDecodeError:
                    return False
                return side_sha == obs_sha
            return None
    return None


def check_observation(obs: Dict[str, Any], fixtures_dir: str) -> List[Dict[str, str]]:
    """Per-fact evidence gate — fail closed."""
    refusals: List[Dict[str, str]] = []
    if obs.get("provenance_state") != "ACQUISITION_VERIFIED":
        refusals.append({"reason": "LEGACY_UNVERIFIED",
                         "detail": f"provenance_state={obs.get('provenance_state')}"})
        return refusals          # an unverified observation never promotes, full stop
    if not obs.get("sha256"):
        refusals.append({"reason": "EVIDENCE_TAMPERED", "detail": "missing sha256"})
    if obs.get("locator") is None:
        refusals.append({"reason": "EVIDENCE_TAMPERED", "detail": "missing locator"})
    if not obs.get("source_url"):
        refusals.append({"reason": "EVIDENCE_TAMPERED", "detail": "missing source_url"})
    rd = obs.get("runner_decision")
    if rd is not None and str(rd).upper() != "ACCEPTED":
        refusals.append({"reason": "RUNNER_REJECTED",
                         "detail": f"runner_decision={rd}"})
    if obs.get("sha256"):
        ok = _sidecar_sha_ok(obs.get("artifact"), obs["sha256"], fixtures_dir)
        if ok is False:
            refusals.append({"reason": "EVIDENCE_TAMPERED",
                             "detail": f"sidecar sha mismatch for {obs.get('artifact')}"})
    return refusals


def evaluate_packets(packets: Iterable[Dict[str, Any]],
                     promoted_facts: Set[Tuple[str, str]],
                     *,
                     fixtures_dir: str = "",
                     catalog: Optional[Dict[str, Any]] = None,
                     universe_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Packet-level + fact-level eligibility with explicit refusal reasons."""
    import sys
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root / "lib") not in sys.path:
        sys.path.insert(0, str(repo_root / "lib"))
    from thai_factory.assembly.join_keys import resolve_join_key

    results = []
    for packet in packets:
        pid = packet.get("packet_id")
        refusals: List[Dict[str, str]] = []
        facts: List[Dict[str, Any]] = []

        status = str(packet.get("status") or "")
        if status != "ACCEPTED":
            blob = json.dumps(packet.get("policy") or {}, default=str).lower()
            if "conflict" in blob or "quarantine" in blob:
                refusals.append({"reason": "CONFLICT_QUARANTINED",
                                 "detail": f"status={status}, unresolved conflict/quarantine"})
            else:
                refusals.append({"reason": "STATUS_NOT_ACCEPTED",
                                 "detail": f"status={status}"})

        # evidence-backed join: a cross-brand collision never promotes.
        # A display-string-only miss is NOT a refusal here — plain
        # resolvability is decided by the worker's DB identity check; only
        # proof of a sibling-brand collision (or a malformed key) refuses.
        if catalog is not None:
            join = resolve_join_key(packet, catalog, universe_path=universe_path)
            if not join.get("ok"):
                reason = str(join.get("reason") or "")
                if reason.startswith("cross_brand_collision"):
                    refusals.append({"reason": "CROSS_BRAND_COLLISION",
                                     "detail": reason})
                elif reason.startswith("malformed_candidate_key"):
                    refusals.append({"reason": "IDENTITY_NOT_RESOLVABLE",
                                     "detail": reason})

        # per-group facts
        groups = packet.get("observations") or {}
        packet_has_promotable_fact = False
        for group in ("identity", "price", "spec"):
            obs_list = groups.get(group) or []
            if not obs_list:
                continue
            group_refusals: List[Dict[str, str]] = []
            for obs in obs_list:
                group_refusals.extend(check_observation(obs, fixtures_dir))
            if (pid, group) in promoted_facts:
                group_refusals.append({"reason": "ALREADY_PROMOTED",
                                       "detail": f"fact {group} present in promotion ledgers"})
            # dedupe by reason
            seen = set()
            uniq = []
            for r in group_refusals:
                if r["reason"] not in seen:
                    seen.add(r["reason"])
                    uniq.append(r)
            if uniq:
                refusals.extend(uniq)
            else:
                packet_has_promotable_fact = True
                facts.append({"fact": group, "obs": obs_list})

        eligible = (not refusals) and packet_has_promotable_fact
        results.append({"packet_id": pid, "eligible": eligible,
                        "refusals": refusals, "facts": facts})
    return results


def load_promoted_facts(*ledger_paths: str) -> Set[Tuple[str, str]]:
    """(packet_id, fact) pairs already promoted, from every promotion ledger."""
    facts: Set[Tuple[str, str]] = set()
    for path in ledger_paths:
        if not path or not os.path.exists(path):
            continue
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for entry in data.get("entries") or []:
            facts.add((entry.get("packet_id"), entry.get("fact") or "identity"))
    return facts
