"""
Tests for Telehealth Exam Inference Engine (18 tests).

Tests:
1. Q&A pair extraction
2. Body system identification
3. Clinical finding inference
4. Pain character extraction
5. Vitals extraction from transcript
6. In-person flag detection
7. Duration extraction
8. Remote assessment capability scoring
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from phoenix_guardian.agents.telehealth_exam_inference import (
    ExamInferenceEngine,
    InferenceResult,
    BODY_SYSTEMS,
    REMOTE_ASSESSABLE_SYSTEMS,
)


class TestExamInferenceEngineInitialization:
    """Tests for inference engine initialization."""
    
    def test_engine_initialization(self):
        """Test engine initializes properly."""
        engine = ExamInferenceEngine()
        
        assert engine is not None
        assert hasattr(engine, 'INPERSON_REQUIRED_KEYWORDS')
        assert hasattr(engine, 'SYSTEM_KEYWORDS')


class TestQAPairExtraction:
    """Tests for Q&A pair extraction."""
    
    @pytest.mark.asyncio
    async def test_extract_qa_from_transcript(self):
        """Test extracting Q&A pairs from transcript."""
        engine = ExamInferenceEngine()
        
        transcript = """
        Doctor: What brings you in today?
        Patient: I have a headache.
        Doctor: How long have you had the headache?
        Patient: About 3 days now.
        """
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="primary_care"
        )
        
        assert len(result.qa_pairs) >= 1
    
    @pytest.mark.asyncio
    async def test_extract_qa_with_speaker_segments(self):
        """Test Q&A extraction with speaker-labeled segments."""
        engine = ExamInferenceEngine()
        
        segments = [
            {"speaker": "physician", "text": "Any chest pain?"},
            {"speaker": "patient", "text": "Yes, on my left side."},
            {"speaker": "physician", "text": "How would you describe it?"},
            {"speaker": "patient", "text": "It's a dull ache."},
        ]
        
        result = await engine.analyze_transcript(
            transcript="",
            specialty="cardiology",
            segments=segments
        )
        
        assert len(result.qa_pairs) >= 2


class TestBodySystemIdentification:
    """Tests for body system identification."""
    
    @pytest.mark.asyncio
    async def test_identify_cardiovascular_symptoms(self):
        """Test identifying cardiovascular system discussion."""
        engine = ExamInferenceEngine()
        
        transcript = """
        Patient: I've been having chest pain and palpitations.
        The pain is worse when I exercise.
        """
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="cardiology"
        )
        
        assert "cardiovascular" in result.systems_assessed
    
    @pytest.mark.asyncio
    async def test_identify_respiratory_symptoms(self):
        """Test identifying respiratory system discussion."""
        engine = ExamInferenceEngine()
        
        transcript = """
        Patient: I've had a cough for a week and I'm short of breath.
        There's some wheezing too.
        """
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="pulmonology"
        )
        
        assert "respiratory" in result.systems_assessed
    
    @pytest.mark.asyncio
    async def test_identify_neurological_symptoms(self):
        """Test identifying neurological system discussion."""
        engine = ExamInferenceEngine()
        
        transcript = """
        Patient: I've had severe headaches and dizziness.
        Sometimes I feel numbness in my hands.
        """
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="neurology"
        )
        
        assert "neurological" in result.systems_assessed
    
    @pytest.mark.asyncio
    async def test_identify_multiple_systems(self):
        """Test identifying multiple systems from transcript."""
        engine = ExamInferenceEngine()
        
        transcript = """
        Patient: I have chest pain, a rash on my arm, and my knee hurts.
        I've also been feeling very tired lately.
        """
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="primary_care"
        )
        
        # Should identify at least 3 systems
        assert len(result.systems_assessed) >= 3


class TestClinicalFindingInference:
    """Tests for clinical finding inference."""
    
    @pytest.mark.asyncio
    async def test_infer_pain_finding(self):
        """Test inferring pain-related finding."""
        engine = ExamInferenceEngine()
        
        transcript = """
        Doctor: Where does it hurt?
        Patient: I have pain in my lower back. It's a dull ache.
        """
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="orthopedics"
        )
        
        # Should have finding about back pain
        assert any("back" in f.lower() or "pain" in f.lower() 
                   for f in result.findings)
    
    @pytest.mark.asyncio
    async def test_infer_negative_finding(self):
        """Test inferring negative (denied) findings."""
        engine = ExamInferenceEngine()
        
        transcript = """
        Doctor: Any fever?
        Patient: No fever.
        Doctor: Any nausea or vomiting?
        Patient: No, I don't have any nausea.
        """
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="primary_care"
        )
        
        # Should have denies findings
        assert any("denies" in f.lower() for f in result.findings)


class TestPainCharacterExtraction:
    """Tests for pain character extraction."""
    
    @pytest.mark.asyncio
    async def test_extract_sharp_pain(self):
        """Test extracting sharp pain character."""
        engine = ExamInferenceEngine()
        
        transcript = "Patient: It's a sharp pain in my chest."
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="cardiology"
        )
        
        assert any("sharp" in f.lower() for f in result.findings)
    
    @pytest.mark.asyncio
    async def test_extract_pleuritic_pain(self):
        """Test extracting pleuritic pain pattern."""
        engine = ExamInferenceEngine()
        
        transcript = "Patient: The chest pain is worse when I breathe."
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="pulmonology"
        )
        
        # Should extract pleuritic character AND flag for in-person
        assert any("pleuritic" in f.lower() or "breathing" in f.lower() 
                   for f in result.findings)


class TestVitalsExtraction:
    """Tests for vitals extraction from patient report."""
    
    @pytest.mark.asyncio
    async def test_extract_blood_pressure(self):
        """Test extracting blood pressure from transcript."""
        engine = ExamInferenceEngine()
        
        transcript = "Patient: I checked my blood pressure at home, it was 140/90."
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="primary_care"
        )
        
        assert "blood_pressure" in result.vitals
        assert "140/90" in result.vitals["blood_pressure"]
    
    @pytest.mark.asyncio
    async def test_extract_temperature(self):
        """Test extracting temperature from transcript."""
        engine = ExamInferenceEngine()
        
        transcript = "Patient: My temperature was 101.5 degrees this morning."
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="primary_care"
        )
        
        assert "temperature" in result.vitals
    
    @pytest.mark.asyncio
    async def test_extract_oxygen_saturation(self):
        """Test extracting O2 saturation from transcript."""
        engine = ExamInferenceEngine()
        
        transcript = "Patient: My pulse ox says 96%."
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="pulmonology"
        )
        
        assert "oxygen_saturation" in result.vitals


class TestInPersonFlagDetection:
    """Tests for detecting conditions requiring in-person visit."""
    
    @pytest.mark.asyncio
    async def test_flag_crushing_chest_pain(self):
        """Test flagging crushing chest pain as emergent."""
        engine = ExamInferenceEngine()
        
        transcript = "Patient: I have crushing chest pain that started an hour ago."
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="cardiology"
        )
        
        assert len(result.inperson_flags) > 0
        assert any("chest" in flag.lower() or "cardiac" in flag.lower() 
                   for flag in result.inperson_flags)
    
    @pytest.mark.asyncio
    async def test_flag_stroke_symptoms(self):
        """Test flagging stroke symptoms."""
        engine = ExamInferenceEngine()
        
        transcript = "Patient: I noticed facial droop this morning and weakness on one side."
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="neurology"
        )
        
        assert len(result.inperson_flags) > 0
        assert any("stroke" in flag.lower() or "emergent" in flag.lower() 
                   for flag in result.inperson_flags)
    
    @pytest.mark.asyncio
    async def test_flag_suicidal_ideation(self):
        """Test flagging suicidal ideation."""
        engine = ExamInferenceEngine()
        
        transcript = "Patient: I've been thinking about ending my life."
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="psychiatry"
        )
        
        assert len(result.inperson_flags) > 0
        assert any("suicidal" in flag.lower() or "psychiatric" in flag.lower() 
                   for flag in result.inperson_flags)


class TestRemoteAssessmentCapability:
    """Tests for remote assessment capability scoring."""
    
    def test_psychiatric_highly_assessable(self):
        """Test psychiatric system is highly remote-assessable."""
        engine = ExamInferenceEngine()
        
        capability = engine.get_remote_assessment_capability("psychiatric")
        
        assert capability >= 0.8  # High capability
    
    def test_genitourinary_not_assessable(self):
        """Test GU system not remote-assessable."""
        engine = ExamInferenceEngine()
        
        capability = engine.get_remote_assessment_capability("genitourinary")
        
        assert capability == 0.0  # Cannot assess remotely
    
    def test_all_systems_have_capability_score(self):
        """Test all body systems have capability scores."""
        for system in BODY_SYSTEMS:
            assert system in REMOTE_ASSESSABLE_SYSTEMS or \
                   REMOTE_ASSESSABLE_SYSTEMS.get(system) is not None or \
                   system in REMOTE_ASSESSABLE_SYSTEMS


class TestDurationExtraction:
    """Tests for symptom duration extraction."""
    
    @pytest.mark.asyncio
    async def test_extract_duration_days(self):
        """Test extracting duration in days."""
        engine = ExamInferenceEngine()
        
        transcript = "Patient: I've had this headache for 3 days."
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="neurology"
        )
        
        assert result.duration is not None
        assert "3" in result.duration
    
    @pytest.mark.asyncio
    async def test_extract_duration_weeks(self):
        """Test extracting duration in weeks."""
        engine = ExamInferenceEngine()
        
        transcript = "Patient: The cough started about 2 weeks ago."
        
        result = await engine.analyze_transcript(
            transcript=transcript,
            specialty="pulmonology"
        )
        
        assert result.duration is not None
        assert "week" in result.duration.lower()
