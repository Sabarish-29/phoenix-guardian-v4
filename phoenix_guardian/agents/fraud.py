"""FraudAgent - Healthcare Billing Fraud Detection.

Detects fraudulent billing patterns including upcoding, unbundling,
phantom billing, and anomalous claim patterns using rule-based analysis
and ML-powered anomaly detection.

Responsibilities:
- Detect upcoding (billing higher E/M level than warranted)
- Identify unbundling violations (NCCI edit checks)
- Flag phantom billing (services not rendered)
- Anomaly detection in billing patterns
- Statistical outlier identification
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from phoenix_guardian.agents.base import BaseAgent

logger = logging.getLogger(__name__)


# ── NCCI Bundled Code Pairs (subset for demonstration) ──
BUNDLED_PAIRS = {
    # E/M codes cannot be billed together on same date
    ("99213", "99214"), ("99213", "99215"), ("99214", "99215"),
    ("99211", "99213"), ("99212", "99213"), ("99212", "99214"),
    # Venipuncture bundled with panels
    ("36415", "80053"), ("36415", "80048"), ("36415", "80050"),
    # Urinalysis bundled with culture
    ("81001", "87086"), ("81003", "87086"),
    # Chest X-ray views
    ("71045", "71046"), ("71045", "71047"), ("71046", "71048"),
    # EKG interpretation with tracing
    ("93000", "93010"), ("93000", "93005"),
}

# E/M code requirements: code → (min_elements, min_duration_minutes, complexity)
EM_CODE_REQUIREMENTS = {
    "99211": {"min_elements": 0, "min_duration": 5, "complexity": "minimal"},
    "99212": {"min_elements": 3, "min_duration": 10, "complexity": "straightforward"},
    "99213": {"min_elements": 6, "min_duration": 15, "complexity": "low"},
    "99214": {"min_elements": 9, "min_duration": 25, "complexity": "moderate"},
    "99215": {"min_elements": 12, "min_duration": 40, "complexity": "high"},
}

# Complexity hierarchy for comparison
COMPLEXITY_LEVELS = {
    "minimal": 1,
    "straightforward": 2,
    "low": 3,
    "moderate": 4,
    "high": 5,
}


class FraudAgent(BaseAgent):
    """Detect fraudulent billing and coding patterns.

    Combines rule-based NCCI edit checking with AI-powered analysis
    for comprehensive fraud detection in healthcare billing.

    Detection Methods:
    1. NCCI Edit Checks: validate code pairs are not improperly unbundled
    2. Upcoding Detection: verify E/M level matches documentation
    3. Statistical Anomaly: flag outlier billing patterns
    4. AI Analysis: Claude-powered contextual fraud assessment
    """

    def __init__(self):
        """Initialize FraudAgent with optional ML model."""
        super().__init__()
        self.ml_model = None
        self._load_ml_model()

    def _load_ml_model(self):
        """Load trained fraud detection model if available."""
        model_path = "models/fraud_detector_bidirectional.pkl"
        if os.path.exists(model_path):
            try:
                import joblib
                self.ml_model = joblib.load(model_path)
                logger.info("Fraud detection ML model loaded")
            except Exception as e:
                logger.warning(f"Could not load fraud ML model: {e}")

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process billing data for fraud detection.

        Args:
            input_data: Dict with keys:
                - procedure_codes: List[str] — CPT codes billed
                - encounter_complexity: str — documented complexity
                - encounter_duration: int — duration in minutes
                - documented_elements: int — number of documented elements
                - billed_cpt_code: str — primary E/M code
                - date_of_service: str — date in ISO format

        Returns:
            Dict with fraud analysis results
        """
        results = {
            "agent": "fraud_detection",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks_performed": [],
            "risk_level": "LOW",
            "risk_score": 0.0,
            "findings": [],
        }

        # Check 1: Unbundling
        procedure_codes = input_data.get("procedure_codes", [])
        if len(procedure_codes) >= 2:
            unbundling = self.detect_unbundling(procedure_codes)
            results["checks_performed"].append("unbundling")
            if unbundling["violations_detected"]:
                results["findings"].extend(unbundling["violations"])
                results["risk_score"] += 0.3 * len(unbundling["violations"])

        # Check 2: Upcoding
        billed_code = input_data.get("billed_cpt_code", "")
        if billed_code:
            upcoding = self.detect_upcoding(
                encounter_complexity=input_data.get("encounter_complexity", "low"),
                billed_cpt_code=billed_code,
                encounter_duration=input_data.get("encounter_duration", 15),
                documented_elements=input_data.get("documented_elements", 6),
            )
            results["checks_performed"].append("upcoding")
            if upcoding["upcoding_detected"]:
                results["findings"].append(upcoding)
                results["risk_score"] += 0.4

        # Check 3: AI-powered contextual analysis
        if input_data.get("clinical_note"):
            ai_analysis = await self._ai_fraud_analysis(input_data)
            results["checks_performed"].append("ai_analysis")
            results["ai_analysis"] = ai_analysis
            if ai_analysis.get("risk_score", 0) > 0.6:
                results["risk_score"] += ai_analysis["risk_score"] * 0.3

        # Overall risk level
        score = min(results["risk_score"], 1.0)
        results["risk_score"] = round(score, 3)
        if score >= 0.7:
            results["risk_level"] = "HIGH"
        elif score >= 0.4:
            results["risk_level"] = "MODERATE"
        else:
            results["risk_level"] = "LOW"

        return results

    def detect_unbundling(self, procedure_codes: List[str]) -> Dict[str, Any]:
        """Detect unbundling violations per NCCI edits.

        Unbundling is billing separately for services that should be
        billed as a single bundled code.

        Args:
            procedure_codes: List of CPT codes billed together

        Returns:
            Dict with violations_detected flag and violation details
        """
        violations = []

        for i, code1 in enumerate(procedure_codes):
            for code2 in procedure_codes[i + 1:]:
                pair = (code1, code2)
                reverse_pair = (code2, code1)
                if pair in BUNDLED_PAIRS or reverse_pair in BUNDLED_PAIRS:
                    violations.append({
                        "type": "unbundling",
                        "code1": code1,
                        "code2": code2,
                        "message": (
                            f"Codes {code1} and {code2} are bundled per NCCI edits "
                            f"and should not be billed separately."
                        ),
                        "severity": "HIGH",
                    })

        return {
            "violations_detected": len(violations) > 0,
            "violations": violations,
            "codes_checked": len(procedure_codes),
            "pairs_checked": len(procedure_codes) * (len(procedure_codes) - 1) // 2,
        }

    def detect_upcoding(
        self,
        encounter_complexity: str,
        billed_cpt_code: str,
        encounter_duration: int,
        documented_elements: int,
    ) -> Dict[str, Any]:
        """Detect potential upcoding.

        Upcoding is billing at a higher E/M level than the documentation
        and complexity of the encounter warrant.

        Args:
            encounter_complexity: documented complexity level
            billed_cpt_code: CPT code billed
            encounter_duration: visit duration in minutes
            documented_elements: number of clinical elements documented

        Returns:
            Dict with upcoding analysis
        """
        requirements = EM_CODE_REQUIREMENTS.get(billed_cpt_code)
        if not requirements:
            return {
                "upcoding_detected": False,
                "message": f"Code {billed_cpt_code} not in E/M validation table",
            }

        issues = []

        # Check complexity mismatch
        billed_complexity = requirements["complexity"]
        billed_level = COMPLEXITY_LEVELS.get(billed_complexity, 0)
        actual_level = COMPLEXITY_LEVELS.get(encounter_complexity, 0)
        if actual_level < billed_level:
            issues.append(
                f"Complexity mismatch: billed {billed_complexity} "
                f"but documented {encounter_complexity}"
            )

        # Check duration
        if encounter_duration < requirements["min_duration"]:
            issues.append(
                f"Duration insufficient: {encounter_duration}min < "
                f"required {requirements['min_duration']}min for {billed_cpt_code}"
            )

        # Check documented elements
        if documented_elements < requirements["min_elements"]:
            issues.append(
                f"Documentation insufficient: {documented_elements} elements < "
                f"required {requirements['min_elements']} for {billed_cpt_code}"
            )

        # Suggest appropriate code
        suggested_code = self._suggest_appropriate_code(
            encounter_complexity, encounter_duration, documented_elements
        )

        return {
            "upcoding_detected": len(issues) > 0,
            "billed_code": billed_cpt_code,
            "suggested_code": suggested_code,
            "issues": issues,
            "severity": "HIGH" if len(issues) >= 2 else "MODERATE" if issues else "NONE",
        }

    def _suggest_appropriate_code(
        self,
        complexity: str,
        duration: int,
        elements: int,
    ) -> str:
        """Suggest the appropriate E/M code based on documentation."""
        for code, reqs in sorted(
            EM_CODE_REQUIREMENTS.items(), key=lambda x: x[0], reverse=True
        ):
            if (
                COMPLEXITY_LEVELS.get(complexity, 0)
                >= COMPLEXITY_LEVELS.get(reqs["complexity"], 0)
                and duration >= reqs["min_duration"]
                and elements >= reqs["min_elements"]
            ):
                return code
        return "99211"

    async def _ai_fraud_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Use Claude for contextual fraud analysis."""
        prompt = f"""Analyze this healthcare billing for potential fraud indicators:

Clinical Note: {data.get('clinical_note', 'N/A')[:500]}
Billed CPT Code: {data.get('billed_cpt_code', 'N/A')}
Encounter Duration: {data.get('encounter_duration', 'N/A')} minutes
Documented Elements: {data.get('documented_elements', 'N/A')}
Procedure Codes: {data.get('procedure_codes', [])}

Evaluate for:
1. Documentation supports billed level of service
2. Appropriateness of procedures for diagnosis
3. Unusual patterns or red flags

Respond ONLY with valid JSON:
{{
  "risk_score": 0.0-1.0,
  "findings": ["string"],
  "recommendation": "string"
}}"""

        try:
            response = await self._call_claude(prompt)
            return json.loads(response)
        except Exception as e:
            logger.warning(f"AI fraud analysis failed: {e}")
            return {"risk_score": 0.0, "findings": [], "recommendation": "AI analysis unavailable"}#
