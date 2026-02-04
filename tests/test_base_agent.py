"""Unit tests for BaseAgent and AgentResult classes.

Tests cover:
- Successful agent execution
- Error handling and recovery
- Metrics tracking accuracy
- Abstract method enforcement
- Input validation
"""

import pytest
from typing import Any, Dict
from phoenix_guardian.agents.base_agent import BaseAgent, AgentResult


class MockSuccessAgent(BaseAgent):
    """Mock agent that always succeeds for testing."""
    
    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return mock data based on input."""
        result_data = {
            'output': context.get('input', 'default'),
            'processed': True
        }
        return {
            'data': result_data,
            'reasoning': 'Successfully processed input data'
        }


class MockFailureAgent(BaseAgent):
    """Mock agent that always raises an exception."""
    
    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Always raise a ValueError."""
        raise ValueError("Simulated agent failure")


class MockSlowAgent(BaseAgent):
    """Mock agent that simulates slow execution."""
    
    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate processing time."""
        import asyncio
        await asyncio.sleep(0.1)  # 100ms delay
        return {
            'data': {'completed': True},
            'reasoning': 'Slow operation completed'
        }


# Test Agent Initialization

def test_agent_initialization_valid_name():
    """Test agent can be initialized with valid name."""
    agent = MockSuccessAgent(name="TestAgent")
    assert agent.name == "TestAgent"
    assert agent.call_count == 0
    assert agent.total_execution_time_ms == 0.0


def test_agent_initialization_strips_whitespace():
    """Test agent name is trimmed of leading/trailing whitespace."""
    agent = MockSuccessAgent(name="  TestAgent  ")
    assert agent.name == "TestAgent"


def test_agent_initialization_empty_name_raises_error():
    """Test that empty agent name raises ValueError."""
    with pytest.raises(ValueError, match="Agent name cannot be empty"):
        MockSuccessAgent(name="")


def test_agent_initialization_whitespace_only_name_raises_error():
    """Test that whitespace-only name raises ValueError."""
    with pytest.raises(ValueError, match="Agent name cannot be empty"):
        MockSuccessAgent(name="   ")


# Test Successful Execution

@pytest.mark.asyncio
async def test_successful_agent_execution():
    """Test agent executes successfully and returns correct result."""
    agent = MockSuccessAgent(name="TestAgent")
    context = {'input': 'test_data'}
    
    result = await agent.execute(context)
    
    assert result.success is True
    assert result.error is None
    assert result.data is not None
    assert result.data['output'] == 'test_data'
    assert result.data['processed'] is True
    assert result.reasoning == 'Successfully processed input data'
    assert result.execution_time_ms > 0


@pytest.mark.asyncio
async def test_execution_increments_call_count():
    """Test that each execution increments the call counter."""
    agent = MockSuccessAgent(name="TestAgent")
    
    assert agent.call_count == 0
    
    await agent.execute({'input': 'test1'})
    assert agent.call_count == 1
    
    await agent.execute({'input': 'test2'})
    assert agent.call_count == 2
    
    await agent.execute({'input': 'test3'})
    assert agent.call_count == 3


@pytest.mark.asyncio
async def test_execution_tracks_time_correctly():
    """Test that execution time is measured and accumulated."""
    agent = MockSlowAgent(name="SlowAgent")
    
    result = await agent.execute({'input': 'test'})
    
    # Should take at least 100ms (we sleep for 0.1s)
    assert result.execution_time_ms >= 100
    assert agent.total_execution_time_ms >= 100


# Test Error Handling

@pytest.mark.asyncio
async def test_agent_failure_returns_error_result():
    """Test that exceptions are caught and returned as AgentResult."""
    agent = MockFailureAgent(name="FailAgent")
    
    result = await agent.execute({'input': 'test'})
    
    assert result.success is False
    assert result.data is None
    assert result.error is not None
    assert "ValueError" in result.error
    assert "Simulated agent failure" in result.error
    assert result.reasoning == "Execution failed: ValueError"


@pytest.mark.asyncio
async def test_error_still_increments_metrics():
    """Test that failed executions still update metrics."""
    agent = MockFailureAgent(name="FailAgent")
    
    result = await agent.execute({'input': 'test'})
    
    assert agent.call_count == 1
    assert agent.total_execution_time_ms > 0
    assert result.execution_time_ms > 0


@pytest.mark.asyncio
async def test_multiple_failures_tracked():
    """Test that multiple failures are properly tracked in metrics."""
    agent = MockFailureAgent(name="FailAgent")
    
    result1 = await agent.execute({'input': 'test1'})
    result2 = await agent.execute({'input': 'test2'})
    
    assert agent.call_count == 2
    assert result1.success is False
    assert result2.success is False


# Test Metrics

def test_get_metrics_initial_state():
    """Test metrics return zeros for new agent."""
    agent = MockSuccessAgent(name="TestAgent")
    metrics = agent.get_metrics()
    
    assert metrics['call_count'] == 0
    assert metrics['avg_execution_time_ms'] == 0.0
    assert metrics['total_execution_time_ms'] == 0.0


@pytest.mark.asyncio
async def test_get_metrics_after_execution():
    """Test metrics are correctly calculated after execution."""
    agent = MockSuccessAgent(name="TestAgent")
    
    await agent.execute({'input': 'test'})
    metrics = agent.get_metrics()
    
    assert metrics['call_count'] == 1
    assert metrics['avg_execution_time_ms'] > 0
    assert metrics['total_execution_time_ms'] > 0
    assert metrics['avg_execution_time_ms'] == metrics['total_execution_time_ms']


@pytest.mark.asyncio
async def test_get_metrics_average_calculation():
    """Test average execution time is calculated correctly."""
    agent = MockSuccessAgent(name="TestAgent")
    
    # Execute multiple times
    await agent.execute({'input': 'test1'})
    await agent.execute({'input': 'test2'})
    await agent.execute({'input': 'test3'})
    
    metrics = agent.get_metrics()
    
    assert metrics['call_count'] == 3
    expected_avg = metrics['total_execution_time_ms'] / 3
    assert abs(metrics['avg_execution_time_ms'] - expected_avg) < 0.01


# Test Abstract Method Enforcement

def test_cannot_instantiate_base_agent_directly():
    """Test that BaseAgent cannot be instantiated without implementing _run."""
    with pytest.raises(TypeError):
        BaseAgent(name="Test")  # type: ignore


def test_agent_without_run_implementation_fails():
    """Test that agent without _run implementation raises error on execution."""
    class IncompleteAgent(BaseAgent):
        pass  # Doesn't implement _run()
    
    # Cannot instantiate due to abstract method
    with pytest.raises(TypeError):
        IncompleteAgent(name="Incomplete")  # type: ignore


# Test AgentResult Dataclass

def test_agent_result_creation():
    """Test AgentResult can be created with all fields."""
    result = AgentResult(
        success=True,
        data={'key': 'value'},
        error=None,
        execution_time_ms=123.45,
        reasoning='Test reasoning'
    )
    
    assert result.success is True
    assert result.data == {'key': 'value'}
    assert result.error is None
    assert result.execution_time_ms == 123.45
    assert result.reasoning == 'Test reasoning'


def test_agent_result_with_error():
    """Test AgentResult for error cases."""
    result = AgentResult(
        success=False,
        data=None,
        error='ValueError: Test error',
        execution_time_ms=50.0,
        reasoning='Execution failed: ValueError'
    )
    
    assert result.success is False
    assert result.data is None
    assert result.error == 'ValueError: Test error'


# Integration Tests

@pytest.mark.asyncio
async def test_multiple_agents_independent_metrics():
    """Test that different agent instances track metrics independently."""
    agent1 = MockSuccessAgent(name="Agent1")
    agent2 = MockSuccessAgent(name="Agent2")
    
    await agent1.execute({'input': 'test1'})
    await agent1.execute({'input': 'test2'})
    await agent2.execute({'input': 'test3'})
    
    metrics1 = agent1.get_metrics()
    metrics2 = agent2.get_metrics()
    
    assert metrics1['call_count'] == 2
    assert metrics2['call_count'] == 1


@pytest.mark.asyncio
async def test_agent_execution_with_empty_context():
    """Test agent handles empty context dict."""
    agent = MockSuccessAgent(name="TestAgent")
    
    result = await agent.execute({})
    
    assert result.success is True
    assert result.data['output'] == 'default'


@pytest.mark.asyncio
async def test_agent_execution_with_complex_context():
    """Test agent handles complex nested context data."""
    agent = MockSuccessAgent(name="TestAgent")
    context = {
        'input': 'complex_test',
        'patient_history': {
            'age': 45,
            'conditions': ['hypertension', 'diabetes']
        },
        'metadata': {
            'timestamp': '2026-01-30T10:00:00Z',
            'physician_id': 'DR123'
        }
    }
    
    result = await agent.execute(context)
    
    assert result.success is True
    assert result.data['output'] == 'complex_test'


# Performance Tests

@pytest.mark.asyncio
async def test_execution_time_measurement_accuracy():
    """Test that execution time is measured accurately."""
    agent = MockSlowAgent(name="SlowAgent")
    
    result = await agent.execute({'input': 'test'})
    
    # Should be at least 100ms (we sleep for 0.1s) but less than 200ms
    assert 100 <= result.execution_time_ms <= 200


@pytest.mark.asyncio
async def test_concurrent_execution_metrics():
    """Test metrics are correct when same agent runs concurrently."""
    import asyncio
    agent = MockSuccessAgent(name="TestAgent")
    
    # Run 5 executions concurrently
    tasks = [
        agent.execute({'input': f'test{i}'})
        for i in range(5)
    ]
    results = await asyncio.gather(*tasks)
    
    # All should succeed
    assert all(r.success for r in results)
    
    # Call count should be 5
    metrics = agent.get_metrics()
    assert metrics['call_count'] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
