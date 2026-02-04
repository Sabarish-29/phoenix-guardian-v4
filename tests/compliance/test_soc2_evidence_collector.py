"""
Tests for SOC 2 Evidence Collector.

Tests the main orchestrator that coordinates evidence collection.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from phoenix_guardian.compliance.soc2_evidence_collector import (
    SOC2EvidenceCollector,
    EvidenceCollectionResult,
    CollectionFrequency,
)
from phoenix_guardian.compliance.evidence_types import (
    Evidence,
    EvidenceType,
    EvidenceSource,
    TSCCriterion,
)


class TestEvidenceCollectionResult:
    """Tests for EvidenceCollectionResult dataclass."""
    
    def test_total_evidence_count(self):
        """Test total evidence count property."""
        result = EvidenceCollectionResult(
            collection_id="test_001",
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            evidence_items=[MagicMock()] * 10,
            evidence_by_tsc={},
            evidence_by_type={},
        )
        assert result.total_evidence_count == 10
    
    def test_success_with_no_errors(self):
        """Test success is True when no errors."""
        result = EvidenceCollectionResult(
            collection_id="test_001",
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            evidence_items=[],
            evidence_by_tsc={},
            evidence_by_type={},
            errors=[],
        )
        assert result.success is True
    
    def test_success_with_errors(self):
        """Test success is False when errors present."""
        result = EvidenceCollectionResult(
            collection_id="test_001",
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            evidence_items=[],
            evidence_by_tsc={},
            evidence_by_type={},
            errors=["An error occurred"],
        )
        assert result.success is False
    
    def test_duration_seconds(self):
        """Test duration calculation."""
        start = datetime.now()
        end = start + timedelta(seconds=30)
        
        result = EvidenceCollectionResult(
            collection_id="test_001",
            started_at=start.isoformat(),
            completed_at=end.isoformat(),
            evidence_items=[],
            evidence_by_tsc={},
            evidence_by_type={},
        )
        assert result.duration_seconds == 30.0
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = EvidenceCollectionResult(
            collection_id="test_001",
            started_at="2026-01-01T00:00:00",
            completed_at="2026-01-01T00:01:00",
            evidence_items=[],
            evidence_by_tsc={TSCCriterion.CC6_LOGICAL_ACCESS: 5},
            evidence_by_type={EvidenceType.ACCESS_LOG: 5},
        )
        
        data = result.to_dict()
        
        assert data["collection_id"] == "test_001"
        assert data["success"] is True
        assert "CC6" in data["evidence_by_tsc"]


class TestSOC2EvidenceCollector:
    """Tests for SOC2EvidenceCollector."""
    
    @pytest.fixture
    def collector(self):
        """Create a collector instance."""
        return SOC2EvidenceCollector()
    
    def test_collection_schedule_defined(self, collector):
        """Test collection schedule is properly defined."""
        schedule = collector.COLLECTION_SCHEDULE
        
        assert EvidenceType.ACCESS_LOG in schedule
        assert schedule[EvidenceType.ACCESS_LOG] == CollectionFrequency.CONTINUOUS
        assert schedule[EvidenceType.VULNERABILITY_SCAN] == CollectionFrequency.WEEKLY
    
    def test_retention_months_set(self, collector):
        """Test retention period is set."""
        assert collector.RETENTION_MONTHS == 18
    
    @pytest.mark.asyncio
    async def test_collect_all_basic(self, collector):
        """Test basic evidence collection."""
        start_date = "2026-01-01T00:00:00"
        end_date = "2026-01-31T23:59:59"
        
        result = await collector.collect_all(start_date, end_date)
        
        assert isinstance(result, EvidenceCollectionResult)
        assert result.collection_id.startswith("collection_")
        assert result.total_evidence_count > 0
    
    @pytest.mark.asyncio
    async def test_collect_all_with_tenant(self, collector):
        """Test evidence collection with tenant filter."""
        result = await collector.collect_all(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59",
            tenant_id="tenant_001"
        )
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_collect_incremental(self, collector):
        """Test incremental collection."""
        since = (datetime.now() - timedelta(hours=1)).isoformat()
        
        result = await collector.collect_incremental(since)
        
        assert isinstance(result, EvidenceCollectionResult)
    
    @pytest.mark.asyncio
    async def test_collect_by_tsc_access_control(self, collector):
        """Test collection by specific TSC."""
        evidence = await collector.collect_by_tsc(
            TSCCriterion.CC6_LOGICAL_ACCESS,
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        assert isinstance(evidence, list)
        # All evidence should be for CC6
        for e in evidence:
            assert TSCCriterion.CC6_LOGICAL_ACCESS in e.tsc_criteria
    
    @pytest.mark.asyncio
    async def test_collect_by_tsc_change_management(self, collector):
        """Test collection for CC8."""
        evidence = await collector.collect_by_tsc(
            TSCCriterion.CC8_CHANGE_MANAGEMENT,
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        assert isinstance(evidence, list)
    
    def test_get_evidence_no_filters(self, collector):
        """Test getting evidence without filters."""
        evidence = collector.get_evidence()
        assert isinstance(evidence, list)
    
    def test_get_evidence_with_tsc_filter(self, collector):
        """Test getting evidence with TSC filter."""
        # Add some evidence first
        collector.evidence_store.append(Evidence(
            evidence_id="test_001",
            evidence_type=EvidenceType.ACCESS_LOG,
            evidence_source=EvidenceSource.APPLICATION_LOG,
            tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
            control_description="Test",
            collected_at=datetime.now().isoformat(),
            event_timestamp=datetime.now().isoformat(),
            data_hash="abc123",
        ))
        
        evidence = collector.get_evidence(tsc=TSCCriterion.CC6_LOGICAL_ACCESS)
        
        assert len(evidence) >= 1
    
    def test_get_collection_statistics(self, collector):
        """Test getting collection statistics."""
        start = "2026-01-01T00:00:00"
        end = "2026-01-31T23:59:59"
        
        stats = collector.get_collection_statistics(start, end)
        
        assert "total_evidence" in stats
        assert "by_tsc_criterion" in stats
        assert "by_evidence_type" in stats
    
    def test_get_tsc_coverage(self, collector):
        """Test TSC coverage report."""
        coverage = collector.get_tsc_coverage()
        
        assert TSCCriterion.CC6_LOGICAL_ACCESS in coverage
        assert "evidence_count" in coverage[TSCCriterion.CC6_LOGICAL_ACCESS]
    
    def test_cleanup_old_evidence(self, collector):
        """Test evidence cleanup."""
        # Add old evidence
        old_date = (datetime.now() - timedelta(days=600)).isoformat()
        collector.evidence_store.append(Evidence(
            evidence_id="old_001",
            evidence_type=EvidenceType.ACCESS_LOG,
            evidence_source=EvidenceSource.APPLICATION_LOG,
            tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
            control_description="Old evidence",
            collected_at=old_date,
            event_timestamp=old_date,
            data_hash="abc123",
        ))
        
        removed = collector.cleanup_old_evidence()
        
        assert removed >= 1
    
    @pytest.mark.asyncio
    async def test_evidence_aggregation_by_tsc(self, collector):
        """Test that evidence is aggregated by TSC."""
        result = await collector.collect_all(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        assert len(result.evidence_by_tsc) > 0
        # Should have CC6 evidence
        assert TSCCriterion.CC6_LOGICAL_ACCESS in result.evidence_by_tsc
    
    @pytest.mark.asyncio
    async def test_evidence_aggregation_by_type(self, collector):
        """Test that evidence is aggregated by type."""
        result = await collector.collect_all(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        assert len(result.evidence_by_type) > 0
    
    @pytest.mark.asyncio
    async def test_collection_history_tracked(self, collector):
        """Test that collection history is tracked."""
        await collector.collect_all(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        assert len(collector.collection_history) >= 1
    
    @pytest.mark.asyncio
    async def test_error_handling_in_collection(self, collector):
        """Test that errors are captured gracefully."""
        # Mock a collector to fail
        collector.access_control.collect = AsyncMock(
            side_effect=Exception("Database error")
        )
        
        result = await collector.collect_all(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        # Should still complete, but with errors
        assert "Access control collection failed" in result.errors[0]
