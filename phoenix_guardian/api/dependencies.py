"""Dependency injection for FastAPI.

Provides singleton instances of agents and orchestrator.
"""

import os
from functools import lru_cache
from typing import Optional
from unittest.mock import MagicMock

from phoenix_guardian.agents.navigator_agent import NavigatorAgent
from phoenix_guardian.agents.safety_agent import SafetyAgent
from phoenix_guardian.api.utils.orchestrator import EncounterOrchestrator


@lru_cache()
def get_navigator() -> NavigatorAgent:
    """Get Navigator Agent singleton.

    Returns:
        NavigatorAgent instance configured with default settings
    """
    return NavigatorAgent()


@lru_cache()
def get_safety() -> SafetyAgent:
    """Get Safety Agent singleton.

    Returns:
        SafetyAgent instance configured with default security settings
    """
    return SafetyAgent()


@lru_cache()
def get_scribe():
    """Get Scribe Agent singleton.

    Returns:
        ScribeAgent instance configured with API key from environment,
        or a mock if API key is not available.

    Note:
        Requires ANTHROPIC_API_KEY environment variable to be set
        for real API calls. Returns mock for testing without API key.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key or api_key == "test-api-key-for-testing":
        # Return a mock for testing
        mock_scribe = MagicMock()
        mock_scribe.get_metrics.return_value = {
            "call_count": 0.0,
            "avg_execution_time_ms": 0.0,
            "total_execution_time_ms": 0.0,
        }
        return mock_scribe

    # Import here to avoid issues when API key not available
    from phoenix_guardian.agents.scribe_agent import ScribeAgent

    return ScribeAgent(api_key=api_key)


@lru_cache()
def get_orchestrator() -> EncounterOrchestrator:
    """Get Encounter Orchestrator singleton.

    Returns:
        EncounterOrchestrator instance with configured agents
    """
    return EncounterOrchestrator(
        navigator_agent=get_navigator(),
        scribe_agent=get_scribe(),
        safety_agent=get_safety(),
    )


def clear_dependency_cache() -> None:
    """Clear cached dependencies.

    Useful for testing when you need fresh instances.
    """
    get_navigator.cache_clear()
    get_safety.cache_clear()
    get_scribe.cache_clear()
    get_orchestrator.cache_clear()
