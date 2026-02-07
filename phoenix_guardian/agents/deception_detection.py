"""DeceptionDetectionAgent - Clinical Consistency & Deception Analysis.

Detects inconsistencies in patient reporting for clinical safety:
- Contradiction detection between current and historical statements
- Drug-seeking behavior pattern recognition
- Symptom exaggeration indicators
- Timeline discrepancy analysis
- Malingering risk assessment

IMPORTANT: This agent is a clinical TOOL, not a lie detector.
All findings must be interpreted by a licensed physician in clinical context.
False positives are expected — the goal is to flag for physician review,
not to deny care.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from phoenix_guardian.agents.base import BaseAgent

logger = logging.getLogger(__name__)


# ── Drug-Seeking Red Flag Indicators ──
DRUG_SEEKING_RED_FLAGS = [
    "requests specific controlled substance by name",
    "reports allergy to all non-narcotic alternatives",
    "claims prescription was lost or stolen",
    "multiple providers for similar complaints",
    "presenting to ED for chronic pain",
    "insists only specific narcotic works",
    "refuses diagnostic workup",
    "aggressive when alternative offered",
    "reports pain out of proportion to exam",
    "frequent early refill requests",
]

# Controlled substances that trigger enhanced screening
CONTROLLED_SUBSTANCES = {
    "schedule_ii": [
        "oxycodone", "hydromorphone", "fentanyl", "morphine",
        "methadone", "amphetamine", "methylphenidate",
    ],
    "schedule_iii": [
        "codeine", "buprenorphine", "ketamine", "testosterone",
    ],
    "schedule_iv": [
        "alprazolam", "diazepam", "lorazepam", "clonazepam",
        "zolpidem", "tramadol",
    ],
}


class DeceptionDetectionAgent(BaseAgent):
    """Detect inconsistencies and potential deception in clinical encounters.

    This agent analyzes patient statements for consistency, identifies
    potential drug-seeking behavior, and flags concerning patterns.
    All findings are for physician review — NOT for automated decision-making.
    """

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process deception detection request.

        Args:
            input_data: Dict with keys:
                - action: str — "analyze_consistency", "detect_drug_seeking",
                                "assess_malingering"
                - patient_history: List[str] — previous statements
                - current_statement: str — current patient statement
                - patient_request: str — medication/treatment request
                - medical_history: str — documented medical history
                - current_medications: List[str]

        Returns:
            Dict with consistency analysis results
        """
        action = input_data.get("action", "analyze_consistency")

        if action == "detect_drug_seeking":
            return await self.detect_drug_seeking(
                patient_request=input_data.get("patient_request", ""),
                medical_history=input_data.get("medical_history", ""),
                current_medications=input_data.get("current_medications", []),
            )
        elif action == "assess_malingering":
            return await self.assess_malingering(
                symptoms=input_data.get("symptoms", []),
                exam_findings=input_data.get("exam_findings", ""),
                patient_history=input_data.get("patient_history", []),
            )
        else:
            return await self.analyze_consistency(
                patient_history=input_data.get("patient_history", []),
                current_statement=input_data.get("current_statement", ""),
            )

    async def analyze_consistency(
        self,
        patient_history: List[str],
        current_statement: str,
    ) -> Dict[str, Any]:
        """Analyze consistency between current and past statements.

        Identifies contradictions, timeline discrepancies, and
        concerning patterns in patient statements.

        Args:
            patient_history: List of previous patient statements
            current_statement: Current statement to analyze

        Returns:
            Dict with consistency score and flagged concerns
        """
        if not current_statement:
            return {
                "agent": "deception_detection",
                "error": "No current statement provided",
            }

        # Rule-based quick checks
        rule_flags = self._rule_based_consistency_check(
            patient_history, current_statement
        )

        # AI-powered deep analysis
        history_text = "\n".join(f"- {h}" for h in patient_history) if patient_history else "No prior statements on record"

        prompt = f"""Analyze consistency in patient statements. This is for clinical documentation
quality, NOT a lie detector. Flag genuine concerns for physician review only.

Previous Statements:
{history_text}

Current Statement:
"{current_statement}"

Evaluate:
1. Factual contradictions (e.g., different onset dates, conflicting symptoms)
2. Timeline discrepancies (events in illogical order)
3. Symptom escalation patterns (unusual rapid progression)
4. Missing context (important details omitted vs. prior visits)

IMPORTANT: Do NOT flag normal symptom progression or expected clinical variation.
Only flag genuine inconsistencies that could affect clinical decision-making.

Respond ONLY with valid JSON:
{{
  "consistency_score": 0-100,
  "contradictions": [
    {{
      "previous": "what was said before",
      "current": "what is said now",
      "concern": "why this is inconsistent"
    }}
  ],
  "timeline_issues": ["string"],
  "clinical_impact": "none/low/moderate/high",
  "recommendation": "string"
}}"""

        try:
            response = await self._call_claude(prompt)
            ai_result = json.loads(response)
        except Exception as e:
            logger.warning(f"AI consistency analysis failed: {e}")
            ai_result = {
                "consistency_score": 100,
                "contradictions": [],
                "timeline_issues": [],
                "clinical_impact": "unknown",
                "recommendation": "AI analysis unavailable — review manually",
            }

        # Merge rule-based and AI results
        all_flags = rule_flags + ai_result.get("contradictions", [])

        return {
            "agent": "deception_detection",
            "action": "analyze_consistency",
            "consistency_score": ai_result.get("consistency_score", 100),
            "flags": all_flags,
            "timeline_issues": ai_result.get("timeline_issues", []),
            "clinical_impact": ai_result.get("clinical_impact", "none"),
            "recommendation": ai_result.get("recommendation", ""),
            "disclaimer": (
                "Consistency analysis is a clinical support tool. "
                "Findings must be interpreted by a physician in clinical context. "
                "Inconsistencies may have benign explanations."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def detect_drug_seeking(
        self,
        patient_request: str,
        medical_history: str,
        current_medications: List[str],
    ) -> Dict[str, Any]:
        """Identify potential drug-seeking behavior patterns.

        Uses red flag criteria and AI analysis to identify concerning patterns.
        NOT a substitute for clinical judgment — findings are for physician
        review and should not be used to deny care.

        Args:
            patient_request: Patient's medication/treatment request
            medical_history: Documented medical history
            current_medications: Current medication list

        Returns:
            Dict with risk assessment and identified red flags
        """
        # Rule-based red flag check
        request_lower = patient_request.lower()
        identified_flags = []

        # Check for specific controlled substance requests
        for schedule, drugs in CONTROLLED_SUBSTANCES.items():
            for drug in drugs:
                if drug in request_lower:
                    identified_flags.append({
                        "flag": f"Requests specific {schedule} controlled substance: {drug}",
                        "severity": "moderate",
                    })

        # Check for allergy claims to alternatives
        if "allerg" in request_lower and any(
            term in request_lower
            for term in ["nsaid", "tylenol", "ibuprofen", "acetaminophen", "naproxen"]
        ):
            identified_flags.append({
                "flag": "Reports allergy to non-narcotic alternatives",
                "severity": "moderate",
            })

        # AI-powered analysis
        prompt = f"""Evaluate for potential drug-seeking behavior patterns.
This is for physician awareness — NOT to deny care.

Patient Request: "{patient_request}"
Medical History: {medical_history[:500] if medical_history else 'Not available'}
Current Medications: {', '.join(current_medications) if current_medications else 'None listed'}

Accepted clinical red flags:
{chr(10).join(f'- {rf}' for rf in DRUG_SEEKING_RED_FLAGS)}

IMPORTANT: Many patients with legitimate pain conditions may trigger some flags.
Assess the overall pattern, not individual flags. Give benefit of doubt.

Respond ONLY with valid JSON:
{{
  "risk_level": "low/moderate/high",
  "identified_red_flags": ["string"],
  "mitigating_factors": ["string"],
  "recommendation": "string",
  "pdmp_check_recommended": true/false
}}"""

        try:
            response = await self._call_claude(prompt)
            ai_result = json.loads(response)
        except Exception as e:
            logger.warning(f"Drug seeking analysis failed: {e}")
            ai_result = {
                "risk_level": "unknown",
                "identified_red_flags": [],
                "mitigating_factors": [],
                "recommendation": "AI analysis unavailable — clinical judgment required",
                "pdmp_check_recommended": True,
            }

        return {
            "agent": "deception_detection",
            "action": "detect_drug_seeking",
            "risk_level": ai_result.get("risk_level", "unknown"),
            "rule_based_flags": identified_flags,
            "ai_flags": ai_result.get("identified_red_flags", []),
            "mitigating_factors": ai_result.get("mitigating_factors", []),
            "pdmp_check_recommended": ai_result.get("pdmp_check_recommended", True),
            "recommendation": ai_result.get("recommendation", ""),
            "disclaimer": (
                "Drug-seeking risk assessment is a clinical support tool. "
                "Many patients with legitimate conditions may trigger flags. "
                "Always confirm with PDMP check and clinical judgment."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def assess_malingering(
        self,
        symptoms: List[str],
        exam_findings: str,
        patient_history: List[str],
    ) -> Dict[str, Any]:
        """Assess for potential malingering or symptom exaggeration.

        Evaluates objective–subjective discrepancies and inconsistent
        presentation patterns.

        Args:
            symptoms: Reported symptoms
            exam_findings: Physical exam findings
            patient_history: Previous visit records

        Returns:
            Dict with malingering risk assessment
        """
        prompt = f"""Evaluate for potential malingering or symptom exaggeration.
This is a clinical support tool — NOT a diagnostic determination.

Reported Symptoms: {', '.join(symptoms)}
Physical Exam Findings: {exam_findings}
Previous Visits: {chr(10).join(f'- {h}' for h in patient_history[:5]) if patient_history else 'None'}

Evaluate:
1. Subjective–objective discrepancies (symptoms don't match exam)
2. Anatomically implausible symptom patterns
3. Inconsistency with known pathophysiology
4. Symptom magnification indicators

IMPORTANT: Many organic conditions present atypically. Do not over-interpret.

Respond ONLY with valid JSON:
{{
  "concern_level": "none/low/moderate/high",
  "discrepancies": ["string"],
  "consistent_findings": ["string"],
  "recommendation": "string"
}}"""

        try:
            response = await self._call_claude(prompt)
            result = json.loads(response)
        except Exception as e:
            logger.warning(f"Malingering assessment failed: {e}")
            result = {
                "concern_level": "unknown",
                "discrepancies": [],
                "consistent_findings": [],
                "recommendation": "AI analysis unavailable",
            }

        return {
            "agent": "deception_detection",
            "action": "assess_malingering",
            "concern_level": result.get("concern_level", "unknown"),
            "discrepancies": result.get("discrepancies", []),
            "consistent_findings": result.get("consistent_findings", []),
            "recommendation": result.get("recommendation", ""),
            "disclaimer": (
                "Malingering assessment is for physician awareness. "
                "Atypical presentations are common in organic disease. "
                "Never deny care based on algorithmic assessment alone."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _rule_based_consistency_check(
        self,
        history: List[str],
        current: str,
    ) -> List[Dict[str, str]]:
        """Quick rule-based consistency checks."""
        flags = []
        current_lower = current.lower()

        for past_statement in history:
            past_lower = past_statement.lower()

            # Check for contradictory onset times
            if "started" in current_lower and "started" in past_lower:
                # Different timeframes mentioned
                time_words = ["today", "yesterday", "last week", "last month", "years ago"]
                current_times = [w for w in time_words if w in current_lower]
                past_times = [w for w in time_words if w in past_lower]
                if current_times and past_times and current_times != past_times:
                    flags.append({
                        "type": "timeline_discrepancy",
                        "previous": past_statement[:100],
                        "current": current[:100],
                        "concern": "Different onset timeframes reported",
                    })

            # Check for contradictory denial/affirmation
            denial_pairs = [
                ("no pain", "severe pain"),
                ("denies", "reports"),
                ("never had", "history of"),
                ("no allergies", "allergic to"),
            ]
            for deny, affirm in denial_pairs:
                if (deny in past_lower and affirm in current_lower) or (
                    affirm in past_lower and deny in current_lower
                ):
                    flags.append({
                        "type": "contradiction",
                        "previous": past_statement[:100],
                        "current": current[:100],
                        "concern": f"Contradictory statements: '{deny}' vs '{affirm}'",
                    })

        return flags
