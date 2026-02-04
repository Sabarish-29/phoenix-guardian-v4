"""Tests for CodingAgent - ICD-10 and CPT Code Suggestion.

Comprehensive tests for medical coding including:
- Code suggestion from clinical notes
- Database matching
- AI code parsing
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
        
        # Default coding response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="""Based on the documentation, here are the suggested codes:

ICD-10 codes:
J18.9 - Pneumonia, unspecified organism
R50.9 - Fever, unspecified

CPT codes:
99213 - Office visit, established patient
71046 - Chest X-ray, 2 views""")]
        mock_instance.messages.create.return_value = mock_response
        
        yield mock_instance


from phoenix_guardian.agents.coding import CodingAgent


@pytest.mark.asyncio
async def test_coding_agent_suggests_codes(mock_anthropic_client):
    """Test code suggestion from clinical notes."""
    agent = CodingAgent()
    
    input_data = {
        "clinical_note": "Patient presents with pneumonia and fever. Started on antibiotics.",
        "procedures": ["Chest X-ray"]
    }
    
    result = await agent.process(input_data)
    
    assert "icd10_codes" in result
    assert "cpt_codes" in result
    assert isinstance(result["icd10_codes"], list)
    assert isinstance(result["cpt_codes"], list)
    
    # Should find pneumonia code from database match
    codes = [c["code"] for c in result["icd10_codes"]]
    assert "J18.9" in codes


@pytest.mark.asyncio
async def test_coding_agent_database_matching(mock_anthropic_client):
    """Test database matching for common conditions."""
    agent = CodingAgent()
    
    input_data = {
        "clinical_note": "Patient has diabetes and hypertension. No acute issues."
    }
    
    result = await agent.process(input_data)
    
    codes = [c["code"] for c in result["icd10_codes"]]
    assert "E11.9" in codes  # Diabetes
    assert "I10" in codes    # Hypertension


@pytest.mark.asyncio
async def test_coding_agent_parse_icd10(mock_anthropic_client):
    """Test ICD-10 code parsing."""
    agent = CodingAgent()
    
    test_response = """
    ICD-10 codes:
    J18.9 - Pneumonia, unspecified
    E11.9 - Type 2 diabetes mellitus
    """
    
    icd10, cpt = agent._parse_code_suggestions(test_response)
    
    assert len(icd10) >= 2
    assert any(c["code"] == "J18.9" for c in icd10)
    assert any(c["code"] == "E11.9" for c in icd10)


@pytest.mark.asyncio
async def test_coding_agent_parse_cpt(mock_anthropic_client):
    """Test CPT code parsing."""
    agent = CodingAgent()
    
    test_response = """
    CPT codes:
    99213 - Office visit, established patient
    71046 - Chest X-ray, 2 views
    """
    
    icd10, cpt = agent._parse_code_suggestions(test_response)
    
    assert len(cpt) >= 2
    assert any(c["code"] == "99213" for c in cpt)
    assert any(c["code"] == "71046" for c in cpt)


@pytest.mark.asyncio
async def test_coding_agent_all_common_codes(mock_anthropic_client):
    """Test all common ICD-10 codes in database."""
    agent = CodingAgent()
    
    input_data = {
        "clinical_note": """
        Patient has pneumonia, diabetes, hypertension, copd, asthma,
        heart failure, chest pain, fever, headache, and nausea.
        """
    }
    
    result = await agent.process(input_data)
    
    codes = [c["code"] for c in result["icd10_codes"]]
    
    # Check that database codes are found
    expected_codes = ["J18.9", "E11.9", "I10", "J44.9", "J45.909", 
                      "I50.9", "R07.9", "R50.9", "R51", "R11.0"]
    
    for expected in expected_codes:
        assert expected in codes, f"Expected code {expected} not found"


@pytest.mark.asyncio
async def test_coding_agent_no_duplicates(mock_anthropic_client):
    """Test that duplicate codes are not added."""
    agent = CodingAgent()
    
    # Test that if AI suggests a code already in database, no duplicate
    input_data = {
        "clinical_note": "Patient has pneumonia."
    }
    
    result = await agent.process(input_data)
    
    codes = [c["code"] for c in result["icd10_codes"]]
    # Count occurrences of J18.9
    j18_count = codes.count("J18.9")
    assert j18_count == 1, f"Expected 1 occurrence of J18.9, found {j18_count}"


@pytest.mark.asyncio
async def test_coding_agent_empty_note(mock_anthropic_client):
    """Test handling of empty clinical note."""
    agent = CodingAgent()
    
    input_data = {
        "clinical_note": "",
        "procedures": []
    }
    
    result = await agent.process(input_data)
    
    assert "icd10_codes" in result
    assert "cpt_codes" in result
    assert result["agent"] == "CodingAgent"


@pytest.mark.asyncio
async def test_coding_agent_with_procedures(mock_anthropic_client):
    """Test with procedures list."""
    agent = CodingAgent()
    
    input_data = {
        "clinical_note": "Patient with chest pain",
        "procedures": ["ECG", "Chest X-ray", "Blood draw"]
    }
    
    result = await agent.process(input_data)
    
    assert "cpt_codes" in result
    # CPT codes should be suggested for procedures
    assert isinstance(result["cpt_codes"], list)


@pytest.mark.asyncio
async def test_coding_agent_build_prompt(mock_anthropic_client):
    """Test prompt building."""
    agent = CodingAgent()
    
    prompt = agent._build_coding_prompt(
        "Patient has fever",
        ["Blood work"]
    )
    
    assert "Patient has fever" in prompt
    assert "Blood work" in prompt
