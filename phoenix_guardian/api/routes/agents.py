"""API Routes for AI Agents.

Provides REST endpoints for all Phoenix Guardian AI agents:
- ScribeAgent: SOAP note generation
- SafetyAgent: Drug interaction checking
- NavigatorAgent: Workflow suggestions
- CodingAgent: ICD-10/CPT code suggestions
- SentinelAgent: Security threat detection
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from phoenix_guardian.agents.scribe import ScribeAgent
from phoenix_guardian.agents.safety import SafetyAgent
from phoenix_guardian.agents.navigator import NavigatorAgent
from phoenix_guardian.agents.coding import CodingAgent
from phoenix_guardian.agents.sentinel import SentinelAgent
from phoenix_guardian.agents.fraud import FraudAgent
from phoenix_guardian.agents.clinical_decision import ClinicalDecisionAgent
from phoenix_guardian.agents.pharmacy import PharmacyAgent
from phoenix_guardian.agents.deception_detection import DeceptionDetectionAgent
from phoenix_guardian.agents.order_management import OrderManagementAgent
from phoenix_guardian.api.auth import get_current_user

router = APIRouter(prefix="/agents", tags=["agents"])


# ============================================================================
# ScribeAgent - SOAP Note Generation
# ============================================================================

class SOAPGenerationRequest(BaseModel):
    """Request model for SOAP note generation."""
    chief_complaint: str = Field(..., description="Patient's chief complaint")
    vitals: Dict[str, str] = Field(default_factory=dict, description="Vital signs")
    symptoms: List[str] = Field(default_factory=list, description="List of symptoms")
    exam_findings: str = Field(default="", description="Physical exam findings")


class SOAPGenerationResponse(BaseModel):
    """Response model for SOAP note generation."""
    soap_note: str
    icd_codes: List[str]
    agent: str
    model: str


@router.post("/scribe/generate-soap", response_model=SOAPGenerationResponse)
async def generate_soap_note(
    request: SOAPGenerationRequest,
    current_user = Depends(get_current_user)
):
    """Generate SOAP note from encounter data.
    
    Uses Claude Sonnet 4 to generate structured clinical documentation
    in SOAP format with automatic ICD-10 code extraction.
    """
    try:
        agent = ScribeAgent()
        result = await agent.process(request.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SOAP generation failed: {str(e)}")


# ============================================================================
# SafetyAgent - Drug Interaction Checking
# ============================================================================

class SafetyCheckRequest(BaseModel):
    """Request model for drug interaction check."""
    medications: List[str] = Field(..., description="List of medications to check")


class SafetyCheckResponse(BaseModel):
    """Response model for drug interaction check."""
    interactions: List[Dict[str, Any]]
    severity: str
    checked_medications: List[str]
    agent: str


@router.post("/safety/check-interactions", response_model=SafetyCheckResponse)
async def check_drug_interactions(
    request: SafetyCheckRequest,
    current_user = Depends(get_current_user)
):
    """Check medications for drug interactions.
    
    Combines known interaction database with AI-powered analysis
    for comprehensive medication safety assessment.
    """
    try:
        agent = SafetyAgent()
        result = await agent.process(request.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Safety check failed: {str(e)}")


# ============================================================================
# NavigatorAgent - Workflow Suggestions
# ============================================================================

class WorkflowRequest(BaseModel):
    """Request model for workflow suggestions."""
    current_status: str = Field(..., description="Current encounter status")
    encounter_type: str = Field(default="General", description="Type of encounter")
    pending_items: List[str] = Field(default_factory=list, description="Pending tasks")


class WorkflowResponse(BaseModel):
    """Response model for workflow suggestions."""
    next_steps: List[str]
    priority: str
    agent: str


@router.post("/navigator/suggest-workflow", response_model=WorkflowResponse)
async def suggest_next_steps(
    request: WorkflowRequest,
    current_user = Depends(get_current_user)
):
    """Suggest next steps in clinical workflow.
    
    Uses Claude to analyze clinical context and provide
    prioritized workflow recommendations.
    """
    try:
        agent = NavigatorAgent()
        result = await agent.process(request.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow suggestion failed: {str(e)}")


# ============================================================================
# CodingAgent - ICD-10/CPT Code Suggestions
# ============================================================================

class CodingRequest(BaseModel):
    """Request model for code suggestions."""
    clinical_note: str = Field(..., description="Clinical documentation")
    procedures: List[str] = Field(default_factory=list, description="Procedures performed")


class CodeSuggestion(BaseModel):
    """Model for individual code suggestion."""
    code: str
    description: str
    confidence: str


class CodingResponse(BaseModel):
    """Response model for code suggestions."""
    icd10_codes: List[CodeSuggestion]
    cpt_codes: List[CodeSuggestion]
    agent: str


@router.post("/coding/suggest-codes", response_model=CodingResponse)
async def suggest_medical_codes(
    request: CodingRequest,
    current_user = Depends(get_current_user)
):
    """Suggest ICD-10 and CPT codes from documentation.
    
    Combines AI-powered code suggestion with common diagnosis
    database for accurate medical billing assistance.
    """
    try:
        agent = CodingAgent()
        result = await agent.process(request.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code suggestion failed: {str(e)}")


# ============================================================================
# SentinelAgent - Security Threat Detection
# ============================================================================

class SecurityAnalysisRequest(BaseModel):
    """Request model for security analysis."""
    user_input: str = Field(..., description="User input to analyze")
    context: str = Field(default="", description="Optional context")


class SecurityAnalysisResponse(BaseModel):
    """Response model for security analysis."""
    threat_detected: bool
    threat_type: str = ""
    confidence: float = 0.0
    details: str = ""
    method: str = ""
    agent: str


@router.post("/sentinel/analyze-input", response_model=SecurityAnalysisResponse)
async def analyze_security_threat(
    request: SecurityAnalysisRequest,
    current_user = Depends(get_current_user)
):
    """Analyze user input for security threats.
    
    Uses pattern matching, ML model, and AI analysis to detect
    potential security threats like XSS, SQL injection, etc.
    """
    try:
        agent = SentinelAgent()
        result = await agent.process(request.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Security analysis failed: {str(e)}")


# ============================================================================
# ReadmissionAgent - 30-Day Readmission Risk Prediction
# ============================================================================

class ReadmissionRequest(BaseModel):
    """Request model for readmission risk prediction."""
    age: float = Field(..., description="Patient age in years")
    has_heart_failure: bool = Field(default=False, description="Heart failure diagnosis")
    has_diabetes: bool = Field(default=False, description="Diabetes diagnosis")
    has_copd: bool = Field(default=False, description="COPD diagnosis")
    comorbidity_count: int = Field(default=0, description="Total comorbidities")
    length_of_stay: int = Field(..., description="Hospital stay in days")
    visits_30d: int = Field(default=0, description="Hospital visits in last 30 days")
    visits_90d: int = Field(default=0, description="Hospital visits in last 90 days")
    discharge_disposition: str = Field(..., description="Discharge destination: home, snf, rehab")


class ReadmissionResponse(BaseModel):
    """Response model for readmission risk prediction."""
    risk_score: int
    probability: float
    risk_level: str
    alert: bool
    model_auc: float
    factors: List[str]
    recommendations: List[str] = []
    agent: str


@router.post("/readmission/predict-risk", response_model=ReadmissionResponse)
async def predict_readmission_risk(
    request: ReadmissionRequest,
    current_user = Depends(get_current_user)
):
    """Predict 30-day readmission risk for a patient.
    
    Uses trained XGBoost model to predict readmission risk
    based on patient demographics, comorbidities, and encounter data.
    Returns risk score, level, contributing factors, and recommendations.
    """
    try:
        from phoenix_guardian.agents.readmission import ReadmissionAgent
        agent = ReadmissionAgent()
        result = agent.predict(request.model_dump())
        
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Readmission prediction failed: {str(e)}")


# ============================================================================
# FraudAgent - Billing Fraud Detection (#8)
# ============================================================================

class FraudDetectionRequest(BaseModel):
    """Request model for fraud detection."""
    procedure_codes: List[str] = Field(default_factory=list, description="CPT codes billed")
    billed_cpt_code: str = Field(default="", description="Primary E/M code billed")
    encounter_complexity: str = Field(default="low", description="Documented complexity: minimal/straightforward/low/moderate/high")
    encounter_duration: int = Field(default=15, description="Visit duration in minutes")
    documented_elements: int = Field(default=6, description="Number of documented clinical elements")
    clinical_note: str = Field(default="", description="Clinical note for AI analysis")
    date_of_service: str = Field(default="", description="Date of service (ISO format)")


class FraudDetectionResponse(BaseModel):
    """Response model for fraud detection."""
    risk_level: str
    risk_score: float
    findings: List[Dict[str, Any]]
    checks_performed: List[str]
    agent: str


@router.post("/fraud/detect", response_model=FraudDetectionResponse)
async def detect_fraud(
    request: FraudDetectionRequest,
    current_user=Depends(get_current_user),
):
    """Detect billing fraud patterns.

    Checks for upcoding, unbundling, and anomalous billing patterns
    using rule-based NCCI edits and AI analysis.
    """
    try:
        agent = FraudAgent()
        result = await agent.process(request.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fraud detection failed: {str(e)}")


@router.post("/fraud/detect-unbundling")
async def detect_unbundling(
    procedure_codes: List[str],
    current_user=Depends(get_current_user),
):
    """Check procedure codes for NCCI unbundling violations."""
    agent = FraudAgent()
    result = agent.detect_unbundling(procedure_codes)
    return {"result": result, "agent": "fraud_detection"}


@router.post("/fraud/detect-upcoding")
async def detect_upcoding(
    billed_cpt_code: str,
    encounter_complexity: str = "low",
    encounter_duration: int = 15,
    documented_elements: int = 6,
    current_user=Depends(get_current_user),
):
    """Check for E/M upcoding."""
    agent = FraudAgent()
    result = agent.detect_upcoding(
        encounter_complexity=encounter_complexity,
        billed_cpt_code=billed_cpt_code,
        encounter_duration=encounter_duration,
        documented_elements=documented_elements,
    )
    return {"result": result, "agent": "fraud_detection"}


# ============================================================================
# ClinicalDecisionAgent - Clinical Decision Support (#9)
# ============================================================================

class TreatmentRecommendationRequest(BaseModel):
    """Request model for treatment recommendations."""
    diagnosis: str = Field(..., description="Primary diagnosis")
    patient_factors: Dict[str, Any] = Field(default_factory=dict, description="Age, comorbidities, allergies, sex")
    current_medications: List[str] = Field(default_factory=list, description="Current medication list")


class RiskScoreRequest(BaseModel):
    """Request model for clinical risk score calculation."""
    condition: str = Field(..., description="Condition: afib, chest pain, pe, pneumonia")
    clinical_data: Dict[str, Any] = Field(default_factory=dict, description="Parameters for score calculation")


class DifferentialRequest(BaseModel):
    """Request model for differential diagnosis."""
    symptoms: List[str] = Field(..., description="Presenting symptoms")
    patient_factors: Dict[str, Any] = Field(default_factory=dict, description="Age, sex, history")


@router.post("/clinical-decision/recommend-treatment")
async def recommend_treatment(
    request: TreatmentRecommendationRequest,
    current_user=Depends(get_current_user),
):
    """Get evidence-based treatment recommendations.

    Returns guideline-based first-line and alternative treatments
    with contraindication checks and monitoring recommendations.
    """
    try:
        agent = ClinicalDecisionAgent()
        result = await agent.recommend_treatment(
            diagnosis=request.diagnosis,
            patient_factors=request.patient_factors,
            current_medications=request.current_medications,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Treatment recommendation failed: {str(e)}")


@router.post("/clinical-decision/calculate-risk")
async def calculate_risk_score(
    request: RiskScoreRequest,
    current_user=Depends(get_current_user),
):
    """Calculate clinical risk scores.

    Supports: CHA₂DS₂-VASc (AFib), HEART (chest pain),
    Wells (PE), CURB-65 (pneumonia).
    """
    try:
        agent = ClinicalDecisionAgent()
        result = agent.calculate_risk_scores(
            condition=request.condition,
            clinical_data=request.clinical_data,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk score calculation failed: {str(e)}")


@router.post("/clinical-decision/differential")
async def generate_differential(
    request: DifferentialRequest,
    current_user=Depends(get_current_user),
):
    """Generate ranked differential diagnosis.

    Returns top 5 differential diagnoses with likelihood,
    key features, and recommended workup.
    """
    try:
        agent = ClinicalDecisionAgent()
        result = await agent.generate_differential(
            symptoms=request.symptoms,
            patient_factors=request.patient_factors,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Differential diagnosis failed: {str(e)}")


# ============================================================================
# PharmacyAgent - Pharmacy Integration (#10)
# ============================================================================

class FormularyCheckRequest(BaseModel):
    """Request model for formulary check."""
    medication: str = Field(..., description="Medication name")
    insurance_plan: str = Field(default="default", description="Insurance plan")
    patient_id: str = Field(default="", description="Patient identifier")


class PriorAuthCheckRequest(BaseModel):
    """Request model for prior authorization check."""
    medication: str = Field(..., description="Medication name")
    diagnosis: str = Field(default="", description="Primary diagnosis")
    insurance_plan: str = Field(default="default", description="Insurance plan")


class PrescriptionSendRequest(BaseModel):
    """Request model for e-prescribing."""
    prescription: Dict[str, Any] = Field(..., description="Prescription details")
    pharmacy_ncpdp: str = Field(..., description="Pharmacy NCPDP ID")
    patient: Dict[str, Any] = Field(default_factory=dict, description="Patient demographics")


class DURRequest(BaseModel):
    """Request model for drug utilization review."""
    prescription: Dict[str, Any] = Field(..., description="New prescription")
    current_medications: List[str] = Field(default_factory=list, description="Current medications")
    allergies: List[str] = Field(default_factory=list, description="Known allergies")
    patient_factors: Dict[str, Any] = Field(default_factory=dict, description="Age, weight, GFR")


@router.post("/pharmacy/check-formulary")
async def check_formulary(
    request: FormularyCheckRequest,
    current_user=Depends(get_current_user),
):
    """Check medication formulary status.

    Returns tier, copay, generic availability, and cost-saving alternatives.
    """
    try:
        agent = PharmacyAgent()
        result = agent.check_formulary(
            medication=request.medication,
            insurance_plan=request.insurance_plan,
            patient_id=request.patient_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Formulary check failed: {str(e)}")


@router.post("/pharmacy/check-prior-auth")
async def check_prior_auth(
    request: PriorAuthCheckRequest,
    current_user=Depends(get_current_user),
):
    """Check if prior authorization is required for a medication.

    Returns PA criteria and approval turnaround time.
    """
    try:
        agent = PharmacyAgent()
        result = agent.check_prior_auth_required(
            medication=request.medication,
            diagnosis=request.diagnosis,
            insurance=request.insurance_plan,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prior auth check failed: {str(e)}")


@router.post("/pharmacy/send-prescription")
async def send_prescription(
    request: PrescriptionSendRequest,
    current_user=Depends(get_current_user),
):
    """Send electronic prescription (NCPDP SCRIPT standard).

    Generates and transmits e-prescription to pharmacy.
    Demo mode — not transmitted to live pharmacy network.
    """
    try:
        agent = PharmacyAgent()
        result = await agent.send_erx(
            prescription=request.prescription,
            pharmacy_ncpdp=request.pharmacy_ncpdp,
            patient=request.patient,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"e-Prescribing failed: {str(e)}")


@router.post("/pharmacy/drug-utilization-review")
async def drug_utilization_review(
    request: DURRequest,
    current_user=Depends(get_current_user),
):
    """Perform Drug Utilization Review.

    Checks drug-drug interactions, allergies, duplicate therapy,
    and dose appropriateness.
    """
    try:
        agent = PharmacyAgent()
        result = await agent.drug_utilization_review(
            prescription=request.prescription,
            current_medications=request.current_medications,
            allergies=request.allergies,
            patient_factors=request.patient_factors,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drug utilization review failed: {str(e)}")


# ============================================================================
# DeceptionDetectionAgent - Consistency Analysis (#7)
# ============================================================================

class ConsistencyAnalysisRequest(BaseModel):
    """Request model for consistency analysis."""
    patient_history: List[str] = Field(default_factory=list, description="Previous patient statements")
    current_statement: str = Field(..., description="Current patient statement")


class DrugSeekingRequest(BaseModel):
    """Request model for drug-seeking detection."""
    patient_request: str = Field(..., description="Patient's medication request")
    medical_history: str = Field(default="", description="Documented medical history")
    current_medications: List[str] = Field(default_factory=list, description="Current medications")


@router.post("/deception/analyze-consistency")
async def analyze_consistency(
    request: ConsistencyAnalysisRequest,
    current_user=Depends(get_current_user),
):
    """Analyze consistency between current and past patient statements.

    Identifies contradictions, timeline discrepancies, and concerning patterns.
    Results are for physician review — not automated decision-making.
    """
    try:
        agent = DeceptionDetectionAgent()
        result = await agent.analyze_consistency(
            patient_history=request.patient_history,
            current_statement=request.current_statement,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Consistency analysis failed: {str(e)}")


@router.post("/deception/detect-drug-seeking")
async def detect_drug_seeking(
    request: DrugSeekingRequest,
    current_user=Depends(get_current_user),
):
    """Identify potential drug-seeking behavior patterns.

    Uses clinical red flags and AI analysis. Results are for physician
    awareness — always confirm with PDMP check and clinical judgment.
    """
    try:
        agent = DeceptionDetectionAgent()
        result = await agent.detect_drug_seeking(
            patient_request=request.patient_request,
            medical_history=request.medical_history,
            current_medications=request.current_medications,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drug seeking detection failed: {str(e)}")


# ============================================================================
# OrderManagementAgent - Intelligent Order Management (#6)
# ============================================================================

class LabSuggestionRequest(BaseModel):
    """Request model for lab suggestions."""
    clinical_note: str = Field(default="", description="Clinical documentation")
    diagnosis: str = Field(..., description="Primary diagnosis")
    patient_age: int = Field(..., description="Patient age in years")


class ImagingSuggestionRequest(BaseModel):
    """Request model for imaging suggestions."""
    chief_complaint: str = Field(..., description="Chief complaint")
    physical_exam: str = Field(default="", description="Physical exam findings")
    patient_age: int = Field(default=50, description="Patient age")


class PrescriptionGenerationRequest(BaseModel):
    """Request model for prescription generation."""
    medication: str = Field(..., description="Medication name")
    condition: str = Field(..., description="Condition being treated")
    patient_weight: float = Field(default=70.0, description="Patient weight in kg")
    patient_age: int = Field(..., description="Patient age in years")


@router.post("/orders/suggest-labs")
async def suggest_labs(
    request: LabSuggestionRequest,
    current_user=Depends(get_current_user),
):
    """Suggest appropriate lab tests based on diagnosis.

    Uses condition-specific panels and AI analysis for comprehensive
    lab order suggestions.
    """
    try:
        agent = OrderManagementAgent()
        result = await agent.suggest_labs(
            clinical_note=request.clinical_note,
            diagnosis=request.diagnosis,
            patient_age=request.patient_age,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lab suggestion failed: {str(e)}")


@router.post("/orders/suggest-imaging")
async def suggest_imaging(
    request: ImagingSuggestionRequest,
    current_user=Depends(get_current_user),
):
    """Suggest appropriate imaging studies.

    Follows ACR Appropriateness Criteria with radiation
    exposure considerations for pediatric patients.
    """
    try:
        agent = OrderManagementAgent()
        result = await agent.suggest_imaging(
            chief_complaint=request.chief_complaint,
            physical_exam=request.physical_exam,
            patient_age=request.patient_age,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Imaging suggestion failed: {str(e)}")


@router.post("/orders/generate-prescription")
async def generate_prescription(
    request: PrescriptionGenerationRequest,
    current_user=Depends(get_current_user),
):
    """Generate prescription with evidence-based dosing.

    Returns medication details including dosage, frequency, duration,
    quantity, monitoring, and counseling points.
    """
    try:
        agent = OrderManagementAgent()
        result = await agent.generate_prescription(
            medication=request.medication,
            condition=request.condition,
            patient_weight=request.patient_weight,
            patient_age=request.patient_age,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prescription generation failed: {str(e)}")
