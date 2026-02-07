"""PharmacyAgent - Pharmacy Integration and e-Prescribing.

Handles pharmacy integrations including:
- Formulary checking (insurance tier and copay lookup)
- Prior authorization requirement detection
- Electronic prescribing (NCPDP SCRIPT standard)
- Medication synchronization
- Generic/therapeutic alternative suggestions
- Drug utilization review (DUR)

Standards compliance:
- NCPDP SCRIPT 2017071 for e-prescribing
- Surescripts network integration (simulated for demo)
- EPCS (Electronic Prescribing for Controlled Substances)
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from phoenix_guardian.agents.base import BaseAgent

logger = logging.getLogger(__name__)


# ── Formulary Tier Definitions ──
FORMULARY_TIERS = {
    1: {"name": "Preferred Generic", "typical_copay": 10.00},
    2: {"name": "Non-Preferred Generic", "typical_copay": 25.00},
    3: {"name": "Preferred Brand", "typical_copay": 50.00},
    4: {"name": "Non-Preferred Brand", "typical_copay": 75.00},
    5: {"name": "Specialty", "typical_copay": 150.00},
    6: {"name": "Not Covered", "typical_copay": None},
}

# ── Common Formulary Data (demo) ──
MEDICATION_FORMULARY = {
    # Generic medications — Tier 1
    "lisinopril": {"tier": 1, "copay": 10.00, "pa_required": False, "generic_available": True},
    "metformin": {"tier": 1, "copay": 10.00, "pa_required": False, "generic_available": True},
    "atorvastatin": {"tier": 1, "copay": 10.00, "pa_required": False, "generic_available": True},
    "amlodipine": {"tier": 1, "copay": 10.00, "pa_required": False, "generic_available": True},
    "omeprazole": {"tier": 1, "copay": 10.00, "pa_required": False, "generic_available": True},
    "levothyroxine": {"tier": 1, "copay": 10.00, "pa_required": False, "generic_available": True},
    "metoprolol": {"tier": 1, "copay": 10.00, "pa_required": False, "generic_available": True},
    "losartan": {"tier": 1, "copay": 10.00, "pa_required": False, "generic_available": True},
    "gabapentin": {"tier": 1, "copay": 10.00, "pa_required": False, "generic_available": True},
    "sertraline": {"tier": 1, "copay": 10.00, "pa_required": False, "generic_available": True},
    # Brand preferred — Tier 3
    "eliquis": {"tier": 3, "copay": 50.00, "pa_required": False, "generic_available": False},
    "jardiance": {"tier": 3, "copay": 50.00, "pa_required": True, "generic_available": False},
    "ozempic": {"tier": 3, "copay": 75.00, "pa_required": True, "generic_available": False},
    "xarelto": {"tier": 3, "copay": 50.00, "pa_required": False, "generic_available": False},
    "entresto": {"tier": 3, "copay": 60.00, "pa_required": True, "generic_available": False},
    # Specialty — Tier 5
    "humira": {"tier": 5, "copay": 150.00, "pa_required": True, "generic_available": False},
    "keytruda": {"tier": 5, "copay": 200.00, "pa_required": True, "generic_available": False},
}

# ── Therapeutic Alternatives ──
THERAPEUTIC_ALTERNATIVES = {
    "eliquis": [
        {"name": "warfarin", "tier": 1, "copay": 10.00, "note": "Requires INR monitoring"},
        {"name": "xarelto", "tier": 3, "copay": 50.00, "note": "Once daily dosing"},
    ],
    "jardiance": [
        {"name": "metformin", "tier": 1, "copay": 10.00, "note": "First-line per ADA guidelines"},
        {"name": "glipizide", "tier": 1, "copay": 10.00, "note": "Sulfonylurea alternative"},
    ],
    "ozempic": [
        {"name": "trulicity", "tier": 3, "copay": 50.00, "note": "GLP-1 RA alternative"},
        {"name": "metformin", "tier": 1, "copay": 10.00, "note": "First-line per ADA guidelines"},
    ],
    "entresto": [
        {"name": "lisinopril", "tier": 1, "copay": 10.00, "note": "ACE inhibitor (less effective for HFrEF)"},
        {"name": "losartan", "tier": 1, "copay": 10.00, "note": "ARB alternative"},
    ],
    "humira": [
        {"name": "hadlima", "tier": 4, "copay": 100.00, "note": "Adalimumab biosimilar"},
        {"name": "hyrimoz", "tier": 4, "copay": 100.00, "note": "Adalimumab biosimilar"},
    ],
}

# ── Prior Auth Requirements ──
PA_CRITERIA = {
    "jardiance": {
        "required": True,
        "criteria": [
            "Must have tried metformin first (step therapy)",
            "HbA1c ≥7.0% on current therapy",
            "Diagnosis of Type 2 Diabetes (ICD-10: E11.x)",
        ],
        "approval_turnaround": "24-48 hours",
    },
    "ozempic": {
        "required": True,
        "criteria": [
            "Must have tried metformin first (step therapy)",
            "BMI ≥30 or ≥27 with comorbidity",
            "HbA1c ≥7.0% on current therapy",
        ],
        "approval_turnaround": "24-72 hours",
    },
    "entresto": {
        "required": True,
        "criteria": [
            "Diagnosis of HFrEF (LVEF ≤40%)",
            "Must have tried ACE inhibitor or ARB",
            "NYHA Class II–IV",
        ],
        "approval_turnaround": "24-48 hours",
    },
    "humira": {
        "required": True,
        "criteria": [
            "Diagnosis of RA, Crohn's, UC, or psoriasis",
            "Failed conventional therapy",
            "Prescribed by specialist",
        ],
        "approval_turnaround": "3-5 business days",
    },
}


class PharmacyAgent(BaseAgent):
    """Handle pharmacy integrations and e-prescribing.

    Provides formulary checking, prior authorization detection,
    electronic prescribing, and drug utilization review.
    """

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process pharmacy request.

        Args:
            input_data: Dict with keys:
                - action: str — "check_formulary", "check_prior_auth",
                                "send_prescription", "drug_utilization_review"
                - medication: str
                - insurance_plan: str
                - patient_id: str
                - prescription: Dict (for send_prescription)
                - pharmacy_ncpdp: str
                - patient: Dict

        Returns:
            Dict with pharmacy results
        """
        action = input_data.get("action", "check_formulary")

        if action == "check_formulary":
            return self.check_formulary(
                medication=input_data.get("medication", ""),
                insurance_plan=input_data.get("insurance_plan", ""),
                patient_id=input_data.get("patient_id", ""),
            )
        elif action == "check_prior_auth":
            return self.check_prior_auth_required(
                medication=input_data.get("medication", ""),
                diagnosis=input_data.get("diagnosis", ""),
                insurance=input_data.get("insurance_plan", ""),
            )
        elif action == "send_prescription":
            return await self.send_erx(
                prescription=input_data.get("prescription", {}),
                pharmacy_ncpdp=input_data.get("pharmacy_ncpdp", ""),
                patient=input_data.get("patient", {}),
            )
        elif action == "drug_utilization_review":
            return await self.drug_utilization_review(
                prescription=input_data.get("prescription", {}),
                current_medications=input_data.get("current_medications", []),
                allergies=input_data.get("allergies", []),
                patient_factors=input_data.get("patient_factors", {}),
            )
        else:
            return {"error": f"Unknown action: {action}"}

    def check_formulary(
        self,
        medication: str,
        insurance_plan: str,
        patient_id: str,
    ) -> Dict[str, Any]:
        """Check if medication is on formulary for patient's insurance.

        Args:
            medication: Medication name
            insurance_plan: Insurance plan identifier
            patient_id: Patient identifier

        Returns:
            Dict with formulary status, tier, copay, and alternatives
        """
        med_lower = medication.lower().strip()
        formulary_info = MEDICATION_FORMULARY.get(med_lower)

        if formulary_info:
            tier = formulary_info["tier"]
            tier_info = FORMULARY_TIERS.get(tier, {})
            alternatives = THERAPEUTIC_ALTERNATIVES.get(med_lower, [])

            result = {
                "medication": medication,
                "on_formulary": tier <= 5,
                "tier": tier,
                "tier_name": tier_info.get("name", "Unknown"),
                "copay": formulary_info["copay"],
                "prior_auth_required": formulary_info["pa_required"],
                "generic_available": formulary_info["generic_available"],
                "alternatives": alternatives,
                "insurance_plan": insurance_plan,
            }

            # Cost-saving suggestion
            if tier >= 3 and alternatives:
                cheapest = min(alternatives, key=lambda x: x["copay"])
                result["cost_saving_suggestion"] = {
                    "alternative": cheapest["name"],
                    "savings": formulary_info["copay"] - cheapest["copay"],
                    "note": cheapest["note"],
                }
        else:
            result = {
                "medication": medication,
                "on_formulary": False,
                "tier": 6,
                "tier_name": "Not Found in Formulary",
                "copay": None,
                "prior_auth_required": True,
                "generic_available": False,
                "alternatives": [],
                "insurance_plan": insurance_plan,
                "note": "Medication not found in formulary database. Contact pharmacy.",
            }

        result["agent"] = "pharmacy"
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        return result

    def check_prior_auth_required(
        self,
        medication: str,
        diagnosis: str,
        insurance: str,
    ) -> Dict[str, Any]:
        """Determine if prior authorization is required.

        Args:
            medication: Medication name
            diagnosis: Primary diagnosis
            insurance: Insurance plan

        Returns:
            Dict with PA requirement details and criteria
        """
        med_lower = medication.lower().strip()
        pa_info = PA_CRITERIA.get(med_lower)

        if pa_info:
            return {
                "medication": medication,
                "prior_auth_required": pa_info["required"],
                "criteria": pa_info["criteria"],
                "approval_turnaround": pa_info["approval_turnaround"],
                "diagnosis": diagnosis,
                "insurance": insurance,
                "recommendation": (
                    "Submit prior authorization with documentation meeting "
                    "all listed criteria for fastest approval."
                ),
                "agent": "pharmacy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Check formulary for PA requirement
        formulary_info = MEDICATION_FORMULARY.get(med_lower, {})
        return {
            "medication": medication,
            "prior_auth_required": formulary_info.get("pa_required", False),
            "criteria": [],
            "approval_turnaround": "N/A",
            "diagnosis": diagnosis,
            "insurance": insurance,
            "agent": "pharmacy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def send_erx(
        self,
        prescription: Dict[str, Any],
        pharmacy_ncpdp: str,
        patient: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send electronic prescription (NCPDP SCRIPT standard).

        In production, integrates with Surescripts network.
        Demo mode generates valid NCPDP SCRIPT message structure.

        Args:
            prescription: Prescription details (medication, dosage, etc.)
            pharmacy_ncpdp: Pharmacy NCPDP identifier
            patient: Patient demographics

        Returns:
            Dict with prescription transmission result
        """
        # Validate prescription fields
        required_fields = ["medication", "dosage", "frequency", "quantity"]
        missing = [f for f in required_fields if f not in prescription]
        if missing:
            return {
                "status": "error",
                "message": f"Missing required prescription fields: {missing}",
                "agent": "pharmacy",
            }

        # Build NCPDP SCRIPT message (simplified structure)
        rx_id = f"RX-{uuid.uuid4().hex[:8].upper()}"
        script_message = {
            "header": {
                "message_id": rx_id,
                "sent_time": datetime.now(timezone.utc).isoformat(),
                "from": "Phoenix Guardian EHR",
                "to": pharmacy_ncpdp,
                "message_type": "NewRx",
                "version": "NCPDP SCRIPT 2017071",
            },
            "patient": {
                "name": patient.get("name", ""),
                "dob": patient.get("dob", ""),
                "gender": patient.get("gender", ""),
                "address": patient.get("address", {}),
            },
            "medication": {
                "drug_description": prescription["medication"],
                "quantity": prescription["quantity"],
                "days_supply": prescription.get("days_supply", 30),
                "refills": prescription.get("refills", 0),
                "directions": f"{prescription['dosage']} {prescription['frequency']}",
                "ndc": prescription.get("ndc", ""),
                "dea_schedule": prescription.get("dea_schedule", ""),
            },
            "prescriber": {
                "name": prescription.get("prescriber_name", ""),
                "npi": prescription.get("prescriber_npi", ""),
                "dea": prescription.get("prescriber_dea", ""),
            },
        }

        # In production: send via Surescripts
        # response = await self._send_to_surescripts(script_message)

        return {
            "status": "sent",
            "confirmation_number": rx_id,
            "pharmacy_ncpdp": pharmacy_ncpdp,
            "medication": prescription["medication"],
            "script_message": script_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "pharmacy",
            "note": "Demo mode — not transmitted to live pharmacy network",
        }

    async def drug_utilization_review(
        self,
        prescription: Dict[str, Any],
        current_medications: List[str],
        allergies: List[str],
        patient_factors: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Perform Drug Utilization Review (DUR).

        Checks for:
        - Drug-drug interactions
        - Drug-allergy contraindications
        - Duplicate therapy
        - Age/weight appropriateness
        - Dose range validation

        Args:
            prescription: New prescription details
            current_medications: Current medication list
            allergies: Known drug allergies
            patient_factors: Age, weight, renal function, etc.

        Returns:
            Dict with DUR findings
        """
        medication = prescription.get("medication", "")

        prompt = f"""Perform a Drug Utilization Review (DUR) for this new prescription:

New Medication: {medication}
Dosage: {prescription.get('dosage', 'N/A')}
Frequency: {prescription.get('frequency', 'N/A')}

Current Medications: {', '.join(current_medications) if current_medications else 'None'}
Allergies: {', '.join(allergies) if allergies else 'NKDA'}
Patient Age: {patient_factors.get('age', 'unknown')}
Patient Weight: {patient_factors.get('weight', 'unknown')} kg
Renal Function (GFR): {patient_factors.get('gfr', 'unknown')} mL/min

Check for:
1. Drug-drug interactions with current medications
2. Drug-allergy cross-reactivity
3. Duplicate therapy
4. Dose appropriateness for age/weight/renal function
5. Contraindications

Respond ONLY with valid JSON:
{{
  "interactions": [
    {{"drugs": ["drug1", "drug2"], "severity": "high/moderate/low", "description": "string"}}
  ],
  "allergy_alerts": ["string"],
  "duplicate_therapy": ["string"],
  "dose_check": {{
    "appropriate": true,
    "concerns": ["string"]
  }},
  "overall_risk": "high/moderate/low",
  "recommendation": "string"
}}"""

        try:
            response = await self._call_claude(prompt)
            dur_result = json.loads(response)
        except Exception as e:
            logger.warning(f"DUR analysis failed: {e}")
            dur_result = {
                "interactions": [],
                "allergy_alerts": [],
                "duplicate_therapy": [],
                "dose_check": {"appropriate": True, "concerns": []},
                "overall_risk": "unknown",
                "recommendation": "AI analysis unavailable — manual DUR recommended",
            }

        return {
            "medication": medication,
            "dur_result": dur_result,
            "agent": "pharmacy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
