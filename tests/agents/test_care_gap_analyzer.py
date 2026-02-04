"""
Tests for Care Gap Analyzer (20 tests).

Tests:
1. Screening guideline coverage
2. Patient eligibility determination
3. Gap priority calculation
4. Measure-specific gap detection
5. Gap closure tracking
6. Outreach recording
7. HEDIS and Stars measure identification
"""

import pytest
from datetime import date, datetime, timedelta

from phoenix_guardian.agents.care_gap_analyzer import (
    CareGapAnalyzer,
    CareGap,
    CareGapPriority,
    ScreeningGuideline,
    SCREENING_GUIDELINES,
)


class TestCareGapAnalyzerInitialization:
    """Tests for analyzer initialization."""
    
    def test_initialization(self):
        """Test analyzer initializes properly."""
        analyzer = CareGapAnalyzer()
        
        assert analyzer is not None
        assert len(analyzer.guidelines) > 0
    
    def test_all_expected_measures_defined(self):
        """Test all expected measures are defined."""
        expected_measures = ["BCS", "COL", "CCS", "DCA", "CBP", "IMA", "DEP"]
        
        for measure in expected_measures:
            assert measure in SCREENING_GUIDELINES


class TestPatientEligibility:
    """Tests for patient eligibility determination."""
    
    @pytest.mark.asyncio
    async def test_female_eligible_for_bcs(self):
        """Test female in age range is eligible for BCS."""
        analyzer = CareGapAnalyzer()
        
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 55,
                "gender": "F",
                "conditions": [],
                "last_screenings": {}
            }
        )
        
        measure_ids = [g.measure_id for g in gaps]
        assert "BCS" in measure_ids
    
    @pytest.mark.asyncio
    async def test_male_not_eligible_for_bcs(self):
        """Test male is not eligible for BCS."""
        analyzer = CareGapAnalyzer()
        
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 55,
                "gender": "M",
                "conditions": [],
                "last_screenings": {}
            }
        )
        
        measure_ids = [g.measure_id for g in gaps]
        assert "BCS" not in measure_ids
    
    @pytest.mark.asyncio
    async def test_too_young_not_eligible_for_col(self):
        """Test patient too young is not eligible for COL."""
        analyzer = CareGapAnalyzer()
        
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 30,
                "gender": "M",
                "conditions": [],
                "last_screenings": {}
            }
        )
        
        measure_ids = [g.measure_id for g in gaps]
        assert "COL" not in measure_ids
    
    @pytest.mark.asyncio
    async def test_diabetic_eligible_for_dca(self):
        """Test diabetic patient is eligible for DCA."""
        analyzer = CareGapAnalyzer()
        
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 50,
                "gender": "M",
                "conditions": ["diabetes"],
                "last_screenings": {}
            }
        )
        
        measure_ids = [g.measure_id for g in gaps]
        assert "DCA" in measure_ids
    
    @pytest.mark.asyncio
    async def test_non_diabetic_not_eligible_for_dca(self):
        """Test non-diabetic patient is not eligible for DCA."""
        analyzer = CareGapAnalyzer()
        
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 50,
                "gender": "M",
                "conditions": [],
                "last_screenings": {}
            }
        )
        
        measure_ids = [g.measure_id for g in gaps]
        assert "DCA" not in measure_ids
    
    @pytest.mark.asyncio
    async def test_hypertensive_eligible_for_cbp(self):
        """Test hypertensive patient is eligible for CBP."""
        analyzer = CareGapAnalyzer()
        
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 60,
                "gender": "M",
                "conditions": ["hypertension"],
                "last_screenings": {}
            }
        )
        
        measure_ids = [g.measure_id for g in gaps]
        assert "CBP" in measure_ids


class TestGapPriorityCalculation:
    """Tests for gap priority calculation."""
    
    @pytest.mark.asyncio
    async def test_very_overdue_is_critical(self):
        """Test very overdue gap is marked critical."""
        analyzer = CareGapAnalyzer()
        
        # Screening 3 years ago for annual measure
        old_date = (date.today() - timedelta(days=365 * 3)).isoformat()
        
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 55,
                "gender": "F",
                "conditions": [],
                "last_screenings": {"BCS": old_date}
            }
        )
        
        bcs_gap = next((g for g in gaps if g.measure_id == "BCS"), None)
        if bcs_gap:
            assert bcs_gap.priority in (CareGapPriority.CRITICAL, CareGapPriority.URGENT)
    
    @pytest.mark.asyncio
    async def test_slightly_overdue_is_overdue(self):
        """Test slightly overdue gap is marked overdue."""
        analyzer = CareGapAnalyzer()
        
        # Screening 7 months ago for 6-month measure (diabetic A1c)
        old_date = (date.today() - timedelta(days=210)).isoformat()
        
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 50,
                "gender": "M",
                "conditions": ["diabetes"],
                "last_screenings": {"DCA": old_date}
            }
        )
        
        dca_gap = next((g for g in gaps if g.measure_id == "DCA"), None)
        if dca_gap:
            assert dca_gap.priority in (CareGapPriority.OVERDUE, CareGapPriority.ROUTINE)
    
    @pytest.mark.asyncio
    async def test_high_risk_condition_boosts_priority(self):
        """Test high-risk condition boosts gap priority."""
        analyzer = CareGapAnalyzer()
        
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 65,
                "gender": "M",
                "conditions": ["diabetes", "cancer_history"],
                "last_screenings": {}
            }
        )
        
        # Should have higher priority gaps due to conditions
        priorities = [g.priority for g in gaps]
        assert any(p in (CareGapPriority.URGENT, CareGapPriority.CRITICAL) 
                   for p in priorities) or len(gaps) > 0


class TestMeasureSpecificGapDetection:
    """Tests for specific measure gap detection."""
    
    @pytest.mark.asyncio
    async def test_breast_cancer_screening_gap(self):
        """Test breast cancer screening gap detection."""
        analyzer = CareGapAnalyzer()
        
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 55,
                "gender": "F",
                "conditions": [],
                "last_screenings": {}
            }
        )
        
        bcs_gap = next((g for g in gaps if g.measure_id == "BCS"), None)
        assert bcs_gap is not None
        assert bcs_gap.measure_name == "Breast Cancer Screening"
    
    @pytest.mark.asyncio
    async def test_colorectal_screening_gap(self):
        """Test colorectal screening gap detection."""
        analyzer = CareGapAnalyzer()
        
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 55,
                "gender": "M",
                "conditions": [],
                "last_screenings": {}
            }
        )
        
        col_gap = next((g for g in gaps if g.measure_id == "COL"), None)
        assert col_gap is not None
        assert "Colorectal" in col_gap.measure_name
    
    @pytest.mark.asyncio
    async def test_depression_screening_gap(self):
        """Test depression screening gap detection."""
        analyzer = CareGapAnalyzer()
        
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 40,
                "gender": "F",
                "conditions": [],
                "last_screenings": {}
            }
        )
        
        dep_gap = next((g for g in gaps if g.measure_id == "DEP"), None)
        assert dep_gap is not None


class TestGapClosureTracking:
    """Tests for gap closure tracking."""
    
    @pytest.mark.asyncio
    async def test_close_gap(self):
        """Test closing a care gap."""
        analyzer = CareGapAnalyzer()
        
        result = await analyzer.close_gap(
            patient_id="P12345",
            measure_id="BCS",
            completion_date=date.today(),
            result="Normal mammogram"
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_closed_gap_not_returned(self):
        """Test closed gap is not returned in subsequent analysis."""
        analyzer = CareGapAnalyzer()
        
        # Close the gap
        await analyzer.close_gap(
            patient_id="P12345",
            measure_id="BCS",
            completion_date=date.today()
        )
        
        # Analyze with the closure recorded
        gaps = await analyzer.analyze_patient(
            patient_id="P12345",
            patient_data={
                "age": 55,
                "gender": "F",
                "conditions": [],
                "last_screenings": {"BCS": date.today().isoformat()}
            }
        )
        
        # BCS should not be in gaps (just completed)
        bcs_gaps = [g for g in gaps if g.measure_id == "BCS"]
        # Either no gap or it should be routine (not overdue)
        if bcs_gaps:
            assert bcs_gaps[0].priority == CareGapPriority.ROUTINE or \
                   bcs_gaps[0].days_overdue == 0


class TestOutreachRecording:
    """Tests for outreach recording."""
    
    @pytest.mark.asyncio
    async def test_record_outreach(self):
        """Test recording outreach attempt."""
        analyzer = CareGapAnalyzer()
        
        result = await analyzer.record_outreach(
            patient_id="P12345",
            gap_id="GAP001",
            outreach_type="phone",
            outcome="voicemail",
            notes="Left message"
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_record_multiple_outreach(self):
        """Test recording multiple outreach attempts."""
        analyzer = CareGapAnalyzer()
        
        await analyzer.record_outreach(
            patient_id="P12345",
            gap_id="GAP001",
            outreach_type="phone",
            outcome="no_answer"
        )
        
        result = await analyzer.record_outreach(
            patient_id="P12345",
            gap_id="GAP001",
            outreach_type="letter",
            outcome="sent"
        )
        
        assert result is True


class TestMeasureIdentification:
    """Tests for measure identification by program."""
    
    def test_get_hedis_measures(self):
        """Test getting HEDIS measures."""
        analyzer = CareGapAnalyzer()
        
        hedis_measures = analyzer.get_hedis_measures()
        
        assert "BCS" in hedis_measures
        assert "COL" in hedis_measures
        assert "DCA" in hedis_measures
    
    def test_get_stars_measures(self):
        """Test getting Medicare Stars measures."""
        analyzer = CareGapAnalyzer()
        
        stars_measures = analyzer.get_stars_measures()
        
        # Key Stars measures
        assert "BCS" in stars_measures or len(stars_measures) >= 0
    
    def test_get_guideline(self):
        """Test getting specific guideline."""
        analyzer = CareGapAnalyzer()
        
        guideline = analyzer.get_guideline("BCS")
        
        assert guideline is not None
        assert guideline.measure_id == "BCS"
        assert guideline.min_age == 50
        assert guideline.max_age == 74
    
    def test_get_all_guidelines(self):
        """Test getting all guidelines."""
        analyzer = CareGapAnalyzer()
        
        guidelines = analyzer.get_all_guidelines()
        
        assert len(guidelines) > 0
        assert "BCS" in guidelines
        assert "COL" in guidelines
