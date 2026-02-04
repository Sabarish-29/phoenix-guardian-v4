# ADR-019: Circuit Breaker Pattern for External Services

## Status
Accepted

## Date
Day 112 (Phase 3)

## Context

Phoenix Guardian integrates with multiple external services:
1. EHR systems (Epic, Cerner, etc.)
2. AI model APIs (OpenAI, Azure)
3. Translation services (DeepL)
4. Notification services (Twilio, SendGrid)

These services can experience:
- Temporary outages
- Latency spikes
- Rate limiting
- Complete failures

We need graceful degradation without cascading failures.

## Decision

We will implement the Circuit Breaker pattern using a custom implementation based on the standard three-state model.

### Circuit Breaker States

```
┌────────────────────────────────────────────────────────────────┐
│                  Circuit Breaker State Machine                  │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│                    ┌─────────────┐                              │
│                    │   CLOSED    │◄────────────────┐            │
│                    │  (normal)   │                 │            │
│                    └──────┬──────┘                 │            │
│                           │                        │            │
│                   failure threshold                │            │
│                   exceeded (5 in 30s)              │            │
│                           │                   success           │
│                           ▼                   threshold         │
│                    ┌─────────────┐            met (3)           │
│                    │    OPEN     │                 │            │
│                    │  (failing)  │                 │            │
│                    └──────┬──────┘                 │            │
│                           │                        │            │
│                    timeout (30s)                   │            │
│                           │                        │            │
│                           ▼                        │            │
│                    ┌─────────────┐                 │            │
│                    │ HALF-OPEN   │─────────────────┘            │
│                    │  (testing)  │                              │
│                    └─────────────┘                              │
│                           │                                     │
│                      failure                                    │
│                           │                                     │
│                           └─────────► OPEN                      │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Callable, TypeVar, Generic
import asyncio
from functools import wraps

T = TypeVar('T')

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_seconds: int = 30
    half_open_max_calls: int = 3

@dataclass
class CircuitBreakerStats:
    failures: int = 0
    successes: int = 0
    last_failure_time: Optional[datetime] = None
    state_changed_at: datetime = field(default_factory=datetime.utcnow)

class CircuitBreaker(Generic[T]):
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable[[], T]] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback = fallback
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable[[], T]) -> T:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to(CircuitState.HALF_OPEN)
                else:
                    return self._handle_open_circuit()
            
            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    return self._handle_open_circuit()
                self._half_open_calls += 1
        
        try:
            result = await func()
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure(e)
            raise
    
    async def _on_success(self):
        async with self._lock:
            self.stats.successes += 1
            
            if self.state == CircuitState.HALF_OPEN:
                if self.stats.successes >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self.state == CircuitState.CLOSED:
                self.stats.failures = 0  # Reset on success
    
    async def _on_failure(self, error: Exception):
        async with self._lock:
            self.stats.failures += 1
            self.stats.last_failure_time = datetime.utcnow()
            
            if self.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif self.state == CircuitState.CLOSED:
                if self.stats.failures >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
    
    def _should_attempt_reset(self) -> bool:
        elapsed = datetime.utcnow() - self.stats.state_changed_at
        return elapsed.total_seconds() >= self.config.timeout_seconds
    
    def _transition_to(self, new_state: CircuitState):
        self.state = new_state
        self.stats = CircuitBreakerStats(state_changed_at=datetime.utcnow())
        self._half_open_calls = 0
    
    def _handle_open_circuit(self) -> T:
        if self.fallback:
            return self.fallback()
        raise CircuitOpenError(f"Circuit {self.name} is open")


# Decorator usage
def circuit_protected(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
    fallback: Optional[Callable] = None
):
    breaker = CircuitBreaker(name, config, fallback)
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(lambda: func(*args, **kwargs))
        return wrapper
    return decorator


# Example usage
class EHRClient:
    @circuit_protected(
        name="epic_ehr",
        config=CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=60
        ),
        fallback=lambda: {"status": "cached", "data": get_cached_data()}
    )
    async def get_patient_data(self, patient_id: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{EHR_URL}/patients/{patient_id}") as resp:
                return await resp.json()
```

## Consequences

### Positive
- Prevents cascading failures
- Fast failure for known-bad services
- Automatic recovery attempts
- Fallback provides degraded functionality

### Negative
- Additional complexity
- Tuning thresholds is challenging
- May mask real issues during half-open

## References
- Martin Fowler: https://martinfowler.com/bliki/CircuitBreaker.html
- Release It! by Michael Nygard
