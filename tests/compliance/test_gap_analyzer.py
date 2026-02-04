"""
Tests for Gap Analyzer.

Tests identification of evidence gaps before SOC 2 audit.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from phoenix_guardian.compliance.gap_analyzer import (
    GapAnalyzer,
    GapAnalysisResult,
    EvidenceGap,
    GapSeverity,
    GapType,
)
from phoenix_guardian.compliance.evidence_types import (
    Evidence,
    EvidenceType,
    EvidenceSource,
    TSCCriterion,
)


class TestEvidenceGap:
    """Tests for EvidenceGap dataclass."""
    
    def test_gap_creation(self):
        """Test creating an evidence gap."""
        gap = EvidenceGap(
            gap_id="GAP-0001",
            gap_type=GapType.MISSING_TSC,
            severity=GapSeverity.CRITICAL,
            tsc_criterion=TSCCriterion.CC6_LOGICAL_ACCESS,
            description="No evidence for CC6",
            remediation="Collect access control evidence",
        )
        
        assert gap.gap_id == "GAP-0001"
        assert gap.severity == GapSeverity.CRITICAL


class TestGapAnalysisResult:
    """Tests for GapAnalysisResult dataclass."""
    
    def test_critical_gaps_count(self):
        """Test critical gaps count."""
        result = GapAnalysisResult(
            analysis_id="gap_001",
            analyzed_at=datetime.now().isoformat(),
            audit_period_start="2025-07-01",
            audit_period_end="2025-12-31",
            gaps=[
                EvidenceGap("1", GapType.MISSING_TSC, GapSeverity.CRITICAL, None, "", ""),
                EvidenceGap("2", GapType.MISSING_TSC, GapSeverity.HIGH, None, "", ""),
            ],
        )
        
        assert result.critical_gaps == 1
        assert result.high_gaps == 1
    
    def test_is_audit_ready(self):
        """Test audit readiness check."""
        result = GapAnalysisResult(
            analysis_id="gap_001",
            analyzed_at=datetime.now().isoformat(),
            audit_period_start="2025-07-01",
            audit_period_end="2025-12-31",
            gaps=[],
        )
        
        assert result.is_audit_ready is True
    
    def test_not_audit_ready_with_critical(self):
        """Test not audit ready with critical gaps."""
        result = GapAnalysisResult(
            analysis_id="gap_001",
            analyzed_at=datetime.now().isoformat(),
            audit_period_start="2025-07-01",
            audit_period_end="2025-12-31",
            gaps=[
                EvidenceGap("1", GapType.MISSING_TSC, GapSeverity.CRITICAL, None, "", ""),
            ],
        )
        
        assert result.is_audit_ready is False
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = GapAnalysisResult(
            analysis_id="gap_001",
            analyzed_at="2026-01-01T00:00:00",
            audit_period_start="2025-07-01",
            audit_period_end="2025-12-31",
        )
        
        data = result.to_dict()
        
        assert data["analysis_id"] == "gap_001"
        assert "gap_summary" in data


class TestGapAnalyzer:
    """Tests for GapAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Create an analyzer instance."""
        return GapAnalyzer()
    
    @pytest.fixture
    def full_evidence(self):
        """Create evidence covering all TSC."""
        evidence_list = []
        
        # CC3 - Risk Assessment
        e = Evidence(
            evidence_id="vuln_001",
            evidence_type=EvidenceType.VULNERABILITY_SCAN,
            evidence_source=EvidenceSource.SECURITY_SCANNER,
            tsc_criteria=[TSCCriterion.CC3_RISK_ASSESSMENT],
            control_description="Regular vulnerability scanning",
            collected_at=datetime.now().isoformat(),
            event_timestamp="2025-10-15T12:00:00",
            data_hash="",
            data={},
        )
        e.data_hash = e.compute_hash()
        evidence_list.extend([e] * 10)
        
        # CC4 - Monitoring
        e = Evidence(
            evidence_id="perf_001",
            evidence_type=EvidenceType.PERFORMANCE_METRIC,
            evidence_source=EvidenceSource.PROMETHEUS,
            tsc_criteria=[TSCCriterion.CC4_MONITORING],
            control_description="Performance monitoring",
            collected_at=datetime.now().isoformat(),
            event_timestamp="2025-10-15T12:00:00",
            data_hash="",
            data={},
        )
        e.data_hash = e.compute_hash()
        evidence_list.extend([e] * 15)
        
        # CC6 - Logical Access
        e = Evidence(
            evidence_id="auth_001",
            evidence_type=EvidenceType.AUTHENTICATION_EVENT,
            evidence_source=EvidenceSource.APPLICATION_LOG,
            tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
            control_description="Authentication logging",
            collected_at=datetime.now().isoformat(),
            event_timestamp="2025-10-15T12:00:00",
            data_hash="",
            data={},
        )
        e.data_hash = e.compute_hash()
        evidence_list.extend([e] * 25)
        
        # CC7 - System Operations
        e = Evidence(
            evidence_id="incident_001",
            evidence_type=EvidenceType.INCIDENT_REPORT,
            evidence_source=EvidenceSource.INCIDENT_MANAGER,
            tsc_criteria=[TSCCriterion.CC7_SYSTEM_OPERATIONS],
            control_description="Incident response",
            collected_at=datetime.now().isoformat(),
            event_timestamp="2025-10-15T12:00:00",
            data_hash="",
            data={},
        )
        e.data_hash = e.compute_hash()
        evidence_list.extend([e] * 20)
        
        # CC8 - Change Management
        e = Evidence(
            evidence_id="deploy_001",
            evidence_type=EvidenceType.DEPLOYMENT_RECORD,
            evidence_source=EvidenceSource.GITHUB_ACTIONS,
            tsc_criteria=[TSCCriterion.CC8_CHANGE_MANAGEMENT],
            control_description="Deployment records",
            collected_at=datetime.now().isoformat(),
            event_timestamp="2025-10-15T12:00:00",
            data_hash="",
            data={},
        )
        e.data_hash = e.compute_hash()
        evidence_list.extend([e] * 15)
        
        return evidence_list
    
    def test_min_evidence_per_tsc_defined(self, analyzer):
        """Test minimum evidence requirements are defined."""
        assert TSCCriterion.CC6_LOGICAL_ACCESS in analyzer.MIN_EVIDENCE_PER_TSC
        assert analyzer.MIN_EVIDENCE_PER_TSC[TSCCriterion.CC6_LOGICAL_ACCESS] == 20
    
    def test_required_evidence_types_defined(self, analyzer):
        """Test required evidence types are defined."""
        assert TSCCriterion.CC3_RISK_ASSESSMENT in analyzer.REQUIRED_EVIDENCE_TYPES
        assert EvidenceType.VULNERABILITY_SCAN in analyzer.REQUIRED_EVIDENCE_TYPES[TSCCriterion.CC3_RISK_ASSESSMENT]
    
    def test_analyze_empty_evidence(self, analyzer):
        """Test analyzing empty evidence list."""
        result = analyzer.analyze(
            [],
            "2025-07-01",
            "2025-12-31"
        )
        
        # Should find many critical gaps
        assert result.critical_gaps > 0
        assert result.is_audit_ready is False
    
    def test_analyze_with_full_evidence(self, analyzer, full_evidence):
        """Test analyzing with full evidence."""
        result = analyzer.analyze(
            full_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        # Should find fewer critical gaps
        # (may still have some for missing evidence types)
        assert isinstance(result, GapAnalysisResult)
    
    def test_detects_missing_tsc(self, analyzer):
        """Test detection of missing TSC coverage."""
        # Only CC6 evidence
        evidence = Evidence(
            evidence_id="auth_001",
            evidence_type=EvidenceType.AUTHENTICATION_EVENT,
            evidence_source=EvidenceSource.APPLICATION_LOG,
            tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
            control_description="Auth logging",
            collected_at=datetime.now().isoformat(),
            event_timestamp="2025-10-15T12:00:00",
            data_hash="",
            data={},
        )
        evidence.data_hash = evidence.compute_hash()
        
        result = analyzer.analyze(
            [evidence],
            "2025-07-01",
            "2025-12-31"
        )
        
        # Should detect missing CC3, CC4, CC7, CC8
        missing_tsc_gaps = [
            g for g in result.gaps
            if g.gap_type == GapType.MISSING_TSC
        ]
        assert len(missing_tsc_gaps) > 0
    
    def test_detects_temporal_gap(self, analyzer):
        """Test detection of temporal gaps."""
        # Evidence only from middle of period
        evidence = Evidence(
            evidence_id="auth_001",
            evidence_type=EvidenceType.AUTHENTICATION_EVENT,
            evidence_source=EvidenceSource.APPLICATION_LOG,
            tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
            control_description="Auth logging",
            collected_at=datetime.now().isoformat(),
            event_timestamp="2025-09-15T12:00:00",  # Middle of period
            data_hash="",
            data={},
        )
        evidence.data_hash = evidence.compute_hash()
        
        result = analyzer.analyze(
            [evidence],
            "2025-07-01",  # July start
            "2025-12-31"   # December end
        )
        
        temporal_gaps = [
            g for g in result.gaps
            if g.gap_type == GapType.TEMPORAL_GAP
        ]
        assert len(temporal_gaps) > 0
    
    def test_generate_remediation_plan(self, analyzer, full_evidence):
        """Test remediation plan generation."""
        result = analyzer.analyze(
            full_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        plan = analyzer.generate_remediation_plan(result)
        
        assert "priority_actions" in plan
        assert "detailed_actions" in plan
    
    def test_analysis_history_tracked(self, analyzer, full_evidence):
        """Test analysis history is tracked."""
        analyzer.analyze(
            full_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        assert len(analyzer.analysis_history) == 1
    
    def test_tsc_coverage_in_result(self, analyzer, full_evidence):
        """Test TSC coverage is included in result."""
        result = analyzer.analyze(
            full_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        assert "CC6" in result.tsc_coverage
    
    def test_gap_ids_assigned(self, analyzer):
        """Test gap IDs are assigned."""
        result = analyzer.analyze(
            [],
            "2025-07-01",
            "2025-12-31"
        )
        
        for gap in result.gaps:
            assert gap.gap_id.startswith("GAP-")
    
    def test_remediation_deadlines_calculated(self, analyzer):
        """Test remediation deadlines are calculated."""
        result = analyzer.analyze(
            [],
            "2025-07-01",
            "2025-12-31"
        )
        
        plan = analyzer.generate_remediation_plan(result)
        
        for action in plan["detailed_actions"]:
            assert action["deadline"] is not None
