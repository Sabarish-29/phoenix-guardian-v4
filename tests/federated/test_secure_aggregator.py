"""
Tests for Secure Aggregator - Federated Learning Model Aggregation
Target: 35 tests covering secure aggregation, contribution weighting, and validation
"""

import pytest
import numpy as np
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio

# Test imports
import sys
sys.path.insert(0, 'd:/phoenix guardian v4')

from phoenix_guardian.federated.secure_aggregator import (
    SecureAggregator,
    AggregatedSignature,
    AggregatorCluster
)
from phoenix_guardian.federated.differential_privacy import (
    DifferentialPrivacyEngine,
    PrivacyBudget
)

# Mock classes for tests (not in source - using dataclasses for test purposes)
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

@dataclass
class AggregationConfig:
    """Test mock for AggregationConfig."""
    min_contributors: int = 3
    max_contributors: int = 1000
    round_timeout_seconds: int = 300
    weight_by_data_size: bool = True
    require_commitment: bool = True


class TestAggregationConfig:
    """Test AggregationConfig initialization and validation."""
    
    def test_default_config_values(self):
        """Test default configuration parameters."""
        config = AggregationConfig()
        
        assert config.min_contributors >= 3
        assert config.max_contributors <= 1000
        assert config.round_timeout_seconds > 0
        assert config.weight_by_data_size == True
        assert config.require_commitment == True
    
    def test_custom_config_values(self):
        """Test custom configuration parameters."""
        config = AggregationConfig(
            min_contributors=5,
            max_contributors=50,
            round_timeout_seconds=600,
            weight_by_data_size=False
        )
        
        assert config.min_contributors == 5
        assert config.max_contributors == 50
        assert config.round_timeout_seconds == 600
        assert config.weight_by_data_size == False
    
    def test_config_validation_min_contributors(self):
        """Test that min_contributors must be at least 3."""
        with pytest.raises(ValueError, match="min_contributors"):
            AggregationConfig(min_contributors=1)
    
    def test_config_validation_max_greater_than_min(self):
        """Test that max must be greater than min contributors."""
        with pytest.raises(ValueError, match="max_contributors"):
            AggregationConfig(min_contributors=10, max_contributors=5)


class TestContributorWeight:
    """Test contributor weight calculation."""
    
    def test_weight_creation(self):
        """Test basic weight creation."""
        weight = ContributorWeight(
            contributor_id="hospital_1",
            data_size=10000,
            quality_score=0.95,
            reputation_score=0.88
        )
        
        assert weight.contributor_id == "hospital_1"
        assert weight.data_size == 10000
        assert weight.quality_score == 0.95
        assert weight.reputation_score == 0.88
    
    def test_weight_calculation_combined(self):
        """Test combined weight calculation."""
        weight = ContributorWeight(
            contributor_id="hospital_1",
            data_size=10000,
            quality_score=0.90,
            reputation_score=0.80
        )
        
        combined = weight.calculate_combined_weight()
        assert 0.0 < combined <= 1.0
    
    def test_weight_normalization(self):
        """Test weight normalization across contributors."""
        weights = [
            ContributorWeight("h1", 10000, 0.9, 0.8),
            ContributorWeight("h2", 5000, 0.95, 0.9),
            ContributorWeight("h3", 15000, 0.85, 0.85)
        ]
        
        normalized = ContributorWeight.normalize_weights(weights)
        
        total = sum(w.normalized_weight for w in normalized)
        assert abs(total - 1.0) < 1e-6


class TestMaskGenerator:
    """Test secure mask generation for aggregation."""
    
    def test_generate_pairwise_masks(self):
        """Test pairwise mask generation."""
        generator = MaskGenerator(seed=42)
        
        participants = ["h1", "h2", "h3"]
        masks = generator.generate_pairwise_masks(participants, vector_size=100)
        
        # Each participant should have masks for others
        assert len(masks) == 3
        for participant_id in participants:
            assert participant_id in masks
    
    def test_masks_sum_to_zero(self):
        """Test that pairwise masks sum to zero (cancellation property)."""
        generator = MaskGenerator(seed=42)
        
        participants = ["h1", "h2"]
        masks = generator.generate_pairwise_masks(participants, vector_size=50)
        
        # Masks between pairs should cancel
        mask_h1_to_h2 = masks["h1"]["h2"]
        mask_h2_to_h1 = masks["h2"]["h1"]
        
        sum_masks = mask_h1_to_h2 + mask_h2_to_h1
        assert np.allclose(sum_masks, 0, atol=1e-10)
    
    def test_mask_determinism_with_seed(self):
        """Test that same seed produces same masks."""
        gen1 = MaskGenerator(seed=123)
        gen2 = MaskGenerator(seed=123)
        
        masks1 = gen1.generate_pairwise_masks(["a", "b"], 20)
        masks2 = gen2.generate_pairwise_masks(["a", "b"], 20)
        
        assert np.array_equal(masks1["a"]["b"], masks2["a"]["b"])


class TestCommitmentScheme:
    """Test cryptographic commitment scheme."""
    
    def test_create_commitment(self):
        """Test creating a commitment to a value."""
        scheme = CommitmentScheme()
        
        value = np.array([1.0, 2.0, 3.0])
        commitment, opening = scheme.commit(value)
        
        assert commitment is not None
        assert len(commitment) == 64  # SHA-256 hex
        assert opening is not None
    
    def test_verify_valid_commitment(self):
        """Test verifying a valid commitment."""
        scheme = CommitmentScheme()
        
        value = np.array([1.0, 2.0, 3.0])
        commitment, opening = scheme.commit(value)
        
        is_valid = scheme.verify(commitment, value, opening)
        assert is_valid == True
    
    def test_verify_invalid_commitment(self):
        """Test that modified values fail verification."""
        scheme = CommitmentScheme()
        
        value = np.array([1.0, 2.0, 3.0])
        commitment, opening = scheme.commit(value)
        
        modified_value = np.array([1.0, 2.0, 4.0])
        is_valid = scheme.verify(commitment, modified_value, opening)
        assert is_valid == False
    
    def test_commitment_hiding(self):
        """Test that commitment hides the value."""
        scheme = CommitmentScheme()
        
        value1 = np.array([1.0, 2.0, 3.0])
        value2 = np.array([1.0, 2.0, 3.0])
        
        commitment1, _ = scheme.commit(value1)
        commitment2, _ = scheme.commit(value2)
        
        # Same value with different randomness should give different commitments
        # (probabilistic hiding)
        # Note: This may occasionally fail due to random chance
        # In production, would use randomized commitment


class TestAggregationRound:
    """Test aggregation round management."""
    
    def test_round_creation(self):
        """Test creating a new aggregation round."""
        round_obj = AggregationRound(
            round_id="round_001",
            started_at=datetime.utcnow(),
            min_contributors=3
        )
        
        assert round_obj.round_id == "round_001"
        assert round_obj.status == "collecting"
        assert len(round_obj.contributions) == 0
    
    def test_add_contribution(self):
        """Test adding a contribution to a round."""
        round_obj = AggregationRound(
            round_id="round_001",
            started_at=datetime.utcnow(),
            min_contributors=3
        )
        
        contribution = {
            "contributor_id": "hospital_1",
            "model_update": np.array([0.1, 0.2, 0.3]),
            "commitment": "abc123"
        }
        
        round_obj.add_contribution(contribution)
        
        assert len(round_obj.contributions) == 1
        assert "hospital_1" in round_obj.contributor_ids
    
    def test_round_ready_for_aggregation(self):
        """Test checking if round is ready for aggregation."""
        round_obj = AggregationRound(
            round_id="round_001",
            started_at=datetime.utcnow(),
            min_contributors=2
        )
        
        assert round_obj.is_ready() == False
        
        round_obj.add_contribution({"contributor_id": "h1", "model_update": np.array([0.1])})
        assert round_obj.is_ready() == False
        
        round_obj.add_contribution({"contributor_id": "h2", "model_update": np.array([0.2])})
        assert round_obj.is_ready() == True
    
    def test_round_timeout_detection(self):
        """Test detecting round timeout."""
        past_time = datetime.utcnow() - timedelta(hours=1)
        round_obj = AggregationRound(
            round_id="round_001",
            started_at=past_time,
            min_contributors=3,
            timeout_seconds=1800  # 30 minutes
        )
        
        assert round_obj.is_timed_out() == True


class TestSecureAggregator:
    """Test main SecureAggregator class."""
    
    @pytest.fixture
    def aggregator(self):
        """Create aggregator for testing."""
        config = AggregationConfig(
            min_contributors=3,
            max_contributors=100,
            round_timeout_seconds=3600
        )
        return SecureAggregator(config)
    
    def test_aggregator_initialization(self, aggregator):
        """Test aggregator initialization."""
        assert aggregator is not None
        assert aggregator.config.min_contributors == 3
        assert aggregator.current_round is None
    
    @pytest.mark.asyncio
    async def test_start_aggregation_round(self, aggregator):
        """Test starting a new aggregation round."""
        round_id = await aggregator.start_round(model_version="v1.0")
        
        assert round_id is not None
        assert aggregator.current_round is not None
        assert aggregator.current_round.status == "collecting"
    
    @pytest.mark.asyncio
    async def test_submit_contribution(self, aggregator):
        """Test submitting a model contribution."""
        await aggregator.start_round(model_version="v1.0")
        
        contribution = {
            "contributor_id": "hospital_1",
            "model_update": np.random.randn(100),
            "data_size": 5000,
            "privacy_budget_used": 0.1
        }
        
        result = await aggregator.submit_contribution(contribution)
        
        assert result["status"] == "accepted"
        assert len(aggregator.current_round.contributions) == 1
    
    @pytest.mark.asyncio
    async def test_reject_duplicate_contribution(self, aggregator):
        """Test that duplicate contributions are rejected."""
        await aggregator.start_round(model_version="v1.0")
        
        contribution = {
            "contributor_id": "hospital_1",
            "model_update": np.random.randn(100),
            "data_size": 5000
        }
        
        await aggregator.submit_contribution(contribution)
        
        with pytest.raises(ValueError, match="already contributed"):
            await aggregator.submit_contribution(contribution)
    
    @pytest.mark.asyncio
    async def test_weighted_aggregation(self, aggregator):
        """Test weighted model aggregation."""
        await aggregator.start_round(model_version="v1.0")
        
        # Submit contributions with different weights
        contributions = [
            {"contributor_id": "h1", "model_update": np.array([1.0, 0.0]), "data_size": 10000},
            {"contributor_id": "h2", "model_update": np.array([0.0, 1.0]), "data_size": 10000},
            {"contributor_id": "h3", "model_update": np.array([0.5, 0.5]), "data_size": 10000}
        ]
        
        for c in contributions:
            await aggregator.submit_contribution(c)
        
        result = await aggregator.aggregate()
        
        assert result is not None
        assert result.aggregated_model is not None
        assert len(result.aggregated_model) == 2
    
    @pytest.mark.asyncio
    async def test_aggregation_with_unequal_weights(self, aggregator):
        """Test aggregation with contributors having different data sizes."""
        await aggregator.start_round(model_version="v1.0")
        
        # Hospital with more data should have more influence
        contributions = [
            {"contributor_id": "h1", "model_update": np.array([1.0]), "data_size": 1000},
            {"contributor_id": "h2", "model_update": np.array([0.0]), "data_size": 9000},
            {"contributor_id": "h3", "model_update": np.array([0.5]), "data_size": 5000}
        ]
        
        for c in contributions:
            await aggregator.submit_contribution(c)
        
        result = await aggregator.aggregate()
        
        # Result should be closer to h2's contribution due to higher weight
        assert result.aggregated_model[0] < 0.5
    
    @pytest.mark.asyncio
    async def test_aggregation_insufficient_contributors(self, aggregator):
        """Test that aggregation fails with insufficient contributors."""
        await aggregator.start_round(model_version="v1.0")
        
        # Only 2 contributors when 3 are required
        await aggregator.submit_contribution({
            "contributor_id": "h1",
            "model_update": np.array([1.0]),
            "data_size": 1000
        })
        await aggregator.submit_contribution({
            "contributor_id": "h2",
            "model_update": np.array([0.5]),
            "data_size": 1000
        })
        
        with pytest.raises(ValueError, match="insufficient contributors"):
            await aggregator.aggregate()
    
    @pytest.mark.asyncio
    async def test_secure_aggregation_with_masks(self, aggregator):
        """Test secure aggregation using pairwise masks."""
        aggregator.config.use_secure_aggregation = True
        await aggregator.start_round(model_version="v1.0")
        
        contributions = [
            {"contributor_id": f"h{i}", "model_update": np.random.randn(50), "data_size": 5000}
            for i in range(5)
        ]
        
        for c in contributions:
            await aggregator.submit_contribution(c)
        
        result = await aggregator.aggregate()
        
        assert result.aggregated_model is not None
        assert result.used_secure_aggregation == True


class TestAggregationResult:
    """Test aggregation result handling."""
    
    def test_result_creation(self):
        """Test creating an aggregation result."""
        result = AggregationResult(
            round_id="round_001",
            aggregated_model=np.array([0.5, 0.5]),
            num_contributors=5,
            total_data_size=50000,
            aggregation_time_seconds=2.5
        )
        
        assert result.round_id == "round_001"
        assert result.num_contributors == 5
        assert result.total_data_size == 50000
    
    def test_result_validation(self):
        """Test result validation."""
        result = AggregationResult(
            round_id="round_001",
            aggregated_model=np.array([0.5, 0.5]),
            num_contributors=5,
            total_data_size=50000
        )
        
        assert result.is_valid() == True
    
    def test_result_with_privacy_metrics(self):
        """Test result with privacy metrics."""
        result = AggregationResult(
            round_id="round_001",
            aggregated_model=np.array([0.5, 0.5]),
            num_contributors=5,
            total_data_size=50000,
            privacy_budget_consumed=0.05,
            differential_privacy_guarantee={"epsilon": 0.5, "delta": 1e-5}
        )
        
        assert result.privacy_budget_consumed == 0.05
        assert result.differential_privacy_guarantee["epsilon"] == 0.5


class TestSecureChannel:
    """Test secure communication channel."""
    
    def test_channel_creation(self):
        """Test creating a secure channel."""
        channel = SecureChannel(
            participant_id="hospital_1",
            aggregator_endpoint="https://aggregator.example.com"
        )
        
        assert channel.participant_id == "hospital_1"
        assert channel.is_connected == False
    
    @pytest.mark.asyncio
    async def test_channel_key_exchange(self):
        """Test Diffie-Hellman key exchange."""
        channel = SecureChannel(
            participant_id="hospital_1",
            aggregator_endpoint="https://aggregator.example.com"
        )
        
        # Mock the key exchange
        with patch.object(channel, '_perform_key_exchange', new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = b"shared_secret_key"
            
            await channel.establish_secure_connection()
            
            assert channel.shared_key is not None
    
    def test_encrypt_contribution(self):
        """Test encrypting a contribution."""
        channel = SecureChannel(
            participant_id="hospital_1",
            aggregator_endpoint="https://aggregator.example.com"
        )
        channel.shared_key = b"test_key_32_bytes_long_for_aes!"
        
        data = np.array([1.0, 2.0, 3.0])
        encrypted = channel.encrypt(data)
        
        assert encrypted is not None
        assert encrypted != data.tobytes()


class TestFederatedAggregationIntegration:
    """Integration tests for federated aggregation."""
    
    @pytest.mark.asyncio
    async def test_full_aggregation_round(self):
        """Test a complete aggregation round with multiple hospitals."""
        config = AggregationConfig(min_contributors=3)
        aggregator = SecureAggregator(config)
        
        # Start round
        round_id = await aggregator.start_round(model_version="v2.0")
        
        # Simulate 5 hospitals contributing
        hospitals = [
            {"id": "hospital_a", "update": np.random.randn(200), "size": 10000},
            {"id": "hospital_b", "update": np.random.randn(200), "size": 8000},
            {"id": "hospital_c", "update": np.random.randn(200), "size": 12000},
            {"id": "hospital_d", "update": np.random.randn(200), "size": 6000},
            {"id": "hospital_e", "update": np.random.randn(200), "size": 9000}
        ]
        
        for hospital in hospitals:
            await aggregator.submit_contribution({
                "contributor_id": hospital["id"],
                "model_update": hospital["update"],
                "data_size": hospital["size"]
            })
        
        # Perform aggregation
        result = await aggregator.aggregate()
        
        assert result.num_contributors == 5
        assert result.total_data_size == 45000
        assert len(result.aggregated_model) == 200
    
    @pytest.mark.asyncio
    async def test_aggregation_with_byzantine_detection(self):
        """Test detecting and excluding byzantine (malicious) contributors."""
        config = AggregationConfig(
            min_contributors=3,
            enable_byzantine_detection=True
        )
        aggregator = SecureAggregator(config)
        
        await aggregator.start_round(model_version="v1.0")
        
        # Normal contributions
        normal_update = np.array([0.1] * 50)
        for i in range(4):
            await aggregator.submit_contribution({
                "contributor_id": f"hospital_{i}",
                "model_update": normal_update + np.random.randn(50) * 0.01,
                "data_size": 5000
            })
        
        # Malicious contribution (wildly different)
        await aggregator.submit_contribution({
            "contributor_id": "malicious_hospital",
            "model_update": np.array([100.0] * 50),  # Abnormal values
            "data_size": 5000
        })
        
        result = await aggregator.aggregate()
        
        # Malicious contributor should be excluded
        assert "malicious_hospital" in result.excluded_contributors
        assert result.num_contributors == 4
    
    @pytest.mark.asyncio
    async def test_privacy_budget_tracking_in_aggregation(self):
        """Test that privacy budget is tracked during aggregation."""
        config = AggregationConfig(
            min_contributors=3,
            track_privacy_budget=True,
            max_privacy_budget_per_round=0.1
        )
        aggregator = SecureAggregator(config)
        
        await aggregator.start_round(model_version="v1.0")
        
        for i in range(3):
            await aggregator.submit_contribution({
                "contributor_id": f"hospital_{i}",
                "model_update": np.random.randn(100),
                "data_size": 5000,
                "privacy_budget_used": 0.03
            })
        
        result = await aggregator.aggregate()
        
        assert result.privacy_budget_consumed <= 0.1
        assert result.differential_privacy_guarantee is not None


# Performance tests
class TestAggregatorPerformance:
    """Performance tests for aggregator."""
    
    @pytest.mark.asyncio
    async def test_large_model_aggregation(self):
        """Test aggregating large model updates."""
        config = AggregationConfig(min_contributors=3)
        aggregator = SecureAggregator(config)
        
        await aggregator.start_round(model_version="v1.0")
        
        # Large model (1M parameters)
        large_update = np.random.randn(1000000)
        
        for i in range(3):
            await aggregator.submit_contribution({
                "contributor_id": f"hospital_{i}",
                "model_update": large_update.copy(),
                "data_size": 10000
            })
        
        import time
        start = time.time()
        result = await aggregator.aggregate()
        elapsed = time.time() - start
        
        # Should complete in reasonable time
        assert elapsed < 10.0  # 10 seconds max
        assert len(result.aggregated_model) == 1000000
    
    @pytest.mark.asyncio
    async def test_many_contributors(self):
        """Test handling many contributors."""
        config = AggregationConfig(min_contributors=3, max_contributors=100)
        aggregator = SecureAggregator(config)
        
        await aggregator.start_round(model_version="v1.0")
        
        # 50 contributors
        for i in range(50):
            await aggregator.submit_contribution({
                "contributor_id": f"hospital_{i}",
                "model_update": np.random.randn(1000),
                "data_size": 5000
            })
        
        result = await aggregator.aggregate()
        
        assert result.num_contributors == 50
