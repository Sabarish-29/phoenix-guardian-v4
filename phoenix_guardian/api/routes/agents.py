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
