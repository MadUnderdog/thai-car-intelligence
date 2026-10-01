"""
Deterministic capture classification (§94 Idempotency) — pure functions.

  same sha                                  → UNCHANGED
  new sha + identical extracted output      → CONTENT_CHANGED_OUTPUT_UNCHANGED
  new sha + different output                → CHANGED (+ field-level diffs)
  no previous state                         → FIRST_CAPTURE (baseline, no diff)

Outputs are canonicalized (sorted-key JSON) so two runs over the same bytes
produce byte-identical observation sets (§94 / test J).
"""
import hashlib
import json
from typing import Any, Dict, List, Optional

STATUS_UNCHANGED = "UNCHANGED"
STATUS_CONTENT_ONLY = "CONTENT_CHANGED_OUTPUT_UNCHANGED"
STATUS_CHANGED = "CHANGED"
STATUS_FIRST = "FIRST_CAPTURE"


def canonical_output(output: Any) -> Dict:
    """Return the canonical (sorted, JSON-safe) form of an extracted output."""
    return json.loads(json.dumps(output, sort_keys=True, ensure_ascii=False, default=str))


def output_hash(output: Any) -> str:
    blob = json.dumps(canonical_output(output), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def sha_of_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _flatten(value: Any, prefix: str = "") -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    if isinstance(value, dict):
        for key in sorted(value):
            flat.update(_flatten(value[key], f"{prefix}.{key}" if prefix else str(key)))
    else:
        flat[prefix] = value
    return flat


def _set_diff(prev: Any, new: Any, entity: str) -> List[Dict]:
    """Membership diff for list-valued fields (e.g. output['models'])."""
    prev_set = set(prev or [])
    new_set = set(new or [])
    diffs = []
    for name in sorted(new_set - prev_set):
        diffs.append({
            "entity": entity,
            "field": f"membership:{name}",
            "old_value": "absent",
            "new_value": "present",
        })
    for name in sorted(prev_set - new_set):
        diffs.append({
            "entity": entity,
            "field": f"membership:{name}",
            "old_value": "present",
            "new_value": "absent",
        })
    return diffs


def classify_capture(
    prev_sha: Optional[str],
    prev_output: Optional[Dict],
    new_sha: str,
    new_output: Any,
) -> Dict:
    """
    Classify one capture against the previous accepted state.

    Returns:
      {
        status: FIRST_CAPTURE | UNCHANGED | CONTENT_CHANGED_OUTPUT_UNCHANGED | CHANGED,
        field_diffs: [{entity, field, old_value, new_value}],
        set_diffs:   {added: [...], removed: [...]},
        observations: [canonical observation rows, stable order],
      }

    `entity` for scalar price fields is the leaf owner under `prices.*`
    (e.g. prices.<variant> → variant key); list membership diffs use the list
    key ('models') as entity.
    """
    if prev_sha is None:
        return {
            "status": STATUS_FIRST,
            "field_diffs": [],
            "set_diffs": {"added": [], "removed": []},
            "observations": _observations(new_output),
        }

    if prev_sha == new_sha:
        return {
            "status": STATUS_UNCHANGED,
            "field_diffs": [],
            "set_diffs": {"added": [], "removed": []},
            "observations": _observations(new_output),
        }

    prev_canon = canonical_output(prev_output if prev_output is not None else {})
    new_canon = canonical_output(new_output)
    if prev_canon == new_canon:
        return {
            "status": STATUS_CONTENT_ONLY,
            "field_diffs": [],
            "set_diffs": {"added": [], "removed": []},
            "observations": _observations(new_output),
        }

    field_diffs: List[Dict] = []
    set_diffs: Dict[str, List] = {"added": [], "removed": []}

    prev_flat = _flatten(prev_canon)
    new_flat = _flatten(new_canon)
    for path in sorted(set(prev_flat) | set(new_flat)):
        old = prev_flat.get(path)
        new = new_flat.get(path)
        if old == new:
            continue
        head = path.split(".", 1)[0]
        if head == "models" and isinstance(old, list) and isinstance(new, list):
            membership = _set_diff(old, new, "models")
            field_diffs.extend(membership)
            set_diffs["added"].extend(
                d["field"].split(":", 1)[1] for d in membership if d["new_value"] == "present"
            )
            set_diffs["removed"].extend(
                d["field"].split(":", 1)[1] for d in membership if d["new_value"] == "absent"
            )
            continue
        if isinstance(old, list) and isinstance(new, list):
            # non-model list fields: treat as membership too (deterministic)
            membership = _set_diff(old, new, head)
            field_diffs.extend(membership)
            continue
        entity = path.split(".", 1)[1] if head == "prices" and "." in path else path
        field_diffs.append({
            "entity": entity,
            "field": path,
            "old_value": old,
            "new_value": new,
        })

    return {
        "status": STATUS_CHANGED if field_diffs else STATUS_CONTENT_ONLY,
        "field_diffs": field_diffs,
        "set_diffs": {
            "added": sorted(set(set_diffs["added"])),
            "removed": sorted(set(set_diffs["removed"])),
        },
        "observations": _observations(new_output),
    }


def _observations(output: Any) -> List[Dict]:
    """Stable, byte-identical observation rows for one extracted output."""
    canon = canonical_output(output)
    if isinstance(canon, dict):
        rows = [{"key": k, "value": canon[k]} for k in sorted(canon)]
    elif isinstance(canon, list):
        rows = [{"index": i, "value": v} for i, v in enumerate(canon)]
    else:
        rows = [{"value": canon}]
    return rows
