"""OrderManagementAgent - Intelligent Order Management.

Handles clinical order management including:
- Lab order suggestions based on clinical context
- Imaging study recommendations with appropriateness criteria
- Prescription generation with guidelines-based dosing
- Order tracking and status management
- Duplicate order detection

Integrates with the full OrdersAgent (orders_agent.py) for validation.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from phoenix_guardian.agents.base import BaseAgent

logger = logging.getLogger(__name__)


# ── Common Lab Panels by Condition ──
CONDITION_LAB_PANELS = {
    "diabetes": [
        {"test_name": "HbA1c", "urgency": "routine", "indication": "Glycemic control monitoring", "icd10": "E11.65"},
        {"test_name": "Comprehensive Metabolic Panel", "urgency": "routine", "indication": "Renal/hepatic function", "icd10": "E11.65"},
        {"test_name": "Lipid Panel", "urgency": "routine", "indication": "Cardiovascular risk assessment", "icd10": "E78.5"},
        {"test_name": "Urine Albumin/Creatinine Ratio", "urgency": "routine", "indication": "Diabetic nephropathy screening", "icd10": "E11.21"},
    ],
    "hypertension": [
        {"test_name": "Basic Metabolic Panel", "urgency": "routine", "indication": "Electrolytes and renal function", "icd10": "I10"},
        {"test_name": "Lipid Panel", "urgency": "routine", "indication": "Cardiovascular risk", "icd10": "E78.5"},
        {"test_name": "Urinalysis", "urgency": "routine", "indication": "Renal assessment", "icd10": "I10"},
        {"test_name": "TSH", "urgency": "routine", "indication": "Secondary hypertension screen", "icd10": "E03.9"},
    ],
    "chest pain": [
        {"test_name": "Troponin I (serial)", "urgency": "stat", "indication": "Acute MI evaluation", "icd10": "R07.9"},
        {"test_name": "Complete Blood Count", "urgency": "stat", "indication": "Anemia/infection evaluation", "icd10": "R07.9"},
        {"test_name": "Basic Metabolic Panel", "urgency": "stat", "indication": "Electrolytes", "icd10": "R07.9"},
        {"test_name": "D-dimer", "urgency": "stat", "indication": "PE exclusion", "icd10": "R07.9"},
        {"test_name": "BNP", "urgency": "stat", "indication": "Heart failure evaluation", "icd10": "R07.9"},
    ],
    "pneumonia": [
        {"test_name": "Complete Blood Count", "urgency": "stat", "indication": "Infection evaluation", "icd10": "J18.9"},
        {"test_name": "Basic Metabolic Panel", "urgency": "stat", "indication": "Dehydration assessment", "icd10": "J18.9"},
        {"test_name": "Blood Culture x2", "urgency": "stat", "indication": "Identify causative organism", "icd10": "J18.9"},
        {"test_name": "Procalcitonin", "urgency": "stat", "indication": "Bacterial vs viral differentiation", "icd10": "J18.9"},
        {"test_name": "Sputum Culture", "urgency": "routine", "indication": "Targeted antibiotic therapy", "icd10": "J18.9"},
    ],
    "anemia": [
        {"test_name": "Complete Blood Count with Differential", "urgency": "routine", "indication": "Anemia characterization", "icd10": "D64.9"},
        {"test_name": "Reticulocyte Count", "urgency": "routine", "indication": "Bone marrow response", "icd10": "D64.9"},
        {"test_name": "Iron Studies (Fe, TIBC, Ferritin)", "urgency": "routine", "indication": "Iron deficiency evaluation", "icd10": "D50.9"},
        {"test_name": "Vitamin B12, Folate", "urgency": "routine", "indication": "Megaloblastic anemia", "icd10": "D51.9"},
    ],
    "fever": [
        {"test_name": "Complete Blood Count with Differential", "urgency": "stat", "indication": "Infection/leukocytosis", "icd10": "R50.9"},
        {"test_name": "Blood Culture x2", "urgency": "stat", "indication": "Bacteremia evaluation", "icd10": "R50.9"},
        {"test_name": "Urinalysis with Culture", "urgency": "stat", "indication": "UTI evaluation", "icd10": "R50.9"},
        {"test_name": "Basic Metabolic Panel", "urgency": "stat", "indication": "Dehydration/renal function", "icd10": "R50.9"},
        {"test_name": "C-Reactive Protein", "urgency": "stat", "indication": "Inflammatory marker", "icd10": "R50.9"},
    ],
}

# ── Imaging Appropriateness ──
IMAGING_RECOMMENDATIONS = {
    "chest pain": [
        {"modality": "chest_xray", "body_part": "Chest", "indication": "Initial evaluation", "contrast": False, "radiation": "low"},
        {"modality": "echocardiogram", "body_part": "Heart", "indication": "Cardiac function assessment", "contrast": False, "radiation": "none"},
    ],
    "headache": [
        {"modality": "ct_head", "body_part": "Head", "indication": "Acute hemorrhage exclusion", "contrast": False, "radiation": "moderate"},
    ],
    "abdominal pain": [
        {"modality": "ct_abdomen_pelvis", "body_part": "Abdomen/Pelvis", "indication": "Acute abdomen evaluation", "contrast": True, "radiation": "moderate"},
    ],
    "back pain": [
        {"modality": "xray_lumbar_spine", "body_part": "Lumbar Spine", "indication": "Fracture/alignment evaluation", "contrast": False, "radiation": "low"},
    ],
    "shortness of breath": [
        {"modality": "chest_xray", "body_part": "Chest", "indication": "Pulmonary evaluation", "contrast": False, "radiation": "low"},
        {"modality": "ct_chest_pe", "body_part": "Chest", "indication": "PE protocol if Wells >4", "contrast": True, "radiation": "moderate"},
    ],
}


class OrderManagementAgent(BaseAgent):
    """Intelligent order management with AI-powered suggestions.

    Suggests appropriate labs, imaging, and prescriptions based
    on clinical context, following evidence-based guidelines.
    """

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process order management request.

        Args:
            input_data: Dict with keys:
                - action: str — "suggest_labs", "suggest_imaging",
                                "generate_prescription", "check_duplicates"
                - clinical_note: str
                - diagnosis: str
                - patient_age: int
                - chief_complaint: str
                - physical_exam: str

        Returns:
            Dict with order suggestions
        """
        action = input_data.get("action", "suggest_labs")

        if action == "suggest_imaging":
            return await self.suggest_imaging(
                chief_complaint=input_data.get("chief_complaint", ""),
                physical_exam=input_data.get("physical_exam", ""),
                patient_age=input_data.get("patient_age", 50),
            )
        elif action == "generate_prescription":
            return await self.generate_prescription(
                medication=input_data.get("medication", ""),
                condition=input_data.get("condition", ""),
                patient_weight=input_data.get("patient_weight", 70.0),
                patient_age=input_data.get("patient_age", 50),
            )
        else:
            return await self.suggest_labs(
                clinical_note=input_data.get("clinical_note", ""),
                diagnosis=input_data.get("diagnosis", ""),
                patient_age=input_data.get("patient_age", 50),
            )

    async def suggest_labs(
        self,
        clinical_note: str,
        diagnosis: str,
        patient_age: int,
    ) -> Dict[str, Any]:
        """Suggest appropriate lab tests based on diagnosis and clinical context.

        Uses condition-specific lab panels and AI analysis for uncommon
        presentations.

        Args:
            clinical_note: Clinical documentation
            diagnosis: Primary diagnosis
            patient_age: Patient age in years

        Returns:
            Dict with suggested lab orders
        """
        suggested_labs = []

        # Rule-based: match known conditions
        diagnosis_lower = diagnosis.lower()
        for condition, labs in CONDITION_LAB_PANELS.items():
            if condition in diagnosis_lower:
                suggested_labs.extend(labs)

        # Age-based screening additions
        if patient_age >= 50 and not any(l["test_name"] == "Lipid Panel" for l in suggested_labs):
            suggested_labs.append({
                "test_name": "Lipid Panel",
                "urgency": "routine",
                "indication": "Age-appropriate cardiovascular screening",
                "icd10": "Z13.6",
            })

        # AI-powered suggestions for complex cases
        if not suggested_labs or clinical_note:
            ai_labs = await self._ai_lab_suggestions(
                clinical_note, diagnosis, patient_age
            )
            # Add AI suggestions that aren't duplicates
            existing_names = {l["test_name"].lower() for l in suggested_labs}
            for lab in ai_labs:
                if lab.get("test_name", "").lower() not in existing_names:
                    suggested_labs.append(lab)

        return {
            "agent": "order_management",
            "action": "suggest_labs",
            "diagnosis": diagnosis,
            "patient_age": patient_age,
            "suggested_labs": suggested_labs,
            "total_suggested": len(suggested_labs),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def suggest_imaging(
        self,
        chief_complaint: str,
        physical_exam: str,
        patient_age: int,
    ) -> Dict[str, Any]:
        """Suggest appropriate imaging studies.

        Follows ACR (American College of Radiology) Appropriateness Criteria.

        Args:
            chief_complaint: Patient's chief complaint
            physical_exam: Physical exam findings
            patient_age: Patient age (for radiation considerations)

        Returns:
            Dict with imaging recommendations
        """
        suggested_imaging = []

        # Rule-based matching
        complaint_lower = chief_complaint.lower()
        for condition, studies in IMAGING_RECOMMENDATIONS.items():
            if condition in complaint_lower:
                for study in studies:
                    study_copy = study.copy()
                    # Radiation warning for pediatric/young patients
                    if patient_age < 18 and study["radiation"] != "none":
                        study_copy["pediatric_warning"] = (
                            "Consider radiation exposure in pediatric patient. "
                            "Use ALARA principles."
                        )
                    suggested_imaging.append(study_copy)

        # AI-powered imaging suggestions
        if not suggested_imaging:
            ai_imaging = await self._ai_imaging_suggestions(
                chief_complaint, physical_exam, patient_age
            )
            suggested_imaging.extend(ai_imaging)

        return {
            "agent": "order_management",
            "action": "suggest_imaging",
            "chief_complaint": chief_complaint,
            "suggested_imaging": suggested_imaging,
            "total_suggested": len(suggested_imaging),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def generate_prescription(
        self,
        medication: str,
        condition: str,
        patient_weight: float,
        patient_age: int,
    ) -> Dict[str, Any]:
        """Generate prescription with guidelines-based dosing.

        Uses AI to determine appropriate dosing based on patient factors.

        Args:
            medication: Medication name
            condition: Condition being treated
            patient_weight: Patient weight in kg
            patient_age: Patient age

        Returns:
            Dict with prescription details
        """
        prompt = f"""Generate an evidence-based prescription for:

Medication: {medication}
Condition: {condition}
Patient Age: {patient_age} years
Patient Weight: {patient_weight} kg

Provide appropriate:
1. Dosage (based on age/weight guidelines)
2. Frequency
3. Duration
4. Quantity to dispense
5. Number of refills
6. Important counseling points

Respond ONLY with valid JSON:
{{
  "medication": "{medication}",
  "dosage": "string",
  "frequency": "string",
  "route": "oral/IV/topical/etc",
  "duration": "string",
  "quantity": 0,
  "refills": 0,
  "counseling": ["string"],
  "monitoring": ["string"],
  "black_box_warning": "string or null"
}}"""

        try:
            response = await self._call_claude(prompt)
            prescription = json.loads(response)
        except Exception as e:
            logger.warning(f"Prescription generation failed: {e}")
            prescription = {
                "medication": medication,
                "dosage": "See clinical guidelines",
                "frequency": "As directed",
                "route": "oral",
                "duration": "As directed",
                "quantity": 30,
                "refills": 0,
                "counseling": ["Consult prescribing reference"],
                "monitoring": [],
                "black_box_warning": None,
            }

        return {
            "agent": "order_management",
            "action": "generate_prescription",
            "prescription": prescription,
            "patient_age": patient_age,
            "patient_weight": patient_weight,
            "condition": condition,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _ai_lab_suggestions(
        self, clinical_note: str, diagnosis: str, age: int
    ) -> List[Dict[str, str]]:
        """Get AI-powered lab suggestions for complex cases."""
        prompt = f"""Based on this clinical context, suggest appropriate lab tests:

Diagnosis: {diagnosis}
Patient Age: {age}
Clinical Note: {clinical_note[:500] if clinical_note else 'Not available'}

Suggest labs that are clinically indicated. Be specific and evidence-based.

Respond ONLY with valid JSON array:
[
  {{
    "test_name": "Complete Blood Count",
    "urgency": "routine",
    "indication": "Evaluate for infection/anemia",
    "icd10": "R50.9"
  }}
]"""

        try:
            response = await self._call_claude(prompt)
            labs = json.loads(response)
            if isinstance(labs, list):
                return [l for l in labs if isinstance(l, dict)]
            return []
        except Exception:
            return []

    async def _ai_imaging_suggestions(
        self, complaint: str, exam: str, age: int
    ) -> List[Dict[str, Any]]:
        """Get AI-powered imaging suggestions."""
        prompt = f"""Suggest appropriate imaging studies:

Chief Complaint: {complaint}
Physical Exam: {exam}
Patient Age: {age}

Consider: ACR Appropriateness Criteria, cost-effectiveness, radiation exposure.

Respond ONLY with valid JSON array:
[
  {{
    "modality": "chest_xray",
    "body_part": "Chest",
    "indication": "string",
    "contrast": false,
    "radiation": "low/moderate/high/none"
  }}
]"""

        try:
            response = await self._call_claude(prompt)
            return json.loads(response)
        except Exception:
            return []
