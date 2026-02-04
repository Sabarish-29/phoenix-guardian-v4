"""
Tests for Risk Assessment Collector (CC3).

Tests collection of vulnerability scan and penetration test evidence.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from phoenix_guardian.compliance.risk_assessment_collector import (
    RiskAssessmentCollector,
)
from phoenix_guardian.compliance.evidence_types import (
    VulnerabilityScanEvidence,
    PenetrationTestEvidence,
    TSCCriterion,
    EvidenceType,
    EvidenceSource,
)


class TestRiskAssessmentCollector:
    """Tests for RiskAssessmentCollector."""
    
    @pytest.fixture
    def collector(self):
        """Create a collector instance."""
        return RiskAssessmentCollector()
    
    def test_control_descriptions_defined(self, collector):
        """Test that control descriptions are defined."""
        assert "vulnerability_scan" in collector.CONTROL_DESCRIPTIONS
        assert "penetration_test" in collector.CONTROL_DESCRIPTIONS
        assert "security_assessment" in collector.CONTROL_DESCRIPTIONS
    
    def test_remediation_sla_defined(self, collector):
        """Test remediation SLA is defined by severity."""
        assert "critical" in collector.REMEDIATION_SLA_DAYS
        assert "high" in collector.REMEDIATION_SLA_DAYS
        assert collector.REMEDIATION_SLA_DAYS["critical"] == 7
    
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
    async def test_vulnerability_scans_collected(self, collector):
        """Test vulnerability scans are collected."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        scans = [
            e for e in evidence
            if e.evidence_type == EvidenceType.VULNERABILITY_SCAN
        ]
        
        assert len(scans) > 0
    
    @pytest.mark.asyncio
    async def test_penetration_tests_collected(self, collector):
        """Test penetration tests are collected."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        pentests = [
            e for e in evidence
            if e.evidence_type == EvidenceType.PENETRATION_TEST
        ]
        
        assert len(pentests) > 0
    
    @pytest.mark.asyncio
    async def test_evidence_has_correct_tsc(self, collector):
        """Test evidence is mapped to CC3."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        for e in evidence:
            assert TSCCriterion.CC3_RISK_ASSESSMENT in e.tsc_criteria
    
    @pytest.mark.asyncio
    async def test_vuln_scan_has_counts(self, collector):
        """Test vulnerability scans have severity counts."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        scans = [
            e for e in evidence
            if isinstance(e, VulnerabilityScanEvidence)
        ]
        
        for s in scans:
            assert s.critical_count >= 0
            assert s.high_count >= 0
            assert s.medium_count >= 0
            assert s.low_count >= 0
    
    @pytest.mark.asyncio
    async def test_vuln_scan_has_scanner_name(self, collector):
        """Test vulnerability scans have scanner name."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        scans = [
            e for e in evidence
            if isinstance(e, VulnerabilityScanEvidence)
        ]
        
        for s in scans:
            assert s.scanner_name in ["trivy", "snyk"]
    
    @pytest.mark.asyncio
    async def test_pentest_has_tester_name(self, collector):
        """Test penetration tests have tester name."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        pentests = [
            e for e in evidence
            if isinstance(e, PenetrationTestEvidence)
        ]
        
        for p in pentests:
            assert p.tester_name is not None
    
    @pytest.mark.asyncio
    async def test_pentest_has_scope(self, collector):
        """Test penetration tests have scope."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        pentests = [
            e for e in evidence
            if isinstance(e, PenetrationTestEvidence)
        ]
        
        for p in pentests:
            assert p.test_scope is not None
    
    @pytest.mark.asyncio
    async def test_pentest_has_dates(self, collector):
        """Test penetration tests have test dates."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        pentests = [
            e for e in evidence
            if isinstance(e, PenetrationTestEvidence)
        ]
        
        for p in pentests:
            assert p.test_start_date is not None
            assert p.test_end_date is not None
    
    @pytest.mark.asyncio
    async def test_get_vulnerability_summary(self, collector):
        """Test vulnerability summary statistics."""
        summary = await collector.get_vulnerability_summary(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        assert "scans_performed" in summary
        assert "total_vulnerabilities" in summary
        assert "by_severity" in summary
        assert "remediated" in summary
    
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
    async def test_multiple_scanners_used(self, collector):
        """Test multiple scanners are used."""
        evidence = await collector.collect(
            "2026-01-01T00:00:00",
            "2026-01-31T23:59:59"
        )
        
        scans = [
            e for e in evidence
            if isinstance(e, VulnerabilityScanEvidence)
        ]
        
        scanners = set(s.scanner_name for s in scans)
        assert len(scanners) >= 2
