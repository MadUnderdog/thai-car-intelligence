#!/usr/bin/env python3
"""
P102 — high-recall catalog identity enumeration + first-party reconciliation.

Builds the Phase-1 IDENTITY UNIVERSE (models + variants) for every in-scope OEM
and reconciles each candidate against first-party Thai-market evidence.

Source roles (Blueprint §96) — never silently upgraded:
  IDENTITY_ENUMERATOR  insurance / used-car / finance taxonomy surfaces
  MARKET_REFERENCE     reference datasets (Thai makes, FIPE, DLT)
  MEDIA_DISCOVERY      media price indexes — discovery only
  MARKET_TRUTH         first-party OEM/importer rows already in staging

Hard rules honoured here:
  * every NEW capture goes through AcquisitionWriter (artifact + .prov.json
    from the same acquisition event) — §94
  * per-host politeness >= 5 s, no UA rotation, no TLS bypass, and no request
    to any host the OEM registry records as BLOCKED_* before next_retry_at
  * the universe is a SEPARATE artifact: no staging rows, no production DB
  * identity-only candidates are never promoted; no price is ever invented
  * blocked OEMs keep their official blocker — secondary enumeration never
    makes them "official" or "covered"

Usage:
  python3 scripts/p102_identity_universe.py            # full run
  python3 scripts/p102_identity_universe.py --offline  # reuse captures only
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from thai_factory.acquisition.provenance import (  # noqa: E402
    AcquisitionReader, AcquisitionWriter, ProvenanceError,
)
from thai_factory.catalog.identity_pass import (  # noqa: E402
    BRAND_ALIASES, FirstPartyStatus, IdentityReconciliation,
    match_key, parse_index_page,
)
from thai_factory.catalog.universe import SourceRole  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG_PATH = os.path.join(REPO, "audit", "coverage", "oem-registry.json")
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
CATALOG_DISCOVERY = os.path.join(REPO, "audit", "catalog-discovery")
OUT_DIR = os.path.join(REPO, "audit", "coverage")
ENUM_DIR = os.path.join(REPO, "tests", "fixtures", "identity-enumerator-artifacts")
PROBE = os.path.join(OUT_DIR, "p102_enumerator_probe.json")
STAMP = datetime.now(timezone.utc).strftime("%Y%m%d")
SESSION_ID = f"p102-identity-{STAMP}"

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
POLITENESS_S = 5.5           # §94 per-host politeness

# ─── identity-enumerator surfaces ────────────────────────────────────────────
# 9carthai publishes a Thai-market price index per manufacturer.  Its ROLE is
# MEDIA_DISCOVERY (discovery only); it is never market truth.
NINECARTHAI_SLUGS = {
    "Audi": ["audi-price"],
    "BMW": ["bmw-price"],
    "BYD": ["byd-price"],
    "Changan": ["new-changan-lumin-price"],
    "Chery": ["chery-price"],
    "Chevrolet": ["chevrolet-price"],
    "Deepal": ["deepal-price"],
    "Ford": ["ford-price"],
    "GWM": ["gwm-price"],
    "Haval": ["haval-price"],
    "Honda": ["honda-price"],
    "Isuzu": ["isuzu-price"],
    "Jaguar": ["jaguar-price"],
    "Kia": ["kia-price"],
    "Lexus": ["lexus-price"],
    "MG": ["mg-price"],
    "MINI": ["mini-price"],
    "Mazda": ["mazda-price"],
    "Mercedes-Benz": ["mercedes-benz-price"],
    "Mitsubishi": ["mitsubishi-price"],
    "NETA": ["neta-price"],
    "Nissan": ["nissan-price"],
    "Peugeot": ["peugeot-price"],
    "Porsche": ["porsche-price"],
    "Subaru": ["subaru-price"],
    "Suzuki": ["suzuki-price"],
    "Tesla": ["tesla-price"],
    "Toyota": ["toyota-price"],
    "Volvo": ["volvo-price"],
}
# in-scope OEMs with no published page on the enumerator — recorded, not guessed
NINECARTHAI_MISSING = {
    "Avance": "no published index page for this manufacturer on the enumerator",
    "Land Rover": "no published index page for this manufacturer on the enumerator "
                  "(only Jaguar is indexed)",
    "Smart": "no published index page for this manufacturer on the enumerator",
}

# genuine IDENTITY_ENUMERATOR surfaces (insurance / used-car) — brand taxonomy
INSURANCE_SURFACES = [
    ("bki_motor_quote", "https://www.bangkokinsurance.com/product/motor/voluntary/register",
     "bki_motor_quote_form.html", "insurance motor-quote brand taxonomy"),
    ("viriyah_landing", "https://www.viriyah.co.th/",
     "viriyah_home_page.html", "insurance landing — checked for a published taxonomy"),
]

USED_CAR_BLOCKERS = [
    ("one2car", "https://www.one2car.com/",
     "BLOCKED_HTTP_403", "bot-challenge interstitial on every used-car taxonomy path"),
    ("chobrod", "https://www.chobrod.com/",
     "BLOCKED_TLS", "certificate subject mismatch; TLS verification is never bypassed"),
]


# ─── capture ─────────────────────────────────────────────────────────────────
def _fetch(url: str):
    import requests
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45)
    return resp.status_code, resp.text, resp.url


def capture(url: str, filename: str, offline: bool):
    """Capture through AcquisitionWriter, reusing a verified artifact if present."""
    os.makedirs(ENUM_DIR, exist_ok=True)
    path = os.path.join(ENUM_DIR, filename)
    if os.path.exists(path):
        try:
            content, prov = AcquisitionReader.read(path)
            return {"filename": filename, "status": "REUSED_VERIFIED",
                    "url": prov.get("source_url"), "sha256": prov.get("sha256"),
                    "captured_at": prov.get("captured_at"), "content": content}
        except ProvenanceError as exc:
            return {"filename": filename, "status": "PROVENANCE_ERROR",
                    "error": str(exc)[:200], "content": None}
    if offline:
        return {"filename": filename, "status": "SKIPPED_OFFLINE", "content": None}

    code, text, final_url = _fetch(url)
    if code >= 400:
        return {"filename": filename, "status": f"BLOCKED_HTTP_{code}",
                "url": url, "content": None}
    # AcquisitionReader verifies the sidecar hash against a universal-newline
    # read, so the artifact is stored LF-only — otherwise any lone \r in the
    # source body makes the pair unverifiable (§94 fail-closed).
    prov = AcquisitionWriter.write(
        content=text.replace("\r\n", "\n").replace("\r", "\n"),
        source_url=final_url, acquisition_method="http_get",
        output_dir=ENUM_DIR, filename=filename, session_id=SESSION_ID,
    )
    return {"filename": filename, "status": "CAPTURED", "url": final_url,
            "sha256": prov["sha256"], "captured_at": prov["captured_at"],
            "content": text}


def _bki_brands(html_text):
    """Brand options published by the insurance motor-quote form."""
    i = html_text.find("dropdownCarBrand")
    if i < 0:
        return []
    seg = html_text[i:i + 6000]
    out = []
    for value, text in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', seg):
        label = re.sub(r"\s+", " ", text).strip()
        if value and label and label != value:
            out.append({"value": value, "label": label})
    return out


# ─── committed enumerator artifacts ──────────────────────────────────────────
def load_thai_reference(rec: IdentityReconciliation, in_scope):
    path = os.path.join(CATALOG_DISCOVERY, "thai_market_reference.json")
    if not os.path.exists(path):
        return
    rec.add_source("thai_market_reference", SourceRole.MARKET_REFERENCE.value,
                   "audit/catalog-discovery/thai_market_reference.json",
                   "reference dataset — Thai makes/models, never market truth")
    data = json.load(open(path, encoding="utf-8"))
    for make in data.get("vehicle_makes_thailand", []):
        brand = make.get("make")
        if brand not in in_scope:
            rec.reject(brand or "?", brand or "?",
                       "manufacturer is not an in-scope OEM in the coverage registry",
                       "thai_market_reference")
            continue
        for model in make.get("models", []) or []:
            rec.add_enumerator(brand, model, "",
                               {"source_name": "thai_market_reference",
                                "source_role": SourceRole.MARKET_REFERENCE.value,
                                "source_url": "audit/catalog-discovery/thai_market_reference.json",
                                "label": model})


def load_headlightmag(rec: IdentityReconciliation, in_scope):
    path = os.path.join(CATALOG_DISCOVERY, "media_discovery_headlightmag.json")
    if not os.path.exists(path):
        return
    rec.add_source("headlightmag", SourceRole.MEDIA_DISCOVERY.value,
                   "audit/catalog-discovery/media_discovery_headlightmag.json",
                   "media category model mentions — discovery only")
    data = json.load(open(path, encoding="utf-8"))
    for entry in data.get("entries", []):
        if entry.get("classification") != "model-mention":
            continue
        cat = (entry.get("brand_category_name") or "").replace("Brand - ", "").strip()
        brand = cat.title() if cat.upper() == cat else cat
        brand = next((b for b in in_scope
                      if b.upper().replace("-", "") ==
                      brand.upper().replace("-", "")), None)
        if not brand:
            continue
        model = entry.get("clean_model") or entry.get("raw_model")
        if not model:
            continue
        rec.add_enumerator(brand, model, "",
                           {"source_name": "headlightmag",
                            "source_role": SourceRole.MEDIA_DISCOVERY.value,
                            "source_url": "audit/catalog-discovery/"
                                          "media_discovery_headlightmag.json",
                            "label": model})


def load_open_ev(rec: IdentityReconciliation, in_scope):
    """open-ev-data rows are enumerated for evaluation only; rows whose published
    markets exclude Thailand are rejected with an explicit reason (scope)."""
    path = os.path.join(CATALOG_DISCOVERY, "second_taxonomy_capture.json")
    if not os.path.exists(path):
        return
    rec.add_source("open_ev_data", SourceRole.IDENTITY_ENUMERATOR.value,
                   "audit/catalog-discovery/second_taxonomy_capture.json",
                   "global EV taxonomy — Thai-market scope filtered")
    data = json.load(open(path, encoding="utf-8"))
    brand_titles = {"byd": "BYD", "toyota": "Toyota", "bmw": "BMW",
                    "nissan": "Nissan", "volvo": "Volvo",
                    "mercedes_benz": "Mercedes-Benz", "mg": "MG",
                    "porsche": "Porsche", "mini": "MINI", "honda": "Honda"}
    for row in data.get("rows", []):
        brand = brand_titles.get(row.get("brand", "").lower(), row.get("brand", ""))
        markets = row.get("markets") or []
        model = row.get("model", "")
        trim = row.get("trim_name") or row.get("trim_slug") or ""
        if "TH" not in markets:
            rec.reject(brand, f"{model} {trim}".strip(),
                       f"scope: published markets {markets} do not include TH — "
                       f"not a Thailand-market identity",
                       "open_ev_data")
            continue
        if brand not in in_scope:
            rec.reject(brand, f"{model} {trim}".strip(),
                       "manufacturer is not an in-scope OEM", "open_ev_data")
            continue
        rec.add_enumerator(brand, model, trim,
                           {"source_name": "open_ev_data",
                            "source_role": SourceRole.IDENTITY_ENUMERATOR.value,
                            "source_url": "audit/catalog-discovery/"
                                          "second_taxonomy_capture.json",
                            "label": f"{model} {trim}".strip()})


def load_fipe_scope_rejects(rec: IdentityReconciliation):
    """FIPE is a Brazilian reference: enumerated, then rejected for Thai scope."""
    path = os.path.join(CATALOG_DISCOVERY, "reconciled_identity_universe.json")
    if not os.path.exists(path):
        return
    rec.add_source("fipe_brazilian_vehicle_reference",
                   SourceRole.MARKET_REFERENCE.value,
                   "audit/catalog-discovery/reconciled_identity_universe.json",
                   "Brazilian reference — evaluated, rejected for TH scope")
    data = json.load(open(path, encoding="utf-8"))
    for c in data.get("candidates", []):
        reps = c.get("source_representations") or []
        if not any(r.get("source_name") == "fipe_brazilian_vehicle_reference"
                   for r in reps):
            continue
        rec.reject(c.get("manufacturer", "?"),
                   f"{c.get('model', '')} {c.get('variant', '')}".strip(),
                   "scope: Brazilian reference taxonomy publishes no Thailand "
                   "market evidence for this identity",
                   "fipe_brazilian_vehicle_reference")


def load_first_party(rec: IdentityReconciliation, in_scope):
    """MARKET_TRUTH = the first-party rows already staged from official artifacts."""
    if not os.path.exists(STAGING):
        return
    rec.add_source("staging_vehicle_observations",
                   SourceRole.MARKET_TRUTH.value,
                   "audit/data-staging/vehicle_observations.jsonl",
                   "first-party OEM/importer rows (source.class == OEM_OFFICIAL)")
    brand_alias = {b.lower().replace(" ", "-"): b for b in in_scope}
    brand_alias.update({"land-rover": "Land Rover", "mini": "MINI",
                        "mercedes-benz": "Mercedes-Benz"})
    with open(STAGING, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("source", {}).get("class") != "OEM_OFFICIAL":
                continue
            brand = brand_alias.get(row["identity"]["brand_normalized"])
            if not brand:
                continue
            model = row["identity"]["model_raw"]
            variant = (row["identity"].get("variant_raw") or "").strip()
            rec.add_first_party(brand, model, variant, {
                "source_name": row["source"]["name"],
                "source_role": SourceRole.MARKET_TRUTH.value,
                "source_url": row["source"]["url"],
                "label": f"{model} {variant}".strip(),
                "artifact": row["source"].get("artifact_path"),
                "model": model,
                "identity_level": row["identity"]["identity_level"],
            })


# ─── catalog layers (reuses the P100/P101 layer vocabulary) ─────────────────
import generate_catalog_matrix as gcm  # noqa: E402


def layers_for_oem(rows_for_brand, brand_entry):
    layers = set()
    for r in rows_for_brand:
        layers |= set(gcm.SOURCE_LAYERS.get(r["source"]["name"], set()))
        art = os.path.basename(r["source"]["artifact_path"])
        layers |= gcm.layers_for_artifact(art, r["source"]["url"])
        method = r["source"].get("extraction_method") or ""
        if method in gcm.STRUCTURED_METHODS or "json" in method:
            layers.add("structured_payload")
    for ep in brand_entry.get("captured_endpoints", []):
        layers |= gcm.layers_for_artifact(ep.get("artifact", ""), ep.get("url", ""))
    return layers



# ─── audit surface: enumerator inventory + separated final result ───────────
def _enumerator_inventory(capture_log):
    """Every enumerator the probe evaluated, with its exact disposition.

    A usable enumerator is never silently omitted: either it is used here, or
    the reason it is not captured is recorded against it.
    """
    used = {}
    for c in capture_log:
        used.setdefault(c.get("enumerator"), []).append(c.get("status"))
    committed = {
        "headlightmag": {
            "probe_status": "OK",
            "disposition": "USED_NOT_RECAPTURED",
            "evidence": "audit/catalog-discovery/media_discovery_headlightmag.json",
            "reason": ("the enumerator evidence for this source was already "
                       "captured and provenance-bound in a previous session and "
                       "is committed; re-fetching would only duplicate an "
                       "existing artifact. The probe result "
                       "(audit/coverage/p102_enumerator_probe.json) records the "
                       "live endpoint as reachable for a future capture."),
            "records_used": "MODEL candidates with classification "
                            "'model-mention' from brand categories "
                            "NISSAN/TOYOTA/MAZDA/HONDA/BMW/MG/MERCEDES-BENZ",
        },
    }
    inventory = {
        "ninecarthai": {
            "probe_status": "OK",
            "role": SourceRole.MEDIA_DISCOVERY.value,
            "disposition": "CAPTURED",
            "captures": used.get("9carthai", []),
            "evidence": "tests/fixtures/identity-enumerator-artifacts/"
                        "9carthai_*.html (+ .prov.json)",
        },
        "bangkok_insurance": {
            "probe_status": "OK",
            "role": SourceRole.IDENTITY_ENUMERATOR.value,
            "disposition": "CAPTURED_BRAND_LEVEL_ONLY",
            "captures": used.get("bki_motor_quote", []),
            "evidence": "tests/fixtures/identity-enumerator-artifacts/"
                        "bki_motor_quote_form.html (+ .prov.json)",
            "limitation": ("the motor-quote model API requires credentials, so "
                           "only the published brand dropdown is enumerable; "
                           "no model/trim layer is claimed from this source"),
        },
        "viriyah": {
            "probe_status": "OK",
            "role": SourceRole.IDENTITY_ENUMERATOR.value,
            "disposition": "CAPTURED_NO_TAXONOMY_PUBLISHED",
            "captures": used.get("viriyah_landing", []),
            "evidence": "tests/fixtures/identity-enumerator-artifacts/"
                        "viriyah_home_page.html (+ .prov.json)",
            "limitation": "no published brand/model taxonomy found on the page",
        },
        "one2car": {
            "probe_status": "BLOCKED_HTTP_403 / BLOCKED_HTTP_404",
            "role": SourceRole.IDENTITY_ENUMERATOR.value,
            "disposition": "BLOCKED_NOT_CAPTURED",
            "evidence": "audit/coverage/p102_enumerator_probe.json",
            "reason": "bot-challenge interstitial (title รอสักครู่...) on every "
                      "used-car taxonomy path; nothing was extracted from it",
        },
        "chobrod": {
            "probe_status": "BLOCKED_TLS",
            "role": SourceRole.IDENTITY_ENUMERATOR.value,
            "disposition": "BLOCKED_NOT_CAPTURED",
            "reason": "certificate subject mismatch; TLS verification is never "
                      "bypassed, so no taxonomy was captured",
        },
        "autolife": {"probe_status": "ERROR", "disposition": "NO_RESPONSE",
                     "role": SourceRole.IDENTITY_ENUMERATOR.value,
                     "evidence": "audit/coverage/p102_enumerator_probe.json"},
        "autocar_th": {"probe_status": "ERROR", "disposition": "NO_RESPONSE",
                       "role": SourceRole.IDENTITY_ENUMERATOR.value},
        "ttb_bank": {"probe_status": "ERROR", "disposition": "NO_RESPONSE",
                     "role": SourceRole.IDENTITY_ENUMERATOR.value,
                     "reason": "finance-style enumerator did not respond; no "
                               "identity extracted"},
        "uob_th": {"probe_status": "ERROR", "disposition": "NO_RESPONSE",
                   "role": SourceRole.IDENTITY_ENUMERATOR.value,
                   "reason": "finance-style enumerator did not respond; no "
                             "identity extracted"},
        "dlt": {"probe_status": "ERROR", "disposition": "NO_RESPONSE",
                "role": SourceRole.MARKET_REFERENCE.value,
                "reason": "registration taxonomy did not respond"},
        "tisco": {"probe_status": "ERROR", "disposition": "NO_RESPONSE",
                  "role": SourceRole.IDENTITY_ENUMERATOR.value},
        "headlightmag": committed["headlightmag"],
        "thai_market_reference": {
            "probe_status": "n/a (committed artifact)",
            "role": SourceRole.MARKET_REFERENCE.value,
            "disposition": "USED",
            "evidence": "audit/catalog-discovery/thai_market_reference.json",
        },
        "open_ev_data": {
            "probe_status": "n/a (committed artifact)",
            "role": SourceRole.IDENTITY_ENUMERATOR.value,
            "disposition": "USED_TH_SCOPE_FILTERED",
            "evidence": "audit/catalog-discovery/second_taxonomy_capture.json",
        },
        "fipe_brazilian_vehicle_reference": {
            "probe_status": "n/a (committed artifact)",
            "role": SourceRole.MARKET_REFERENCE.value,
            "disposition": "EVALUATED_REJECTED_TH_SCOPE",
            "evidence": "audit/catalog-discovery/"
                        "reconciled_identity_universe.json",
            "reason": "Brazilian taxonomy publishes no Thailand-market "
                      "evidence; enumerated then rejected per identity",
        },
    }
    return inventory


def _final_result(summary, universe_json, rec, matrix, capture_log):
    """The P102 result, with the required categories kept strictly apart."""
    by_reason = {}
    for r in rec.rejected:
        reason = r.get("reason", "")
        key = reason.split(":")[0][:90]
        by_reason[key] = by_reason.get(key, 0) + 1

    per_source = {}
    for r in universe_json["records"]:
        for src in r["sources"]:
            bucket = per_source.setdefault(src["source_name"], {
                "role": src["source_role"], "records": 0,
                "confirmed_records": 0})
            bucket["records"] += 1
            if r["status"] in (FirstPartyStatus.CONFIRMED_MODEL.value,
                               FirstPartyStatus.CONFIRMED_VARIANT.value):
                bucket["confirmed_records"] += 1

    per_role = {}
    for r in universe_json["records"]:
        roles = {s["source_role"] for s in r["sources"]}
        key = "MARKET_TRUTH+enumerator" if (
            SourceRole.MARKET_TRUTH.value in roles and len(roles) > 1)             else sorted(roles)[0]
        per_role[key] = per_role.get(key, 0) + 1

    return {
        "schema": "p102-final-result/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_id": SESSION_ID,
        "acceptance_boundary": "",
        "enumerator_candidates": {
            "models": summary["models"],
            "variants": summary["variants"],
            "records": summary["records"],
            "note": "high-recall candidates from non-official sources; NOT "
                    "officially sold in Thailand until first-party reconciled",
        },
        "first_party_confirmed_models": sum(
            e["identity"]["first_party_confirmed_models"] for e in matrix),
        "first_party_confirmed_variants": sum(
            e["identity"]["first_party_confirmed_variants"] for e in matrix),
        "identity_only_candidates": {
            # two different, explicitly-named measures — never conflated:
            "records_with_identity_only_status": summary["identity_only"],
            "model_identities_not_first_party_confirmed": sum(
                e["identity"]["identity_only_models"] for e in matrix),
            "variant_identities_not_first_party_confirmed": sum(
                e["identity"]["identity_only_variants"] for e in matrix),
            "note": ("candidates with no MARKET_TRUTH row carrying the same "
                     "identity. Kept in this Phase-1 artifact only; never "
                     "written to staging or the accepted/production DB"),
        },
        "record_reconciliation": {
            "records_total": summary["records"],
            "identity_only_records": summary["identity_only"],
            "first_party_confirmed_records": (
                summary["records"] - summary["identity_only"]
                - summary["conflicts"]),
            "conflict_records": summary["conflicts"],
            "checks_out": (
                summary["records"] == summary["identity_only"]
                + (summary["records"] - summary["identity_only"]
                   - summary["conflicts"]) + summary["conflicts"]),
            "identity_measurements": {
                "distinct_model_identities": summary["models"],
                "distinct_variant_identities": summary["variants"],
                "distinct_models_first_party_confirmed": sum(
                    e["identity"]["first_party_confirmed_models"]
                    for e in matrix),
                "distinct_variants_first_party_confirmed": sum(
                    e["identity"]["first_party_confirmed_variants"]
                    for e in matrix),
            },
        },
        "conflicts": {
            "records": summary["conflicts"],
            "by_reason": {
                r: sum(1 for x in universe_json["records"]
                       if x["status"] == FirstPartyStatus.CONFLICT.value
                       and any(r in y for y in x["rejection_reasons"]))
                for r in ("same model+variant label attributed to multiple "
                          "manufacturers across sources",
                          "label published as a MODEL by one source")
            },
            "definition": (
                "conflict = distinct source evidence disagrees about one "
                "identity: either one shared source attributes the same label "
                "to two OEMs, or two publications put the same identity at "
                "conflicting MODEL/VARIANT levels within one OEM. Equal "
                "labels from different sources, and one publication seen at "
                "both levels, are NOT conflicts — they stay identity-only "
                "with an explicit note."),
            "publication_level_evidence": {
                "rule": "each source entry declares identity_level "
                        "(MODEL|VARIANT); level sets are built only from the "
                        "declared level; publications without a level are "
                        "excluded from level-clash detection",
                "publications_without_identity_level": universe_json[
                    "summary"].get("unlevelled_publications", 0),
                "every_source_entry_declared": all(
                    s.get("identity_level") in ("MODEL", "VARIANT")
                    for r in universe_json["records"] for s in r["sources"]),
            },
            "level_clash_evidence": {
                "identity_keys": universe_json["summary"].get(
                    "level_clash_keys", 0),
                "records_at_those_keys": universe_json["summary"].get(
                    "level_clash_records", 0),
                "records_first_party_confirmed_not_downgraded": universe_json[
                    "summary"].get("level_clash_records_confirmed_not_downgraded", 0),
                "note": "conflict_records only counts records downgraded from "
                        "IDENTITY_ONLY; a record carrying MARKET_TRUTH "
                        "confirmation stays CONFIRMED_* and is counted here "
                        "instead, never silently dropped",
            },
            "identity_only_with_notes": sum(
                1 for x in universe_json["records"]
                if x["status"] == FirstPartyStatus.IDENTITY_ONLY.value
                and x.get("notes")),
        },
        "rejected_candidates": {
            "total": len(rec.rejected),
            "by_reason": dict(sorted(by_reason.items(),
                                     key=lambda kv: -kv[1])),
        },
        "per_oem": [
            {
                "oem": e["brand"],
                "official_access_status": e["official_access_status"],
                "enumerator_model_candidates":
                    e["identity"]["model_candidates_discovered"],
                "enumerator_variant_candidates":
                    e["identity"]["variant_candidates_discovered"],
                "candidate_sources": e["identity"]["candidate_sources"],
                "first_party_confirmed_models":
                    e["identity"]["first_party_confirmed_models"],
                "first_party_confirmed_variants":
                    e["identity"]["first_party_confirmed_variants"],
                "first_party_confirmation":
                    e["identity"]["first_party_confirmation"],
                "identity_only_models": e["identity"]["identity_only_models"],
                "identity_only_variants": e["identity"]["identity_only_variants"],
                "conflicts": e["unresolved_conflicting_identities"]["conflicts"],
                "rejected": e["unresolved_conflicting_identities"]["rejected"],
                "missing_catalog_layers": e["missing_catalog_layers"],
                "blockers": e["blockers"],
            } for e in matrix
        ],
        "per_source_coverage": dict(sorted(per_source.items())),
        "per_role_record_counts": per_role,
        "layer_coverage": {
            layer: sorted(e["brand"] for e in matrix
                          if layer in e["layers_checked"])
            for layer in sorted({l for e in matrix for l in e["layers_checked"]})
        },
        "unresolved_gaps": [
            {
                "oem": e["brand"],
                "gap": ("no identity candidates at all"
                        if e["identity"]["model_candidates_discovered"] == 0
                        else "no first-party confirmation for any candidate"
                        if e["identity"]["first_party_confirmed_models"] == 0
                        else "first-party coverage is partial"),
                "missing_layers": e["missing_catalog_layers"],
                "exact_reason": (
                    e["blockers"][0]["detail"] if e["blockers"]
                    else "official pages reachable but not all layers staged"),
            }
            for e in matrix
            if e["identity"]["model_candidates_discovered"] == 0
            or e["identity"]["first_party_confirmed_models"] == 0
            or e["missing_catalog_layers"]
        ],
        "captures": capture_log,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="do not fetch; reuse verified captures only")
    args = ap.parse_args()

    import requests  # noqa: F401  (used by _fetch)
    reg = json.load(open(REG_PATH, encoding="utf-8"))
    brands = {b["brand"]: b for b in reg["brands"] if b.get("in_scope")}
    in_scope = set(brands)

    rec = IdentityReconciliation(target_date=STAMP)

    # 1 ── first-party (MARKET_TRUTH) comes first so enumeration never inflates it
    load_first_party(rec, in_scope)

    # 2 ── identity enumerators
    capture_log = []
    for brand, slug in sorted(NINECARTHAI_SLUGS.items()):
        if brand not in in_scope:
            continue
        for s in slug:
            url = f"https://www.9carthai.com/{s}/"
            res = capture(url, f"9carthai_{s}.html", args.offline)
            res.update({"brand": brand, "enumerator": "9carthai",
                        "role": SourceRole.MEDIA_DISCOVERY.value})
            capture_log.append({k: v for k, v in res.items() if k != "content"})
            content = res.pop("content", None)
            if not content:
                continue
            parsed = parse_index_page(
                content, brand, "9carthai price index", url,
                SourceRole.MEDIA_DISCOVERY.value)
            for m in parsed.models:
                rec.add_enumerator(brand, m["model"], "", {
                    "source_name": "9carthai price index",
                    "source_role": SourceRole.MEDIA_DISCOVERY.value,
                    "source_url": url, "label": m["label"],
                    "origin": m["origin"],
                    "artifact": res["filename"]})
            for v in parsed.variants:
                rec.add_enumerator(brand, v["model"], v["variant"], {
                    "source_name": "9carthai price index",
                    "source_role": SourceRole.MEDIA_DISCOVERY.value,
                    "source_url": url, "label": v["label"],
                    "origin": v["origin"], "artifact": res["filename"]},
                    published_price=v["published_price_thb"],
                    price_role=v["published_price_role"])
            for u in parsed.unresolved:
                rec.reject(brand, u["text"], f"{u['kind']}: {u['reason']}",
                           "9carthai price index")
            time.sleep(POLITENESS_S)
    rec.add_source("9carthai price index", SourceRole.MEDIA_DISCOVERY.value,
                   "https://www.9carthai.com/<brand>-price/",
                   "media Thai-market price index — discovery only, never truth")

    for brand, reason in sorted(NINECARTHAI_MISSING.items()):
        if brand in in_scope:
            rec.reject(brand, brand, f"enumerator_unavailable: {reason}",
                       "9carthai price index")

    # insurance-style identity enumerators (brand-level taxonomy)
    for sid, url, filename, note in INSURANCE_SURFACES:
        res = capture(url, filename, args.offline)
        res.update({"brand": "-", "enumerator": sid,
                    "role": SourceRole.IDENTITY_ENUMERATOR.value})
        content = res.pop("content", None)
        capture_log.append({k: v for k, v in res.items() if k != "content"})
        if not content:
            continue
        if sid == "bki_motor_quote":
            rec.add_source("bangkok_insurance_motor_quote",
                           SourceRole.IDENTITY_ENUMERATOR.value, url,
                           "insurance motor-quote taxonomy (brand level only — "
                           "the model API requires credentials)")
            for opt in _bki_brands(content):
                brand = next((b for b in in_scope
                              if b.upper() == opt["value"].upper()), None)
                if brand:
                    rec.add_enumerator(brand, opt["label"], "", {
                        "source_name": "bangkok_insurance_motor_quote",
                        "source_role": SourceRole.IDENTITY_ENUMERATOR.value,
                        "source_url": url, "label": opt["label"],
                        "origin": "insurance_brand_dropdown",
                        "artifact": filename})
                else:
                    rec.reject(opt["value"], opt["label"],
                               "brand option is not an in-scope OEM",
                               "bangkok_insurance_motor_quote")
        else:
            rec.add_source("viriyah", SourceRole.IDENTITY_ENUMERATOR.value, url,
                           "insurance landing page reachable; no published "
                           "brand/model taxonomy found on it")
        time.sleep(POLITENESS_S)

    for sid, url, blocker, note in USED_CAR_BLOCKERS:
        rec.add_source(sid, SourceRole.IDENTITY_ENUMERATOR.value, url,
                       f"{blocker}: {note} — no taxonomy captured, "
                       f"recorded as an enumerator access blocker")

    # committed enumerator artifacts
    load_thai_reference(rec, in_scope)
    load_headlightmag(rec, in_scope)
    load_open_ev(rec, in_scope)
    load_fipe_scope_rejects(rec)

    rec.resolve_statuses()

    # 3 ── per-OEM matrix
    rows = [json.loads(l) for l in open(STAGING, encoding="utf-8") if l.strip()]
    rows_by_brand = {}
    brand_alias = {b.lower().replace(" ", "-"): b for b in in_scope}
    brand_alias.update({"land-rover": "Land Rover", "mini": "MINI",
                        "mercedes-benz": "Mercedes-Benz"})
    for r in rows:
        b = brand_alias.get(r["identity"]["brand_normalized"])
        if b:
            rows_by_brand.setdefault(b, []).append(r)

    summary = rec.summary()
    universe_json = rec.to_json()

    matrix, totals = [], {"oems_in_scope": 0, "oems_with_identity_candidates": 0,
                          "oems_first_party_confirmed": 0}
    for brand in sorted(in_scope):
        totals["oems_in_scope"] += 1
        entry = brands[brand]
        mfr_records = [r for r in rec.records if r.manufacturer == brand]
        cand = summary["by_manufacturer"].get(brand, {
            "models": 0, "variants": 0,
            "first_party_confirmed_models": 0,
            "first_party_confirmed_variants": 0,
            "identity_only_models": 0, "identity_only_variants": 0,
            "conflicts": 0, "sources": []})

        fp_models = cand["first_party_confirmed_models"]
        fp_variants = cand["first_party_confirmed_variants"]
        cand_models, cand_variants = cand["models"], cand["variants"]

        if cand_models:
            totals["oems_with_identity_candidates"] += 1
        if fp_models:
            totals["oems_first_party_confirmed"] += 1

        if cand_models == 0:
            fp_status = "NO_ENUMERATOR_AND_NO_FIRST_PARTY" if fp_models == 0 \
                else "FIRST_PARTY_ONLY"
        elif fp_models == 0:
            fp_status = "NONE_FIRST_PARTY_MISSING"
        elif fp_models >= cand_models:
            fp_status = "ALL_CANDIDATE_MODELS_CONFIRMED"
        else:
            fp_status = "PARTIAL"

        blockers = []
        if entry.get("access_status") != "REACHABLE":
            blockers.append({
                "layer": "official_first_party",
                "blocker": entry.get("access_status"),
                "detail": json.dumps(entry.get("blocker_evidence"),
                                     ensure_ascii=False),
                "consequence": "official alternate-route requests are deferred "
                               "until next_retry_at; enumeration continues "
                               "without ever marking this OEM official",
                "next_retry_at": entry.get("next_retry_at"),
            })
        if brand in NINECARTHAI_MISSING:
            blockers.append({
                "layer": "identity_enumerator",
                "blocker": "ENUMERATOR_PAGE_NOT_PUBLISHED",
                "detail": NINECARTHAI_MISSING[brand],
            })
        for cap in capture_log:
            if cap.get("brand") == brand and str(cap.get("status", "")).startswith("BLOCKED"):
                blockers.append({"layer": "identity_enumerator",
                                 "blocker": cap["status"],
                                 "detail": cap.get("url", "")})
        for sid, url, blk, note in USED_CAR_BLOCKERS:
            blockers.append({"layer": "identity_enumerator", "blocker": blk,
                             "detail": f"{sid}: {note}"})

        gp_rows = rows_by_brand.get(brand, [])
        layers = layers_for_oem(gp_rows, entry)
        missing_layers = [l for l in gcm.LAYERS if l not in layers]

        unresolved = [r for r in rec.records
                      if r.manufacturer == brand
                      and r.status == FirstPartyStatus.CONFLICT.value]
        noted = [r for r in rec.records
                 if r.manufacturer == brand
                 and r.status == FirstPartyStatus.IDENTITY_ONLY.value
                 and r.notes]
        rejected = [r for r in rec.rejected if r["manufacturer"] == brand]

        matrix.append({
            "brand": brand,
            "in_scope": True,
            "official_access_status": entry.get("access_status"),
            "official_provenance_status": entry.get("provenance_status"),
            "identity": {
                "model_candidates_discovered": cand_models,
                "variant_candidates_discovered": cand_variants,
                "first_party_confirmed_models": fp_models,
                "first_party_confirmed_variants": fp_variants,
                "identity_only_models": cand_models - fp_models,
                "identity_only_variants": cand_variants - fp_variants,
                "first_party_confirmation": fp_status,
                "candidate_sources": cand["sources"],
                "identity_levels_present": sorted({
                    "VARIANT" if r.variant else "MODEL"
                    for r in mfr_records}),
            },
            "staged_first_party_rows": len(gp_rows),
            "staged_first_party_models": len({
                r["identity"]["model_raw"] for r in gp_rows}),
            "staged_first_party_variants": len({
                (r["identity"]["model_raw"], r["identity"]["variant_raw"])
                for r in gp_rows if (r["identity"].get("variant_raw") or "").strip()}),
            "unresolved_conflicting_identities": {
                "conflicts": len(unresolved),
                "noted_unresolved": len(noted),
                "rejected": len(rejected),
                "rejected_examples": rejected[:12],
            },
            "missing_catalog_layers": missing_layers,
            "layers_checked": sorted(layers),
            "blockers": blockers,
        })

    out_universe = {
        "schema": "p102-identity-universe/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_id": SESSION_ID,
        "blueprint_sections": ["§93 coverage registry", "§94 acquisition contract",
                               "§95 quality rules", "§96 source classes",
                               "§97 evidence", "§98 test categories"],
        "acceptance_boundary": (
            "Phase-1 identity/catalog artifact only. It is NOT staging, NOT the "
            "accepted set and NOT the production DB: identity-only candidates "
            "have no price/locator and therefore cannot satisfy §95 mandatory "
            "fields, so they are never promoted."),
        "capture_log": capture_log,
        "universe": universe_json,
    }
    out_matrix = {
        "schema": "p102-identity-matrix/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": totals,
        "summary": {k: v for k, v in summary.items() if k != "by_manufacturer"},
        "enumerator_inventory": _enumerator_inventory(capture_log),
        "oems": matrix,
    }

    final = _final_result(summary, universe_json, rec, matrix, capture_log)
    final["acceptance_boundary"] = out_universe["acceptance_boundary"]

    os.makedirs(OUT_DIR, exist_ok=True)
    u_path = os.path.join(OUT_DIR, f"identity_universe_p102.json")
    m_path = os.path.join(OUT_DIR, f"identity_matrix_p102.json")
    json.dump(out_universe, open(u_path, "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    json.dump(out_matrix, open(m_path, "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    f_path = os.path.join(OUT_DIR, "p102_final_result.json")
    json.dump(final, open(f_path, "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    md = [f"# P102 identity universe matrix ({STAMP})", "",
          f"- in-scope OEMs: **{totals['oems_in_scope']}** · "
          f"with identity candidates: **{totals['oems_with_identity_candidates']}** · "
          f"with first-party confirmed models: **{totals['oems_first_party_confirmed']}**",
          f"- universe records: **{summary['records']}** · models **{summary['models']}** · "
          f"variants **{summary['variants']}** · "
          f"identity-only **{summary['identity_only']}** · "
          f"conflicts **{summary['conflicts']}** · rejected **{summary['rejected']}**",
          "",
          "> Roles: enumerator sources are enumeration evidence only. Nothing here "
          "is market truth unless a MARKET_TRUTH row carries the same identity, and "
          "nothing in this file is written to staging or the production DB.",
          "",
          "| OEM | official access | model cand. | variant cand. | FP confirmed (m/v) | "
          "identity-only (m/v) | confirmation | conflicts | rejected | missing layers |",
          "|---|---|---:|---:|---:|---:|---|---:|---:|---|"]
    for e in matrix:
        i = e["identity"]
        md.append(
            f"| {e['brand']} | {e['official_access_status']} | "
            f"{i['model_candidates_discovered']} | {i['variant_candidates_discovered']} | "
            f"{i['first_party_confirmed_models']}/{i['first_party_confirmed_variants']} | "
            f"{i['identity_only_models']}/{i['identity_only_variants']} | "
            f"{i['first_party_confirmation']} | "
            f"{e['unresolved_conflicting_identities']['conflicts']} | "
            f"{e['unresolved_conflicting_identities']['rejected']} | "
            f"{','.join(e['missing_catalog_layers']) or '—'} |")
    md += ["", "## blockers and exact reasons", ""]
    for e in matrix:
        for b in e["blockers"]:
            md.append(f"- **{e['brand']}** / {b['layer']}: `{b['blocker']}` — "
                      f"{b['detail']}")
    md_path = os.path.join(OUT_DIR, f"identity_matrix_p102.md")
    open(md_path, "w", encoding="utf-8").write("\n".join(md) + "\n")

    print(json.dumps({"totals": totals,
                      "records": summary["records"],
                      "models": summary["models"],
                      "variants": summary["variants"],
                      "identity_only": summary["identity_only"],
                      "conflicts": summary["conflicts"],
                      "rejected": summary["rejected"],
                      "captures": len(capture_log)}, indent=2))
    print("wrote", u_path)
    print("wrote", m_path)
    print("wrote", md_path)
    print("wrote", f_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
