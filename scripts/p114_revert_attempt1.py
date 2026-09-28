#!/usr/bin/env python3
"""P114 attempt-1 revert (bounded, count-verified).

Attempt 1 of the P114 promotion transaction COMMITTED its DB writes, then
crashed in post-commit ledger assembly (packet_id carried a fact suffix,
KeyError 'PKT-0001.identity'), so the canonical append-only ledger/result
were never written. To keep the promotion ledger truthful (INSERT actions
recorded by the run that performed them), attempt 1 is reverted EXACTLY to
the preflight baseline and the fixed producer runs once as the canonical
transaction.

What this reverts (all derived from the attempt-1 DataChangeLog, nothing
guessed):
  1. restores the 8 demoted legacy isCurrent flags (beforeValue), then
  2. deletes attempt-1 DataChangeLog rows (reason 'P114%'),
  3. VariantSpec rows created by attempt 1 (changelog entityIds),
  4. Price rows created by attempt 1 (+ any price citing our new docs),
  5. SourceDocuments whose contentHash is a P113 cited artifact hash,
  6. Sources that hold ONLY those new documents,
  7. Variant/CarModel/Manufacturer rows created by attempt 1.
Finally asserts every table count equals the committed preflight baseline.

Usage: python3 scripts/p114_revert_attempt1.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "audit/coverage")


def db_url():
    txt = open(os.path.join(REPO, ".env"), encoding="utf-8").read()
    m = re.search(r'^DATABASE_URL="([^"]+)"', txt, re.M)
    return m.group(1).split("?")[0]


def main() -> int:
    import psycopg2
    pf = json.load(open(os.path.join(OUT, "p114_promotion_preflight.json"),
                        encoding="utf-8"))
    p113 = json.load(open(os.path.join(OUT, "p113_evidence_packets.json"),
                           encoding="utf-8"))
    cited = set()
    for p in p113["packets"]:
        if p["status"] != "ACCEPTED":
            continue
        for g in ("identity", "price", "spec"):
            for o in p["observations"][g]:
                cited.add(o["sha256"])
    conn = psycopg2.connect(db_url())
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute(
            'select "entityType", "changeType", "entityId" from '
            '"DataChangeLog" where reason like %s',
            ("P114%",))
        created = {"Variant": [], "CarModel": [], "Manufacturer": [],
                   "Price": [], "VariantSpec": []}
        demoted = []
        for etype, ctype, eid in cur.fetchall():
            if etype == "Price" and ctype == "UPDATED":
                demoted.append(eid)
            elif etype in created and ctype == "CREATED":
                created[etype].append(eid)
        cur.execute(
            'select id from "SourceDocument" where "contentHash" = any(%s)',
            (list(cited),))
        our_docs = [r[0] for r in cur.fetchall()]
        cur.execute(
            'select s.id from "Source" s where exists '
            '(select 1 from "SourceDocument" d where d."sourceId" = s.id '
            'and d.id = any(%s::uuid[])) and not exists '
            '(select 1 from "SourceDocument" d2 where d2."sourceId" = s.id '
            'and not (d2.id = any(%s::uuid[])))',
            (our_docs, our_docs))
        our_sources = [r[0] for r in cur.fetchall()]
        plan = {"demote_restores": len(demoted),
                "changelog": None, "spec_rows": len(created["VariantSpec"]),
                "price_rows": len(created["Price"]),
                "source_documents": len(our_docs),
                "sources": len(our_sources),
                "variants": len(created["Variant"]),
                "models": len(created["CarModel"]),
                "manufacturers": len(created["Manufacturer"])}
        print("revert plan:", json.dumps(plan))
        assert len(created["Variant"]) == 405, plan
        assert len(created["Price"]) == 294, plan
        assert len(created["VariantSpec"]) == 1043, plan
        assert len(our_docs) == 122, plan

        # DataChangeLog references SourceDocument -> delete it before the
        # documents go (entity ids were collected above already)
        cur.execute("delete from \"DataChangeLog\" where reason like %s",
                    ("P114%",))
        plan["changelog"] = cur.rowcount
        if created["VariantSpec"]:
            cur.execute('delete from "VariantSpec" where id = any(%s::uuid[])',
                        (created["VariantSpec"],))
            assert cur.rowcount == len(created["VariantSpec"])
        if created["Price"]:
            cur.execute('delete from "Price" where id = any(%s::uuid[]) or '
                        '"sourceDocumentId" = any(%s::uuid[])',
                        (created["Price"], our_docs))
            assert cur.rowcount >= len(created["Price"])
        cur.execute('delete from "SourceDocument" where id = any(%s::uuid[])',
                    (our_docs,))
        assert cur.rowcount == len(our_docs)
        cur.execute('delete from "Source" where id = any(%s::uuid[])',
                    (our_sources,))
        assert cur.rowcount == len(our_sources)
        # restore demoted legacy current flags only after attempt-1 current
        # rows are gone (exclusion constraint would otherwise fire)
        if demoted:
            cur.execute('update "Price" set "isCurrent" = true '
                        'where id = any(%s::uuid[])', (demoted,))
            assert cur.rowcount == len(demoted)
        cur.execute('delete from "Variant" where id = any(%s::uuid[])',
                    (created["Variant"],))
        assert cur.rowcount == len(created["Variant"])
        cur.execute('delete from "CarModel" where id = any(%s::uuid[])',
                    (created["CarModel"],))
        assert cur.rowcount == len(created["CarModel"])
        cur.execute('delete from "Manufacturer" where id = any(%s::uuid[])',
                    (created["Manufacturer"],))
        assert cur.rowcount == len(created["Manufacturer"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    # verify exact baseline restore
    cur = psycopg2.connect(db_url()).cursor()
    base = pf["db_baseline"]
    ok = True
    for table, expected in base.items():
        cur.execute(f'select count(*) from "{table}"')
        got = int(cur.fetchone()[0])
        if got != expected:
            ok = False
            print(f"MISMATCH {table}: got {got} expected {expected}")
    cur.execute('select count(*) from "Price" where "isCurrent"')
    if int(cur.fetchone()[0]) != 96:
        ok = False
        print("MISMATCH isCurrent total (expected 96)")
    cur.execute('select count(*) from (select "variantId" from "Price" '
                'where "isCurrent" group by 1 having count(*) > 1) x')
    if int(cur.fetchone()[0]) != 13:
        ok = False
        print("MISMATCH preexisting dup-current variants (expected 13)")
    print("REVERT_OK" if ok else "REVERT_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
