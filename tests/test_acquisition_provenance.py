"""
Boundary tests for acquisition-side provenance.

These tests execute the actual AcquisitionWriter with a controlled clock,
prove manifest timestamp comes from acquisition call, and verify hash mismatch => hard failure.

NOT circular: writer emits X → persists X + hash → reader verifies X + hash.
"""
import os
import json
import hashlib
import pytest
from datetime import datetime, timezone

# Add parent directory to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from thai_factory.acquisition.provenance import (
    AcquisitionWriter,
    AcquisitionReader,
    LegacyManifestReader,
    get_provenance_for_fixture,
    ProvenanceError,
)


# ─── Acquisition Writer Tests (boundary: capture-time provenance) ───

def test_writer_records_capture_time_from_clock(tmp_path):
    """Writer must record captured_at from the clock callable, not retrofitted."""
    fixed_time = "2026-01-15T12:00:00Z"
    
    provenance = AcquisitionWriter.write(
        content="<html><body>test</body></html>",
        source_url="https://example.com/test",
        acquisition_method="playwright",
        output_dir=str(tmp_path),
        filename="test_page.html",
        session_id="test_session_001",
        clock=lambda: fixed_time,
    )
    
    assert provenance['captured_at'] == fixed_time, \
        f"captured_at should come from clock, got {provenance['captured_at']}"
    assert provenance['source_url'] == "https://example.com/test"
    assert provenance['session_id'] == "test_session_001"
    assert len(provenance['sha256']) == 64  # SHA-256 hex


def test_writer_creates_artifact_and_sidecar_together(tmp_path):
    """Writer must create artifact + sidecar as a pair."""
    provenance = AcquisitionWriter.write(
        content="<html>content</html>",
        source_url="https://example.com",
        acquisition_method="http_get",
        output_dir=str(tmp_path),
        filename="page.html",
        session_id="run_123",
        clock=lambda: "2026-01-15T10:00:00Z",
    )
    
    artifact_path = tmp_path / "page.html"
    sidecar_path = tmp_path / "page.html.prov.json"
    
    assert artifact_path.exists(), "Artifact not created"
    assert sidecar_path.exists(), "Sidecar not created"
    
    # Sidecar must match returned provenance
    with open(sidecar_path) as f:
        saved = json.load(f)
    assert saved == provenance


def test_writer_sha256_matches_content(tmp_path):
    """SHA-256 in sidecar must match artifact content."""
    content = "<html><body>Toyota Corolla Altis</body></html>"
    
    AcquisitionWriter.write(
        content=content,
        source_url="https://toyota.co.th",
        acquisition_method="playwright",
        output_dir=str(tmp_path),
        filename="toyota.html",
        session_id="run_456",
        clock=lambda: "2026-01-15T11:00:00Z",
    )
    
    # Verify hash manually
    expected_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    with open(tmp_path / "toyota.html.prov.json") as f:
        saved = json.load(f)
    
    assert saved['sha256'] == expected_hash


# ─── Acquisition Reader Tests (boundary: hash verification) ───

def test_reader_verifies_correct_hash(tmp_path):
    """Reader must accept artifact with matching hash."""
    content = "<html>valid content</html>"
    
    AcquisitionWriter.write(
        content=content,
        source_url="https://example.com",
        acquisition_method="playwright",
        output_dir=str(tmp_path),
        filename="valid.html",
        session_id="run_789",
        clock=lambda: "2026-01-15T12:00:00Z",
    )
    
    read_content, provenance = AcquisitionReader.read(str(tmp_path / "valid.html"))
    assert read_content == content
    assert provenance['captured_at'] == "2026-01-15T12:00:00Z"


def test_reader_fails_on_hash_mismatch(tmp_path):
    """Reader must RAISE on SHA-256 mismatch, not silently continue."""
    content = "<html>original content</html>"
    
    AcquisitionWriter.write(
        content=content,
        source_url="https://example.com",
        acquisition_method="playwright",
        output_dir=str(tmp_path),
        filename="tampered.html",
        session_id="run_000",
        clock=lambda: "2026-01-15T12:00:00Z",
    )
    
    # Tamper with artifact (change content but keep sidecar)
    tampered_path = tmp_path / "tampered.html"
    with open(tampered_path, 'w') as f:
        f.write("<html>TAMPERED CONTENT</html>")
    
    # Reader must raise ProvenanceError
    with pytest.raises(ProvenanceError) as exc_info:
        AcquisitionReader.read(str(tampered_path))
    
    assert "SHA-256 mismatch" in str(exc_info.value)


def test_reader_fails_on_missing_sidecar(tmp_path):
    """Reader must RAISE if sidecar missing."""
    # Create artifact without sidecar
    artifact_path = tmp_path / "orphan.html"
    with open(artifact_path, 'w') as f:
        f.write("<html>no sidecar</html>")
    
    with pytest.raises(ProvenanceError) as exc_info:
        AcquisitionReader.read(str(artifact_path))
    
    assert "sidecar not found" in str(exc_info.value)


def test_reader_fails_on_missing_required_field(tmp_path):
    """Reader must RAISE if provenance missing required fields."""
    content = "<html>content</html>"
    
    AcquisitionWriter.write(
        content=content,
        source_url="https://example.com",
        acquisition_method="playwright",
        output_dir=str(tmp_path),
        filename="incomplete.html",
        session_id="run_111",
        clock=lambda: "2026-01-15T12:00:00Z",
    )
    
    # Remove required field from sidecar
    sidecar_path = tmp_path / "incomplete.html.prov.json"
    with open(sidecar_path) as f:
        prov = json.load(f)
    del prov['source_url']
    with open(sidecar_path, 'w') as f:
        json.dump(prov, f)
    
    with pytest.raises(ProvenanceError) as exc_info:
        AcquisitionReader.read(str(tmp_path / "incomplete.html"))
    
    assert "missing required field" in str(exc_info.value)


# ─── Legacy Manifest Tests (fallback for historical fixtures) ───

def test_legacy_manifest_returns_unknown_for_missing_entry(tmp_path):
    """Legacy manifest should return UNKNOWN for fixtures not in manifest."""
    manifest_path = tmp_path / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump({}, f)
    
    reader = LegacyManifestReader(str(manifest_path))
    prov = reader.get_provenance("unknown_fixture.html")
    
    assert prov['captured_at'] == 'UNKNOWN'
    assert prov['legacy'] == True


def test_legacy_manifest_returns_timestamp_for_known_entry(tmp_path):
    """Legacy manifest should return captured_at for known entries."""
    manifest_path = tmp_path / "manifest.json"
    manifest = {
        "known.html": {
            "source_url": "https://example.com",
            "captured_at": "2026-01-15T08:00:00Z",
            "acquisition_method": "playwright",
            "session_context": "historical_run",
            "sha256": "abc123...",
        }
    }
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f)
    
    reader = LegacyManifestReader(str(manifest_path))
    prov = reader.get_provenance("known.html")
    
    assert prov['captured_at'] == "2026-01-15T08:00:00Z"
    assert prov['legacy'] == True


def test_legacy_manifest_treats_empty_string_as_unknown(tmp_path):
    """Legacy manifest should treat empty captured_at as UNKNOWN."""
    manifest_path = tmp_path / "manifest.json"
    manifest = {
        "empty.html": {
            "captured_at": "",
            "source_url": "https://example.com",
        }
    }
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f)
    
    reader = LegacyManifestReader(str(manifest_path))
    prov = reader.get_provenance("empty.html")
    
    assert prov['captured_at'] == 'UNKNOWN'


# ─── Unified Getter Tests ───

def test_getter_prefers_sidecar_over_legacy(tmp_path):
    """get_provenance_for_fixture should prefer sidecar when available."""
    content = "<html>with sidecar</html>"
    
    # Write with sidecar
    AcquisitionWriter.write(
        content=content,
        source_url="https://new.com",
        acquisition_method="playwright",
        output_dir=str(tmp_path),
        filename="both.html",
        session_id="run_new",
        clock=lambda: "2026-02-01T10:00:00Z",
    )
    
    # Also create legacy manifest with different timestamp
    manifest_path = tmp_path / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump({"both.html": {"captured_at": "2020-01-01T00:00:00Z"}}, f)
    
    prov = get_provenance_for_fixture(
        str(tmp_path / "both.html"),
        legacy_manifest_path=str(manifest_path),
    )
    
    # Should use sidecar (new timestamp), not legacy
    assert prov['captured_at'] == "2026-02-01T10:00:00Z"
    assert not prov.get('legacy', False)


def test_getter_falls_back_to_legacy(tmp_path):
    """get_provenance_for_fixture should fall back to legacy when no sidecar."""
    # Create artifact without sidecar
    artifact_path = tmp_path / "legacy_only.html"
    with open(artifact_path, 'w') as f:
        f.write("<html>legacy</html>")
    
    # Create legacy manifest
    manifest_path = tmp_path / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump({"legacy_only.html": {"captured_at": "2025-06-01T12:00:00Z"}}, f)
    
    prov = get_provenance_for_fixture(
        str(artifact_path),
        legacy_manifest_path=str(manifest_path),
    )
    
    assert prov['captured_at'] == "2025-06-01T12:00:00Z"
    assert prov['legacy'] == True


def test_getter_returns_unknown_when_no_provenance(tmp_path):
    """get_provenance_for_fixture should return UNKNOWN when no provenance available."""
    artifact_path = tmp_path / "no_provenance.html"
    with open(artifact_path, 'w') as f:
        f.write("<html>no prov</html>")
    
    prov = get_provenance_for_fixture(str(artifact_path))
    
    assert prov['captured_at'] == 'UNKNOWN'
    assert prov['legacy'] == True


# ─── Integration Test: End-to-end acquisition → provenance → verification → extraction ───

def test_integration_acquisition_to_extraction(tmp_path):
    """
    Integration: run actual capture/writer path, then feed through get_provenance_for_fixture.
    Proves: sidecar path selected, hash verification occurs, tampering fails.
    """
    # Step 1: Simulate acquisition - capture and write with AcquisitionWriter
    content = "<html><body><h1>Toyota Corolla Altis</h1><p>฿1,099,000</p></body></html>"
    fixed_time = "2026-09-25T10:30:00Z"
    
    provenance = AcquisitionWriter.write(
        content=content,
        source_url="https://www.toyota.co.th/en/pricelist",
        acquisition_method="playwright",
        output_dir=str(tmp_path),
        filename="integration_test.html",
        session_id="integration_run_001",
        clock=lambda: fixed_time,
    )
    
    artifact_path = str(tmp_path / "integration_test.html")
    
    # Step 2: Feed through get_provenance_for_fixture - should select sidecar path
    from thai_factory.acquisition.provenance import get_provenance_for_fixture
    
    prov = get_provenance_for_fixture(artifact_path)
    
    # Prove sidecar path selected (not legacy)
    assert not prov.get('legacy', False), "Should use sidecar, not legacy fallback"
    assert prov['provenance_state'] == 'ACQUISITION_VERIFIED'
    assert prov['captured_at'] == fixed_time
    assert prov['sha256'] == provenance['sha256']
    
    # Step 3: Verify hash verification occurs (read succeeds)
    read_content, read_prov = AcquisitionReader.read(artifact_path)
    assert read_content == content
    assert read_prov['provenance_state'] == 'ACQUISITION_VERIFIED'
    
    # Step 4: Tamper with artifact - extraction/read must fail
    with open(artifact_path, 'w') as f:
        f.write("<html><body>TAMPERED - price changed to ฿999,000</body></html>")
    
    with pytest.raises(ProvenanceError) as exc_info:
        AcquisitionReader.read(artifact_path)
    
    assert "SHA-256 mismatch" in str(exc_info.value)
    
    # Also verify get_provenance_for_fixture fails on tampered artifact
    with pytest.raises(ProvenanceError):
        get_provenance_for_fixture(artifact_path)


def test_provenance_state_acquisition_verified(tmp_path):
    """ACQUISITION_VERIFIED only for artifacts with sidecar hash binding."""
    AcquisitionWriter.write(
        content="<html>verified</html>",
        source_url="https://example.com",
        acquisition_method="http_get",
        output_dir=str(tmp_path),
        filename="verified.html",
        session_id="run_v",
        clock=lambda: "2026-01-15T12:00:00Z",
    )
    
    from thai_factory.acquisition.provenance import get_provenance_for_fixture
    prov = get_provenance_for_fixture(str(tmp_path / "verified.html"))
    
    assert prov['provenance_state'] == 'ACQUISITION_VERIFIED'
    assert not prov.get('legacy', False)


def test_provenance_state_legacy_unverified(tmp_path):
    """LEGACY_UNVERIFIED for fixtures without sidecar (even if in manifest)."""
    # Create artifact without sidecar
    artifact_path = tmp_path / "legacy.html"
    with open(artifact_path, 'w') as f:
        f.write("<html>legacy fixture</html>")
    
    # Create legacy manifest WITH timestamp
    manifest_path = tmp_path / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump({"legacy.html": {"captured_at": "2025-01-01T00:00:00Z"}}, f)
    
    from thai_factory.acquisition.provenance import get_provenance_for_fixture
    prov = get_provenance_for_fixture(
        str(artifact_path),
        legacy_manifest_path=str(manifest_path),
    )
    
    # Must be LEGACY_UNVERIFIED (no hash binding)
    assert prov['provenance_state'] == 'LEGACY_UNVERIFIED'
    assert prov['legacy'] == True
    # Timestamp retained from manifest, but state is unverified
    assert prov['captured_at'] == "2025-01-01T00:00:00Z"


def test_legacy_without_manifest_is_unknown(tmp_path):
    """Fixtures with no manifest entry must have captured_at=UNKNOWN."""
    artifact_path = tmp_path / "no_manifest.html"
    with open(artifact_path, 'w') as f:
        f.write("<html>no manifest</html>")
    
    # Empty manifest
    manifest_path = tmp_path / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump({}, f)
    
    from thai_factory.acquisition.provenance import get_provenance_for_fixture
    prov = get_provenance_for_fixture(
        str(artifact_path),
        legacy_manifest_path=str(manifest_path),
    )
    
    assert prov['captured_at'] == 'UNKNOWN'
    assert prov['provenance_state'] == 'LEGACY_UNVERIFIED'


# ─── Credential Guard Tests (secret-scanning remediation) ───

def test_writer_redacts_incidental_credentials(tmp_path):
    """AcquisitionWriter must redact Google API keys BEFORE hashing/writing."""
    fake_key = "AIza" + "0" * 35  # syntactically valid Google API key shape, fake value
    content = f'<html><script>const cfg = {{"apiKey": "{fake_key}"}};</script></html>'

    prov = AcquisitionWriter.write(
        content=content,
        source_url="https://example.com/leaky",
        acquisition_method="playwright",
        output_dir=str(tmp_path),
        filename="leaky.html",
        session_id="sec_test_001",
        clock=lambda: "2026-01-15T12:00:00Z",
    )

    stored = open(tmp_path / "leaky.html", encoding="utf-8").read()
    assert fake_key not in stored, "credential leaked into stored artifact"
    assert "[REDACTED:google_api_key]" in stored
    # sha256 binds the sanitized bytes actually on disk
    import hashlib as _hl
    assert prov["sha256"] == _hl.sha256(stored.encode("utf-8")).hexdigest()
    # sanitization disclosed in sidecar
    assert prov.get("sanitized") is True
    assert prov["sanitizations"][0]["pattern"] == "google_api_key"
    assert prov["sanitizations"][0]["count"] == 1
    # fail-closed reader still accepts (hash consistent with stored file)
    read_content, read_prov = AcquisitionReader.read(str(tmp_path / "leaky.html"))
    assert fake_key not in read_content
    assert read_prov["sha256"] == prov["sha256"]


def test_fixture_tree_contains_no_credentials():
    """Committed OEM fixtures must never contain credential material."""
    import re as _re
    patterns = [
        _re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
        _re.compile(r"GOCSPX-[0-9A-Za-z_-]{30,}"),
        _re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ]
    fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures", "oem-artifacts")
    offenders = []
    for root, _dirs, files in os.walk(fixture_dir):
        for name in files:
            path = os.path.join(root, name)
            try:
                txt = open(path, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            for pat in patterns:
                if pat.search(txt):
                    offenders.append(f"{name}:{pat.pattern}")
    assert not offenders, f"credential material in fixtures: {offenders}"


def test_sanitize_credentials_function():
    from thai_factory.acquisition.provenance import sanitize_credentials
    fake_key = "AIza" + "1" * 35
    content, notes = sanitize_credentials(f"key={fake_key}; GOCSPX-{'A'*40} end")
    assert fake_key not in content and "GOCSPX-" not in content
    assert [n["pattern"] for n in notes] == ["google_api_key", "google_oauth_token"]
