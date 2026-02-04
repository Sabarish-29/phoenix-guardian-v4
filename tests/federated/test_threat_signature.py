"""
Tests for Threat Signature Generation.

This module contains 22 tests covering:
    - Signature creation and validation
    - Privacy sanitization
    - Timestamp coarsening
    - Forbidden field detection
    - Signature similarity
"""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch

from phoenix_guardian.federated.threat_signature import (
    ThreatSignature,
    ThreatSignatureGenerator,
    FORBIDDEN_FIELDS,
    coarsen_timestamp_to_month,
)
from phoenix_guardian.federated.differential_privacy import DifferentialPrivacyEngine


class TestThreatSignature:
    """Test suite for ThreatSignature dataclass."""
    
    def test_signature_creation(self):
        """Test basic signature creation."""
        sig = ThreatSignature(
            signature_id="test-123",
            attack_type="prompt_injection",
            pattern_features=[0.1] * 128,
            confidence=0.85,
            first_seen="2024-01",
            last_seen="2024-01",
        )
        
        assert sig.signature_id == "test-123"
        assert sig.attack_type == "prompt_injection"
        assert len(sig.pattern_features) == 128
        assert sig.confidence == 0.85
    
    def test_signature_validation_timestamp_format(self):
        """Test timestamp must be YYYY-MM format."""
        with pytest.raises(ValueError, match="month-level"):
            ThreatSignature(
                signature_id="test-123",
                attack_type="prompt_injection",
                pattern_features=[0.1] * 128,
                confidence=0.85,
                first_seen="2024-01-15",  # Too specific!
                last_seen="2024-01",
            )
    
    def test_signature_validation_confidence_range(self):
        """Test confidence must be in [0, 1]."""
        with pytest.raises(ValueError, match="confidence"):
            ThreatSignature(
                signature_id="test-123",
                attack_type="prompt_injection",
                pattern_features=[0.1] * 128,
                confidence=1.5,  # Invalid!
                first_seen="2024-01",
                last_seen="2024-01",
            )
    
    def test_signature_validation_feature_dimension(self):
        """Test pattern_features must be 128-dimensional."""
        with pytest.raises(ValueError, match="128"):
            ThreatSignature(
                signature_id="test-123",
                attack_type="prompt_injection",
                pattern_features=[0.1] * 64,  # Wrong dimension!
                confidence=0.85,
                first_seen="2024-01",
                last_seen="2024-01",
            )
    
    def test_signature_to_dict(self):
        """Test signature serialization."""
        sig = ThreatSignature(
            signature_id="test-123",
            attack_type="prompt_injection",
            pattern_features=[0.1] * 128,
            confidence=0.85,
            first_seen="2024-01",
            last_seen="2024-01",
        )
        
        d = sig.to_dict()
        
        assert d["signature_id"] == "test-123"
        assert d["attack_type"] == "prompt_injection"
        assert len(d["pattern_features"]) == 128
    
    def test_signature_from_dict(self):
        """Test signature deserialization."""
        data = {
            "signature_id": "test-123",
            "attack_type": "prompt_injection",
            "pattern_features": [0.1] * 128,
            "confidence": 0.85,
            "first_seen": "2024-01",
            "last_seen": "2024-01",
            "noise_added": True,
            "privacy_metadata": {},
        }
        
        sig = ThreatSignature.from_dict(data)
        
        assert sig.signature_id == "test-123"
        assert sig.noise_added == True
    
    def test_signature_similarity_identical(self):
        """Test identical signatures are similar."""
        features = [0.5] * 128
        
        sig1 = ThreatSignature(
            signature_id="sig-1",
            attack_type="prompt_injection",
            pattern_features=features.copy(),
            confidence=0.85,
            first_seen="2024-01",
            last_seen="2024-01",
        )
        
        sig2 = ThreatSignature(
            signature_id="sig-2",
            attack_type="prompt_injection",
            pattern_features=features.copy(),
            confidence=0.85,
            first_seen="2024-01",
            last_seen="2024-01",
        )
        
        assert sig1.is_similar_to(sig2, threshold=0.99)
    
    def test_signature_similarity_different(self):
        """Test different signatures are not similar."""
        sig1 = ThreatSignature(
            signature_id="sig-1",
            attack_type="prompt_injection",
            pattern_features=[1.0] * 128,
            confidence=0.85,
            first_seen="2024-01",
            last_seen="2024-01",
        )
        
        sig2 = ThreatSignature(
            signature_id="sig-2",
            attack_type="prompt_injection",
            pattern_features=[-1.0] * 128,
            confidence=0.85,
            first_seen="2024-01",
            last_seen="2024-01",
        )
        
        assert not sig1.is_similar_to(sig2, threshold=0.5)
    
    def test_signature_hash(self):
        """Test signature hash computation."""
        sig = ThreatSignature(
            signature_id="test-123",
            attack_type="prompt_injection",
            pattern_features=[0.1] * 128,
            confidence=0.85,
            first_seen="2024-01",
            last_seen="2024-01",
        )
        
        hash1 = sig.compute_hash()
        hash2 = sig.compute_hash()
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex


class TestTimestampCoarsening:
    """Test timestamp coarsening functions."""
    
    def test_coarsen_full_timestamp(self):
        """Test coarsening full ISO timestamp."""
        result = coarsen_timestamp_to_month("2024-01-15T10:30:00")
        assert result == "2024-01"
    
    def test_coarsen_date_only(self):
        """Test coarsening date-only timestamp."""
        result = coarsen_timestamp_to_month("2024-01-15")
        assert result == "2024-01"
    
    def test_coarsen_already_month(self):
        """Test already-coarsened timestamp."""
        result = coarsen_timestamp_to_month("2024-01")
        assert result == "2024-01"
    
    def test_coarsen_datetime_object(self):
        """Test coarsening datetime object."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = coarsen_timestamp_to_month(dt)
        assert result == "2024-01"


class TestThreatSignatureGenerator:
    """Test suite for ThreatSignatureGenerator class."""
    
    def test_generator_initialization(self):
        """Test generator initialization."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5)
        generator = ThreatSignatureGenerator(privacy_engine=engine)
        
        assert generator.privacy_engine == engine
    
    def test_generate_signature_basic(self):
        """Test basic signature generation."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        generator = ThreatSignatureGenerator(privacy_engine=engine)
        
        event = {
            "attack_type": "prompt_injection",
            "features": [0.1] * 128,
            "confidence": 0.85,
            "timestamp": "2024-01-15T10:30:00",
        }
        
        sig = generator.generate_signature(event)
        
        assert sig is not None
        assert sig.attack_type == "prompt_injection"
        assert sig.noise_added == True
        assert sig.first_seen == "2024-01"
    
    def test_generate_signature_sanitizes_forbidden_fields(self):
        """Test generator removes forbidden fields."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        generator = ThreatSignatureGenerator(privacy_engine=engine)
        
        event = {
            "attack_type": "prompt_injection",
            "features": [0.1] * 128,
            "confidence": 0.85,
            "timestamp": "2024-01-15",
            "hospital_id": "HOSP-123",  # FORBIDDEN!
            "patient_id": "PAT-456",    # FORBIDDEN!
            "ip_address": "192.168.1.1", # FORBIDDEN!
        }
        
        sig = generator.generate_signature(event)
        
        # Signature should exist but forbidden fields removed
        sig_dict = sig.to_dict()
        sig_str = str(sig_dict).lower()
        
        assert "hosp-123" not in sig_str
        assert "pat-456" not in sig_str
        assert "192.168.1.1" not in sig_str
    
    def test_generate_signature_adds_noise(self):
        """Test generator adds DP noise to features."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        generator = ThreatSignatureGenerator(privacy_engine=engine)
        
        original_features = [0.5] * 128
        event = {
            "attack_type": "prompt_injection",
            "features": original_features.copy(),
            "confidence": 0.85,
            "timestamp": "2024-01-15",
        }
        
        sig = generator.generate_signature(event)
        
        # Features should be different due to noise
        assert sig.pattern_features != original_features
        assert sig.noise_added == True
    
    def test_generate_signature_includes_privacy_metadata(self):
        """Test signature includes privacy metadata."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        generator = ThreatSignatureGenerator(privacy_engine=engine)
        
        event = {
            "attack_type": "prompt_injection",
            "features": [0.1] * 128,
            "confidence": 0.85,
            "timestamp": "2024-01-15",
        }
        
        sig = generator.generate_signature(event)
        
        assert sig.privacy_metadata is not None
        assert "features" in sig.privacy_metadata
        assert "epsilon" in sig.privacy_metadata["features"]
    
    def test_validate_forbidden_fields(self):
        """Test forbidden field validation."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5)
        generator = ThreatSignatureGenerator(privacy_engine=engine)
        
        # These should be detected as forbidden
        for field in ["hospital_id", "patient_name", "mrn", "ssn", "email"]:
            assert generator._is_forbidden_field(field)
        
        # These should be allowed
        for field in ["attack_type", "confidence", "features"]:
            assert not generator._is_forbidden_field(field)
    
    def test_batch_generate_signatures(self):
        """Test batch signature generation."""
        engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)
        generator = ThreatSignatureGenerator(privacy_engine=engine)
        
        events = [
            {
                "attack_type": "prompt_injection",
                "features": [0.1 * i] * 128,
                "confidence": 0.8,
                "timestamp": "2024-01-15",
            }
            for i in range(1, 6)
        ]
        
        signatures = generator.batch_generate(events)
        
        assert len(signatures) == 5
        assert all(s.noise_added for s in signatures)


class TestForbiddenFields:
    """Test forbidden field constants."""
    
    def test_forbidden_fields_includes_hospital_id(self):
        """Test hospital_id is forbidden."""
        assert "hospital_id" in FORBIDDEN_FIELDS
    
    def test_forbidden_fields_includes_patient_id(self):
        """Test patient_id is forbidden."""
        assert "patient_id" in FORBIDDEN_FIELDS
    
    def test_forbidden_fields_includes_pii(self):
        """Test PII fields are forbidden."""
        pii_fields = ["ssn", "mrn", "email", "patient_name"]
        for field in pii_fields:
            assert field in FORBIDDEN_FIELDS


# Fixtures

@pytest.fixture
def privacy_engine():
    """Create a test privacy engine."""
    return DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5, seed=42)


@pytest.fixture
def signature_generator(privacy_engine):
    """Create a test signature generator."""
    return ThreatSignatureGenerator(privacy_engine=privacy_engine)


@pytest.fixture
def sample_event():
    """Create a sample security event."""
    return {
        "attack_type": "prompt_injection",
        "features": [0.1] * 128,
        "confidence": 0.85,
        "timestamp": "2024-01-15T10:30:00",
    }


@pytest.fixture
def sample_signature():
    """Create a sample threat signature."""
    return ThreatSignature(
        signature_id="test-123",
        attack_type="prompt_injection",
        pattern_features=[0.1] * 128,
        confidence=0.85,
        first_seen="2024-01",
        last_seen="2024-01",
        noise_added=True,
        privacy_metadata={"features": {"epsilon": 0.1}},
    )
