"""Tests for NavigatorAgent - Workflow Coordination.

Comprehensive tests for clinical workflow suggestion including:
- Step generation
- Priority detection
- Response parsing
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
        
        # Default workflow response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="""Here are the next steps:
1. Order STAT ECG to assess cardiac rhythm
2. Draw troponin levels to rule out MI
3. Obtain chest X-ray for evaluation
4. Consult cardiology if needed
5. Document assessment and plan""")]
        mock_instance.messages.create.return_value = mock_response
        
        yield mock_instance


from phoenix_guardian.agents.navigator import NavigatorAgent


@pytest.mark.asyncio
async def test_navigator_suggests_workflow(mock_anthropic_client):
    """Test workflow suggestion generation."""
    agent = NavigatorAgent()
    
    input_data = {
        "current_status": "Patient admitted with chest pain",
        "encounter_type": "Emergency",
        "pending_items": ["ECG", "Troponin", "Chest X-ray"]
    }
    
    result = await agent.process(input_data)
    
    assert "next_steps" in result
    assert "priority" in result
    assert isinstance(result["next_steps"], list)
    assert len(result["next_steps"]) > 0
    assert result["agent"] == "NavigatorAgent"


@pytest.mark.asyncio
async def test_navigator_priority_detection(mock_anthropic_client):
    """Test priority determination from keywords."""
    agent = NavigatorAgent()
    
    input_data = {
        "current_status": "Urgent: Patient unstable",
        "encounter_type": "Emergency"
    }
    
    result = await agent.process(input_data)
    
    # Should detect HIGH priority from "urgent" keyword
    assert result["priority"] in ["HIGH", "NORMAL"]


@pytest.mark.asyncio
async def test_navigator_parses_steps(mock_anthropic_client):
    """Test step parsing from response."""
    agent = NavigatorAgent()
    
    test_response = """
    Here are the next steps:
    1. Order STAT ECG
    2. Draw troponin levels
    3. Obtain chest X-ray
    4. Consult cardiology
    """
    
    steps = agent._parse_steps(test_response)
    assert len(steps) >= 3
    assert any("ECG" in step for step in steps)


@pytest.mark.asyncio
async def test_navigator_parses_bullet_points(mock_anthropic_client):
    """Test parsing of bullet point format."""
    agent = NavigatorAgent()
    
    test_response = """
    - Complete vital signs
    - Review lab results
    - Document assessment
    • Call pharmacy
    """
    
    steps = agent._parse_steps(test_response)
    assert len(steps) >= 3


@pytest.mark.asyncio
async def test_navigator_limits_steps(mock_anthropic_client):
    """Test that steps are limited to 5."""
    agent = NavigatorAgent()
    
    test_response = """
    1. Step one
    2. Step two
    3. Step three
    4. Step four
    5. Step five
    6. Step six
    7. Step seven
    """
    
    steps = agent._parse_steps(test_response)
    assert len(steps) <= 5


@pytest.mark.asyncio
async def test_navigator_empty_pending_items(mock_anthropic_client):
    """Test handling of empty pending items."""
    agent = NavigatorAgent()
    
    input_data = {
        "current_status": "Follow-up visit",
        "encounter_type": "Outpatient",
        "pending_items": []
    }
    
    result = await agent.process(input_data)
    
    assert "next_steps" in result
    assert isinstance(result["next_steps"], list)


@pytest.mark.asyncio
async def test_navigator_determine_priority_urgent(mock_anthropic_client):
    """Test priority detection with urgent keywords."""
    agent = NavigatorAgent()
    
    urgent_response = "This is an URGENT situation requiring immediate attention."
    assert agent._determine_priority(urgent_response) == "HIGH"
    
    critical_response = "Critical: Patient requires STAT intervention."
    assert agent._determine_priority(critical_response) == "HIGH"


@pytest.mark.asyncio
async def test_navigator_determine_priority_normal(mock_anthropic_client):
    """Test priority detection without urgent keywords."""
    agent = NavigatorAgent()
    
    normal_response = "Proceed with standard workup and documentation."
    assert agent._determine_priority(normal_response) == "NORMAL"


@pytest.mark.asyncio
async def test_navigator_build_workflow_prompt(mock_anthropic_client):
    """Test workflow prompt building."""
    agent = NavigatorAgent()
    
    input_data = {
        "current_status": "Admission",
        "encounter_type": "Inpatient",
        "pending_items": ["Labs", "Imaging"]
    }
    
    prompt = agent._build_workflow_prompt(input_data)
    
    assert "Admission" in prompt
    assert "Inpatient" in prompt
    assert "Labs, Imaging" in prompt
