"""
Protected encounter processing endpoints.

Handles secure encounter creation, SOAP note generation, and management.
All endpoints require authentication and proper role permissions.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from fastapi import Query as QueryParam

from phoenix_guardian.agents.navigator_agent import PatientNotFoundError
from phoenix_guardian.api.auth.utils import (
    get_current_active_user,
    require_can_edit,
    require_can_sign,
    require_physician,
)
from phoenix_guardian.api.dependencies import get_orchestrator
from phoenix_guardian.api.models import EncounterRequest, SOAPNoteResponse
from phoenix_guardian.api.utils.orchestrator import (
    EncounterOrchestrator,
    OrchestrationError,
)
from phoenix_guardian.database.connection import get_db
from phoenix_guardian.models import (
    AuditAction,
    AuditLog,
    Encounter,
    EncounterStatus,
    SOAPNote,
    User,
)


router = APIRouter(tags=["Encounters"])


# =============================================================================
# Request/Response Models
# =============================================================================


class EncounterCreateRequest(BaseModel):
    """Request model for creating a new encounter."""
    patient_mrn: str = Field(..., min_length=1, description="Patient MRN")
    transcript: str = Field(..., min_length=10, description="Encounter transcript")
    encounter_type: str = Field(default="outpatient", description="Type of encounter")
    chief_complaint: Optional[str] = Field(None, description="Chief complaint")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_mrn": "MRN001",
                "transcript": "Patient presents with persistent headache for 3 days...",
                "encounter_type": "outpatient",
                "chief_complaint": "Headache"
            }
        }
    )


class EncounterResponse(BaseModel):
    """Response model for encounter data."""
    id: int
    patient_mrn: str
    encounter_type: str
    status: str
    chief_complaint: Optional[str] = None
    visit_date: datetime
    created_at: datetime
    created_by: Optional[int] = None
    has_soap_note: bool = False
    
    model_config = ConfigDict(from_attributes=True)


class SOAPNoteUpdateRequest(BaseModel):
    """Request model for updating a SOAP note."""
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None


class SOAPNoteSignRequest(BaseModel):
    """Request model for signing a SOAP note."""
    attestation: str = Field(..., description="Signing attestation statement")


class SOAPNoteDBResponse(BaseModel):
    """Response model for SOAP note from database."""
    id: int
    encounter_id: int
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    full_note: Optional[str] = None
    is_signed: bool
    was_edited: bool = False
    edit_count: int = 0
    reviewed_by: Optional[int] = None
    generated_by_model: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# In-memory storage for encounters (replace with database in production)
ENCOUNTERS_DB: Dict[str, Dict[str, Any]] = {}


# =============================================================================
# Protected Endpoints
# =============================================================================


@router.post(
    "",
    response_model=SOAPNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_encounter(
    request: Request,
    encounter: EncounterRequest,
    orchestrator: EncounterOrchestrator = Depends(get_orchestrator),
    current_user: User = Depends(require_physician),
    db: Session = Depends(get_db)
) -> SOAPNoteResponse:
    """
    Create a new encounter and generate SOAP note.
    
    **Requires:** PHYSICIAN role or higher
    
    This endpoint:
    1. Validates encounter data
    2. Fetches patient history
    3. Generates SOAP note using AI
    4. Creates database records with proper audit trail
    5. Returns complete results
    
    **Request Body:**
    - `patient_mrn`: Patient Medical Record Number
    - `transcript`: Complete encounter transcript
    - `encounter_type`: Type of encounter (outpatient, inpatient, emergency)
    - `provider_id`: Optional provider ID (defaults to current user)
    
    **Returns:**
    - Generated SOAP note with metadata
    
    **Errors:**
    - `401`: Not authenticated
    - `403`: Not a physician
    - `404`: Patient not found
    - `500`: Processing error
    """
    try:
        # Use current user as provider if not specified
        provider_id = encounter.provider_id or str(current_user.id)
        
        # Process encounter through orchestrator
        result = await orchestrator.process_encounter(
            patient_mrn=encounter.patient_mrn,
            transcript=encounter.transcript,
            encounter_type=encounter.encounter_type.value,
            provider_id=provider_id,
        )

        # Store encounter (in-memory for now)
        encounter_id = result["encounter_id"]
        ENCOUNTERS_DB[encounter_id] = result

        # Get client info for audit log
        ip_address = request.client.host if request.client else None
        
        # Log PHI access for HIPAA compliance
        try:
            AuditLog.log_action(
                session=db,
                action=AuditAction.PHI_ACCESSED,
                user_id=current_user.id,
                user_email=current_user.email,
                resource_type="encounter",
                resource_id=None,
                ip_address=ip_address,
                success=True,
                description=f"Created encounter for patient {encounter.patient_mrn}",
                metadata={
                    "patient_mrn": encounter.patient_mrn,
                    "encounter_type": encounter.encounter_type.value,
                    "encounter_id": encounter_id,
                }
            )
        except Exception:
            # Don't let audit logging failure prevent encounter creation
            db.rollback()

        # Build response
        response = SOAPNoteResponse(
            encounter_id=result["encounter_id"],
            patient_mrn=result["patient_mrn"],
            soap_note=result["soap_note"],
            sections=result["sections"],
            reasoning=result["reasoning"],
            model_used=result["model_used"],
            token_count=result["token_count"],
            execution_time_ms=result["execution_metrics"]["total_time_ms"],
            created_at=result["created_at"],
            status=result["status"],
        )

        return response

    except PatientNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    except OrchestrationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process encounter: {str(e)}",
        ) from e

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the encounter",
        ) from e


@router.get("/{encounter_id}")
async def get_encounter(
    request: Request,
    encounter_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retrieve an encounter by ID.
    
    **Requires:** Any authenticated user
    
    All PHI access is logged for HIPAA compliance.
    
    **Path Parameters:**
    - `encounter_id`: Unique encounter identifier
    
    **Returns:**
    - Encounter data including SOAP note
    
    **Errors:**
    - `401`: Not authenticated
    - `404`: Encounter not found
    """
    encounter = ENCOUNTERS_DB.get(encounter_id)

    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Encounter '{encounter_id}' not found",
        )
    
    # Get client info for audit log
    ip_address = request.client.host if request.client else None
    
    # Log PHI access (don't let audit failure break the endpoint)
    try:
        AuditLog.log_action(
            session=db,
            action=AuditAction.PHI_ACCESSED,
            user_id=current_user.id,
            user_email=current_user.email,
            resource_type="encounter",
            resource_id=None,
            ip_address=ip_address,
            success=True,
            description=f"Viewed encounter {encounter_id}",
            metadata={"patient_mrn": encounter.get("patient_mrn"), "encounter_id": encounter_id}
        )
    except Exception:
        db.rollback()

    # Return in the format the frontend expects (EncounterApiResponse shape)
    sections = encounter.get("sections", {})
    # Map status: backend uses 'pending_review', frontend expects 'awaiting_review'
    raw_status = encounter.get("status", "pending_review")
    fe_status = "awaiting_review" if raw_status == "pending_review" else raw_status
    return {
        "id": 0,
        "uuid": encounter_id,
        "status": fe_status,
        "patient_first_name": None,
        "patient_last_name": None,
        "patient_dob": None,
        "patient_mrn": encounter.get("patient_mrn"),
        "encounter_type": encounter.get("encounter_type", "office_visit"),
        "chief_complaint": None,
        "transcript_text": None,
        "soap_note": sections if sections else None,
        "ai_confidence_score": None,
        "safety_flags": [],
        "icd_codes": [],
        "cpt_codes": [],
        "physician_edits": None,
        "physician_signature": None,
        "signed_at": None,
        "created_at": encounter.get("created_at", ""),
        "updated_at": None,
        "created_by_id": current_user.id,
        "assigned_physician_id": None,
    }


@router.post("/{encounter_id}/approve")
async def approve_encounter(
    encounter_id: str,
    request: Request,
    current_user: User = Depends(require_physician),
) -> Dict[str, Any]:
    """
    Approve and sign a SOAP note.
    
    **Requires:** PHYSICIAN role
    """
    encounter = ENCOUNTERS_DB.get(encounter_id)
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Encounter '{encounter_id}' not found",
        )
    
    # Parse request body
    body = await request.json()
    signature = body.get("signature", "")
    
    # Update encounter status
    encounter["status"] = "approved"
    encounter["physician_signature"] = signature
    encounter["signed_at"] = datetime.now(timezone.utc).isoformat()
    ENCOUNTERS_DB[encounter_id] = encounter
    
    sections = encounter.get("sections", {})
    return {
        "id": 0,
        "uuid": encounter_id,
        "status": "approved",
        "patient_first_name": None,
        "patient_last_name": None,
        "patient_dob": None,
        "patient_mrn": encounter.get("patient_mrn"),
        "encounter_type": encounter.get("encounter_type", "office_visit"),
        "chief_complaint": None,
        "transcript_text": None,
        "soap_note": sections if sections else None,
        "ai_confidence_score": None,
        "safety_flags": [],
        "icd_codes": [],
        "cpt_codes": [],
        "physician_edits": None,
        "physician_signature": signature,
        "signed_at": encounter["signed_at"],
        "created_at": encounter.get("created_at", ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by_id": current_user.id,
        "assigned_physician_id": None,
    }


@router.post("/{encounter_id}/reject")
async def reject_encounter(
    encounter_id: str,
    request: Request,
    current_user: User = Depends(require_physician),
) -> Dict[str, Any]:
    """
    Reject a SOAP note.
    
    **Requires:** PHYSICIAN role
    """
    encounter = ENCOUNTERS_DB.get(encounter_id)
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Encounter '{encounter_id}' not found",
        )
    
    body = await request.json()
    reason = body.get("reason", "")
    
    encounter["status"] = "rejected"
    encounter["reject_reason"] = reason
    ENCOUNTERS_DB[encounter_id] = encounter
    
    sections = encounter.get("sections", {})
    return {
        "id": 0,
        "uuid": encounter_id,
        "status": "rejected",
        "patient_first_name": None,
        "patient_last_name": None,
        "patient_dob": None,
        "patient_mrn": encounter.get("patient_mrn"),
        "encounter_type": encounter.get("encounter_type", "office_visit"),
        "chief_complaint": None,
        "transcript_text": None,
        "soap_note": sections if sections else None,
        "ai_confidence_score": None,
        "safety_flags": [],
        "icd_codes": [],
        "cpt_codes": [],
        "physician_edits": None,
        "physician_signature": None,
        "signed_at": None,
        "created_at": encounter.get("created_at", ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by_id": current_user.id,
        "assigned_physician_id": None,
    }


@router.get("")
async def list_encounters(
    page: int = 1,
    page_size: int = 10,
    status: Optional[str] = QueryParam(None, alias="status"),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    List all encounters with pagination.
    
    **Requires:** Any authenticated user
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 10)
    - `status`: Optional status filter (e.g. 'awaiting_review')
    
    **Returns:**
    - Paginated list of encounters
    """
    # Get all in-memory encounters as list
    all_encounters = []
    for eid, enc in ENCOUNTERS_DB.items():
        sections = enc.get("sections", {})
        raw_status = enc.get("status", "pending_review")
        fe_status = "awaiting_review" if raw_status == "pending_review" else raw_status
        
        all_encounters.append({
            "id": 0,
            "uuid": eid,
            "status": fe_status,
            "patient_first_name": None,
            "patient_last_name": None,
            "patient_dob": None,
            "patient_mrn": enc.get("patient_mrn"),
            "encounter_type": enc.get("encounter_type", "office_visit"),
            "chief_complaint": None,
            "transcript_text": None,
            "soap_note": sections if sections else None,
            "ai_confidence_score": None,
            "safety_flags": [],
            "icd_codes": [],
            "cpt_codes": [],
            "physician_edits": None,
            "physician_signature": enc.get("physician_signature"),
            "signed_at": enc.get("signed_at"),
            "created_at": enc.get("created_at", ""),
            "updated_at": None,
            "created_by_id": current_user.id,
            "assigned_physician_id": None,
        })
    
    # Apply status filter if provided
    if status:
        all_encounters = [e for e in all_encounters if e["status"] == status]
    
    # Sort by created_at descending
    all_encounters.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    # Paginate
    total = len(all_encounters)
    start = (page - 1) * page_size
    end = start + page_size
    items = all_encounters[start:end]
    pages = max(1, (total + page_size - 1) // page_size)
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


# =============================================================================
# Database-backed Protected Endpoints
# =============================================================================


@router.post("/db", response_model=EncounterResponse, status_code=status.HTTP_201_CREATED)
async def create_db_encounter(
    request: Request,
    encounter_data: EncounterCreateRequest,
    current_user: User = Depends(require_physician),
    db: Session = Depends(get_db)
) -> EncounterResponse:
    """
    Create a new encounter in the database.
    
    **Requires:** PHYSICIAN role or higher
    
    Creates a new encounter record with full audit trail.
    
    **Request Body:**
    - `patient_mrn`: Patient Medical Record Number
    - `transcript`: Encounter transcript
    - `encounter_type`: Type of encounter
    - `chief_complaint`: Optional chief complaint
    """
    # Create encounter record
    encounter = Encounter(
        patient_mrn=encounter_data.patient_mrn,
        encounter_type=encounter_data.encounter_type,
        status=EncounterStatus.DRAFT,
        chief_complaint=encounter_data.chief_complaint,
        visit_date=datetime.now(timezone.utc),
        transcript=encounter_data.transcript,
        created_by=current_user.id,
        provider_id=current_user.id
    )
    
    db.add(encounter)
    db.commit()
    db.refresh(encounter)
    
    # Get client info for audit log
    ip_address = request.client.host if request.client else None
    
    # Log encounter creation
    AuditLog.log_action(
        session=db,
        action=AuditAction.ENCOUNTER_CREATED,
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="encounter",
        resource_id=encounter.id,
        ip_address=ip_address,
        success=True,
        description=f"Created encounter for patient {encounter_data.patient_mrn}",
        metadata={
            "patient_mrn": encounter_data.patient_mrn,
            "encounter_type": encounter_data.encounter_type
        }
    )
    
    return EncounterResponse(
        id=encounter.id,
        patient_mrn=encounter.patient_mrn,
        encounter_type=encounter.encounter_type,
        status=encounter.status.value,
        chief_complaint=encounter.chief_complaint,
        visit_date=encounter.visit_date,
        created_at=encounter.created_at,
        created_by=encounter.created_by,
        has_soap_note=False
    )


@router.get("/db/{encounter_id}", response_model=EncounterResponse)
async def get_db_encounter(
    request: Request,
    encounter_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> EncounterResponse:
    """
    Retrieve an encounter from the database.
    
    **Requires:** Any authenticated user
    
    All PHI access is logged.
    """
    encounter = db.query(Encounter).filter(
        Encounter.id == encounter_id,
        Encounter.is_deleted == False
    ).first()
    
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found"
        )
    
    # Get client info for audit log
    ip_address = request.client.host if request.client else None
    
    # Log PHI access
    AuditLog.log_action(
        session=db,
        action=AuditAction.PHI_ACCESSED,
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="encounter",
        resource_id=encounter.id,
        ip_address=ip_address,
        success=True,
        description=f"Viewed encounter {encounter.id}"
    )
    
    # Check if encounter has SOAP note
    has_soap = db.query(SOAPNote).filter(
        SOAPNote.encounter_id == encounter.id
    ).first() is not None
    
    return EncounterResponse(
        id=encounter.id,
        patient_mrn=encounter.patient_mrn,
        encounter_type=encounter.encounter_type,
        status=encounter.status.value,
        chief_complaint=encounter.chief_complaint,
        visit_date=encounter.visit_date,
        created_at=encounter.created_at,
        created_by=encounter.created_by,
        has_soap_note=has_soap
    )


@router.get("/db/{encounter_id}/soap", response_model=SOAPNoteDBResponse)
async def get_encounter_soap_note(
    request: Request,
    encounter_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> SOAPNoteDBResponse:
    """
    Get the SOAP note for an encounter.
    
    **Requires:** Any authenticated user
    
    Returns the latest version of the SOAP note.
    """
    # Verify encounter exists
    encounter = db.query(Encounter).filter(
        Encounter.id == encounter_id,
        Encounter.is_deleted == False
    ).first()
    
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found"
        )
    
    # Get SOAP note for this encounter
    soap_note = db.query(SOAPNote).filter(
        SOAPNote.encounter_id == encounter_id
    ).first()
    
    if not soap_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SOAP note not found for this encounter"
        )
    
    # Get client info for audit log
    ip_address = request.client.host if request.client else None
    
    # Log PHI access
    AuditLog.log_action(
        session=db,
        action=AuditAction.PHI_ACCESSED,
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="soap_note",
        resource_id=soap_note.id,
        ip_address=ip_address,
        success=True,
        description=f"Viewed SOAP note for encounter {encounter_id}"
    )
    
    return SOAPNoteDBResponse(
        id=soap_note.id,
        encounter_id=soap_note.encounter_id,
        subjective=soap_note.subjective,
        objective=soap_note.objective,
        assessment=soap_note.assessment,
        plan=soap_note.plan,
        full_note=soap_note.full_note,
        is_signed=soap_note.is_signed,
        was_edited=soap_note.was_edited,
        edit_count=soap_note.edit_count,
        reviewed_by=soap_note.reviewed_by,
        generated_by_model=soap_note.generated_by_model,
        created_at=soap_note.created_at
    )


@router.put("/db/{encounter_id}/soap", response_model=SOAPNoteDBResponse)
async def update_soap_note(
    request: Request,
    encounter_id: int,
    update_data: SOAPNoteUpdateRequest,
    current_user: User = Depends(require_can_edit),
    db: Session = Depends(get_db)
) -> SOAPNoteDBResponse:
    """
    Update a SOAP note.
    
    **Requires:** Edit permission (Physician, Nurse, or Scribe)
    
    Cannot update signed notes - creates a new version instead if needed.
    """
    # Get current SOAP note
    soap_note = db.query(SOAPNote).filter(
        SOAPNote.encounter_id == encounter_id
    ).first()
    
    if not soap_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SOAP note not found"
        )
    
    # Cannot edit signed notes
    if soap_note.is_signed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify signed SOAP note. Create an amendment instead."
        )
    
    # Update fields
    if update_data.subjective is not None:
        soap_note.subjective = update_data.subjective
    if update_data.objective is not None:
        soap_note.objective = update_data.objective
    if update_data.assessment is not None:
        soap_note.assessment = update_data.assessment
    if update_data.plan is not None:
        soap_note.plan = update_data.plan
    
    # Update full note
    soap_note.full_note = f"""SUBJECTIVE:
{soap_note.subjective or ''}

OBJECTIVE:
{soap_note.objective or ''}

ASSESSMENT:
{soap_note.assessment or ''}

PLAN:
{soap_note.plan or ''}"""
    
    # Mark as edited
    soap_note.mark_edited()
    soap_note.modified_by = current_user.id
    db.commit()
    db.refresh(soap_note)
    
    # Get client info for audit log
    ip_address = request.client.host if request.client else None
    
    # Log modification
    AuditLog.log_action(
        session=db,
        action=AuditAction.NOTE_MODIFIED,
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="soap_note",
        resource_id=soap_note.id,
        ip_address=ip_address,
        success=True,
        description=f"Modified SOAP note for encounter {encounter_id}"
    )
    
    return SOAPNoteDBResponse(
        id=soap_note.id,
        encounter_id=soap_note.encounter_id,
        subjective=soap_note.subjective,
        objective=soap_note.objective,
        assessment=soap_note.assessment,
        plan=soap_note.plan,
        full_note=soap_note.full_note,
        is_signed=soap_note.is_signed,
        was_edited=soap_note.was_edited,
        edit_count=soap_note.edit_count,
        reviewed_by=soap_note.reviewed_by,
        generated_by_model=soap_note.generated_by_model,
        created_at=soap_note.created_at
    )


@router.post("/db/{encounter_id}/soap/sign", response_model=SOAPNoteDBResponse)
async def sign_soap_note(
    request: Request,
    encounter_id: int,
    sign_data: SOAPNoteSignRequest,
    current_user: User = Depends(require_can_sign),
    db: Session = Depends(get_db)
) -> SOAPNoteDBResponse:
    """
    Sign a SOAP note (physician attestation).
    
    **Requires:** Sign permission (Physicians only)
    
    Once signed, note cannot be modified. This is a legally binding action.
    """
    # Get current SOAP note
    soap_note = db.query(SOAPNote).filter(
        SOAPNote.encounter_id == encounter_id
    ).first()
    
    if not soap_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SOAP note not found"
        )
    
    if soap_note.is_signed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SOAP note is already signed"
        )
    
    # Sign the note using the model method
    soap_note.sign(current_user.id)
    
    # Update encounter status
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if encounter:
        encounter.status = EncounterStatus.COMPLETED
    
    db.commit()
    db.refresh(soap_note)
    
    # Get client info for audit log
    ip_address = request.client.host if request.client else None
    
    # Log signing (important audit event)
    AuditLog.log_action(
        session=db,
        action=AuditAction.NOTE_SIGNED,
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="soap_note",
        resource_id=soap_note.id,
        ip_address=ip_address,
        success=True,
        description=f"Signed SOAP note for encounter {encounter_id}",
        metadata={
            "attestation": sign_data.attestation,
            "signer_npi": current_user.npi_number
        }
    )
    
    return SOAPNoteDBResponse(
        id=soap_note.id,
        encounter_id=soap_note.encounter_id,
        subjective=soap_note.subjective,
        objective=soap_note.objective,
        assessment=soap_note.assessment,
        plan=soap_note.plan,
        full_note=soap_note.full_note,
        is_signed=soap_note.is_signed,
        was_edited=soap_note.was_edited,
        edit_count=soap_note.edit_count,
        reviewed_by=soap_note.reviewed_by,
        generated_by_model=soap_note.generated_by_model,
        created_at=soap_note.created_at
    )


@router.get("/db/list", response_model=List[EncounterResponse])
async def list_db_encounters(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[EncounterResponse]:
    """
    List encounters from database with pagination.
    
    **Requires:** Any authenticated user
    
    **Query Parameters:**
    - `skip`: Number of records to skip (default: 0)
    - `limit`: Maximum records to return (default: 20, max: 100)
    """
    limit = min(limit, 100)  # Cap at 100
    
    encounters = db.query(Encounter).filter(
        Encounter.is_deleted == False
    ).order_by(
        Encounter.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    result = []
    for enc in encounters:
        has_soap = db.query(SOAPNote).filter(
            SOAPNote.encounter_id == enc.id
        ).first() is not None
        
        result.append(EncounterResponse(
            id=enc.id,
            patient_mrn=enc.patient_mrn,
            encounter_type=enc.encounter_type,
            status=enc.status.value,
            chief_complaint=enc.chief_complaint,
            visit_date=enc.visit_date,
            created_at=enc.created_at,
            created_by=enc.created_by,
            has_soap_note=has_soap
        ))
    
    return result
