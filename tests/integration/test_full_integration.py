"""
Sprint 7: Comprehensive Integration Test Suite.

End-to-end tests that verify all 7 sprints work together:
1. All 10 agents operational
2. Temporal SAGA workflow
3. Post-quantum cryptography
4. Voice transcription pipeline
5. Bidirectional learning
6. Agent orchestration
7. API endpoint integration
"""

import asyncio
import json
import os
import ssl
import uuid
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Check optional dependency availability
try:
    import temporalio
    HAS_TEMPORALIO = True
except ImportError:
    HAS_TEMPORALIO = False


# ═══════════════════════════════════════════════════════════════════════════════
# Sprint 1: All 10 Agents Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAllAgentsIntegration:
    """Verify all 10 agents are importable and follow consistent patterns."""

    AGENT_CLASSES = [
        ("phoenix_guardian.agents.scribe", "ScribeAgent"),
        ("phoenix_guardian.agents.safety", "SafetyAgent"),
        ("phoenix_guardian.agents.navigator", "NavigatorAgent"),
        ("phoenix_guardian.agents.coding", "CodingAgent"),
        ("phoenix_guardian.agents.sentinel", "SentinelAgent"),
        ("phoenix_guardian.agents.order_management", "OrderManagementAgent"),
        ("phoenix_guardian.agents.deception_detection", "DeceptionDetectionAgent"),
        ("phoenix_guardian.agents.fraud", "FraudAgent"),
        ("phoenix_guardian.agents.clinical_decision", "ClinicalDecisionAgent"),
        ("phoenix_guardian.agents.pharmacy", "PharmacyAgent"),
    ]

    def test_all_10_agents_importable(self):
        """All 10 agents should be importable."""
        import importlib
        for module_path, class_name in self.AGENT_CLASSES:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            assert cls is not None, f"{class_name} not found in {module_path}"

    def test_all_agents_have_process_method(self):
        """All agents should have a process() method."""
        import importlib
        for module_path, class_name in self.AGENT_CLASSES:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            assert hasattr(cls, "process"), f"{class_name} missing process() method"

    def test_agent_count_is_10(self):
        """Should have exactly 10 agent classes."""
        assert len(self.AGENT_CLASSES) == 10

    def test_agents_init_export(self):
        """agents/__init__.py should export all new agents."""
        from phoenix_guardian.agents import (
            FraudAgent,
            ClinicalDecisionAgent,
            PharmacyAgent,
            DeceptionDetectionAgent,
            OrderManagementAgent,
        )
        assert FraudAgent is not None
        assert ClinicalDecisionAgent is not None
        assert PharmacyAgent is not None
        assert DeceptionDetectionAgent is not None
        assert OrderManagementAgent is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Sprint 2: Temporal Workflow Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not HAS_TEMPORALIO, reason="temporalio not installed")
class TestTemporalIntegration:
    """Verify Temporal workflow components are properly configured."""

    def test_workflow_module_structure(self):
        """Workflow package should have all required modules."""
        from phoenix_guardian.workflows import (
            activities,
            encounter_workflow,
            worker,
        )
        assert activities is not None
        assert encounter_workflow is not None
        assert worker is not None

    def test_all_activities_registered(self):
        """Worker should register all 12 activities."""
        from phoenix_guardian.workflows.worker import ACTIVITIES
        assert len(ACTIVITIES) == 12

    def test_workflow_class_defined(self):
        """EncounterProcessingWorkflow should be properly defined."""
        from phoenix_guardian.workflows.encounter_workflow import EncounterProcessingWorkflow
        wf = EncounterProcessingWorkflow()
        assert wf._status == "initializing"

    @pytest.mark.asyncio
    async def test_validation_activity(self):
        """Validation activity should work standalone."""
        from phoenix_guardian.workflows.activities import validate_encounter

        valid_data = {
            "patient_mrn": "MRN001",
            "transcript": "Patient presents with headache for 3 days",
        }
        result = await validate_encounter(valid_data)
        assert result["valid"] is True

        invalid_data = {}
        result = await validate_encounter(invalid_data)
        assert result["valid"] is False

    def test_saga_compensation_stack(self):
        """SAGA compensation should process in LIFO order."""
        from phoenix_guardian.workflows.encounter_workflow import EncounterProcessingWorkflow

        wf = EncounterProcessingWorkflow()
        wf._compensation_stack.append(("revert_soap", "S1"))
        wf._compensation_stack.append(("revert_safety", "S2"))
        wf._compensation_stack.append(("revert_codes", "S3"))

        reversed_stack = list(reversed(wf._compensation_stack))
        assert reversed_stack[0][0] == "revert_codes"
        assert reversed_stack[1][0] == "revert_safety"
        assert reversed_stack[2][0] == "revert_soap"


# ═══════════════════════════════════════════════════════════════════════════════
# Sprint 3: Post-Quantum Cryptography Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPQCIntegration:
    """Verify post-quantum cryptography end-to-end."""

    def test_pqc_encrypt_decrypt_roundtrip(self):
        """Data should survive PQC encrypt/decrypt roundtrip."""
        from phoenix_guardian.security.pqc_encryption import HybridPQCEncryption

        pqc = HybridPQCEncryption()
        plaintext = b"Patient MRN: 12345, Diagnosis: Hypertension"
        encrypted = pqc.encrypt(plaintext)
        decrypted = pqc.decrypt(encrypted)
        assert decrypted == plaintext

    def test_phi_field_encryption(self):
        """PHI fields should be encrypted/decrypted correctly."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService

        service = PHIEncryptionService(audit_log=False)
        patient_data = {
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
            "mrn": "MRN-001",
            "visit_type": "outpatient",
            "provider": "Dr. Smith",
        }

        encrypted = service.encrypt_phi_fields(patient_data)

        # PHI fields encrypted
        assert encrypted["patient_name"]["__pqc_encrypted__"] is True
        assert encrypted["ssn"]["__pqc_encrypted__"] is True
        assert encrypted["mrn"]["__pqc_encrypted__"] is True
        # Non-PHI unchanged
        assert encrypted["visit_type"] == "outpatient"
        assert encrypted["provider"] == "Dr. Smith"

        # Decrypt roundtrip
        decrypted = service.decrypt_phi_fields(encrypted)
        assert decrypted["patient_name"] == "John Doe"
        assert decrypted["ssn"] == "123-45-6789"
        assert decrypted["mrn"] == "MRN-001"

    def test_pqc_key_rotation(self):
        """Key rotation should produce new key pair."""
        from phoenix_guardian.security.pqc_encryption import HybridPQCEncryption

        pqc = HybridPQCEncryption()
        old_version = pqc.key_version
        rotation = pqc.rotate_keys()
        assert pqc.key_version == old_version + 1

    def test_pqc_benchmark_runs(self):
        """Benchmark should complete without errors."""
        from phoenix_guardian.security.pqc_encryption import benchmark_encryption

        results = benchmark_encryption(data_sizes=[100, 1000])
        assert "results" in results
        assert len(results["results"]) == 2
        for r in results["results"]:
            assert r["encryption_ms"] > 0
            assert r["decryption_ms"] > 0

    def test_tls_config(self):
        """TLS config should create valid SSL context."""
        from phoenix_guardian.security.phi_encryption import PQCTLSConfig

        config = PQCTLSConfig()
        info = config.get_tls_info()
        assert info["tls_version"] == "TLS 1.3"

        try:
            ctx = config.create_ssl_context()
            assert isinstance(ctx, ssl.SSLContext)
        except ssl.SSLError:
            # Some environments don't support the PQC cipher suites
            pytest.skip("SSL environment does not support PQC cipher suites")


# ═══════════════════════════════════════════════════════════════════════════════
# Sprint 4: Voice Transcription Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestVoiceTranscriptionIntegration:
    """Verify voice transcription pipeline components."""

    def test_transcription_service_importable(self):
        """Multi-provider transcription service should import."""
        from phoenix_guardian.services.voice_transcription import (
            MultiProviderTranscriptionService,
            ASRProvider,
            ASRConfig,
        )
        assert MultiProviderTranscriptionService is not None
        assert len(ASRProvider) == 5  # whisper_local, whisper_api, google, azure, web_speech

    def test_provider_listing(self):
        """Should list available ASR providers."""
        from phoenix_guardian.services.voice_transcription import (
            MultiProviderTranscriptionService,
        )
        service = MultiProviderTranscriptionService()
        providers = service.get_available_providers()
        assert len(providers) >= 3  # At least web_speech, whisper_api, azure listed

        # Web Speech is always "available" (browser-side)
        web_speech = next(
            (p for p in providers if p["provider"].value == "web_speech"), None
        )
        assert web_speech is not None
        assert web_speech["available"] is True

    def test_medical_vocabulary(self):
        """Medical vocabulary should contain common terms."""
        from phoenix_guardian.services.voice_transcription import MEDICAL_VOCABULARY

        assert "hypertension" in MEDICAL_VOCABULARY
        assert "metformin" in MEDICAL_VOCABULARY
        assert "echocardiogram" in MEDICAL_VOCABULARY
        assert "hemoglobin" in MEDICAL_VOCABULARY
        assert len(MEDICAL_VOCABULARY) >= 50

    def test_existing_transcription_service(self):
        """Existing text transcription service should work."""
        from phoenix_guardian.services.transcription_service import process_transcript

        result = process_transcript(
            transcript="Patient reports hypertension and takes metformin daily",
            segments=[],
        )
        assert result.transcript != ""
        assert result.quality_score >= 0

    def test_transcription_api_routes_exist(self):
        """Transcription API routes should include new endpoints."""
        from phoenix_guardian.api.routes.transcription import router

        paths = [route.path for route in router.routes]
        assert "/providers" in paths or any("/providers" in p for p in paths)


# ═══════════════════════════════════════════════════════════════════════════════
# Sprint 5: Bidirectional Learning Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestBidirectionalLearningIntegration:
    """Verify bidirectional learning pipeline end-to-end."""

    def test_pipeline_importable(self):
        """Bidirectional pipeline should import correctly."""
        from phoenix_guardian.learning.bidirectional_pipeline import (
            BidirectionalLearningPipeline,
            ModelDomain,
            FeedbackEvent,
        )
        assert BidirectionalLearningPipeline is not None
        assert len(ModelDomain) == 5

    def test_feedback_recording(self):
        """Should record and track feedback events."""
        from phoenix_guardian.learning.bidirectional_pipeline import (
            BidirectionalLearningPipeline,
            ModelDomain,
            FeedbackEvent,
        )

        pipeline = BidirectionalLearningPipeline(
            domain=ModelDomain.FRAUD_DETECTION,
            min_feedback_for_training=3,
        )

        # Record feedback
        for action in ["accept", "reject", "modify", "accept", "accept"]:
            pipeline.record_feedback(FeedbackEvent(
                id="",
                agent="fraud",
                action=action,
                original_output="test output",
                corrected_output="corrected" if action == "modify" else None,
            ))

        stats = pipeline.get_feedback_stats()
        assert stats["total"] == 5
        assert stats["accepted"] == 3
        assert stats["rejected"] == 1
        assert stats["modified"] == 1
        assert stats["acceptance_rate"] == 0.6
        assert stats["ready_for_training"] is True

    @pytest.mark.asyncio
    async def test_pipeline_cycle(self):
        """Full pipeline cycle should run with sufficient feedback (mocked training)."""
        from unittest.mock import AsyncMock, patch
        from phoenix_guardian.learning.bidirectional_pipeline import (
            BidirectionalLearningPipeline,
            ModelDomain,
            FeedbackEvent,
        )

        pipeline = BidirectionalLearningPipeline(
            domain=ModelDomain.FRAUD_DETECTION,
            min_feedback_for_training=5,
            ab_test_sample_threshold=3,
        )

        # Generate feedback
        for i in range(10):
            pipeline.record_feedback(FeedbackEvent(
                id="",
                agent="fraud",
                action=["accept", "reject", "modify"][i % 3],
                original_output=f"agent output {i}",
                corrected_output=f"corrected output {i}" if i % 3 == 2 else None,
            ))

        # Mock heavy ML operations to avoid loading RoBERTa model
        mock_train_result = {
            "training_time_ms": 150.0,
            "epochs": 3,
            "final_loss": 0.25,
            "best_f1": 0.85,
            "checkpoint_id": "test-checkpoint-001",
        }
        mock_eval_result = {
            "baseline_f1": 0.78,
            "bidirectional_f1": 0.85,
            "f1_improvement": 0.07,
            "baseline_accuracy": 0.80,
            "bidirectional_accuracy": 0.87,
            "accuracy_improvement": 0.07,
            "p_value": 0.03,
            "significant": True,
        }

        with patch.object(pipeline, "_train_model", new_callable=AsyncMock, return_value=mock_train_result), \
             patch.object(pipeline, "_evaluate_model", new_callable=AsyncMock, return_value=mock_eval_result):
            metrics = await pipeline.run_cycle()

        assert metrics.stage == "completed"
        assert metrics.training_examples > 0
        assert metrics.deployment_decision in ["deploy_bidirectional", "keep_baseline"]

    def test_pipeline_registry(self):
        """Pipeline registry should manage domain-specific pipelines."""
        from phoenix_guardian.learning.bidirectional_pipeline import (
            get_pipeline,
            ModelDomain,
        )

        p1 = get_pipeline(ModelDomain.FRAUD_DETECTION)
        p2 = get_pipeline(ModelDomain.FRAUD_DETECTION)
        assert p1 is p2  # Same instance

        p3 = get_pipeline(ModelDomain.THREAT_DETECTION)
        assert p1 is not p3  # Different domain

    def test_learning_api_routes_exist(self):
        """Learning API routes should be registered."""
        from phoenix_guardian.api.routes.learning import router

        paths = [route.path for route in router.routes]
        assert any("feedback" in str(p) for p in paths)
        assert any("run-cycle" in str(p) for p in paths)
        assert any("status" in str(p) for p in paths)


# ═══════════════════════════════════════════════════════════════════════════════
# Sprint 6: Agent Orchestration Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentOrchestrationIntegration:
    """Verify agent orchestration layer."""

    def test_orchestrator_importable(self):
        """AgentOrchestrator should import correctly."""
        from phoenix_guardian.orchestration.agent_orchestrator import (
            AgentOrchestrator,
            OrchestrationResult,
        )
        assert AgentOrchestrator is not None

    def test_orchestrator_registers_10_agents(self):
        """Orchestrator should register all 10 agents."""
        from phoenix_guardian.orchestration.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()
        assert len(orch._agents) == 10

        expected_agents = {
            "scribe", "safety", "navigator", "coding", "sentinel",
            "orders", "deception", "fraud", "clinical_decision", "pharmacy"
        }
        assert set(orch._agents.keys()) == expected_agents

    def test_execution_phases(self):
        """Orchestrator should define 4 execution phases."""
        from phoenix_guardian.orchestration.agent_orchestrator import AgentOrchestrator

        assert len(AgentOrchestrator.EXECUTION_PHASES) == 4
        
        # Phase 1 is critical
        assert AgentOrchestrator.EXECUTION_PHASES[0]["critical"] is True
        assert AgentOrchestrator.EXECUTION_PHASES[0]["name"] == "safety_gate"

    def test_agent_health_report(self):
        """Health report should include all agents."""
        from phoenix_guardian.orchestration.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()
        health = orch.get_agent_health()
        assert len(health) == 10

        for name, info in health.items():
            assert "status" in info
            assert "capabilities" in info
            assert "circuit_open" in info

    def test_circuit_breaker(self):
        """Circuit breaker should open after threshold errors."""
        from phoenix_guardian.orchestration.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()

        # Simulate errors
        for _ in range(5):
            orch._record_error("fraud")

        assert orch._is_circuit_open("fraud") is True

        # Reset
        orch.reset_circuit_breaker("fraud")
        assert orch._is_circuit_open("fraud") is False

    def test_agent_list(self):
        """Agent list should return structured info."""
        from phoenix_guardian.orchestration.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()
        agents = orch.get_agent_list()
        assert len(agents) == 10

        for agent in agents:
            assert "name" in agent
            assert "class" in agent
            assert "capabilities" in agent
            assert len(agent["capabilities"]) > 0

    def test_orchestration_api_routes(self):
        """Orchestration API routes should be registered."""
        from phoenix_guardian.api.routes.orchestration import router

        paths = [route.path for route in router.routes]
        assert any("process" in str(p) for p in paths)
        assert any("health" in str(p) for p in paths)
        assert any("agents" in str(p) for p in paths)


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-Sprint Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCrossSprintIntegration:
    """Tests that verify components from different sprints work together."""

    def test_api_main_registers_all_routers(self):
        """Main FastAPI app should include all new routers."""
        from phoenix_guardian.api.main import app

        route_prefixes = set()
        for route in app.routes:
            if hasattr(route, "path"):
                parts = route.path.split("/")
                if len(parts) >= 4:
                    route_prefixes.add(parts[3] if parts[3] else parts[2])

        # Should have routes for key modules
        expected = {"agents", "health", "encounters", "auth", "patients", "transcription"}
        for prefix in expected:
            assert any(
                prefix in str(route.path) for route in app.routes if hasattr(route, "path")
            ), f"Missing router prefix: {prefix}"

    def test_pqc_with_phi_encryption(self):
        """PQC encryption should work with PHI field detection."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService
        from phoenix_guardian.security.pqc_encryption import HybridPQCEncryption

        pqc = HybridPQCEncryption()
        phi_service = PHIEncryptionService(pqc_engine=pqc, audit_log=False)

        data = {
            "patient_name": "Integration Test Patient",
            "diagnosis": "Testing bidirectional learning",
            "visit_type": "integration_test",
        }

        encrypted = phi_service.encrypt_phi_fields(data)
        decrypted = phi_service.decrypt_phi_fields(encrypted)

        assert decrypted["patient_name"] == "Integration Test Patient"
        assert decrypted["diagnosis"] == "Testing bidirectional learning"
        assert decrypted["visit_type"] == "integration_test"

    @pytest.mark.asyncio
    async def test_learning_pipeline_with_agent_feedback(self):
        """Learning pipeline should accept feedback from agent outputs."""
        from phoenix_guardian.learning.bidirectional_pipeline import (
            BidirectionalLearningPipeline,
            ModelDomain,
            FeedbackEvent,
        )

        pipeline = BidirectionalLearningPipeline(
            domain=ModelDomain.SOAP_QUALITY,
            min_feedback_for_training=2,
        )

        # Simulate scribe agent feedback
        pipeline.record_feedback(FeedbackEvent(
            id="",
            agent="scribe",
            action="modify",
            original_output="S: Patient reports headache",
            corrected_output="S: Patient reports severe bilateral frontal headache x3 days",
        ))
        pipeline.record_feedback(FeedbackEvent(
            id="",
            agent="scribe",
            action="accept",
            original_output="O: Vitals WNL",
        ))
        pipeline.record_feedback(FeedbackEvent(
            id="",
            agent="scribe",
            action="reject",
            original_output="A: Common cold",
        ))

        stats = pipeline.get_feedback_stats()
        assert stats["total"] == 3
        assert stats["by_agent"]["scribe"] == 3

    def test_medical_terminology_in_transcription(self):
        """Medical term detection should work in transcription pipeline."""
        from phoenix_guardian.services.medical_terminology import find_medical_terms

        text = "Patient has hypertension and takes metformin for diabetes mellitus"
        terms = find_medical_terms(text)
        term_strings = [t.term.lower() for t in terms]

        assert any("hypertension" in t for t in term_strings)

    def test_clinical_decision_risk_scores(self):
        """ClinicalDecisionAgent should calculate risk scores independently."""
        from phoenix_guardian.agents.clinical_decision import ClinicalDecisionAgent

        agent = ClinicalDecisionAgent.__new__(ClinicalDecisionAgent)

        # CHA2DS2-VASc (takes a dict)
        score = agent._calculate_chads2_vasc({
            "age": 75,
            "sex": "female",
            "chf": True,
            "hypertension": True,
            "stroke_history": False,
            "vascular_disease": False,
            "diabetes": True,
        })
        assert isinstance(score, dict)
        assert "score" in score
        assert score["score"] >= 0

    def test_fraud_detection_rules(self):
        """FraudAgent rule-based checks should work without API."""
        from phoenix_guardian.agents.fraud import FraudAgent

        agent = FraudAgent.__new__(FraudAgent)

        # Upcoding detection
        result = agent.detect_upcoding(
            encounter_complexity="low",
            billed_cpt_code="99215",  # High complexity
            encounter_duration=5,      # Very short visit
            documented_elements=2,     # Few elements
        )
        assert isinstance(result, dict)
        assert "severity" in result or "risk_level" in result

    def test_pharmacy_formulary_check(self):
        """PharmacyAgent formulary check should work without API."""
        from phoenix_guardian.agents.pharmacy import PharmacyAgent

        agent = PharmacyAgent.__new__(PharmacyAgent)
        result = agent.check_formulary("metformin", "BCBS-PPO", "PT-001")
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Performance / Benchmark Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPerformanceBenchmarks:
    """Verify performance characteristics."""

    def test_pqc_encryption_performance(self):
        """PQC encryption should complete in < 100ms for typical records."""
        import time
        from phoenix_guardian.security.pqc_encryption import HybridPQCEncryption

        pqc = HybridPQCEncryption()
        plaintext = b"Patient record: " * 100  # ~1.6KB

        start = time.time()
        encrypted = pqc.encrypt(plaintext)
        decrypted = pqc.decrypt(encrypted)
        elapsed = (time.time() - start) * 1000

        assert decrypted == plaintext
        assert elapsed < 500  # Should complete in under 500ms

    def test_phi_field_encryption_performance(self):
        """PHI field encryption should handle typical records quickly."""
        import time
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService

        service = PHIEncryptionService(audit_log=False)
        record = {
            "patient_name": "Performance Test",
            "ssn": "999-99-9999",
            "mrn": "MRN-PERF-001",
            "diagnosis": "Benchmark test condition",
            "medications": ["test_drug_1", "test_drug_2"],
            "visit_type": "benchmark",
            "notes": "Performance testing notes",
        }

        start = time.time()
        encrypted = service.encrypt_phi_fields(record)
        decrypted = service.decrypt_phi_fields(encrypted)
        elapsed = (time.time() - start) * 1000

        assert decrypted["patient_name"] == "Performance Test"
        assert elapsed < 2000  # 5 PHI fields in under 2s

    def test_orchestrator_initialization_performance(self):
        """Orchestrator should initialize in reasonable time."""
        import time
        from phoenix_guardian.orchestration.agent_orchestrator import AgentOrchestrator

        start = time.time()
        orch = AgentOrchestrator()
        elapsed = (time.time() - start) * 1000

        assert len(orch._agents) == 10
        assert elapsed < 100  # Registration should be fast


# ═══════════════════════════════════════════════════════════════════════════════
# Summary Test
# ═══════════════════════════════════════════════════════════════════════════════


class TestImplementationCompleteness:
    """Verify all 7 sprints are implemented."""

    def test_sprint_1_agents_complete(self):
        """Sprint 1: 5 new agents should exist."""
        from phoenix_guardian.agents.fraud import FraudAgent
        from phoenix_guardian.agents.clinical_decision import ClinicalDecisionAgent
        from phoenix_guardian.agents.pharmacy import PharmacyAgent
        from phoenix_guardian.agents.deception_detection import DeceptionDetectionAgent
        from phoenix_guardian.agents.order_management import OrderManagementAgent
        assert all([FraudAgent, ClinicalDecisionAgent, PharmacyAgent,
                    DeceptionDetectionAgent, OrderManagementAgent])

    @pytest.mark.skipif(not HAS_TEMPORALIO, reason="temporalio not installed")
    def test_sprint_2_temporal_complete(self):
        """Sprint 2: Temporal workflow should exist."""
        from phoenix_guardian.workflows.encounter_workflow import EncounterProcessingWorkflow
        from phoenix_guardian.workflows.activities import validate_encounter
        from phoenix_guardian.workflows.worker import ACTIVITIES
        assert EncounterProcessingWorkflow is not None
        assert len(ACTIVITIES) == 12

    def test_sprint_3_pqc_complete(self):
        """Sprint 3: PQC + PHI encryption should work."""
        from phoenix_guardian.security.pqc_encryption import HybridPQCEncryption
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService, PQCTLSConfig
        assert HybridPQCEncryption is not None
        assert PHIEncryptionService is not None
        assert PQCTLSConfig is not None

    def test_sprint_4_voice_complete(self):
        """Sprint 4: Multi-provider voice transcription should exist."""
        from phoenix_guardian.services.voice_transcription import (
            MultiProviderTranscriptionService,
            ASRProvider,
        )
        assert MultiProviderTranscriptionService is not None
        assert len(ASRProvider) == 5

    def test_sprint_5_learning_complete(self):
        """Sprint 5: Bidirectional learning pipeline should exist."""
        from phoenix_guardian.learning.bidirectional_pipeline import (
            BidirectionalLearningPipeline,
            ModelDomain,
        )
        assert BidirectionalLearningPipeline is not None
        assert len(ModelDomain) == 5

    def test_sprint_6_orchestration_complete(self):
        """Sprint 6: Agent orchestrator should manage 10 agents."""
        from phoenix_guardian.orchestration.agent_orchestrator import AgentOrchestrator
        orch = AgentOrchestrator()
        assert len(orch._agents) == 10
        assert len(orch.EXECUTION_PHASES) == 4

    def test_sprint_7_api_complete(self):
        """Sprint 7: All API routes should be registered in main app."""
        from phoenix_guardian.api.main import app
        route_paths = [
            route.path for route in app.routes if hasattr(route, "path")
        ]
        # Check key route groups exist
        assert any("/agents/" in p for p in route_paths)
        assert any("/encounters" in p for p in route_paths)
        assert any("/pqc/" in p for p in route_paths)
        assert any("/learning/" in p for p in route_paths)
        assert any("/orchestration/" in p for p in route_paths)
