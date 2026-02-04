"""Base Agent Architecture for Phoenix Guardian AI Agents.

This module provides the foundational abstract class for all Phoenix Guardian
AI agents powered by Claude Sonnet 4.
"""

from abc import ABC, abstractmethod
from anthropic import Anthropic
import os
from typing import Dict, Any


class BaseAgent(ABC):
    """Base class for all AI agents.
    
    Provides common functionality for Claude API interaction and establishes
    the contract that all agents must implement.
    
    Attributes:
        client: Anthropic API client instance
        model: Claude model identifier
        max_tokens: Maximum tokens for API response
    """
    
    def __init__(self):
        """Initialize the base agent with Claude API client.
        
        Raises:
            ValueError: If ANTHROPIC_API_KEY environment variable not set
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
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
        """Call Claude API with error handling.
        
        Args:
            prompt: User prompt to send to Claude
            system: Optional system prompt
            
        Returns:
            Claude's response text
            
        Raises:
            RuntimeError: If API call fails
        """
        try:
            message_params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            if system:
                message_params["system"] = system
            
            response = self.client.messages.create(**message_params)
            return response.content[0].text
        except Exception as e:
            raise RuntimeError(f"Claude API error: {e}")
