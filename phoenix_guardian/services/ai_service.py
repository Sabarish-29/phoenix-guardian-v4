"""Unified AI Service for Phoenix Guardian.

Provides a single interface for AI/LLM interactions with automatic failover:
    1. Groq Cloud API (primary) - Free tier, Llama 3.3 70B, ~8x faster
    2. Ollama (local fallback) - Llama 3.2 1B for offline use (CPU-friendly)

All 10 AI agents route through this service instead of calling Anthropic directly.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("phoenix_guardian.ai_service")


class UnifiedAIService:
    """Unified AI service with Groq primary + Ollama local fallback.

    Usage:
        service = UnifiedAIService()
        response = await service.chat("Analyze this fraud pattern...", system="You are a fraud analyst.")

    Environment Variables:
        GROQ_API_KEY: Groq Cloud API key (required for Groq)
        GROQ_MODEL: Groq model override (default: llama-3.3-70b-versatile)
        OLLAMA_BASE_URL: Ollama server URL (default: http://localhost:11434)
        OLLAMA_MODEL: Ollama model override (default: llama3.1:8b)
        AI_PROVIDER: Force a specific provider ("groq" or "ollama")
    """

    # Groq configuration
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
    GROQ_MAX_TOKENS = 4096
    GROQ_TIMEOUT = 30.0

    # Ollama configuration
    OLLAMA_DEFAULT_URL = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL = "llama3.2:1b"
    OLLAMA_TIMEOUT = 60.0

    def __init__(
        self,
        groq_api_key: Optional[str] = None,
        groq_model: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> None:
        """Initialize unified AI service.

        Args:
            groq_api_key: Groq API key (falls back to GROQ_API_KEY env var).
            groq_model: Override Groq model name.
            ollama_base_url: Ollama server URL override.
            ollama_model: Override Ollama model name.
            max_tokens: Maximum tokens for response generation.
            temperature: Sampling temperature (0.0-1.0).
        """
        # Groq setup
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self.groq_model = groq_model or os.getenv("GROQ_MODEL", self.GROQ_DEFAULT_MODEL)

        # Ollama setup
        self.ollama_base_url = (
            ollama_base_url or os.getenv("OLLAMA_BASE_URL", self.OLLAMA_DEFAULT_URL)
        ).rstrip("/")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL", self.OLLAMA_DEFAULT_MODEL)

        # Generation parameters
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Provider preference
        self._forced_provider = os.getenv("AI_PROVIDER", "").lower()

        # Metrics
        self._call_count = 0
        self._groq_successes = 0
        self._ollama_successes = 0
        self._total_latency_ms = 0.0

        # Determine available providers
        self._groq_available = bool(self.groq_api_key)
        if not self._groq_available:
            logger.warning("GROQ_API_KEY not set — Groq provider unavailable")

        logger.info(
            "UnifiedAIService initialized: groq=%s, ollama=%s, forced=%s",
            "available" if self._groq_available else "unavailable",
            self.ollama_base_url,
            self._forced_provider or "auto",
        )

    # ─── Public API ───────────────────────────────────────────────────────

    async def chat(
        self,
        prompt: str,
        system: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
    ) -> str:
        """Send a chat completion request with automatic failover.

        Tries Groq first (if available), then falls back to Ollama.

        Args:
            prompt: User message / prompt text.
            system: Optional system prompt.
            temperature: Override default temperature for this call.
            max_tokens: Override default max_tokens for this call.
            response_format: Set to "json" to request JSON output.

        Returns:
            The model's response text.

        Raises:
            RuntimeError: If all providers fail.
        """
        self._call_count += 1
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens or self.max_tokens

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        errors: List[str] = []

        # Determine provider order
        if self._forced_provider == "ollama":
            providers = [("ollama", self._call_ollama)]
        elif self._forced_provider == "groq":
            providers = [("groq", self._call_groq)]
        elif self._groq_available:
            providers = [("groq", self._call_groq), ("ollama", self._call_ollama)]
        else:
            providers = [("ollama", self._call_ollama)]

        for provider_name, call_fn in providers:
            start = time.perf_counter()
            try:
                result = await call_fn(messages, temp, tokens, response_format)
                elapsed_ms = (time.perf_counter() - start) * 1000
                self._total_latency_ms += elapsed_ms

                if provider_name == "groq":
                    self._groq_successes += 1
                else:
                    self._ollama_successes += 1

                logger.info(
                    "AI call succeeded: provider=%s, latency=%.0fms, total_calls=%d",
                    provider_name,
                    elapsed_ms,
                    self._call_count,
                )
                return result

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start) * 1000
                error_msg = f"{provider_name} failed ({elapsed_ms:.0f}ms): {e}"
                errors.append(error_msg)
                logger.warning("AI provider failed: %s", error_msg)

        raise RuntimeError(
            f"All AI providers failed after {len(errors)} attempts:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Return service metrics for monitoring dashboards.

        Returns:
            Dict with call counts, success rates, average latency.
        """
        avg_latency = (
            self._total_latency_ms / max(self._groq_successes + self._ollama_successes, 1)
        )
        return {
            "total_calls": self._call_count,
            "groq_successes": self._groq_successes,
            "ollama_successes": self._ollama_successes,
            "groq_available": self._groq_available,
            "avg_latency_ms": round(avg_latency, 1),
            "groq_model": self.groq_model,
            "ollama_model": self.ollama_model,
            "forced_provider": self._forced_provider or "auto",
        }

    # ─── Groq Provider ───────────────────────────────────────────────────

    async def _call_groq(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[str] = None,
    ) -> str:
        """Call Groq Cloud API (OpenAI-compatible endpoint).

        Args:
            messages: Chat messages list.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            response_format: Optional "json" for JSON mode.

        Returns:
            Response text from Groq.

        Raises:
            httpx.HTTPStatusError: On API errors.
            httpx.TimeoutException: On timeout.
        """
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.groq_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=self.GROQ_TIMEOUT) as client:
            resp = await client.post(
                self.GROQ_API_URL,
                headers=headers,
                json=payload,
            )
            if resp.status_code >= 400:
                error_body = resp.text[:500]
                logger.error("Groq API error %d: %s", resp.status_code, error_body)
                raise RuntimeError(f"Groq API {resp.status_code}: {error_body}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    # ─── Ollama Provider ──────────────────────────────────────────────────

    async def _call_ollama(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[str] = None,
    ) -> str:
        """Call local Ollama server.

        Args:
            messages: Chat messages list.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens (maps to num_predict).
            response_format: Optional "json" for JSON mode.

        Returns:
            Response text from Ollama.

        Raises:
            httpx.ConnectError: If Ollama is not running.
            httpx.HTTPStatusError: On API errors.
        """
        url = f"{self.ollama_base_url}/api/chat"

        payload: Dict[str, Any] = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_gpu": 0,
                "num_ctx": 512,
            },
        }

        if response_format == "json":
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=self.OLLAMA_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]

    # ─── Transcription (Groq Whisper) ─────────────────────────────────────

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "en",
    ) -> Dict[str, Any]:
        """Transcribe audio using Groq Whisper API.

        Args:
            audio_bytes: Raw audio file bytes.
            filename: Original filename for MIME type detection.
            language: ISO language code.

        Returns:
            Dict with 'text' and 'provider' keys.

        Raises:
            RuntimeError: If transcription fails.
        """
        if not self._groq_available:
            raise RuntimeError("Groq API key required for Whisper transcription")

        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.groq_api_key}"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                headers=headers,
                files={"file": (filename, audio_bytes)},
                data={
                    "model": "whisper-large-v3",
                    "language": language,
                    "response_format": "verbose_json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return {
            "text": data.get("text", ""),
            "segments": data.get("segments", []),
            "language": data.get("language", language),
            "duration": data.get("duration", 0),
            "provider": "groq-whisper",
        }


# ─── Singleton for shared use across the application ──────────────────────

_service_instance: Optional[UnifiedAIService] = None


def get_ai_service() -> UnifiedAIService:
    """Get or create the singleton AI service instance.

    Returns:
        The shared UnifiedAIService instance.
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = UnifiedAIService()
    return _service_instance


def reset_ai_service() -> None:
    """Reset the singleton instance (useful for testing or config changes)."""
    global _service_instance
    _service_instance = None
