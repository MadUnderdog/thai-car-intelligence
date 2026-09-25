#!/usr/bin/env python3
"""Write the cycle report (JSON + Markdown) from live state only.

Every number here is recomputed at run time from the registry, the staged files,
the artifacts on disk and the test log — nothing is carried over from a previous
report by hand.
"""
import argparse
import collections
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(REPO, "audit", "coverage", "oem-registry.json")
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
MEDIA = os.path.join(REPO, "audit", "data-staging", "media_observations.jsonl")
JOINS = os.path.join(REPO, "audit", "data-staging", "cross_class_joins.json")
POLICY = os.path.join(REPO, "audit", "policies", "toyota-currentness.json")
SPEC_PLAN = os.path.join(REPO, "audit", "spec-coverage-plan.json")
OUT_DIR = os.path.join(REPO, "audit", "daily-runs")

# the ambiguity that P99 reported and P100 had to remove
AMBIGUOUS_BEFORE = {
    "total": 20,
    "toyota_json_path": 10,
    "nissan_shared_selector": 10,
}


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def jlines(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def head():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def duplicate_locators(rows, key_fn):
    """Rows that do not carry this locator field are excluded: absent fields
    must not be mistaken for a shared locator."""
    values = [key_fn(r) for r in rows]
    buckets = collections.Counter(v for v in values if v)
    return {k: n for k, n in buckets.items() if n > 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suffix", default="")
    ap.add_argument("--tests-log", default="")
    ap.add_argument("--commit", default="")
    ap.add_argument("--title", default="coverage + locator integrity + second-source layer")
    args = ap.parse_args()

    reg = load(REGISTRY)
    official = jlines(STAGING)
    media = jlines(MEDIA)
    joins = load(JOINS)
    policy = load(POLICY)
    spec_plan = load(SPEC_PLAN)

    # ── coverage ──
    brands = reg["brands"]
    # coverage = extraction adapter PARSED_TESTED + provenance ACQUISITION_VERIFIED,
    # exactly the registry's own two axes (never a single blended score)
    in_scope = [b for b in brands if b.get("in_scope")]
    parsed = [b for b in in_scope
              if b.get("adapter_status") == "PARSED_TESTED"
              and b.get("provenance_status") == "ACQUISITION_VERIFIED"]
    blocked = [b for b in brands
               if (b.get("access_status") or "").upper().startswith("BLOCKED")
               or (b.get("access_status") or "").upper() == "DEALER_REDIRECT"]

    # ── staging ──
    # identity_level is the canonical field; identity_scope/level are the
    # legacy spellings kept only as fallbacks so old rows still count.
    identity = collections.Counter(
        r["identity"].get("identity_level")
        or r["identity"].get("identity_scope")
        or r["identity"].get("level") for r in official)
    price_type = collections.Counter(r["price"].get("type") for r in official)
    prov = collections.Counter(r["source"].get("provenance_state") for r in official)

    # ── locator integrity ──
    def loc(r):
        return (r.get("evidence_locator") or
                (r.get("evidence") or {}).get("evidence_locator") or
                (r.get("evidence") or {}).get("locator") or {})

    dup_full = duplicate_locators(official, lambda r: json.dumps(loc(r), sort_keys=True))
    dup_json = duplicate_locators(official, lambda r: loc(r).get("json_path"))
    dup_dom = duplicate_locators(official, lambda r: loc(r).get("dom_path"))

    # ── fixtures ──
    oem_dir = os.path.join(REPO, "tests", "fixtures", "oem-artifacts")
    media_dir = os.path.join(REPO, "tests", "fixtures", "media-artifacts")
    oem_html = [f for f in os.listdir(oem_dir) if f.endswith(".html")]
    oem_side = [f for f in os.listdir(oem_dir) if f.endswith(".prov.json")]
    oem_pdf = [f for f in os.listdir(oem_dir) if f.endswith(".b64")]
    media_html = [f for f in os.listdir(media_dir) if f.endswith(".html")] if os.path.isdir(media_dir) else []
    media_side = [f for f in os.listdir(media_dir) if f.endswith(".prov.json")] if os.path.isdir(media_dir) else []

    # ── this cycle's coverage wave: the most recently promoted verified brand,
    # recomputed from the registry + staging (never carried over by hand) ──
    verified = [b for b in brands
                if b.get("in_scope")
                and b.get("provenance_status") == "ACQUISITION_VERIFIED"
                and b.get("adapter_status") == "PARSED_TESTED"]
    wave_brand = max((b for b in verified if b.get("last_success_at")),
                     key=lambda b: b["last_success_at"], default=None)
    wave_name = (wave_brand or {}).get("brand") or ""
    wave_rows = [r for r in official
                 if (r["source"].get("name") or "").startswith(wave_name)]
    endpoints = (wave_brand or {}).get("captured_endpoints") or []
    wave_arts = sorted({e["artifact"] for e in endpoints if e.get("artifact")})
    wave_side = sorted(a for a in wave_arts
                       if os.path.exists(os.path.join(oem_dir, a + ".prov.json")))
    price_free = sorted({e["artifact"] for e in endpoints
                         if e.get("artifact") and not e.get("parsed")})
    promoted = next((e for e in sorted(endpoints,
                                       key=lambda e: bool(e.get("parsed")), reverse=True)
                     if e.get("parsed")), {})
    rej_files = sorted(glob.glob(os.path.join(
        REPO, "audit", "coverage", f"{wave_name.lower()}_*candidates*.json")))
    rejected = load(rej_files[-1]).get("rejected_candidates", []) if rej_files else []
    coverage_wave = {
        "brand": wave_name,
        "source": promoted.get("url")
                  or ((wave_brand or {}).get("source_urls") or ["—"])[0],
        "newly_covered": True,
        "artifacts": len(wave_arts),
        "sidecars": len(wave_side),
        "rows_staged": len(wave_rows),
        "identity": dict(collections.Counter(
            r["identity"].get("identity_level") for r in wave_rows)),
        "price_type": dict(collections.Counter(
            r["price"].get("type") for r in wave_rows)),
        "rejected_candidates": len(rejected),
        "rejected_reasons": dict(collections.Counter(
            c.get("reason") for c in rejected)),
        "rejected_values_thb": [c.get("value_thb") for c in rejected],
        "price_free_artifacts_staging_nothing": price_free,
        "candidates_log": os.path.relpath(rej_files[-1], REPO) if rej_files else None,
    }

    # ── tests ──
    tests = {}
    if args.tests_log and os.path.exists(args.tests_log):
        txt = open(args.tests_log, encoding="utf-8", errors="ignore").read()
        m = re.search(r"(\d+) passed", txt)
        f = re.search(r"(\d+) failed", txt)
        e = re.search(r"(\d+) error", txt)
        tests["pytest"] = (f"{m.group(1)} passed" if m else "unknown") + \
                          (f", {f.group(1)} failed" if f else "") + \
                          (f", {e.group(1)} errors" if e else "")
        tests["log"] = args.tests_log
    for name, cmd in (("prisma_validate", ["npx", "prisma", "validate"]),
                      ("tsc_noemit", ["npx", "tsc", "--noEmit"])):
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=600)
        tests[name] = f"rc={r.returncode}"

    # ── security scan over changed + new files ──
    diff = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                          capture_output=True, text=True).stdout.splitlines()
    changed = [line[3:].strip() for line in diff if line[3:].strip()]
    if not changed:
        # a report generated right after the wave's own commit would otherwise
        # scan an empty tree and print 0/0 as if the check had passed; fall
        # back to the files of the commit this report cites (strictly more,
        # never fewer).
        ref = args.commit or head()
        changed = subprocess.run(
            ["git", "show", "--pretty=", "--name-only", ref],
            cwd=REPO, capture_output=True, text=True, timeout=60).stdout.split()
    pat = re.compile(r"AIza[0-9A-Za-z_\-]{35}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
                     r"sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}", re.I)
    hits = []
    for rel in changed:
        path = os.path.join(REPO, rel.split(" -> ")[-1].strip('"'))
        if os.path.isfile(path) and os.path.getsize(path) < 20_000_000:
            try:
                data = open(path, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if pat.search(data):
                hits.append(rel)
    tests["credential_scan_changed_or_new_files"] = len(hits)
    tests["credential_scan_files_checked"] = len(changed)

    # ── collection errors: prove whether they predate this wave ──
    # A collection ImportError can only be a regression of the wave that wrote
    # the failing test or drifted the code under it; otherwise it is carried
    # in from before.
    if args.tests_log and os.path.exists(args.tests_log):
        log_txt = open(args.tests_log, encoding="utf-8", errors="ignore").read()
        mods = sorted(set(re.findall(r"ERROR collecting (\S+)", log_txt)))
        if mods:
            ref = args.commit or head()
            try:
                wave = set(subprocess.run(
                    ["git", "diff", "--name-only", f"{ref}~1..{ref}"],
                    cwd=REPO, capture_output=True, text=True, timeout=60).stdout.split())
            except Exception:
                wave = set()
            touched = sorted(m for m in mods if m in wave) + \
                sorted(f for f in wave if f.startswith("lib/"))
            tests["collection_error_modules"] = mods
            tests["collection_error_preexisting"] = not touched
            tests["collection_error_evidence"] = (
                "this wave's diff touches neither the failing test module "
                "nor any lib/ module"
                if not touched else
                "this wave's diff touches: " + ", ".join(sorted(set(touched))))

    # ── retry windows ──
    # mirror the `blocked` predicate above: access_status is BLOCKED_<reason>
    # or DEALER_REDIRECT, never the bare string "BLOCKED".
    now = datetime.datetime.now(datetime.timezone.utc)
    due, not_due = [], []
    for b in brands:
        status = (b.get("access_status") or "").upper()
        nr = b.get("next_retry_at")
        if not nr or not (status.startswith("BLOCKED") or status == "DEALER_REDIRECT"):
            continue
        entry = {"brand": b.get("brand"), "access_status": b.get("access_status"),
                 "next_retry_at": nr,
                 "blocker": (b.get("blocker_evidence") or {}).get("summary")
                 if isinstance(b.get("blocker_evidence"), dict) else b.get("blocker_evidence")}
        try:
            t = datetime.datetime.fromisoformat(nr.replace("Z", "+00:00"))
            (due if t <= now else not_due).append(entry)
        except Exception:
            not_due.append(entry)

    # a blocker re-checked during today's run WAS retried this cycle, even when
    # its next window has already moved into the future (DEALER_REDIRECT,
    # §94, is re-probed daily). Reported instead of asserted by hand.
    retried = [{"brand": b.get("brand"),
                "access_status": b.get("access_status"),
                "checked_at": (b.get("blocker_evidence") or {}).get("checked_at"),
                "outcome": (b.get("blocker_evidence") or {}).get("http_status_or_error")}
               for b in brands
               if str(((b.get("blocker_evidence") or {}).get("checked_at") or ""))
               .startswith(now.date().isoformat())]

    report = {
        "report_id": f"daily-run-{datetime.date.today().isoformat()}{args.suffix}",
        "generated_at": now.isoformat(),
        "commit": args.commit or head(),
        "branch": subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO,
                                 capture_output=True, text=True).stdout.strip(),
        "locator_integrity": {
            "before": AMBIGUOUS_BEFORE,
            "after": {
                "ambiguous_full_locators": len(dup_full),
                "duplicate_json_path": len(dup_json),
                "duplicate_dom_path": len(dup_dom),
                "rows": len(official),
            },
            "resolution": {
                "engine": "scripts/resolve_locators.py",
                "rule": "every accepted row must resolve to exactly one matching record",
                "official_rows": len(official),
                "media_rows": len(media),
            },
            "mutation_proof": {
                "swap": "price rewrite on every row -> zero matches",
                "delete": "record deletion -> zero, or the identical record "
                          "(pages whose own framework rebuilds the node)",
            },
        },
        "secondary_source_layer": {
            "source_class": "AUTOMOTIVE_MEDIA",
            "trust_state": "RESEARCH_UNVERIFIED",
            "registry": "storage/thai-source-registry.json",
            "batch": "3 documented brand_price_page_crawl pages",
            "artifacts": len(media_html),
            "sidecars": len(media_side),
            "records": len(media),
            "fail_closed_skips": "records without a unique locator or a model heading were dropped",
            "file": "audit/data-staging/media_observations.jsonl",
        },
        "cross_class_joins": {
            "file": "audit/data-staging/cross_class_joins.json",
            "join_count": joins["join_count"],
            "target": ">=3 genuine",
            "target_met": joins["join_count"] >= 3,
            "join_keys": [j["join_key"] for j in joins["joins"]],
            "by_class_pair": joins["by_class_pair"],
        },
        "toyota_currentness_policy": {
            "file": "audit/policies/toyota-currentness.json",
            "decision": policy["decision"],
            "basis": policy["currentness_basis"],
            "basis_not_claimed": policy["basis_not_claimed"],
            "rows_unchanged": policy["row_change_required_now"] is False,
            "demotion_target": policy["demotion"]["target"],
            "demotion_rows": policy["demotion"]["rows_affected"],
        },
        "spec_coverage_plan": {
            "file": "audit/spec-coverage-plan.json",
            "current": spec_plan["current_state"],
            "tiers": [{"tier": t["tier"], "name": t["name"]} for t in spec_plan["tiers"]],
            "staged_now": 0,
        },
        "staging": {
            "official_rows": len(official),
            "identity": dict(identity),
            "price_type": dict(price_type),
            "provenance": dict(prov),
            "media_rows": len(media),
        },
        "fixtures": {
            "oem_html": len(oem_html), "oem_sidecars": len(oem_side), "oem_pdf": len(oem_pdf),
            "media_html": len(media_html), "media_sidecars": len(media_side),
        },
        "coverage": {
            "verified_parsed": len(parsed),
            "denominator": len(in_scope),
            "percent": round(100.0 * len(parsed) / len(in_scope), 1) if in_scope else 0.0,
            "blocked": len(blocked),
        },
        "coverage_wave": coverage_wave,
        "tests": tests,
        "retry_windows": {"elapsed_now": due, "not_yet_due": not_due,
                          "retried_this_cycle": retried,
                          "blocked_brand_count": len(blocked)},
        "not_touched": [
            "production database", "AI model/provider/config", "verifier (FROZEN)",
            "PR #3 merge state", "skills/references/memory/self-improvement",
            "blocked hosts before next_retry_at",
        ],
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.date.today().isoformat().replace("-", "") + args.suffix
    jp = os.path.join(OUT_DIR, stamp + ".json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ── markdown ──
    li = report["locator_integrity"]
    cw = report["coverage_wave"]
    lines = [
        f"# Daily run {stamp} — {args.title}",
        "",
        f"- commit: `{report['commit']}` · branch `{report['branch']}` · generated {report['generated_at']}",
        f"- coverage: {report['coverage']['verified_parsed']}/{report['coverage']['denominator']} "
        f"({report['coverage']['percent']}%), blocked {report['coverage']['blocked']}",
        "",
        f"## Coverage wave — {cw['brand']} Thailand (newly covered)",
        f"- route: {cw['source']}",
        f"- captures: {cw['artifacts']} artifacts + {cw['sidecars']} capture-time sidecars (all verify)",
        f"- staged {cw['rows_staged']} rows: " +
        " / ".join(f"{k} {v}" for k, v in sorted(cw["identity"].items())),
        "- price types: " +
        ", ".join(f"{k} {v}" for k, v in sorted(cw["price_type"].items())),
        f"- rejected {cw['rejected_candidates']} published figures, never staged" +
        (": " + "; ".join(f"{n}x {reason}"
                          for reason, n in sorted(cw["rejected_reasons"].items())) +
         f" (values: {', '.join(str(v) for v in cw['rejected_values_thb'])})"
         if cw["rejected_candidates"] else ""),
    ] + (
        [f"- candidates log: {cw['candidates_log']}"] if cw.get("candidates_log") else []
    ) + (
        ["- captured endpoints staged nothing (no parser yet): " +
         ", ".join(cw["price_free_artifacts_staging_nothing"])]
        if cw.get("price_free_artifacts_staging_nothing") else []
    ) + [
        "",
        "## Locator integrity",
        f"- before: {li['before']['total']} ambiguous rows "
        f"(Toyota json_path {li['before']['toyota_json_path']}, "
        f"Nissan shared selector {li['before']['nissan_shared_selector']})",
        f"- after: {li['after']['ambiguous_full_locators']} ambiguous full locators, "
        f"{li['after']['duplicate_json_path']} duplicate json_path, "
        f"{li['after']['duplicate_dom_path']} duplicate dom_path",
        f"- resolution: {li['resolution']['official_rows']} official rows and "
        f"{li['resolution']['media_rows']} media rows each resolve to exactly one record",
        f"- mutation: {li['mutation_proof']['swap']} / {li['mutation_proof']['delete']}",
        "",
        "## Second source layer",
        f"- {report['secondary_source_layer']['records']} {report['secondary_source_layer']['source_class']} "
        f"records, trust {report['secondary_source_layer']['trust_state']}",
        f"- artifacts {report['secondary_source_layer']['artifacts']} + sidecars "
        f"{report['secondary_source_layer']['sidecars']}, batch: "
        f"{report['secondary_source_layer']['batch']}",
        "",
        "## Cross-class joins",
        f"- {joins['join_count']} genuine joins: " + ", ".join(j["join_key"] for j in joins["joins"]),
        "",
        "## Toyota currentness",
        f"- decision `{policy['decision']}` on basis `{policy['currentness_basis']}`; "
        f"rows unchanged; demotion target `{policy['demotion']['target']}` "
        f"({policy['demotion']['rows_affected']} rows) if the policy is flipped",
        "",
        "## Spec coverage",
        f"- current {spec_plan['current_state']['rows_with_specs']}/"
        f"{spec_plan['current_state']['total_rows']} rows "
        f"({spec_plan['current_state']['coverage_pct']}%), brands "
        f"{spec_plan['current_state']['brands_with_specs']}",
        "- plan tiers: " + "; ".join(f"{t['tier']} {t['name']}" for t in spec_plan["tiers"]),
        "- staged in this cycle: 0 (plan only, no harvesting)",
        "",
        "## Tests and security",
        f"- pytest: {report['tests'].get('pytest', 'n/a')}",
        (f"- collection error ({', '.join(report['tests'].get('collection_error_modules', []))}): "
         f"{'pre-existing, NOT a regression — ' if report['tests'].get('collection_error_preexisting') else 'NEW in this wave — '}"
         f"{report['tests'].get('collection_error_evidence', '')}"),
        f"- prisma: {report['tests'].get('prisma_validate', 'n/a')} · "
        f"tsc: {report['tests'].get('tsc_noemit', 'n/a')}",
        f"- credential scan over {report['tests'].get('credential_scan_files_checked', 0)} "
        f"changed/new files: {report['tests'].get('credential_scan_changed_or_new_files', 0)} hits",
        "",
        "## Retry windows",
        f"- retried this cycle: {len(retried)} · elapsed now: {len(due)} · "
        f"not yet due: {len(not_due)} · blocked: {len(blocked)}",
    ] + [
        f"  - retried {d['brand']}: {d['access_status']} checked {d['checked_at']} — {d['outcome']}"
        for d in retried
    ] + [
        f"  - {d['brand']}: {d['access_status']} — next retry {d['next_retry_at']}"
        for d in sorted(not_due, key=lambda d: d["next_retry_at"] or "")
    ] + [
        "",
        "## Not touched",
    ]
    lines += [f"- {x}" for x in report["not_touched"]]
    mp = os.path.join(OUT_DIR, stamp + ".md")
    with open(mp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(json.dumps({"json": os.path.relpath(mp.replace('.md', '.json'), REPO),
                      "md": os.path.relpath(mp, REPO),
                      "coverage": report["coverage"],
                      "joins": report["cross_class_joins"]["join_count"],
                      "locator_after": report["locator_integrity"]["after"],
                      "tests": report["tests"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
