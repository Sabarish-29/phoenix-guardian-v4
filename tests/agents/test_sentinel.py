"""Tests for SentinelAgent - Security Threat Detection.

Comprehensive tests for security analysis including:
- XSS detection
- SQL injection detection
- Path traversal detection
- Safe input handling
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
        
        # Default safe response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="NO - This appears to be normal medical text with no security threats.")]
        mock_instance.messages.create.return_value = mock_response
        
        yield mock_instance


from phoenix_guardian.agents.sentinel import SentinelAgent


@pytest.mark.asyncio
async def test_sentinel_detects_xss(mock_anthropic_client):
    """Test XSS attack detection."""
    agent = SentinelAgent()
    
    input_data = {
        "user_input": "<script>alert('XSS')</script>"
    }
    
    result = await agent.process(input_data)
    
    assert result["threat_detected"] is True
    assert result["threat_type"] == "XSS_ATTEMPT"
    assert result["confidence"] > 0.9


@pytest.mark.asyncio
async def test_sentinel_detects_sql_injection(mock_anthropic_client):
    """Test SQL injection detection."""
    agent = SentinelAgent()
    
    input_data = {
        "user_input": "admin'; DROP TABLE users; --"
    }
    
    result = await agent.process(input_data)
    
    assert result["threat_detected"] is True
    assert result["threat_type"] == "SQL_INJECTION"


@pytest.mark.asyncio
async def test_sentinel_detects_path_traversal(mock_anthropic_client):
    """Test path traversal detection."""
    agent = SentinelAgent()
    
    input_data = {
        "user_input": "../../etc/passwd"
    }
    
    result = await agent.process(input_data)
    
    assert result["threat_detected"] is True
    assert result["threat_type"] == "PATH_TRAVERSAL"


@pytest.mark.asyncio
async def test_sentinel_safe_input(mock_anthropic_client):
    """Test that safe input is not flagged."""
    agent = SentinelAgent()
    
    input_data = {
        "user_input": "Patient presents with chest pain and fever"
    }
    
    result = await agent.process(input_data)
    
    # Should not detect threat in normal medical text
    assert result["threat_detected"] is False


@pytest.mark.asyncio
async def test_sentinel_pattern_check(mock_anthropic_client):
    """Test pattern checking method."""
    agent = SentinelAgent()
    
    # Should detect
    result = agent._pattern_check("<script>alert(1)</script>")
    assert result["threat_detected"] is True
    
    # Should not detect
    result = agent._pattern_check("Normal text")
    assert result["threat_detected"] is False


@pytest.mark.asyncio
async def test_sentinel_credential_probe(mock_anthropic_client):
    """Test credential probing detection."""
    agent = SentinelAgent()
    
    input_data = {
        "user_input": "admin password reset"
    }
    
    result = await agent.process(input_data)
    
    assert result["threat_detected"] is True
    assert result["threat_type"] == "CREDENTIAL_PROBE"


@pytest.mark.asyncio
async def test_sentinel_empty_input(mock_anthropic_client):
    """Test handling of empty input."""
    agent = SentinelAgent()
    
    input_data = {
        "user_input": ""
    }
    
    result = await agent.process(input_data)
    
    assert result["threat_detected"] is False


@pytest.mark.asyncio
async def test_sentinel_case_insensitive(mock_anthropic_client):
    """Test that pattern matching is case insensitive."""
    agent = SentinelAgent()
    
    input_data = {
        "user_input": "<SCRIPT>alert('xss')</SCRIPT>"
    }
    
    result = await agent.process(input_data)
    
    assert result["threat_detected"] is True
    assert result["threat_type"] == "XSS_ATTEMPT"


@pytest.mark.asyncio
async def test_sentinel_sql_injection_comment(mock_anthropic_client):
    """Test SQL injection with comment syntax."""
    agent = SentinelAgent()
    
    input_data = {
        "user_input": "'; -- comment"
    }
    
    result = await agent.process(input_data)
    
    assert result["threat_detected"] is True
    assert result["threat_type"] == "SQL_INJECTION"


@pytest.mark.asyncio
async def test_sentinel_multiple_threats(mock_anthropic_client):
    """Test input with multiple threat patterns."""
    agent = SentinelAgent()
    
    # First pattern match should be returned
    input_data = {
        "user_input": "<script>alert(1)</script>'; DROP TABLE users; --"
    }
    
    result = await agent.process(input_data)
    
    assert result["threat_detected"] is True
    # Should match first pattern (XSS)
    assert result["threat_type"] in ["XSS_ATTEMPT", "SQL_INJECTION"]


@pytest.mark.asyncio
async def test_sentinel_agent_attribution(mock_anthropic_client):
    """Test that agent name is included in result."""
    agent = SentinelAgent()
    
    input_data = {
        "user_input": "Safe medical text"
    }
    
    result = await agent.process(input_data)
    
    assert result["agent"] == "SentinelAgent"
