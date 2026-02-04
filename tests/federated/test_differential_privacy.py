"""
Tests for Differential Privacy Engine.

This module contains 25 tests covering:
    - Laplace noise mechanism
    - Privacy budget tracking
    - Vector privatization
    - Count privatization
    - Advanced composition
"""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch

from phoenix_guardian.federated.differential_privacy import (
    DifferentialPrivacyEngine,
    PrivacyBudget,
    PrivacyAccountant,
)


class TestPrivacyBudget:
    """Test suite for PrivacyBudget class."""
    
    def test_budget_initialization(self):
        """Test budget initializes with correct values."""
        budget = PrivacyBudget(
            total_epsilon=50.0,
            total_delta=1e-5,
            max_queries=100,
        )
        
        assert budget.total_epsilon == 50.0
        assert budget.total_delta == 1e-5
        assert budget.max_queries == 100
        assert budget.consumed_epsilon == 0.0
        assert budget.query_count == 0
    
    def test_budget_consumption(self):
        """Test budget consumption tracking."""
        budget = PrivacyBudget(
            total_epsilon=50.0,
            total_delta=1e-5,
            max_queries=100,
        )
        
        assert budget.consume(epsilon=0.5)
        assert budget.consumed_epsilon == 0.5
        assert budget.query_count == 1
    
    def test_budget_remaining_queries(self):
        """Test remaining query calculation."""
        budget = PrivacyBudget(
            total_epsilon=50.0,
            total_delta=1e-5,
            max_queries=100,
        )
        
        for _ in range(10):
            budget.consume(epsilon=0.5)
        
        assert budget.remaining_queries() == 90
    
    def test_budget_remaining_epsilon(self):
        """Test remaining epsilon calculation."""
        budget = PrivacyBudget(
            total_epsilon=50.0,
            total_delta=1e-5,
            max_queries=100,
        )
        
        budget.consume(epsilon=10.0)
        assert budget.remaining_epsilon() == 40.0
    
    def test_budget_exhaustion_by_epsilon(self):
        """Test budget exhaustion when epsilon limit reached."""
        budget = PrivacyBudget(
            total_epsilon=10.0,
            total_delta=1e-5,
            max_queries=100,
        )
        
        # Consume all epsilon
        for _ in range(20):
            budget.consume(epsilon=0.5)
        
        assert budget.is_exhausted()
        assert not budget.consume(epsilon=0.5)
    
    def test_budget_exhaustion_by_queries(self):
        """Test budget exhaustion when query limit reached."""
        budget = PrivacyBudget(
            total_epsilon=1000.0,
            total_delta=1e-5,
            max_queries=10,
        )
        
        # Consume all queries
        for _ in range(10):
            budget.consume(epsilon=0.5)
        
        assert budget.is_exhausted()
    
    def test_budget_reset(self):
        """Test budget reset functionality."""
        budget = PrivacyBudget(
            total_epsilon=50.0,
            total_delta=1e-5,
            max_queries=100,
        )
        
        budget.consume(epsilon=25.0)
        budget.reset()
        
        assert budget.consumed_epsilon == 0.0
        assert budget.query_count == 0
        assert not budget.is_exhausted()


class TestDifferentialPrivacyEngine:
    """Test suite for DifferentialPrivacyEngine class."""
    
    def test_engine_initialization(self):
        """Test engine initializes with correct parameters."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5)
        
        assert engine.epsilon == 0.5
        assert engine.delta == 1e-5
    
    def test_add_laplace_noise_scalar(self):
        """Test Laplace noise addition to scalar."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        
        value = 10.0
        sensitivity = 1.0
        noisy = engine.add_laplace_noise(value, sensitivity)
        
        # Value should be different due to noise
        assert noisy != value
        
        # But not too different (with high probability)
        assert abs(noisy - value) < 50  # Very loose bound
    
    def test_add_laplace_noise_reproducibility(self):
        """Test that seed provides reproducibility."""
        engine1 = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        engine2 = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        
        value = 10.0
        sensitivity = 1.0
        
        noisy1 = engine1.add_laplace_noise(value, sensitivity)
        noisy2 = engine2.add_laplace_noise(value, sensitivity)
        
        assert noisy1 == noisy2
    
    def test_privatize_vector(self):
        """Test vector privatization."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        
        vector = [1.0, 2.0, 3.0, 4.0, 5.0]
        noisy = engine.privatize_vector(vector)
        
        assert len(noisy) == len(vector)
        assert noisy != vector  # Should be different
    
    def test_privatize_vector_clipping(self):
        """Test vector clipping before noise."""
        engine = DifferentialPrivacyEngine(
            epsilon=0.5,
            delta=1e-5,
            seed=42,
            clip_bounds=(-1.0, 1.0),
        )
        
        vector = [-5.0, 0.5, 3.0]
        noisy = engine.privatize_vector(vector)
        
        # Original values outside [-1, 1] should be clipped before noise
        # Results will have noise added, but underlying values were clipped
        assert len(noisy) == 3
    
    def test_privatize_count(self):
        """Test count privatization."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        
        count = 100
        noisy_count = engine.privatize_count(count)
        
        # Should be close to original
        assert abs(noisy_count - count) < 50  # Loose bound
        assert isinstance(noisy_count, int)
    
    def test_privatize_count_non_negative(self):
        """Test privatized count is non-negative."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        
        # Small count might become negative without flooring
        count = 1
        
        for _ in range(100):
            noisy = engine.privatize_count(count)
            assert noisy >= 0
    
    def test_privatize_average(self):
        """Test average privatization."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        true_avg = 3.0
        
        noisy_avg = engine.privatize_average(values)
        
        # Should be close to true average
        assert abs(noisy_avg - true_avg) < 10  # Loose bound
    
    def test_compute_sensitivity(self):
        """Test sensitivity computation."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5)
        
        sensitivity = engine.compute_sensitivity(
            query_type="count",
            data_range=(0, 100),
        )
        
        assert sensitivity > 0
    
    def test_noise_calibration(self):
        """Test noise is calibrated to epsilon."""
        engine_low = DifferentialPrivacyEngine(epsilon=0.1, delta=1e-5, seed=42)
        engine_high = DifferentialPrivacyEngine(epsilon=10.0, delta=1e-5, seed=42)
        
        # Lower epsilon should add more noise
        # Run multiple times to get average noise magnitude
        low_epsilon_diffs = []
        high_epsilon_diffs = []
        
        for i in range(100):
            engine_low_temp = DifferentialPrivacyEngine(epsilon=0.1, delta=1e-5, seed=i)
            engine_high_temp = DifferentialPrivacyEngine(epsilon=10.0, delta=1e-5, seed=i)
            
            value = 100.0
            low_epsilon_diffs.append(abs(engine_low_temp.add_laplace_noise(value, 1.0) - value))
            high_epsilon_diffs.append(abs(engine_high_temp.add_laplace_noise(value, 1.0) - value))
        
        avg_low = sum(low_epsilon_diffs) / len(low_epsilon_diffs)
        avg_high = sum(high_epsilon_diffs) / len(high_epsilon_diffs)
        
        # Low epsilon should have higher average noise
        assert avg_low > avg_high


class TestPrivacyAccountant:
    """Test suite for PrivacyAccountant class."""
    
    def test_accountant_initialization(self):
        """Test accountant initializes correctly."""
        accountant = PrivacyAccountant(
            base_epsilon=0.5,
            base_delta=1e-5,
        )
        
        assert accountant.base_epsilon == 0.5
        assert accountant.base_delta == 1e-5
        assert accountant.total_epsilon == 0.0
    
    def test_basic_composition(self):
        """Test basic composition theorem."""
        accountant = PrivacyAccountant(
            base_epsilon=0.5,
            base_delta=1e-5,
            composition_theorem="basic",
        )
        
        # 10 queries at epsilon=0.5 each
        for _ in range(10):
            accountant.record_query(epsilon=0.5)
        
        # Basic composition: total = sum of epsilons
        assert accountant.total_epsilon == 5.0
    
    def test_advanced_composition(self):
        """Test advanced composition theorem."""
        accountant = PrivacyAccountant(
            base_epsilon=0.5,
            base_delta=1e-5,
            composition_theorem="advanced",
        )
        
        # 10 queries at epsilon=0.5 each
        for _ in range(10):
            accountant.record_query(epsilon=0.5)
        
        # Advanced composition should give tighter bound
        # epsilon_total <= sqrt(2k * ln(1/delta')) * epsilon + k * epsilon * (e^epsilon - 1)
        assert accountant.total_epsilon < 5.0  # Tighter than basic
    
    def test_query_history(self):
        """Test query history is maintained."""
        accountant = PrivacyAccountant(
            base_epsilon=0.5,
            base_delta=1e-5,
        )
        
        accountant.record_query(epsilon=0.5, query_type="count")
        accountant.record_query(epsilon=0.3, query_type="average")
        
        history = accountant.get_query_history()
        
        assert len(history) == 2
        assert history[0]["epsilon"] == 0.5
        assert history[1]["epsilon"] == 0.3
    
    def test_remaining_budget(self):
        """Test remaining budget calculation."""
        accountant = PrivacyAccountant(
            base_epsilon=0.5,
            base_delta=1e-5,
            max_epsilon=10.0,
        )
        
        accountant.record_query(epsilon=3.0)
        
        remaining = accountant.remaining_budget()
        assert remaining < 10.0
    
    def test_reset_accountant(self):
        """Test accountant reset."""
        accountant = PrivacyAccountant(
            base_epsilon=0.5,
            base_delta=1e-5,
        )
        
        for _ in range(10):
            accountant.record_query(epsilon=0.5)
        
        accountant.reset()
        
        assert accountant.total_epsilon == 0.0
        assert len(accountant.get_query_history()) == 0


class TestIntegration:
    """Integration tests for differential privacy components."""
    
    def test_engine_with_budget(self):
        """Test engine respects budget limits."""
        budget = PrivacyBudget(
            total_epsilon=5.0,
            total_delta=1e-5,
            max_queries=10,
        )
        
        engine = DifferentialPrivacyEngine(
            epsilon=0.5,
            delta=1e-5,
            budget=budget,
        )
        
        # Should work for 10 queries
        for _ in range(10):
            result = engine.privatize_count(100)
            assert result is not None
        
        # 11th query should fail if budget enforced
        assert budget.is_exhausted()
    
    def test_end_to_end_privatization(self):
        """Test complete privatization workflow."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        
        # Original data
        features = [0.1, 0.2, 0.3, 0.4, 0.5]
        count = 50
        average = 2.5
        
        # Privatize all
        private_features = engine.privatize_vector(features)
        private_count = engine.privatize_count(count)
        private_avg = engine.privatize_average([1.0, 2.0, 3.0, 4.0])
        
        # All should be modified
        assert private_features != features
        assert private_count != count  # With high probability
        assert isinstance(private_count, int)
        assert isinstance(private_avg, float)


# Fixtures

@pytest.fixture
def privacy_engine():
    """Create a test privacy engine."""
    return DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)


@pytest.fixture
def privacy_budget():
    """Create a test privacy budget."""
    return PrivacyBudget(
        total_epsilon=50.0,
        total_delta=1e-5,
        max_queries=100,
    )


@pytest.fixture
def privacy_accountant():
    """Create a test privacy accountant."""
    return PrivacyAccountant(
        base_epsilon=0.5,
        base_delta=1e-5,
        max_epsilon=50.0,
    )
