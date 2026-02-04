"""
Tests for ROI Calculator and Executive Report Generator.

Tests cover:
- Formula verification
- Edge cases (zero encounters, zero attacks)
- Custom platform costs
- Report generation
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pytest

from src.analytics.roi_calculator import (
    AVG_HEALTHCARE_BREACH_COST_USD,
    DEFAULT_PLATFORM_COST_USD,
    PHYSICIAN_HOURLY_RATE_USD,
    TRADITIONAL_DOC_TIME_MINUTES,
    ROICalculator,
    ROIInput,
    ROIResult,
)
from src.analytics.executive_report import ExecutiveReportGenerator


class TestROIInputValidation:
    """Tests for ROIInput validation."""
    
    def test_valid_input_creation(self):
        """Test creating a valid ROIInput."""
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=5000,
            ai_doc_time_minutes=8.0,
            attacks_blocked_month=15,
            physicians_count=50,
            months_active=12,
        )
        
        assert inputs.hospital_name == "Test Hospital"
        assert inputs.total_encounters_month == 5000
        assert inputs.ai_doc_time_minutes == 8.0
        assert inputs.attacks_blocked_month == 15
        assert inputs.physicians_count == 50
        assert inputs.months_active == 12
    
    def test_default_months_active(self):
        """Test that months_active defaults to 1."""
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=5000,
            ai_doc_time_minutes=8.0,
            attacks_blocked_month=15,
            physicians_count=50,
        )
        
        assert inputs.months_active == 1
    
    def test_negative_encounters_raises_error(self):
        """Test that negative encounters raises ValueError."""
        with pytest.raises(ValueError, match="total_encounters_month must be non-negative"):
            ROIInput(
                hospital_name="Test Hospital",
                total_encounters_month=-100,
                ai_doc_time_minutes=8.0,
                attacks_blocked_month=15,
                physicians_count=50,
            )
    
    def test_negative_ai_time_raises_error(self):
        """Test that negative AI time raises ValueError."""
        with pytest.raises(ValueError, match="ai_doc_time_minutes must be non-negative"):
            ROIInput(
                hospital_name="Test Hospital",
                total_encounters_month=5000,
                ai_doc_time_minutes=-5.0,
                attacks_blocked_month=15,
                physicians_count=50,
            )
    
    def test_ai_time_exceeds_traditional_raises_error(self):
        """Test that AI time exceeding traditional time raises ValueError."""
        with pytest.raises(ValueError, match="ai_doc_time_minutes.*cannot exceed"):
            ROIInput(
                hospital_name="Test Hospital",
                total_encounters_month=5000,
                ai_doc_time_minutes=30.0,  # Exceeds 25 min traditional
                attacks_blocked_month=15,
                physicians_count=50,
            )
    
    def test_negative_attacks_raises_error(self):
        """Test that negative attacks raises ValueError."""
        with pytest.raises(ValueError, match="attacks_blocked_month must be non-negative"):
            ROIInput(
                hospital_name="Test Hospital",
                total_encounters_month=5000,
                ai_doc_time_minutes=8.0,
                attacks_blocked_month=-5,
                physicians_count=50,
            )
    
    def test_negative_physicians_raises_error(self):
        """Test that negative physicians count raises ValueError."""
        with pytest.raises(ValueError, match="physicians_count must be non-negative"):
            ROIInput(
                hospital_name="Test Hospital",
                total_encounters_month=5000,
                ai_doc_time_minutes=8.0,
                attacks_blocked_month=15,
                physicians_count=-10,
            )
    
    def test_zero_months_active_raises_error(self):
        """Test that zero months_active raises ValueError."""
        with pytest.raises(ValueError, match="months_active must be at least 1"):
            ROIInput(
                hospital_name="Test Hospital",
                total_encounters_month=5000,
                ai_doc_time_minutes=8.0,
                attacks_blocked_month=15,
                physicians_count=50,
                months_active=0,
            )
    
    def test_negative_platform_cost_raises_error(self):
        """Test that negative platform cost raises ValueError."""
        with pytest.raises(ValueError, match="platform_cost_usd must be non-negative"):
            ROIInput(
                hospital_name="Test Hospital",
                total_encounters_month=5000,
                ai_doc_time_minutes=8.0,
                attacks_blocked_month=15,
                physicians_count=50,
                platform_cost_usd=-1000.0,
            )


class TestROIResult:
    """Tests for ROIResult."""
    
    def test_result_creation(self):
        """Test creating an ROIResult."""
        result = ROIResult(
            hospital_name="Test Hospital",
            period_months=12,
            time_saved_minutes_per_encounter=17.0,
            time_saved_hours_total=17000.0,
            time_saved_value_usd=2550000.0,
            attacks_blocked=180,
            breach_prevention_value_usd=1962000.0,
            total_roi_usd=4512000.0,
            roi_multiplier=7.52,
            platform_cost_usd=600000.0,
            net_roi_usd=3912000.0,
        )
        
        assert result.hospital_name == "Test Hospital"
        assert result.period_months == 12
        assert result.total_roi_usd == 4512000.0
    
    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = ROIResult(
            hospital_name="Test Hospital",
            period_months=12,
            time_saved_minutes_per_encounter=17.0,
            time_saved_hours_total=17000.0,
            time_saved_value_usd=2550000.0,
            attacks_blocked=180,
            breach_prevention_value_usd=1962000.0,
            total_roi_usd=4512000.0,
            roi_multiplier=7.52,
            platform_cost_usd=600000.0,
            net_roi_usd=3912000.0,
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["hospital_name"] == "Test Hospital"
        assert result_dict["period_months"] == 12
        assert result_dict["total_roi_usd"] == 4512000.0
        assert isinstance(result_dict, dict)
    
    def test_result_summary(self):
        """Test generating result summary."""
        result = ROIResult(
            hospital_name="Test Hospital",
            period_months=12,
            time_saved_minutes_per_encounter=17.0,
            time_saved_hours_total=17000.0,
            time_saved_value_usd=2550000.0,
            attacks_blocked=180,
            breach_prevention_value_usd=1962000.0,
            total_roi_usd=4512000.0,
            roi_multiplier=7.52,
            platform_cost_usd=600000.0,
            net_roi_usd=3912000.0,
        )
        
        summary = result.summary()
        
        assert "Test Hospital" in summary
        assert "12 month" in summary
        assert "4,512,000" in summary
        assert "7.5x" in summary


class TestROICalculatorFormulas:
    """Tests for ROI Calculator formulas."""
    
    def test_time_savings_formula(self):
        """Test time savings calculation formula.
        
        Formula: (25 - ai_time) × encounters × months / 60 × $150
        """
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,  # 15 minutes saved per encounter
            attacks_blocked_month=0,  # No attacks for isolated test
            physicians_count=10,
            months_active=1,
        )
        
        result = calculator.calculate(inputs)
        
        # Time saved: (25 - 10) = 15 minutes per encounter
        assert result.time_saved_minutes_per_encounter == 15.0
        
        # Total hours: 15 × 1000 / 60 = 250 hours
        assert result.time_saved_hours_total == 250.0
        
        # Value: 250 × $150 = $37,500
        assert result.time_saved_value_usd == 37500.0
    
    def test_breach_prevention_formula(self):
        """Test breach prevention calculation formula.
        
        Formula: attacks × months × 0.001 × $10.9M
        """
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=0,  # No encounters for isolated test
            ai_doc_time_minutes=0.0,
            attacks_blocked_month=100,
            physicians_count=10,
            months_active=1,
        )
        
        result = calculator.calculate(inputs)
        
        # Breach value: 100 × 1 × 0.001 × $10,900,000 = $1,090,000
        expected_breach_value = 100 * 0.001 * AVG_HEALTHCARE_BREACH_COST_USD
        assert result.breach_prevention_value_usd == expected_breach_value
    
    def test_roi_multiplier_formula(self):
        """Test ROI multiplier calculation.
        
        Formula: total_roi / (platform_cost × months)
        """
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=1,
            platform_cost_usd=10000.0,
        )
        
        result = calculator.calculate(inputs)
        
        # Verify multiplier = total_roi / platform_cost
        expected_multiplier = result.total_roi_usd / 10000.0
        assert abs(result.roi_multiplier - expected_multiplier) < 0.01
    
    def test_net_roi_calculation(self):
        """Test net ROI calculation (total - cost)."""
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=1,
            platform_cost_usd=10000.0,
        )
        
        result = calculator.calculate(inputs)
        
        assert result.net_roi_usd == result.total_roi_usd - result.platform_cost_usd
    
    def test_multi_month_calculation(self):
        """Test calculations scale correctly with months."""
        calculator = ROICalculator()
        
        inputs_1month = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=1,
        )
        
        inputs_12months = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=12,
        )
        
        result_1 = calculator.calculate(inputs_1month)
        result_12 = calculator.calculate(inputs_12months)
        
        # Time savings should scale by 12
        assert result_12.time_saved_hours_total == result_1.time_saved_hours_total * 12
        
        # Attacks blocked should scale by 12
        assert result_12.attacks_blocked == result_1.attacks_blocked * 12


class TestROICalculatorEdgeCases:
    """Tests for edge cases."""
    
    def test_zero_encounters(self):
        """Test calculation with zero encounters."""
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=0,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=1,
        )
        
        result = calculator.calculate(inputs)
        
        assert result.time_saved_hours_total == 0.0
        assert result.time_saved_value_usd == 0.0
        # Still has breach prevention value
        assert result.breach_prevention_value_usd > 0
    
    def test_zero_attacks(self):
        """Test calculation with zero attacks."""
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=0,
            physicians_count=10,
            months_active=1,
        )
        
        result = calculator.calculate(inputs)
        
        assert result.attacks_blocked == 0
        assert result.breach_prevention_value_usd == 0.0
        # Still has time savings value
        assert result.time_saved_value_usd > 0
    
    def test_zero_both_encounters_and_attacks(self):
        """Test calculation with zero encounters and attacks."""
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=0,
            ai_doc_time_minutes=0.0,
            attacks_blocked_month=0,
            physicians_count=10,
            months_active=1,
        )
        
        result = calculator.calculate(inputs)
        
        assert result.total_roi_usd == 0.0
        assert result.roi_multiplier == 0.0
    
    def test_ai_time_equals_traditional(self):
        """Test when AI time equals traditional time (no savings)."""
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=25.0,  # Same as traditional
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=1,
        )
        
        result = calculator.calculate(inputs)
        
        assert result.time_saved_minutes_per_encounter == 0.0
        assert result.time_saved_hours_total == 0.0
        assert result.time_saved_value_usd == 0.0
    
    def test_zero_platform_cost(self):
        """Test handling of zero platform cost (free tier)."""
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=1,
            platform_cost_usd=0.0,
        )
        
        result = calculator.calculate(inputs)
        
        # ROI multiplier should be infinite when cost is zero
        assert result.roi_multiplier == float("inf")
        assert result.net_roi_usd == result.total_roi_usd


class TestROICalculatorCustomCosts:
    """Tests for custom platform costs."""
    
    def test_custom_platform_cost(self):
        """Test with custom platform cost."""
        calculator = ROICalculator()
        
        custom_cost = 75000.0
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=1,
            platform_cost_usd=custom_cost,
        )
        
        result = calculator.calculate(inputs)
        
        assert result.platform_cost_usd == custom_cost
    
    def test_default_platform_cost(self):
        """Test that default platform cost is used when not specified."""
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=1,
        )
        
        result = calculator.calculate(inputs)
        
        assert result.platform_cost_usd == DEFAULT_PLATFORM_COST_USD
    
    def test_custom_breach_cost(self):
        """Test calculator with custom breach cost."""
        custom_breach_cost = 5_000_000.0
        calculator = ROICalculator(breach_cost_usd=custom_breach_cost)
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=0,
            ai_doc_time_minutes=0.0,
            attacks_blocked_month=100,
            physicians_count=10,
            months_active=1,
        )
        
        result = calculator.calculate(inputs)
        
        expected = 100 * 0.001 * custom_breach_cost
        assert result.breach_prevention_value_usd == expected
    
    def test_custom_physician_rate(self):
        """Test calculator with custom physician hourly rate."""
        custom_rate = 200.0
        calculator = ROICalculator(physician_rate_usd=custom_rate)
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=0,
            physicians_count=10,
            months_active=1,
        )
        
        result = calculator.calculate(inputs)
        
        # 15 min saved × 1000 encounters / 60 = 250 hours
        # 250 hours × $200 = $50,000
        assert result.time_saved_value_usd == 50000.0


class TestROICalculatorAdvancedMethods:
    """Tests for advanced calculator methods."""
    
    def test_break_even_months(self):
        """Test break-even calculation."""
        calculator = ROICalculator()
        
        break_even = calculator.calculate_break_even_months(
            encounters_per_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            platform_cost_usd=50000.0,
        )
        
        # Should be a positive number
        assert break_even > 0
        assert break_even < float("inf")
    
    def test_break_even_with_zero_value(self):
        """Test break-even when monthly value is zero."""
        calculator = ROICalculator()
        
        break_even = calculator.calculate_break_even_months(
            encounters_per_month=0,
            ai_doc_time_minutes=25.0,  # No time saved
            attacks_blocked_month=0,
            platform_cost_usd=50000.0,
        )
        
        assert break_even == float("inf")
    
    def test_project_annual_roi(self):
        """Test annual ROI projection."""
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=1,
        )
        
        annual_result = calculator.project_annual_roi(inputs)
        
        assert annual_result.period_months == 12
        
        # Verify annual values are 12x monthly
        monthly_result = calculator.calculate(inputs)
        assert annual_result.time_saved_hours_total == monthly_result.time_saved_hours_total * 12
    
    def test_compare_scenarios(self):
        """Test scenario comparison."""
        calculator = ROICalculator()
        
        base_inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=1,
        )
        
        comparison = calculator.compare_scenarios(
            base_inputs,
            improved_ai_time=5.0,  # Faster AI
        )
        
        assert "base" in comparison
        assert "improved" in comparison
        assert "delta_roi_usd" in comparison
        
        # Improved scenario should have higher ROI
        assert comparison["delta_roi_usd"] > 0
        assert comparison["improved"].total_roi_usd > comparison["base"].total_roi_usd


class TestExecutiveReportGenerator:
    """Tests for Executive Report Generator."""
    
    def test_generator_initialization(self):
        """Test report generator initialization."""
        generator = ExecutiveReportGenerator()
        
        assert generator.company_name == "Phoenix Guardian"
        assert generator.logo_path is None
    
    def test_generator_with_custom_company(self):
        """Test generator with custom company name."""
        generator = ExecutiveReportGenerator(company_name="Custom Healthcare AI")
        
        assert generator.company_name == "Custom Healthcare AI"
    
    def test_generate_report(self):
        """Test generating a full PDF report."""
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=5000,
            ai_doc_time_minutes=8.0,
            attacks_blocked_month=15,
            physicians_count=50,
            months_active=12,
        )
        
        roi = calculator.calculate(inputs)
        generator = ExecutiveReportGenerator()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_report.pdf")
            
            result_path = generator.generate(
                hospital_name="Test Hospital",
                roi=roi,
                encounters_total=60000,
                attacks_detected=200,
                attacks_blocked=180,
                physician_satisfaction=4.5,
                avg_doc_time_minutes=8.0,
                output_path=output_path,
            )
            
            assert result_path == output_path
            assert os.path.exists(result_path)
            
            # Check file size is reasonable (should be at least a few KB)
            file_size = os.path.getsize(result_path)
            assert file_size > 1000
    
    def test_generate_summary_page(self):
        """Test generating a single-page summary."""
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=5000,
            ai_doc_time_minutes=8.0,
            attacks_blocked_month=15,
            physicians_count=50,
            months_active=1,
        )
        
        roi = calculator.calculate(inputs)
        generator = ExecutiveReportGenerator()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "summary.pdf")
            
            result_path = generator.generate_summary_page(
                hospital_name="Test Hospital",
                roi=roi,
                output_path=output_path,
            )
            
            assert os.path.exists(result_path)
    
    def test_report_creates_directory(self):
        """Test that report generator creates output directory if needed."""
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=1,
        )
        
        roi = calculator.calculate(inputs)
        generator = ExecutiveReportGenerator()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = os.path.join(tmpdir, "nested", "reports", "test.pdf")
            
            result_path = generator.generate(
                hospital_name="Test Hospital",
                roi=roi,
                encounters_total=1000,
                attacks_detected=15,
                attacks_blocked=10,
                physician_satisfaction=4.0,
                avg_doc_time_minutes=10.0,
                output_path=nested_path,
            )
            
            assert os.path.exists(result_path)
    
    def test_report_without_recommendations(self):
        """Test generating report without recommendations section."""
        calculator = ROICalculator()
        
        inputs = ROIInput(
            hospital_name="Test Hospital",
            total_encounters_month=1000,
            ai_doc_time_minutes=10.0,
            attacks_blocked_month=10,
            physicians_count=10,
            months_active=1,
        )
        
        roi = calculator.calculate(inputs)
        generator = ExecutiveReportGenerator()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "no_rec_report.pdf")
            
            result_path = generator.generate(
                hospital_name="Test Hospital",
                roi=roi,
                encounters_total=1000,
                attacks_detected=15,
                attacks_blocked=10,
                physician_satisfaction=4.0,
                avg_doc_time_minutes=10.0,
                output_path=output_path,
                include_recommendations=False,
            )
            
            assert os.path.exists(result_path)


class TestReportRecommendations:
    """Tests for report recommendation generation."""
    
    def test_low_roi_recommendation(self):
        """Test recommendation for low ROI multiplier."""
        generator = ExecutiveReportGenerator()
        
        low_roi = ROIResult(
            hospital_name="Test",
            period_months=1,
            time_saved_minutes_per_encounter=5.0,
            time_saved_hours_total=100.0,
            time_saved_value_usd=15000.0,
            attacks_blocked=5,
            breach_prevention_value_usd=5450.0,
            total_roi_usd=20450.0,
            roi_multiplier=1.5,  # Below 2.0 benchmark
            platform_cost_usd=13633.0,
            net_roi_usd=6817.0,
        )
        
        recommendations = generator._generate_recommendations(
            low_roi, satisfaction=4.5, block_rate=0.95
        )
        
        # Should recommend increasing utilization
        assert any("utilization" in r.lower() for r in recommendations)
    
    def test_high_roi_recommendation(self):
        """Test recommendation for high ROI multiplier."""
        generator = ExecutiveReportGenerator()
        
        high_roi = ROIResult(
            hospital_name="Test",
            period_months=1,
            time_saved_minutes_per_encounter=17.0,
            time_saved_hours_total=1000.0,
            time_saved_value_usd=150000.0,
            attacks_blocked=50,
            breach_prevention_value_usd=545000.0,
            total_roi_usd=695000.0,
            roi_multiplier=6.0,  # Above 5.0 threshold
            platform_cost_usd=115833.0,
            net_roi_usd=579167.0,
        )
        
        recommendations = generator._generate_recommendations(
            high_roi, satisfaction=4.5, block_rate=0.95
        )
        
        # Should recommend expansion
        assert any("expand" in r.lower() for r in recommendations)
    
    def test_low_satisfaction_recommendation(self):
        """Test recommendation for low satisfaction score."""
        generator = ExecutiveReportGenerator()
        
        roi = ROIResult(
            hospital_name="Test",
            period_months=1,
            time_saved_minutes_per_encounter=10.0,
            time_saved_hours_total=500.0,
            time_saved_value_usd=75000.0,
            attacks_blocked=20,
            breach_prevention_value_usd=218000.0,
            total_roi_usd=293000.0,
            roi_multiplier=3.0,
            platform_cost_usd=97667.0,
            net_roi_usd=195333.0,
        )
        
        recommendations = generator._generate_recommendations(
            roi, satisfaction=3.5, block_rate=0.95  # Below 4.0
        )
        
        # Should recommend training
        assert any("training" in r.lower() or "satisfaction" in r.lower() for r in recommendations)


class TestConstants:
    """Tests for module constants."""
    
    def test_breach_cost_constant(self):
        """Test breach cost constant value."""
        assert AVG_HEALTHCARE_BREACH_COST_USD == 10_900_000
    
    def test_traditional_doc_time_constant(self):
        """Test traditional documentation time constant."""
        assert TRADITIONAL_DOC_TIME_MINUTES == 25.0
    
    def test_physician_rate_constant(self):
        """Test physician hourly rate constant."""
        assert PHYSICIAN_HOURLY_RATE_USD == 150.0
    
    def test_default_platform_cost_constant(self):
        """Test default platform cost constant."""
        assert DEFAULT_PLATFORM_COST_USD == 50_000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
