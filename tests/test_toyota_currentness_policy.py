"""Toyota currentness: an explicit policy decision, not a silent convention.

The staged Toyota rows carry currentness=CURRENT for 96 of 99 records. This test
pins WHY, from the artifact bytes, and enforces whatever the policy record says:

  decision = keep_current            -> those rows stay CURRENT (unchanged)
  decision = demote_without_source_date -> they must become UNKNOWN

It also proves the three concepts stay separate:
  * availability (InStock)            — observed stock, not price validity
  * source-dated price validity       — priceValidUntil/dateModified/... (absent here)
  * capture time                      — never usable as effective-date evidence
"""
import json
import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY_PATH = os.path.join(REPO, "audit", "policies", "toyota-currentness.json")
STAGING = os.path.join(REPO, "audit", "data-staging", "vehicle_observations.jsonl")
ARTIFACT = os.path.join(REPO, "tests", "fixtures", "oem-artifacts", "toyota_pricelist_page.html")
DATE_TERMS = ("priceValidUntil", "dateModified", "datePublished", "validFrom", "validThrough")


@pytest.fixture(scope="module")
def policy():
    with open(POLICY_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def toyota_rows():
    with open(STAGING, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    return [r for r in rows if r["source"]["name"].startswith("Toyota")]


@pytest.fixture(scope="module")
def artifact_counts():
    raw = open(ARTIFACT, encoding="utf-8", errors="ignore").read()
    counts = {term: raw.count(term) for term in DATE_TERMS}
    counts["availability"] = raw.count("availability")
    counts["InStock"] = raw.count("InStock")
    counts["OutOfStock"] = raw.count("OutOfStock")
    return counts


# ─────────────────────────── the decision record ───────────────────────────

def test_policy_record_is_explicit_and_decided(policy):
    assert policy["policy_id"] == "toyota-currentness-v1"
    assert policy["decision"] in ("keep_current", "demote_without_source_date"), policy["decision"]
    assert policy["row_change_required_now"] is (policy["decision"] != "keep_current")
    assert policy["demotion"]["target"] == "UNKNOWN"
    # the record must name what the evidence is NOT, not only what it is
    assert "capture_time_as_effective_date" in policy["basis_not_claimed"]
    assert "source_dated_price_validity" in policy["basis_not_claimed"]


def test_policy_evidence_matches_the_artifact(policy, artifact_counts):
    """The record may not drift from reality — recompute, don't trust."""
    rec = policy["observed_evidence"]
    for term in DATE_TERMS + ("availability", "InStock", "OutOfStock"):
        assert rec[term] == artifact_counts[term], (
            f"policy record says {term}={rec[term]}, artifact says {artifact_counts[term]}"
        )


def test_availability_and_price_validity_are_separated(artifact_counts):
    """Distinguish the two concepts: stock availability exists, price validity does not."""
    assert artifact_counts["availability"] > 0, "no availability evidence on this artifact"
    assert artifact_counts["InStock"] > 0
    dated = {t: artifact_counts[t] for t in DATE_TERMS if artifact_counts[t]}
    # if the source starts publishing a validity date, this test fails on purpose:
    # the policy record must then be re-decided, not quietly relied upon
    assert not dated, (
        f"artifact now publishes source-dated price validity {dated} — "
        "revisit audit/policies/toyota-currentness.json before trusting currentness"
    )


# ───────────────────── the decision applied to the rows ─────────────────────

def test_rows_follow_the_policy_decision(policy, toyota_rows):
    assert toyota_rows, "no Toyota rows staged"
    decision = policy["decision"]
    instock = [r for r in toyota_rows if r.get("raw_labels", {}).get("availability_raw") == "InStock"]
    out_of_stock = [r for r in toyota_rows
                    if r.get("raw_labels", {}).get("availability_raw") != "InStock"]

    if decision == "keep_current":
        # unchanged: availability-backed CURRENT, and NOT price-validity-backed
        not_current = [r for r in instock if r["price"]["currentness"] != "CURRENT"]
        assert not not_current, (
            f"{len(not_current)} InStock rows are not CURRENT although the policy says keep: "
            + str([r["identity"]["model_raw"] for r in not_current[:5]])
        )
    else:
        stale = [r for r in toyota_rows if r["price"]["currentness"] != "UNKNOWN"]
        assert not stale, (
            f"policy says demote without source-dated validity but {len(stale)} rows still claim "
            + str([r["price"]["currentness"] for r in stale[:5]])
        )

    # independent of the decision: non-InStock rows never claim CURRENT
    wrongly_current = [r for r in out_of_stock if r["price"]["currentness"] == "CURRENT"]
    assert not wrongly_current, [r["identity"]["model_raw"] for r in wrongly_current]


def test_no_row_uses_capture_time_as_currentness_evidence(toyota_rows):
    """captured_at is acquisition bookkeeping, never source effective-date evidence."""
    for r in toyota_rows:
        blob = json.dumps(r, ensure_ascii=False)
        assert r["source"]["captured_at"] not in json.dumps(
            r.get("raw_labels", {}), ensure_ascii=False
        ), f"{r['identity']['model_raw']}: captured_at leaked into raw source labels"
        # no fabricated validity date anywhere on the row
        for term in DATE_TERMS:
            assert term not in blob, f"{r['identity']['model_raw']}: row asserts {term}"


def test_currentness_claims_stay_internally_consistent(toyota_rows):
    """CURRENT without a validity date is only licensed by the policy record —
    so the record must exist and be readable next to the rows it governs."""
    with open(POLICY_PATH, encoding="utf-8") as f:
        policy = json.load(f)
    current = [r for r in toyota_rows if r["price"]["currentness"] == "CURRENT"]
    for r in current:
        assert r.get("raw_labels", {}).get("availability_raw") == "InStock", (
            f"{r['identity']['model_raw']}: CURRENT without InStock"
        )
        assert policy["currentness_basis"] == "availability_instock"
        assert not re.search(r"\d{4}-\d{2}-\d{2}", json.dumps(r.get("raw_labels", {}))), (
            "raw labels carry a date; price validity must be source-dated, not inferred"
        )
