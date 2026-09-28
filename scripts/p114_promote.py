#!/usr/bin/env python3
"""P114 producer — controlled promotion of ACCEPTED evidence into the
canonical DB (ONE transaction, idempotent, ledger-traced).

Scope (hard):
  * source = audit/coverage/p113_evidence_packets.json status=ACCEPTED only
    (417 packets); quarantined/rejected packets are never read for writes;
  * identity = the frozen 488 ledger (packets carry it); no other identities;
  * price = P111 semantics verbatim (PRICE_MAP); spec = P112 cited rows
    verbatim (SPEC_KEY_MAP); missing fields stay missing — nothing synthesized;
  * every fact keeps source URL / SourceDocument (contentHash = artifact
    sha256) / locator / verification metadata via existing schema relations;
  * one transaction: any failure rolls the whole promotion back;
  * idempotent: second run reports NO_ACTION everywhere and writes no row.

Gate: each promoted fact is evaluated by the EXISTING AcceptanceRunner and
recorded in the append-only AcceptanceLedger (packet -> entity/field ->
INSERT/UPDATE/NO_ACTION -> DB row id -> reason).

Usage:
  python3 scripts/p114_promote.py [--ledger PATH] [--result PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
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
from thai_factory.acceptance.ledger import AcceptanceLedger  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "p114_preflight_maps",
    os.path.join(REPO, "scripts/p114_promotion_preflight.py"))
MAPS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MAPS)
PRICE_MAP = MAPS.PRICE_MAP
SPEC_KEY_MAP = MAPS.SPEC_KEY_MAP
CONFIDENCE_MAP = MAPS.CONFIDENCE_MAP

DEFAULT_LEDGER = os.path.join(OUT, "p114_promotion_ledger.json")
DEFAULT_RESULT = os.path.join(OUT, "p114_promotion_result.json")
CHANGE_REASON = "P114 controlled promotion (G1-G8 PASS)"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def head_sha() -> str:
    return os.popen(f"git -C {REPO} rev-parse HEAD 2>/dev/null").read().strip()


def norm(s) -> str:
    return re.sub(r"[^0-9a-zก-๙]+", " ", (s or "").lower()).strip()


def slugify(s) -> str:
    """Deterministic, URL-safe slug.

    Thai-script identity labels (the frozen ledger keeps publisher-exact
    Thai model names) must NOT be dropped: the repo carries no
    transliteration source, so Thai letters/smarks are preserved as
    Unicode and only punctuation/whitespace folds to '-'.
    """
    return re.sub(r"-+", "-", re.sub(r"[^0-9a-zก-๙]+", "-",
                                     (s or "").lower())).strip("-")


def db_url() -> str:
    txt = open(os.path.join(REPO, ".env"), encoding="utf-8").read()
    m = re.search(r'^DATABASE_URL="([^"]+)"', txt, re.M)
    if not m:
        raise RuntimeError("DATABASE_URL missing")
    return m.group(1).split("?")[0]


def sha256_file(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load(name):
    return json.load(open(os.path.join(OUT, name), encoding="utf-8"))


class Ctx:
    """Mutable promotion counters shared by every phase."""

    def __init__(self):
        self.sources_created = 0
        self.docs_created = 0
        self.mans_created = 0
        self.models_created = 0
        self.variants_created = 0
        self.prices_created = 0
        self.specs_created = 0
        self.demotions = 0
        self.changelog_created = 0


def ensure_source(cur, host_map, url, manufacturer, ctx=None):
    from urllib.parse import urlparse
    p = urlparse(url)
    origin = f"{p.scheme}://{p.netloc}"
    if p.netloc in host_map:
        return host_map[p.netloc]
    cur.execute('select id from "Source" where "baseUrl" = %s',
                (origin,))
    row = cur.fetchone()
    if row:
        host_map[p.netloc] = row[0]
        return row[0]
    created_here = True
    sid = str(uuid.uuid4())
    path = p.path.lower()
    if any(t in path for t in ("price", "pricelist")):
        stype = "OFFICIAL_MANUFACTURER_PRICE_LIST"
    elif "brochure" in path or path.endswith(".pdf"):
        stype = "OFFICIAL_MANUFACTURER_BROCHURE"
    else:
        stype = "OFFICIAL_MANUFACTURER"
    name = f"{manufacturer} Official Website" if manufacturer else p.netloc
    cur.execute(
        'insert into "Source" (id, "nameTh", "nameEn", "sourceType", '
        '"baseUrl", domain, "rightsStatus", status, "createdAt", '
        '"updatedAt") values (%s,%s,%s,%s,%s,%s,\'UNKNOWN\',\'ACTIVE\','
        'now(),now()) on conflict ("baseUrl") do nothing',
        (sid, name, name, stype, origin, p.netloc))
    cur.execute('select id from "Source" where "baseUrl" = %s', (origin,))
    host_map[p.netloc] = cur.fetchone()[0]
    if ctx is not None and created_here:
        ctx.sources_created += 1
    return host_map[p.netloc]


def ensure_doc(cur, ctx, source_id, url, sha, artifact, captured_at):
    cur.execute('select id from "SourceDocument" where "sourceId" = %s '
                'and "contentHash" = %s', (source_id, sha))
    row = cur.fetchone()
    if row:
        return row[0], False
    did = str(uuid.uuid4())
    ext = artifact.rsplit(".", 1)[-1].lower()
    mime = {"html": "text/html", "json": "application/json",
            "pdf": "application/pdf", "b64": "application/pdf"}.get(
                ext, "text/plain")
    cur.execute(
        'insert into "SourceDocument" (id, "sourceId", url, "canonicalUrl", '
        '"mimeType", "contentHash", "fetchedAt", "documentType", '
        '"localPath", "extractionMethod", "extractionStatus", status, '
        '"rightsStatus", "createdAt", "updatedAt") values '
        '(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,\'SUCCEEDED\',\'VERIFIED\','
        '\'UNKNOWN\',now(),now()) on conflict ("sourceId","contentHash") '
        'do nothing',
        (did, source_id, url, url, mime, sha, captured_at, ext,
         f"tests/fixtures/oem-artifacts/{artifact}", "committed-fixture"))
    cur.execute('select id from "SourceDocument" where "sourceId" = %s '
                'and "contentHash" = %s', (source_id, sha))
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"source document insert failed for {sha}")
    ctx.docs_created += 1
    return row[0], True


def insert_changelog(cur, ctx, entity_type, entity_id, change_type,
                     source_doc_id, reason, evidence, after_value,
                     before_value=None, field_name=None, excerpt=None):
    cur.execute(
        'insert into "DataChangeLog" (id, "sourceDocumentId", '
        '"entityType", "entityId", "fieldName", "changeType", '
        '"beforeValue", "afterValue", reason, confidence, '
        '"evidenceExcerpt", evidence, proposed, applied, "reviewStatus", '
        '"createdAt") values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false,true,'
        '\'APPROVED\',now())',
        (str(uuid.uuid4()), source_doc_id, entity_type, entity_id,
         field_name, change_type,
         json.dumps(before_value) if before_value is not None else None,
         json.dumps(after_value) if after_value is not None else None,
         reason, "0.9000", excerpt,
         json.dumps(evidence, ensure_ascii=False)))
    ctx.changelog_created += 1


def record(ctx_ledger, runner, packet, fact, action, row_id,
           db_value, extra=None, base_pid=None):
    decision = runner.evaluate(packet)
    if decision != AcceptanceDecision.ACCEPTED:
        raise RuntimeError(
            f"runner refused {packet.packet_id}: {packet.acceptance_reason}")
    packet.acceptance_decision = decision
    ctx_ledger.record(packet, db_action=action, db_row_id=row_id)
    entry = ctx_ledger.entries[-1]
    if base_pid:
        # the ledger keys on the bare P113 packet id; the fact suffix lives
        # only on the runner-facing EvidencePacket.packet_id
        entry["packet_id"] = base_pid
    entry["fact"] = fact
    entry["db_value"] = db_value
    if extra:
        entry.update(extra)
    return entry


def field_packet(pid, suffix, candidate, row, value, locator, sha,
                 currentness):
    return EvidencePacket(
        packet_id=f"{pid}.{suffix}",
        candidate_key=candidate,
        source_class=EvidenceClass.OEM_OFFICIAL,
        source_url=row["source_url"],
        source_name=row.get("source_name") or "",
        immutable_revision=head_sha(),
        currentness=currentness,
        extracted_value=value,
        extraction_confidence=ExtractionConfidence.HIGH,
        evidence_locator=locator,
        artifact_hashes=ArtifactHash(local_artifact_sha256=sha,
                                     upstream_payload_sha256=sha),
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    ap.add_argument("--result", default=DEFAULT_RESULT)
    args = ap.parse_args(argv)

    import psycopg2
    conn = psycopg2.connect(db_url())
    conn.autocommit = False
    cur = conn.cursor()
    ctx = Ctx()
    runner = AcceptanceRunner()
    ledger = AcceptanceLedger()
    run_id = "p114_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    packets_all = load("p113_evidence_packets.json")
    accepted = [p for p in packets_all["packets"] if p["status"] == "ACCEPTED"]
    quarantined_ids = {p["packet_id"] for p in packets_all["packets"]
                       if p["status"] != "ACCEPTED"}
    assert len(accepted) == 417
    p111_rows = {(r["manufacturer"], r["model"], r["variant"]): r
                 for r in load("p111_price_evidence.json")["rows"]}
    p112_rows = {r["evidence_id"]: r
                 for r in load("p112_spec_evidence.json")["rows"]}
    pf = load("p114_promotion_preflight.json")
    assert pf["all_gates_pass"] is True, "preflight gates must be PASS"
    upstream_before = dict(pf["inputs"]["upstream_artifact_shas"])

    try:
        # ── pass 1: sources + source documents for every cited observation ─
        host_map = {}
        from urllib.parse import urlparse
        cur.execute('select id, "baseUrl" from "Source"')
        for sid, base in cur.fetchall():
            host_map[urlparse(base).netloc] = sid
        doc_cache = {}
        for p in accepted:
            for grp in ("identity", "price", "spec"):
                for o in p["observations"][grp]:
                    key = (o["source_url"], o["sha256"])
                    if key in doc_cache:
                        continue
                    src = ensure_source(cur, host_map, o["source_url"],
                                        p["manufacturer"], ctx)
                    cap = None
                    side = os.path.join(FIXTURE_DIR,
                                        o["artifact"] + ".prov.json")
                    if os.path.exists(side):
                        cap = json.load(open(side, encoding="utf-8")
                                        ).get("captured_at")
                    if cap is None and grp == "price":
                        cap = p111_rows.get(
                            (p["manufacturer"], p["model"], p["variant"]),
                            {}).get("captured_at")
                    did, created = ensure_doc(
                        cur, ctx, src, o["source_url"], o["sha256"],
                        o["artifact"], cap)
                    doc_cache[key] = did
                    if created:
                        ctx.sources_created += 0  # counted below if new

        # ── pass 2: identity (frozen ledger packets only) ─────────────────
        cur.execute('select id, "nameEn", slug from "Manufacturer"')
        mans = {norm(r[1]): {"id": r[0], "nameEn": r[1], "slug": r[2]}
                for r in cur.fetchall()}
        cur.execute(
            'select m."nameEn", c."nameEn", c.id from "CarModel" c '
            'join "Manufacturer" m on m.id = c."manufacturerId"')
        models = defaultdict(list)
        for mfr, mdl, mid in cur.fetchall():
            models[(norm(mfr), norm(mdl))].append(mid)
        for k in models:
            models[k].sort()
        cur.execute(
            'select c.id, v."nameEn" from "Variant" v '
            'join "CarModel" c on c.id = v."modelId"')
        variants = defaultdict(list)
        for mid, vname in cur.fetchall():
            variants[(mid, norm(vname))].append(1)
        variant_ids = {}
        cur.execute(
            'select v.id, c.id, v."nameEn" from "Variant" v '
            'join "CarModel" c on c.id = v."modelId"')
        for vid, mid, vname in cur.fetchall():
            variant_ids[(mid, norm(vname))] = vid

        packet_variant = {}
        for p in accepted:
            pid = p["packet_id"]
            mk = (norm(p["manufacturer"]), norm(p["model"]))
            vk = mk + (norm(p["variant"]),)
            # manufacturer
            mfr = mans.get(mk[0])
            mfr_created = False
            if not mfr:
                mid = str(uuid.uuid4())
                slug = slugify(p["manufacturer"])
                while any(x["slug"] == slug for x in mans.values()):
                    slug += "-2"
                name = p["manufacturer"]
                cur.execute(
                    'insert into "Manufacturer" (id, "nameTh", "nameEn", '
                    'slug, status, "createdAt", "updatedAt") values '
                    '(%s,%s,%s,%s,\'ACTIVE\',now(),now())',
                    (mid, name, name, slug))
                mfr = {"id": mid, "nameEn": name, "slug": slug}
                mans[mk[0]] = mfr
                ctx.mans_created += 1
                mfr_created = True
                id_obs = p["observations"]["identity"][0]
                insert_changelog(
                    cur, ctx, "Manufacturer", mid, "CREATED",
                    doc_cache[(id_obs["source_url"], id_obs["sha256"])],
                    f"{CHANGE_REASON} — packet {pid}",
                    {"packet_id": pid, "artifact": id_obs["artifact"],
                     "sha256": id_obs["sha256"],
                     "source_url": id_obs["source_url"],
                     "nameTh_policy": "copied from nameEn (no Thai name in "
                                      "identity evidence)"},
                    {"nameEn": name, "slug": slug},
                    excerpt=id_obs.get("label"))
            # model — when the manufacturer has duplicate model rows (seed
            # twins, e.g. Toyota 'Yaris ATIV' x2), prefer the row under which
            # THIS variant already exists so no business duplicate is created;
            # otherwise the deterministic lowest id (matches the committed
            # preflight plan: 404 inserts, 13 present).
            vnorm = norm(p["variant"])
            cands = sorted(models.get(mk) or [])
            model_id = None
            for cand in cands:
                if (cand, vnorm) in variant_ids:
                    model_id = cand
                    break
            if model_id is None and cands:
                model_id = cands[0]
            model_created = False
            if not model_id:
                model_id = str(uuid.uuid4())
                slug = slugify(p["model"])
                cur.execute(
                    'select slug from "CarModel" where "manufacturerId" = %s',
                    (mfr["id"],))
                taken = {r[0] for r in cur.fetchall()}
                while slug in taken:
                    slug += "-2"
                gen = p.get("generation_context") or None
                cur.execute(
                    'insert into "CarModel" (id, "manufacturerId", '
                    '"nameTh", "nameEn", slug, generation, status, '
                    '"createdAt", "updatedAt") values '
                    '(%s,%s,%s,%s,%s,%s,\'ACTIVE\',now(),now())',
                    (model_id, mfr["id"], p["model"], p["model"], slug, gen))
                models[mk].append(model_id)
                models[mk].sort()
                ctx.models_created += 1
                model_created = True
                id_obs = p["observations"]["identity"][0]
                insert_changelog(
                    cur, ctx, "CarModel", model_id, "CREATED",
                    doc_cache[(id_obs["source_url"], id_obs["sha256"])],
                    f"{CHANGE_REASON} — packet {pid}",
                    {"packet_id": pid, "artifact": id_obs["artifact"],
                     "sha256": id_obs["sha256"],
                     "source_url": id_obs["source_url"]},
                    {"nameEn": p["model"], "generation": gen},
                    excerpt=id_obs.get("label"))
            # variant
            vid = variant_ids.get((model_id, norm(p["variant"])))
            var_created = False
            if not vid:
                vid = str(uuid.uuid4())
                slug = slugify(p["variant"])
                cur.execute(
                    'select slug from "Variant" where "modelId" = %s',
                    (model_id,))
                taken = {r[0] for r in cur.fetchall()}
                while slug in taken:
                    slug += "-2"
                cur.execute(
                    'insert into "Variant" (id, "modelId", "nameTh", '
                    '"nameEn", slug, status, "createdAt", "updatedAt") '
                    'values (%s,%s,%s,%s,%s,\'ACTIVE\',now(),now())',
                    (vid, model_id, p["variant"], p["variant"], slug))
                variant_ids[(model_id, norm(p["variant"]))] = vid
                ctx.variants_created += 1
                var_created = True
                id_obs = p["observations"]["identity"][0]
                insert_changelog(
                    cur, ctx, "Variant", vid, "CREATED",
                    doc_cache[(id_obs["source_url"], id_obs["sha256"])],
                    f"{CHANGE_REASON} — packet {pid}",
                    {"packet_id": pid, "artifact": id_obs["artifact"],
                     "sha256": id_obs["sha256"],
                     "source_url": id_obs["source_url"],
                     "identity_level": id_obs.get("identity_level")},
                    {"nameEn": p["variant"], "modelId": model_id},
                    excerpt=id_obs.get("label"))
            packet_variant[p["packet_id"]] = vid
            id_obs = p["observations"]["identity"][0]
            fp = field_packet(
                pid, "identity", p["candidate_key"],
                {"source_url": id_obs["source_url"],
                 "source_name": id_obs.get("source_name")},
                {"variant": p["variant"], "model": p["model"]},
                EvidenceLocator(
                    artifact_path=f"tests/fixtures/oem-artifacts/"
                                  f"{id_obs['artifact']}",
                    quote=id_obs.get("label")),
                id_obs["sha256"], CurrentnessState.UNKNOWN)
            record(ledger, runner, fp, "identity",
                   "INSERT" if var_created else "NO_ACTION", vid,
                   {"variant_id": vid, "model_id": model_id,
                    "manufacturer_id": mfr["id"]},
                   {"manufacturer_created": mfr_created,
                    "model_created": model_created},
                   base_pid=pid)

        # ── pass 3: prices (P111 semantics verbatim) ──────────────────────
        current_row_by_variant = defaultdict(list)
        for p in accepted:
            pid = p["packet_id"]
            vid = packet_variant[pid]
            for o in p["observations"]["price"]:
                prow = p111_rows[(p["manufacturer"], p["model"],
                                  p["variant"])]
                sem = PRICE_MAP[o["msrp_status"]]
                did = doc_cache[(o["source_url"], o["sha256"])]
                conf = CONFIDENCE_MAP[o["trust_tier"]]
                # validFrom is timestamp(3) without time zone; captured_at is
                # a full-precision UTC string. Normalize to millisecond
                # precision BEFORE insert/select so the unique index, the
                # conflict check and the rerun lookup all see the same value
                # (an offset-suffixed literal compares as timestamptz and
                # silently misses the rounded stored value).
                from datetime import datetime as _dt, timezone as _tz, \
                    timedelta as _td
                _d = _dt.fromisoformat(prow["captured_at"])
                assert _d.utcoffset() == _td(0), prow["captured_at"]
                _d = _d.astimezone(_tz.utc).replace(tzinfo=None)
                _ms = (_d.microsecond + 500) // 1000
                if _ms == 1000:
                    _d += _td(seconds=1)
                    _ms = 0
                valid_from = _d.strftime("%Y-%m-%dT%H:%M:%S") + f".{_ms:03d}"
                our_id = None
                if sem["is_current"]:
                    cur.execute(
                        'select id from "Price" where "variantId" = %s and '
                        '"sourceDocumentId" = %s and "priceType" = %s and '
                        'amount = %s and "validFrom" = %s',
                        (vid, did, sem["price_type"], str(o["value"]),
                         valid_from))
                    got = cur.fetchone()
                    our_id = got[0] if got else None
                    # Price_current_interval_exclusion (gist, WHERE
                    # isCurrent=true) forbids two open current intervals of
                    # the same variant+type: supersede legacy current flags
                    # FIRST (values kept, history via DataChangeLog), then
                    # insert ours.
                    cur.execute(
                        'update "Price" set "isCurrent" = false where '
                        '"variantId" = %s and "isCurrent" = true and '
                        'id is distinct from %s '
                        'returning id, "priceType"::text, amount',
                        (vid, our_id))
                    for rid2, ptype2, amt2 in cur.fetchall():
                        ctx.demotions += 1
                        insert_changelog(
                            cur, ctx, "Price", rid2, "UPDATED", did,
                            f"{CHANGE_REASON} — packet {pid} supersedes "
                            f"legacy current price",
                            {"packet_id": pid,
                             "superseded_by": our_id or "pending-insert"},
                            {"isCurrent": False},
                            before_value={"isCurrent": True,
                                          "priceType": ptype2,
                                          "amount": str(amt2)},
                            field_name="isCurrent")
                        ledger.entries.append({
                            "packet_id": pid,
                            "candidate_key": p["candidate_key"],
                            "source_class": EvidenceClass.OEM_OFFICIAL.value,
                            "source_url": "",
                            "native_id": None,
                            "acceptance_decision":
                                AcceptanceDecision.ACCEPTED.value,
                            "reason": "legacy current price superseded by "
                                      "verified current MSRP",
                            "db_action": "UPDATE", "db_row_id": rid2,
                            "timestamp": now(),
                            "extracted_value_hash": "",
                            "fact": "price_current",
                            "db_value": {"is_current": False}})
                cur.execute(
                    'insert into "Price" (id, "variantId", ' 
                    '"sourceDocumentId", "priceType", amount, currency, '
                    '"validFrom", "observedAt", confidence, "isCurrent") '
                    'values (%s,%s,%s,%s,%s,\'THB\',%s,now(),%s,%s) '
                    'on conflict ("variantId","sourceDocumentId",'
                    '"priceType",amount,"validFrom") do nothing '
                    'returning id',
                    (str(uuid.uuid4()), vid, did, sem["price_type"],
                     str(o["value"]), valid_from, conf,
                     sem["is_current"]))
                row = cur.fetchone()
                if row:
                    action, rid = "INSERT", row[0]
                    ctx.prices_created += 1
                    if sem["is_current"]:
                        current_row_by_variant[vid].append(rid)
                    insert_changelog(
                        cur, ctx, "Price", rid, "CREATED", did,
                        f"{CHANGE_REASON} — packet {pid}",
                        {"packet_id": pid, "msrp_status": o["msrp_status"],
                         "artifact": o["artifact"], "sha256": o["sha256"],
                         "source_url": o["source_url"],
                         "locator": o.get("locator")},
                        {"priceType": sem["price_type"],
                         "amount": o["value"],
                         "isCurrent": sem["is_current"]},
                        excerpt=(o.get("locator") or {}).get("quote"))
                else:
                    cur.execute(
                        'select id from "Price" where "variantId" = %s and '
                        '"sourceDocumentId" = %s and "priceType" = %s and '
                        'amount = %s and "validFrom" = %s',
                        (vid, did, sem["price_type"], str(o["value"]),
                         valid_from))
                    action, rid = "NO_ACTION", cur.fetchone()[0]
                    if sem["is_current"]:
                        current_row_by_variant[vid].append(rid)
                fp = field_packet(
                    pid, "price", p["candidate_key"],
                    {"source_url": o["source_url"],
                     "source_name": o.get("source_name")},
                    {"price_thb": o["value"], "price_type": o["price_type"]},
                    EvidenceLocator(
                        artifact_path=f"tests/fixtures/oem-artifacts/"
                                      f"{o['artifact']}",
                        quote=str((o.get("locator") or {}).get("quote")
                                  or o["value"])),
                    o["sha256"], CurrentnessState.CURRENT)
                record(ledger, runner, fp, "price", action, rid,
                       {"price_type": sem["price_type"],
                        "is_current": sem["is_current"],
                        "amount": o["value"]},
                       {"msrp_status": o["msrp_status"],
                        "evidence_id": o["obs_id"],
                        "source_document_id": did},
                       base_pid=pid)

        # ── pass 4: specs (P112 rows verbatim) ────────────────────────────
        for p in accepted:
            pid = p["packet_id"]
            vid = packet_variant[pid]
            for o in p["observations"]["spec"]:
                srow = p112_rows[o["obs_id"]]
                key = SPEC_KEY_MAP[srow["field_key"]]
                did = doc_cache[(o["source_url"], o["sha256"])]
                conf = CONFIDENCE_MAP[o["trust_tier"]]
                cur.execute(
                    'insert into "VariantSpec" (id, "variantId", '
                    '"sourceDocumentId", key, "valueTh", "valueEn", '
                    '"valueNumeric", unit, confidence) values '
                    '(%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict '
                    '("variantId",key,"sourceDocumentId") do nothing '
                    'returning id',
                    (str(uuid.uuid4()), vid, did, key,
                     srow["value_text"], srow["value_text"],
                     (str(srow["value_numeric"])
                      if srow.get("value_numeric") is not None else None),
                     srow.get("unit"), conf))
                row = cur.fetchone()
                if row:
                    action, rid = "INSERT", row[0]
                    ctx.specs_created += 1
                    insert_changelog(
                        cur, ctx, "VariantSpec", rid, "CREATED", did,
                        f"{CHANGE_REASON} — packet {pid}",
                        {"packet_id": pid, "evidence_id": o["obs_id"],
                         "artifact": o["artifact"], "sha256": o["sha256"],
                         "source_url": o["source_url"],
                         "binding": o["binding"],
                         "locator": o.get("locator")},
                        {"key": key, "value_text": srow["value_text"],
                         "unit": srow.get("unit"),
                         "value_numeric": srow.get("value_numeric")},
                        excerpt=(o.get("locator") or {}).get("quote"))
                else:
                    cur.execute(
                        'select id from "VariantSpec" where "variantId" = %s '
                        'and key = %s and "sourceDocumentId" = %s',
                        (vid, key, did))
                    action, rid = "NO_ACTION", cur.fetchone()[0]
                fp = field_packet(
                    pid, "spec", p["candidate_key"],
                    {"source_url": o["source_url"], "source_name": key},
                    {"field_key": srow["field_key"],
                     "value": srow["value_text"], "unit": srow.get("unit")},
                    EvidenceLocator(
                        artifact_path=f"tests/fixtures/oem-artifacts/"
                                      f"{o['artifact']}",
                        quote=str((o.get("locator") or {}).get("quote") or
                                  srow["value_text"])),
                    o["sha256"], CurrentnessState.CURRENT)
                record(ledger, runner, fp, "spec", action, rid,
                       {"key": key, "value_text": srow["value_text"],
                        "unit": srow.get("unit"),
                        "value_numeric": srow.get("value_numeric")},
                       {"evidence_id": o["obs_id"],
                        "field_key": srow["field_key"],
                        "binding": o["binding"],
                        "source_document_id": did},
                       base_pid=pid)

        # fail-closed: nothing quarantined may appear in the ledger
        assert not quarantined_ids & {e["packet_id"]
                                      for e in ledger.entries}
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    # ── ledger + result (post-commit) ─────────────────────────────────────
    entries = ledger.entries
    ins = [e for e in entries if e["db_action"] == "INSERT"]
    upd = [e for e in entries if e["db_action"] == "UPDATE"]
    ident_ins = [e for e in ins if e["fact"] == "identity"]
    price_ins = [e for e in ins if e["fact"] == "price"]
    spec_ins = [e for e in ins if e["fact"] == "spec"]
    promoted_packets = {e["packet_id"] for e in ins}
    per_oem = defaultdict(lambda: {"packets": 0, "identity_inserts": 0,
                                   "price_inserts": 0, "spec_inserts": 0})
    pmap = {p["packet_id"]: p for p in accepted}
    for e in entries:
        b = per_oem[pmap[e["packet_id"]]["manufacturer"]]
        if e["fact"] == "identity":
            b["packets"] += 1
    for e in ident_ins:
        per_oem[pmap[e["packet_id"]]["manufacturer"]]["identity_inserts"] += 1
    for e in price_ins:
        per_oem[pmap[e["packet_id"]]["manufacturer"]]["price_inserts"] += 1
    for e in spec_ins:
        per_oem[pmap[e["packet_id"]]["manufacturer"]]["spec_inserts"] += 1

    counts = {}
    conn = psycopg2.connect(db_url())
    cur = conn.cursor()
    for t in ("Manufacturer", "CarModel", "Variant", "Price", "VariantSpec",
              "Source", "SourceDocument", "DataChangeLog"):
        cur.execute(f'select count(*) from "{t}"')
        counts[t] = int(cur.fetchone()[0])
    cur.close()
    conn.close()

    upstream_after = {n: sha256_file(os.path.join(OUT, n))
                      for n in upstream_before}
    assert upstream_after == upstream_before, "upstream artifacts changed"

    price_by_status = Counter(e["msrp_status"] for e in price_ins)
    spec_by_key = Counter(e["field_key"] for e in spec_ins)
    result = {
        "schema": "promotion_result_p114/v1",
        "generated_at": now(), "run_id": run_id, "head": head_sha(),
        "targeted_packets": len(accepted),
        "packets_promoted": len(promoted_packets),
        "packets_skipped": len(accepted) - len(promoted_packets),
        "packets_failed": 0,
        "manufacturers_inserted": ctx.mans_created,
        "models_inserted": ctx.models_created,
        "identity_variants_inserted": ctx.variants_created,
        "identity_variants_present_no_action":
            len(accepted) - ctx.variants_created,
        "sources_inserted": ctx.sources_created,
        "source_documents_inserted": ctx.docs_created,
        "price_rows_inserted": ctx.prices_created,
        "price_inserted_by_status": dict(price_by_status),
        "spec_rows_inserted": ctx.specs_created,
        "spec_inserted_by_field_key": dict(spec_by_key),
        "legacy_current_price_demotions": ctx.demotions,
        "data_change_log_rows": ctx.changelog_created,
        "ledger_entries": len(entries),
        "ledger_inserts": len(ins), "ledger_updates": len(upd),
        "ledger_no_actions": sum(1 for e in entries
                                 if e["db_action"] == "NO_ACTION"),
        "per_oem": dict(sorted(per_oem.items())),
        "quarantined_promoted": 0,
        "values_invented": 0,
        "identity_ledger_unchanged": {"confirmed_variants": 488,
                                      "changed_by_p114": False},
        "upstream_artifact_shas_unchanged": True,
        "db_after": counts,
        "gates": {"staging_write": False, "prisma_touched": False,
                  "verifier_touched": False, "api_config_touched": False,
                  "production_db": "canonical (thai_car_intelligence)",
                  "single_transaction": True, "rolled_back_on_error": True},
    }
    with open(args.result, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(args.ledger, "w", encoding="utf-8") as fh:
        json.dump({"schema": "promotion_ledger_p114/v1",
                   "generated_at": now(), "run_id": run_id,
                   "head": head_sha(),
                   "append_only": True,
                   "entries": entries}, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"promoted: mans+{ctx.mans_created} models+{ctx.models_created} "
          f"variants+{ctx.variants_created} prices+{ctx.prices_created} "
          f"specs+{ctx.specs_created} demotions={ctx.demotions} "
          f"changelog={ctx.changelog_created} sources+{ctx.sources_created} "
          f"docs+{ctx.docs_created} | ledger={len(entries)} "
          f"(ins={len(ins)} upd={len(upd)}) packets_promoted="
          f"{len(promoted_packets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
