"""Base Agent Architecture for Phoenix Guardian AI Agents.

This module provides the foundational abstract class for all Phoenix Guardian
AI agents powered by the Unified AI Service (Groq + Ollama failover).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

from phoenix_guardian.services.ai_service import get_ai_service


class BaseAgent(ABC):
    """Base class for all AI agents.

    Provides common functionality for AI/LLM interaction via the Unified AI
    Service (Groq primary + Ollama local fallback) and establishes the
    contract that all agents must implement.

    Attributes:
        ai: UnifiedAIService instance (shared singleton)
        max_tokens: Maximum tokens for API response
    """

    def __init__(self):
        """Initialize the base agent with the Unified AI service."""
        self.ai = get_ai_service()
        self.max_tokens = 4000

    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input and return result.

        Args:
            input_data: Dictionary with agent-specific input data

        Returns:
            Dictionary with agent-specific output data
        """
        pass

    async def _call_claude(self, prompt: str, system: str = "") -> str:
        """Call AI service with error handling.

        Maintained as ``_call_claude`` for backward compatibility — all child
        agents call this method by name.  Internally delegates to the
        UnifiedAIService (Groq → Ollama failover).

        Args:
            prompt: User prompt to send to the AI model
            system: Optional system prompt

        Returns:
            The model's response text

        Raises:
            RuntimeError: If all AI providers fail
        """
        try:
            # Auto-detect JSON mode: only use if the prompt mentions JSON
            fmt = None
            combined = (prompt + system).lower()
            if "json" in combined:
                fmt = "json"

            return await self.ai.chat(
                prompt=prompt,
                system=system,
                max_tokens=self.max_tokens,
                response_format=fmt,
            )
        except Exception as e:
            raise RuntimeError(f"AI service error: {e}")
