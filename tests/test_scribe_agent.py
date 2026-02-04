"""Comprehensive tests for ScribeAgent.

Tests cover:
- Agent initialization and configuration
- Input validation (transcript, patient_history)
- SOAP note generation with mocked API
- Section parsing and validation
- Error handling (API errors, rate limits)
- Performance metrics tracking
- Prompt construction logic
"""

import pytest
from unittest.mock import Mock, patch
from phoenix_guardian.agents.scribe_agent import ScribeAgent


# =============================================================================
# Sample Test Data
# =============================================================================

SAMPLE_TRANSCRIPT = """
Patient is a 65-year-old male presenting with acute substernal chest pain 
for the past 2 hours. Pain described as pressure-like, 7/10 severity, 
radiating to left arm. Associated with shortness of breath and diaphoresis. 
No relief with rest.

Vital signs: BP 150/95, HR 105, RR 22, SpO2 96% on room air, Temp 98.6°F

Physical exam reveals tachycardic regular rhythm, no murmurs. 
Lungs clear bilaterally. Patient appears anxious and diaphoretic.

Given cardiovascular risk factors and presentation, concerned for 
acute coronary syndrome. Plan: 12-lead EKG stat, cardiac enzymes, 
chest X-ray. Aspirin 325mg given. IV access established. 
Cardiology consultation requested.
"""

SAMPLE_PATIENT_HISTORY = {
    "age": 65,
    "conditions": ["Hypertension", "Type 2 Diabetes", "Hyperlipidemia"],
    "medications": [
        "Lisinopril 10mg daily",
        "Metformin 1000mg BID",
        "Atorvastatin 40mg daily",
    ],
    "allergies": ["Penicillin (rash)"],
}

SAMPLE_SOAP_NOTE = """SUBJECTIVE:
Chief Complaint: Chest pain for 2 hours
HPI: 65-year-old male with history of hypertension, type 2 diabetes, and hyperlipidemia presents with acute onset substernal chest pain, pressure-like quality, 7/10 severity, radiating to left arm. Associated symptoms include shortness of breath and diaphoresis. No relief with rest.

OBJECTIVE:
Vital Signs:
- BP: 150/95 mmHg
- HR: 105 bpm
- RR: 22/min
- SpO2: 96% on room air
- Temperature: 98.6°F

Physical Exam:
- General: Anxious, diaphoretic
- Cardiovascular: Tachycardic, regular rhythm, no murmurs
- Respiratory: Clear to auscultation bilaterally

ASSESSMENT:
Acute coronary syndrome, suspected
- Typical anginal symptoms with radiation
- Multiple cardiovascular risk factors (HTN, DM, HLD)
- Hemodynamically stable

PLAN:
1. Diagnostic workup:
   - 12-lead EKG - STAT
   - Cardiac enzymes (troponin)
   - Chest X-ray
2. Treatment:
   - Aspirin 325mg PO (administered)
   - IV access established
   - Continuous cardiac monitoring
3. Consultation:
   - Cardiology consultation
4. Disposition:
   - Admit for telemetry monitoring

REASONING:
Patient's presentation with typical anginal symptoms (substernal chest pain radiating to left arm, diaphoresis, dyspnea) combined with significant cardiovascular risk factors (age 65, HTN, DM, HLD) raises high suspicion for acute coronary syndrome. Immediate diagnostic workup with EKG and cardiac biomarkers is essential. Aspirin appropriately initiated for antiplatelet effect. Close monitoring with cardiology involvement warranted."""


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_claude_response():
    """Create reusable mock Claude API response."""
    mock_response = Mock()
    mock_response.content = [Mock(text=SAMPLE_SOAP_NOTE)]
    mock_response.usage = Mock(input_tokens=500, output_tokens=800)
    return mock_response


@pytest.fixture
def scribe_agent():
    """Create ScribeAgent instance with test API key."""
    return ScribeAgent(api_key="test-api-key-12345")


# =============================================================================
# Test: Agent Initialization
# =============================================================================


class TestScribeAgentInitialization:
    """Test ScribeAgent initialization and configuration."""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        agent = ScribeAgent(api_key="test-key-123")
        assert agent.name == "Scribe"
        assert agent.model == "claude-sonnet-4-20250514"
        assert agent.max_tokens == 2000
        assert agent.temperature == 0.3

    def test_init_with_env_api_key(self, monkeypatch):
        """Test initialization with environment variable API key."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-test-key")
        agent = ScribeAgent()
        assert agent.name == "Scribe"

    def test_init_without_api_key_raises_error(self, monkeypatch):
        """Test initialization fails without API key."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError, match="API key required"):
            ScribeAgent()

    def test_init_custom_parameters(self):
        """Test initialization with custom parameters."""
        agent = ScribeAgent(
            api_key="test-key",
            model="custom-model",
            max_tokens=3000,
            temperature=0.5,
        )
        assert agent.model == "custom-model"
        assert agent.max_tokens == 3000
        assert agent.temperature == 0.5

    def test_inherits_from_base_agent(self, scribe_agent):
        """Test ScribeAgent inherits from BaseAgent properly."""
        assert hasattr(scribe_agent, "execute")
        assert hasattr(scribe_agent, "get_metrics")
        assert scribe_agent.call_count == 0


# =============================================================================
# Test: Input Validation
# =============================================================================


class TestScribeAgentValidation:
    """Test input validation logic."""

    @pytest.mark.asyncio
    async def test_missing_transcript_key(self, scribe_agent):
        """Test error when transcript key missing."""
        context = {"patient_history": SAMPLE_PATIENT_HISTORY}

        result = await scribe_agent.execute(context)

        assert result.success is False
        assert "must contain 'transcript'" in result.error

    @pytest.mark.asyncio
    async def test_empty_transcript(self, scribe_agent):
        """Test error when transcript is empty."""
        context = {"transcript": "   "}

        result = await scribe_agent.execute(context)

        assert result.success is False
        assert "cannot be empty" in result.error

    @pytest.mark.asyncio
    async def test_transcript_too_short(self, scribe_agent):
        """Test error when transcript below minimum length."""
        context = {"transcript": "Too short text here"}

        result = await scribe_agent.execute(context)

        assert result.success is False
        assert "too short" in result.error.lower()

    @pytest.mark.asyncio
    async def test_transcript_too_long(self, scribe_agent):
        """Test error when transcript exceeds maximum length."""
        long_transcript = "A" * 15000
        context = {"transcript": long_transcript}

        result = await scribe_agent.execute(context)

        assert result.success is False
        assert "too long" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_transcript_type(self, scribe_agent):
        """Test error when transcript is not a string."""
        context = {"transcript": 12345}

        result = await scribe_agent.execute(context)

        assert result.success is False
        assert "must be string" in result.error

    @pytest.mark.asyncio
    async def test_invalid_patient_history_type(self, scribe_agent):
        """Test error when patient_history is not a dict."""
        context = {"transcript": SAMPLE_TRANSCRIPT, "patient_history": "invalid"}

        result = await scribe_agent.execute(context)

        assert result.success is False
        assert "must be dict" in result.error

    @pytest.mark.asyncio
    async def test_empty_context_dict(self, scribe_agent):
        """Test error with completely empty context."""
        result = await scribe_agent.execute({})

        assert result.success is False
        assert "must contain 'transcript'" in result.error


# =============================================================================
# Test: SOAP Note Generation
# =============================================================================


class TestScribeAgentSOAPGeneration:
    """Test SOAP note generation functionality."""

    @pytest.mark.asyncio
    async def test_basic_soap_generation(
        self, scribe_agent, mock_claude_response
    ):
        """Test successful SOAP note generation."""
        with patch.object(
            scribe_agent, "_call_claude_api", return_value=mock_claude_response
        ):
            context = {
                "transcript": SAMPLE_TRANSCRIPT,
                "patient_history": SAMPLE_PATIENT_HISTORY,
            }

            result = await scribe_agent.execute(context)

            assert result.success is True
            assert "soap_note" in result.data
            assert "SUBJECTIVE:" in result.data["soap_note"]
            assert "OBJECTIVE:" in result.data["soap_note"]
            assert "ASSESSMENT:" in result.data["soap_note"]
            assert "PLAN:" in result.data["soap_note"]

    @pytest.mark.asyncio
    async def test_soap_generation_without_patient_history(
        self, scribe_agent, mock_claude_response
    ):
        """Test SOAP generation without patient history."""
        with patch.object(
            scribe_agent, "_call_claude_api", return_value=mock_claude_response
        ):
            context = {"transcript": SAMPLE_TRANSCRIPT}

            result = await scribe_agent.execute(context)

            assert result.success is True
            assert result.data["soap_note"] is not None

    @pytest.mark.asyncio
    async def test_sections_parsing(self, scribe_agent, mock_claude_response):
        """Test SOAP section parsing."""
        with patch.object(
            scribe_agent, "_call_claude_api", return_value=mock_claude_response
        ):
            context = {
                "transcript": SAMPLE_TRANSCRIPT,
                "patient_history": SAMPLE_PATIENT_HISTORY,
            }

            result = await scribe_agent.execute(context)

            sections = result.data["sections"]
            assert "subjective" in sections
            assert "objective" in sections
            assert "assessment" in sections
            assert "plan" in sections
            assert len(sections["subjective"]) > 20
            assert len(sections["objective"]) > 20

    @pytest.mark.asyncio
    async def test_reasoning_extraction(
        self, scribe_agent, mock_claude_response
    ):
        """Test reasoning trail extraction."""
        with patch.object(
            scribe_agent, "_call_claude_api", return_value=mock_claude_response
        ):
            context = {
                "transcript": SAMPLE_TRANSCRIPT,
                "patient_history": SAMPLE_PATIENT_HISTORY,
            }

            result = await scribe_agent.execute(context)

            assert len(result.reasoning) > 0
            # Check reasoning contains clinical terms
            reasoning_lower = result.reasoning.lower()
            assert any(
                term in reasoning_lower
                for term in ["risk", "clinical", "symptom", "presentation"]
            )

    @pytest.mark.asyncio
    async def test_token_counting(self, scribe_agent, mock_claude_response):
        """Test token usage tracking."""
        with patch.object(
            scribe_agent, "_call_claude_api", return_value=mock_claude_response
        ):
            context = {
                "transcript": SAMPLE_TRANSCRIPT,
                "patient_history": SAMPLE_PATIENT_HISTORY,
            }

            result = await scribe_agent.execute(context)

            assert "token_count" in result.data
            assert result.data["token_count"] == 1300  # 500 + 800

    @pytest.mark.asyncio
    async def test_model_used_in_response(
        self, scribe_agent, mock_claude_response
    ):
        """Test model identifier is included in response."""
        with patch.object(
            scribe_agent, "_call_claude_api", return_value=mock_claude_response
        ):
            context = {"transcript": SAMPLE_TRANSCRIPT}

            result = await scribe_agent.execute(context)

            assert result.data["model_used"] == "claude-sonnet-4-20250514"


# =============================================================================
# Test: Error Handling
# =============================================================================


class TestScribeAgentErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_api_error_handling(self, scribe_agent):
        """Test handling of API errors."""
        from anthropic import APIError

        # Create mock request for APIError
        mock_request = Mock()
        mock_request.url = "https://api.anthropic.com/v1/messages"
        mock_request.method = "POST"

        with patch.object(
            scribe_agent,
            "_call_claude_api",
            side_effect=APIError(
                message="API Error",
                request=mock_request,
                body=None
            ),
        ):
            context = {
                "transcript": SAMPLE_TRANSCRIPT,
                "patient_history": SAMPLE_PATIENT_HISTORY,
            }

            result = await scribe_agent.execute(context)

            assert result.success is False
            assert "API unavailable" in result.error
            # Ensure no PHI leaked in error
            assert "chest pain" not in result.error.lower()

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, scribe_agent):
        """Test handling of rate limit errors."""
        from anthropic import RateLimitError

        # Create mock request and response for RateLimitError
        mock_request = Mock()
        mock_request.url = "https://api.anthropic.com/v1/messages"
        mock_request.method = "POST"
        mock_response = Mock()
        mock_response.status_code = 429

        with patch.object(
            scribe_agent,
            "_call_claude_api",
            side_effect=RateLimitError(
                message="Rate limit exceeded",
                response=mock_response,
                body=None,
            ),
        ):
            context = {"transcript": SAMPLE_TRANSCRIPT}

            result = await scribe_agent.execute(context)

            assert result.success is False
            assert "unavailable" in result.error.lower()

    @pytest.mark.asyncio
    async def test_incomplete_soap_note_missing_assessment(self, scribe_agent):
        """Test handling of SOAP notes missing assessment section."""
        incomplete_soap = """SUBJECTIVE:
Chief complaint and history here with enough text to pass validation.

OBJECTIVE:
Physical exam findings with enough text to pass validation here.

PLAN:
Treatment plan with sufficient content for validation purposes."""

        mock_response = Mock()
        mock_response.content = [Mock(text=incomplete_soap)]
        mock_response.usage = Mock(input_tokens=100, output_tokens=200)

        with patch.object(
            scribe_agent, "_call_claude_api", return_value=mock_response
        ):
            context = {"transcript": SAMPLE_TRANSCRIPT}

            result = await scribe_agent.execute(context)

            assert result.success is False
            assert "missing required sections" in result.error.lower()

    @pytest.mark.asyncio
    async def test_soap_section_too_short(self, scribe_agent):
        """Test handling of SOAP notes with sections that are too short."""
        short_section_soap = """SUBJECTIVE:
Brief.

OBJECTIVE:
Brief.

ASSESSMENT:
Brief.

PLAN:
Brief."""

        mock_response = Mock()
        mock_response.content = [Mock(text=short_section_soap)]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)

        with patch.object(
            scribe_agent, "_call_claude_api", return_value=mock_response
        ):
            context = {"transcript": SAMPLE_TRANSCRIPT}

            result = await scribe_agent.execute(context)

            assert result.success is False
            assert "too short" in result.error.lower()

    @pytest.mark.asyncio
    async def test_generic_exception_handling(self, scribe_agent):
        """Test handling of unexpected exceptions."""
        with patch.object(
            scribe_agent,
            "_call_claude_api",
            side_effect=Exception("Unexpected error"),
        ):
            context = {"transcript": SAMPLE_TRANSCRIPT}

            result = await scribe_agent.execute(context)

            assert result.success is False
            assert "Exception" in result.error


# =============================================================================
# Test: Performance and Metrics
# =============================================================================


class TestScribeAgentPerformance:
    """Test performance and metrics tracking."""

    @pytest.mark.asyncio
    async def test_execution_time_tracking(
        self, scribe_agent, mock_claude_response
    ):
        """Test execution time is tracked."""
        with patch.object(
            scribe_agent, "_call_claude_api", return_value=mock_claude_response
        ):
            context = {"transcript": SAMPLE_TRANSCRIPT}

            result = await scribe_agent.execute(context)

            assert result.execution_time_ms > 0
            assert result.execution_time_ms < 10000  # Under 10 seconds

    @pytest.mark.asyncio
    async def test_metrics_accumulation(
        self, scribe_agent, mock_claude_response
    ):
        """Test metrics accumulate across multiple calls."""
        with patch.object(
            scribe_agent, "_call_claude_api", return_value=mock_claude_response
        ):
            # Execute multiple times
            for _ in range(3):
                context = {"transcript": SAMPLE_TRANSCRIPT}
                await scribe_agent.execute(context)

            metrics = scribe_agent.get_metrics()
            assert metrics["call_count"] == 3
            assert metrics["avg_execution_time_ms"] > 0
            assert metrics["total_execution_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_failed_calls_still_tracked(self, scribe_agent):
        """Test that failed calls are still tracked in metrics."""
        # Cause validation failure
        result = await scribe_agent.execute({"transcript": "short"})

        assert result.success is False
        metrics = scribe_agent.get_metrics()
        assert metrics["call_count"] == 1


# =============================================================================
# Test: Prompt Building
# =============================================================================


class TestScribeAgentPromptBuilding:
    """Test prompt construction logic."""

    def test_prompt_with_full_patient_history(self, scribe_agent):
        """Test prompt building with complete patient history."""
        prompt = scribe_agent._build_prompt(
            SAMPLE_TRANSCRIPT, SAMPLE_PATIENT_HISTORY
        )

        assert "65" in prompt  # Age
        assert "Hypertension" in prompt  # Condition
        assert "Lisinopril" in prompt  # Medication
        assert "Penicillin" in prompt  # Allergy
        assert SAMPLE_TRANSCRIPT in prompt

    def test_prompt_with_empty_patient_history(self, scribe_agent):
        """Test prompt building with empty patient history."""
        prompt = scribe_agent._build_prompt(SAMPLE_TRANSCRIPT, {})

        assert "Unknown" in prompt or "None documented" in prompt
        assert SAMPLE_TRANSCRIPT in prompt

    def test_prompt_with_partial_patient_history(self, scribe_agent):
        """Test prompt building with partial patient history."""
        partial_history = {"age": 30, "conditions": ["Asthma"]}
        prompt = scribe_agent._build_prompt(SAMPLE_TRANSCRIPT, partial_history)

        assert "30" in prompt
        assert "Asthma" in prompt
        assert "None documented" in prompt  # For missing medications

    def test_prompt_contains_critical_rules(self, scribe_agent):
        """Test prompt includes clinical rules."""
        prompt = scribe_agent._build_prompt(SAMPLE_TRANSCRIPT, {})

        assert "do not fabricate" in prompt.lower()
        assert "soap" in prompt.lower()
        assert "reasoning" in prompt.lower()
        assert "subjective" in prompt.lower()
        assert "objective" in prompt.lower()

    def test_prompt_contains_format_instructions(self, scribe_agent):
        """Test prompt contains format instructions."""
        prompt = scribe_agent._build_prompt(SAMPLE_TRANSCRIPT, {})

        assert "SUBJECTIVE:" in prompt
        assert "OBJECTIVE:" in prompt
        assert "ASSESSMENT:" in prompt
        assert "PLAN:" in prompt

    def test_format_list_with_items(self, scribe_agent):
        """Test list formatting with items."""
        items = ["Item1", "Item2", "Item3"]
        result = scribe_agent._format_list(items, "Default")
        assert result == "Item1, Item2, Item3"

    def test_format_list_empty(self, scribe_agent):
        """Test list formatting with empty list."""
        result = scribe_agent._format_list([], "Default Value")
        assert result == "Default Value"

    def test_format_list_none(self, scribe_agent):
        """Test list formatting with None."""
        result = scribe_agent._format_list(None, "Default Value")
        assert result == "Default Value"


# =============================================================================
# Test: Section Parsing
# =============================================================================


class TestScribeAgentSectionParsing:
    """Test SOAP section parsing logic."""

    def test_parse_complete_soap_note(self, scribe_agent):
        """Test parsing a complete SOAP note."""
        sections = scribe_agent._parse_soap_sections(SAMPLE_SOAP_NOTE)

        assert len(sections["subjective"]) > 0
        assert len(sections["objective"]) > 0
        assert len(sections["assessment"]) > 0
        assert len(sections["plan"]) > 0

    def test_parse_soap_note_without_reasoning(self, scribe_agent):
        """Test parsing SOAP note without reasoning section."""
        soap_without_reasoning = """SUBJECTIVE:
Patient complaint text here.

OBJECTIVE:
Physical exam findings here.

ASSESSMENT:
Clinical assessment here.

PLAN:
Treatment plan here."""

        sections = scribe_agent._parse_soap_sections(soap_without_reasoning)

        assert "patient complaint" in sections["subjective"].lower()
        assert "physical exam" in sections["objective"].lower()

    def test_extract_reasoning_present(self, scribe_agent):
        """Test reasoning extraction when present."""
        reasoning = scribe_agent._extract_reasoning(SAMPLE_SOAP_NOTE)

        assert len(reasoning) > 0
        assert "symptom" in reasoning.lower() or "risk" in reasoning.lower()

    def test_extract_reasoning_fallback(self, scribe_agent):
        """Test reasoning extraction fallback when not present."""
        soap_without_reasoning = """SUBJECTIVE:
Test.

OBJECTIVE:
Test.

ASSESSMENT:
Test.

PLAN:
Test."""

        reasoning = scribe_agent._extract_reasoning(soap_without_reasoning)

        assert "SOAP note generated" in reasoning


# =============================================================================
# Test: HIPAA Compliance
# =============================================================================


class TestScribeAgentHIPAACompliance:
    """Test HIPAA compliance features."""

    @pytest.mark.asyncio
    async def test_no_phi_in_validation_errors(self, scribe_agent):
        """Test that validation errors don't leak PHI."""
        context = {"transcript": "Patient John Smith with SSN 123-45-6789"}

        result = await scribe_agent.execute(context)

        assert result.success is False
        # Error should not contain patient identifiers
        assert "john" not in result.error.lower()
        assert "smith" not in result.error.lower()
        assert "123-45-6789" not in result.error

    @pytest.mark.asyncio
    async def test_no_phi_in_api_errors(self, scribe_agent):
        """Test that API errors don't leak PHI."""
        from anthropic import APIError

        mock_request = Mock()
        mock_request.url = "https://api.anthropic.com/v1/messages"
        mock_request.method = "POST"

        with patch.object(
            scribe_agent,
            "_call_claude_api",
            side_effect=APIError(
                message="API Error",
                request=mock_request,
                body=None
            ),
        ):
            context = {
                "transcript": "Patient Jane Doe presents with chest pain",
                "patient_history": {"age": 45},
            }

            result = await scribe_agent.execute(context)

            assert result.success is False
            # Error should not contain any transcript content
            assert "jane" not in result.error.lower()
            assert "doe" not in result.error.lower()
            assert "chest pain" not in result.error.lower()


# =============================================================================
# Test: Integration with BaseAgent
# =============================================================================


class TestScribeAgentBaseIntegration:
    """Test integration with BaseAgent functionality."""

    @pytest.mark.asyncio
    async def test_result_has_correct_structure(
        self, scribe_agent, mock_claude_response
    ):
        """Test that result follows AgentResult structure."""
        with patch.object(
            scribe_agent, "_call_claude_api", return_value=mock_claude_response
        ):
            context = {"transcript": SAMPLE_TRANSCRIPT}

            result = await scribe_agent.execute(context)

            # Check all AgentResult fields
            assert hasattr(result, "success")
            assert hasattr(result, "data")
            assert hasattr(result, "error")
            assert hasattr(result, "execution_time_ms")
            assert hasattr(result, "reasoning")

    @pytest.mark.asyncio
    async def test_multiple_concurrent_executions(
        self, scribe_agent, mock_claude_response
    ):
        """Test agent handles multiple concurrent executions."""
        import asyncio

        with patch.object(
            scribe_agent, "_call_claude_api", return_value=mock_claude_response
        ):
            tasks = [
                scribe_agent.execute({"transcript": SAMPLE_TRANSCRIPT})
                for _ in range(5)
            ]

            results = await asyncio.gather(*tasks)

            assert all(r.success for r in results)
            metrics = scribe_agent.get_metrics()
            assert metrics["call_count"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=phoenix_guardian.agents.scribe_agent"])
