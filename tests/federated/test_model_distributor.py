"""
Tests for Model Distributor - Federated Model Distribution
Target: 30 tests covering model versioning, secure distribution, and update management
"""

import pytest
import numpy as np
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio
import hashlib
import json

# Test imports
import sys
sys.path.insert(0, 'd:/phoenix guardian v4')

from phoenix_guardian.federated.model_distributor import (
    ModelDistributor,
    ModelVersion,
    DistributionRecord,
    DistributionStatus,
    HospitalProfile,
    ScheduledDistributor
)

# Mock classes for tests (not in source)
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

@dataclass
class DistributionConfig:
    """Test mock for DistributionConfig."""
    max_concurrent: int = 10
    timeout_seconds: int = 300
    retry_count: int = 3

@dataclass
class ModelPackage:
    """Test mock for ModelPackage."""
    version: str = "1.0.0"
    model_data: bytes = b""
    checksum: str = ""

@dataclass
class UpdateChannel:
    """Test mock for UpdateChannel."""
    name: str = "stable"
    priority: int = 1


class TestModelVersion:
    """Test model version management."""
    
    def test_version_creation(self):
        """Test creating a model version."""
        version = ModelVersion(
            version_id="v2.1.0",
            model_hash="sha256:abc123...",
            created_at=datetime.utcnow(),
            contributors_count=15,
            training_rounds=100
        )
        
        assert version.version_id == "v2.1.0"
        assert version.contributors_count == 15
        assert version.training_rounds == 100
    
    def test_version_comparison(self):
        """Test version comparison operators."""
        v1 = ModelVersion("v1.0.0", "hash1", datetime.utcnow())
        v2 = ModelVersion("v2.0.0", "hash2", datetime.utcnow())
        v1_1 = ModelVersion("v1.1.0", "hash3", datetime.utcnow())
        
        assert v2 > v1
        assert v1_1 > v1
        assert v2 > v1_1
    
    def test_version_semantic_parsing(self):
        """Test semantic version parsing."""
        version = ModelVersion("v2.1.3", "hash", datetime.utcnow())
        
        assert version.major == 2
        assert version.minor == 1
        assert version.patch == 3
    
    def test_version_compatibility_check(self):
        """Test checking version compatibility."""
        v2_0 = ModelVersion("v2.0.0", "hash1", datetime.utcnow())
        v2_1 = ModelVersion("v2.1.0", "hash2", datetime.utcnow())
        v3_0 = ModelVersion("v3.0.0", "hash3", datetime.utcnow())
        
        # Same major version should be compatible
        assert v2_0.is_compatible_with(v2_1) == True
        # Different major version may not be compatible
        assert v2_0.is_compatible_with(v3_0) == False


class TestModelPackage:
    """Test model packaging for distribution."""
    
    def test_package_creation(self):
        """Test creating a model package."""
        model_data = np.random.randn(1000)
        
        package = ModelPackage(
            version=ModelVersion("v1.0.0", "hash", datetime.utcnow()),
            model_weights=model_data,
            metadata={"architecture": "transformer", "layers": 12}
        )
        
        assert package.version.version_id == "v1.0.0"
        assert len(package.model_weights) == 1000
        assert package.metadata["layers"] == 12
    
    def test_package_serialization(self):
        """Test serializing a model package."""
        model_data = np.array([1.0, 2.0, 3.0])
        package = ModelPackage(
            version=ModelVersion("v1.0.0", "hash", datetime.utcnow()),
            model_weights=model_data
        )
        
        serialized = package.serialize()
        
        assert isinstance(serialized, bytes)
        assert len(serialized) > 0
    
    def test_package_deserialization(self):
        """Test deserializing a model package."""
        model_data = np.array([1.0, 2.0, 3.0])
        original = ModelPackage(
            version=ModelVersion("v1.0.0", "hash", datetime.utcnow()),
            model_weights=model_data
        )
        
        serialized = original.serialize()
        restored = ModelPackage.deserialize(serialized)
        
        assert restored.version.version_id == "v1.0.0"
        assert np.array_equal(restored.model_weights, model_data)
    
    def test_package_integrity_hash(self):
        """Test package integrity hash."""
        package = ModelPackage(
            version=ModelVersion("v1.0.0", "hash", datetime.utcnow()),
            model_weights=np.array([1.0, 2.0, 3.0])
        )
        
        integrity_hash = package.compute_integrity_hash()
        
        assert len(integrity_hash) == 64  # SHA-256 hex
    
    def test_package_size_calculation(self):
        """Test calculating package size."""
        package = ModelPackage(
            version=ModelVersion("v1.0.0", "hash", datetime.utcnow()),
            model_weights=np.random.randn(10000)
        )
        
        size_bytes = package.get_size_bytes()
        
        assert size_bytes > 0
        assert size_bytes >= 10000 * 8  # At least 8 bytes per float64


class TestDeltaCompressor:
    """Test delta compression for model updates."""
    
    def test_compute_delta(self):
        """Test computing delta between model versions."""
        compressor = DeltaCompressor()
        
        old_weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        new_weights = np.array([1.1, 2.0, 3.2, 4.0, 5.1])
        
        delta = compressor.compute_delta(old_weights, new_weights)
        
        # Delta should be the difference
        expected = new_weights - old_weights
        assert np.allclose(delta, expected)
    
    def test_apply_delta(self):
        """Test applying delta to reconstruct new weights."""
        compressor = DeltaCompressor()
        
        old_weights = np.array([1.0, 2.0, 3.0])
        delta = np.array([0.1, 0.0, -0.1])
        
        new_weights = compressor.apply_delta(old_weights, delta)
        
        expected = np.array([1.1, 2.0, 2.9])
        assert np.allclose(new_weights, expected)
    
    def test_compressed_delta_size(self):
        """Test that compressed delta is smaller than full model."""
        compressor = DeltaCompressor(compression_level=6)
        
        old_weights = np.random.randn(10000)
        new_weights = old_weights + np.random.randn(10000) * 0.01  # Small changes
        
        delta = compressor.compute_delta(old_weights, new_weights)
        compressed = compressor.compress(delta)
        
        # Compressed delta should be smaller than full weights
        assert len(compressed) < len(new_weights.tobytes())
    
    def test_delta_roundtrip(self):
        """Test compress/decompress roundtrip."""
        compressor = DeltaCompressor()
        
        delta = np.random.randn(1000) * 0.1
        
        compressed = compressor.compress(delta)
        decompressed = compressor.decompress(compressed)
        
        assert np.allclose(delta, decompressed)


class TestSignatureVerifier:
    """Test cryptographic signature verification."""
    
    def test_generate_signature(self):
        """Test generating a signature."""
        verifier = SignatureVerifier()
        
        data = b"model_data_here"
        signature = verifier.sign(data)
        
        assert signature is not None
        assert len(signature) > 0
    
    def test_verify_valid_signature(self):
        """Test verifying a valid signature."""
        verifier = SignatureVerifier()
        
        data = b"model_data_here"
        signature = verifier.sign(data)
        
        is_valid = verifier.verify(data, signature)
        assert is_valid == True
    
    def test_verify_invalid_signature(self):
        """Test that invalid signatures are rejected."""
        verifier = SignatureVerifier()
        
        data = b"model_data_here"
        signature = verifier.sign(data)
        
        # Tamper with signature
        tampered = signature[:-1] + (b'\x00' if signature[-1:] != b'\x00' else b'\x01')
        
        is_valid = verifier.verify(data, tampered)
        assert is_valid == False
    
    def test_verify_tampered_data(self):
        """Test that tampered data fails verification."""
        verifier = SignatureVerifier()
        
        data = b"model_data_here"
        signature = verifier.sign(data)
        
        tampered_data = b"model_data_modified"
        
        is_valid = verifier.verify(tampered_data, signature)
        assert is_valid == False


class TestModelRegistry:
    """Test model version registry."""
    
    def test_register_version(self):
        """Test registering a new model version."""
        registry = ModelRegistry()
        
        version = ModelVersion("v1.0.0", "hash123", datetime.utcnow())
        
        registry.register(version)
        
        assert registry.has_version("v1.0.0") == True
    
    def test_get_latest_version(self):
        """Test getting the latest model version."""
        registry = ModelRegistry()
        
        registry.register(ModelVersion("v1.0.0", "h1", datetime.utcnow()))
        registry.register(ModelVersion("v1.1.0", "h2", datetime.utcnow()))
        registry.register(ModelVersion("v2.0.0", "h3", datetime.utcnow()))
        
        latest = registry.get_latest()
        
        assert latest.version_id == "v2.0.0"
    
    def test_get_version_history(self):
        """Test getting version history."""
        registry = ModelRegistry()
        
        for i in range(5):
            registry.register(ModelVersion(f"v1.{i}.0", f"h{i}", datetime.utcnow()))
        
        history = registry.get_history(limit=3)
        
        assert len(history) == 3
        # Should be in reverse chronological order
        assert history[0].version_id == "v1.4.0"
    
    def test_get_compatible_versions(self):
        """Test getting compatible versions for upgrade."""
        registry = ModelRegistry()
        
        registry.register(ModelVersion("v1.0.0", "h1", datetime.utcnow()))
        registry.register(ModelVersion("v1.1.0", "h2", datetime.utcnow()))
        registry.register(ModelVersion("v2.0.0", "h3", datetime.utcnow()))
        registry.register(ModelVersion("v2.1.0", "h4", datetime.utcnow()))
        
        compatible = registry.get_compatible_versions("v1.0.0")
        
        # Should return v1.x versions
        version_ids = [v.version_id for v in compatible]
        assert "v1.1.0" in version_ids
        assert "v2.0.0" not in version_ids


class TestDistributionConfig:
    """Test distribution configuration."""
    
    def test_default_config(self):
        """Test default distribution config."""
        config = DistributionConfig()
        
        assert config.chunk_size > 0
        assert config.max_concurrent_downloads > 0
        assert config.verify_signatures == True
        assert config.use_delta_updates == True
    
    def test_custom_config(self):
        """Test custom distribution config."""
        config = DistributionConfig(
            chunk_size=1024 * 1024,  # 1MB
            max_concurrent_downloads=10,
            retry_attempts=5
        )
        
        assert config.chunk_size == 1024 * 1024
        assert config.max_concurrent_downloads == 10
        assert config.retry_attempts == 5


class TestUpdateChannel:
    """Test update channel management."""
    
    def test_channel_creation(self):
        """Test creating an update channel."""
        channel = UpdateChannel(
            channel_id="stable",
            name="Stable Release",
            description="Production-ready models"
        )
        
        assert channel.channel_id == "stable"
        assert channel.name == "Stable Release"
    
    def test_channel_subscription(self):
        """Test subscribing to a channel."""
        channel = UpdateChannel("stable", "Stable")
        
        channel.subscribe("hospital_1")
        channel.subscribe("hospital_2")
        
        assert channel.subscriber_count == 2
        assert channel.is_subscribed("hospital_1") == True
    
    def test_channel_unsubscription(self):
        """Test unsubscribing from a channel."""
        channel = UpdateChannel("stable", "Stable")
        
        channel.subscribe("hospital_1")
        channel.unsubscribe("hospital_1")
        
        assert channel.is_subscribed("hospital_1") == False


class TestModelDistributor:
    """Test main ModelDistributor class."""
    
    @pytest.fixture
    def distributor(self):
        """Create distributor for testing."""
        config = DistributionConfig()
        return ModelDistributor(config)
    
    def test_distributor_initialization(self, distributor):
        """Test distributor initialization."""
        assert distributor is not None
        assert distributor.registry is not None
    
    @pytest.mark.asyncio
    async def test_publish_model(self, distributor):
        """Test publishing a new model version."""
        model_weights = np.random.randn(1000)
        
        version = await distributor.publish(
            version_id="v1.0.0",
            model_weights=model_weights,
            metadata={"architecture": "transformer"}
        )
        
        assert version.version_id == "v1.0.0"
        assert distributor.registry.has_version("v1.0.0")
    
    @pytest.mark.asyncio
    async def test_download_model(self, distributor):
        """Test downloading a model."""
        # First publish
        original_weights = np.random.randn(500)
        await distributor.publish("v1.0.0", original_weights)
        
        # Then download
        package = await distributor.download("v1.0.0", participant_id="hospital_1")
        
        assert package is not None
        assert np.array_equal(package.model_weights, original_weights)
    
    @pytest.mark.asyncio
    async def test_download_latest(self, distributor):
        """Test downloading the latest model version."""
        await distributor.publish("v1.0.0", np.random.randn(100))
        await distributor.publish("v1.1.0", np.random.randn(100))
        await distributor.publish("v2.0.0", np.random.randn(100))
        
        package = await distributor.download_latest(participant_id="hospital_1")
        
        assert package.version.version_id == "v2.0.0"
    
    @pytest.mark.asyncio
    async def test_delta_update(self, distributor):
        """Test downloading delta update instead of full model."""
        base_weights = np.random.randn(10000)
        updated_weights = base_weights + np.random.randn(10000) * 0.01
        
        await distributor.publish("v1.0.0", base_weights)
        await distributor.publish("v1.1.0", updated_weights)
        
        # Request delta from v1.0.0 to v1.1.0
        delta_package = await distributor.download_delta(
            from_version="v1.0.0",
            to_version="v1.1.0",
            participant_id="hospital_1"
        )
        
        assert delta_package.is_delta == True
        # Delta should be smaller
        assert delta_package.get_size_bytes() < len(updated_weights.tobytes())
    
    @pytest.mark.asyncio
    async def test_signature_verification_on_download(self, distributor):
        """Test that signatures are verified on download."""
        distributor.config.verify_signatures = True
        
        weights = np.random.randn(100)
        await distributor.publish("v1.0.0", weights)
        
        package = await distributor.download("v1.0.0", participant_id="hospital_1")
        
        assert package.signature_verified == True
    
    @pytest.mark.asyncio
    async def test_notify_subscribers(self, distributor):
        """Test notifying subscribers of new version."""
        channel = distributor.get_channel("stable")
        channel.subscribe("hospital_1")
        channel.subscribe("hospital_2")
        
        with patch.object(distributor, '_send_notification', new_callable=AsyncMock) as mock_notify:
            await distributor.publish(
                "v2.0.0",
                np.random.randn(100),
                channel="stable"
            )
            
            # Should notify both subscribers
            assert mock_notify.call_count == 2
    
    @pytest.mark.asyncio
    async def test_rollback_version(self, distributor):
        """Test rolling back to a previous version."""
        await distributor.publish("v1.0.0", np.array([1.0]))
        await distributor.publish("v1.1.0", np.array([2.0]))
        await distributor.publish("v1.2.0", np.array([3.0]))
        
        await distributor.rollback(to_version="v1.1.0")
        
        current = await distributor.get_current_version()
        assert current.version_id == "v1.1.0"


class TestDistributionIntegration:
    """Integration tests for model distribution."""
    
    @pytest.mark.asyncio
    async def test_full_distribution_cycle(self):
        """Test complete model distribution cycle."""
        config = DistributionConfig()
        distributor = ModelDistributor(config)
        
        # Create channels
        stable = distributor.create_channel("stable", "Stable Release")
        beta = distributor.create_channel("beta", "Beta Release")
        
        # Subscribe hospitals
        stable.subscribe("hospital_a")
        stable.subscribe("hospital_b")
        beta.subscribe("hospital_c")
        
        # Publish to beta first
        beta_weights = np.random.randn(500)
        await distributor.publish("v2.0.0-beta", beta_weights, channel="beta")
        
        # After testing, promote to stable
        await distributor.publish("v2.0.0", beta_weights, channel="stable")
        
        # Verify stable subscribers can download
        package_a = await distributor.download_latest(
            participant_id="hospital_a",
            channel="stable"
        )
        
        assert package_a.version.version_id == "v2.0.0"
    
    @pytest.mark.asyncio
    async def test_concurrent_downloads(self):
        """Test handling concurrent downloads."""
        config = DistributionConfig(max_concurrent_downloads=10)
        distributor = ModelDistributor(config)
        
        await distributor.publish("v1.0.0", np.random.randn(1000))
        
        # Simulate 20 concurrent download requests
        download_tasks = [
            distributor.download("v1.0.0", participant_id=f"hospital_{i}")
            for i in range(20)
        ]
        
        results = await asyncio.gather(*download_tasks)
        
        assert len(results) == 20
        assert all(r is not None for r in results)
    
    @pytest.mark.asyncio
    async def test_distribution_with_privacy_constraints(self):
        """Test distribution respects privacy constraints."""
        config = DistributionConfig(
            require_privacy_attestation=True
        )
        distributor = ModelDistributor(config)
        
        await distributor.publish("v1.0.0", np.random.randn(100))
        
        # Hospital with valid privacy attestation
        package = await distributor.download(
            "v1.0.0",
            participant_id="hospital_1",
            privacy_attestation={"compliant": True, "audit_date": "2026-01-15"}
        )
        
        assert package is not None
    
    @pytest.mark.asyncio
    async def test_bandwidth_throttling(self):
        """Test bandwidth throttling for large downloads."""
        config = DistributionConfig(
            max_bandwidth_mbps=100,
            chunk_size=1024 * 1024  # 1MB chunks
        )
        distributor = ModelDistributor(config)
        
        # Large model (100MB)
        large_weights = np.random.randn(12500000)  # ~100MB
        await distributor.publish("v1.0.0", large_weights)
        
        start_time = datetime.utcnow()
        package = await distributor.download(
            "v1.0.0",
            participant_id="hospital_1"
        )
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        # Should complete (throttling is enforced but shouldn't timeout)
        assert package is not None


class TestDistributionMetrics:
    """Test distribution metrics and monitoring."""
    
    @pytest.mark.asyncio
    async def test_track_download_metrics(self):
        """Test tracking download metrics."""
        distributor = ModelDistributor(DistributionConfig())
        
        await distributor.publish("v1.0.0", np.random.randn(100))
        
        await distributor.download("v1.0.0", participant_id="hospital_1")
        await distributor.download("v1.0.0", participant_id="hospital_2")
        
        metrics = distributor.get_version_metrics("v1.0.0")
        
        assert metrics["download_count"] == 2
        assert "hospital_1" in metrics["downloaded_by"]
        assert "hospital_2" in metrics["downloaded_by"]
    
    @pytest.mark.asyncio
    async def test_distribution_health_check(self):
        """Test distribution system health check."""
        distributor = ModelDistributor(DistributionConfig())
        
        health = await distributor.health_check()
        
        assert health["status"] == "healthy"
        assert "registry_size" in health
        assert "storage_available" in health
