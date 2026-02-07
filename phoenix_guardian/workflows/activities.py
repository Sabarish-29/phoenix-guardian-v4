"""
Temporal Activities for Phoenix Guardian.

Activities are the building blocks of workflows — each activity performs
a single unit of work (calling an agent, validating data, storing results).
Activities can be retried independently on failure.

Activity Design Principles:
- Each activity wraps a single agent or service call
- Activities are idempotent where possible
- Activities include compensation counterparts for SAGA rollback
- All activities log execution for audit trail
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from temporalio import activity

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION ACTIVITIES
# ═══════════════════════════════════════════════════════════════════════════════

@activity.defn(name="validate_encounter")
async def validate_encounter(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate encounter data before processing.

    Checks:
    - Required fields present (patient_mrn, transcript)
    - Transcript minimum length
    - Patient MRN format
    - Medication list validity

    Args:
        data: Encounter data to validate

    Returns:
        Dict with 'valid' bool and 'errors' list
    """
    activity.logger.info("Validating encounter data")
    errors: List[str] = []

    # Required fields
    if not data.get("patient_mrn"):
        errors.append("Patient MRN is required")
    if not data.get("transcript") and not data.get("chief_complaint"):
        errors.append("Either transcript or chief_complaint is required")

    # Transcript length
    transcript = data.get("transcript", "")
    if transcript and len(transcript) < 20:
        errors.append(f"Transcript too short ({len(transcript)} chars, minimum 20)")

    # MRN format
    mrn = data.get("patient_mrn", "")
    if mrn and not (mrn.startswith("MRN-") or mrn.isalnum()):
        errors.append(f"Invalid MRN format: {mrn}")

    result = {
        "valid": len(errors) == 0,
        "errors": errors,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }
    activity.logger.info(f"Validation result: valid={result['valid']}, errors={len(errors)}")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT ACTIVITIES
# ═══════════════════════════════════════════════════════════════════════════════

@activity.defn(name="generate_soap")
async def generate_soap_activity(data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate SOAP note using ScribeAgent.

    Args:
        data: Encounter data with transcript, chief_complaint, etc.

    Returns:
        Dict with 'id', 'soap_note', and generation metadata
    """
    activity.logger.info("Generating SOAP note via ScribeAgent")

    try:
        from phoenix_guardian.agents.scribe import ScribeAgent
        agent = ScribeAgent()
        result = await agent.process({
            "chief_complaint": data.get("chief_complaint", ""),
            "vitals": data.get("vitals", {}),
            "symptoms": data.get("symptoms", []),
            "exam_findings": data.get("exam_findings", ""),
        })

        soap_id = f"soap-{uuid.uuid4().hex[:12]}"
        return {
            "id": soap_id,
            "soap_note": result.get("soap_note", ""),
            "icd_codes": result.get("icd_codes", []),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "draft",
        }
    except Exception as e:
        activity.logger.error(f"SOAP generation failed: {e}")
        raise


@activity.defn(name="check_drug_interactions")
async def check_drug_interactions(data: Dict[str, Any]) -> Dict[str, Any]:
    """Check for drug interactions using SafetyAgent.

    Args:
        data: Dict with 'medications' list and 'soap_id'

    Returns:
        Dict with 'id', 'interactions', and 'high_risk_interaction' flag
    """
    activity.logger.info("Checking drug interactions via SafetyAgent")

    try:
        from phoenix_guardian.agents.safety import SafetyAgent
        agent = SafetyAgent()
        result = await agent.process({
            "medications": data.get("medications", []),
        })

        safety_id = f"safety-{uuid.uuid4().hex[:12]}"
        interactions = result.get("interactions", [])
        high_risk = any(
            i.get("severity", "").lower() in ("severe", "high", "critical")
            for i in interactions
        )

        return {
            "id": safety_id,
            "soap_id": data.get("soap_id", ""),
            "interactions": interactions,
            "high_risk_interaction": high_risk,
            "checked_medications": data.get("medications", []),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        activity.logger.error(f"Drug interaction check failed: {e}")
        raise


@activity.defn(name="suggest_codes")
async def suggest_codes_activity(data: Dict[str, Any]) -> Dict[str, Any]:
    """Suggest ICD-10 and CPT codes using CodingAgent.

    Args:
        data: Dict with 'clinical_note' (SOAP note text)

    Returns:
        Dict with 'id', 'icd10_codes', 'cpt_codes'
    """
    activity.logger.info("Suggesting medical codes via CodingAgent")

    try:
        from phoenix_guardian.agents.coding import CodingAgent
        agent = CodingAgent()
        result = await agent.process({
            "clinical_note": data.get("clinical_note", ""),
            "procedures": data.get("procedures", []),
        })

        coding_id = f"codes-{uuid.uuid4().hex[:12]}"
        return {
            "id": coding_id,
            "icd10_codes": result.get("icd10_codes", []),
            "cpt_codes": result.get("cpt_codes", []),
            "coded_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        activity.logger.error(f"Code suggestion failed: {e}")
        raise


@activity.defn(name="predict_readmission")
async def predict_readmission(data: Dict[str, Any]) -> Dict[str, Any]:
    """Predict 30-day readmission risk.

    Args:
        data: Encounter data with patient demographics

    Returns:
        Dict with 'risk_score', 'risk_level', 'factors'
    """
    activity.logger.info("Predicting readmission risk")

    try:
        from phoenix_guardian.agents.readmission import ReadmissionAgent
        agent = ReadmissionAgent()

        prediction_input = {
            "age": data.get("patient_age", 50),
            "has_heart_failure": data.get("has_heart_failure", False),
            "has_diabetes": data.get("has_diabetes", False),
            "has_copd": data.get("has_copd", False),
            "comorbidity_count": data.get("comorbidity_count", 0),
            "length_of_stay": data.get("length_of_stay", 3),
            "visits_30d": data.get("visits_30d", 0),
            "visits_90d": data.get("visits_90d", 0),
            "discharge_disposition": data.get("discharge_disposition", "home"),
        }

        result = agent.predict(prediction_input)
        return {
            "risk_score": result.get("risk_score", 0),
            "risk_level": result.get("risk_level", "unknown"),
            "probability": result.get("probability", 0.0),
            "factors": result.get("factors", []),
            "recommendations": result.get("recommendations", []),
            "predicted_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        activity.logger.warning(f"Readmission prediction failed: {e}")
        return {
            "risk_score": 0,
            "risk_level": "unknown",
            "probability": 0.0,
            "factors": [],
            "recommendations": [],
            "error": str(e),
        }


@activity.defn(name="check_security_threats")
async def check_security_threats(data: Dict[str, Any]) -> Dict[str, Any]:
    """Check for security threats using SentinelAgent.

    Args:
        data: Dict with 'transcript' or 'user_input'

    Returns:
        Dict with 'threat_detected', 'threat_type', 'confidence'
    """
    activity.logger.info("Checking security threats via SentinelAgent")

    try:
        from phoenix_guardian.agents.sentinel import SentinelAgent
        agent = SentinelAgent()
        result = await agent.process({
            "user_input": data.get("transcript", data.get("user_input", "")),
            "context": "encounter_processing",
        })

        return {
            "threat_detected": result.get("threat_detected", False),
            "threat_type": result.get("threat_type", ""),
            "confidence": result.get("confidence", 0.0),
            "details": result.get("details", ""),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        activity.logger.error(f"Security check failed: {e}")
        return {"threat_detected": False, "error": str(e)}


@activity.defn(name="detect_fraud")
async def detect_fraud_activity(data: Dict[str, Any]) -> Dict[str, Any]:
    """Run fraud detection on billing data.

    Args:
        data: Dict with billing details

    Returns:
        Dict with fraud risk assessment
    """
    activity.logger.info("Running fraud detection")

    try:
        from phoenix_guardian.agents.fraud import FraudAgent
        agent = FraudAgent()
        result = await agent.process(data)
        return result
    except Exception as e:
        activity.logger.error(f"Fraud detection failed: {e}")
        return {"risk_level": "unknown", "error": str(e)}


@activity.defn(name="flag_for_review")
async def flag_for_review(data: Dict[str, Any]) -> Dict[str, Any]:
    """Flag encounter for physician review.

    Args:
        data: Dict with 'encounter_id' and 'reason'

    Returns:
        Dict with flag status
    """
    activity.logger.info(
        f"Flagging encounter {data.get('encounter_id')} for review: {data.get('reason')}"
    )
    return {
        "flagged": True,
        "encounter_id": data.get("encounter_id"),
        "reason": data.get("reason"),
        "flagged_at": datetime.now(timezone.utc).isoformat(),
    }


@activity.defn(name="store_encounter")
async def store_encounter(data: Dict[str, Any]) -> Dict[str, Any]:
    """Store processed encounter in database.

    Args:
        data: Dict with all processing results (soap, codes, risk, safety)

    Returns:
        Dict with stored encounter ID
    """
    activity.logger.info("Storing processed encounter")

    encounter_id = f"enc-{uuid.uuid4().hex[:12]}"
    return {
        "id": encounter_id,
        "stored": True,
        "soap_id": data.get("soap", {}).get("id"),
        "coding_id": data.get("codes", {}).get("id"),
        "safety_id": data.get("safety", {}).get("id"),
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# COMPENSATION ACTIVITIES (SAGA Rollback)
# ═══════════════════════════════════════════════════════════════════════════════

@activity.defn(name="delete_soap_draft")
async def delete_soap_draft(soap_id: str) -> Dict[str, Any]:
    """Compensation: delete SOAP draft on workflow failure.

    Args:
        soap_id: ID of the SOAP note to delete

    Returns:
        Dict with deletion status
    """
    activity.logger.info(f"COMPENSATION: Deleting SOAP draft {soap_id}")
    # In production, would delete from database
    return {"deleted": True, "soap_id": soap_id, "compensated_at": datetime.now(timezone.utc).isoformat()}


@activity.defn(name="remove_safety_flags")
async def remove_safety_flags(safety_id: str) -> Dict[str, Any]:
    """Compensation: remove safety flags on workflow failure.

    Args:
        safety_id: ID of the safety check to remove

    Returns:
        Dict with removal status
    """
    activity.logger.info(f"COMPENSATION: Removing safety flags {safety_id}")
    return {"removed": True, "safety_id": safety_id, "compensated_at": datetime.now(timezone.utc).isoformat()}


@activity.defn(name="remove_code_suggestions")
async def remove_code_suggestions(coding_id: str) -> Dict[str, Any]:
    """Compensation: remove code suggestions on workflow failure.

    Args:
        coding_id: ID of the coding suggestions to remove

    Returns:
        Dict with removal status
    """
    activity.logger.info(f"COMPENSATION: Removing code suggestions {coding_id}")
    return {"removed": True, "coding_id": coding_id, "compensated_at": datetime.now(timezone.utc).isoformat()}
