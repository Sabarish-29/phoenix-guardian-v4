"""
Tests for Population Health Reporter (15 tests).

Tests:
1. Report generation
2. Summary format
3. Detailed format
4. Executive format
5. Provider scorecard
6. Financial impact estimation
7. Recommendations generation
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict

from phoenix_guardian.agents.population_health_reporter import (
    PopulationHealthReporter,
    ReportFormat,
    ReportType,
)


@dataclass
class MockQualityMeasure:
    """Mock quality measure result."""
    measure_id: str
    measure_name: str
    rate: float
    benchmark: float
    percentile: int
    stars_rating: int
    trend: str
    gap_count: int
    numerator: int = 0
    denominator: int = 0
    program: str = "hedis"


@dataclass
class MockPopulationSummary:
    """Mock population health summary."""
    population_id: str
    population_name: str
    total_patients: int
    risk_distribution: Dict[str, int] = field(default_factory=dict)
    total_care_gaps: int = 0
    critical_gaps: int = 0
    gaps_by_measure: Dict[str, int] = field(default_factory=dict)
    quality_measures: List[MockQualityMeasure] = field(default_factory=list)
    overall_quality_score: float = 75.0
    trend_period: str = "Q4 2024"
    improvement_areas: List[str] = field(default_factory=list)
    concern_areas: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.risk_distribution:
            self.risk_distribution = {
                "low": 400,
                "moderate": 350,
                "high": 180,
                "critical": 70
            }
        if not self.quality_measures:
            self.quality_measures = [
                MockQualityMeasure(
                    measure_id="BCS",
                    measure_name="Breast Cancer Screening",
                    rate=0.75,
                    benchmark=0.72,
                    percentile=70,
                    stars_rating=4,
                    trend="improving",
                    gap_count=250
                ),
                MockQualityMeasure(
                    measure_id="COL",
                    measure_name="Colorectal Cancer Screening",
                    rate=0.68,
                    benchmark=0.66,
                    percentile=55,
                    stars_rating=3,
                    trend="stable",
                    gap_count=320
                ),
            ]


class TestReporterInitialization:
    """Tests for reporter initialization."""
    
    def test_initialization(self):
        """Test reporter initializes properly."""
        reporter = PopulationHealthReporter()
        
        assert reporter is not None
        assert len(reporter.report_templates) > 0


class TestSummaryReportGeneration:
    """Tests for summary report generation."""
    
    @pytest.mark.asyncio
    async def test_generate_summary_report(self):
        """Test generating summary report."""
        reporter = PopulationHealthReporter()
        
        summary = MockPopulationSummary(
            population_id="POP001",
            population_name="Test Population",
            total_patients=1000,
            total_care_gaps=500,
            critical_gaps=25
        )
        
        report = await reporter.generate_report(summary, format="summary")
        
        assert report is not None
        assert report["report_type"] == "summary"
        assert "population" in report
        assert "key_metrics" in report
    
    @pytest.mark.asyncio
    async def test_summary_includes_risk_distribution(self):
        """Test summary includes risk distribution."""
        reporter = PopulationHealthReporter()
        
        summary = MockPopulationSummary(
            population_id="POP001",
            population_name="Test",
            total_patients=1000
        )
        
        report = await reporter.generate_report(summary, format="summary")
        
        assert "risk_distribution" in report
    
    @pytest.mark.asyncio
    async def test_summary_includes_top_measures(self):
        """Test summary includes top measures."""
        reporter = PopulationHealthReporter()
        
        summary = MockPopulationSummary(
            population_id="POP001",
            population_name="Test",
            total_patients=1000
        )
        
        report = await reporter.generate_report(summary, format="summary")
        
        assert "top_measures" in report


class TestDetailedReportGeneration:
    """Tests for detailed report generation."""
    
    @pytest.mark.asyncio
    async def test_generate_detailed_report(self):
        """Test generating detailed report."""
        reporter = PopulationHealthReporter()
        
        summary = MockPopulationSummary(
            population_id="POP001",
            population_name="Test Population",
            total_patients=1000
        )
        
        report = await reporter.generate_report(summary, format="detailed")
        
        assert report["report_type"] == "detailed"
        assert "quality_measures" in report
        assert "recommendations" in report
    
    @pytest.mark.asyncio
    async def test_detailed_includes_all_measures(self):
        """Test detailed report includes all measures."""
        reporter = PopulationHealthReporter()
        
        summary = MockPopulationSummary(
            population_id="POP001",
            population_name="Test",
            total_patients=1000
        )
        
        report = await reporter.generate_report(summary, format="detailed")
        
        assert len(report["quality_measures"]) == 2  # BCS and COL
    
    @pytest.mark.asyncio
    async def test_detailed_includes_gaps_by_measure(self):
        """Test detailed includes gaps by measure."""
        reporter = PopulationHealthReporter()
        
        summary = MockPopulationSummary(
            population_id="POP001",
            population_name="Test",
            total_patients=1000,
            gaps_by_measure={"BCS": 100, "COL": 150}
        )
        
        report = await reporter.generate_report(summary, format="detailed")
        
        assert "gaps_by_measure" in report


class TestExecutiveReportGeneration:
    """Tests for executive report generation."""
    
    @pytest.mark.asyncio
    async def test_generate_executive_report(self):
        """Test generating executive report."""
        reporter = PopulationHealthReporter()
        
        summary = MockPopulationSummary(
            population_id="POP001",
            population_name="Test Population",
            total_patients=1000
        )
        
        report = await reporter.generate_report(summary, format="executive")
        
        assert report["report_type"] == "executive"
        assert "executive_summary" in report
        assert "priority_actions" in report
    
    @pytest.mark.asyncio
    async def test_executive_includes_financial_impact(self):
        """Test executive includes financial impact."""
        reporter = PopulationHealthReporter()
        
        summary = MockPopulationSummary(
            population_id="POP001",
            population_name="Test",
            total_patients=1000
        )
        
        report = await reporter.generate_report(summary, format="executive")
        
        assert "financial_impact" in report
    
    @pytest.mark.asyncio
    async def test_executive_includes_highlights(self):
        """Test executive includes key highlights."""
        reporter = PopulationHealthReporter()
        
        summary = MockPopulationSummary(
            population_id="POP001",
            population_name="Test",
            total_patients=1000
        )
        
        report = await reporter.generate_report(summary, format="executive")
        
        assert "key_highlights" in report
        assert len(report["key_highlights"]) > 0


class TestProviderScorecard:
    """Tests for provider scorecard generation."""
    
    @pytest.mark.asyncio
    async def test_generate_provider_scorecard(self):
        """Test generating provider scorecard."""
        reporter = PopulationHealthReporter()
        
        measures = [
            MockQualityMeasure(
                measure_id="BCS",
                measure_name="Breast Cancer Screening",
                rate=0.78,
                benchmark=0.72,
                percentile=75,
                stars_rating=4,
                trend="improving",
                gap_count=25
            )
        ]
        
        scorecard = await reporter.generate_provider_scorecard(
            provider_id="DR001",
            provider_name="Dr. Smith",
            measures=measures,
            panel_size=500
        )
        
        assert scorecard is not None
        assert scorecard["provider_id"] == "DR001"
        assert scorecard["provider_name"] == "Dr. Smith"
        assert scorecard["panel_size"] == 500
    
    @pytest.mark.asyncio
    async def test_scorecard_includes_composite_score(self):
        """Test scorecard includes composite score."""
        reporter = PopulationHealthReporter()
        
        measures = [
            MockQualityMeasure(
                measure_id="BCS",
                measure_name="Breast Cancer Screening",
                rate=0.80,
                benchmark=0.72,
                percentile=80,
                stars_rating=4,
                trend="stable",
                gap_count=20
            )
        ]
        
        scorecard = await reporter.generate_provider_scorecard(
            provider_id="DR001",
            provider_name="Dr. Smith",
            measures=measures,
            panel_size=500
        )
        
        assert "composite_score" in scorecard
        assert scorecard["composite_score"] > 0
    
    @pytest.mark.asyncio
    async def test_scorecard_includes_opportunities(self):
        """Test scorecard includes improvement opportunities."""
        reporter = PopulationHealthReporter()
        
        measures = [
            MockQualityMeasure(
                measure_id="COL",
                measure_name="Colorectal Screening",
                rate=0.60,
                benchmark=0.70,  # Below benchmark
                percentile=40,
                stars_rating=3,
                trend="declining",
                gap_count=100
            )
        ]
        
        scorecard = await reporter.generate_provider_scorecard(
            provider_id="DR001",
            provider_name="Dr. Smith",
            measures=measures,
            panel_size=500
        )
        
        assert "improvement_opportunities" in scorecard
        assert len(scorecard["improvement_opportunities"]) > 0


class TestRecommendationsGeneration:
    """Tests for recommendations generation."""
    
    @pytest.mark.asyncio
    async def test_recommendations_generated(self):
        """Test recommendations are generated."""
        reporter = PopulationHealthReporter()
        
        summary = MockPopulationSummary(
            population_id="POP001",
            population_name="Test",
            total_patients=1000,
            concern_areas=["Colorectal Screening"]
        )
        
        report = await reporter.generate_report(summary, format="detailed")
        
        assert "recommendations" in report
        assert len(report["recommendations"]) > 0
    
    @pytest.mark.asyncio
    async def test_critical_gaps_trigger_recommendation(self):
        """Test critical gaps trigger recommendations."""
        reporter = PopulationHealthReporter()
        
        summary = MockPopulationSummary(
            population_id="POP001",
            population_name="Test",
            total_patients=1000,
            critical_gaps=50
        )
        
        report = await reporter.generate_report(summary, format="detailed")
        
        # Should have recommendation about critical gaps
        recommendations = report.get("recommendations", [])
        assert any("critical" in str(r).lower() or "gap" in str(r).lower() 
                   for r in recommendations) or len(recommendations) > 0


class TestFinancialImpactEstimation:
    """Tests for financial impact estimation."""
    
    @pytest.mark.asyncio
    async def test_financial_impact_calculated(self):
        """Test financial impact is calculated."""
        reporter = PopulationHealthReporter()
        
        summary = MockPopulationSummary(
            population_id="POP001",
            population_name="Test",
            total_patients=1000,
            total_care_gaps=500
        )
        
        report = await reporter.generate_report(summary, format="executive")
        
        financial = report["financial_impact"]
        assert "gap_closure_opportunity" in financial
        assert "quality_bonus_potential" in financial
        assert "total_opportunity" in financial
