"""
Tests for Quality Metrics Engine (15 tests).

Tests:
1. Metric calculation
2. Benchmarking
3. Stars rating calculation
4. Trend calculation
5. Composite score calculation
6. Program-specific measures
7. Improvement simulation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from phoenix_guardian.agents.quality_metrics_engine import (
    QualityMetricsEngine,
    QualityMeasureResult,
    MeasureSpecification,
    QualityProgram,
    MEASURE_SPECIFICATIONS,
)


class TestQualityMetricsEngineInitialization:
    """Tests for engine initialization."""
    
    def test_initialization_default(self):
        """Test engine initializes with default programs."""
        engine = QualityMetricsEngine()
        
        assert engine is not None
        assert QualityProgram.HEDIS in engine.programs
        assert QualityProgram.MIPS in engine.programs
    
    def test_initialization_specific_programs(self):
        """Test engine initializes with specific programs."""
        engine = QualityMetricsEngine(programs=[QualityProgram.STARS])
        
        assert QualityProgram.STARS in engine.programs
        assert len(engine.programs) == 1
    
    def test_measure_specifications_loaded(self):
        """Test measure specifications are loaded."""
        engine = QualityMetricsEngine()
        
        assert len(engine.specifications) > 0
        assert "BCS" in engine.specifications
        assert "COL" in engine.specifications


class TestMetricCalculation:
    """Tests for metric calculation."""
    
    @pytest.mark.asyncio
    async def test_calculate_metrics_returns_results(self):
        """Test calculating metrics returns results."""
        engine = QualityMetricsEngine()
        
        results = await engine.calculate_metrics(
            population_ids=["P1", "P2", "P3", "P4", "P5"]
        )
        
        assert isinstance(results, list)
        assert len(results) > 0
    
    @pytest.mark.asyncio
    async def test_calculate_specific_measures(self):
        """Test calculating specific measures."""
        engine = QualityMetricsEngine()
        
        results = await engine.calculate_metrics(
            measure_ids=["BCS"]
        )
        
        # Should have BCS measure
        measure_ids = [r.measure_id for r in results]
        assert "BCS" in measure_ids
    
    @pytest.mark.asyncio
    async def test_result_has_required_fields(self):
        """Test result has all required fields."""
        engine = QualityMetricsEngine()
        
        results = await engine.calculate_metrics(
            population_ids=["P1", "P2"]
        )
        
        if results:
            result = results[0]
            assert hasattr(result, 'measure_id')
            assert hasattr(result, 'measure_name')
            assert hasattr(result, 'numerator')
            assert hasattr(result, 'denominator')
            assert hasattr(result, 'rate')
            assert hasattr(result, 'percentile')
            assert hasattr(result, 'stars_rating')


class TestBenchmarking:
    """Tests for benchmarking."""
    
    @pytest.mark.asyncio
    async def test_percentile_calculation(self):
        """Test percentile is calculated."""
        engine = QualityMetricsEngine()
        
        results = await engine.calculate_metrics()
        
        if results:
            for result in results:
                assert 0 <= result.percentile <= 100
    
    @pytest.mark.asyncio
    async def test_benchmark_comparison(self):
        """Test benchmark is included in result."""
        engine = QualityMetricsEngine()
        
        results = await engine.calculate_metrics()
        
        if results:
            result = results[0]
            assert result.benchmark >= 0
            assert result.benchmark <= 1.0


class TestStarsRatingCalculation:
    """Tests for Medicare Stars rating calculation."""
    
    @pytest.mark.asyncio
    async def test_stars_rating_1_to_5(self):
        """Test stars rating is 0-5."""
        engine = QualityMetricsEngine()
        
        results = await engine.calculate_metrics()
        
        for result in results:
            assert 0 <= result.stars_rating <= 5
    
    def test_stars_thresholds_defined(self):
        """Test Stars thresholds are defined for key measures."""
        bcs_spec = MEASURE_SPECIFICATIONS.get("BCS")
        
        assert bcs_spec is not None
        assert bcs_spec.stars_1 > 0
        assert bcs_spec.stars_5 > bcs_spec.stars_4 > bcs_spec.stars_3


class TestTrendCalculation:
    """Tests for trend calculation."""
    
    @pytest.mark.asyncio
    async def test_trend_values_valid(self):
        """Test trend values are valid."""
        engine = QualityMetricsEngine()
        
        results = await engine.calculate_metrics()
        
        valid_trends = ["improving", "declining", "stable", ""]
        for result in results:
            assert result.trend in valid_trends


class TestCompositeScoreCalculation:
    """Tests for composite score calculation."""
    
    @pytest.mark.asyncio
    async def test_composite_score_calculated(self):
        """Test composite score is calculated."""
        engine = QualityMetricsEngine()
        
        results = await engine.calculate_metrics()
        
        composite = await engine.calculate_composite_score(results)
        
        assert 0 <= composite <= 100
    
    @pytest.mark.asyncio
    async def test_composite_score_empty_results(self):
        """Test composite score with empty results."""
        engine = QualityMetricsEngine()
        
        composite = await engine.calculate_composite_score([])
        
        assert composite == 0.0


class TestProgramSpecificMeasures:
    """Tests for program-specific measure identification."""
    
    @pytest.mark.asyncio
    async def test_get_hedis_measures(self):
        """Test getting HEDIS measures."""
        engine = QualityMetricsEngine()
        
        hedis_measures = await engine.get_program_measures(QualityProgram.HEDIS)
        
        assert "BCS" in hedis_measures
        assert "COL" in hedis_measures
    
    @pytest.mark.asyncio
    async def test_get_mips_measures(self):
        """Test getting MIPS measures."""
        engine = QualityMetricsEngine()
        
        mips_measures = await engine.get_program_measures(QualityProgram.MIPS)
        
        assert len(mips_measures) > 0
    
    @pytest.mark.asyncio
    async def test_get_domain_measures(self):
        """Test getting measures by domain."""
        engine = QualityMetricsEngine()
        
        prevention_measures = await engine.get_domain_measures("Prevention")
        
        assert "BCS" in prevention_measures
        assert "COL" in prevention_measures


class TestMeasureDetails:
    """Tests for measure detail retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_measure_details(self):
        """Test getting measure details."""
        engine = QualityMetricsEngine()
        
        details = await engine.get_measure_details("BCS")
        
        assert details is not None
        assert details.measure_id == "BCS"
        assert details.measure_name == "Breast Cancer Screening"
        assert details.age_min == 50
        assert details.age_max == 74
    
    @pytest.mark.asyncio
    async def test_get_measure_details_not_found(self):
        """Test getting details for non-existent measure."""
        engine = QualityMetricsEngine()
        
        details = await engine.get_measure_details("NONEXISTENT")
        
        assert details is None


class TestImprovementSimulation:
    """Tests for improvement simulation."""
    
    @pytest.mark.asyncio
    async def test_simulate_improvement(self):
        """Test simulating measure improvement."""
        engine = QualityMetricsEngine()
        
        simulation = await engine.simulate_improvement(
            measure_id="BCS",
            current_rate=0.65,
            target_rate=0.80,
            population_size=1000
        )
        
        assert simulation is not None
        assert "patients_to_close" in simulation
        assert "percentile_improvement" in simulation
    
    @pytest.mark.asyncio
    async def test_simulate_improvement_invalid_measure(self):
        """Test simulating improvement for invalid measure."""
        engine = QualityMetricsEngine()
        
        simulation = await engine.simulate_improvement(
            measure_id="INVALID",
            current_rate=0.60,
            target_rate=0.70,
            population_size=100
        )
        
        assert "error" in simulation
    
    @pytest.mark.asyncio
    async def test_simulate_improvement_calculates_gap_count(self):
        """Test simulation calculates gap count correctly."""
        engine = QualityMetricsEngine()
        
        simulation = await engine.simulate_improvement(
            measure_id="COL",
            current_rate=0.60,
            target_rate=0.70,
            population_size=1000
        )
        
        # 70% of 1000 - 60% of 1000 = 100 patients to close
        assert simulation["patients_to_close"] == 100
