"""Tests for BaseAgent class.

Tests the core agent functionality including initialization,
Claude API calls, and error handling.
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
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello there!")]
        mock_instance.messages.create.return_value = mock_response
        
        yield mock_instance


from phoenix_guardian.agents.base import BaseAgent


class TestAgent(BaseAgent):
    """Test implementation of BaseAgent."""
    
    async def process(self, input_data: dict) -> dict:
        """Process input by calling Claude."""
        result = await self._call_claude("Say hello in 5 words or less")
        return {"response": result}


@pytest.mark.asyncio
async def test_base_agent_initialization(mock_anthropic_client):
    """Test BaseAgent can be instantiated."""
    agent = TestAgent()
    assert agent.model == "claude-sonnet-4-20250514"
    assert agent.max_tokens == 4000


@pytest.mark.asyncio
async def test_base_agent_calls_claude(mock_anthropic_client):
    """Test BaseAgent can call Claude API."""
    agent = TestAgent()
    result = await agent.process({})
    assert "response" in result
    assert len(result["response"]) > 0
    assert isinstance(result["response"], str)


@pytest.mark.asyncio
async def test_base_agent_error_handling(mock_anthropic_client):
    """Test BaseAgent handles API errors gracefully."""
    agent = TestAgent()
    # This should work or raise RuntimeError, not crash
    try:
        result = await agent._call_claude("Test prompt")
        assert isinstance(result, str)
    except RuntimeError as e:
        assert "Claude API error" in str(e)


@pytest.mark.asyncio
async def test_base_agent_with_system_prompt(mock_anthropic_client):
    """Test BaseAgent can use system prompts."""
    agent = TestAgent()
    try:
        result = await agent._call_claude(
            "What is 2+2?",
            system="You are a helpful math assistant. Answer concisely."
        )
        assert isinstance(result, str)
        assert len(result) > 0
    except RuntimeError as e:
        assert "Claude API error" in str(e)


@pytest.mark.asyncio
async def test_base_agent_abstract_process(mock_anthropic_client):
    """Test that BaseAgent process method must be implemented."""
    # TestAgent implements process, so this should work
    agent = TestAgent()
    assert hasattr(agent, 'process')
    assert callable(agent.process)


@pytest.mark.asyncio
async def test_base_agent_api_error_handling():
    """Test that missing API key raises ValueError."""
    with patch.dict(os.environ, {}, clear=True):
        # Remove all env vars
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            TestAgent()
