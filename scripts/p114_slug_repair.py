#!/usr/bin/env python3
"""P114 slug repair — fix slugs on rows CREATED by the P114 promotion only.

Defect (red-before in tests/test_p114_promotion.py):
  slugify() dropped every non-[a-z0-9] character, so the publisher-exact
  Thai identity labels the frozen ledger carries
  ('เอ็กซ์ฟอร์ส เอชอีวี', 'ไทรทัน ดับเบิ้ล แค็บ พลัส', ...) were written as
  degenerate slugs ('', '2', '-2-2', ...).

Scope (hard):
  * ONLY rows whose DataChangeLog CREATED entry has reason 'P114%'
    (i.e. rows the P114 promotion created). No historical row is touched.
  * slug-only UPDATE, values/names untouched.
  * every UPDATE gets a DataChangeLog UPDATED entry with before/after +
    reason carrying the packet id of the creating promotion entry.
  * deterministic, collision-safe (suffix loop within the parent scope).

Output: audit/coverage/p114_slug_repairs.json (append-only record of this
one bounded repair).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import importlib.util

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "lib"))

ARTIFACT = os.path.join(REPO, "audit/coverage/p114_slug_repairs.json")


def db_url() -> str:
    txt = open(os.path.join(REPO, ".env"), encoding="utf-8").read()
    m = re.search(r'^DATABASE_URL="([^"]+)"', txt, re.M)
    if not m:
        raise RuntimeError("DATABASE_URL not found in .env")
    return m.group(1).split("?")[0]


def slugify_v2(s) -> str:
    spec = importlib.util.spec_from_file_location(
        "p114_promote_for_slug_repair",
        os.path.join(REPO, "scripts/p114_promote.py"))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.slugify(s)


def main() -> int:
    import psycopg2
    conn = psycopg2.connect(db_url())
    conn.autocommit = False
    cur = conn.cursor()
    try:
        # ---- scope: rows CREATED by the P114 promotion -------------------
        cur.execute(
            '''select d."entityType", d."entityId", d.evidence->>'packet_id',
                      d."sourceDocumentId"
                 from "DataChangeLog" d
                where d."changeType" = 'CREATED' and d.reason like 'P114%' ''')
        created = cur.fetchall()
        by_type = {"CarModel": [], "Variant": []}
        meta = {}
        for etype, eid, pkt, sdid in created:
            if etype in by_type:
                by_type[etype].append(eid)
                meta[(etype, eid)] = {"packet": pkt, "sourceDocumentId": sdid}
        print(f"scope: {len(by_type['CarModel'])} models, "
              f"{len(by_type['Variant'])} variants created by P114")
        assert by_type["CarModel"], "no P114-created models found"
        assert by_type["Variant"], "no P114-created variants found"

        repairs = []

        def plan_updates(rows, parent_query, parent_key):
            """rows: (id, nameEn, slug, parent_id). Returns [(id, before,
            after, parent_id)] with in-parent collision-safe slugs."""
            taken = {}
            for (pid, slug) in parent_query:
                taken.setdefault(pid, set()).add(slug)
            out = []
            for rid, name, slug, parent in rows:
                new = slugify_v2(name)
                assert new, f"slugify produced empty slug for {name!r}"
                base = new
                n = 2
                while new in taken.get(parent, set()) and new != slug:
                    new = f"{base}-{n}"
                    n += 1
                taken.setdefault(parent, set()).add(new)
                if new != slug:
                    out.append((rid, slug, new, parent, name))
            return out

        # ---- CarModel updates -------------------------------------------
        placeholders = ",".join(["%s"] * len(by_type["CarModel"]))
        cur.execute(
            f'''select c.id, c."nameEn", c.slug, c."manufacturerId"
                  from "CarModel" c where c.id in ({placeholders})''',
            by_type["CarModel"])
        model_rows = cur.fetchall()
        cur.execute('select "manufacturerId", slug from "CarModel"')
        model_taken = cur.fetchall()
        model_updates = plan_updates(model_rows, model_taken, 0)

        # ---- Variant updates --------------------------------------------
        placeholders = ",".join(["%s"] * len(by_type["Variant"]))
        cur.execute(
            f'''select v.id, v."nameEn", v.slug, v."modelId"
                  from "Variant" v where v.id in ({placeholders})''',
            by_type["Variant"])
        variant_rows = cur.fetchall()
        cur.execute('select "modelId", slug from "Variant"')
        variant_taken = cur.fetchall()
        variant_updates = plan_updates(variant_rows, variant_taken, 0)

        # ---- apply in ONE transaction -----------------------------------
        for etype, updates in (("CarModel", model_updates),
                               ("Variant", variant_updates)):
            for rid, before, after, parent, name in updates:
                m = meta[(etype, rid)]
                cur.execute(
                    f'update "{etype}" set slug = %s where id = %s',
                    (after, rid))
                assert cur.rowcount == 1, rid
                cur.execute(
                    '''insert into "DataChangeLog"
                       (id, "sourceDocumentId", "entityType", "entityId",
                        "fieldName", "changeType", "beforeValue", "afterValue",
                        reason, confidence, "evidenceExcerpt", evidence,
                        proposed, applied, "reviewStatus", "createdAt")
                       values (%s,%s,%s,%s,%s,'UPDATED',%s,%s,%s,%s,%s,%s,
                               false,true,'APPROVED',now())''',
                    (str(__import__("uuid").uuid4()), m["sourceDocumentId"],
                     etype, rid, "slug",
                     json.dumps({"slug": before}),
                     json.dumps({"slug": after}),
                     f"P114 slug repair — Thai-script identity preserved as "
                     f"Unicode slug (no transliteration source in repo) — "
                     f"packet {m['packet']} (row created by P114)",
                     "0.9000", None,
                     json.dumps({"packet_id": m["packet"],
                                 "repair": "slugify_v2_unicode_thai",
                                 "name": name},
                                ensure_ascii=False)))
                repairs.append({
                    "entity_type": etype,
                    "entity_id": rid,
                    "packet_id": m["packet"],
                    "name": name,
                    "before": before,
                    "after": after,
                    "action": "UPDATE",
                })

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    artifact = {
        "schema": "p114_slug_repairs/v1",
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "scope": "rows created by P114 promotion only "
                 "(DataChangeLog CREATED reason 'P114%')",
        "count": len(repairs),
        "models_updated": sum(1 for r in repairs
                              if r["entity_type"] == "CarModel"),
        "variants_updated": sum(1 for r in repairs
                                if r["entity_type"] == "Variant"),
        "repairs": sorted(repairs, key=lambda r: (r["entity_type"],
                                                  r["entity_id"])),
    }
    with open(ARTIFACT, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(json.dumps({k: artifact[k] for k in
                      ("count", "models_updated", "variants_updated")},
                     ensure_ascii=False))
    print("SLUG_REPAIR_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
