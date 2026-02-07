"""
Temporal Workflow: Encounter Processing with SAGA Compensation.

Implements the complete encounter processing pipeline as a durable workflow
with automatic compensation (rollback) on failure.

SAGA Pattern:
Each step has a corresponding compensation action. If step N fails,
steps N-1 through 1 are compensated in reverse order.

Workflow Steps:
1. Validate encounter data
2. Generate SOAP note (Scribe Agent)          → compensate: delete draft
3. Check drug interactions (Safety Agent)      → compensate: remove flags
4. Suggest ICD-10/CPT codes (Coding Agent)    → compensate: remove suggestions
5. Predict readmission risk
6. Check security threats (Sentinel Agent)
7. Run fraud detection (Fraud Agent)
8. Store encounter                            → compensate: delete record

Execution Strategy:
- Steps 1, 6 are blocking safety gates
- Steps 2-4 can partially overlap
- Step 7 runs after coding (needs CPT codes)
- Step 8 is final commit
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Tuple

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

# Import activities with their wrappers
with workflow.unsafe.imports_passed_through():
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

logger = logging.getLogger(__name__)

# ── Retry Policies ──
FAST_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=3,
    backoff_coefficient=2.0,
)

AGENT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=3,
    backoff_coefficient=2.0,
)


@workflow.defn(name="EncounterProcessingWorkflow")
class EncounterProcessingWorkflow:
    """Main workflow for encounter processing with SAGA compensation.

    Orchestrates all 10 agents through a durable, fault-tolerant workflow.
    Each step is executed as a Temporal activity with retry policies.
    Failures trigger automatic compensation of all completed steps.

    Usage:
        result = await client.execute_workflow(
            EncounterProcessingWorkflow.run,
            encounter_data,
            id=f"encounter-{uuid}",
            task_queue="phoenix-guardian-queue",
        )
    """

    def __init__(self):
        self._status = "initializing"
        self._current_step = ""
        self._compensation_stack: List[Tuple[str, str]] = []

    @workflow.run
    async def run(self, encounter_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the encounter processing workflow.

        Args:
            encounter_data: Dict containing:
                - patient_mrn: str (required)
                - transcript: str or chief_complaint: str (required)
                - symptoms: List[str]
                - vitals: Dict[str, str]
                - medications: List[str]
                - exam_findings: str
                - patient_age: int
                - diagnosis: str

        Returns:
            Dict with complete processing results from all agents

        Raises:
            ApplicationError: On validation failure or security threat
        """
        self._status = "running"

        try:
            # ── Step 1: Validate Encounter Data ──
            self._current_step = "validation"
            workflow.logger.info(f"Step 1: Validating encounter {encounter_data.get('patient_mrn')}")

            validation = await workflow.execute_activity(
                validate_encounter,
                encounter_data,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=FAST_RETRY,
            )

            if not validation["valid"]:
                self._status = "failed_validation"
                raise ApplicationError(
                    f"Validation failed: {validation['errors']}",
                    type="VALIDATION_ERROR",
                    non_retryable=True,
                )

            # ── Step 2: Generate SOAP Note ──
            self._current_step = "soap_generation"
            workflow.logger.info("Step 2: Generating SOAP note")

            soap_result = await workflow.execute_activity(
                generate_soap_activity,
                encounter_data,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=AGENT_RETRY,
            )
            self._compensation_stack.append(("revert_soap", soap_result["id"]))

            # ── Step 3: Safety Check (Drug Interactions) ──
            self._current_step = "safety_check"
            workflow.logger.info("Step 3: Checking drug interactions")

            safety_result = await workflow.execute_activity(
                check_drug_interactions,
                {
                    "medications": encounter_data.get("medications", []),
                    "soap_id": soap_result["id"],
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=AGENT_RETRY,
            )
            self._compensation_stack.append(("revert_safety", safety_result["id"]))

            # Flag high-risk interactions for physician review
            if safety_result.get("high_risk_interaction"):
                workflow.logger.warning("HIGH-RISK drug interaction detected — flagging for review")
                await workflow.execute_activity(
                    flag_for_review,
                    {
                        "encounter_id": soap_result["id"],
                        "reason": "high_risk_drug_interaction",
                    },
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=FAST_RETRY,
                )

            # ── Step 4: Suggest Medical Codes ──
            self._current_step = "code_suggestion"
            workflow.logger.info("Step 4: Suggesting ICD-10/CPT codes")

            coding_result = await workflow.execute_activity(
                suggest_codes_activity,
                {"clinical_note": soap_result.get("soap_note", "")},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=AGENT_RETRY,
            )
            self._compensation_stack.append(("revert_codes", coding_result["id"]))

            # ── Step 5: Predict Readmission Risk ──
            self._current_step = "readmission_prediction"
            workflow.logger.info("Step 5: Predicting readmission risk")

            risk_result = await workflow.execute_activity(
                predict_readmission,
                encounter_data,
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=FAST_RETRY,
            )

            # ── Step 6: Security Threat Check ──
            self._current_step = "security_check"
            workflow.logger.info("Step 6: Checking for security threats")

            security_result = await workflow.execute_activity(
                check_security_threats,
                {"transcript": encounter_data.get("transcript", "")},
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=FAST_RETRY,
            )

            if security_result.get("threat_detected"):
                workflow.logger.error("SECURITY THREAT DETECTED — rolling back all steps")
                self._status = "security_threat"
                await self._compensate()
                raise ApplicationError(
                    f"Security threat detected: {security_result.get('threat_type')}",
                    type="SECURITY_THREAT",
                    non_retryable=True,
                )

            # ── Step 7: Fraud Detection ──
            self._current_step = "fraud_detection"
            workflow.logger.info("Step 7: Running fraud detection")

            fraud_result = await workflow.execute_activity(
                detect_fraud_activity,
                {
                    "procedure_codes": [
                        c.get("code", "") for c in coding_result.get("cpt_codes", [])
                        if isinstance(c, dict)
                    ],
                    "billed_cpt_code": (
                        coding_result.get("cpt_codes", [{}])[0].get("code", "99213")
                        if coding_result.get("cpt_codes")
                        else "99213"
                    ),
                    "encounter_duration": encounter_data.get("duration", 15),
                    "documented_elements": 6,
                },
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=AGENT_RETRY,
            )

            # ── Step 8: Store Encounter ──
            self._current_step = "storing"
            workflow.logger.info("Step 8: Storing processed encounter")

            final_result = await workflow.execute_activity(
                store_encounter,
                {
                    "soap": soap_result,
                    "codes": coding_result,
                    "risk": risk_result,
                    "safety": safety_result,
                    "fraud": fraud_result,
                },
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=FAST_RETRY,
            )

            # ── Success ──
            self._status = "completed"
            self._current_step = "done"

            return {
                "status": "completed",
                "encounter_id": final_result["id"],
                "soap_note": soap_result.get("soap_note", ""),
                "icd_codes": soap_result.get("icd_codes", []),
                "coding": {
                    "icd10": coding_result.get("icd10_codes", []),
                    "cpt": coding_result.get("cpt_codes", []),
                },
                "risk": {
                    "score": risk_result.get("risk_score", 0),
                    "level": risk_result.get("risk_level", "unknown"),
                },
                "safety": {
                    "interactions": safety_result.get("interactions", []),
                    "high_risk": safety_result.get("high_risk_interaction", False),
                },
                "fraud": {
                    "risk_level": fraud_result.get("risk_level", "LOW"),
                    "risk_score": fraud_result.get("risk_score", 0),
                },
                "security": {
                    "threat_detected": False,
                },
                "steps_completed": 8,
                "workflow_id": workflow.info().workflow_id,
            }

        except ApplicationError:
            # Re-raise application errors (validation, security)
            raise
        except Exception as e:
            # Unexpected error — compensate and re-raise
            workflow.logger.error(f"Workflow failed at step '{self._current_step}': {e}")
            self._status = "failed"
            await self._compensate()
            raise ApplicationError(
                f"Encounter processing failed at {self._current_step}: {str(e)}",
                type="PROCESSING_ERROR",
            )

    async def _compensate(self) -> None:
        """Execute SAGA compensation logic (rollback completed steps).

        Compensation runs in reverse order (LIFO) to undo all completed
        steps. Each compensation action is best-effort — failures are
        logged but don't prevent other compensations from running.
        """
        workflow.logger.info(
            f"Starting SAGA compensation for {len(self._compensation_stack)} steps"
        )

        for action, resource_id in reversed(self._compensation_stack):
            workflow.logger.info(f"Compensating: {action} for {resource_id}")

            try:
                if action == "revert_soap":
                    await workflow.execute_activity(
                        delete_soap_draft,
                        resource_id,
                        start_to_close_timeout=timedelta(seconds=10),
                        retry_policy=FAST_RETRY,
                    )
                elif action == "revert_safety":
                    await workflow.execute_activity(
                        remove_safety_flags,
                        resource_id,
                        start_to_close_timeout=timedelta(seconds=10),
                        retry_policy=FAST_RETRY,
                    )
                elif action == "revert_codes":
                    await workflow.execute_activity(
                        remove_code_suggestions,
                        resource_id,
                        start_to_close_timeout=timedelta(seconds=10),
                        retry_policy=FAST_RETRY,
                    )
            except Exception as comp_error:
                workflow.logger.error(
                    f"Compensation failed for {action}/{resource_id}: {comp_error}"
                )
                # Continue compensating remaining steps

        self._compensation_stack.clear()

    @workflow.query(name="get_status")
    def get_status(self) -> Dict[str, Any]:
        """Query current workflow status.

        Returns:
            Dict with status, current step, and compensation stack size
        """
        return {
            "status": self._status,
            "current_step": self._current_step,
            "pending_compensations": len(self._compensation_stack),
        }
