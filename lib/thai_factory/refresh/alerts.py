"""
§94 alerting — signal, not noise.

ALLOWLIST (alert ONLY on):
  - tracked price change                      PRICE_CHANGE
  - model/variant added or removed            MODEL_VARIANT_ADDED_REMOVED
  - new conflict record                       NEW_CONFLICT
  - hash/provenance verification failure      PROVENANCE_FAILURE
  - source state transition reachable→blocked SOURCE_STATE_TRANSITION
  - promotion-gate failure                    PROMOTION_GATE_FAILURE

NEVER alert on: unchanged capture, repeated known blocker, expected ladder
outcome.

Event identity is content-derived (sha256 over the canonical event payload),
so the same event emitted in any later run is deduplicated — alerting is
deterministic by event identity (test O).
"""
import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ALLOWLIST = {
    "PRICE_CHANGE",
    "MODEL_VARIANT_ADDED_REMOVED",
    "NEW_CONFLICT",
    "PROVENANCE_FAILURE",
    "SOURCE_STATE_TRANSITION",
    "PROMOTION_GATE_FAILURE",
}


def is_allowlisted(event_type: str) -> bool:
    return event_type in ALLOWLIST


def event_id(event: Dict) -> str:
    """Deterministic identity: same content → same id, key order irrelevant."""
    payload = {k: v for k, v in event.items() if k not in ("event_id", "run_id", "created_at")}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def existing_event_ids(path: Path) -> set:
    p = Path(path)
    if not p.exists():
        return set()
    ids = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("event_id"):
            ids.add(row["event_id"])
    return ids


def append_events(
    path: Path,
    events: Iterable[Dict],
    run_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> List[str]:
    """
    Append allowlisted events that were not seen before.
    Returns the event ids actually written (deduped ones are dropped).
    """
    path = Path(path)
    seen = existing_event_ids(path)
    accepted: List[str] = []
    rows = []
    for event in events:
        if not is_allowlisted(event.get("type", "")):
            continue
        eid = event_id(event)
        if eid in seen:
            continue
        seen.add(eid)
        row = dict(event)
        row["event_id"] = eid
        if run_id:
            row["run_id"] = run_id
        if created_at:
            row["created_at"] = created_at
        rows.append(row)
        accepted.append(eid)
    if rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")
            fh.flush()
    return accepted
