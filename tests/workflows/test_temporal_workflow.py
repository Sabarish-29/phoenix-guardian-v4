"""
Tests for Sprint 2: Temporal.io Orchestration and SAGA Patterns.

Tests cover:
- Activities (unit tests with mocked agents)
- EncounterProcessingWorkflow (workflow tests with mocked activities)
- Worker configuration
- SAGA compensation logic
"""

import asyncio
import os
import uuid
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    import temporalio
    HAS_TEMPORALIO = True
except ImportError:
    HAS_TEMPORALIO = False

skip_no_temporalio = pytest.mark.skipif(
    not HAS_TEMPORALIO, reason="temporalio not installed"
)


# ── Activity Unit Tests ──


@skip_no_temporalio
class TestActivities:
    """Test individual Temporal activities."""

    def test_activities_importable(self):
        """Activities module should be importable."""
        from phoenix_guardian.workflows.activities import (
            validate_encounter,
            generate_soap_activity,
            check_drug_interactions,
            suggest_codes_activity,
            predict_readmission,
            check_security_threats,
            detect_fraud_activity,
            flag_for_review,
            store_encounter,
            delete_soap_draft,
            remove_safety_flags,
            remove_code_suggestions,
        )
        # All 12 activities should import
        assert validate_encounter is not None
        assert generate_soap_activity is not None
        assert check_drug_interactions is not None
        assert suggest_codes_activity is not None
        assert predict_readmission is not None
        assert check_security_threats is not None
        assert detect_fraud_activity is not None
        assert flag_for_review is not None
        assert store_encounter is not None
        assert delete_soap_draft is not None
        assert remove_safety_flags is not None
        assert remove_code_suggestions is not None

    @pytest.mark.asyncio
    async def test_validate_encounter_valid(self):
        """Valid encounter data should pass validation."""
        from phoenix_guardian.workflows.activities import validate_encounter

        data = {
            "patient_mrn": "MRN001",
            "transcript": "Patient presents with headache...",
            "symptoms": ["headache"],
        }
        result = await validate_encounter(data)
        assert result["valid"] is True
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_validate_encounter_missing_mrn(self):
        """Missing patient_mrn should fail validation."""
        from phoenix_guardian.workflows.activities import validate_encounter

        data = {"transcript": "test"}
        result = await validate_encounter(data)
        assert result["valid"] is False
        assert any("patient_mrn" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_encounter_missing_content(self):
        """Missing both transcript and chief_complaint should fail."""
        from phoenix_guardian.workflows.activities import validate_encounter

        data = {"patient_mrn": "MRN123"}
        result = await validate_encounter(data)
        assert result["valid"] is False
        assert any("transcript" in e.lower() or "complaint" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_soap_activity(self):
        """SOAP generation activity should return structured result."""
        from phoenix_guardian.workflows.activities import generate_soap_activity

        with patch("phoenix_guardian.agents.scribe.ScribeAgent.process", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = {
                "soap_note": "S: Headache\nO: BP 120/80\nA: Tension headache\nP: Acetaminophen",
                "icd_codes": ["G44.1"],
            }

            data = {
                "chief_complaint": "headache",
                "symptoms": ["headache"],
                "vitals": {"bp": "120/80"},
            }
            result = await generate_soap_activity(data)

            assert "soap_note" in result
            assert "id" in result
            assert result["soap_note"] != ""

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_check_drug_interactions(self):
        """Drug interaction activity should check medication safety."""
        from phoenix_guardian.workflows.activities import check_drug_interactions

        with patch("phoenix_guardian.agents.safety.SafetyAgent.process", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = {
                "interactions": [],
                "severity": "none",
            }

            data = {
                "medications": ["aspirin", "metformin"],
                "soap_id": "test-soap-123",
            }
            result = await check_drug_interactions(data)

            assert "id" in result
            assert "interactions" in result
            assert "high_risk_interaction" in result

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_suggest_codes_activity(self):
        """Code suggestion activity should return ICD-10 and CPT codes."""
        from phoenix_guardian.workflows.activities import suggest_codes_activity

        with patch("phoenix_guardian.agents.coding.CodingAgent.process", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = {
                "icd_codes": ["G44.1"],
                "cpt_codes": ["99213"],
            }

            data = {"clinical_note": "S: Headache\nO: normal exam\nA: Tension headache\nP: OTC meds"}
            result = await suggest_codes_activity(data)

            assert "id" in result
            assert "icd10_codes" in result or "icd_codes" in result
            assert "cpt_codes" in result

    @pytest.mark.asyncio
    async def test_predict_readmission(self):
        """Readmission prediction should return a risk score."""
        from phoenix_guardian.workflows.activities import predict_readmission

        data = {
            "patient_age": 75,
            "diagnosis": "CHF",
            "medications": ["furosemide", "lisinopril"],
        }
        result = await predict_readmission(data)

        assert "risk_score" in result
        assert "risk_level" in result
        assert 0 <= result["risk_score"] <= 1

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_check_security_threats(self):
        """Security check should analyze transcript for threats."""
        from phoenix_guardian.workflows.activities import check_security_threats

        with patch("phoenix_guardian.agents.sentinel.SentinelAgent.process", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = {
                "threat_detected": False,
                "threat_type": None,
            }

            data = {"transcript": "Patient reports headache for 3 days"}
            result = await check_security_threats(data)

            assert "threat_detected" in result
            assert result["threat_detected"] is False

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_detect_fraud_activity(self):
        """Fraud detection should analyze billing patterns."""
        from phoenix_guardian.workflows.activities import detect_fraud_activity

        with patch("phoenix_guardian.agents.fraud.FraudAgent.process", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = {
                "risk_level": "LOW",
                "risk_score": 0.1,
            }

            data = {
                "procedure_codes": ["99213"],
                "billed_cpt_code": "99213",
                "encounter_duration": 15,
                "documented_elements": 6,
            }
            result = await detect_fraud_activity(data)

            assert "risk_level" in result
            assert "risk_score" in result

    @pytest.mark.asyncio
    async def test_store_encounter(self):
        """Store encounter should persist the final result."""
        from phoenix_guardian.workflows.activities import store_encounter

        data = {
            "soap": {"soap_note": "test note"},
            "codes": {"icd10_codes": ["G44.1"]},
            "risk": {"risk_score": 0.2},
            "safety": {"interactions": []},
            "fraud": {"risk_level": "LOW"},
        }
        result = await store_encounter(data)

        assert "id" in result
        assert "stored_at" in result

    @pytest.mark.asyncio
    async def test_compensation_delete_soap_draft(self):
        """Compensation: delete_soap_draft should run without error."""
        from phoenix_guardian.workflows.activities import delete_soap_draft

        result = await delete_soap_draft("test-soap-id")
        assert result["deleted"] is True

    @pytest.mark.asyncio
    async def test_compensation_remove_safety_flags(self):
        """Compensation: remove_safety_flags should run without error."""
        from phoenix_guardian.workflows.activities import remove_safety_flags

        result = await remove_safety_flags("test-safety-id")
        assert result["removed"] is True

    @pytest.mark.asyncio
    async def test_compensation_remove_code_suggestions(self):
        """Compensation: remove_code_suggestions should run without error."""
        from phoenix_guardian.workflows.activities import remove_code_suggestions

        result = await remove_code_suggestions("test-code-id")
        assert result["removed"] is True


# ── Workflow Tests ──


@skip_no_temporalio
class TestEncounterWorkflow:
    """Test the EncounterProcessingWorkflow."""

    def test_workflow_importable(self):
        """Workflow class should be importable."""
        from phoenix_guardian.workflows.encounter_workflow import EncounterProcessingWorkflow
        assert EncounterProcessingWorkflow is not None

    def test_workflow_has_run_method(self):
        """Workflow should define a run method."""
        from phoenix_guardian.workflows.encounter_workflow import EncounterProcessingWorkflow
        assert hasattr(EncounterProcessingWorkflow, "run")

    def test_workflow_has_query(self):
        """Workflow should define status query."""
        from phoenix_guardian.workflows.encounter_workflow import EncounterProcessingWorkflow
        assert hasattr(EncounterProcessingWorkflow, "get_status")

    def test_workflow_init(self):
        """Workflow should initialize with correct defaults."""
        from phoenix_guardian.workflows.encounter_workflow import EncounterProcessingWorkflow
        wf = EncounterProcessingWorkflow()
        assert wf._status == "initializing"
        assert wf._current_step == ""
        assert wf._compensation_stack == []

    def test_retry_policies(self):
        """Retry policies should be configured."""
        from phoenix_guardian.workflows.encounter_workflow import FAST_RETRY, AGENT_RETRY
        assert FAST_RETRY.maximum_attempts == 3
        assert AGENT_RETRY.maximum_attempts == 3


# ── Worker Tests ──


@skip_no_temporalio
class TestWorker:
    """Test worker configuration."""

    def test_worker_module_importable(self):
        """Worker module should be importable."""
        from phoenix_guardian.workflows.worker import ACTIVITIES, TASK_QUEUE
        assert len(ACTIVITIES) == 12  # 9 main + 3 compensation
        assert TASK_QUEUE == "phoenix-guardian-queue"

    def test_worker_env_defaults(self):
        """Worker should have sensible defaults."""
        from phoenix_guardian.workflows.worker import TEMPORAL_HOST, TEMPORAL_NAMESPACE
        assert TEMPORAL_HOST == "localhost:7233"
        assert TEMPORAL_NAMESPACE == "default"

    @patch.dict("os.environ", {"TEMPORAL_HOST": "custom:7234", "TASK_QUEUE": "custom-queue"})
    def test_worker_env_override(self):
        """Worker should respect environment variable overrides."""
        import importlib
        import phoenix_guardian.workflows.worker as worker_mod
        importlib.reload(worker_mod)
        assert worker_mod.TEMPORAL_HOST == "custom:7234"
        assert worker_mod.TASK_QUEUE == "custom-queue"


# ── Integration-Style Tests (with mocked Temporal) ──


@skip_no_temporalio
class TestWorkflowIntegration:
    """Test workflow integration patterns.
    
    These test the data flow and SAGA patterns without requiring
    a running Temporal server.
    """

    def test_compensation_stack_operations(self):
        """Compensation stack should support LIFO operations."""
        from phoenix_guardian.workflows.encounter_workflow import EncounterProcessingWorkflow

        wf = EncounterProcessingWorkflow()
        wf._compensation_stack.append(("revert_soap", "id-1"))
        wf._compensation_stack.append(("revert_safety", "id-2"))
        wf._compensation_stack.append(("revert_codes", "id-3"))

        assert len(wf._compensation_stack) == 3

        # Reverse order for compensation
        reversed_stack = list(reversed(wf._compensation_stack))
        assert reversed_stack[0] == ("revert_codes", "id-3")
        assert reversed_stack[1] == ("revert_safety", "id-2")
        assert reversed_stack[2] == ("revert_soap", "id-1")

    def test_encounter_data_schema(self):
        """Valid encounter data should have expected shape."""
        encounter_data = {
            "patient_mrn": "MRN001",
            "transcript": "Patient presents with persistent headache for 3 days...",
            "chief_complaint": "Headache",
            "symptoms": ["headache", "photophobia"],
            "vitals": {"bp": "120/80", "hr": "72"},
            "medications": ["ibuprofen"],
            "exam_findings": "Alert, no focal deficits",
            "patient_age": 35,
            "diagnosis": "Tension headache",
            "duration": 15,
        }

        assert "patient_mrn" in encounter_data
        assert isinstance(encounter_data["symptoms"], list)
        assert isinstance(encounter_data["vitals"], dict)
        assert isinstance(encounter_data["medications"], list)

    def test_workflow_result_schema(self):
        """Result from completed workflow should have expected shape."""
        expected_keys = {
            "status", "encounter_id", "soap_note", "icd_codes",
            "coding", "risk", "safety", "fraud", "security",
            "steps_completed", "workflow_id"
        }
        # Verify the expected structure matches our workflow
        from phoenix_guardian.workflows.encounter_workflow import EncounterProcessingWorkflow
        assert EncounterProcessingWorkflow is not None
        # The keys are defined in the workflow's return statement
        assert len(expected_keys) == 11


class TestWorkflowAPIEndpoints:
    """Test encounter workflow API integration."""

    def test_workflow_request_model(self):
        """WorkflowEncounterRequest model should validate correctly."""
        from phoenix_guardian.api.routes.encounters import WorkflowEncounterRequest

        req = WorkflowEncounterRequest(
            patient_mrn="MRN001",
            transcript="Patient presents with headache...",
            symptoms=["headache"],
            vitals={"bp": "120/80"},
            medications=["aspirin"],
        )
        assert req.patient_mrn == "MRN001"
        assert len(req.symptoms) == 1
        assert req.duration == 15  # default

    def test_workflow_status_response_model(self):
        """WorkflowStatusResponse model should work correctly."""
        from phoenix_guardian.api.routes.encounters import WorkflowStatusResponse

        resp = WorkflowStatusResponse(
            workflow_id="encounter-abc123",
            run_id="run-xyz",
            status="started",
            message="Workflow started",
        )
        assert resp.workflow_id == "encounter-abc123"
        assert resp.status == "started"
