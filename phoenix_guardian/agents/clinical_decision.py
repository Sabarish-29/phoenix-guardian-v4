"""ClinicalDecisionAgent - Evidence-Based Clinical Decision Support.

Provides AI-powered clinical decision support including:
- Evidence-based treatment recommendations
- Clinical risk score calculations (CHA₂DS₂-VASc, HEART, Wells, etc.)
- Diagnostic support and differential diagnosis
- Guideline adherence checking
- Drug–disease interaction warnings

Compliant with FDA CDS classification (non-device) under 21st Century Cures Act.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from phoenix_guardian.agents.base import BaseAgent

logger = logging.getLogger(__name__)


# ── Clinical Risk Score Definitions ──

HEART_CRITERIA = {
    "history": {
        "highly_suspicious": 2,
        "moderately_suspicious": 1,
        "slightly_suspicious": 0,
    },
    "ekg": {
        "significant_st_deviation": 2,
        "non_specific_repolarization": 1,
        "normal": 0,
    },
    "age": {
        ">=65": 2, "45-64": 1, "<45": 0,
    },
    "risk_factors": {
        ">=3": 2, "1-2": 1, "0": 0,
    },
    "troponin": {
        ">=3x_normal": 2, "1-3x_normal": 1, "normal": 0,
    },
}


class ClinicalDecisionAgent(BaseAgent):
    """Provide evidence-based clinical decision support.

    This agent does NOT make diagnoses — it provides clinical decision
    SUPPORT per FDA CDS classification criteria. All recommendations
    require physician review and approval.

    Capabilities:
    1. Treatment recommendations based on guidelines (ACC/AHA, IDSA, ADA)
    2. Validated clinical risk scores
    3. Differential diagnosis generation
    4. Drug–disease interaction checking
    """

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process clinical decision support request.

        Args:
            input_data: Dict with keys:
                - action: str — "recommend_treatment", "calculate_risk",
                                "differential_diagnosis"
                - diagnosis: str — primary diagnosis
                - patient_factors: Dict — age, comorbidities, allergies, sex
                - current_medications: List[str]
                - condition: str — for risk score calculation
                - clinical_data: Dict — for risk score parameters

        Returns:
            Dict with clinical decision support results
        """
        action = input_data.get("action", "recommend_treatment")

        if action == "calculate_risk":
            return self.calculate_risk_scores(
                condition=input_data.get("condition", ""),
                clinical_data=input_data.get("clinical_data", {}),
            )
        elif action == "differential_diagnosis":
            return await self.generate_differential(
                symptoms=input_data.get("symptoms", []),
                patient_factors=input_data.get("patient_factors", {}),
            )
        else:
            return await self.recommend_treatment(
                diagnosis=input_data.get("diagnosis", ""),
                patient_factors=input_data.get("patient_factors", {}),
                current_medications=input_data.get("current_medications", []),
            )

    async def recommend_treatment(
        self,
        diagnosis: str,
        patient_factors: Dict[str, Any],
        current_medications: List[str],
    ) -> Dict[str, Any]:
        """Recommend evidence-based treatment options.

        Args:
            diagnosis: Primary diagnosis
            patient_factors: Patient demographics and history
            current_medications: Current medication list

        Returns:
            Dict with treatment recommendations, alternatives, and monitoring
        """
        age = patient_factors.get("age", "unknown")
        comorbidities = patient_factors.get("comorbidities", [])
        allergies = patient_factors.get("allergies", [])
        sex = patient_factors.get("sex", "unknown")

        prompt = f"""As a clinical decision support system, provide evidence-based
treatment recommendations for the following case:

Diagnosis: {diagnosis}
Patient: {age} years old, {sex}
Comorbidities: {', '.join(comorbidities) if comorbidities else 'None reported'}
Allergies: {', '.join(allergies) if allergies else 'NKDA'}
Current Medications: {', '.join(current_medications) if current_medications else 'None'}

Provide recommendations based on current clinical guidelines (ACC/AHA, IDSA, ADA, etc.).

Respond ONLY with valid JSON:
{{
  "first_line": {{
    "treatment": "string",
    "guideline": "string",
    "evidence_level": "A/B/C",
    "dosing": "string"
  }},
  "alternatives": [
    {{
      "treatment": "string",
      "reason": "string",
      "guideline": "string"
    }}
  ],
  "contraindications": ["string"],
  "monitoring": ["string"],
  "drug_interactions": ["string"],
  "disclaimer": "Clinical decision support — physician review required"
}}"""

        try:
            response = await self._call_claude(prompt)
            result = json.loads(response)
        except Exception as e:
            logger.warning(f"AI treatment recommendation failed: {e}")
            result = {
                "first_line": {
                    "treatment": "Consult clinical guidelines",
                    "guideline": "N/A",
                    "evidence_level": "N/A",
                    "dosing": "N/A",
                },
                "alternatives": [],
                "contraindications": [],
                "monitoring": [],
                "drug_interactions": [],
                "disclaimer": "AI analysis unavailable — consult guidelines directly",
            }

        return {
            "agent": "clinical_decision_support",
            "action": "recommend_treatment",
            "diagnosis": diagnosis,
            "recommendations": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def calculate_risk_scores(
        self,
        condition: str,
        clinical_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate validated clinical risk scores.

        Supported scores:
        - CHA₂DS₂-VASc (atrial fibrillation stroke risk)
        - HEART Score (chest pain risk stratification)
        - Wells Score (PE probability)
        - CURB-65 (pneumonia severity)

        Args:
            condition: Clinical condition for score selection
            clinical_data: Parameters for score calculation

        Returns:
            Dict with calculated score, interpretation, and recommendation
        """
        condition_lower = condition.lower()
        result = {"agent": "clinical_decision_support", "action": "calculate_risk"}

        if condition_lower in ("afib", "atrial fibrillation"):
            score_result = self._calculate_chads2_vasc(clinical_data)
        elif condition_lower in ("chest pain", "acs"):
            score_result = self._calculate_heart_score(clinical_data)
        elif condition_lower in ("pe", "pulmonary embolism"):
            score_result = self._calculate_wells_score(clinical_data)
        elif condition_lower == "pneumonia":
            score_result = self._calculate_curb65(clinical_data)
        else:
            score_result = {
                "error": f"No validated risk score for condition: {condition}",
                "supported": ["afib", "chest pain", "pe", "pneumonia"],
            }

        result.update(score_result)
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        return result

    def _calculate_chads2_vasc(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate CHA₂DS₂-VASc score for stroke risk in AFib.

        Components (max 9):
        C — CHF (1 point)
        H — Hypertension (1 point)
        A₂ — Age ≥75 (2 points)
        D — Diabetes (1 point)
        S₂ — Stroke/TIA/VTE history (2 points)
        V — Vascular disease (1 point)
        A — Age 65–74 (1 point)
        Sc — Sex category (female = 1 point)
        """
        score = 0
        components = []

        if data.get("chf"):
            score += 1
            components.append("CHF (+1)")
        if data.get("hypertension"):
            score += 1
            components.append("Hypertension (+1)")

        age = data.get("age", 0)
        if age >= 75:
            score += 2
            components.append("Age ≥75 (+2)")
        elif age >= 65:
            score += 1
            components.append("Age 65–74 (+1)")

        if data.get("diabetes"):
            score += 1
            components.append("Diabetes (+1)")
        if data.get("stroke_history"):
            score += 2
            components.append("Stroke/TIA history (+2)")
        if data.get("vascular_disease"):
            score += 1
            components.append("Vascular disease (+1)")
        if data.get("sex") == "female":
            score += 1
            components.append("Female sex (+1)")

        # Interpretation
        if score == 0:
            risk = "Low"
            annual_stroke_rate = "0.2%"
            recommendation = "No anticoagulation needed (may consider aspirin)"
        elif score == 1:
            risk = "Low-Moderate"
            annual_stroke_rate = "0.6%"
            recommendation = "Consider oral anticoagulation (OAC) or aspirin"
        elif score == 2:
            risk = "Moderate"
            annual_stroke_rate = "2.2%"
            recommendation = "Oral anticoagulation recommended (DOAC preferred)"
        else:
            risk = "High"
            rates = {3: "3.2%", 4: "4.8%", 5: "7.2%", 6: "9.7%", 7: "11.2%", 8: "10.8%", 9: "12.2%"}
            annual_stroke_rate = rates.get(score, ">10%")
            recommendation = "Oral anticoagulation strongly recommended (DOAC preferred)"

        return {
            "score_name": "CHA₂DS₂-VASc",
            "score": score,
            "max_score": 9,
            "components": components,
            "risk_level": risk,
            "annual_stroke_rate": annual_stroke_rate,
            "recommendation": recommendation,
            "reference": "2023 ACC/AHA/ACCP/HRS AFib Guideline",
        }

    def _calculate_heart_score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate HEART Score for chest pain risk stratification.

        Components (0–10):
        H — History (0–2)
        E — ECG (0–2)
        A — Age (0–2)
        R — Risk factors (0–2)
        T — Troponin (0–2)
        """
        score = 0
        components = []

        # History
        history = data.get("history", "slightly_suspicious")
        h_score = HEART_CRITERIA["history"].get(history, 0)
        score += h_score
        components.append(f"History: {history} (+{h_score})")

        # ECG
        ekg = data.get("ekg", "normal")
        e_score = HEART_CRITERIA["ekg"].get(ekg, 0)
        score += e_score
        components.append(f"ECG: {ekg} (+{e_score})")

        # Age
        age = data.get("age", 0)
        if age >= 65:
            a_score = 2
        elif age >= 45:
            a_score = 1
        else:
            a_score = 0
        score += a_score
        components.append(f"Age {age}: (+{a_score})")

        # Risk factors
        rf_count = data.get("risk_factor_count", 0)
        if rf_count >= 3:
            r_score = 2
        elif rf_count >= 1:
            r_score = 1
        else:
            r_score = 0
        score += r_score
        components.append(f"Risk factors ({rf_count}): (+{r_score})")

        # Troponin
        troponin = data.get("troponin", "normal")
        t_score = HEART_CRITERIA["troponin"].get(troponin, 0)
        score += t_score
        components.append(f"Troponin: {troponin} (+{t_score})")

        # Interpretation
        if score <= 3:
            risk = "Low"
            mace_risk = "0.9–1.7%"
            recommendation = "Consider early discharge with outpatient follow-up"
        elif score <= 6:
            risk = "Moderate"
            mace_risk = "12–16.6%"
            recommendation = "Admit for observation, serial troponins, cardiology consult"
        else:
            risk = "High"
            mace_risk = "50–65%"
            recommendation = "Urgent intervention, cardiology consult, consider catheterization"

        return {
            "score_name": "HEART Score",
            "score": score,
            "max_score": 10,
            "components": components,
            "risk_level": risk,
            "mace_risk_6_weeks": mace_risk,
            "recommendation": recommendation,
            "reference": "Six et al. HEART Score validation studies",
        }

    def _calculate_wells_score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate Wells Score for PE probability.

        Components:
        - Clinical signs of DVT (3 points)
        - PE most likely diagnosis (3 points)
        - Heart rate >100 (1.5 points)
        - Immobilization/surgery in prior 4 weeks (1.5 points)
        - Previous DVT/PE (1.5 points)
        - Hemoptysis (1 point)
        - Active cancer (1 point)
        """
        score = 0.0
        components = []

        criteria = [
            ("dvt_signs", 3.0, "Clinical signs of DVT"),
            ("pe_most_likely", 3.0, "PE most likely or equally likely diagnosis"),
            ("heart_rate_over_100", 1.5, "Heart rate >100 bpm"),
            ("immobilization_surgery", 1.5, "Immobilization or surgery in prior 4 weeks"),
            ("previous_dvt_pe", 1.5, "Previous DVT/PE"),
            ("hemoptysis", 1.0, "Hemoptysis"),
            ("active_cancer", 1.0, "Active cancer (treatment within 6 months)"),
        ]

        for key, points, desc in criteria:
            if data.get(key):
                score += points
                components.append(f"{desc} (+{points})")

        # Interpretation (traditional two-tier)
        if score <= 4.0:
            risk = "PE Unlikely"
            probability = "<15%"
            recommendation = "D-dimer testing; if negative, PE excluded"
        else:
            risk = "PE Likely"
            probability = ">40%"
            recommendation = "CT pulmonary angiography recommended"

        return {
            "score_name": "Wells Score (PE)",
            "score": score,
            "max_score": 12.5,
            "components": components,
            "risk_level": risk,
            "pre_test_probability": probability,
            "recommendation": recommendation,
            "reference": "Wells et al. Thromb Haemost 2000",
        }

    def _calculate_curb65(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate CURB-65 score for pneumonia severity.

        C — Confusion (1 point)
        U — Urea >7 mmol/L (1 point)
        R — Respiratory rate ≥30 (1 point)
        B — Blood pressure (systolic <90 or diastolic ≤60) (1 point)
        65 — Age ≥65 (1 point)
        """
        score = 0
        components = []

        if data.get("confusion"):
            score += 1
            components.append("Confusion (+1)")
        if data.get("urea", 0) > 7:
            score += 1
            components.append(f"Urea {data['urea']} mmol/L (+1)")
        if data.get("respiratory_rate", 0) >= 30:
            score += 1
            components.append(f"RR {data['respiratory_rate']} (+1)")
        if data.get("systolic_bp", 120) < 90 or data.get("diastolic_bp", 80) <= 60:
            score += 1
            components.append("Low blood pressure (+1)")
        if data.get("age", 0) >= 65:
            score += 1
            components.append("Age ≥65 (+1)")

        if score <= 1:
            risk = "Low"
            mortality = "1.5%"
            recommendation = "Outpatient treatment appropriate"
        elif score == 2:
            risk = "Moderate"
            mortality = "9.2%"
            recommendation = "Consider short inpatient stay or closely supervised outpatient"
        else:
            risk = "High"
            mortality = "22%" if score == 3 else "33%"
            recommendation = "Hospitalize; consider ICU if score 4–5"

        return {
            "score_name": "CURB-65",
            "score": score,
            "max_score": 5,
            "components": components,
            "risk_level": risk,
            "30_day_mortality": mortality,
            "recommendation": recommendation,
            "reference": "Lim et al. Thorax 2003",
        }

    async def generate_differential(
        self,
        symptoms: List[str],
        patient_factors: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate differential diagnosis using AI.

        Args:
            symptoms: List of presenting symptoms
            patient_factors: Patient demographics and history

        Returns:
            Dict with ranked differential diagnoses
        """
        prompt = f"""Generate a ranked differential diagnosis for:

Symptoms: {', '.join(symptoms)}
Age: {patient_factors.get('age', 'unknown')}
Sex: {patient_factors.get('sex', 'unknown')}
Relevant History: {patient_factors.get('history', 'None')}

Provide top 5 differential diagnoses ranked by likelihood.

Respond ONLY with valid JSON:
{{
  "differentials": [
    {{
      "diagnosis": "string",
      "likelihood": "high/moderate/low",
      "key_features": ["string"],
      "workup": ["string"]
    }}
  ],
  "red_flags": ["string"],
  "disclaimer": "Differential diagnosis support — physician judgment required"
}}"""

        try:
            response = await self._call_claude(prompt)
            result = json.loads(response)
        except Exception as e:
            logger.warning(f"Differential diagnosis generation failed: {e}")
            result = {
                "differentials": [],
                "red_flags": [],
                "disclaimer": "AI analysis unavailable",
            }

        return {
            "agent": "clinical_decision_support",
            "action": "differential_diagnosis",
            "symptoms": symptoms,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
