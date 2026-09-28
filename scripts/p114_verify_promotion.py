#!/usr/bin/env python3
"""P114 verifier — INDEPENDENT post-write verification (G7: verifier code
path is separate from the producer; this module imports nothing from it).

Recomputes every promotion claim from the database + committed artifacts:
  * DB deltas vs the preflight baseline == ledger INSERT counts, table by table
  * every registered SourceDocument contentHash is a cited P113 artifact hash
  * zero values invented: each promoted Price/VariantSpec row is re-derived
    from P111/P112 rows via the DataChangeLog evidence link
  * zero rows from quarantined packets (DataChangeLog packet ids subset)
  * price semantics: 264 MSRP isCurrent, 29 LIST_PRICE not-current, MG row
    MSRP not-current; no touched variant keeps two current prices
  * identity ledger exactly 488; upstream P111/P112/P113 bytes unchanged

Writes audit/coverage/p114_promotion_verification.json and prints
VERIFY_PASS / VERIFY_FAIL (rc 0 / 1).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "audit/coverage")


def load(name):
    return json.load(open(os.path.join(OUT, name), encoding="utf-8"))


def sha256_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def db_url():
    txt = open(os.path.join(REPO, ".env"), encoding="utf-8").read()
    m = re.search(r'^DATABASE_URL="([^"]+)"', txt, re.M)
    return m.group(1).split("?")[0]


def sql(query):
    r = subprocess.run(["psql", db_url(), "-tAc", query],
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:300])
    return [l for l in r.stdout.splitlines() if l]


def main() -> int:
    led = load("p114_promotion_ledger.json")
    res = load("p114_promotion_result.json")
    pf = load("p114_promotion_preflight.json")
    p113 = load("p113_evidence_packets.json")
    p111_rows = {(r["manufacturer"], r["model"], r["variant"]): r
                 for r in load("p111_price_evidence.json")["rows"]}
    p112_rows = {r["evidence_id"]: r
                 for r in load("p112_spec_evidence.json")["rows"]}
    accepted = {p["packet_id"] for p in p113["packets"]
                if p["status"] == "ACCEPTED"}
    entries = led["entries"]
    ins = [e for e in entries if e["db_action"] == "INSERT"]
    checks = {}
    failures = []

    def check(name, ok, detail=""):
        checks[name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            failures.append(name)

    # 1. DB deltas == ledger INSERT counts
    base = pf["db_baseline"]
    after = res["db_after"]
    deltas = {
        "Manufacturer": res["manufacturers_inserted"],
        "CarModel": res["models_inserted"],
        "Variant": res["identity_variants_inserted"],
        "Price": res["price_rows_inserted"],
        "VariantSpec": res["spec_rows_inserted"],
        "DataChangeLog": res["data_change_log_rows"],
    }
    for table, claimed in deltas.items():
        actual = after[table] - base[table]
        # also re-read live to be sure the stored after-count is real
        live = int(sql('select count(*) from "%s"' % table)[0])
        check(f"delta_{table}", actual == claimed == live - base[table],
              f"baseline={base[table]} after={after[table]} "
              f"claimed={claimed} live={live}")

    # 2. every registered SourceDocument hash is a cited artifact hash
    cited = set()
    for p in p113["packets"]:
        if p["status"] != "ACCEPTED":
            continue
        for g in ("identity", "price", "spec"):
            for o in p["observations"][g]:
                cited.add(o["sha256"])
    in_list = ",".join("'%s'" % s for s in cited)
    docs = sql('select "contentHash" from "SourceDocument" where '
               '"contentHash" in (%s)' % in_list)
    check("source_documents_registered", set(docs) == cited,
          f"registered={len(set(docs))} cited={len(cited)}")
    # no promotion doc outside the cited set was created by this wave
    extra = sql("select count(*) from \"SourceDocument\" where "
                "\"localPath\" like 'tests/fixtures/oem-artifacts/%' and "
                "\"contentHash\" not in (%s) and \"createdAt\" >= "
                "timestamp '%s'" % (in_list,
                                    pf["generated_at"][:19].replace("T", " ")))
    check("no_uncited_documents", int(extra[0]) == 0, f"extra={extra[0]}")

    # 3. zero invented values: re-derive promoted rows from P111/P112
    #    via the DataChangeLog evidence links
    invented = 0
    rows = sql(
        "select d.\"entityType\", d.evidence->>'evidence_id', "
        "d.evidence->>'packet_id', d.\"afterValue\"->>'value_text', "
        "d.\"afterValue\"->>'unit', d.\"afterValue\"->>'amount' "
        "from \"DataChangeLog\" d "
        "where d.reason like 'P114%' and d.\"changeType\" = 'CREATED'")
    spec_checked = price_checked = 0
    for etype, evidence_id, packet_id, value_text, unit, amount in (
            r.split("|") for r in rows):
        if etype == "VariantSpec":
            src = p112_rows.get(evidence_id)
            if src is None or value_text != str(src["value_text"]) \
                    or (unit or None) != (src.get("unit") or None):
                invented += 1
            spec_checked += 1
        elif etype == "Price":
            pk = next((p for p in p113["packets"]
                       if p["packet_id"] == packet_id), None)
            if pk is None:
                invented += 1
                continue
            prow = p111_rows.get((pk["manufacturer"], pk["model"],
                                  pk["variant"]))
            if prow is None or str(amount) != str(prow["price_thb"]):
                invented += 1
            price_checked += 1
    check("values_verbatim_from_p111_p112", invented == 0,
          f"spec_rows={spec_checked} price_rows={price_checked} "
          f"invented={invented}")

    # 4. no quarantined packet referenced anywhere
    q_ids = {p["packet_id"] for p in p113["packets"]
             if p["status"] != "ACCEPTED"}
    reasons = sql("select reason from \"DataChangeLog\" where reason like "
                  "'P114%'")
    seen_packets = set()
    for r in reasons:
        m = re.search(r"PKT-\d{4}", r)
        if m:
            seen_packets.add(m.group(0))
    check("quarantined_rows_promoted", not (seen_packets & q_ids),
          f"packet_ids_in_changelog={len(seen_packets)}")

    # 5. price semantics in the DB
    price_rows = sql(
        "select price_type::text, \"isCurrent\", count(*) from \"Price\" "
        "where \"sourceDocumentId\" in (select id from \"SourceDocument\" "
        "where \"contentHash\" in (%s)) group by 1,2" % in_list)
    got = {}
    for l in price_rows:
        t, cur, n = l.split("|")
        got[(t, cur)] = int(n)
    expect = {("MSRP", "t"): res["price_inserted_by_status"].get(
        "EXACT_CURRENT_MSRP_VERIFIED", 0),
        ("MSRP", "f"): res["price_inserted_by_status"].get(
            "EXACT_BINDING_NOT_VERIFIED_CURRENT", 0),
        ("LIST_PRICE", "f"): res["price_inserted_by_status"].get(
            "MSRP_STARTING_NOT_EXACT", 0)}
    check("price_semantics_db", got == expect, f"got={got}")
    mg = sql(
        "select count(*) from \"Price\" where \"sourceDocumentId\" in "
        "(select id from \"SourceDocument\" where \"contentHash\" in (%s)) "
        "and price_type::text = 'MSRP' and \"isCurrent\" = false" % in_list)
    check("mg_not_current_in_db",
          int(mg[0]) == res["price_inserted_by_status"].get(
              "EXACT_BINDING_NOT_VERIFIED_CURRENT", 0), f"rows={mg[0]}")

    # 6. touched variants have at most one current price
    dup = sql(
        "select count(*) from (select \"variantId\" from \"Price\" where "
        "\"isCurrent\" = true and \"variantId\" in "
        "(select distinct \"variantId\" from \"Price\" where "
        "\"sourceDocumentId\" in (select id from \"SourceDocument\" where "
        "\"contentHash\" in (%s))) group by 1 having count(*) > 1) x"
        % in_list)
    check("single_current_price_per_touched_variant", int(dup[0]) == 0,
          f"dup_variants={dup[0]}")

    # 7. upstream artifacts + identity ledger unchanged
    ok_up = True
    for name, sha in pf["inputs"]["upstream_artifact_shas"].items():
        if sha256_file(os.path.join(OUT, name)) != sha:
            ok_up = False
    check("upstream_artifacts_byte_identical", ok_up)
    u = load("identity_universe_p108.json")
    n_acc = sum(1 for r in u["universe"]["records"]
                if r["status"] == "CONFIRMED_VARIANT")
    check("identity_ledger_488", n_acc == 488, f"count={n_acc}")

    # 8. ledger covers exactly the accepted set, INSERTs carry row ids
    check("ledger_only_accepted_packets",
          all(e["packet_id"] in accepted for e in entries))
    check("ledger_identity_one_per_accepted",
          {e["packet_id"] for e in entries if e["fact"] == "identity"}
          == accepted)
    check("inserts_have_row_ids", all(e["db_row_id"] for e in ins))

    status = "PASS" if not failures else "FAIL"
    out = {"schema": "promotion_verification_p114/v1", "status": status,
           "checks": checks, "failures": failures,
           "quarantined_rows_promoted":
               len(seen_packets & q_ids),
           "invented_values": invented,
           "verified_at": __import__("datetime").datetime.now(
               __import__("datetime").timezone.utc).isoformat()}
    with open(os.path.join(OUT, "p114_promotion_verification.json"),
              "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(("VERIFY_PASS" if status == "PASS" else "VERIFY_FAIL"),
          f"checks={len(checks)} failures={failures}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
