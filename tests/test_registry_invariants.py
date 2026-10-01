"""Registry evidence/consistency invariants.

Guards against the P97+ defects where `last_success_sha256` kept pointing at a
LEGACY_UNVERIFIED artifact after a brand was promoted to ACQUISITION_VERIFIED,
where `last_success_sha256` was left null, and where registry `generated_at`
preceded the capture times of the facts it contained.

Every value is recomputed from the on-disk artifacts + sidecars — no stored
string in the registry is trusted as evidence for itself.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG_PATH = os.path.join(REPO, "audit", "coverage", "oem-registry.json")
FIXTURE_DIR = os.path.join(REPO, "tests", "fixtures", "oem-artifacts")


def _load():
    with open(REG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _sha(artifact):
    p = os.path.join(FIXTURE_DIR, artifact)
    assert os.path.exists(p), f"promoted artifact missing from tree: {artifact}"
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _captured_at(artifact):
    p = os.path.join(FIXTURE_DIR, artifact + ".prov.json")
    assert os.path.exists(p), f"promoted artifact missing sidecar: {artifact}.prov.json"
    return json.load(open(p, encoding="utf-8"))["captured_at"]


def _dt(s):
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _verified_parsed():
    reg = _load()
    return [b for b in reg["brands"]
            if b.get("provenance_status") == "ACQUISITION_VERIFIED"
            and b.get("adapter_status") == "PARSED_TESTED"]


def _promoted_endpoints(brand):
    eps = [e for e in brand.get("captured_endpoints", [])
           if e.get("provenance_state") == "ACQUISITION_VERIFIED" and e.get("parsed") is True]
    eps.sort(key=lambda e: _captured_at(e["artifact"]) if os.path.exists(
        os.path.join(FIXTURE_DIR, e["artifact"] + ".prov.json")) else "", reverse=True)
    return eps


def test_registry_has_verified_parsed_brands():
    assert len(_verified_parsed()) >= 17


def test_last_success_sha_equals_promoted_artifact():
    """last_success_sha256 must be the promoted parsed ACQUISITION_VERIFIED artifact."""
    for b in _verified_parsed():
        eps = _promoted_endpoints(b)
        assert eps, (f"{b['brand']}: provenance/adapter claim verified+parsed but no "
                     f"captured_endpoint is ACQUISITION_VERIFIED with parsed=true")
        expected = _sha(eps[0]["artifact"])
        assert b.get("last_success_sha256") == expected, (
            f"{b['brand']}: last_success_sha256={b.get('last_success_sha256')} != "
            f"promoted {eps[0]['artifact']} sha {expected}")


def test_last_success_never_targets_legacy_artifact():
    """No verified+parsed brand may point last_success at a LEGACY_UNVERIFIED artifact."""
    legacy_sha = {}
    for b in _verified_parsed():
        for e in b.get("captured_endpoints", []):
            if e.get("provenance_state") == "LEGACY_UNVERIFIED" and e.get("artifact"):
                legacy_sha[e["artifact"]] = _sha(e["artifact"])
        ls = b.get("last_success_sha256")
        assert ls, f"{b['brand']}: last_success_sha256 is null"
        for art, h in legacy_sha.items():
            assert ls != h, f"{b['brand']}: last_success points at LEGACY artifact {art}"
        for e in b.get("captured_endpoints", []):
            if e.get("artifact") and _sha(e["artifact"]) == ls:
                assert e["provenance_state"] != "LEGACY_UNVERIFIED", (
                    f"{b['brand']}: last_success_sha resolves to LEGACY_UNVERIFIED endpoint "
                    f"{e['artifact']}")


def test_last_success_at_at_or_after_capture_time():
    for b in _verified_parsed():
        eps = _promoted_endpoints(b)
        cap = _captured_at(eps[0]["artifact"])
        assert _dt(b["last_success_at"]) >= _dt(cap), (
            f"{b['brand']}: last_success_at {b['last_success_at']} precedes capture "
            f"{cap} of {eps[0]['artifact']}")


def test_generated_at_not_older_than_any_success():
    reg = _load()
    gen = _dt(reg["generated_at"])
    for b in reg["brands"]:
        lsa = b.get("last_success_at")
        if lsa:
            assert gen >= _dt(lsa), (
                f"{b['brand']}: registry generated_at {reg['generated_at']} precedes "
                f"last_success_at {lsa}")


def test_every_endpoint_sha_matches_disk():
    reg = _load()
    for b in reg["brands"]:
        for e in b.get("captured_endpoints", []):
            art = e.get("artifact")
            if not art:
                continue
            p = os.path.join(FIXTURE_DIR, art)
            if not os.path.exists(p):
                continue
            actual = _sha(art)
            assert e.get("sha256") == actual, (
                f"{b['brand']}: endpoint {art} recorded sha {e.get('sha256')} != disk {actual}")


def test_promoted_endpoint_sidecar_is_verified():
    for b in _verified_parsed():
        eps = _promoted_endpoints(b)
        sc_path = os.path.join(FIXTURE_DIR, eps[0]["artifact"] + ".prov.json")
        sc = json.load(open(sc_path, encoding="utf-8"))
        assert sc["provenance_state"] == "ACQUISITION_VERIFIED"
        assert sc["captured_at"] != "UNKNOWN"
