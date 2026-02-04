"""
Tests for Incident Response Collector (CC7).

Tests collection of incident and resolution evidence.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from phoenix_guardian.compliance.incident_response_collector import (
    IncidentResponseCollector,
)
from phoenix_guardian.compliance.evidence_types import (
    IncidentEvidence,
    ResolutionEvidence,
    TSCCriterion,
)


@pytest.fixture
def collector():
    """Create a test collector instance."""
    return IncidentResponseCollector()


class TestIncidentResponseCollector:
    """Tests for incident response evidence collection."""

    @pytest.mark.asyncio
    async def test_collect_incident_evidence(self, collector):
        """Test collecting evidence for a security incident."""
        incident_data = {
            "incident_id": "INC-2024-001",
            "incident_type": "unauthorized_access",
            "severity": "high",
            "detected_at": datetime.now().isoformat(),
            "description": "Unauthorized access attempt detected",
            "affected_systems": ["api-gateway", "auth-service"],
        }
        
        evidence = await collector.collect_incident_evidence(incident_data)
        
        assert evidence is not None
        assert isinstance(evidence, IncidentEvidence)
        assert evidence.incident_id == "INC-2024-001"
        assert evidence.criterion == TSCCriterion.CC7

    @pytest.mark.asyncio
    async def test_collect_resolution_evidence(self, collector):
        """Test collecting evidence for incident resolution."""
        resolution_data = {
            "incident_id": "INC-2024-001",
            "resolution_type": "access_revoked",
            "resolved_at": datetime.now().isoformat(),
            "root_cause": "Compromised API key",
            "remediation_steps": [
                "Revoked compromised API key",
                "Rotated all related credentials",
                "Updated access policies",
            ],
            "prevented_future_occurrence": True,
        }
        
        evidence = await collector.collect_resolution_evidence(resolution_data)
        
        assert evidence is not None
        assert isinstance(evidence, ResolutionEvidence)
        assert evidence.incident_id == "INC-2024-001"

    @pytest.mark.asyncio
    async def test_evidence_chain_integrity(self, collector):
        """Test that evidence chain maintains integrity."""
        incident_data = {
            "incident_id": "INC-2024-002",
            "incident_type": "data_breach_attempt",
            "severity": "critical",
            "detected_at": datetime.now().isoformat(),
        }
        
        # Collect incident evidence
        incident_evidence = await collector.collect_incident_evidence(incident_data)
        
        # Verify evidence has integrity hash
        assert hasattr(incident_evidence, "integrity_hash")
        assert incident_evidence.integrity_hash is not None

    @pytest.mark.asyncio
    async def test_timeline_tracking(self, collector):
        """Test incident timeline is properly tracked."""
        incident_id = "INC-2024-003"
        
        # Add timeline events
        await collector.add_timeline_event(
            incident_id=incident_id,
            event_type="detection",
            description="Anomaly detected by ML model",
        )
        
        await collector.add_timeline_event(
            incident_id=incident_id,
            event_type="investigation",
            description="Security team notified",
        )
        
        await collector.add_timeline_event(
            incident_id=incident_id,
            event_type="containment",
            description="Affected systems isolated",
        )
        
        timeline = await collector.get_incident_timeline(incident_id)
        
        assert len(timeline) == 3
        assert timeline[0]["event_type"] == "detection"
        assert timeline[-1]["event_type"] == "containment"
