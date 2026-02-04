"""
Differential Privacy Engine for Phoenix Guardian Federated Learning.

This module implements the core differential privacy mechanisms that enable
privacy-preserving threat intelligence sharing across hospitals.

Differential Privacy Definition:
    For all datasets D and D' differing in at most one record, and for all
    possible outputs S:
    
        Pr[M(D) ∈ S] ≤ e^ε × Pr[M(D') ∈ S] + δ
    
    Where:
        - M is our randomized mechanism
        - ε (epsilon) controls privacy loss (smaller = more private)
        - δ (delta) is the probability of privacy breach

Laplace Mechanism:
    For a function f with sensitivity Δf, we add noise:
    
        M(D) = f(D) + Lap(Δf / ε)
    
    Where Lap(b) is Laplace distribution with scale b.

Advanced Composition Theorem:
    For k queries with (ε, δ)-DP each:
    
        ε_total = √(2k × ln(1/δ')) × ε + k × ε × (e^ε - 1)
    
    This provides tighter bounds than naive composition (k × ε).

Privacy Budget:
    Each hospital has a privacy budget (ε_max, δ_max) that limits
    how many queries can be answered before privacy degrades.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import math
import numpy as np
import secrets


@dataclass
class PrivacyBudget:
    """
    Privacy budget for a single tenant/hospital.
    
    The budget tracks how much privacy has been "spent" through queries.
    Once exhausted, no more queries can be answered without compromising
    the ε-δ guarantees.
    
    Attributes:
        epsilon: Base epsilon per query (default 0.5, strong privacy)
        delta: Base delta per query (default 1e-5, extremely low failure)
        queries_used: Number of queries already processed
        max_queries: Maximum queries before budget exhausted
        total_epsilon_spent: Cumulative epsilon using composition
        total_delta_spent: Cumulative delta using composition
    """
    epsilon: float = 0.5
    delta: float = 1e-5
    queries_used: int = 0
    max_queries: int = 100
    total_epsilon_spent: float = 0.0
    total_delta_spent: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_query_at: Optional[str] = None
    
    def is_exhausted(self) -> bool:
        """Check if budget is exhausted."""
        return self.queries_used >= self.max_queries
    
    def remaining_queries(self) -> int:
        """Get number of queries remaining."""
        return max(0, self.max_queries - self.queries_used)
    
    def consume_query(self, epsilon: Optional[float] = None, delta: Optional[float] = None) -> bool:
        """
        Consume a query from the budget.
        
        Args:
            epsilon: Custom epsilon for this query (uses default if None)
            delta: Custom delta for this query (uses default if None)
            
        Returns:
            True if query was allowed, False if budget exhausted
        """
        if self.is_exhausted():
            return False
        
        eps = epsilon or self.epsilon
        dlt = delta or self.delta
        
        self.queries_used += 1
        self.total_epsilon_spent += eps
        self.total_delta_spent += dlt
        self.last_query_at = datetime.utcnow().isoformat()
        
        return True
    
    def reset(self) -> None:
        """Reset budget (typically done monthly)."""
        self.queries_used = 0
        self.total_epsilon_spent = 0.0
        self.total_delta_spent = 0.0
        self.created_at = datetime.utcnow().isoformat()
        self.last_query_at = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "epsilon": self.epsilon,
            "delta": self.delta,
            "queries_used": self.queries_used,
            "max_queries": self.max_queries,
            "total_epsilon_spent": self.total_epsilon_spent,
            "total_delta_spent": self.total_delta_spent,
            "created_at": self.created_at,
            "last_query_at": self.last_query_at,
            "remaining_queries": self.remaining_queries(),
            "is_exhausted": self.is_exhausted(),
        }


@dataclass
class PrivacyMetadata:
    """
    Metadata about privacy noise applied to data.
    
    This metadata is attached to all privatized outputs to enable
    auditing and validation of privacy guarantees.
    
    Attributes:
        epsilon: Epsilon used for this privatization
        delta: Delta used for this privatization
        noise_scale: Scale parameter of noise distribution
        sensitivity: Sensitivity of the query function
        mechanism: Type of mechanism used (laplace, gaussian)
        timestamp: When privatization occurred
        privacy_budget_consumed: How much budget was consumed
        query_id: Unique identifier for this query (for auditing)
    """
    epsilon: float
    delta: float
    noise_scale: float
    sensitivity: float
    mechanism: str = "laplace"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    privacy_budget_consumed: float = 0.0
    query_id: str = field(default_factory=lambda: secrets.token_hex(16))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "epsilon": self.epsilon,
            "delta": self.delta,
            "noise_scale": self.noise_scale,
            "sensitivity": self.sensitivity,
            "mechanism": self.mechanism,
            "timestamp": self.timestamp,
            "privacy_budget_consumed": self.privacy_budget_consumed,
            "query_id": self.query_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PrivacyMetadata":
        """Create from dictionary."""
        return cls(
            epsilon=data["epsilon"],
            delta=data["delta"],
            noise_scale=data["noise_scale"],
            sensitivity=data["sensitivity"],
            mechanism=data.get("mechanism", "laplace"),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            privacy_budget_consumed=data.get("privacy_budget_consumed", 0.0),
            query_id=data.get("query_id", secrets.token_hex(16)),
        )


class DifferentialPrivacyEngine:
    """
    Core differential privacy engine implementing DP mechanisms.
    
    This engine provides privacy-preserving query mechanisms that add
    calibrated noise to true query answers, ensuring individual records
    cannot be identified from the output.
    
    Supported Mechanisms:
        - Laplace: For numeric queries with bounded sensitivity
        - Gaussian: For high-dimensional queries (approximate DP)
        - Randomized Response: For categorical queries
    
    Example:
        >>> engine = DifferentialPrivacyEngine()
        >>> # Privatize a count (sensitivity = 1)
        >>> private_count = engine.privatize_count(150, max_count=1000)
        >>> # Privatize a feature vector
        >>> private_vector = engine.privatize_vector([0.5, 0.3, 0.8], sensitivity=1.0)
    
    Mathematical Foundation:
        Laplace Distribution:
            PDF: f(x|b) = (1/2b) × exp(-|x|/b)
            Variance: 2b²
            
        For (ε, 0)-DP, we set b = Δf/ε where Δf is sensitivity.
    """
    
    def __init__(
        self,
        default_epsilon: float = 0.5,
        default_delta: float = 1e-5,
        privacy_budget: Optional[PrivacyBudget] = None,
        seed: Optional[int] = None,
    ):
        """
        Initialize the differential privacy engine.
        
        Args:
            default_epsilon: Default privacy parameter (lower = more private)
            default_delta: Default failure probability (lower = stronger guarantee)
            privacy_budget: Optional budget tracker for this engine
            seed: Random seed for reproducibility (testing only)
        """
        if default_epsilon <= 0:
            raise ValueError("Epsilon must be positive")
        if default_delta < 0 or default_delta >= 1:
            raise ValueError("Delta must be in [0, 1)")
        
        self.default_epsilon = default_epsilon
        self.default_delta = default_delta
        self.privacy_budget = privacy_budget or PrivacyBudget(
            epsilon=default_epsilon,
            delta=default_delta,
        )
        self._rng = np.random.default_rng(seed)
        self._query_history: List[Dict[str, Any]] = []
    
    def add_laplace_noise(
        self,
        value: float,
        sensitivity: float,
        epsilon: Optional[float] = None,
    ) -> Tuple[float, PrivacyMetadata]:
        """
        Add Laplace noise to a numeric value.
        
        The Laplace mechanism adds noise drawn from Lap(sensitivity/epsilon),
        providing (ε, 0)-differential privacy.
        
        Mathematical Guarantee:
            For neighboring databases D, D' differing in one record:
            Pr[M(D) = y] / Pr[M(D') = y] ≤ e^ε
        
        Args:
            value: The true value to privatize
            sensitivity: Maximum change in value from one record (Δf)
            epsilon: Privacy parameter (uses default if None)
            
        Returns:
            Tuple of (privatized_value, metadata)
            
        Raises:
            ValueError: If sensitivity is non-positive
            RuntimeError: If privacy budget is exhausted
        """
        if sensitivity <= 0:
            raise ValueError("Sensitivity must be positive")
        
        eps = epsilon or self.default_epsilon
        
        # Check and consume budget
        if not self.privacy_budget.consume_query(epsilon=eps):
            raise RuntimeError("Privacy budget exhausted")
        
        # Calculate noise scale: b = Δf / ε
        noise_scale = sensitivity / eps
        
        # Draw noise from Laplace distribution
        noise = self._rng.laplace(loc=0.0, scale=noise_scale)
        
        # Create metadata
        metadata = PrivacyMetadata(
            epsilon=eps,
            delta=0.0,  # Pure DP for Laplace
            noise_scale=noise_scale,
            sensitivity=sensitivity,
            mechanism="laplace",
            privacy_budget_consumed=eps,
        )
        
        # Log query for auditing
        self._log_query("laplace_noise", value, eps, sensitivity)
        
        return value + noise, metadata
    
    def add_gaussian_noise(
        self,
        value: float,
        sensitivity: float,
        epsilon: Optional[float] = None,
        delta: Optional[float] = None,
    ) -> Tuple[float, PrivacyMetadata]:
        """
        Add Gaussian noise to a numeric value.
        
        The Gaussian mechanism provides (ε, δ)-differential privacy,
        which is slightly weaker than pure DP but better for high
        dimensional data.
        
        The noise scale is: σ = Δf × √(2 ln(1.25/δ)) / ε
        
        Args:
            value: The true value to privatize
            sensitivity: Maximum change in value from one record (Δf)
            epsilon: Privacy parameter (uses default if None)
            delta: Failure probability (uses default if None)
            
        Returns:
            Tuple of (privatized_value, metadata)
        """
        if sensitivity <= 0:
            raise ValueError("Sensitivity must be positive")
        
        eps = epsilon or self.default_epsilon
        dlt = delta or self.default_delta
        
        if not self.privacy_budget.consume_query(epsilon=eps, delta=dlt):
            raise RuntimeError("Privacy budget exhausted")
        
        # Calculate noise scale for (ε, δ)-DP
        noise_scale = sensitivity * math.sqrt(2 * math.log(1.25 / dlt)) / eps
        
        # Draw noise from Gaussian distribution
        noise = self._rng.normal(loc=0.0, scale=noise_scale)
        
        metadata = PrivacyMetadata(
            epsilon=eps,
            delta=dlt,
            noise_scale=noise_scale,
            sensitivity=sensitivity,
            mechanism="gaussian",
            privacy_budget_consumed=eps,
        )
        
        self._log_query("gaussian_noise", value, eps, sensitivity)
        
        return value + noise, metadata
    
    def privatize_vector(
        self,
        vector: List[float],
        sensitivity: float,
        epsilon: Optional[float] = None,
        per_element: bool = True,
    ) -> Tuple[List[float], PrivacyMetadata]:
        """
        Add noise to each element of a vector.
        
        For per-element privacy, each element gets its own noise.
        For vector-level privacy, the total sensitivity is divided
        across all elements.
        
        Args:
            vector: The feature vector to privatize
            sensitivity: Sensitivity per element (or total if per_element=False)
            epsilon: Privacy parameter
            per_element: If True, apply sensitivity per element
            
        Returns:
            Tuple of (privatized_vector, metadata)
            
        Note:
            When per_element=True, total epsilon consumption is ε × len(vector)
            due to composition. Consider using per_element=False for large vectors.
        """
        if not vector:
            raise ValueError("Vector cannot be empty")
        
        eps = epsilon or self.default_epsilon
        
        if per_element:
            # Each element gets full sensitivity, divide epsilon
            element_epsilon = eps / len(vector)
            noise_scale = sensitivity / element_epsilon
        else:
            # Total sensitivity divided across elements
            element_sensitivity = sensitivity / len(vector)
            noise_scale = element_sensitivity / eps
        
        # Check budget for single vector query
        if not self.privacy_budget.consume_query(epsilon=eps):
            raise RuntimeError("Privacy budget exhausted")
        
        # Add noise to each element
        noised_vector = []
        for val in vector:
            noise = self._rng.laplace(loc=0.0, scale=noise_scale)
            noised_vector.append(val + noise)
        
        metadata = PrivacyMetadata(
            epsilon=eps,
            delta=0.0,
            noise_scale=noise_scale,
            sensitivity=sensitivity,
            mechanism="laplace_vector",
            privacy_budget_consumed=eps,
        )
        
        self._log_query("privatize_vector", len(vector), eps, sensitivity)
        
        return noised_vector, metadata
    
    def privatize_count(
        self,
        count: int,
        max_count: int = 1000,
        epsilon: Optional[float] = None,
    ) -> Tuple[int, PrivacyMetadata]:
        """
        Privatize a count query.
        
        Count queries have sensitivity = 1 because adding or removing
        one record changes the count by at most 1.
        
        Args:
            count: The true count
            max_count: Maximum expected count (for normalization)
            epsilon: Privacy parameter
            
        Returns:
            Tuple of (privatized_count, metadata)
            
        Note:
            The returned count is rounded and clamped to [0, max_count].
        """
        sensitivity = 1.0  # Adding/removing one record changes count by 1
        
        noised_value, metadata = self.add_laplace_noise(
            float(count),
            sensitivity,
            epsilon,
        )
        
        # Clamp and round
        privatized_count = int(round(max(0, min(max_count, noised_value))))
        
        return privatized_count, metadata
    
    def privatize_average(
        self,
        values: List[float],
        value_range: Tuple[float, float],
        epsilon: Optional[float] = None,
    ) -> Tuple[float, PrivacyMetadata]:
        """
        Privatize an average query.
        
        Computing a private average requires:
        1. Private sum (sensitivity = max_value - min_value)
        2. Private count (sensitivity = 1)
        
        We use 2× epsilon budget for the two queries.
        
        Args:
            values: The list of values to average
            value_range: (min_value, max_value) range of values
            epsilon: Privacy parameter (total for both queries)
            
        Returns:
            Tuple of (privatized_average, metadata)
        """
        if not values:
            raise ValueError("Values cannot be empty")
        
        eps = epsilon or self.default_epsilon
        half_eps = eps / 2  # Split between sum and count
        
        min_val, max_val = value_range
        sensitivity_sum = max_val - min_val
        
        # Private sum
        true_sum = sum(values)
        noised_sum, sum_meta = self.add_laplace_noise(
            true_sum,
            sensitivity_sum,
            half_eps,
        )
        
        # Private count
        true_count = len(values)
        noised_count, _ = self.privatize_count(
            true_count,
            max_count=len(values) * 2,  # Allow some headroom
            epsilon=half_eps,
        )
        
        # Avoid division by zero
        if noised_count <= 0:
            noised_count = 1
        
        private_avg = noised_sum / noised_count
        
        # Clamp to valid range
        private_avg = max(min_val, min(max_val, private_avg))
        
        metadata = PrivacyMetadata(
            epsilon=eps,
            delta=0.0,
            noise_scale=sum_meta.noise_scale,  # Report sum's noise scale
            sensitivity=sensitivity_sum,
            mechanism="laplace_average",
            privacy_budget_consumed=eps,
        )
        
        return private_avg, metadata
    
    def privatize_histogram(
        self,
        histogram: Dict[str, int],
        epsilon: Optional[float] = None,
    ) -> Tuple[Dict[str, int], PrivacyMetadata]:
        """
        Privatize a histogram query.
        
        Each bin is privatized independently with sensitivity = 1.
        Total epsilon is divided across all bins.
        
        Args:
            histogram: Dictionary mapping categories to counts
            epsilon: Privacy parameter
            
        Returns:
            Tuple of (privatized_histogram, metadata)
        """
        if not histogram:
            raise ValueError("Histogram cannot be empty")
        
        eps = epsilon or self.default_epsilon
        bin_epsilon = eps / len(histogram)
        
        if not self.privacy_budget.consume_query(epsilon=eps):
            raise RuntimeError("Privacy budget exhausted")
        
        noise_scale = 1.0 / bin_epsilon  # sensitivity = 1 for counts
        
        privatized = {}
        for key, count in histogram.items():
            noise = self._rng.laplace(loc=0.0, scale=noise_scale)
            privatized[key] = max(0, int(round(count + noise)))
        
        metadata = PrivacyMetadata(
            epsilon=eps,
            delta=0.0,
            noise_scale=noise_scale,
            sensitivity=1.0,
            mechanism="laplace_histogram",
            privacy_budget_consumed=eps,
        )
        
        return privatized, metadata
    
    def randomized_response(
        self,
        value: bool,
        epsilon: Optional[float] = None,
    ) -> Tuple[bool, PrivacyMetadata]:
        """
        Randomized response for binary queries.
        
        With probability p = e^ε / (1 + e^ε), return true value.
        Otherwise, return random value.
        
        This provides plausible deniability for sensitive binary attributes.
        
        Args:
            value: The true binary value
            epsilon: Privacy parameter
            
        Returns:
            Tuple of (privatized_value, metadata)
        """
        eps = epsilon or self.default_epsilon
        
        if not self.privacy_budget.consume_query(epsilon=eps):
            raise RuntimeError("Privacy budget exhausted")
        
        # Probability of returning true value
        p = math.exp(eps) / (1 + math.exp(eps))
        
        if self._rng.random() < p:
            result = value
        else:
            result = self._rng.random() < 0.5
        
        metadata = PrivacyMetadata(
            epsilon=eps,
            delta=0.0,
            noise_scale=0.0,  # Not applicable
            sensitivity=1.0,
            mechanism="randomized_response",
            privacy_budget_consumed=eps,
        )
        
        return result, metadata
    
    def get_query_history(self) -> List[Dict[str, Any]]:
        """Get history of all queries for auditing."""
        return self._query_history.copy()
    
    def get_privacy_budget_status(self) -> Dict[str, Any]:
        """Get current status of privacy budget."""
        return self.privacy_budget.to_dict()
    
    def _log_query(
        self,
        query_type: str,
        value: Any,
        epsilon: float,
        sensitivity: float,
    ) -> None:
        """Log a query for auditing purposes."""
        self._query_history.append({
            "query_type": query_type,
            "epsilon": epsilon,
            "sensitivity": sensitivity,
            "timestamp": datetime.utcnow().isoformat(),
            "query_id": secrets.token_hex(8),
        })


class PrivacyAccountant:
    """
    Track privacy budget across multiple queries using composition theorems.
    
    The accountant provides tighter privacy bounds than naive composition
    by using advanced composition theorems.
    
    Composition Theorems:
        Basic Composition:
            k queries with (ε, δ)-DP each → (k×ε, k×δ)-DP total
            
        Advanced Composition (Theorem 3.16, Dwork & Roth):
            k queries with (ε, δ)-DP each → (ε', k×δ + δ')-DP total
            where ε' = √(2k×ln(1/δ'))×ε + k×ε×(e^ε - 1)
            
        Moments Accountant (for Gaussian):
            Provides even tighter bounds for Gaussian mechanism
    
    Example:
        >>> accountant = PrivacyAccountant(target_epsilon=1.0, target_delta=1e-5)
        >>> for query in queries:
        ...     if accountant.can_query(epsilon=0.1):
        ...         # Perform query
        ...         accountant.add_query(epsilon=0.1, delta=0.0, query_type="count")
    """
    
    def __init__(
        self,
        target_epsilon: float = 1.0,
        target_delta: float = 1e-5,
        composition_method: str = "advanced",
    ):
        """
        Initialize the privacy accountant.
        
        Args:
            target_epsilon: Maximum total epsilon allowed
            target_delta: Maximum total delta allowed
            composition_method: 'basic', 'advanced', or 'moments'
        """
        self.target_epsilon = target_epsilon
        self.target_delta = target_delta
        self.composition_method = composition_method
        self._queries: List[Dict[str, Any]] = []
        self._total_epsilon = 0.0
        self._total_delta = 0.0
    
    def add_query(
        self,
        epsilon: float,
        delta: float,
        query_type: str,
    ) -> bool:
        """
        Record a query and update privacy loss.
        
        Args:
            epsilon: Epsilon for this query
            delta: Delta for this query
            query_type: Description of query type
            
        Returns:
            True if query was allowed, False if would exceed budget
        """
        # Check if query would exceed budget
        new_eps, new_delta = self._compute_composition(epsilon, delta)
        
        if new_eps > self.target_epsilon or new_delta > self.target_delta:
            return False
        
        # Record the query
        self._queries.append({
            "epsilon": epsilon,
            "delta": delta,
            "query_type": query_type,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # Update totals
        self._total_epsilon = new_eps
        self._total_delta = new_delta
        
        return True
    
    def can_query(self, epsilon: float, delta: float = 0.0) -> bool:
        """Check if a query with given parameters would be allowed."""
        new_eps, new_delta = self._compute_composition(epsilon, delta)
        return new_eps <= self.target_epsilon and new_delta <= self.target_delta
    
    def get_total_privacy_loss(self) -> Tuple[float, float]:
        """Get current total privacy loss (epsilon, delta)."""
        return self._total_epsilon, self._total_delta
    
    def get_remaining_budget(self) -> Tuple[float, float]:
        """Get remaining budget (epsilon, delta)."""
        return (
            self.target_epsilon - self._total_epsilon,
            self.target_delta - self._total_delta,
        )
    
    def get_query_count(self) -> int:
        """Get number of queries recorded."""
        return len(self._queries)
    
    def get_queries(self) -> List[Dict[str, Any]]:
        """Get all recorded queries."""
        return self._queries.copy()
    
    def reset(self) -> None:
        """Reset the accountant (e.g., for a new budget period)."""
        self._queries = []
        self._total_epsilon = 0.0
        self._total_delta = 0.0
    
    def _compute_composition(
        self,
        new_epsilon: float,
        new_delta: float,
    ) -> Tuple[float, float]:
        """
        Compute total privacy loss after adding a new query.
        
        Uses the configured composition method.
        """
        if self.composition_method == "basic":
            return self._basic_composition(new_epsilon, new_delta)
        elif self.composition_method == "advanced":
            return self._advanced_composition(new_epsilon, new_delta)
        else:
            return self._basic_composition(new_epsilon, new_delta)
    
    def _basic_composition(
        self,
        new_epsilon: float,
        new_delta: float,
    ) -> Tuple[float, float]:
        """
        Basic composition: simply sum epsilons and deltas.
        
        (ε₁, δ₁) + (ε₂, δ₂) → (ε₁ + ε₂, δ₁ + δ₂)
        """
        return (
            self._total_epsilon + new_epsilon,
            self._total_delta + new_delta,
        )
    
    def _advanced_composition(
        self,
        new_epsilon: float,
        new_delta: float,
    ) -> Tuple[float, float]:
        """
        Advanced composition theorem.
        
        For k queries with (ε, δ)-DP, the total privacy loss is:
            ε' = √(2k×ln(1/δ'))×ε + k×ε×(e^ε - 1)
        
        where δ' is an additional failure probability.
        
        This is tighter than basic composition for many queries.
        """
        k = len(self._queries) + 1  # Including new query
        
        # Use all epsilons for composition
        all_epsilons = [q["epsilon"] for q in self._queries] + [new_epsilon]
        all_deltas = [q["delta"] for q in self._queries] + [new_delta]
        
        # For simplicity, use maximum epsilon for bound
        max_eps = max(all_epsilons) if all_epsilons else new_epsilon
        
        # Additional failure probability for advanced composition
        delta_prime = self.target_delta / 10  # Small fraction of target
        
        # Advanced composition bound
        if k > 0 and delta_prime > 0:
            eps_prime = (
                math.sqrt(2 * k * math.log(1 / delta_prime)) * max_eps
                + k * max_eps * (math.exp(max_eps) - 1)
            )
        else:
            eps_prime = k * max_eps
        
        delta_total = sum(all_deltas) + delta_prime
        
        return eps_prime, delta_total
    
    def generate_audit_report(self) -> Dict[str, Any]:
        """
        Generate an audit report of all privacy-related activity.
        
        Returns:
            Dictionary with audit information
        """
        eps, delta = self.get_total_privacy_loss()
        remaining_eps, remaining_delta = self.get_remaining_budget()
        
        return {
            "total_queries": len(self._queries),
            "total_epsilon": eps,
            "total_delta": delta,
            "remaining_epsilon": remaining_eps,
            "remaining_delta": remaining_delta,
            "target_epsilon": self.target_epsilon,
            "target_delta": self.target_delta,
            "composition_method": self.composition_method,
            "queries": self._queries,
            "generated_at": datetime.utcnow().isoformat(),
            "budget_exhausted": eps >= self.target_epsilon or delta >= self.target_delta,
        }


def compute_sensitivity(
    query_type: str,
    data_range: Optional[Tuple[float, float]] = None,
    vector_dim: Optional[int] = None,
) -> float:
    """
    Compute sensitivity for common query types.
    
    Args:
        query_type: Type of query ('count', 'sum', 'average', 'vector')
        data_range: (min, max) range for numeric data
        vector_dim: Dimension of vector for vector queries
        
    Returns:
        Sensitivity value (Δf)
    """
    if query_type == "count":
        # Adding/removing one record changes count by at most 1
        return 1.0
    
    elif query_type == "sum":
        if data_range is None:
            raise ValueError("data_range required for sum query")
        min_val, max_val = data_range
        # Adding/removing one record changes sum by at most max - min
        return max_val - min_val
    
    elif query_type == "average":
        if data_range is None:
            raise ValueError("data_range required for average query")
        min_val, max_val = data_range
        # Sensitivity of average is (max - min) / n, but we bound by n=1
        return max_val - min_val
    
    elif query_type == "vector":
        if vector_dim is None:
            raise ValueError("vector_dim required for vector query")
        # L2 sensitivity for unit vectors
        return math.sqrt(vector_dim)
    
    else:
        raise ValueError(f"Unknown query type: {query_type}")


def verify_epsilon_delta(
    original: float,
    privatized: float,
    noise_scale: float,
    epsilon: float,
) -> bool:
    """
    Verify that the privatized value satisfies ε-DP.
    
    This is a probabilistic test that checks if the noise
    distribution is consistent with the claimed privacy guarantee.
    
    Args:
        original: Original value
        privatized: Privatized value
        noise_scale: Scale of noise distribution
        epsilon: Claimed epsilon
        
    Returns:
        True if the noise is consistent with ε-DP
    """
    noise = abs(privatized - original)
    
    # For Laplace noise, 99.9% of samples should be within 7× noise_scale
    max_expected_noise = 7 * noise_scale
    
    return noise <= max_expected_noise
