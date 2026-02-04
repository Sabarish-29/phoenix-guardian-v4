"""
Tests for Access Control Collector (CC6).

Tests collection of authentication, authorization, and access control evidence.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from phoenix_guardian.compliance.access_control_collector import (
    AccessControlCollector,
)
from phoenix_guardian.compliance.evidence_types import (
    AccessLogEvidence,
    AuthenticationEvidence,
    TSCCriterion,
    EvidenceType,
    EvidenceSource,
)


class TestAccessControlCollector:
    """Tests for AccessControlCollector."""
    
    @pytest.fixture
    def collector(self):
        """Create a collector instance."""
        return AccessControlCollector()
    
    def test_control_descriptions_defined(self, collector):
        """Test that control descriptions are defined."""
        assert "authentication" in collector.CONTROL_DESCRIPTIONS
        assert "authorization" in collector.CONTROL_DESCRIPTIONS
        assert "failed_login" in collector.CONTROL_DESCRIPTIONS
    
    @pytest.mark.asyncio
    async def test_collect_returns_list(self, collector):
        """Test collect returns a list of evidence."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        assert isinstance(evidence, list)
        assert len(evidence) > 0
    
    @pytest.mark.asyncio
    async def test_collect_with_tenant_filter(self, collector):
        """Test collection with tenant filter."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59",
            tenant_id="tenant_001"
        )
        
        # All evidence should have tenant_id set
        for e in evidence:
            assert e.tenant_id == "tenant_001"
    
    @pytest.mark.asyncio
    async def test_authentication_events_collected(self, collector):
        """Test authentication events are collected."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        auth_events = [
            e for e in evidence
            if e.evidence_type == EvidenceType.AUTHENTICATION_EVENT
        ]
        
        assert len(auth_events) > 0
    
    @pytest.mark.asyncio
    async def test_authorization_events_collected(self, collector):
        """Test authorization events are collected."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        authz_events = [
            e for e in evidence
            if e.evidence_type == EvidenceType.AUTHORIZATION_CHECK
        ]
        
        assert len(authz_events) > 0
    
    @pytest.mark.asyncio
    async def test_failed_logins_collected(self, collector):
        """Test failed login attempts are collected."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        # Find failed logins
        failed_logins = [
            e for e in evidence
            if isinstance(e, AuthenticationEvidence) and not e.success
        ]
        
        assert len(failed_logins) > 0
    
    @pytest.mark.asyncio
    async def test_evidence_has_correct_tsc(self, collector):
        """Test evidence is mapped to CC6."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        for e in evidence:
            assert TSCCriterion.CC6_LOGICAL_ACCESS in e.tsc_criteria
    
    @pytest.mark.asyncio
    async def test_evidence_has_data_hash(self, collector):
        """Test evidence has computed hash."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        for e in evidence:
            assert e.data_hash is not None
            assert len(e.data_hash) == 64  # SHA-256 hex
    
    @pytest.mark.asyncio
    async def test_evidence_integrity_verifies(self, collector):
        """Test evidence integrity verification passes."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        for e in evidence:
            assert e.verify_integrity() is True
    
    @pytest.mark.asyncio
    async def test_authentication_event_has_user_id(self, collector):
        """Test authentication events have user_id."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        auth_events = [
            e for e in evidence
            if isinstance(e, AuthenticationEvidence)
        ]
        
        for e in auth_events:
            assert e.user_id is not None
    
    @pytest.mark.asyncio
    async def test_authentication_event_has_mfa_type(self, collector):
        """Test successful auth events have MFA type."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        successful_auths = [
            e for e in evidence
            if isinstance(e, AuthenticationEvidence) and e.success
        ]
        
        for e in successful_auths:
            assert e.mfa_type is not None
    
    @pytest.mark.asyncio
    async def test_access_log_has_resource(self, collector):
        """Test access logs have resource accessed."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        access_logs = [
            e for e in evidence
            if isinstance(e, AccessLogEvidence)
        ]
        
        for e in access_logs:
            assert e.resource_accessed is not None
    
    @pytest.mark.asyncio
    async def test_collect_mfa_enrollment(self, collector):
        """Test MFA enrollment statistics."""
        stats = await collector.collect_mfa_enrollment()
        
        assert "total_users" in stats
        assert "mfa_enrolled" in stats
        assert "mfa_percentage" in stats
        assert stats["mfa_percentage"] > 95  # Should be high
    
    @pytest.mark.asyncio
    async def test_evidence_source_is_correct(self, collector):
        """Test evidence source is set correctly."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        for e in evidence:
            assert e.evidence_source in [
                EvidenceSource.APPLICATION_LOG,
                EvidenceSource.DATABASE_AUDIT_LOG,
                EvidenceSource.MANUAL_UPLOAD,
            ]
    
    @pytest.mark.asyncio
    async def test_control_description_is_set(self, collector):
        """Test control descriptions are set."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        for e in evidence:
            assert e.control_description is not None
            assert len(e.control_description) > 20
    
    @pytest.mark.asyncio
    async def test_timestamps_are_valid(self, collector):
        """Test timestamps are valid ISO format."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        for e in evidence:
            # Should not raise
            datetime.fromisoformat(e.collected_at)
            datetime.fromisoformat(e.event_timestamp)
