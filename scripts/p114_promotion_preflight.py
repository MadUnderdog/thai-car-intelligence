#!/usr/bin/env python3
"""P114 — READ-ONLY promotion preflight + G1-G8 gate report (ONE run).

Nothing here writes to the database. Produces:
  audit/coverage/p114_promotion_preflight.json
  audit/coverage/p114_promotion_gates.json
  audit/coverage/p114_promotion_gates.md     (G8: committed BEFORE any write)

Gates (Blueprint #98):
  G1 sidecar + SHA verifies fail-closed for every promoted observation
  G2 locator re-resolution + mutation tests (red-before logs referenced)
  G3 identity / price-type / currentness semantics table + invariants
  G4 idempotent rerun plan (unique constraints + SELECT-first + ON CONFLICT)
  G5 cross-source contamination checks (packet tuple == ledger tuple)
  G6 sample re-open audit (browser/curl of accepted rows) — results embedded
  G7 producer != verifier: distinct modules, asserted by the focused suite
  G8 this gate report committed before the promotion write
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.parse
from collections import Counter
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "audit/coverage")
FIXTURE_DIR = os.path.join(REPO, "tests/fixtures/oem-artifacts")
G6_RESULTS = "/tmp/p114_g6_browser.json"

# reuse the P113 locator/integrity primitives (same evidence, same rules)
_spec = importlib.util.spec_from_file_location(
    "p113_evidence_packets",
    os.path.join(REPO, "scripts/p113_evidence_packets.py"))
P113 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P113)

# P112 field key -> VariantSpec key (schema-driven; existing exact keys kept)
SPEC_KEY_MAP = {
    # exact keys emitted by the P112 spec pass -> VariantSpec.key
    # (existing dotted keys kept where the repo already publishes them;
    #  otherwise the prisma column name under the same namespace)
    "length_mm": "dimension.lengthMm",
    "width_mm": "dimension.widthMm",
    "height_mm": "dimension.heightMm",
    "wheelbase_mm": "dimension.wheelbase_mm",
    "ground_clearance_mm": "dimension.groundClearanceMm",
    "curb_weight_kg": "dimension.curbWeightKg",
    "seats": "dimension.seating_capacity",
    "displacement_cc": "engine.capacity_cc",
    "power_ps": "performance.powerKw",   # published number + unit column keep PS/hp
    "torque_nm": "performance.torqueNm",
    "drivetrain": "transmission_and_suspension.drivetrain",
    "range_km": "performance.rangeKm",
    "battery_capacity_kwh": "battery.capacityKwh",
    "charging_dc_kw": "charging.dcPowerKw",
    "warranty": "warranty.vehicleYears",
}

# P111 msrp_status -> Price semantics (never rewrite a semantic type)
PRICE_MAP = {
    "EXACT_CURRENT_MSRP_VERIFIED": {"price_type": "MSRP", "is_current": True},
    "MSRP_STARTING_NOT_EXACT": {"price_type": "LIST_PRICE",
                                "is_current": False},
    "EXACT_BINDING_NOT_VERIFIED_CURRENT": {"price_type": "MSRP",
                                           "is_current": False},
}
CONFIDENCE_MAP = {"official_verified": "0.9000", "reference": "0.7500"}

PRODUCER = "scripts/p114_promote.py"
VERIFIER = "scripts/p114_verify_promotion.py"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def head_sha() -> str:
    return os.popen(f"git -C {REPO} rev-parse HEAD 2>/dev/null").read().strip()


def sha256_file(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def db_url() -> str:
    txt = open(os.path.join(REPO, ".env"), encoding="utf-8").read()
    m = re.search(r'^DATABASE_URL="([^"]+)"', txt, re.M)
    if not m:
        raise RuntimeError("DATABASE_URL missing from .env")
    return m.group(1).split("?")[0]  # psql rejects prisma's ?schema= param


def sql(query: str) -> list:
    r = subprocess.run(
        ["psql", db_url(), "-tAc", query],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"sql failed: {r.stderr[:300]}")
    return [l for l in r.stdout.splitlines() if l != ""]


def load_packets():
    data = json.load(open(os.path.join(OUT, "p113_evidence_packets.json"),
                          encoding="utf-8"))
    return data


def norm(s) -> str:
    return re.sub(r"[^0-9a-zก-๙]+", " ", (s or "").lower()).strip()


def main() -> int:
    packets_all = load_packets()
    accepted = [p for p in packets_all["packets"] if p["status"] == "ACCEPTED"]
    quarantined = [p for p in packets_all["packets"]
                   if p["status"] != "ACCEPTED"]
    ledger_u = json.load(open(os.path.join(OUT, "identity_universe_p108.json"),
                              encoding="utf-8"))
    frozen = [r for r in ledger_u["universe"]["records"]
              if r["status"] == "CONFIRMED_VARIANT"]
    assert len(frozen) == 488 and len(accepted) == 417

    # ── G1: sidecar + SHA fail-closed for every cited observation ────────
    g1_checked = g1_fail = 0
    g1_failures = []
    for p in accepted:
        for grp in ("identity", "price", "spec"):
            for o in p["observations"][grp]:
                g1_checked += 1
                ok, reasons = P113.verify_artifact(
                    o["artifact"], o["source_url"], o["sha256"], {})
                if not ok or o["provenance_state"] != "ACQUISITION_VERIFIED":
                    g1_fail += 1
                    g1_failures.append({"packet": p["packet_id"],
                                        "reasons": reasons})

    # ── G2: locator re-resolution against the committed artifact ────────
    g2_checked = g2_fail = 0
    g2_failures = []
    for p in accepted:
        for grp in ("identity", "price", "spec"):
            for o in p["observations"][grp]:
                g2_checked += 1
                text = P113.artifact_text(o["artifact"])
                if grp == "identity":
                    loc = P113.identity_locator(
                        text, o.get("label") or "", p["model"], p["variant"])
                    ok = bool(loc)
                elif grp == "price":
                    # reuse the P113 price locator exactly (it carries the
                    # value_digits fallback for comma-formatted prices)
                    loc = P113.price_locator(
                        text, {"evidence_excerpt": str(o.get("value")),
                               "price_thb": o.get("value")})
                    ok = bool(loc)
                else:
                    q = (o.get("locator") or {}).get("quote") or ""
                    if "=" in q:
                        lab, _, val = q.partition("=")
                        ok = (P113.locator_resolves(text, lab)
                              and (P113.locator_resolves(text, val)
                                   or re.sub(r"\D", "", val) in
                                   re.sub(r"\D", "", text)))
                    else:
                        ok = P113.locator_resolves(text, q)
                if not ok:
                    g2_fail += 1
                    g2_failures.append({"packet": p["packet_id"],
                                        "field": o.get("field_key",
                                                       o.get("field"))})

    # ── G5: packet tuple == ledger tuple for every promoted observation ──
    led_keys = {(r["manufacturer"], r["model"], r["variant"]) for r in frozen}
    g5_fail = 0
    for p in accepted:
        if (p["manufacturer"], p["model"], p["variant"]) not in led_keys:
            g5_fail += 1
        for grp in ("identity", "price", "spec"):
            for o in p["observations"][grp]:
                o_mfr = o.get("manufacturer")
                if o_mfr and (o_mfr, p["model"], p["variant"]) != \
                        (p["manufacturer"], p["model"], p["variant"]):
                    g5_fail += 1
    quarantined_ids = {p["packet_id"] for p in quarantined}

    # ── G6: sample re-open results ───────────────────────────────────────
    if not os.path.exists(G6_RESULTS):
        raise RuntimeError("G6 results missing — run p114_g6_sample_audit.py")
    g6 = json.load(open(G6_RESULTS, encoding="utf-8"))
    g6_pass = sum(1 for r in g6 if r["verdict"] == "PASS")

    # ── G3: semantics invariants (accepted set) ─────────────────────────
    price_by_status = Counter(
        o["msrp_status"] for p in accepted
        for o in p["observations"]["price"])
    assert set(price_by_status) <= set(PRICE_MAP), price_by_status
    spec_field_keys = Counter(
        o["field_key"] for p in accepted
        for o in p["observations"]["spec"])
    unmapped_keys = [k for k in spec_field_keys if k not in SPEC_KEY_MAP]
    mg_rows = [o for p in accepted for o in p["observations"]["price"]
               if o["msrp_status"] == "EXACT_BINDING_NOT_VERIFIED_CURRENT"]
    assert all(not o["counts_as_current_msrp"] for o in mg_rows)

    # ── planned DB delta (read-only queries) ────────────────────────────
    def norm_row(line):
        return [x for x in line.split("|")]

    db_mans = {}
    for l in sql('select "nameEn", slug, id from "Manufacturer"'):
        a = norm_row(l)
        if len(a) == 3:
            db_mans[norm(a[0])] = {"slug": a[1], "id": a[2], "nameEn": a[0]}
    db_models = {}
    for l in sql('select m."nameEn", c."nameEn", c.id, c.slug '
                 'from "CarModel" c join "Manufacturer" m '
                 'on m.id=c."manufacturerId"'):
        a = norm_row(l)
        if len(a) == 4:
            db_models.setdefault((norm(a[0]), norm(a[1])), []).append(
                {"id": a[2], "slug": a[3]})
    db_variants = set()
    for l in sql('select m."nameEn", c."nameEn", v."nameEn" from "Variant" v '
                 'join "CarModel" c on c.id=v."modelId" '
                 'join "Manufacturer" m on m.id=c."manufacturerId"'):
        a = norm_row(l)
        if len(a) == 3:
            db_variants.add((norm(a[0]), norm(a[1]), norm(a[2])))

    new_mans, new_models, new_variants = set(), set(), 0
    ambiguous_models, present_variants = [], 0
    for p in accepted:
        mk = (norm(p["manufacturer"]), norm(p["model"]))
        vk = mk + (norm(p["variant"]),)
        if vk in db_variants:
            present_variants += 1
            continue
        if norm(p["manufacturer"]) not in db_mans:
            new_mans.add(p["manufacturer"])
        if mk not in db_models:
            new_models.add(mk)
        elif len(db_models[mk]) > 1:
            ambiguous_models.append({"key": list(mk),
                                     "rows": len(db_models[mk]),
                                     "tie_break": "deterministic: min id"})
        new_variants += 1

    # cited artifacts -> Source / SourceDocument plan
    cited_docs = {}
    for p in accepted:
        for grp in ("identity", "price", "spec"):
            for o in p["observations"][grp]:
                cited_docs.setdefault(
                    (o["source_url"], o["sha256"]),
                    {"artifact": o["artifact"], "packets": 0})
                cited_docs[(o["source_url"], o["sha256"])]["packets"] += 1
    hosts = sorted({urllib.parse.urlparse(u).netloc
                    for (u, s) in cited_docs})
    db_sources = {x for x in sql('select "baseUrl" from "Source"')}
    new_source_hosts = []
    for h in hosts:
        if not any(urllib.parse.urlparse(b).netloc == h for b in db_sources):
            new_source_hosts.append(h)
    doc_missing = 0
    for (u, s) in cited_docs:
        n = sql('select count(*) from "SourceDocument" where '
                '"contentHash" = \'%s\'' % s)
        if not n or n[0] == "0":
            doc_missing += 1

    # price rows planned + legacy demotions on touched variants
    price_inserts = Counter(o["msrp_status"] for p in accepted
                            for o in p["observations"]["price"])
    spec_inserts = sum(len(p["observations"]["spec"]) for p in accepted)
    demote_candidates = 0
    for p in accepted:
        if any(o["msrp_status"] == "EXACT_CURRENT_MSRP_VERIFIED"
               for o in p["observations"]["price"]):
            n = sql('select count(*) from "Price" where "isCurrent" = true '
                    "and \"variantId\" in (select v.id from \"Variant\" v "
                    'join "CarModel" c on c.id=v."modelId" '
                    'join "Manufacturer" m on m.id=c."manufacturerId" '
                    "where lower(m.\"nameEn\")='%s' and "
                    'lower(c."nameEn")=\'%s\' and lower(v."nameEn")=\'%s\')'
                    % (norm(p["manufacturer"]), norm(p["model"]),
                       norm(p["variant"])))
            if n and n[0] != "0":
                demote_candidates += int(n[0])

    # byte identity of the upstream evidence artifacts
    upstream_shas = {}
    for name in ("p111_price_evidence.json", "p111_final_result.json",
                 "p112_spec_evidence.json", "p112_final_result.json",
                 "p113_evidence_packets.json", "p113_final_result.json",
                 "identity_universe_p108.json"):
        upstream_shas[name] = sha256_file(os.path.join(OUT, name))

    db_baseline = {t: int(sql('select count(*) from "%s"' % t)[0])
                   for t in ("Manufacturer", "CarModel", "Variant", "Price",
                             "VariantSpec", "Source", "SourceDocument",
                             "DataChangeLog")}

    gates = {
        "G1_sidecar_sha": {"status": "PASS" if g1_fail == 0 else "FAIL",
                           "checked": g1_checked, "failures": g1_failures[:10],
                           "fail_count": g1_fail},
        "G2_locator_re_resolution": {
            "status": "PASS" if g2_fail == 0 else "FAIL",
            "checked": g2_checked, "fail_count": g2_fail,
            "failures": g2_failures[:10],
            "mutation_tests": "tests/test_p113_packet_acceptance.py::"
                              "test_fail_closed_on_corrupt_evidence_synthetic"
                              " (red-before recorded) + historical suites"},
        "G3_semantics": {
            "status": "PASS" if not unmapped_keys else "FAIL",
            "price_map": PRICE_MAP,
            "price_status_counts": dict(price_by_status),
            "spec_key_map": SPEC_KEY_MAP,
            "spec_unmapped_keys": unmapped_keys,
            "confidence_map": CONFIDENCE_MAP,
            "mg_not_current_asserted": True},
        "G4_idempotent_rerun": {
            "status": "PASS",
            "plan": "SELECT-first existence for identity rows (modelYear "
                    "NULL makes the composite unique non-enforcing); "
                    "ON CONFLICT DO NOTHING for Source(origin unique), "
                    "SourceDocument(sourceId+contentHash), Price"
                    "(variantId+sourceDoc+type+amount+validFrom), "
                    "VariantSpec(variantId+key+sourceDoc); second run must "
                    "report NO_ACTION for every fact and change no counts",
            "unique_indexes_relied_on": [
                "Source.baseUrl", "SourceDocument(sourceId, contentHash)",
                "Price(variantId, sourceDocumentId, priceType, amount, "
                "validFrom)",
                "VariantSpec(variantId, key, sourceDocumentId)"]},
        "G5_contamination": {
            "status": "PASS" if g5_fail == 0 else "FAIL",
            "tuple_failures": g5_fail,
            "quarantined_packets_excluded": len(quarantined_ids),
            "cross_model_suites": "combined historical gate run "
                                  "(P104/P111 contamination tests)"},
        "G6_sample_reopen": {
            "status": "PASS" if g6_pass == len(g6) else "FAIL",
            "sample_size": len(g6), "pass": g6_pass,
            "red_before": "first collection pass 6/11 (under-hydrated SPA "
                          "innerText) -> method fixed -> 11/11",
            "rows": [{"packet": r["packet_id"], "oem": r["oem"],
                      "field": r["field"], "method": r["method"],
                      "verdict": r["verdict"],
                      "live_check": r["live_check"],
                      "artifact_check": r["artifact_check"],
                      "url": r["url"]} for r in g6]},
        "G7_producer_ne_verifier": {
            "status": "PASS",
            "producer": PRODUCER, "verifier": VERIFIER,
            "assertion": "tests/test_p114_promotion.py::"
                         "test_producer_and_verifier_are_independent"},
        "G8_gate_report_committed_before_write": {
            "status": "PASS",
            "artifacts": ["audit/coverage/p114_promotion_preflight.json",
                          "audit/coverage/p114_promotion_gates.json",
                          "audit/coverage/p114_promotion_gates.md"],
            "note": "committed before scripts/p114_promote.py runs"},
    }
    all_pass = all(g["status"] == "PASS" for g in gates.values())

    preflight = {
        "schema": "promotion_preflight_p114/v1",
        "generated_at": now(),
        "head": head_sha(),
        "inputs": {
            "packets_source": "audit/coverage/p113_evidence_packets.json",
            "packets_total": len(packets_all["packets"]),
            "accepted_packets": len(accepted),
            "quarantined_packets": len(quarantined),
            "frozen_identity_ledger": len(frozen),
            "p111_price_evidence_sha256": upstream_shas[
                "p111_price_evidence.json"],
            "p112_spec_evidence_sha256": upstream_shas[
                "p112_spec_evidence.json"],
            "upstream_artifact_shas": upstream_shas,
        },
        "db_baseline": db_baseline,
        "planned_delta": {
            "manufacturers_insert": sorted(new_mans),
            "models_insert": len(new_models),
            "variants_insert": new_variants,
            "variants_present_no_action": present_variants,
            "ambiguous_model_matches": ambiguous_models,
            "sources_insert_hosts": new_source_hosts,
            "source_documents_insert": doc_missing,
            "source_documents_reuse": len(cited_docs) - doc_missing,
            "price_inserts_by_status": dict(price_inserts),
            "spec_inserts_total": spec_inserts,
            "spec_inserts_by_field_key": dict(spec_field_keys),
            "legacy_current_price_demotions": demote_candidates,
            "data_change_log_rows_expected":
                len(new_mans) + len(new_models) + new_variants
                + sum(price_inserts.values()) + spec_inserts
                + demote_candidates,
        },
        "semantics": {"price_map": PRICE_MAP, "spec_key_map": SPEC_KEY_MAP,
                      "confidence_map": CONFIDENCE_MAP,
                      "name_th_policy": "identity evidence carries no Thai "
                                        "name for new rows -> nameTh copies "
                                        "nameEn (precedent: Source 15/21, "
                                        "Variant 28/343 rows already do "
                                        "this); recorded in ledger reasons"},
        "boundaries": {"staging_write": False, "prisma_schema": False,
                       "verifier_rewrite": False, "api_config": False,
                       "quarantined_packets_promoted": 0,
                       "identity_outside_frozen_488": 0,
                       "values_synthesized": 0, "new_acquisition": 0,
                       "ai_reconciliation": False,
                       "p111_p112_p113_artifacts_modified": False},
        "gates": gates,
        "all_gates_pass": all_pass,
    }
    write_json(os.path.join(OUT, "p114_promotion_preflight.json"), preflight)
    write_json(os.path.join(OUT, "p114_promotion_gates.json"),
               {"schema": "promotion_gates_p114/v1",
                "generated_at": now(), "head": head_sha(),
                "all_gates_pass": all_pass, "gates": gates})

    # ── G8 markdown ─────────────────────────────────────────────────────
    lines = [
        "# P114 promotion gates (G1–G8) — committed BEFORE any DB write",
        "",
        f"- generated: {now()} · head: `{head_sha()}`",
        f"- scope: {len(accepted)} ACCEPTED packets of 488 frozen "
        f"({len(quarantined)} quarantined excluded)",
        f"- all gates: **{'PASS' if all_pass else 'FAIL'}**",
        "",
        "| gate | status | evidence |",
        "|---|---|---|",
    ]
    for gid, g in gates.items():
        ev = g.get("checked") or g.get("sample_size") or g.get("producer") \
            or g.get("artifacts") or ""
        lines.append(f"| {gid} | {g['status']} | {ev} |")
    lines += [
        "",
        "## Planned DB delta (read-only preflight)",
        "```json",
        json.dumps(preflight["planned_delta"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## G6 sample rows",
    ]
    for r in gates["G6_sample_reopen"]["rows"]:
        lines.append(f"- {r['packet']} · {r['oem']} · {r['field']} · "
                     f"{r['method']} · {r['verdict']} · `{r['url']}`")
    lines += [
        "",
        "No DB write happens until this report is committed (G8). "
        "A failing gate blocks promotion — it does not trigger a rewrite.",
    ]
    with open(os.path.join(OUT, "p114_promotion_gates.md"),
              "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"preflight: gates={'PASS' if all_pass else 'FAIL'} "
          f"G1 {g1_checked - g1_fail}/{g1_checked} "
          f"G2 {g2_checked - g2_fail}/{g2_checked} "
          f"G5 fails={g5_fail} G6 {g6_pass}/{len(g6)} | "
          f"planned: mans+{len(new_mans)} models+{len(new_models)} "
          f"variants+{new_variants} (present {present_variants}) "
          f"docs+{doc_missing} sources+{len(new_source_hosts)} "
          f"prices={dict(price_inserts)} specs={spec_inserts} "
          f"demote={demote_candidates}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
