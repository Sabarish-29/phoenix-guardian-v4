"""
Integration Tests for Federated Learning System
Target: 30 tests covering end-to-end workflows, cross-component interactions
"""

import pytest
import numpy as np
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio
import json

# Test imports
import sys
sys.path.insert(0, 'd:/phoenix guardian v4')

from phoenix_guardian.federated.differential_privacy import (
    DifferentialPrivacyEngine,
    PrivacyBudget,
    PrivacyAccountant
)
from phoenix_guardian.federated.threat_signature import (
    ThreatSignature,
    ThreatSignatureGenerator
)
from phoenix_guardian.federated.privacy_validator import PrivacyValidator
from phoenix_guardian.federated.attack_pattern_extractor import (
    AttackPatternExtractor,
    FeatureVector,
    AttackTypeClassifier
)
from phoenix_guardian.federated.contribution_pipeline import ContributionPipeline
from phoenix_guardian.federated.secure_aggregator import (
    SecureAggregator,
    AggregatedSignature
)
from phoenix_guardian.federated.global_model_builder import GlobalModelBuilder
from phoenix_guardian.federated.model_distributor import (
    ModelDistributor,
    ModelVersion,
    DistributionStatus
)
from phoenix_guardian.federated.privacy_auditor import (
    PrivacyAuditor,
    AuditResult
)

# Mock classes for tests (not in source)
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

@dataclass
class AggregationConfig:
    """Test mock for AggregationConfig."""
    min_contributors: int = 3
    max_contributors: int = 1000

@dataclass
class DistributionConfig:
    """Test mock for DistributionConfig."""
    max_concurrent: int = 10

@dataclass
class AuditConfig:
    """Test mock for AuditConfig."""
    log_all_events: bool = True


class TestEndToEndFederatedLearning:
    """End-to-end tests for federated learning workflow."""
    
    @pytest.fixture
    def federated_system(self):
        """Create complete federated learning system for testing."""
        return {
            "dp_engine": DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5),
            "signature_generator": ThreatSignatureGenerator(),
            "privacy_validator": PrivacyValidator(),
            "pattern_extractor": AttackPatternExtractor(),
            "contribution_pipeline": ContributionPipeline(),
            "aggregator": SecureAggregator(AggregationConfig(min_contributors=3)),
            "model_builder": GlobalModelBuilder(),
            "distributor": ModelDistributor(DistributionConfig()),
            "auditor": PrivacyAuditor(AuditConfig())
        }
    
    @pytest.mark.asyncio
    async def test_complete_training_round(self, federated_system):
        """Test a complete federated training round from contributions to distribution."""
        dp_engine = federated_system["dp_engine"]
        aggregator = federated_system["aggregator"]
        model_builder = federated_system["model_builder"]
        distributor = federated_system["distributor"]
        auditor = federated_system["auditor"]
        
        # Phase 1: Hospitals submit contributions
        hospitals = ["hospital_a", "hospital_b", "hospital_c", "hospital_d"]
        
        await aggregator.start_round(model_version="v1.0")
        
        for hospital in hospitals:
            # Generate local model update with DP
            local_update = np.random.randn(500)
            private_update = dp_engine.add_noise(local_update)
            
            # Submit contribution
            await aggregator.submit_contribution({
                "contributor_id": hospital,
                "model_update": private_update,
                "data_size": np.random.randint(5000, 15000),
                "privacy_budget_used": 0.05
            })
            
            # Log to auditor
            auditor.log_contribution(hospital, "round_1", 0.05, 5e-7)
        
        # Phase 2: Aggregate contributions
        aggregation_result = await aggregator.aggregate()
        
        assert aggregation_result.num_contributors == 4
        assert aggregation_result.aggregated_model is not None
        
        # Phase 3: Build global model
        global_model = await model_builder.build(
            base_version="v1.0",
            aggregated_updates=aggregation_result.aggregated_model,
            round_id="round_1"
        )
        
        assert global_model is not None
        
        # Phase 4: Distribute to participants
        version = await distributor.publish(
            version_id="v1.1.0",
            model_weights=global_model.weights,
            metadata={"round": "round_1", "contributors": 4}
        )
        
        # Phase 5: Verify audit trail
        report = auditor.generate_report(
            period_start=datetime.utcnow() - timedelta(hours=1),
            period_end=datetime.utcnow()
        )
        
        assert report.privacy_metrics["num_contributions"] == 4
    
    @pytest.mark.asyncio
    async def test_threat_intelligence_sharing(self, federated_system):
        """Test threat signature generation and sharing workflow."""
        pattern_extractor = federated_system["pattern_extractor"]
        signature_generator = federated_system["signature_generator"]
        dp_engine = federated_system["dp_engine"]
        aggregator = federated_system["aggregator"]
        
        # Hospital A detects an attack
        attack_data = {
            "attack_type": "ransomware",
            "indicators": [
                {"type": "file_hash", "value": "abc123..."},
                {"type": "c2_domain", "value": "malicious.example.com"},
                {"type": "process_behavior", "value": "encrypt_files_recursive"}
            ],
            "timestamp": datetime.utcnow(),
            "severity": "critical"
        }
        
        # Extract attack pattern
        pattern = pattern_extractor.extract(attack_data)
        
        assert pattern.attack_type == "ransomware"
        assert len(pattern.indicators) >= 1
        
        # Generate threat signature with differential privacy
        signature = signature_generator.generate(
            pattern=pattern,
            privacy_engine=dp_engine
        )
        
        assert signature is not None
        assert signature.is_private == True
        
        # Share via federated system
        await aggregator.start_round(model_version="threat_v1")
        
        await aggregator.submit_contribution({
            "contributor_id": "hospital_a",
            "model_update": signature.to_vector(),
            "data_size": 1,
            "privacy_budget_used": 0.1
        })
        
        # Other hospitals would contribute their own threat intelligence
        # ...
    
    @pytest.mark.asyncio
    async def test_privacy_preservation_verification(self, federated_system):
        """Test that privacy is preserved throughout the pipeline."""
        dp_engine = federated_system["dp_engine"]
        privacy_validator = federated_system["privacy_validator"]
        contribution_pipeline = federated_system["contribution_pipeline"]
        
        # Original sensitive data
        sensitive_data = np.array([100.0, 200.0, 300.0, 400.0, 500.0])
        
        # Process through pipeline with privacy
        result = await contribution_pipeline.process(
            data=sensitive_data,
            participant_id="hospital_1",
            privacy_engine=dp_engine
        )
        
        # Validate privacy guarantees
        validation = privacy_validator.validate(
            original=sensitive_data,
            processed=result.processed_data,
            epsilon=dp_engine.epsilon,
            delta=dp_engine.delta
        )
        
        assert validation.is_valid == True
        assert validation.epsilon_verified <= dp_engine.epsilon
        
        # Ensure reconstruction attack fails
        with pytest.raises(Exception):
            privacy_validator.attempt_reconstruction(result.processed_data)


class TestCrossComponentInteractions:
    """Test interactions between federated learning components."""
    
    @pytest.mark.asyncio
    async def test_aggregator_distributor_integration(self):
        """Test aggregator output flows correctly to distributor."""
        aggregator = SecureAggregator(AggregationConfig(min_contributors=3))
        distributor = ModelDistributor(DistributionConfig())
        
        # Run aggregation
        await aggregator.start_round(model_version="v1.0")
        
        for i in range(3):
            await aggregator.submit_contribution({
                "contributor_id": f"hospital_{i}",
                "model_update": np.random.randn(100),
                "data_size": 5000
            })
        
        result = await aggregator.aggregate()
        
        # Feed to distributor
        version = await distributor.publish(
            version_id="v1.1.0",
            model_weights=result.aggregated_model,
            metadata={
                "aggregation_round": result.round_id,
                "num_contributors": result.num_contributors
            }
        )
        
        # Verify distribution ready
        assert distributor.registry.has_version("v1.1.0")
        
        # Participants can download
        package = await distributor.download("v1.1.0", "hospital_0")
        assert np.array_equal(package.model_weights, result.aggregated_model)
    
    @pytest.mark.asyncio
    async def test_privacy_engine_auditor_integration(self):
        """Test privacy engine events are captured by auditor."""
        dp_engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5)
        auditor = PrivacyAuditor(AuditConfig())
        
        # Connect engine to auditor
        dp_engine.set_audit_callback(auditor.log_privacy_operation)
        
        # Perform privacy operations
        for i in range(5):
            data = np.random.randn(50)
            dp_engine.add_noise(data, participant_id=f"hospital_{i}")
        
        # Check auditor captured events
        events = auditor.trail.get_events_by_type("privacy_operation")
        assert len(events) == 5
    
    @pytest.mark.asyncio
    async def test_pattern_extractor_signature_generator_pipeline(self):
        """Test attack pattern to signature generation pipeline."""
        extractor = AttackPatternExtractor()
        generator = ThreatSignatureGenerator()
        
        # Raw attack event
        raw_event = {
            "source_ip": "192.168.1.100",
            "destination_ip": "10.0.0.50",
            "port": 445,
            "payload_signature": "SMB_EXPLOIT_PATTERN",
            "timestamp": datetime.utcnow()
        }
        
        # Extract pattern
        pattern = extractor.extract(raw_event)
        
        # Generate signature
        signature = generator.generate(pattern)
        
        assert signature is not None
        assert signature.pattern_id == pattern.pattern_id
        assert signature.detection_rules is not None


class TestFaultTolerance:
    """Test fault tolerance and error handling."""
    
    @pytest.mark.asyncio
    async def test_aggregation_with_dropout(self):
        """Test aggregation handles participant dropout."""
        aggregator = SecureAggregator(AggregationConfig(
            min_contributors=3,
            handle_dropout=True
        ))
        
        await aggregator.start_round(model_version="v1.0")
        
        # 5 hospitals start contributing
        for i in range(5):
            await aggregator.submit_contribution({
                "contributor_id": f"hospital_{i}",
                "model_update": np.random.randn(100),
                "data_size": 5000
            })
        
        # 2 hospitals drop out (simulate by removing)
        await aggregator.remove_contributor("hospital_3")
        await aggregator.remove_contributor("hospital_4")
        
        # Should still aggregate with remaining 3
        result = await aggregator.aggregate()
        
        assert result.num_contributors == 3
        assert "hospital_3" not in result.contributor_ids
    
    @pytest.mark.asyncio
    async def test_distribution_retry_on_failure(self):
        """Test distribution retries on transient failures."""
        distributor = ModelDistributor(DistributionConfig(
            retry_attempts=3,
            retry_delay_seconds=0.1
        ))
        
        await distributor.publish("v1.0.0", np.random.randn(100))
        
        # Mock transient failures
        failure_count = [0]
        original_download = distributor._perform_download
        
        async def flaky_download(*args, **kwargs):
            failure_count[0] += 1
            if failure_count[0] < 3:
                raise ConnectionError("Transient failure")
            return await original_download(*args, **kwargs)
        
        with patch.object(distributor, '_perform_download', flaky_download):
            package = await distributor.download("v1.0.0", "hospital_1")
        
        # Should succeed after retries
        assert package is not None
        assert failure_count[0] == 3
    
    @pytest.mark.asyncio
    async def test_privacy_budget_exhaustion_handling(self):
        """Test graceful handling when privacy budget exhausted."""
        auditor = PrivacyAuditor(AuditConfig())
        auditor.ledger._total_epsilon = 0.5
        auditor.ledger._remaining_epsilon = 0.05  # Nearly exhausted
        
        # Attempt to log contribution that would exceed budget
        with pytest.raises(Exception) as exc_info:
            auditor.log_contribution(
                participant_id="hospital_1",
                round_id="round_1",
                epsilon_used=0.1,  # Exceeds remaining
                delta_used=1e-6
            )
        
        # Should provide informative error
        assert "budget" in str(exc_info.value).lower()


class TestScalability:
    """Test system scalability."""
    
    @pytest.mark.asyncio
    async def test_large_scale_aggregation(self):
        """Test aggregation with many contributors."""
        aggregator = SecureAggregator(AggregationConfig(
            min_contributors=10,
            max_contributors=100
        ))
        
        await aggregator.start_round(model_version="v1.0")
        
        # 50 contributors
        for i in range(50):
            await aggregator.submit_contribution({
                "contributor_id": f"hospital_{i}",
                "model_update": np.random.randn(1000),
                "data_size": np.random.randint(1000, 10000)
            })
        
        import time
        start = time.time()
        result = await aggregator.aggregate()
        elapsed = time.time() - start
        
        assert result.num_contributors == 50
        assert elapsed < 5.0  # Should complete in reasonable time
    
    @pytest.mark.asyncio
    async def test_high_frequency_audit_logging(self):
        """Test auditor handles high-frequency logging."""
        auditor = PrivacyAuditor(AuditConfig())
        
        # Log 1000 events rapidly
        import time
        start = time.time()
        
        for i in range(1000):
            auditor.log_contribution(
                f"hospital_{i % 20}",
                f"round_{i % 10}",
                0.001,
                1e-8
            )
        
        elapsed = time.time() - start
        
        assert len(auditor.trail.events) == 1000
        assert elapsed < 2.0  # Should handle rapidly


class TestSecurityScenarios:
    """Test security-related scenarios."""
    
    @pytest.mark.asyncio
    async def test_malicious_contribution_detection(self):
        """Test detecting and rejecting malicious contributions."""
        aggregator = SecureAggregator(AggregationConfig(
            min_contributors=3,
            enable_byzantine_detection=True
        ))
        
        await aggregator.start_round(model_version="v1.0")
        
        # Normal contributions
        for i in range(4):
            await aggregator.submit_contribution({
                "contributor_id": f"hospital_{i}",
                "model_update": np.random.randn(100) * 0.1,  # Normal range
                "data_size": 5000
            })
        
        # Malicious contribution (gradient poisoning attempt)
        await aggregator.submit_contribution({
            "contributor_id": "malicious_actor",
            "model_update": np.ones(100) * 1000,  # Abnormally large
            "data_size": 5000
        })
        
        result = await aggregator.aggregate()
        
        # Malicious contribution should be excluded
        assert "malicious_actor" in result.excluded_contributors
    
    @pytest.mark.asyncio
    async def test_model_integrity_verification(self):
        """Test model integrity is verified on distribution."""
        distributor = ModelDistributor(DistributionConfig(
            verify_signatures=True
        ))
        
        original_weights = np.random.randn(100)
        await distributor.publish("v1.0.0", original_weights)
        
        # Normal download
        package = await distributor.download("v1.0.0", "hospital_1")
        assert package.signature_verified == True
        
        # Simulate tampered package
        with patch.object(distributor, '_verify_signature', return_value=False):
            with pytest.raises(Exception) as exc_info:
                await distributor.download("v1.0.0", "hospital_2")
            
            assert "integrity" in str(exc_info.value).lower() or "signature" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_replay_attack_prevention(self):
        """Test prevention of replay attacks on contributions."""
        aggregator = SecureAggregator(AggregationConfig(min_contributors=3))
        
        await aggregator.start_round(model_version="v1.0")
        
        contribution = {
            "contributor_id": "hospital_1",
            "model_update": np.random.randn(100),
            "data_size": 5000,
            "nonce": str(uuid4()),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # First submission succeeds
        await aggregator.submit_contribution(contribution)
        
        # Replay attack (same nonce) should fail
        with pytest.raises(ValueError, match="replay|duplicate|already"):
            await aggregator.submit_contribution(contribution)


class TestPrivacyGuarantees:
    """Test differential privacy guarantees."""
    
    def test_epsilon_budget_tracking(self):
        """Test epsilon budget is accurately tracked."""
        dp_engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5)
        
        initial_budget = dp_engine.remaining_epsilon
        
        # Perform operations
        for _ in range(5):
            dp_engine.add_noise(np.random.randn(100))
        
        # Budget should decrease
        assert dp_engine.remaining_epsilon < initial_budget
    
    def test_composition_theorem(self):
        """Test privacy composition follows theoretical bounds."""
        accountant = PrivacyAccountant(epsilon=1.0, delta=1e-5)
        
        # Sequential operations
        operations = [
            {"epsilon": 0.1, "delta": 1e-6},
            {"epsilon": 0.2, "delta": 1e-6},
            {"epsilon": 0.15, "delta": 1e-6}
        ]
        
        for op in operations:
            accountant.record_operation(op["epsilon"], op["delta"])
        
        total_epsilon, total_delta = accountant.get_total_privacy_cost()
        
        # Should follow advanced composition
        naive_sum = sum(op["epsilon"] for op in operations)
        assert total_epsilon <= naive_sum  # Advanced composition is tighter
    
    def test_privacy_amplification_subsampling(self):
        """Test privacy amplification through subsampling."""
        dp_engine = DifferentialPrivacyEngine(epsilon=0.5, delta=1e-5)
        
        # Full dataset operation
        full_epsilon = dp_engine.compute_privacy_cost(sampling_rate=1.0)
        
        # Subsampled operation (10% of data)
        subsampled_epsilon = dp_engine.compute_privacy_cost(sampling_rate=0.1)
        
        # Subsampling should amplify privacy
        assert subsampled_epsilon < full_epsilon


class TestRealWorldScenarios:
    """Test realistic healthcare scenarios."""
    
    @pytest.mark.asyncio
    async def test_hospital_network_collaboration(self):
        """Test multiple hospitals collaborating on threat detection."""
        # Setup federated system
        aggregator = SecureAggregator(AggregationConfig(min_contributors=3))
        pattern_extractor = AttackPatternExtractor()
        signature_generator = ThreatSignatureGenerator()
        
        # Simulate hospital network
        hospitals = [
            {"id": "mayo_clinic", "attacks_detected": 3},
            {"id": "cleveland_clinic", "attacks_detected": 2},
            {"id": "johns_hopkins", "attacks_detected": 4},
            {"id": "mass_general", "attacks_detected": 1}
        ]
        
        await aggregator.start_round(model_version="threat_model_v1")
        
        for hospital in hospitals:
            # Each hospital generates local threat intelligence
            local_patterns = []
            for i in range(hospital["attacks_detected"]):
                pattern = pattern_extractor.extract({
                    "attack_type": np.random.choice(["ransomware", "phishing", "insider"]),
                    "severity": np.random.choice(["low", "medium", "high", "critical"]),
                    "timestamp": datetime.utcnow()
                })
                local_patterns.append(pattern)
            
            # Generate combined signature
            combined_signature = signature_generator.generate_combined(local_patterns)
            
            # Submit to federated system
            await aggregator.submit_contribution({
                "contributor_id": hospital["id"],
                "model_update": combined_signature.to_vector(),
                "data_size": hospital["attacks_detected"]
            })
        
        # Aggregate threat intelligence
        result = await aggregator.aggregate()
        
        assert result.num_contributors == 4
        assert result.total_data_size == 10  # Total attacks detected
    
    @pytest.mark.asyncio
    async def test_24_hour_protection_cycle(self):
        """Test the 24-hour threat protection distribution cycle."""
        distributor = ModelDistributor(DistributionConfig())
        
        # Morning: New threats detected
        morning_model = np.random.randn(1000)
        await distributor.publish(
            "v1.0.0",
            morning_model,
            metadata={"cycle": "morning", "threats_incorporated": 5}
        )
        
        # Evening: Additional threats incorporated
        evening_model = morning_model + np.random.randn(1000) * 0.1
        await distributor.publish(
            "v1.1.0",
            evening_model,
            metadata={"cycle": "evening", "threats_incorporated": 8}
        )
        
        # All hospitals should be able to get latest protection
        for hospital in ["hospital_1", "hospital_2", "hospital_3"]:
            package = await distributor.download_latest(participant_id=hospital)
            assert package.version.version_id == "v1.1.0"
            assert package.metadata["threats_incorporated"] == 8
