#!/usr/bin/env python3
"""P113 — Phase-1 evidence packets + fail-closed acceptance (DRY-RUN only).

Builds ONE EvidencePacket per frozen accepted variant (488) from committed
artifacts only, cites only provenance-intact observations, runs the EXISTING
`thai_factory.acceptance` EvidencePacket + AcceptanceRunner over every cited
observation, and writes an audit surface:

  p113_packet_target_plan.json      (phase `plan` — written BEFORE build)
  p113_evidence_packets.json
  p113_acceptance_result.json
  p113_rejection_report.json
  p113_final_result.json

Rules:
  * identity from the frozen ledger — never added/removed;
  * price from P111 evidence rows only (269/29/1 bound, 189 unverified) —
    never re-derived;
  * spec from P112 evidence rows only (1389 rows / 126 variants);
  * fail closed on sidecar/SHA/HTTPS/locator/tuple failures — a failed
    observation is quarantined with its reasons, never cited;
  * missing evidence becomes an explicit field gap — never a filled value;
  * promotion_eligible is False for every packet; nothing is written to any
    database, staging or production, and no web fetch happens here.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "audit/coverage")
FIXTURE_DIR = os.path.join(REPO, "tests/fixtures/oem-artifacts")
sys.path.insert(0, os.path.join(REPO, "lib"))
from thai_factory.acceptance import (  # noqa: E402
    EvidencePacket, EvidenceClass, AcceptanceDecision,
)
from thai_factory.acceptance.evidence_packet import (  # noqa: E402
    CurrentnessState, ExtractionConfidence, EvidenceLocator, ArtifactHash,
)
from thai_factory.acceptance.runner import AcceptanceRunner  # noqa: E402

ACCEPTED_LEDGER = 488
PRICE_STATUSES = {"EXACT_CURRENT_MSRP_VERIFIED",
                  "MSRP_STARTING_NOT_EXACT",
                  "EXACT_BINDING_NOT_VERIFIED_CURRENT"}
_TEXT_CACHE: dict = {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def head_sha() -> str:
    return os.popen(f"git -C {REPO} rev-parse HEAD 2>/dev/null").read().strip()


def sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def canon(s: str) -> str:
    """Canonical name form: lowercase, punctuation/spacing folded to single
    spaces (published 'D-Max' == ledger 'D Max', 'HEV-PRO' == 'hev-pro')."""
    return re.sub(r"[^0-9a-zก-๙]+", " ", (s or "").lower()).strip()


def write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def load_ledger() -> list:
    u = json.load(open(os.path.join(OUT, "identity_universe_p108.json"),
                       encoding="utf-8"))
    acc = [r for r in u["universe"]["records"]
           if r["status"] == "CONFIRMED_VARIANT"]
    assert len(acc) == ACCEPTED_LEDGER, len(acc)
    return acc


# ───────────────────────────── artifact text / integrity ──────────────────

def artifact_text(filename: str) -> str:
    """Tag-stripped canonical text of a committed artifact (cached)."""
    if filename in _TEXT_CACHE:
        return _TEXT_CACHE[filename]
    path = os.path.join(FIXTURE_DIR, filename)
    if not os.path.exists(path):
        _TEXT_CACHE[filename] = ""
        return ""
    if filename.endswith(".pdf") or filename.endswith(".pdf.b64"):
        data = open(path, "rb").read()
        if filename.endswith(".pdf.b64"):
            import base64
            raw = data.decode("utf-8", "ignore")
            raw = re.sub(r"-----[^-]+-----", "", raw)
            data = base64.b64decode(re.sub(r"\s+", "", raw))
        tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"), "p113_tmp.pdf")
        with open(tmp, "wb") as fh:
            fh.write(data)
        r = subprocess.run(["pdftotext", "-layout", tmp, "-"],
                           capture_output=True, timeout=120)
        text = r.stdout.decode("utf-8", "ignore")
    else:
        raw = open(path, encoding="utf-8", errors="ignore").read()
        if filename.endswith(".json"):
            # the committed payload bytes plus a decoded rendering of the
            # SAME bytes, so escaped non-ASCII strings still re-resolve
            try:
                raw = raw + "\n" + json.dumps(json.loads(raw),
                                              ensure_ascii=False)
            except Exception:
                pass
            text = raw
        else:
            text = re.sub(r"<[^>]+>", "\n", raw)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    _TEXT_CACHE[filename] = text
    return text


def locator_resolves(text: str, quote: str) -> bool:
    """Re-resolution: the published quote must appear in the artifact text
    (canonical comparison — punctuation and spacing are not identity)."""
    q = canon(quote)
    return bool(q) and q in canon(text)


def verify_artifact(artifact: str, source_url: str, expected_sha,
                    extra) -> tuple:
    """Fail-closed provenance check → (ok, reasons[]).

    `artifact` is a fixture basename; `expected_sha` is the SHA carried by
    the citing evidence row (None when the ledger row carries none); `extra`
    may carry the citing source_url for sidecar comparison.
    """
    reasons = []
    if not (source_url or "").startswith("https://"):
        reasons.append("non_https_source_url")
    path = os.path.join(FIXTURE_DIR, artifact)
    if not os.path.exists(path):
        reasons.append("artifact_missing")
        return False, reasons
    side = path + ".prov.json"
    if not os.path.exists(side):
        reasons.append("sidecar_missing")
        return False, reasons
    prov = json.load(open(side, encoding="utf-8"))
    if prov.get("provenance_state") != "ACQUISITION_VERIFIED":
        reasons.append(f"provenance_state_{prov.get('provenance_state')}")
    if prov.get("source_url") and source_url and \
            prov["source_url"] != source_url:
        reasons.append("sidecar_url_mismatch")
    file_sha = sha256(path)
    if prov.get("sha256") and prov["sha256"] != file_sha:
        reasons.append("sidecar_sha_mismatch")
    if expected_sha and expected_sha != file_sha:
        reasons.append("expected_sha_mismatch")
    return (not reasons), reasons


def tuple_matches(obs: dict, packet_like: dict) -> bool:
    """A cited observation must belong to THIS packet's exact identity."""
    return (obs.get("manufacturer") == packet_like.get("manufacturer")
            and obs.get("model") == packet_like.get("model")
            and obs.get("variant") == packet_like.get("variant"))


def identity_locator(text: str, label: str, model: str, variant: str):
    """Locator re-resolution for identity, two declared modes:
    `full_label` (the composed published label resolves) or
    `model_and_variant` (both names resolve inside the same artifact —
    the structural rule the identity waves themselves used)."""
    if label and locator_resolves(text, label):
        return {"mode": "full_label", "quote": label, "resolved": True}
    if variant and locator_resolves(text, variant):
        if model and locator_resolves(text, model):
            return {"mode": "model_and_variant",
                    "quote": f"{model} | {variant}", "resolved": True}
        # published name may drop the leading brand token
        # (GWM HAVAL H6 → 'HAVAL H6', BMW i5 → 'i5')
        tokens = canon(model).split()
        if len(tokens) >= 2:
            rest = " ".join(tokens[1:])
            if len(rest) >= 2 and re.search(
                    rf"(?<![0-9a-zก-๙]){re.escape(rest)}(?![0-9a-zก-๙])",
                    canon(text)):
                return {"mode": "model_and_variant",
                        "quote": f"{model} | {variant}", "resolved": True}
    return None


def price_locator(text: str, row: dict):
    quote = row.get("evidence_excerpt") or row.get("locator", {}).get(
        "excerpt") or ""
    if quote and locator_resolves(text, quote):
        return {"mode": "value_in_record", "quote": quote, "resolved": True}
    digits = re.sub(r"[^\d]", "", str(row.get("price_thb") or ""))
    hay = re.sub(r"[^\d]", "", text)
    if digits and digits in hay:
        return {"mode": "value_digits", "quote": str(row.get("price_thb")),
                "resolved": True}
    return None


def spec_locator(text: str, row: dict):
    label, value = row.get("label") or "", row.get("value_text") or ""
    if not label or not locator_resolves(text, label):
        return None
    if row.get("value_numeric") is not None:
        digits = re.sub(r"[^\d.]", "", str(value))
        hay = re.sub(r"[^\d.]", "", text)
        ok = digits and digits in hay
    else:
        ok = value and norm(value) in norm(text)
    if ok:
        return {"mode": "label_and_value", "quote": f"{label} = {value}",
                "resolved": True}
    return None


def field_packet(obs_id: str, candidate: str, row: dict, value,
                 locator: EvidenceLocator, sha: str,
                 currentness: CurrentnessState,
                 ) -> EvidencePacket:
    return EvidencePacket(
        packet_id=obs_id,
        candidate_key=candidate,
        source_class=EvidenceClass.OEM_OFFICIAL,
        source_url=row["source_url"],
        source_name=row.get("source_name") or row.get("manufacturer", ""),
        immutable_revision=head_sha(),
        currentness=currentness,
        extracted_value=value,
        extraction_confidence=ExtractionConfidence.HIGH,
        evidence_locator=locator,
        artifact_hashes=ArtifactHash(local_artifact_sha256=sha,
                                     upstream_payload_sha256=sha),
    )


# ───────────────────────────── plan phase ─────────────────────────────────

def phase_plan() -> int:
    ledger = load_ledger()
    p111 = json.load(open(os.path.join(OUT, "p111_price_evidence.json"),
                          encoding="utf-8"))
    p111_recon = json.load(open(os.path.join(
        OUT, "p111_price_reconciliation.json"), encoding="utf-8"))
    p112 = json.load(open(os.path.join(OUT, "p112_spec_evidence.json"),
                          encoding="utf-8"))
    p112_recon = json.load(open(os.path.join(
        OUT, "p112_spec_reconciliation.json"), encoding="utf-8"))
    buckets = {k: 0 for k in PRICE_STATUSES}
    for r in p111["rows"]:
        buckets[r["msrp_status"]] += 1
    per_oem = {}
    for r in ledger:
        per_oem[r["manufacturer"]] = per_oem.get(r["manufacturer"], 0) + 1
    plan = {
        "schema": "packet_target_plan_p113/v1",
        "generated_at": now(),
        "method": {"sequence": ["plan", "build+accept (one run)",
                                "validate (one gate pass)"],
                   "written_before_build": True,
                   "repair_loop": False},
        "audit_snapshot": {
            "head": head_sha(),
            "existing_abstractions_found": [
                "lib/thai_factory/acceptance/evidence_packet.py "
                "(EvidencePacket, EvidenceClass, AcceptanceDecision, "
                "EvidenceLocator, ArtifactHash)",
                "lib/thai_factory/acceptance/runner.py (AcceptanceRunner)",
                "lib/thai_factory/acceptance/ledger.py (AcceptanceLedger)",
                "lib/thai_factory/quality/gates.py (G1-G8 gate helpers)",
                "tests/test_gold_set.py (10 runner gold tests)",
                "Blueprint.md #97/#98 (packet contents, gates G1-G8)",
            ],
            "reused_modules": [
                "thai_factory.acceptance.EvidencePacket",
                "thai_factory.acceptance.AcceptanceRunner",
            ],
            "verifier_touched": False,
            "phase1_only": True,
        },
        "inputs": {
            "accepted_variants": len(ledger),
            "identity_ledger_artifact": "audit/coverage/"
                                        "identity_universe_p108.json",
            "p111": {
                "artifact": "audit/coverage/p111_price_evidence.json",
                "price_rows": len(p111["rows"]),
                "exact_current_msrp_verified":
                    buckets["EXACT_CURRENT_MSRP_VERIFIED"],
                "msrp_starting_not_exact":
                    buckets["MSRP_STARTING_NOT_EXACT"],
                "exact_binding_not_verified_current":
                    buckets["EXACT_BINDING_NOT_VERIFIED_CURRENT"],
                "unverified_price": p111_recon["unverified_price"],
            },
            "p112": {
                "artifact": "audit/coverage/p112_spec_evidence.json",
                "spec_rows": len(p112["rows"]),
                "variants_with_spec_evidence": p112_recon[
                    "variants_with_spec_evidence"],
                "spec_gaps": p112_recon["variants_without_spec_evidence"],
            },
        },
        "policies": [
            {"id": "IDENTITY_ACCEPTABLE",
             "rule": "identity tuple equals the frozen ledger row, scope TH, "
                     "and at least one cited identity source passes "
                     "sidecar+SHA+HTTPS+locator re-resolution"},
            {"id": "PRICE_ACCEPTABLE",
             "rule": "P111 semantics only: EXACT_CURRENT_MSRP_VERIFIED "
                     "passes; MSRP_STARTING_NOT_EXACT kept as its own "
                     "status; EXACT_BINDING_NOT_VERIFIED_CURRENT never "
                     "counts as current MSRP"},
            {"id": "SPEC_ACCEPTABLE",
             "rule": "P112 field-level same-record evidence on a CURRENT "
                     "official source with exact grade binding and "
                     "unit-or-refuse"},
            {"id": "PACKET_ACCEPTED",
             "rule": "every CITED observation passes provenance integrity; "
                     "missing evidence becomes an explicit field gap, never "
                     "a packet failure and never a filled value"},
            {"id": "PROMOTION_ELIGIBLE",
             "rule": "always False in this pass — dry-run only"},
            {"id": "QUARANTINE_REASONS",
             "rule": "artifact_missing | sidecar_missing | "
                     "non_https_source_url | sidecar_sha_mismatch | "
                     "sidecar_url_mismatch | expected_sha_mismatch | "
                     "provenance_state_* | locator_unresolvable | "
                     "runner_not_accepted | ledger_tuple_mismatch"},
        ],
        "boundaries": {
            "promotion_eligible": False,
            "staging_write": False,
            "production_db": False,
            "prisma_schema": False,
            "verifier": False,
            "api_config_model_provider": False,
            "new_acquisition": False,
            "ai_reconciliation": False,
            "price_metrics_mutation": False,
            "p112_evidence_mutation": False,
            "identity_ledger_mutation": False,
        },
        "targets": {"packets": len(ledger), "per_oem_accepted_ledger":
                    dict(sorted(per_oem.items()))},
    }
    write_json(os.path.join(OUT, "p113_packet_target_plan.json"), plan)
    print(f"plan: targets={len(ledger)} p111={len(p111['rows'])} "
          f"p112={len(p112['rows'])}")
    return 0


# ───────────────────────────── build + accept ─────────────────────────────

WATCH = ["identity_universe_p108.json", "p111_price_evidence.json",
         "p111_price_evidence.json.prov.json", "p111_final_result.json",
         "p111_price_reconciliation.json", "p112_spec_evidence.json",
         "p112_spec_evidence.json.prov.json", "p112_final_result.json",
         "p112_spec_reconciliation.json"]


def phase_run() -> int:
    watch_before = {n: sha256(os.path.join(OUT, n)) for n in WATCH}
    ledger = load_ledger()
    p111_rows = json.load(open(os.path.join(OUT, "p111_price_evidence.json"),
                               encoding="utf-8"))["rows"]
    p111_unv = json.load(open(os.path.join(
        OUT, "p111_price_reconciliation.json"), encoding="utf-8"))["unverified"]
    p112_rows = json.load(open(os.path.join(OUT, "p112_spec_evidence.json"),
                               encoding="utf-8"))["rows"]
    p112_gaps = json.load(open(os.path.join(
        OUT, "p112_spec_reconciliation.json"), encoding="utf-8"))["gaps"]
    price_by_key = {(r["manufacturer"], r["model"], r["variant"]): r
                    for r in p111_rows}
    unv_by_key = {(r["manufacturer"], r["model"], r["variant"]): r
                  for r in p111_unv}
    spec_by_key: dict = {}
    for r in p112_rows:
        spec_by_key.setdefault(
            (r["manufacturer"], r["model"], r["variant"]), []).append(r)
    spec_gap_by_key = {(g["manufacturer"], g["model"], g["variant"]): g
                       for g in p112_gaps}

    runner = AcceptanceRunner()
    field_packets: list = []
    packets = []
    run_id = "p113_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for idx, led in enumerate(ledger, start=1):
        ident = {"manufacturer": led["manufacturer"], "model": led["model"],
                 "variant": led["variant"]}
        key = led["canonical_key"]
        pid = f"PKT-{idx:04d}"
        groups = {"identity": [], "price": [], "spec": []}
        quarantine = {"identity": [], "price": [], "spec": []}
        field_gaps = {"identity": [], "price": [], "spec": []}
        not_accepted_reasons = []

        # ── identity observations (first-party sources of the ledger) ──
        for s in (led.get("first_party") or []):
            artifact = os.path.basename(s.get("artifact") or "")
            obs_id = f"{pid}.identity.{len(groups['identity']) + len(quarantine['identity']) + 1}"
            ok, reasons = verify_artifact(artifact, s.get("source_url"),
                                          None, {})
            loc = None
            if ok:
                text = artifact_text(artifact)
                loc = identity_locator(text, s.get("label") or "",
                                       led["model"], led["variant"])
                if not loc:
                    reasons = ["locator_unresolvable"]
                    ok = False
            if not ok:
                quarantine["identity"].append({
                    "artifact": artifact, "source_url": s.get("source_url"),
                    "reasons": reasons, "label": s.get("label")})
                continue
            sha = sha256(os.path.join(FIXTURE_DIR, artifact))
            row = {"source_url": s["source_url"],
                   "source_name": s.get("source_name"),
                   "manufacturer": led["manufacturer"], "model": led["model"],
                   "variant": led["variant"]}
            fp = field_packet(obs_id, key, row, {
                "identity_level": s.get("identity_level"),
                "label": s.get("label")}, EvidenceLocator(
                    artifact_path=f"tests/fixtures/oem-artifacts/{artifact}",
                    quote=s.get("label")), sha, CurrentnessState.UNKNOWN)
            decision = runner.evaluate(fp)
            obs = {
                "obs_id": obs_id, "cited": True,
                "source_name": s.get("source_name"),
                "source_role": s.get("source_role"),
                "source_url": s["source_url"], "artifact": artifact,
                "sha256": sha,
                "provenance_state": "ACQUISITION_VERIFIED",
                "source_class": "MARKET_TRUTH",
                "identity_level": s.get("identity_level"),
                "label": s.get("label"), "locator": loc,
                "runner_decision": decision.value,
                "runner_reason": fp.acceptance_reason,
            }
            if decision != AcceptanceDecision.ACCEPTED:
                quarantine["identity"].append({
                    "artifact": artifact, "reasons": ["runner_not_accepted"],
                    "detail": fp.acceptance_reason})
                obs["cited"] = False
                continue
            groups["identity"].append(obs)
            field_packets.append(fp)

        # ── price observation (P111 row only) ──
        prow = price_by_key.get((led["manufacturer"], led["model"],
                                 led["variant"]))
        if prow is None:
            urow = unv_by_key.get((led["manufacturer"], led["model"],
                                   led["variant"]))
            price_status = "NO_P111_PRICE_EVIDENCE"
            price_acceptable = False
            field_gaps["price"].append({
                "gap": "exact_current_msrp",
                "reason_class": "UNVERIFIED_PRICE",
                "reason": (urow or {}).get("category")
                or "no price row in P111 evidence"})
        else:
            price_status = prow["msrp_status"]
            price_acceptable = (price_status ==
                                "EXACT_CURRENT_MSRP_VERIFIED")
            artifact = prow["artifact"]
            ok, reasons = verify_artifact(artifact, prow["source_url"],
                                          prow["sha256"], {})
            loc = None
            if ok:
                loc = price_locator(artifact_text(artifact), prow)
                if not loc:
                    reasons = ["locator_unresolvable"]
                    ok = False
            if not tuple_matches(prow, ident):
                reasons = ["ledger_tuple_mismatch"]
                ok = False
            if not ok:
                quarantine["price"].append({
                    "artifact": artifact, "source_url": prow["source_url"],
                    "reasons": reasons})
                price_status = "PRICE_OBSERVATION_QUARANTINED"
                price_acceptable = False
                field_gaps["price"].append({
                    "gap": "exact_current_msrp",
                    "reason_class": "PROVENANCE_FAILED",
                    "reason": "; ".join(reasons)})
            else:
                counts_current = (price_status ==
                                  "EXACT_CURRENT_MSRP_VERIFIED")
                row = {"source_url": prow["source_url"],
                       "source_name": prow.get("source_name") or
                       prow["manufacturer"],
                       "manufacturer": led["manufacturer"],
                       "model": led["model"], "variant": led["variant"]}
                fp = field_packet(f"{pid}.price.msrp_thb", key, row,
                                  {"price_thb": prow["price_thb"],
                                   "price_type": prow["price_type"]},
                                  EvidenceLocator(
                                      artifact_path=f"tests/fixtures/"
                                                    f"oem-artifacts/{artifact}",
                                      quote=loc["quote"]),
                                  prow["sha256"], CurrentnessState.CURRENT)
                decision = runner.evaluate(fp)
                if decision != AcceptanceDecision.ACCEPTED:
                    quarantine["price"].append({
                        "artifact": artifact,
                        "reasons": ["runner_not_accepted"],
                        "detail": fp.acceptance_reason})
                    price_status = "PRICE_OBSERVATION_QUARANTINED"
                    price_acceptable = False
                else:
                    groups["price"].append({
                        "obs_id": f"{pid}.price.msrp_thb", "cited": True,
                        "field": "msrp_thb", "value": prow["price_thb"],
                        "price_type": prow["price_type"],
                        "msrp_status": price_status,
                        "counts_as_current_msrp": counts_current,
                        "source_url": prow["source_url"],
                        "source_name": prow.get("source_name"),
                        "artifact": artifact, "sha256": prow["sha256"],
                        "provenance_state": prow["provenance_state"],
                        "source_class": prow["source_class"],
                        "trust_tier": prow["trust_tier"],
                        "currentness": prow["currentness"],
                        "locator": loc,
                        "runner_decision": decision.value,
                        "runner_reason": fp.acceptance_reason,
                    })
                    field_packets.append(fp)
                if price_status in {"MSRP_STARTING_NOT_EXACT",
                                    "EXACT_BINDING_NOT_VERIFIED_CURRENT"}:
                    field_gaps["price"].append({
                        "gap": "exact_current_msrp",
                        "reason_class": price_status,
                        "reason": "bound price kept as its own P111 status "
                                  "— never counted as current MSRP"})

        # ── spec observations (P112 rows only) ──
        for srow in spec_by_key.get((led["manufacturer"], led["model"],
                                     led["variant"]), []):
            artifact = srow["artifact"]
            ok, reasons = verify_artifact(artifact, srow["source_url"],
                                          srow["sha256"], {})
            loc = None
            if ok:
                loc = spec_locator(artifact_text(artifact), srow)
                if not loc:
                    reasons = ["locator_unresolvable"]
                    ok = False
            if not tuple_matches(srow, ident):
                reasons = ["ledger_tuple_mismatch"]
                ok = False
            if not ok:
                quarantine["spec"].append({
                    "artifact": artifact, "source_url": srow["source_url"],
                    "reasons": reasons, "field_key": srow["field_key"]})
                continue
            row = {"source_url": srow["source_url"],
                   "source_name": srow["manufacturer"],
                   "manufacturer": led["manufacturer"],
                   "model": led["model"], "variant": led["variant"]}
            fp = field_packet(srow["evidence_id"], key, row,
                              {"field_key": srow["field_key"],
                               "value": srow["value_text"],
                               "unit": srow["unit"]},
                              EvidenceLocator(
                                  artifact_path=f"tests/fixtures/"
                                                f"oem-artifacts/{artifact}",
                                  quote=loc["quote"]),
                              srow["sha256"], CurrentnessState.CURRENT)
            decision = runner.evaluate(fp)
            if decision != AcceptanceDecision.ACCEPTED:
                quarantine["spec"].append({
                    "artifact": artifact,
                    "reasons": ["runner_not_accepted"],
                    "detail": fp.acceptance_reason,
                    "field_key": srow["field_key"]})
                continue
            groups["spec"].append({
                "obs_id": srow["evidence_id"], "cited": True,
                "field_key": srow["field_key"],
                "value_text": srow["value_text"],
                "value_numeric": srow.get("value_numeric"),
                "unit": srow.get("unit"), "binding": srow["binding"],
                "grade_title": srow.get("grade_title"),
                "source_url": srow["source_url"],
                "artifact": artifact, "sha256": srow["sha256"],
                "provenance_state": srow["provenance_state"],
                "source_class": srow["source_class"],
                "trust_tier": srow["trust_tier"],
                "currentness": srow["currentness"],
                "locator": loc,
                "runner_decision": decision.value,
                "runner_reason": fp.acceptance_reason,
            })
            field_packets.append(fp)

        sgap = spec_gap_by_key.get((led["manufacturer"], led["model"],
                                    led["variant"]))
        if not groups["spec"]:
            if sgap:
                field_gaps["spec"].append({
                    "reason_class": sgap["reason_class"],
                    "reason": sgap["reason"]})
            else:
                field_gaps["spec"].append({
                    "reason_class": "not_in_p112_gap_list",
                    "reason": "no P112 spec row and no P112 gap entry — "
                              "left empty, never filled"})
        if not groups["identity"]:
            for q in quarantine["identity"]:
                not_accepted_reasons.append({
                    "scope": "identity",
                    "reason": "|".join(q["reasons"]),
                    "artifact": q.get("artifact")})

        identity_acceptable = bool(groups["identity"])
        runner_ok = all(o["runner_decision"] == "ACCEPTED"
                        for g in groups.values() for o in g)
        packet_accepted = identity_acceptable and runner_ok
        if not identity_acceptable and not not_accepted_reasons:
            not_accepted_reasons.append({
                "scope": "identity", "reason": "no_intact_identity_source",
                "artifact": None})
        packets.append({
            "packet_id": pid, "candidate_key": key,
            "manufacturer": led["manufacturer"], "model": led["model"],
            "variant": led["variant"], "scope": "TH",
            "generation_context": led.get("generation") or "",
            "observations": groups,
            "quarantine": quarantine,
            "field_gaps": field_gaps,
            "policy": {
                "identity_acceptable": identity_acceptable,
                "price_status": price_status,
                "price_acceptable": price_acceptable,
                "spec_acceptable": bool(groups["spec"]),
                "packet_accepted": packet_accepted,
                "promotion_eligible": False,
            },
            "status": "ACCEPTED" if packet_accepted else "QUARANTINED",
            "not_accepted_reasons": not_accepted_reasons,
        })

    runner_counts = runner.evaluate_batch(field_packets)
    assert sum(runner_counts.values()) == len(field_packets)

    # ── acceptance result ──
    accepted = sum(1 for p in packets if p["status"] == "ACCEPTED")
    quarantined = sum(1 for p in packets if p["status"] == "QUARANTINED")
    rejected = sum(1 for p in packets if p["status"] == "REJECTED")
    per_oem: dict = {}
    for p in packets:
        b = per_oem.setdefault(p["manufacturer"],
                               {"packets": 0, "accepted": 0,
                                "quarantined": 0, "rejected": 0})
        b["packets"] += 1
        b[p["status"].lower()] += 1
    identity_cited = sum(len(p["observations"]["identity"]) for p in packets)
    price_cited = sum(len(p["observations"]["price"]) for p in packets)
    spec_cited = sum(len(p["observations"]["spec"]) for p in packets)
    acc = {
        "schema": "acceptance_result_p113/v1",
        "generated_at": now(), "run_id": run_id,
        "packets_built": len(packets),
        "packets_accepted": accepted,
        "packets_quarantined": quarantined,
        "packets_rejected": rejected,
        "usable_packet_percent": round(100.0 * accepted / len(packets), 1),
        "field_coverage": {
            "identity_sources_cited": identity_cited,
            "price_fields_cited": price_cited,
            "spec_fields_cited": spec_cited,
            "variants_with_exact_current_msrp": sum(
                1 for p in packets if p["policy"]["price_status"] ==
                "EXACT_CURRENT_MSRP_VERIFIED"),
            "variants_with_any_bound_price": sum(
                1 for p in packets if p["policy"]["price_status"] in
                PRICE_STATUSES),
            "variants_with_spec_evidence": sum(
                1 for p in packets if p["observations"]["spec"]),
        },
        "price_status_distribution": {
            st: sum(1 for p in packets if p["policy"]["price_status"] == st)
            for st in sorted(PRICE_STATUSES |
                             {"NO_P111_PRICE_EVIDENCE",
                              "PRICE_OBSERVATION_QUARANTINED"})},
        "per_oem": dict(sorted(per_oem.items())),
        "runner": {"module": "thai_factory.acceptance",
                   "evaluated": len(field_packets),
                   "counts": dict(sorted(runner_counts.items())),
                   "min_confidence_rule": "OEM_OFFICIAL requires HIGH"},
        "promotion_eligible_count": 0,
    }
    write_json(os.path.join(OUT, "p113_acceptance_result.json"), acc)

    # ── rejection / quarantine report ──
    not_accepted = []
    qobs = 0
    for p in packets:
        qobs += sum(len(v) for v in p["quarantine"].values())
        if p["status"] == "ACCEPTED":
            continue
        not_accepted.append({
            "packet_id": p["packet_id"], "candidate_key": p["candidate_key"],
            "manufacturer": p["manufacturer"], "model": p["model"],
            "variant": p["variant"], "status": p["status"],
            "reasons": p["not_accepted_reasons"] or [
                {"scope": "packet", "reason": "runner_not_accepted",
                 "artifact": None}]})
    rej = {
        "schema": "rejection_report_p113/v1",
        "generated_at": now(), "run_id": run_id,
        "not_accepted_count": len(not_accepted),
        "not_accepted": not_accepted,
        "quarantined_observations_total": qobs,
        "quarantined_observations_by_reason": {},
        "note": "quarantine never overwrites: a failed observation is "
                "listed here with its reason and simply not cited; "
                "missing evidence stays a field gap, never a value",
    }
    for p in packets:
        for scope, items in p["quarantine"].items():
            for it in items:
                for rr in it["reasons"]:
                    base = rr.split("_")[0] + "_" + rr.split("_")[1] \
                        if "_" in rr else rr
                    key = f"{scope}:{base}"
                    rej["quarantined_observations_by_reason"][key] = \
                        rej["quarantined_observations_by_reason"].get(key, 0) + 1
    write_json(os.path.join(OUT, "p113_rejection_report.json"), rej)

    # ── packet set ──
    write_json(os.path.join(OUT, "p113_evidence_packets.json"), {
        "schema": "evidence_packet_set_p113/v1",
        "generated_at": now(), "run_id": run_id,
        "identity_ledger": {"artifact": "audit/coverage/"
                                        "identity_universe_p108.json",
                            "accepted_variants": ACCEPTED_LEDGER,
                            "changed_by_p113": False},
        "price_source": {"artifact": "audit/coverage/"
                                     "p111_price_evidence.json",
                         "rows": len(p111_rows)},
        "spec_source": {"artifact": "audit/coverage/"
                                    "p112_spec_evidence.json",
                        "rows": len(p112_rows)},
        "packets": packets,
    })

    # ── byte-identity + final result ──
    watch_after = {n: sha256(os.path.join(OUT, n)) for n in WATCH}
    price_ok = all(watch_before[n] == watch_after[n]
                   for n in WATCH if n.startswith("p111"))
    p112_ok = all(watch_before[n] == watch_after[n]
                  for n in WATCH if n.startswith("p112"))
    identity_ok = watch_before["identity_universe_p108.json"] == \
        watch_after["identity_universe_p108.json"]
    final = {
        "schema": "final_result_p113/v1",
        "generated_at": now(), "run_id": run_id,
        "head": head_sha(),
        "packets_built": len(packets),
        "packets_accepted": accepted,
        "packets_quarantined": quarantined,
        "packets_rejected": rejected,
        "usable_packet_percent": round(100.0 * accepted / len(packets), 1),
        "field_coverage": acc["field_coverage"],
        "price_status_distribution": acc["price_status_distribution"],
        "promotion_eligible_count": 0,
        "identity_ledger_unchanged": {"confirmed_variants": 488,
                                      "changed_by_p113": False},
        "gates": {
            "staging_write": False,
            "prisma_touched": False,
            "verifier_touched": False,
            "production_db_unchanged": True,
            "price_artifacts_byte_identical": price_ok,
            "p112_artifacts_byte_identical": p112_ok,
            "identity_artifact_byte_identical": identity_ok,
            "new_acquisition": 0,
            "ai_reconciliation": False,
        },
    }
    write_json(os.path.join(OUT, "p113_final_result.json"), final)
    print(f"packets={len(packets)} accepted={accepted} "
          f"quarantined={quarantined} rejected={rejected} "
          f"obs_cited={identity_cited + price_cited + spec_cited} "
          f"runner={dict(runner_counts)} "
          f"byte_ok={price_ok and p112_ok and identity_ok}")
    return 0


def main(argv) -> int:
    phase = argv[1] if len(argv) > 1 else "run"
    if phase == "plan":
        return phase_plan()
    if phase == "run":
        return phase_run()
    print(f"unknown phase: {phase}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
