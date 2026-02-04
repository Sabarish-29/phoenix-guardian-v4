"""
Tests for Privacy Validator.

This module contains 18 tests covering:
    - Epsilon-delta validation
    - Anonymity set testing
    - Membership inference testing
    - Unlinkability validation
    - Privacy loss computation
"""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch

from phoenix_guardian.federated.privacy_validator import (
    PrivacyValidator,
    ValidationResult,
    MembershipInferenceTest,
)
from phoenix_guardian.federated.threat_signature import ThreatSignature


class TestValidationResult:
    """Test suite for ValidationResult dataclass."""
    
    def test_result_creation_passed(self):
        """Test creating a passed result."""
        result = ValidationResult(
            test_name="epsilon_delta_test",
            passed=True,
            message="Test passed",
        )
        
        assert result.test_name == "epsilon_delta_test"
        assert result.passed == True
        assert result.message == "Test passed"
    
    def test_result_creation_failed(self):
        """Test creating a failed result."""
        result = ValidationResult(
            test_name="anonymity_test",
            passed=False,
            message="Anonymity set too small",
            details={"actual_k": 1, "required_k": 2},
        )
        
        assert result.passed == False
        assert result.details["actual_k"] == 1
    
    def test_result_to_dict(self):
        """Test result serialization."""
        result = ValidationResult(
            test_name="test",
            passed=True,
            message="OK",
            details={"key": "value"},
        )
        
        d = result.to_dict()
        
        assert d["test_name"] == "test"
        assert d["passed"] == True
        assert d["details"]["key"] == "value"


class TestPrivacyValidator:
    """Test suite for PrivacyValidator class."""
    
    def test_validator_initialization(self):
        """Test validator initialization."""
        validator = PrivacyValidator(seed=42)
        
        assert validator is not None
    
    def test_validate_epsilon_delta_valid(self):
        """Test validation of valid epsilon-delta."""
        validator = PrivacyValidator(seed=42)
        
        result = validator.validate_epsilon_delta(
            epsilon=0.5,
            delta=1e-5,
            max_epsilon=10.0,
            max_delta=1e-4,
        )
        
        assert result.passed == True
    
    def test_validate_epsilon_delta_invalid_epsilon(self):
        """Test validation catches high epsilon."""
        validator = PrivacyValidator(seed=42)
        
        result = validator.validate_epsilon_delta(
            epsilon=15.0,  # Too high!
            delta=1e-5,
            max_epsilon=10.0,
            max_delta=1e-4,
        )
        
        assert result.passed == False
        assert "epsilon" in result.message.lower()
    
    def test_validate_epsilon_delta_invalid_delta(self):
        """Test validation catches high delta."""
        validator = PrivacyValidator(seed=42)
        
        result = validator.validate_epsilon_delta(
            epsilon=0.5,
            delta=0.1,  # Too high!
            max_epsilon=10.0,
            max_delta=1e-4,
        )
        
        assert result.passed == False
        assert "delta" in result.message.lower()
    
    def test_test_anonymity_set_valid(self):
        """Test anonymity set with sufficient signatures."""
        validator = PrivacyValidator(seed=42)
        
        # Create signatures from multiple "hospitals"
        signatures = [
            ThreatSignature(
                signature_id=f"sig-{i}",
                attack_type="prompt_injection",
                pattern_features=np.random.rand(128).tolist(),
                confidence=0.8,
                first_seen="2024-01",
                last_seen="2024-01",
            )
            for i in range(10)
        ]
        
        result = validator.test_anonymity_set(
            signatures,
            min_anonymity_set=2,
        )
        
        assert result.passed == True
    
    def test_test_anonymity_set_insufficient(self):
        """Test anonymity set with too few signatures."""
        validator = PrivacyValidator(seed=42)
        
        # Only one signature
        signatures = [
            ThreatSignature(
                signature_id="sig-1",
                attack_type="prompt_injection",
                pattern_features=[0.1] * 128,
                confidence=0.8,
                first_seen="2024-01",
                last_seen="2024-01",
            )
        ]
        
        result = validator.test_anonymity_set(
            signatures,
            min_anonymity_set=2,
        )
        
        assert result.passed == False
    
    def test_test_signature_unlinkability(self):
        """Test signature unlinkability."""
        validator = PrivacyValidator(seed=42)
        
        # Create diverse signatures that shouldn't be linkable
        signatures = [
            ThreatSignature(
                signature_id=f"sig-{i}",
                attack_type="prompt_injection",
                pattern_features=np.random.rand(128).tolist(),
                confidence=0.8,
                first_seen="2024-01",
                last_seen="2024-01",
            )
            for i in range(20)
        ]
        
        result = validator.test_signature_unlinkability(signatures)
        
        # Should pass with random features
        assert result.passed == True
    
    def test_compute_privacy_loss_single(self):
        """Test privacy loss computation for single query."""
        validator = PrivacyValidator(seed=42)
        
        loss = validator.compute_privacy_loss(
            epsilon=0.5,
            n_queries=1,
        )
        
        assert loss == 0.5
    
    def test_compute_privacy_loss_multiple(self):
        """Test privacy loss computation for multiple queries."""
        validator = PrivacyValidator(seed=42)
        
        loss = validator.compute_privacy_loss(
            epsilon=0.5,
            n_queries=10,
            composition="basic",
        )
        
        assert loss == 5.0  # Basic composition
    
    def test_compute_privacy_loss_advanced_composition(self):
        """Test privacy loss with advanced composition."""
        validator = PrivacyValidator(seed=42)
        
        basic_loss = validator.compute_privacy_loss(
            epsilon=0.5,
            n_queries=100,
            composition="basic",
        )
        
        advanced_loss = validator.compute_privacy_loss(
            epsilon=0.5,
            n_queries=100,
            composition="advanced",
        )
        
        # Advanced composition should give tighter bound
        assert advanced_loss < basic_loss
    
    def test_validate_noise_magnitude(self):
        """Test noise magnitude validation."""
        validator = PrivacyValidator(seed=42)
        
        result = validator.validate_noise_magnitude(
            original_vector=[1.0, 2.0, 3.0],
            noisy_vector=[1.1, 2.2, 2.8],
            epsilon=0.5,
            sensitivity=1.0,
        )
        
        # Should pass - noise is within expected range
        assert result.passed == True


class TestMembershipInferenceTest:
    """Test suite for MembershipInferenceTest class."""
    
    def test_mi_test_initialization(self):
        """Test membership inference test initialization."""
        mi_test = MembershipInferenceTest(
            attack_success_threshold=0.6,
            seed=42,
        )
        
        assert mi_test.attack_success_threshold == 0.6
    
    def test_mi_test_run_with_random_data(self):
        """Test MI attack on random data (should fail to infer)."""
        mi_test = MembershipInferenceTest(
            attack_success_threshold=0.6,
            seed=42,
        )
        
        # Create random signatures
        member_signatures = [
            ThreatSignature(
                signature_id=f"member-{i}",
                attack_type="prompt_injection",
                pattern_features=np.random.rand(128).tolist(),
                confidence=0.8,
                first_seen="2024-01",
                last_seen="2024-01",
            )
            for i in range(50)
        ]
        
        non_member_signatures = [
            ThreatSignature(
                signature_id=f"non-member-{i}",
                attack_type="prompt_injection",
                pattern_features=np.random.rand(128).tolist(),
                confidence=0.8,
                first_seen="2024-01",
                last_seen="2024-01",
            )
            for i in range(50)
        ]
        
        result = mi_test.run(
            members=member_signatures,
            non_members=non_member_signatures,
        )
        
        # Attack should fail on random data
        assert result.success_rate < 0.7  # Close to random (0.5)
    
    def test_mi_test_privacy_preserved(self):
        """Test MI attack reports privacy preserved."""
        mi_test = MembershipInferenceTest(
            attack_success_threshold=0.6,
            seed=42,
        )
        
        # Create signatures with DP noise
        member_signatures = [
            ThreatSignature(
                signature_id=f"member-{i}",
                attack_type="prompt_injection",
                pattern_features=np.random.rand(128).tolist(),
                confidence=0.8,
                first_seen="2024-01",
                last_seen="2024-01",
                noise_added=True,
            )
            for i in range(50)
        ]
        
        non_member_signatures = [
            ThreatSignature(
                signature_id=f"non-member-{i}",
                attack_type="prompt_injection",
                pattern_features=np.random.rand(128).tolist(),
                confidence=0.8,
                first_seen="2024-01",
                last_seen="2024-01",
            )
            for i in range(50)
        ]
        
        result = mi_test.run(
            members=member_signatures,
            non_members=non_member_signatures,
        )
        
        # Privacy should be preserved
        assert result.privacy_preserved == True


class TestPrivacyValidatorIntegration:
    """Integration tests for privacy validation."""
    
    def test_full_validation_pipeline(self):
        """Test complete validation pipeline."""
        validator = PrivacyValidator(seed=42)
        
        # Create test signatures
        signatures = [
            ThreatSignature(
                signature_id=f"sig-{i}",
                attack_type="prompt_injection",
                pattern_features=np.random.rand(128).tolist(),
                confidence=0.8,
                first_seen="2024-01",
                last_seen="2024-01",
                noise_added=True,
                privacy_metadata={"features": {"epsilon": 0.1}},
            )
            for i in range(20)
        ]
        
        # Run all validations
        results = []
        
        results.append(validator.validate_epsilon_delta(
            epsilon=0.5,
            delta=1e-5,
            max_epsilon=10.0,
            max_delta=1e-4,
        ))
        
        results.append(validator.test_anonymity_set(
            signatures,
            min_anonymity_set=2,
        ))
        
        results.append(validator.test_signature_unlinkability(signatures))
        
        # All should pass
        assert all(r.passed for r in results)


# Fixtures

@pytest.fixture
def privacy_validator():
    """Create a test privacy validator."""
    return PrivacyValidator(seed=42)


@pytest.fixture
def sample_signatures():
    """Create sample signatures for testing."""
    return [
        ThreatSignature(
            signature_id=f"sig-{i}",
            attack_type="prompt_injection",
            pattern_features=np.random.rand(128).tolist(),
            confidence=0.8,
            first_seen="2024-01",
            last_seen="2024-01",
            noise_added=True,
        )
        for i in range(20)
    ]
