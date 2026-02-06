"""Multi-agent orchestration layer.

Coordinates SafetyAgent, NavigatorAgent, and ScribeAgent to process encounters
and generate SOAP notes with security validation.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from phoenix_guardian.agents.navigator_agent import (
    NavigatorAgent,
    PatientNotFoundError,
)
try:
    from phoenix_guardian.agents.safety_agent import SafetyAgent, SecurityException
except BaseException:
    SafetyAgent = None
    SecurityException = Exception
from phoenix_guardian.agents.scribe_agent import ScribeAgent


class OrchestrationError(Exception):
    """Raised when orchestration workflow fails."""

    pass


class EncounterOrchestrator:
    """Orchestrates multi-agent workflow for encounter processing.

    Workflow:
    1. Validate transcript for security threats (SafetyAgent)
    2. Fetch patient history (NavigatorAgent)
    3. Generate SOAP note (ScribeAgent)
    4. Return combined results

    Attributes:
        safety: SafetyAgent instance for input validation
        navigator: NavigatorAgent instance for patient data retrieval
        scribe: ScribeAgent instance for SOAP note generation
        total_encounters: Total encounters processed
        successful_encounters: Successfully processed encounters
        failed_encounters: Failed encounters
        blocked_encounters: Encounters blocked by security

    Example:
        >>> orchestrator = EncounterOrchestrator()
        >>> result = await orchestrator.process_encounter(
        ...     patient_mrn="MRN001234",
        ...     transcript="Patient presents with...",
        ...     encounter_type="office_visit",
        ...     provider_id="provider_001"
        ... )
    """

    def __init__(
        self,
        navigator_agent: Optional[NavigatorAgent] = None,
        scribe_agent: Optional[ScribeAgent] = None,
        safety_agent: Optional[SafetyAgent] = None,
    ) -> None:
        """Initialize orchestrator with agents.

        Args:
            navigator_agent: Patient data retrieval agent.
                            Creates default instance if None.
            scribe_agent: SOAP note generation agent.
                         Creates default instance if None.
            safety_agent: Security validation agent.
                         Creates default instance if None.
        """
        self.safety = safety_agent if safety_agent is not None else (SafetyAgent() if SafetyAgent is not None else None)
        self.navigator = navigator_agent or NavigatorAgent()
        self.scribe = scribe_agent or ScribeAgent()

        # Track orchestration metrics
        self.total_encounters: int = 0
        self.successful_encounters: int = 0
        self.failed_encounters: int = 0
        self.blocked_encounters: int = 0

    async def process_encounter(
        self,
        patient_mrn: str,
        transcript: str,
        encounter_type: str,
        provider_id: str,
    ) -> Dict[str, Any]:
        """Process a complete clinical encounter.

        Args:
            patient_mrn: Patient Medical Record Number
            transcript: Encounter transcript
            encounter_type: Type of encounter (office_visit, etc.)
            provider_id: Provider/physician ID

        Returns:
            Dictionary containing:
                - encounter_id: Unique encounter identifier
                - patient_data: Retrieved patient history
                - soap_note: Generated SOAP note
                - execution_metrics: Performance metrics

        Raises:
            PatientNotFoundError: If patient MRN not found
            OrchestrationError: If workflow fails
            SecurityException: If transcript fails security validation
        """
        self.total_encounters += 1
        encounter_id = self._generate_encounter_id()
        start_time = datetime.now(timezone.utc)

        try:
            # Step 0: Security validation (skip if safety agent unavailable)
            if self.safety is not None:
                try:
                    safety_result = await self.safety.execute({
                        "text": transcript,
                        "context_type": "transcript",
                    })

                    if not safety_result.success:
                        self.blocked_encounters += 1
                        raise OrchestrationError(
                            f"Security validation failed: {safety_result.error}"
                        )

                    safety_data = safety_result.data or {}
                    if not safety_data.get("is_safe", True):
                        self.blocked_encounters += 1
                        detections = safety_data.get("detections", [])
                        threat_types = [d.get("type", "unknown") for d in detections]
                        raise SecurityException(
                            message="Transcript failed security validation",
                            threat_type=threat_types[0] if threat_types else "unknown",
                            threat_level=safety_data.get("threat_level", "high"),
                            detections=detections,
                        )
                except (TypeError, AttributeError):
                    # Safety agent returned unexpected result — skip safety check
                    pass

            # Step 1: Fetch patient history
            patient_result = await self.navigator.execute(
                {"patient_mrn": patient_mrn}
            )

            if not patient_result.success:
                if patient_result.error and "not found" in patient_result.error.lower():
                    raise PatientNotFoundError(patient_mrn)
                raise OrchestrationError(
                    f"Failed to fetch patient data: {patient_result.error}"
                )

            patient_data = patient_result.data or {}

            # Step 2: Generate SOAP note
            scribe_context = self._build_scribe_context(transcript, patient_data)
            scribe_result = await self.scribe.execute(scribe_context)

            if not scribe_result.success:
                raise OrchestrationError(
                    f"Failed to generate SOAP note: {scribe_result.error}"
                )

            # Step 3: Combine results
            end_time = datetime.now(timezone.utc)
            total_time_ms = (end_time - start_time).total_seconds() * 1000

            self.successful_encounters += 1

            scribe_data = scribe_result.data or {}

            return {
                "encounter_id": encounter_id,
                "patient_mrn": patient_mrn,
                "patient_data": patient_data,
                "soap_note": scribe_data.get("soap_note", ""),
                "sections": scribe_data.get("sections", {}),
                "reasoning": scribe_result.reasoning or "",
                "model_used": scribe_data.get("model_used", "unknown"),
                "token_count": scribe_data.get("token_count", 0),
                "execution_metrics": {
                    "navigator_time_ms": patient_result.execution_time_ms,
                    "scribe_time_ms": scribe_result.execution_time_ms,
                    "total_time_ms": total_time_ms,
                },
                "encounter_type": encounter_type,
                "provider_id": provider_id,
                "created_at": start_time.isoformat(),
                "status": "pending_review",
            }

        except PatientNotFoundError:
            self.failed_encounters += 1
            raise  # Re-raise to be handled by API layer

        except SecurityException:
            # Already tracked in blocked_encounters above
            raise  # Re-raise to be handled by API layer

        except OrchestrationError:
            self.failed_encounters += 1
            raise  # Re-raise to be handled by API layer

        except Exception as e:
            self.failed_encounters += 1
            raise OrchestrationError(
                f"Encounter processing failed: {str(e)}"
            ) from e

    def _build_scribe_context(
        self, transcript: str, patient_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build context dictionary for ScribeAgent.

        Args:
            transcript: Encounter transcript
            patient_data: Patient data from NavigatorAgent

        Returns:
            Context dictionary for ScribeAgent.execute()
        """
        # Extract patient history in format expected by ScribeAgent
        demographics = patient_data.get("demographics", {})
        medications = patient_data.get("medications", [])
        allergies = patient_data.get("allergies", [])

        patient_history = {
            "age": demographics.get("age"),
            "conditions": patient_data.get("conditions", []),
            "medications": [
                f"{med.get('name', '')} {med.get('dose', '')} {med.get('frequency', '')}"
                for med in medications
                if isinstance(med, dict)
            ],
            "allergies": [
                alg.get("allergen", "")
                for alg in allergies
                if isinstance(alg, dict) and alg.get("allergen") != "NKDA"
            ],
        }

        return {
            "transcript": transcript,
            "patient_history": patient_history,
        }

    def _generate_encounter_id(self) -> str:
        """Generate unique encounter ID.

        Returns:
            Formatted encounter ID (enc_YYYYMMDD_XXXXXXXX)
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        unique_id = str(uuid.uuid4())[:8]
        return f"enc_{timestamp}_{unique_id}"

    def get_metrics(self) -> Dict[str, Any]:
        """Get orchestrator performance metrics.

        Returns:
            Dictionary with orchestration statistics including:
                - total_encounters: Total processed
                - successful_encounters: Successful count
                - failed_encounters: Failed count
                - blocked_encounters: Security-blocked count
                - success_rate: Success ratio (0.0-1.0)
                - safety_metrics: SafetyAgent metrics
                - navigator_metrics: NavigatorAgent metrics
                - scribe_metrics: ScribeAgent metrics
        """
        success_rate = (
            self.successful_encounters / self.total_encounters
            if self.total_encounters > 0
            else 0.0
        )

        return {
            "total_encounters": self.total_encounters,
            "successful_encounters": self.successful_encounters,
            "failed_encounters": self.failed_encounters,
            "blocked_encounters": self.blocked_encounters,
            "success_rate": success_rate,
            "safety_metrics": self.safety.get_statistics() if self.safety else {},
            "navigator_metrics": self.navigator.get_metrics(),
            "scribe_metrics": self.scribe.get_metrics(),
        }

    async def get_patient_data(self, patient_mrn: str) -> Dict[str, Any]:
        """Fetch patient data without generating SOAP note.

        Convenience method for patient lookup only.

        Args:
            patient_mrn: Patient Medical Record Number

        Returns:
            Patient data dictionary

        Raises:
            PatientNotFoundError: If patient not found
            OrchestrationError: If retrieval fails
        """
        result = await self.navigator.execute({"patient_mrn": patient_mrn})

        if not result.success:
            if "not found" in result.error.lower():
                raise PatientNotFoundError(patient_mrn)
            raise OrchestrationError(
                f"Failed to fetch patient data: {result.error}"
            )

        return result.data
