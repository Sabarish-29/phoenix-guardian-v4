"""Pydantic models for API request/response validation.

These models ensure type safety and automatic validation
for all API endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ===== PATIENT MODELS =====


class PatientDemographics(BaseModel):
    """Patient demographic information."""

    name: str = Field(..., description="Patient full name")
    age: int = Field(..., ge=0, le=150, description="Patient age in years")
    gender: str = Field(..., description="Patient gender")
    dob: str = Field(..., description="Date of birth (YYYY-MM-DD)")


class Medication(BaseModel):
    """Medication information."""

    name: str = Field(..., description="Medication name")
    dose: str = Field(..., description="Dosage (e.g., '10mg')")
    frequency: str = Field(..., description="Frequency (e.g., 'Once daily')")
    route: str = Field(..., description="Route of administration")


class Allergy(BaseModel):
    """Allergy information."""

    allergen: str = Field(..., description="Allergen name")
    reaction: str = Field(..., description="Reaction type")
    severity: str = Field(..., description="Severity level")


class VitalSigns(BaseModel):
    """Vital signs measurement."""

    blood_pressure: str = Field(..., description="BP (e.g., '120/80')")
    heart_rate: int = Field(..., ge=20, le=300, description="Heart rate (bpm)")
    temperature: float = Field(
        ..., ge=90.0, le=110.0, description="Temperature (°F)"
    )
    respiratory_rate: int = Field(..., ge=5, le=60, description="Respiratory rate")
    oxygen_saturation: int = Field(
        ..., ge=0, le=100, description="O2 saturation (%)"
    )
    recorded_at: str = Field(..., description="Timestamp (ISO 8601)")


class LabResult(BaseModel):
    """Laboratory test result."""

    test: str = Field(..., description="Test name")
    value: str = Field(..., description="Test value")
    reference_range: str = Field(..., description="Normal reference range")
    date: str = Field(..., description="Test date")


class LastEncounter(BaseModel):
    """Previous encounter information."""

    date: str = Field(..., description="Encounter date")
    type: str = Field(..., description="Encounter type")
    provider: str = Field(..., description="Provider name")
    chief_complaint: str = Field(..., description="Chief complaint")


class PatientHistory(BaseModel):
    """Complete patient medical history."""

    mrn: str = Field(..., description="Medical Record Number")
    demographics: PatientDemographics
    conditions: List[str] = Field(
        default_factory=list, description="Medical conditions"
    )
    medications: List[Medication] = Field(default_factory=list)
    allergies: List[Allergy] = Field(default_factory=list)
    vitals: Optional[VitalSigns] = None
    labs: List[LabResult] = Field(default_factory=list)
    last_encounter: Optional[LastEncounter] = None
    retrieved_at: Optional[str] = None

    model_config = {"extra": "allow"}


# ===== ENCOUNTER MODELS =====


class EncounterType(str, Enum):
    """Types of clinical encounters."""

    OFFICE_VISIT = "office_visit"
    URGENT_CARE = "urgent_care"
    EMERGENCY = "emergency"
    TELEHEALTH = "telehealth"
    FOLLOW_UP = "follow_up"


class EncounterRequest(BaseModel):
    """Request to create a new encounter."""

    patient_mrn: str = Field(
        ...,
        min_length=5,
        max_length=20,
        description="Patient Medical Record Number",
    )
    encounter_type: EncounterType
    transcript: str = Field(
        ...,
        min_length=50,
        max_length=10000,
        description="Encounter transcript",
    )
    provider_id: Optional[str] = Field(None, description="Physician/provider ID (defaults to current user)")

    @field_validator("transcript")
    @classmethod
    def validate_transcript(cls, value: str) -> str:
        """Ensure transcript has meaningful content."""
        if len(value.strip()) < 50:
            raise ValueError("Transcript must be at least 50 characters")
        return value.strip()


class SOAPNoteResponse(BaseModel):
    """Response containing generated SOAP note."""

    encounter_id: str = Field(..., description="Unique encounter ID")
    patient_mrn: str
    soap_note: str = Field(..., description="Generated SOAP note")
    sections: Dict[str, str] = Field(
        ...,
        description="Parsed SOAP sections (subjective, objective, assessment, plan)",
    )
    reasoning: str = Field(..., description="AI reasoning trail")
    model_used: str = Field(..., description="AI model identifier")
    token_count: int = Field(..., description="Total tokens used")
    execution_time_ms: float = Field(..., description="Processing time")
    created_at: str = Field(..., description="Creation timestamp")
    status: str = Field(
        default="pending_review",
        description="Note status (pending_review, approved, rejected)",
    )


class SOAPNoteRequest(BaseModel):
    """Request to generate SOAP note from encounter."""

    encounter_id: str = Field(..., description="Encounter ID")

    model_config = {
        "json_schema_extra": {"example": {"encounter_id": "enc_20250130_001"}}
    }


# ===== AUTHENTICATION MODELS =====


class LoginRequest(BaseModel):
    """User login credentials."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class LoginResponse(BaseModel):
    """Successful login response."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(..., description="Token expiration (seconds)")
    user_id: str
    username: str
    role: str = Field(..., description="User role (physician, admin, nurse)")


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str = Field(..., description="User ID (subject)")
    username: str
    role: str
    exp: int = Field(..., description="Expiration timestamp")


# ===== HEALTH CHECK MODELS =====


class HealthStatus(str, Enum):
    """System health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class AgentHealth(BaseModel):
    """Individual agent health status."""

    name: str
    status: HealthStatus
    avg_execution_time_ms: float
    call_count: int
    error_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Error rate (0.0-1.0)"
    )


class HealthCheckResponse(BaseModel):
    """System health check response."""

    status: HealthStatus
    timestamp: str = Field(..., description="Check timestamp (ISO 8601)")
    version: str = Field(default="1.0.0")
    agents: List[AgentHealth]
    database_connected: bool
    api_latency_ms: float


# ===== METRICS MODELS =====


class SystemMetrics(BaseModel):
    """Aggregated system metrics."""

    total_encounters: int = Field(..., description="Total encounters processed")
    total_soap_notes: int = Field(..., description="Total SOAP notes generated")
    avg_processing_time_ms: float
    success_rate: float = Field(..., ge=0.0, le=1.0)
    uptime_hours: float
    agents: List[AgentHealth]


# ===== ERROR MODELS =====


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    timestamp: str = Field(..., description="Error timestamp")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "PatientNotFoundError",
                "message": "Patient with MRN 'MRN999999' not found in EHR",
                "detail": "Please verify the Medical Record Number",
                "timestamp": "2025-01-30T14:30:00Z",
            }
        }
    }
