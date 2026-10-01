"""
Gold Set Tests — 10 deliberately chosen end-to-end test cases.

Each test creates evidence packets and runs them through the acceptance runner.
Expected behavior is deterministic and independently auditable.
"""
import pytest
import os
import json
import tempfile
from datetime import datetime

# Add parent directory to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from thai_factory.acceptance.evidence_packet import (
    EvidencePacket, EvidenceClass, AcceptanceDecision,
    CurrentnessState, ExtractionConfidence, EvidenceLocator, ArtifactHash
)
from thai_factory.acceptance.runner import AcceptanceRunner
from thai_factory.acceptance.ledger import AcceptanceLedger


def make_packet(
    packet_id: str,
    candidate_key: str,
    source_class: EvidenceClass,
    source_url: str,
    source_name: str,
    extracted_value: dict,
    confidence: ExtractionConfidence = ExtractionConfidence.MEDIUM,
    currentness: CurrentnessState = CurrentnessState.CURRENT,
    has_locator: bool = True,
    native_id: str = None,
    immutable_revision: str = None,
) -> EvidencePacket:
    """Helper to create evidence packets."""
    return EvidencePacket(
        packet_id=packet_id,
        candidate_key=candidate_key,
        source_class=source_class,
        source_url=source_url,
        source_name=source_name,
        native_id=native_id,
        immutable_revision=immutable_revision,
        extracted_value=extracted_value,
        extraction_confidence=confidence,
        currentness=currentness,
        evidence_locator=EvidenceLocator(
            artifact_path="audit/test/artifact.json",
            json_path="$.rows[0]",
        ) if has_locator else None,
    )


class TestGoldSet:
    """10 gold set tests for acceptance runner."""
    
    def test_gold_1_toyota_oem_price(self):
        """Gold 1: Toyota official OEM price — should ACCEPT."""
        packet = make_packet(
            packet_id="gold-001",
            candidate_key="toyota:corolla-altis:2024:z-e",
            source_class=EvidenceClass.OEM_OFFICIAL,
            source_url="https://www.toyota.co.th/en/pricelist",
            source_name="Toyota Thailand Official",
            extracted_value={
                "model": "Corolla Altis",
                "variant": "Z-E",
                "price_thb": 999000,
                "currency": "THB",
            },
            confidence=ExtractionConfidence.HIGH,
            native_id="toyota-corolla-altis-z-e-2024",
            immutable_revision="2024-09-22",
        )
        
        runner = AcceptanceRunner()
        decision = runner.evaluate(packet)
        
        assert decision == AcceptanceDecision.ACCEPTED
        assert packet.acceptance_reason == "All acceptance criteria met"
    
    def test_gold_2_honda_oem_price(self):
        """Gold 2: Honda official OEM price — should ACCEPT."""
        packet = make_packet(
            packet_id="gold-002",
            candidate_key="honda:civic:2024:rs",
            source_class=EvidenceClass.OEM_OFFICIAL,
            source_url="https://www.honda.co.th/en/civic",
            source_name="Honda Thailand Official",
            extracted_value={
                "model": "Civic",
                "variant": "RS",
                "price_thb": 1299000,
                "currency": "THB",
            },
            confidence=ExtractionConfidence.HIGH,
            native_id="honda-civic-rs-2024",
        )
        
        runner = AcceptanceRunner()
        decision = runner.evaluate(packet)
        
        assert decision == AcceptanceDecision.ACCEPTED
    
    def test_gold_3_byd_oem_price(self):
        """Gold 3: BYD official OEM price — should ACCEPT."""
        packet = make_packet(
            packet_id="gold-003",
            candidate_key="byd:atto-3:2024:extended",
            source_class=EvidenceClass.OEM_OFFICIAL,
            source_url="https://www.byd.com/th/car/atto-3",
            source_name="BYD Thailand Official",
            extracted_value={
                "model": "Atto 3",
                "variant": "Extended",
                "price_thb": 1199900,
                "currency": "THB",
            },
            confidence=ExtractionConfidence.HIGH,
            native_id="byd-atto3-extended-2024",
        )
        
        runner = AcceptanceRunner()
        decision = runner.evaluate(packet)
        
        assert decision == AcceptanceDecision.ACCEPTED
    
    def test_gold_4_variant_level_price(self):
        """Gold 4: Variant-level price with spec fields — should ACCEPT."""
        packet = make_packet(
            packet_id="gold-004",
            candidate_key="mg:zs:2024:com",
            source_class=EvidenceClass.OEM_OFFICIAL,
            source_url="https://www.mgcars.com/th/zs",
            source_name="MG Thailand Official",
            extracted_value={
                "model": "ZS",
                "variant": "COM",
                "price_thb": 799000,
                "currency": "THB",
                "engine": "1.5L Turbo",
                "power_hp": 160,
                "torque_nm": 230,
                "transmission": "CVT",
            },
            confidence=ExtractionConfidence.HIGH,
            native_id="mg-zs-com-2024",
        )
        
        runner = AcceptanceRunner()
        decision = runner.evaluate(packet)
        
        assert decision == AcceptanceDecision.ACCEPTED
    
    def test_gold_5_stale_current_conflict(self):
        """Gold 5: Stale observation — should REJECT."""
        packet = make_packet(
            packet_id="gold-005",
            candidate_key="toyota:camry:2023:highlander",
            source_class=EvidenceClass.OEM_OFFICIAL,
            source_url="https://www.toyota.co.th/en/pricelist",
            source_name="Toyota Thailand Official",
            extracted_value={
                "model": "Camry",
                "variant": "Highlander",
                "price_thb": 1799000,
                "currency": "THB",
            },
            confidence=ExtractionConfidence.HIGH,
            currentness=CurrentnessState.STALE,
        )
        
        runner = AcceptanceRunner()
        decision = runner.evaluate(packet)
        
        assert decision == AcceptanceDecision.REJECTED
        assert "Stale" in packet.acceptance_reason
    
    def test_gold_6_model_range_vs_trim_msrp(self):
        """Gold 6: Model-range MSRP (not variant-specific) — should QUARANTINE."""
        packet = make_packet(
            packet_id="gold-006",
            candidate_key="honda:hr-v:2024:*",
            source_class=EvidenceClass.MEDIA_DISCOVERY,
            source_url="https://www.headlightmag.com/honda-hr-v-2024",
            source_name="HeadLightMag",
            extracted_value={
                "model": "HR-V",
                "price_range_thb": "999000-1299000",
                "note": "Model range, not variant-specific",
            },
            confidence=ExtractionConfidence.MEDIUM,
            native_id="hlm-12345",
        )
        
        runner = AcceptanceRunner()
        decision = runner.evaluate(packet)
        
        # Media source with MEDIUM confidence → QUARANTINED (not directly promotable)
        assert decision == AcceptanceDecision.QUARANTINED
    
    def test_gold_7_duplicate_rerun(self):
        """Gold 7: Duplicate packet — should ACCEPT (idempotent)."""
        packet = make_packet(
            packet_id="gold-007",
            candidate_key="toyota:corolla-altis:2024:z-e",
            source_class=EvidenceClass.OEM_OFFICIAL,
            source_url="https://www.toyota.co.th/en/pricelist",
            source_name="Toyota Thailand Official",
            extracted_value={
                "model": "Corolla Altis",
                "variant": "Z-E",
                "price_thb": 999000,
            },
            confidence=ExtractionConfidence.HIGH,
        )
        
        runner = AcceptanceRunner()
        
        # First run
        decision1 = runner.evaluate(packet)
        assert decision1 == AcceptanceDecision.ACCEPTED
        
        # Second run (duplicate) — should still ACCEPT
        packet2 = make_packet(
            packet_id="gold-007-dup",
            candidate_key="toyota:corolla-altis:2024:z-e",
            source_class=EvidenceClass.OEM_OFFICIAL,
            source_url="https://www.toyota.co.th/en/pricelist",
            source_name="Toyota Thailand Official",
            extracted_value={
                "model": "Corolla Altis",
                "variant": "Z-E",
                "price_thb": 999000,
            },
            confidence=ExtractionConfidence.HIGH,
        )
        decision2 = runner.evaluate(packet2)
        assert decision2 == AcceptanceDecision.ACCEPTED
    
    def test_gold_8_cross_model_contamination(self):
        """Gold 8: Cross-model contamination — should QUARANTINE."""
        packet = make_packet(
            packet_id="gold-008",
            candidate_key="toyota:corolla:2024:z-e",
            source_class=EvidenceClass.MEDIA_DISCOVERY,
            source_url="https://www.headlightmag.com/article-123",
            source_name="HeadLightMag",
            extracted_value={
                "model": "Corolla",
                "variant": "Z-E",
                "price_thb": 999000,
                "note": "Article mentions both Corolla and Civic in same paragraph",
                "contamination_flag": True,
            },
            confidence=ExtractionConfidence.MEDIUM,
        )
        
        runner = AcceptanceRunner()
        decision = runner.evaluate(packet)
        
        # Media source with contamination → QUARANTINED
        assert decision == AcceptanceDecision.QUARANTINED
    
    def test_gold_9_multi_source_assembly(self):
        """Gold 9: Multi-source assembly with >=2 source classes — should ACCEPT from OEM."""
        # OEM source (primary)
        oem_packet = make_packet(
            packet_id="gold-009-oem",
            candidate_key="mg:zs:2024:com",
            source_class=EvidenceClass.OEM_OFFICIAL,
            source_url="https://www.mgcars.com/th/zs",
            source_name="MG Thailand Official",
            extracted_value={
                "model": "ZS",
                "variant": "COM",
                "price_thb": 799000,
            },
            confidence=ExtractionConfidence.HIGH,
        )
        
        # Media source (secondary)
        media_packet = make_packet(
            packet_id="gold-009-media",
            candidate_key="mg:zs:2024:com",
            source_class=EvidenceClass.MEDIA_DISCOVERY,
            source_url="https://www.headlightmag.com/mg-zs-review",
            source_name="HeadLightMag",
            extracted_value={
                "model": "ZS",
                "variant": "COM",
                "price_thb": 799000,
                "confirmed": True,
            },
            confidence=ExtractionConfidence.MEDIUM,
        )
        
        runner = AcceptanceRunner()
        
        # OEM should ACCEPT
        oem_decision = runner.evaluate(oem_packet)
        assert oem_decision == AcceptanceDecision.ACCEPTED
        
        # Media should QUARANTINE (not directly promotable)
        media_decision = runner.evaluate(media_packet)
        assert media_decision == AcceptanceDecision.QUARANTINED
    
    def test_gold_10_git_object_mutation(self):
        """Gold 10: Evidence with Git object SHA — should ACCEPT."""
        packet = make_packet(
            packet_id="gold-010",
            candidate_key="byd:atto-3:2024:extended",
            source_class=EvidenceClass.STRUCTURED_REF,
            source_url="https://raw.githubusercontent.com/open-ev-data/.../atto3.json",
            source_name="open-ev-data",
            extracted_value={
                "brand": "BYD",
                "model": "Atto 3",
                "year": 2024,
                "trim_name": "Extended",
            },
            confidence=ExtractionConfidence.HIGH,
            native_id="open-ev-byd-atto3-2024",
            immutable_revision="8edb266da3b2c4424dd031e248468ba5d445da5d",
        )
        packet.artifact_hashes.git_blob_sha = "abc123def456"
        packet.artifact_hashes.upstream_payload_sha256 = "82e3669a24059c25"
        
        runner = AcceptanceRunner()
        decision = runner.evaluate(packet)
        
        # STRUCTURED_REF with HIGH confidence → ACCEPTED
        assert decision == AcceptanceDecision.ACCEPTED
