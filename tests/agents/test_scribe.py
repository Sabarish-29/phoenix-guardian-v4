"""Tests for ScribeAgent - SOAP Note Generation.

Comprehensive tests for SOAP note generation including:
- Full encounter data processing
- Minimal input handling
- ICD-10 code extraction
"""

import pytest
from unittest.mock import patch, MagicMock
import os


# Set up mock API key for testing
@pytest.fixture(autouse=True)
def mock_anthropic_api_key():
    """Set mock API key for all tests."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-api-key"}):
        yield


@pytest.fixture
def mock_anthropic_client():
    """Mock the Anthropic client."""
    with patch('phoenix_guardian.agents.base.Anthropic') as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        
        # Default SOAP note response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="""**Subjective:**
Patient presents with cough and fever for 3 days.

**Objective:**
Temp: 101.2F, BP: 120/80, HR: 88
Crackles in right lower lung field

**Assessment:**
Pneumonia (J18.9), Fever (R50.9)

**Plan:**
1. Antibiotics
2. Follow-up in 1 week""")]
        mock_instance.messages.create.return_value = mock_response
        
        yield mock_instance


from phoenix_guardian.agents.scribe import ScribeAgent


@pytest.mark.asyncio
async def test_scribe_generates_soap_note(mock_anthropic_client):
    """Test SOAP note generation with realistic data."""
    agent = ScribeAgent()
    
    input_data = {
        "chief_complaint": "Cough and fever for 3 days",
        "vitals": {"temp": "101.2F", "bp": "120/80", "hr": "88"},
        "symptoms": ["cough", "fever", "fatigue"],
        "exam_findings": "Crackles in right lower lung field"
    }
    
    result = await agent.process(input_data)
    
    assert "soap_note" in result
    assert "icd_codes" in result
    assert "agent" in result
    assert result["agent"] == "ScribeAgent"
    
    # Verify all SOAP sections present
    soap = result["soap_note"]
    assert "Subjective:" in soap or "SUBJECTIVE" in soap or "**Subjective" in soap
    assert "Objective:" in soap or "OBJECTIVE" in soap or "**Objective" in soap
    assert "Assessment:" in soap or "ASSESSMENT" in soap or "**Assessment" in soap
    assert "Plan:" in soap or "PLAN" in soap or "**Plan" in soap
    
    # Verify ICD codes extracted
    assert isinstance(result["icd_codes"], list)


@pytest.mark.asyncio
async def test_scribe_handles_minimal_data(mock_anthropic_client):
    """Test SOAP generation with minimal input."""
    agent = ScribeAgent()
    
    input_data = {
        "chief_complaint": "Follow-up visit"
    }
    
    result = await agent.process(input_data)
    assert "soap_note" in result
    assert len(result["soap_note"]) > 0


@pytest.mark.asyncio
async def test_scribe_icd_code_extraction(mock_anthropic_client):
    """Test ICD-10 code extraction from text."""
    agent = ScribeAgent()
    
    # Test direct extraction
    test_text = "Assessment: Pneumonia (J18.9), Type 2 Diabetes (E11.9), Hypertension (I10)"
    codes = agent._extract_icd_codes(test_text)
    
    assert "J18.9" in codes
    assert "E11.9" in codes
    assert "I10" in codes


@pytest.mark.asyncio
async def test_scribe_icd_code_extraction_multiple_formats(mock_anthropic_client):
    """Test ICD-10 code extraction with various formats."""
    agent = ScribeAgent()
    
    # Test with different ICD-10 formats
    test_text = """
    ICD-10 codes identified:
    - J18.9 Pneumonia, unspecified
    - E11.65 Type 2 diabetes with hyperglycemia
    - I10 Essential hypertension
    - R50.9 Fever, unspecified
    """
    codes = agent._extract_icd_codes(test_text)
    
    assert len(codes) >= 4
    assert "J18.9" in codes
    assert "E11.65" in codes
    assert "I10" in codes
    assert "R50.9" in codes


@pytest.mark.asyncio
async def test_scribe_build_prompt(mock_anthropic_client):
    """Test prompt building from encounter data."""
    agent = ScribeAgent()
    
    input_data = {
        "chief_complaint": "Headache",
        "vitals": {"temp": "98.6F", "bp": "130/85"},
        "symptoms": ["headache", "nausea"],
        "exam_findings": "Mild photophobia"
    }
    
    prompt = agent._build_prompt(input_data)
    
    assert "Headache" in prompt
    assert "temp: 98.6F" in prompt
    assert "headache, nausea" in prompt
    assert "Mild photophobia" in prompt


@pytest.mark.asyncio
async def test_scribe_empty_vitals(mock_anthropic_client):
    """Test handling of empty vitals dictionary."""
    agent = ScribeAgent()
    
    input_data = {
        "chief_complaint": "Routine checkup",
        "vitals": {},
        "symptoms": [],
        "exam_findings": ""
    }
    
    result = await agent.process(input_data)
    assert "soap_note" in result
    assert len(result["soap_note"]) > 0


@pytest.mark.asyncio
async def test_scribe_returns_model_info(mock_anthropic_client):
    """Test that result includes model information."""
    agent = ScribeAgent()
    
    input_data = {
        "chief_complaint": "Annual physical"
    }
    
    result = await agent.process(input_data)
    
    assert "model" in result
    assert result["model"] == "claude-sonnet-4-20250514"
