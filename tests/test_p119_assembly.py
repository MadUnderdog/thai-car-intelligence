"""
P119 — field-level multi-source assembly boundaries (Blueprint §96–97).

Red-before: written against d8b3ef6 (+plan commit dc0357b) where
lib/thai_factory/assembly/* does not exist (gaps G1–G7 in the target plan).
Modules load dynamically so each test fails individually.

Inputs are REAL committed artifacts only:
  - audit/coverage/p113_evidence_packets.json (488 packets; 417 ACCEPTED)
  - storage/thai-alias-catalog.json (34 brands / 157 models / 506 aliases)
  - tests/fixtures/* (all 128 packet artifacts resolvable, sidecars present)
Conflict/mutation fixtures are in-memory transformations of REAL packets
(tmp only, never emitted as real consensus).
"""
import copy
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

BASE_SHA = "d8b3ef661e4ca5cbd609cc790fce55873d60ebf1"
PACKETS_PATH = REPO / "audit" / "coverage" / "p113_evidence_packets.json"
ALIAS_PATH = REPO / "storage" / "thai-alias-catalog.json"
FIXTURES = REPO / "tests" / "fixtures"


def load_mod(name: str):
    try:
        return importlib.import_module(f"thai_factory.assembly.{name}")
    except Exception:
        return None


def assemble_mod():
    m = load_mod("assemble")
    assert m is not None, "lib/thai_factory/assembly/assemble.py must exist"
    return m


def join_mod():
    m = load_mod("join_keys")
    assert m is not None, "lib/thai_factory/assembly/join_keys.py must exist"
    return m


def _packets():
    return json.loads(PACKETS_PATH.read_text(encoding="utf-8"))["packets"]


def _accepted():
    return [p for p in _packets() if p.get("status") == "ACCEPTED"]


def _catalog():
    return json.loads(ALIAS_PATH.read_text(encoding="utf-8"))


def run_assemble(packets, catalog=None, fixtures_dir=FIXTURES):
    A = assemble_mod()
    return A.assemble(packets, catalog if catalog is not None else _catalog(), fixtures_dir=str(fixtures_dir))


def price_obs(packet):
    return packet["observations"]["price"][0]


def base_packet():
    return copy.deepcopy(next(p for p in _accepted() if p["observations"].get("price")))


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── A: deterministic rerun ──────────────────────────────────────────────────
def test_p119_A_same_packet_set_rerun_is_byte_identical(tmp_path):
    A = assemble_mod()
    packets = _accepted()
    out1, out2 = tmp_path / "d1", tmp_path / "d2"
    A.write_outputs(run_assemble(packets), out1)
    A.write_outputs(run_assemble(packets), out2)
    for name in ("assembled_records.jsonl", "conflicts.jsonl", "join_errors.jsonl"):
        f1, f2 = out1 / name, out2 / name
        assert f1.exists() and f2.exists(), f"missing output {name}"
        assert sha_file(f1) == sha_file(f2), f"{name} must be byte-identical across runs"


# ── B: field-level provenance = exact source observation ────────────────────
def test_p119_B_field_provenance_points_to_exact_artifact_and_locator(tmp_path):
    packets = _accepted()
    src = next(p for p in packets if p["observations"].get("price"))
    obs = price_obs(src)
    result = run_assemble(packets)
    rec = next(r for r in result.records if r["candidate_id"] == src["packet_id"])
    field = obs["field"]
    prov = rec["fields"][field]
    assert prov["value"] == obs["value"]
    assert prov["artifact_sha256"] == obs["sha256"], "provenance sha must be the observation's artifact sha"
    assert prov["locator"] == obs["locator"], "provenance locator must be the observation's locator"
    assert prov["source_id"] == obs["source_url"]
    assert prov["trust_tier"] == obs["trust_tier"]
    assert prov["packet_id"] == src["packet_id"] and prov["obs_id"] == obs["obs_id"]
    assert prov["observed_at"] == src.get("observed_at")
    # locator quote must re-resolve against the value (re-resolution lite)
    assert str(obs["value"]) in str(obs["locator"].get("quote", str(obs["value"])))


# ── C: contamination fails closed ──────────────────────────────────────────
def test_p119_C_source_B_locator_on_source_A_value_fails_closed():
    # mutation 1: another packet's artifact sha attached to A's observation
    packets = _accepted()
    victim = next(p for p in packets if p["observations"].get("price"))
    other = next(p for p in packets if p["observations"].get("price") and p["packet_id"] != victim["packet_id"])
    mutated = copy.deepcopy(victim)
    mutated["observations"]["price"][0]["sha256"] = price_obs(other)["sha256"]
    mutated["observations"]["price"][0]["locator"] = copy.deepcopy(price_obs(other)["locator"])
    result = run_assemble([mutated, other])
    failures = [f for f in result.failures if f.get("packet_id") == mutated["packet_id"]]
    assert failures, "attaching source B sha/locator to source A's value must fail closed"
    rec = next((r for r in result.records if r["candidate_id"] == mutated["packet_id"]), None)
    field = mutated["observations"]["price"][0]["field"]
    assert rec is None or field not in rec["fields"], "contaminated field must not enter accepted output"

    # mutation 2: price locator quote no longer carries the value (re-resolution fails)
    mutated2 = copy.deepcopy(victim)
    mutated2["observations"]["price"][0]["locator"] = {"mode": "value_digits", "quote": "000000", "resolved": True}
    result2 = run_assemble([mutated2])
    failures2 = [f for f in result2.failures if f.get("packet_id") == mutated2["packet_id"]]
    assert failures2, "locator quote that does not re-resolve to the value must fail closed"
    rec2 = next((r for r in result2.records if r["candidate_id"] == mutated2["packet_id"]), None)
    assert rec2 is None or mutated2["observations"]["price"][0]["field"] not in rec2["fields"]


# ── D: same-tier conflict — newest wins, both sides retained ────────────────
def test_p119_D_same_tier_conflict_newest_wins_both_sides_retained():
    older = base_packet()
    newer = copy.deepcopy(older)
    newer["packet_id"] = older["packet_id"] + "X"
    newer["observed_at"] = "2026-09-29T12:00:00"
    older["observed_at"] = "2026-01-01T00:00:00"
    price_obs(newer)["value"] = price_obs(older)["value"] + 10000
    # locator quote must re-resolve to the (new) value — as any real capture would
    price_obs(newer)["locator"] = {"mode": "value_digits", "quote": str(price_obs(newer)["value"]), "resolved": True}
    # keep each packet's own artifact/sha coherent (real files, real sidecars)
    result = run_assemble([older, newer])
    conflicts = [c for c in result.conflicts if c["field"] == price_obs(older)["field"]]
    assert conflicts, "same-tier different values must produce a conflict record"
    conflict = conflicts[0]
    assert conflict["status"] == "SELECTED_SAME_TIER_NEWEST"
    assert conflict["selected"] is not None
    assert conflict["selected"]["value"] == price_obs(newer)["value"], "newest dated observation must be selected"
    packet_ids = {side["packet_id"] for side in conflict["sides"]}
    assert {older["packet_id"], newer["packet_id"]} <= packet_ids, "BOTH sides must remain recorded with evidence"
    for side in conflict["sides"]:
        assert side["artifact_sha256"] and side["locator"], "each side keeps its own evidence"


# ── E: cross-tier conflict — higher tier wins, lower evidence retained ──────
def test_p119_E_cross_tier_conflict_higher_tier_wins_lower_evidence_kept():
    official = base_packet()
    reference = copy.deepcopy(official)
    reference["packet_id"] = official["packet_id"] + "R"
    reference["observed_at"] = "2020-01-01T00:00:00"  # older AND lower tier
    price_obs(reference)["value"] = price_obs(official)["value"] - 50000
    price_obs(reference)["locator"] = {"mode": "value_digits", "quote": str(price_obs(reference)["value"]), "resolved": True}
    price_obs(reference)["trust_tier"] = "reference"
    result = run_assemble([official, reference])
    conflicts = [c for c in result.conflicts if c["field"] == price_obs(official)["field"]]
    assert conflicts, "cross-tier different values must produce a conflict record"
    conflict = conflicts[0]
    assert conflict["status"] == "SELECTED_HIGHER_TIER"
    assert conflict["selected"]["trust_tier"] == "official_verified"
    assert conflict["selected"]["value"] == price_obs(official)["value"]
    lower = [s for s in conflict["sides"] if s["packet_id"] == reference["packet_id"]]
    assert lower and lower[0]["value"] == price_obs(reference)["value"], "lower-tier observation must be retained verbatim"


# ── F: unresolvable conflict → QUARANTINED, value not emitted ───────────────
def test_p119_F_unresolved_conflict_stays_quarantined():
    a = base_packet()
    b = copy.deepcopy(a)
    b["packet_id"] = a["packet_id"] + "T"
    a["observed_at"] = "2026-05-05T00:00:00"
    b["observed_at"] = "2026-05-05T00:00:00"  # same tier, same date, different value
    price_obs(b)["value"] = price_obs(a)["value"] + 7777
    price_obs(b)["locator"] = {"mode": "value_digits", "quote": str(price_obs(b)["value"]), "resolved": True}
    result = run_assemble([a, b])
    conflicts = [c for c in result.conflicts if c["field"] == price_obs(a)["field"] and c["status"] == "QUARANTINED"]
    assert conflicts, "same-tier same-date different values must quarantine"
    assert conflicts[0]["selected"] is None, "quarantined conflict must select nothing"
    rec = next((r for r in result.records if r["candidate_id"] == a["packet_id"]), None)
    field = price_obs(a)["field"]
    assert rec is None or field not in rec["fields"], "quarantined field must not be emitted as accepted"


# ── G: alias-backed join vs display-string-only ─────────────────────────────
def test_p119_G_join_uses_evidence_backed_key_display_only_rejected():
    J = join_mod()
    packets = _accepted()
    resolved_ok = None
    for p in packets:
        r = J.resolve_join_key(p, _catalog())
        if r.get("ok"):
            resolved_ok = (p, r)
            break
    assert resolved_ok, "at least one real packet must resolve through the alias catalog"
    p, r = resolved_ok
    assert set(r["join_key"]) == {"manufacturer_slug", "model_slug", "variant_slug", "model_year"}
    assert r["join_key"]["manufacturer_slug"] and r["join_key"]["model_slug"]
    matched = str(r.get("matched_via") or "")
    assert matched.startswith(("identity_universe", "alias_catalog")) or matched in ("slug", "nameEn", "nameTh", "alias"), \
        f"resolution must record how the evidence-backed alias path matched, got: {matched}"
    assert r.get("alias_evidence") is not None or matched.startswith("alias_catalog"), \
        "identity-universe joins must carry their source evidence"
    # display-string-only: model segment that exists nowhere in packets+catalog
    bogus = copy.deepcopy(p)
    parts = bogus["candidate_key"].split("|")
    parts[1] = "Totally Unknown Model 9000"
    bogus["candidate_key"] = "|".join(parts)
    r2 = J.resolve_join_key(bogus, _catalog())
    assert not r2.get("ok"), "display-string-only collision must be rejected"
    assert r2.get("reason"), "rejection must carry an explicit reason"


# ── H: candidate_id retained; canonical_id only after reconcile ─────────────
def test_p119_H_candidate_id_until_reconcile_canonical_is_deterministic():
    A = assemble_mod()
    packets = _accepted()[:20]
    result = run_assemble(packets)
    assert result.records, "assembly must produce records"
    for rec in result.records:
        assert rec["candidate_id"], "candidate_id must be present"
        assert rec.get("canonical_id") is None, "canonical_id must not exist before reconciliation"
    reconciled1 = A.reconcile(result.records)
    reconciled2 = A.reconcile(result.records)
    for r1, r2 in zip(reconciled1, reconciled2):
        assert r1["canonical_id"] and r1["canonical_id"] == r2["canonical_id"], "canonical_id must be deterministic"
        assert r1["candidate_id"] == r2["candidate_id"], "candidate_id must never be replaced"


# ── J: no DB/provider imports; values ⊆ packet observations ────────────────
def test_p119_J_assembly_reads_only_packets_no_db_or_provider():
    forbidden = ("psycopg", "prisma", "lib.db", "import db", "sqlite", "requests", "httpx", "urllib.request", "openai", "anthropic")
    for name in ("assemble.py", "models.py", "join_keys.py", "ai_proposals.py", "report.py"):
        path = REPO / "lib" / "thai_factory" / "assembly" / name
        if not path.exists():
            raise AssertionError(f"lib/thai_factory/assembly/{name} must exist")
        src = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in src, f"{name} must not reference {token}"

    packets = _accepted()
    value_universe = set()
    for p in packets:
        for cat in ("identity", "price", "spec"):
            for o in p["observations"].get(cat, []):
                for v in (o.get("value"), o.get("value_numeric"), o.get("value_text"), o.get("label")):
                    if v is not None:
                        value_universe.add(json.dumps(v, sort_keys=True, default=str))
    result = run_assemble(packets)
    for rec in result.records:
        for field, prov in rec["fields"].items():
            assert json.dumps(prov["value"], sort_keys=True, default=str) in value_universe, \
                f"assembled value for {field} not present in any packet observation"


# ── K: repeat run, no duplicates ────────────────────────────────────────────
def test_p119_K_repeat_run_produces_no_duplicates(tmp_path):
    A = assemble_mod()
    packets = _accepted()
    out = tmp_path / "out"
    A.write_outputs(run_assemble(packets), out)
    rows = [json.loads(l) for l in (out / "assembled_records.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    keys = [(r["candidate_id"], f) for r in rows for f in r["fields"]]
    assert len(keys) == len(set(keys)), "no duplicate (candidate, field) rows"
    candidate_ids = [r["candidate_id"] for r in rows]
    assert len(candidate_ids) == len(set(candidate_ids)), "no duplicate records"
    out2 = tmp_path / "out2"
    A.write_outputs(run_assemble(packets), out2)
    assert len((out2 / "assembled_records.jsonl").read_text(encoding="utf-8").splitlines()) == len(rows)


# ── L: legacy/unverified stays explicitly unverified ────────────────────────
def test_p119_L_legacy_unverified_is_flagged_not_verified():
    p = base_packet()
    price_obs(p)["provenance_state"] = "LEGACY_UNVERIFIED"
    result = run_assemble([p])
    rec = next((r for r in result.records if r["candidate_id"] == p["packet_id"]), None)
    assert rec is not None, "legacy observation may be assembled — but only as explicitly unverified"
    prov = rec["fields"][price_obs(p)["field"]]
    assert prov["provenance_state"] == "LEGACY_UNVERIFIED", "provenance state must be preserved verbatim"
    assert prov["verified"] is False, "legacy/unverified must never present as verified"


# ── M: no schema/provider/verifier changes vs P118 head ─────────────────────
def test_p119_M_no_schema_acceptance_verifier_provider_changes():
    changed = subprocess.run(
        ["git", "diff", "--name-only", BASE_SHA], cwd=REPO, capture_output=True, text=True, timeout=30,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=REPO, capture_output=True, text=True, timeout=30,
    ).stdout.splitlines()
    forbidden_prefixes = (
        "prisma/", "lib/thai_factory/acceptance/", "lib/thai_factory/catalog/verifier.py",
        "lib/research/", "lib/thai_factory/extract/ai_extractor.py", "package.json",
        "package-lock.json", ".env", "vitest.config", "tsconfig",
    )
    offending = [f for f in changed + untracked if f.startswith(forbidden_prefixes)]
    assert not offending, f"P119 must not touch: {offending}"


# ── report surface (feeds N/O) ──────────────────────────────────────────────
def test_p119_report_has_required_sections(tmp_path):
    A = assemble_mod()
    packets = _accepted()
    out = tmp_path / "out"
    result = run_assemble(packets)
    A.write_outputs(result, out)
    rep = A.write_report(result, tmp_path / "report", commit_sha=BASE_SHA)
    data = json.loads(Path(rep["json"]).read_text(encoding="utf-8"))
    for key in ("schema", "commit", "packets_in", "records", "fields_assembled",
                "per_source_contribution", "conflicts", "quarantines", "join_errors",
                "provenance_coverage", "resolutions", "blockers"):
        assert key in data, f"report missing {key}"
    assert data["packets_in"] == len(packets)
    assert Path(rep["md"]).exists()
