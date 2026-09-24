#!/usr/bin/env python3
"""
Acquisition-side provenance: capture-time records, cryptographic binding, boundary tests.

Core principle: provenance is created AT CAPTURE TIME, not retrofitted.
The acquisition writer emits captured_at + sha256 together with the artifact.
The reader verifies the hash binding before any extraction.
"""
import json
import hashlib
import os
from datetime import datetime, timezone
from typing import Optional, Tuple, Callable


class ProvenanceError(Exception):
    """Raised when provenance verification fails (hash mismatch, missing sidecar)."""


class AcquisitionWriter:
    """Writes artifact + provenance sidecar together at capture time."""
    
    @staticmethod
    def write(
        content: str,
        source_url: str,
        acquisition_method: str,
        output_dir: str,
        filename: str,
        session_id: str,
        clock: Optional[Callable[[], str]] = None,
    ) -> dict:
        """
        Write artifact and provenance sidecar as a pair.
        
        Args:
            content: Raw HTML/content to store
            source_url: Exact URL fetched
            acquisition_method: e.g., "playwright", "http_get"
            output_dir: Directory for artifacts
            filename: Artifact filename (e.g., "toyota_page.html")
            session_id: Acquisition run identifier
            clock: Callable returning datetime (for testing; defaults to utcnow)
            
        Returns:
            Provenance record dict (also written to sidecar)
        
        Raises:
            ValueError if clock returns invalid time
        """
        # Capture time from runtime clock AT THIS MOMENT
        if clock is None:
            captured_at = datetime.now(timezone.utc).isoformat()
        else:
            captured_at = clock()
            if not isinstance(captured_at, str):
                raise ValueError(f"clock must return ISO string, got {type(captured_at)}")
        
        # Compute SHA-256 of content
        content_bytes = content.encode('utf-8')
        sha256 = hashlib.sha256(content_bytes).hexdigest()
        
        # Write artifact
        os.makedirs(output_dir, exist_ok=True)
        artifact_path = os.path.join(output_dir, filename)
        with open(artifact_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Write provenance sidecar (same basename + .prov.json)
        sidecar_path = artifact_path + '.prov.json'
        provenance = {
            "source_url": source_url,
            "captured_at": captured_at,
            "acquisition_method": acquisition_method,
            "sha256": sha256,
            "session_id": session_id,
            "artifact_filename": filename,
            "provenance_state": "ACQUISITION_VERIFIED",
        }
        with open(sidecar_path, 'w', encoding='utf-8') as f:
            json.dump(provenance, f, indent=2, ensure_ascii=False)
        
        return provenance


class AcquisitionReader:
    """Reads artifact + verifies cryptographic binding to provenance."""
    
    @staticmethod
    def read(artifact_path: str) -> Tuple[str, dict]:
        """
        Read artifact and verify SHA-256 matches sidecar.
        
        Args:
            artifact_path: Path to artifact file
            
        Returns:
            Tuple of (content, provenance_dict)
            
        Raises:
            ProvenanceError: If sidecar missing or SHA-256 mismatch
        """
        # Check artifact exists
        if not os.path.exists(artifact_path):
            raise ProvenanceError(f"Artifact not found: {artifact_path}")
        
        # Check sidecar exists
        sidecar_path = artifact_path + '.prov.json'
        if not os.path.exists(sidecar_path):
            raise ProvenanceError(f"Provenance sidecar not found: {sidecar_path}")
        
        # Read provenance
        with open(sidecar_path, 'r', encoding='utf-8') as f:
            provenance = json.load(f)
        
        # Read artifact content
        with open(artifact_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify SHA-256 binding
        actual_sha256 = hashlib.sha256(content.encode('utf-8')).hexdigest()
        expected_sha256 = provenance.get('sha256')
        
        if not expected_sha256:
            raise ProvenanceError(f"Provenance missing sha256 field: {sidecar_path}")
        
        if actual_sha256 != expected_sha256:
            raise ProvenanceError(
                f"SHA-256 mismatch for {artifact_path}: "
                f"expected {expected_sha256}, got {actual_sha256}"
            )
        
        # Verify required fields
        required = ['source_url', 'captured_at', 'acquisition_method', 'session_id']
        for field in required:
            if field not in provenance or not provenance[field]:
                raise ProvenanceError(f"Provenance missing required field '{field}': {sidecar_path}")
        
        return content, provenance


class LegacyManifestReader:
    """
    Reads legacy manifest (acquisition_manifest.json) for historical fixtures.
    
    Only used for fixtures WITHOUT acquisition-time sidecars.
    Returns captured_at=None (UNKNOWN) if not in manifest or manifest value is None.
    """
    
    def __init__(self, manifest_path: str):
        self.manifest_path = manifest_path
        self._manifest = None
    
    def _load(self) -> dict:
        if self._manifest is None:
            if os.path.exists(self.manifest_path):
                with open(self.manifest_path, 'r', encoding='utf-8') as f:
                    self._manifest = json.load(f)
            else:
                self._manifest = {}
        return self._manifest
    
    def get_provenance(self, filename: str) -> dict:
        """
        Get provenance for a legacy fixture.
        
        Returns dict with captured_at (or None for UNKNOWN), source_url, etc.
        Does NOT include sha256 verification (legacy fixtures have no sidecar).
        """
        manifest = self._load()
        entry = manifest.get(filename, {})
        
        captured_at = entry.get('captured_at')
        # Treat empty string as UNKNOWN
        if captured_at == '':
            captured_at = None
        
        # If no real acquisition record, captured_at must be UNKNOWN
        # Only retain if manifest has explicit non-empty captured_at
        if not captured_at:
            captured_at = 'UNKNOWN'
            provenance_state = 'LEGACY_UNVERIFIED'
        else:
            provenance_state = 'LEGACY_UNVERIFIED'  # Still unverified - no hash binding
        
        return {
            "source_url": entry.get('source_url', 'UNKNOWN'),
            "captured_at": captured_at,
            "acquisition_method": entry.get('acquisition_method', 'UNKNOWN'),
            "session_id": entry.get('session_context', 'UNKNOWN'),
            "sha256": entry.get('sha256'),  # Present but not verified
            "artifact_filename": filename,
            "provenance_state": provenance_state,
            "legacy": True,
        }


def get_provenance_for_fixture(
    artifact_path: str,
    legacy_manifest_path: Optional[str] = None,
) -> dict:
    """
    Unified provenance getter: prefer sidecar, fallback to legacy manifest.
    
    Returns provenance dict with captured_at, source_url, etc.
    Raises ProvenanceError if sidecar exists but hash mismatches.
    """
    filename = os.path.basename(artifact_path)
    sidecar_path = artifact_path + '.prov.json'
    
    # Prefer acquisition-time sidecar (cryptographically verified)
    if os.path.exists(sidecar_path):
        _, provenance = AcquisitionReader.read(artifact_path)
        return provenance
    
    # Fallback to legacy manifest (no hash verification)
    if legacy_manifest_path and os.path.exists(legacy_manifest_path):
        reader = LegacyManifestReader(legacy_manifest_path)
        return reader.get_provenance(filename)
    
    # No provenance available
    return {
        "source_url": 'UNKNOWN',
        "captured_at": 'UNKNOWN',
        "acquisition_method": 'UNKNOWN',
        "session_id": 'UNKNOWN',
        "sha256": None,
        "artifact_filename": filename,
        "provenance_state": "LEGACY_UNVERIFIED",
        "legacy": True,
    }
