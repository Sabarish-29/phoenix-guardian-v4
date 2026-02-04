"""
Tests for Change Management Collector (CC8).

Tests collection of deployment, code review, and change approval evidence.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from phoenix_guardian.compliance.change_management_collector import (
    ChangeManagementCollector,
)
from phoenix_guardian.compliance.evidence_types import (
    DeploymentEvidence,
    ChangeApprovalEvidence,
    TSCCriterion,
    EvidenceType,
    EvidenceSource,
)


class TestChangeManagementCollector:
    """Tests for ChangeManagementCollector."""
    
    @pytest.fixture
    def collector(self):
        """Create a collector instance."""
        return ChangeManagementCollector()
    
    def test_control_descriptions_defined(self, collector):
        """Test that control descriptions are defined."""
        assert "deployment" in collector.CONTROL_DESCRIPTIONS
        assert "code_review" in collector.CONTROL_DESCRIPTIONS
        assert "testing" in collector.CONTROL_DESCRIPTIONS
        assert "approval" in collector.CONTROL_DESCRIPTIONS
    
    def test_min_reviewers_set(self, collector):
        """Test minimum reviewers is set."""
        assert collector.MIN_REVIEWERS == 2
    
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
    async def test_deployments_collected(self, collector):
        """Test deployment records are collected."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        deployments = [
            e for e in evidence
            if e.evidence_type == EvidenceType.DEPLOYMENT_RECORD
        ]
        
        assert len(deployments) > 0
    
    @pytest.mark.asyncio
    async def test_code_reviews_collected(self, collector):
        """Test code reviews are collected."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        reviews = [
            e for e in evidence
            if e.evidence_type == EvidenceType.CODE_REVIEW
        ]
        
        assert len(reviews) > 0
    
    @pytest.mark.asyncio
    async def test_change_approvals_collected(self, collector):
        """Test change approvals are collected."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        approvals = [
            e for e in evidence
            if e.evidence_type == EvidenceType.CHANGE_APPROVAL
        ]
        
        assert len(approvals) > 0
    
    @pytest.mark.asyncio
    async def test_evidence_has_correct_tsc(self, collector):
        """Test evidence is mapped to CC8."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        for e in evidence:
            assert TSCCriterion.CC8_CHANGE_MANAGEMENT in e.tsc_criteria
    
    @pytest.mark.asyncio
    async def test_deployment_has_commit_sha(self, collector):
        """Test deployments have git commit SHA."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        deployments = [
            e for e in evidence
            if isinstance(e, DeploymentEvidence)
        ]
        
        for d in deployments:
            assert d.git_commit_sha is not None
            assert len(d.git_commit_sha) > 0
    
    @pytest.mark.asyncio
    async def test_deployment_has_approvers(self, collector):
        """Test deployments have approvers."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        deployments = [
            e for e in evidence
            if isinstance(e, DeploymentEvidence)
        ]
        
        for d in deployments:
            assert len(d.approver_ids) >= collector.MIN_REVIEWERS
    
    @pytest.mark.asyncio
    async def test_deployment_tests_passed(self, collector):
        """Test deployments have passing tests."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        deployments = [
            e for e in evidence
            if isinstance(e, DeploymentEvidence)
        ]
        
        for d in deployments:
            assert d.tests_passed is True
    
    @pytest.mark.asyncio
    async def test_evidence_source_is_github(self, collector):
        """Test evidence source is GitHub Actions."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        for e in evidence:
            assert e.evidence_source == EvidenceSource.GITHUB_ACTIONS
    
    @pytest.mark.asyncio
    async def test_change_approval_has_approvers(self, collector):
        """Test change approvals have approvers."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        approvals = [
            e for e in evidence
            if isinstance(e, ChangeApprovalEvidence)
        ]
        
        for a in approvals:
            assert len(a.approver_ids) > 0
    
    @pytest.mark.asyncio
    async def test_change_approval_has_justification(self, collector):
        """Test change approvals have justification."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        approvals = [
            e for e in evidence
            if isinstance(e, ChangeApprovalEvidence)
        ]
        
        for a in approvals:
            assert a.justification is not None
    
    @pytest.mark.asyncio
    async def test_get_deployment_statistics(self, collector):
        """Test deployment statistics."""
        stats = await collector.get_deployment_statistics(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        assert "total_deployments" in stats
        assert "successful_deployments" in stats
        assert "rollbacks" in stats
        assert "deployments_with_approval" in stats
    
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
    async def test_deployment_has_rollback_available(self, collector):
        """Test deployments have rollback option."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        deployments = [
            e for e in evidence
            if isinstance(e, DeploymentEvidence)
        ]
        
        for d in deployments:
            assert d.rollback_available is True
    
    @pytest.mark.asyncio
    async def test_code_review_has_reviewers(self, collector):
        """Test code reviews have reviewers in data."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        reviews = [
            e for e in evidence
            if e.evidence_type == EvidenceType.CODE_REVIEW
        ]
        
        for r in reviews:
            assert "reviewers" in r.data or "approvals" in r.data
