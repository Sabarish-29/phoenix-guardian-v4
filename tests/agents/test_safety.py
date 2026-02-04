"""Tests for SafetyAgent - Drug Interaction Detection.

Comprehensive tests for medication safety checking including:
- Known interaction detection
- Multiple medication analysis
- AI safety insights
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
        
        # Default safety response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="No significant drug interactions noted. Monitor routine labs.")]
        mock_instance.messages.create.return_value = mock_response
        
        yield mock_instance


from phoenix_guardian.agents.safety import SafetyAgent


@pytest.mark.asyncio
async def test_safety_agent_detects_known_interaction(mock_anthropic_client):
    """Test detection of known drug interaction."""
    agent = SafetyAgent()
    
    input_data = {
        "medications": ["lisinopril", "potassium"]
    }
    
    result = await agent.process(input_data)
    
    assert "interactions" in result
    assert "severity" in result
    assert result["severity"] == "HIGH"
    
    # Should find the lisinopril-potassium interaction
    db_interactions = [i for i in result["interactions"] if i.get("source") == "Database"]
    assert len(db_interactions) > 0
    assert "Hyperkalemia" in db_interactions[0]["description"]


@pytest.mark.asyncio
async def test_safety_agent_multiple_interactions(mock_anthropic_client):
    """Test detection of multiple interactions."""
    agent = SafetyAgent()
    
    input_data = {
        "medications": ["warfarin", "aspirin", "lisinopril", "potassium"]
    }
    
    result = await agent.process(input_data)
    
    db_interactions = [i for i in result["interactions"] if i.get("source") == "Database"]
    assert len(db_interactions) >= 2  # Should find at least 2 interactions


@pytest.mark.asyncio
async def test_safety_agent_no_interactions(mock_anthropic_client):
    """Test when no interactions found."""
    agent = SafetyAgent()
    
    input_data = {
        "medications": ["ibuprofen", "acetaminophen"]
    }
    
    result = await agent.process(input_data)
    
    assert result["severity"] == "LOW"


@pytest.mark.asyncio
async def test_safety_agent_ai_check(mock_anthropic_client):
    """Test AI safety check is included."""
    agent = SafetyAgent()
    
    input_data = {
        "medications": ["metformin", "insulin"]
    }
    
    result = await agent.process(input_data)
    
    ai_findings = [i for i in result["interactions"] if i.get("source") == "AI"]
    assert len(ai_findings) > 0
    assert len(ai_findings[0]["finding"]) > 0


@pytest.mark.asyncio
async def test_safety_agent_case_insensitive(mock_anthropic_client):
    """Test that medication matching is case insensitive."""
    agent = SafetyAgent()
    
    input_data = {
        "medications": ["LISINOPRIL", "Potassium"]
    }
    
    result = await agent.process(input_data)
    
    # Should still find the interaction
    db_interactions = [i for i in result["interactions"] if i.get("source") == "Database"]
    assert len(db_interactions) > 0


@pytest.mark.asyncio
async def test_safety_agent_empty_medications(mock_anthropic_client):
    """Test handling of empty medication list."""
    agent = SafetyAgent()
    
    input_data = {
        "medications": []
    }
    
    result = await agent.process(input_data)
    
    assert result["severity"] == "LOW"
    assert result["checked_medications"] == []


@pytest.mark.asyncio
async def test_safety_agent_single_medication(mock_anthropic_client):
    """Test with single medication (no interactions possible)."""
    agent = SafetyAgent()
    
    input_data = {
        "medications": ["lisinopril"]
    }
    
    result = await agent.process(input_data)
    
    assert result["severity"] == "LOW"
    assert "lisinopril" in result["checked_medications"]


@pytest.mark.asyncio
async def test_safety_agent_determine_severity(mock_anthropic_client):
    """Test severity determination logic."""
    agent = SafetyAgent()
    
    # Test HIGH severity
    interactions_high = [{"severity": "HIGH"}, {"severity": "MODERATE"}]
    assert agent._determine_severity(interactions_high) == "HIGH"
    
    # Test MODERATE severity
    interactions_moderate = [{"severity": "MODERATE"}, {"severity": "LOW"}]
    assert agent._determine_severity(interactions_moderate) == "MODERATE"
    
    # Test LOW severity
    interactions_low = [{"severity": "INFORMATIONAL"}]
    assert agent._determine_severity(interactions_low) == "LOW"
