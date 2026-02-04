"""
End-to-end tests for SOC 2 Compliance Automation.

Tests the complete workflow from evidence collection through
audit package generation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from phoenix_guardian.compliance import (
    SOC2EvidenceCollector,
    EvidenceValidator,
    AuditPackageGenerator,
    GapAnalyzer,
    TSCCriterion,
    EvidenceType,
)


class TestSOC2EndToEnd:
    """End-to-end tests for SOC 2 automation."""
    
    @pytest.fixture
    def collector(self):
        """Create a collector instance."""
        return SOC2EvidenceCollector()
    
    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return EvidenceValidator()
    
    @pytest.fixture
    def generator(self):
        """Create a generator instance."""
        return AuditPackageGenerator()
    
    @pytest.fixture
    def gap_analyzer(self):
        """Create a gap analyzer instance."""
        return GapAnalyzer()
    
    @pytest.mark.asyncio
    async def test_full_evidence_collection_workflow(self, collector):
        """Test complete evidence collection workflow."""
        # Collect evidence for 30-day period
        result = await collector.collect_all(
            start_date="2026-01-01T00:00:00",
            end_date="2026-01-31T23:59:59"
        )
        
        # Verify collection succeeded
        assert result.success is True
        assert result.total_evidence_count > 0
        
        # Verify TSC coverage
        assert TSCCriterion.CC6_LOGICAL_ACCESS in result.evidence_by_tsc
        assert TSCCriterion.CC8_CHANGE_MANAGEMENT in result.evidence_by_tsc
    
    @pytest.mark.asyncio
    async def test_collection_and_validation(self, collector, validator):
        """Test evidence collection followed by validation."""
        # Collect
        collection_result = await collector.collect_all(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        # Validate
        validation_result = validator.validate(collection_result.evidence_items)
        
        # All collected evidence should be valid
        assert validation_result.valid_count == len(collection_result.evidence_items)
    
    @pytest.mark.asyncio
    async def test_collection_validation_and_packaging(
        self, collector, validator, generator
    ):
        """Test complete workflow: collect -> validate -> package."""
        # Collect
        collection_result = await collector.collect_all(
            "2025-07-01T00:00:00",
            "2025-12-31T23:59:59"
        )
        
        # Generate package (includes validation)
        package = generator.generate(
            collection_result.evidence_items,
            audit_period_start="2025-07-01",
            audit_period_end="2025-12-31",
            validate=True
        )
        
        # Verify package
        assert package.total_evidence == len(collection_result.evidence_items)
        assert package.validation_result is not None
        assert package.manifest_hash is not None
    
    @pytest.mark.asyncio
    async def test_gap_analysis_on_collected_evidence(
        self, collector, gap_analyzer
    ):
        """Test gap analysis on collected evidence."""
        # Collect
        collection_result = await collector.collect_all(
            "2025-07-01T00:00:00",
            "2025-12-31T23:59:59"
        )
        
        # Analyze gaps
        gap_result = gap_analyzer.analyze(
            collection_result.evidence_items,
            audit_period_start="2025-07-01",
            audit_period_end="2025-12-31"
        )
        
        # Should have good coverage
        assert gap_result.tsc_coverage["CC6"] is True
        assert gap_result.tsc_coverage["CC8"] is True
    
    @pytest.mark.asyncio
    async def test_incremental_collection(self, collector):
        """Test incremental evidence collection."""
        # Initial collection
        first_result = await collector.collect_all(
            "2026-01-01T00:00:00",
            "2026-01-15T23:59:59"
        )
        
        # Incremental collection
        second_result = await collector.collect_incremental(
            since="2026-01-15T00:00:00"
        )
        
        # Both should succeed
        assert first_result.success
        assert second_result.success
    
    @pytest.mark.asyncio
    async def test_multi_tenant_collection(self, collector):
        """Test evidence collection for specific tenant."""
        result = await collector.collect_all(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59",
            tenant_id="tenant_enterprise_001"
        )
        
        # All evidence should be for tenant
        for evidence in result.evidence_items:
            if evidence.tenant_id is not None:
                assert evidence.tenant_id == "tenant_enterprise_001"
    
    @pytest.mark.asyncio
    async def test_audit_package_index_generation(
        self, collector, generator
    ):
        """Test audit package index generation."""
        # Collect
        result = await collector.collect_all(
            "2025-07-01T00:00:00",
            "2025-12-31T23:59:59"
        )
        
        # Generate package
        package = generator.generate(
            result.evidence_items,
            "2025-07-01",
            "2025-12-31"
        )
        
        # Generate index
        index = generator.generate_index(package)
        
        # Verify index structure
        assert "summary" in index
        assert "sections" in index
        assert len(index["sections"]) == 9  # All TSC criteria
    
    @pytest.mark.asyncio
    async def test_remediation_plan_generation(
        self, collector, gap_analyzer
    ):
        """Test remediation plan generation."""
        # Collect
        result = await collector.collect_all(
            "2025-07-01T00:00:00",
            "2025-12-31T23:59:59"
        )
        
        # Analyze gaps
        gap_result = gap_analyzer.analyze(
            result.evidence_items,
            "2025-07-01",
            "2025-12-31"
        )
        
        # Generate remediation plan
        plan = gap_analyzer.generate_remediation_plan(gap_result)
        
        # Verify plan structure
        assert "priority_actions" in plan
        assert "detailed_actions" in plan
    
    def test_evidence_integrity_chain(self, validator):
        """Test evidence integrity verification."""
        from phoenix_guardian.compliance.evidence_types import Evidence, EvidenceSource
        
        # Create evidence
        evidence = Evidence(
            evidence_id="test_001",
            evidence_type=EvidenceType.ACCESS_LOG,
            evidence_source=EvidenceSource.APPLICATION_LOG,
            tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
            control_description="Test control for integrity verification",
            collected_at=datetime.now().isoformat(),
            event_timestamp=(datetime.now() - timedelta(hours=1)).isoformat(),
            data_hash="",
            data={"user": "test", "action": "login"},
        )
        evidence.data_hash = evidence.compute_hash()
        
        # Validate
        result = validator.validate([evidence])
        
        # Should pass
        assert result.valid_count == 1
        assert evidence.verify_integrity() is True
        
        # Tamper with data
        evidence.data["action"] = "logout"
        
        # Should now fail integrity
        assert evidence.verify_integrity() is False
    
    @pytest.mark.asyncio
    async def test_collection_statistics(self, collector):
        """Test collection statistics generation."""
        # Collect
        await collector.collect_all(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        # Get statistics
        stats = collector.get_collection_statistics(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        # Verify stats
        assert "total_evidence" in stats
        assert "by_tsc_criterion" in stats
        assert "by_evidence_type" in stats
    
    @pytest.mark.asyncio
    async def test_tsc_specific_collection(self, collector):
        """Test collecting evidence for specific TSC."""
        # Collect only CC6 evidence
        evidence = await collector.collect_by_tsc(
            TSCCriterion.CC6_LOGICAL_ACCESS,
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        # All should be CC6
        for e in evidence:
            assert TSCCriterion.CC6_LOGICAL_ACCESS in e.tsc_criteria
    
    @pytest.mark.asyncio
    async def test_summary_report_generation(
        self, collector, generator
    ):
        """Test summary report generation."""
        # Collect
        result = await collector.collect_all(
            "2025-07-01T00:00:00",
            "2025-12-31T23:59:59"
        )
        
        # Generate package
        package = generator.generate(
            result.evidence_items,
            "2025-07-01",
            "2025-12-31"
        )
        
        # Generate summary
        summary = generator.generate_summary_report(package)
        
        # Verify summary
        assert summary["report_type"] == "SOC 2 Type II Evidence Summary"
        assert "evidence_summary" in summary
        assert "validation_summary" in summary
        assert "integrity" in summary
