"""Dependency injection for FastAPI.

Provides singleton instances of agents and orchestrator.
"""

import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, Optional

from phoenix_guardian.agents.navigator_agent import NavigatorAgent
from phoenix_guardian.agents.base_agent import BaseAgent, AgentResult

try:
    from phoenix_guardian.agents.safety_agent import SafetyAgent
except BaseException:
    SafetyAgent = None

from phoenix_guardian.api.utils.orchestrator import EncounterOrchestrator


class DemoScribeAgent(BaseAgent):
    """A demo ScribeAgent that generates SOAP notes from transcript without an API key."""

    def __init__(self) -> None:
        super().__init__(name="Scribe")

    def _extract_from_transcript(self, transcript: str) -> dict:
        """Extract key clinical info from transcript using simple parsing."""
        lines = transcript.strip().split("\n")
        symptoms = []
        vitals = []
        history_items = []
        patient_statements = []
        doctor_findings = []

        for line in lines:
            lower = line.lower().strip()
            # Extract patient statements
            if lower.startswith("patient:"):
                stmt = line.split(":", 1)[1].strip()
                patient_statements.append(stmt)
                # Look for symptoms (skip negated ones like "no cough")
                for symptom in ["fever", "headache", "cough", "pain", "nausea",
                                "vomiting", "fatigue", "tired", "body ache", "sore throat",
                                "shortness of breath", "dizziness", "chills", "swelling",
                                "rash", "diarrhea", "congestion", "weakness"]:
                    if symptom in lower:
                        # Check for negation
                        idx = lower.index(symptom)
                        preceding = lower[max(0, idx - 15):idx]
                        if not any(neg in preceding for neg in ["no ", "not ", "denies ", "without ", "negative for "]):
                            symptoms.append(symptom)
            # Extract doctor statements
            if lower.startswith("doctor:") or lower.startswith("dr:"):
                stmt = line.split(":", 1)[1].strip()
                doctor_findings.append(stmt)

            # Look for vitals anywhere
            import re
            temp_match = re.search(r'(\d{2,3}\.?\d*)\s*(?:degrees?\s*)?(?:fahrenheit|F\b|°F)', line, re.IGNORECASE)
            if temp_match:
                vitals.append(f"Temperature: {temp_match.group(1)}°F")
            bp_match = re.search(r'(\d{2,3}/\d{2,3})\s*(?:mm\s*Hg)?', line)
            if bp_match:
                vitals.append(f"Blood pressure: {bp_match.group(1)}")
            hr_match = re.search(r'heart rate\s*(?:is\s*)?(\d{2,3})|pulse\s*(?:is\s*)?(\d{2,3})', line, re.IGNORECASE)
            if hr_match:
                rate = hr_match.group(1) or hr_match.group(2)
                vitals.append(f"Heart rate: {rate}")

        # Deduplicate
        symptoms = list(dict.fromkeys(symptoms))
        vitals = list(dict.fromkeys(vitals))

        return {
            "symptoms": symptoms,
            "vitals": vitals,
            "patient_statements": patient_statements,
            "doctor_findings": doctor_findings,
        }

    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        transcript = context.get("transcript", "")
        patient_history = context.get("patient_history", {})

        demographics = patient_history.get("demographics", {})
        patient_name = demographics.get("name", "the patient")
        conditions = patient_history.get("conditions", [])
        medications = patient_history.get("medications", [])

        condition_text = ", ".join(
            [c.get("name", c) if isinstance(c, dict) else str(c) for c in conditions]
        ) if conditions else "none reported"

        medication_text = ", ".join(
            [m.get("name", m) if isinstance(m, dict) else str(m) for m in medications]
        ) if medications else "none reported"

        # Extract details from transcript
        extracted = self._extract_from_transcript(transcript)
        symptoms = extracted["symptoms"]
        vitals = extracted["vitals"]
        patient_statements = extracted["patient_statements"]

        # Build SUBJECTIVE from patient statements and symptoms
        symptom_text = ", ".join(symptoms) if symptoms else "symptoms as described in transcript"
        subj_parts = [f"Patient {patient_name} presents today."]
        if symptoms:
            subj_parts.append(f"Chief complaint: {symptom_text}.")
        if patient_statements:
            # Use first 3 patient statements as HPI
            hpi = " ".join(patient_statements[:3])
            subj_parts.append(f"HPI: {hpi}")
        if conditions and conditions != []:
            subj_parts.append(f"Past medical history: {condition_text}.")
        if medications and medications != []:
            subj_parts.append(f"Current medications: {medication_text}.")

        # Build OBJECTIVE from vitals and doctor findings
        obj_parts = []
        if vitals:
            obj_parts.append("Vital signs: " + "; ".join(vitals) + ".")
        else:
            obj_parts.append("Vital signs within normal limits.")
        obj_parts.append("Physical examination performed.")
        obj_parts.append("General appearance: alert and oriented.")

        # Build ASSESSMENT
        assess_parts = []
        if symptoms:
            assess_parts.append(f"Patient presents with {symptom_text}.")
        else:
            assess_parts.append("Assessment based on clinical encounter.")
        if condition_text != "none reported":
            assess_parts.append(f"History of {condition_text} noted.")
        assess_parts.append("Clinical correlation recommended.")
        assess_parts.append("Further workup may be indicated based on clinical judgment.")

        # Build PLAN
        plan_items = []
        if symptoms:
            plan_items.append(f"1. Evaluate and manage {symptoms[0]} — consider appropriate diagnostics.")
        else:
            plan_items.append("1. Continue monitoring symptoms.")
        plan_items.append("2. Review and continue current medications as appropriate.")
        plan_items.append("3. Patient education provided regarding diagnosis and management.")
        plan_items.append("4. Follow-up in 1-2 weeks or sooner if symptoms worsen.")
        plan_items.append("5. Return precautions discussed with patient.")

        sections = {
            "subjective": " ".join(subj_parts),
            "objective": " ".join(obj_parts),
            "assessment": " ".join(assess_parts),
            "plan": "\n".join(plan_items),
        }

        soap_note = (
            f"SUBJECTIVE:\n{sections['subjective']}\n\n"
            f"OBJECTIVE:\n{sections['objective']}\n\n"
            f"ASSESSMENT:\n{sections['assessment']}\n\n"
            f"PLAN:\n{sections['plan']}"
        )

        return {
            "data": {
                "soap_note": soap_note,
                "sections": sections,
                "model_used": "demo-mode (no API key)",
                "token_count": 0,
            },
            "reasoning": "Generated demo SOAP note from transcript and patient history.",
        }


@lru_cache()
def get_navigator() -> NavigatorAgent:
    """Get Navigator Agent singleton.

    Returns:
        NavigatorAgent instance configured with default settings
    """
    return NavigatorAgent()


@lru_cache()
def get_safety():
    """Get Safety Agent singleton.

    Returns:
        SafetyAgent instance configured with default security settings,
        or None if SafetyAgent is unavailable due to import issues.
    """
    if SafetyAgent is None:
        return None
    try:
        return SafetyAgent()
    except Exception:
        return None


@lru_cache()
def get_scribe():
    """Get Scribe Agent singleton.

    Returns:
        ScribeAgent instance configured with API key from environment,
        or a DemoScribeAgent if API key is not available.

    Note:
        Requires ANTHROPIC_API_KEY environment variable to be set
        for real API calls. Returns demo agent for testing without API key.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key or api_key == "test-api-key-for-testing":
        # Return a demo agent that generates placeholder SOAP notes
        return DemoScribeAgent()

    # Import here to avoid issues when API key not available
    from phoenix_guardian.agents.scribe_agent import ScribeAgent

    return ScribeAgent(api_key=api_key)


@lru_cache()
def get_orchestrator() -> EncounterOrchestrator:
    """Get Encounter Orchestrator singleton.

    Returns:
        EncounterOrchestrator instance with configured agents
    """
    return EncounterOrchestrator(
        navigator_agent=get_navigator(),
        scribe_agent=get_scribe(),
        safety_agent=get_safety(),
    )


def clear_dependency_cache() -> None:
    """Clear cached dependencies.

    Useful for testing when you need fresh instances.
    """
    get_navigator.cache_clear()
    get_safety.cache_clear()
    get_scribe.cache_clear()
    get_orchestrator.cache_clear()
