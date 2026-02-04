"""Base Agent Architecture for Phoenix Guardian.

This module provides the foundational abstract class that all Phoenix
Guardian agents inherit from, ensuring consistent execution patterns,
error handling, and metrics tracking.

Classes:
    AgentResult: Standardized result format for all agent executions
    BaseAgent: Abstract base class for all Phoenix Guardian agents
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Dict, Optional


@dataclass
class AgentResult:
    """Standardized result format for agent execution.

    This dataclass ensures all agents return consistent output that can be
    chained in LangGraph workflows and logged for audit trails.

    Attributes:
        success: Whether the agent execution completed successfully
        data: Agent-specific output data (e.g., SOAP note, detection results)
        error: Error message if execution failed, None otherwise
        execution_time_ms: Total execution time in milliseconds
        reasoning: Explanation of agent's decision-making process (for transparency)
    """

    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    execution_time_ms: float
    reasoning: str


class BaseAgent(ABC):
    """Base class for all Phoenix Guardian agents.

    This abstract class provides:
    - Standardized execution flow with timing
    - Automatic error handling and recovery
    - Performance metrics tracking
    - Consistent logging structure

    All agents (Scribe, Navigator, Safety) inherit from this class
    and implement the _run() method with their specific logic.

    Attributes:
        name: Human-readable agent identifier
        call_count: Total number of times execute() has been called
        total_execution_time_ms: Cumulative execution time across all calls

    Example:
        >>> class MyAgent(BaseAgent):
        ...     async def _run(
        ...         self, context: Dict[str, Any]
        ...     ) -> Dict[str, Any]:
        ...         return {
        ...             'data': {'result': 'success'},
        ...             'reasoning': 'Processed input'
        ...         }
        ...
        >>> agent = MyAgent(name="MyAgent")
        >>> result = await agent.execute({'input': 'test'})
        >>> print(result.success)  # True
        >>> print(agent.get_metrics())  # {'call_count': 1, ...}
    """

    def __init__(self, name: str) -> None:
        """Initialize the base agent with metrics tracking.

        Args:
            name: Human-readable identifier for this agent
                  (e.g., "Scribe", "Safety")

        Raises:
            ValueError: If name is empty or contains only whitespace
        """
        if not name or not name.strip():
            raise ValueError("Agent name cannot be empty")

        self.name: str = name.strip()
        self.call_count: int = 0
        self.total_execution_time_ms: float = 0.0

    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Execute the agent with timing, error handling, and metrics tracking.

        This method wraps the agent-specific _run() implementation with:
        1. Performance timing (in milliseconds)
        2. Automatic error capture and formatting
        3. Metrics tracking (call count, execution time)
        4. Standardized AgentResult output

        Args:
            context: Input data for the agent. Structure varies by agent type.
                    Common keys: 'transcript', 'patient_history', 'soap_note'

        Returns:
            AgentResult with success=True and populated data field on success,
            or success=False with error message on failure.

        Example:
            >>> context = {'transcript': 'Patient reports headache...'}
            >>> result = await agent.execute(context)
            >>> if result.success:
            ...     print(f"Data: {result.data}")
            ... else:
            ...     print(f"Error: {result.error}")
        """
        # Start high-resolution timer
        start_time = perf_counter()

        # Increment call counter for metrics
        self.call_count += 1

        try:
            # Call agent-specific implementation
            result_dict = await self._run(context)

            # Calculate execution time in milliseconds
            execution_time_ms = (perf_counter() - start_time) * 1000
            self.total_execution_time_ms += execution_time_ms

            # Extract data and reasoning from result
            data = result_dict.get("data")
            reasoning = result_dict.get("reasoning", "No reasoning provided")

            return AgentResult(
                success=True,
                data=data,
                error=None,
                execution_time_ms=execution_time_ms,
                reasoning=reasoning,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            # Calculate execution time even on failure
            execution_time_ms = (perf_counter() - start_time) * 1000
            self.total_execution_time_ms += execution_time_ms

            # Format error message without exposing stack traces
            error_type = type(e).__name__
            error_message = str(e)
            formatted_error = f"{error_type}: {error_message}"

            # Log error with agent name for debugging
            # Logger will be injected in Phase 1 Week 2

            return AgentResult(
                success=False,
                data=None,
                error=formatted_error,
                execution_time_ms=execution_time_ms,
                reasoning=f"Execution failed: {error_type}",
            )

    @abstractmethod
    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Implement agent-specific logic here.

        This method must be implemented by all child classes. It contains the
        core functionality of the agent (e.g., calling Claude API, detecting
        adversarial prompts, fetching patient data).

        Args:
            context: Input data specific to the agent's purpose

        Returns:
            Dict with two keys:
                - 'data': Agent-specific output (Dict[str, Any])
                - 'reasoning': Explanation of decisions made (str)

        Raises:
            NotImplementedError: If child class doesn't implement method
            Any exception: Child classes should raise specific exceptions

        Example Implementation:
            >>> async def _run(
            ...     self, context: Dict[str, Any]
            ... ) -> Dict[str, Any]:
            ...     result = await some_async_operation(
            ...         context['input']
            ...     )
            ...     return {
            ...         'data': {'output': result},
            ...         'reasoning': 'Processed input using algorithm X'
            ...     }
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _run() method"
        )

    def get_metrics(self) -> Dict[str, float]:
        """Return performance metrics for monitoring and optimization.

        These metrics are used by:
        - LangGraph orchestrator to detect slow agents
        - CloudWatch dashboards for performance monitoring
        - Load testing to identify bottlenecks

        Returns:
            Dict containing:
                - call_count: Total number of execute() invocations
                - avg_execution_time_ms: Average time per execution
                - total_execution_time_ms: Cumulative execution time

        Example:
            >>> agent = ScribeAgent()
            >>> await agent.execute({'transcript': '...'})
            >>> metrics = agent.get_metrics()
            >>> print(f"Average time: {metrics['avg_execution_time_ms']:.2f}ms")
        """
        avg_execution_time_ms = (
            self.total_execution_time_ms / self.call_count
            if self.call_count > 0
            else 0.0
        )

        return {
            "call_count": float(self.call_count),
            "avg_execution_time_ms": avg_execution_time_ms,
            "total_execution_time_ms": self.total_execution_time_ms,
        }
