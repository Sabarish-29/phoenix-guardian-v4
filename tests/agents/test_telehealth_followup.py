"""
Tests for Telehealth Follow-Up Analyzer (12 tests).

Tests:
1. Emergent follow-up detection
2. Urgent follow-up detection
3. Routine follow-up detection
4. No follow-up scenarios
5. Specialty-specific rules
6. Visit type appropriateness
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from dataclasses import dataclass

from phoenix_guardian.agents.telehealth_followup_analyzer import (
    FollowUpAnalyzer,
    FollowUpResult,
    RedFlag,
    RED_FLAGS,
)


@dataclass
class MockEncounter:
    """Mock encounter for testing."""
    transcript: str = ""
    specialty: str = "primary_care"
    patient_state: str = "FL"


@dataclass
class MockInferenceResult:
    """Mock inference result for testing."""
    systems_assessed: list = None
    systems_not_assessed: list = None
    inperson_flags: list = None
    
    def __post_init__(self):
        self.systems_assessed = self.systems_assessed or []
        self.systems_not_assessed = self.systems_not_assessed or []
        self.inperson_flags = self.inperson_flags or []


class TestFollowUpAnalyzerInitialization:
    """Tests for analyzer initialization."""
    
    def test_initialization(self):
        """Test analyzer initializes properly."""
        analyzer = FollowUpAnalyzer()
        
        assert analyzer is not None
        assert hasattr(analyzer, 'red_flags')
        assert hasattr(analyzer, 'specialty_thresholds')
    
    def test_red_flags_organized_by_urgency(self):
        """Test red flags are organized by urgency level."""
        assert "emergent" in RED_FLAGS
        assert "urgent" in RED_FLAGS
        assert "routine" in RED_FLAGS


class TestEmergentFollowUp:
    """Tests for emergent follow-up detection."""
    
    @pytest.mark.asyncio
    async def test_detect_stroke_symptoms(self):
        """Test detecting stroke symptoms as emergent."""
        analyzer = FollowUpAnalyzer()
        
        encounter = MockEncounter(
            transcript="Patient has facial droop and weakness on one side.",
            specialty="neurology"
        )
        inference = MockInferenceResult()
        
        result = await analyzer.analyze(encounter, inference)
        
        assert result.needs_followup is True
        assert result.urgency == "emergent"
        assert "stroke" in result.reason.lower()
    
    @pytest.mark.asyncio
    async def test_detect_crushing_chest_pain(self):
        """Test detecting crushing chest pain as emergent."""
        analyzer = FollowUpAnalyzer()
        
        encounter = MockEncounter(
            transcript="Patient reports crushing chest pain radiating to arm.",
            specialty="cardiology"
        )
        inference = MockInferenceResult()
        
        result = await analyzer.analyze(encounter, inference)
        
        assert result.needs_followup is True
        assert result.urgency == "emergent"
    
    @pytest.mark.asyncio
    async def test_detect_suicidal_ideation(self):
        """Test detecting suicidal ideation as emergent."""
        analyzer = FollowUpAnalyzer()
        
        encounter = MockEncounter(
            transcript="Patient says they want to end their life.",
            specialty="psychiatry"
        )
        inference = MockInferenceResult()
        
        result = await analyzer.analyze(encounter, inference)
        
        assert result.needs_followup is True
        assert result.urgency == "emergent"


class TestUrgentFollowUp:
    """Tests for urgent follow-up detection."""
    
    @pytest.mark.asyncio
    async def test_detect_pleuritic_chest_pain(self):
        """Test detecting pleuritic chest pain as urgent."""
        analyzer = FollowUpAnalyzer()
        
        encounter = MockEncounter(
            transcript="Patient has chest pain that's worse with breathing.",
            specialty="pulmonology"
        )
        inference = MockInferenceResult()
        
        result = await analyzer.analyze(encounter, inference)
        
        assert result.needs_followup is True
        assert result.urgency == "urgent"
    
    @pytest.mark.asyncio
    async def test_detect_gi_bleeding(self):
        """Test detecting GI bleeding as urgent."""
        analyzer = FollowUpAnalyzer()
        
        encounter = MockEncounter(
            transcript="Patient reports blood in stool for 2 days.",
            specialty="gastroenterology"
        )
        inference = MockInferenceResult()
        
        result = await analyzer.analyze(encounter, inference)
        
        assert result.needs_followup is True
        assert result.urgency == "urgent"
    
    @pytest.mark.asyncio
    async def test_detect_syncope(self):
        """Test detecting syncope as urgent."""
        analyzer = FollowUpAnalyzer()
        
        encounter = MockEncounter(
            transcript="Patient passed out yesterday briefly.",
            specialty="cardiology"
        )
        inference = MockInferenceResult()
        
        result = await analyzer.analyze(encounter, inference)
        
        assert result.needs_followup is True
        assert result.urgency == "urgent"


class TestRoutineFollowUp:
    """Tests for routine follow-up detection."""
    
    @pytest.mark.asyncio
    async def test_detect_skin_lesion_followup(self):
        """Test skin lesion needs routine follow-up."""
        analyzer = FollowUpAnalyzer()
        
        encounter = MockEncounter(
            transcript="Patient has a new mole on their back.",
            specialty="dermatology"
        )
        inference = MockInferenceResult()
        
        result = await analyzer.analyze(encounter, inference)
        
        assert result.needs_followup is True
        assert result.urgency == "routine"
    
    @pytest.mark.asyncio
    async def test_detect_lab_work_needed(self):
        """Test lab work triggers routine follow-up."""
        analyzer = FollowUpAnalyzer()
        
        encounter = MockEncounter(
            transcript="We need to check your A1c levels.",
            specialty="primary_care"
        )
        inference = MockInferenceResult()
        
        result = await analyzer.analyze(encounter, inference)
        
        assert result.needs_followup is True
        assert result.urgency == "routine"


class TestNoFollowUpNeeded:
    """Tests for scenarios not requiring follow-up."""
    
    @pytest.mark.asyncio
    async def test_stable_medication_refill(self):
        """Test stable medication refill doesn't need follow-up."""
        analyzer = FollowUpAnalyzer()
        
        encounter = MockEncounter(
            transcript="Patient here for routine medication refill. Feeling well. No new symptoms.",
            specialty="primary_care"
        )
        inference = MockInferenceResult(
            systems_assessed=["constitutional"],
            inperson_flags=[]
        )
        
        result = await analyzer.analyze(encounter, inference)
        
        # May or may not need follow-up, but shouldn't be urgent
        if result.needs_followup:
            assert result.urgency == "routine"


class TestSpecialtySpecificRules:
    """Tests for specialty-specific follow-up rules."""
    
    @pytest.mark.asyncio
    async def test_cardiology_lower_threshold(self):
        """Test cardiology has lower threshold for follow-up."""
        analyzer = FollowUpAnalyzer()
        
        # Generic chest symptoms - cardiology should flag
        encounter = MockEncounter(
            transcript="Patient mentions occasional chest discomfort.",
            specialty="cardiology"
        )
        inference = MockInferenceResult()
        
        result = await analyzer.analyze(encounter, inference)
        
        # Cardiology should err on side of caution
        assert result.needs_followup is True


class TestVisitTypeAppropriateness:
    """Tests for visit type appropriateness analysis."""
    
    def test_medication_refill_appropriate(self):
        """Test medication refill is appropriate for telehealth."""
        analyzer = FollowUpAnalyzer()
        
        result = analyzer.analyze_visit_type_appropriateness(
            chief_complaint="medication refill",
            specialty="primary_care"
        )
        
        assert result["appropriate_for_telehealth"] is True
    
    def test_new_injury_not_appropriate(self):
        """Test new injury is not ideal for telehealth."""
        analyzer = FollowUpAnalyzer()
        
        result = analyzer.analyze_visit_type_appropriateness(
            chief_complaint="new injury to knee from fall",
            specialty="orthopedics"
        )
        
        assert result["appropriate_for_telehealth"] is False


class TestUrgencyTimelines:
    """Tests for urgency timeline information."""
    
    def test_emergent_timeline(self):
        """Test emergent urgency timeline."""
        analyzer = FollowUpAnalyzer()
        
        timeline = analyzer.get_urgency_timeline("emergent")
        
        assert "immediately" in timeline.lower() or "er" in timeline.lower()
    
    def test_urgent_timeline(self):
        """Test urgent urgency timeline."""
        analyzer = FollowUpAnalyzer()
        
        timeline = analyzer.get_urgency_timeline("urgent")
        
        assert "48" in timeline or "72" in timeline
    
    def test_routine_timeline(self):
        """Test routine urgency timeline."""
        analyzer = FollowUpAnalyzer()
        
        timeline = analyzer.get_urgency_timeline("routine")
        
        assert "week" in timeline.lower()
