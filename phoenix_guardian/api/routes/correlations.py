"""
Cross-Agent Correlation API routes.

Endpoint:
  GET /correlations/{patient_id} — Check cross-agent correlations for a patient
"""

from fastapi import APIRouter, Depends
from phoenix_guardian.api.auth.utils import get_current_active_user
from phoenix_guardian.models import User
from phoenix_guardian.agents.cross_agent_correlator import correlator

router = APIRouter(tags=["cross-agent-correlations"])


@router.get("/correlations/{patient_id}")
async def get_correlations(
    patient_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Check cross-agent correlations for a patient.
    Uses Redis-cached results from recent agent runs.
    """
    try:
        triggered = correlator.correlate(patient_id)
        return {
            "patient_id": patient_id,
            "correlations": triggered,
            "correlation_count": len(triggered),
        }
    except Exception as e:
        return {
            "patient_id": patient_id,
            "correlations": [],
            "correlation_count": 0,
            "error": str(e),
        }
