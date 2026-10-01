"""P108 — external source-discovery batch tests.

Red-before evidence for the one concrete defect found in this batch (artifact
name collision silently overwrote a capture, so inventory sha256 did not match
the sidecar sha256): `/tmp/p108_redbefore.log` recorded
`inventory sha vs sidecar sha: 3 mismatch(es) before fix`
(`toyota_p108_index_dup.html`, `kia_p108_carnival_dup.html` ×2) and
`/tmp/p108_green.log` records `0 mismatch(es)` after unique-name allocation
plus re-acquisition of the three URLs.  This suite re-proves that invariant
against the committed artifacts.
"""
import ast
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "audit/coverage")
FIXTURES = os.path.join(REPO, "tests/fixtures/oem-artifacts")
PRIORITY = ["Toyota", "Mazda", "MG", "Nissan", "Porsche", "Honda", "Mitsubishi",
            "Subaru", "GWM", "Deepal", "MINI", "Changan", "Jaguar", "Isuzu",
            "Suzuki", "Lexus", "Kia"]
BLOCKED = {"byd", "audi", "chevrolet", "ford", "tesla", "chery", "haval", "neta",
           "peugeot", "volvo", "avance", "mercedes-benz", "smart"}


def _load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def inv():
    return _load("p108_source_inventory.json")


@pytest.fixture(scope="module")
def cap():
    return _load("p108_capture_log.json")


@pytest.fixture(scope="module")
def result():
    return _load("p108_final_result.json")


@pytest.fixture(scope="module")
def ev():
    return _load("p108_variant_evidence.json")["evidence"]


@pytest.fixture(scope="module")
def recon():
    return _load("catalog_reconciliation_p108.json")


# ── source inventory ────────────────────────────────────────────────────────
def test_inventory_covers_every_priority_brand(inv):
    seen = {e["brand"] for e in inv["entries"]}
    missing = [b for b in PRIORITY if b not in seen]
    assert missing == [], missing


def test_inventory_every_entry_has_status_and_blocker_or_artifact(inv):
    bad = [e for e in inv["entries"]
           if e.get("status") in (None, "") or
           (e.get("ok") and not e.get("artifact")) or
           (not e.get("ok") and not e.get("blocker"))]
    assert bad == [], bad[:5]


def test_inventory_discovery_is_external_not_href_rehash(inv):
    method = inv["method"].lower()
    assert "sitemap" in method and ("certificate" in method or "transparency" in method)
    assert "de-duplicated" in method


def test_inventory_deduplicates_against_earlier_waves(inv):
    known = set()
    for fn in glob.glob(os.path.join(FIXTURES, "*.prov.json")):
        if "_p108_" in fn:
            continue
        try:
            known.add(json.load(open(fn, encoding="utf-8"))["source_url"].split("#")[0])
        except Exception:
            continue

    def norm(u):
        m = re.match(r"https?://([^/?#]+)([^?#]*)", u)
        if not m:
            return None
        path = re.sub(r"^/(en|th|en_TH|th_TH)(?=/)", "", m.group(2).rstrip("/") or "/")
        return m.group(1).lower().replace("www.", ""), re.sub(r"-(en|th)$", "", path)

    known_norm = {n for n in (norm(u) for u in known) if n}
    clash = [e["url"] for e in inv["entries"] if e.get("url") and norm(e["url"]) in known_norm]
    assert clash == [], clash[:5]


def test_inventory_draws_from_distinct_source_families(inv):
    fam = {}
    for e in inv["entries"]:
        if e.get("ok"):
            fam.setdefault(e["brand"], set()).add(e["source_family"])
    multi = {b: sorted(v) for b, v in fam.items() if len(v) >= 3}
    assert len(multi) >= 8, multi
    assert all(len(v) >= 3 for b, v in fam.items() if b in ("Toyota", "Mazda", "Nissan", "Mitsubishi"))


def test_blocked_hosts_were_never_requested(inv):
    offenders = [e for e in inv["entries"]
                 if e.get("url") and any(t in e["url"].lower() for t in BLOCKED)
                 and e.get("status") != "BLOCKED_HOST"]
    assert offenders == [], offenders[:5]
    assert any(e.get("status") == "BLOCKED_HOST" for e in inv["entries"])


# ── capture log + provenance integrity ─────────────────────────────────────
def test_capture_log_counts_match_inventory(inv, cap):
    inv_ok = [e for e in inv["entries"] if e.get("ok")]
    log_ok = [r for r in cap["results"] if r.get("ok")]
    assert len(inv_ok) == len(log_ok) == inv["captured"]
    assert len(cap["results"]) == inv["attempted"]


def test_every_captured_artifact_sha_matches_its_sidecar(inv):
    """the red-before defect: silent overwrite broke inventory↔sidecar sha."""
    bad = []
    for e in inv["entries"]:
        a = e.get("artifact")
        if not a or not e.get("ok"):
            continue
        prov = os.path.join(FIXTURES, a + ".prov.json")
        if not os.path.exists(prov):
            bad.append((a, "no sidecar"))
            continue
        side = json.load(open(prov, encoding="utf-8"))
        if side.get("sha256") != e.get("sha256"):
            bad.append((a, "sha mismatch"))
        if not side.get("source_url", "").startswith("https://"):
            bad.append((a, "not https"))
        if side.get("provenance_state") != "ACQUISITION_VERIFIED":
            bad.append((a, f"provenance_state {side.get('provenance_state')}"))
    assert bad == [], bad[:6]


def test_no_artifact_name_collides_across_entries(inv):
    by_name = {}
    for e in inv["entries"]:
        if e.get("artifact"):
            by_name.setdefault(e["artifact"], set()).add(e.get("sha256"))
    # a repeated artifact name is only legal when every entry recorded the very
    # same content hash (identical final URL), i.e. no capture was overwritten
    overwritten = {n: sorted(s) for n, s in by_name.items() if len(s) > 1}
    assert overwritten == {}, overwritten


def test_dropped_sources_keep_an_explicit_reason(inv):
    drops = [e for e in inv["entries"] if e.get("status") == "SOURCE_DROPPED"]
    assert drops, "expected wrong-market / no-text-layer sources to be dropped, not used"
    for e in drops:
        assert e["blocker"] and len(e["blocker"]) > 20
    wrong = [e for e in drops if "wrong market" in e["blocker"]]
    assert wrong, "wrong-market captures must be recorded as drops"


# ── evidence + result ──────────────────────────────────────────────────────
def test_evidence_rows_are_bound_and_verified(ev):
    assert ev, "P108 must produce evidence rows or the report must say yield=0"
    for row in ev:
        assert row["source_url"].startswith("https://")
        assert row.get("model") and row.get("variant")
        prov = os.path.join(FIXTURES, row["artifact"] + ".prov.json")
        side = json.load(open(prov, encoding="utf-8"))
        assert side["provenance_state"] == "ACQUISITION_VERIFIED"
        assert side["source_url"] == row["source_url"]
        assert side["sha256"] == row["sha256"]


def test_evidence_never_stores_a_price(ev, recon, result):
    for row in ev:
        for k in row:
            assert not re.search(r"price|baht|thb|amount", k, re.I), k
        assert not re.search(r"\b[0-9]{1,3},[0-9]{3},[0-9]{3}\b", json.dumps(row, ensure_ascii=False))
    assert recon["price_pass"] is False
    assert recon["staging_written"] is False
    assert result["gates"]["price_pass"] is False
    assert result["gates"]["staging_written"] is False


def test_result_counts_agree_with_reconciliation(ev, recon, result):
    assert result["before_after"]["first_party_confirmed_variants"][0] == 482
    assert result["harvested_rows"] == len(ev)
    assert recon["harvested"] == len(ev)
    assert sum(v["rows"] for v in result["per_oem_delta"].values()) == len(ev)
    added = sum(v["confirmed_variants"] for v in result["per_oem_delta"].values())
    after = result["before_after"]["first_party_confirmed_variants"][1]
    assert after - 482 == added, (after, added)
    assert result["before_after"]["universe_records"][0] == result["before_after"]["universe_records"][1] == 1424


def test_every_new_variant_was_identity_only_at_the_p107_baseline(ev):
    uni = _load("identity_universe_p107.json")
    ident = {(r["manufacturer"], r["model"], r["variant"])
             for r in uni["universe"]["records"]
             if r.get("variant") and r.get("status") == "IDENTITY_ONLY"}
    promoted = [(e["manufacturer"], e["model"], e["variant"]) for e in ev
                if (e["manufacturer"], e["model"], e["variant"]) not in ident]
    assert promoted == [], promoted[:5]


def test_rejected_rows_record_explicit_reasons(recon):
    assert recon["rejected_rows"], "rejections must be recorded, never dropped silently"
    for r in recon["rejected_rows"]:
        assert r["reason"] and len(r["reason"]) > 8
    reasons = {r["reason"].split(":")[0] for r in recon["rejected_rows"]}
    assert len(reasons) >= 3, reasons


def test_identity_only_drop_equals_confirmed_gains(result, ev):
    baseline = _load("p107_final_result.json")["identity_only"]["variants"]
    after = result["identity_only"]["variants"]
    gained = result["before_after"]["first_party_confirmed_variants"][1] - 482
    assert gained > 0, "P108 must confirm at least one new variant or report yield=0"
    assert baseline - after == gained, (baseline, after, gained)


def test_gates_flags_remain_closed(result):
    g = result["gates"]
    assert g["staging_written"] is False and g["price_pass"] is False
    assert g["prisma_touched"] is False and g["p104_p103_p102_logic_changed"] is False
    assert g["production_db_unchanged"] is True


def test_result_declares_deficit_and_no_completeness_claim(result, inv):
    plan = _load("p108_target_plan.json")
    assert plan["totals"]["variant_deficit"] == 383, "baseline deficit must be re-derived, not assumed"
    gained = result["before_after"]["first_party_confirmed_variants"][1] - 482
    deficit_after = plan["totals"]["variant_deficit"] - gained
    assert 0 < deficit_after < plan["totals"]["variant_deficit"]
    assert inv["method"], "inventory must document how sources were discovered"
    assert result["before_after"]["first_party_confirmed_variants"][1] < 1424


# ── code hygiene ────────────────────────────────────────────────────────────
def test_acquire_script_has_unique_name_allocation():
    src = open(os.path.join(REPO, "scripts/p108_batch_acquire.py"), encoding="utf-8").read()
    assert "while os.path.exists" in src, "safe_name must never overwrite an existing artifact"
    ast.parse(src)


def test_rerun_is_deterministic():
    """Two consecutive runs in the CURRENT tree must produce identical evidence;
    the wave's artifacts are snapshotted and restored so a later fixture can
    never rewrite an accepted baseline."""
    patterns = ["p108_*", "catalog_reconciliation_p108*", "identity_*_p108*"]
    files = sorted({f for pat in patterns for f in glob.glob(os.path.join(OUT, pat))})
    assert files, patterns
    saved = dict((f, open(f, "rb").read()) for f in files)

    def run_once():
        proc = subprocess.run([sys.executable, "scripts/p108_variant_harvest.py"],
                              cwd=REPO, capture_output=True, text=True, timeout=900)
        assert proc.returncode == 0, proc.stderr[-2000:]
        rows = json.load(open(os.path.join(OUT, "p108_variant_evidence.json"),
                              encoding="utf-8"))["evidence"]
        canon = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canon.encode()).hexdigest(), len(rows)

    try:
        first = run_once()
        second = run_once()
    finally:
        for f, data in saved.items():
            with open(f, "wb") as fh:
                fh.write(data)
    assert first == second, (first, second)
    assert first[1] > 0


def test_this_suite_contains_no_vacuous_assertions():
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    forbidden = "or" + " True"          # never spelled literally in this file
    hits = [i + 1 for i, line in enumerate(src.split("\n"))
            if forbidden in line and "forbidden" not in line]
    assert hits == [], hits
    asserts = [line for line in src.split("\n") if line.strip().startswith("assert")]
    assert len(asserts) >= 25, len(asserts)
