"""Patient data endpoints.

Provides access to patient medical records from the EHR system.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from phoenix_guardian.api.dependencies import get_navigator
from phoenix_guardian.agents.navigator_agent import NavigatorAgent

router = APIRouter()


@router.get("/{mrn}")
async def get_patient(
    mrn: str,
    include_fields: Optional[str] = None,
    navigator: NavigatorAgent = Depends(get_navigator),
) -> Dict[str, Any]:
    """Fetch patient data by Medical Record Number.

    Args:
        mrn: Patient Medical Record Number
        include_fields: Optional comma-separated list of fields to include
                       (demographics, conditions, medications, allergies,
                        vitals, labs, last_encounter)

    Returns:
        Complete patient medical history

    Raises:
        HTTPException: If patient not found
    """
    # Build context
    context: Dict[str, Any] = {"patient_mrn": mrn}

    # Parse include_fields if provided
    if include_fields:
        fields_list: List[str] = [
            f.strip() for f in include_fields.split(",") if f.strip()
        ]
        if fields_list:
            context["include_fields"] = fields_list

    result = await navigator.execute(context)

    if not result.success:
        raise HTTPException(
            status_code=404,
            detail=f"Patient with MRN '{mrn}' not found",
        )

    return result.data
