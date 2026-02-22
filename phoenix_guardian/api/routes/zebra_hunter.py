"""
Zebra Hunter API routes — Phoenix Guardian V5 Phase 3.

Endpoints:
  POST /zebra-hunter/analyze/{patient_id}    — run full ZebraHunter analysis
  GET  /zebra-hunter/result/{patient_id}     — fetch stored analysis result
  GET  /zebra-hunter/ghost-cases             — list all ghost cases
  POST /zebra-hunter/report-ghost/{ghost_id} — report ghost case to ICMR/CDC
  GET  /zebra-hunter/health                  — public health check
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from phoenix_guardian.api.auth.utils import get_current_active_user
from phoenix_guardian.database.connection import get_db
from phoenix_guardian.agents.zebra_hunter_agent import (
    ZebraHunterAgent,
    PATIENT_A_ID,
    PATIENT_B_ID,
)
from phoenix_guardian.config.v5_agent_config import v5_settings
from phoenix_guardian.models import User

logger = logging.getLogger("phoenix_guardian.api.routes.zebra_hunter")

router = APIRouter(tags=["Zebra Hunter"])

# ── Shared agent instance ─────────────────────────────────────────────────
_agent: Optional[ZebraHunterAgent] = None


def _get_agent() -> ZebraHunterAgent:
    global _agent
    if _agent is None:
        _agent = ZebraHunterAgent()
    return _agent


# ==========================================================================
# Pydantic response models
# ==========================================================================


class MatchResponse(BaseModel):
    disease: str = ""
    orphacode: str = ""
    confidence: int = 0
    matching_symptoms: List[str] = Field(default_factory=list)
    total_patient_symptoms: int = 0
    url: str = ""


class TimelineEntry(BaseModel):
    visit_number: int = 0
    visit_date: str = ""
    diagnosis_given: str = ""
    was_diagnosable: bool = False
    missed_clues: List[str] = Field(default_factory=list)
    confidence: int = 0
    reason: str = ""
    is_first_diagnosable: bool = False


class GhostProtocolResult(BaseModel):
    activated: bool = False
    ghost_id: Optional[str] = None
    patient_count: int = 0
    symptom_signature: List[str] = Field(default_factory=list)
    symptom_hash: str = ""
    first_case_seen: str = ""
    message: str = ""


class AnalyzeResponse(BaseModel):
    status: str = ""
    patient_id: str = ""
    patient_name: str = ""
    total_visits: int = 0
    symptoms_found: List[str] = Field(default_factory=list)
    analysis_timestamp: str = ""
    top_matches: List[MatchResponse] = Field(default_factory=list)
    missed_clue_timeline: List[TimelineEntry] = Field(default_factory=list)
    years_lost: float = 0.0
    first_diagnosable_visit: Optional[TimelineEntry] = None
    recommendation: str = ""
    ghost_protocol: Optional[GhostProtocolResult] = None
    analysis_time_seconds: float = 0.0


class GhostCaseResponse(BaseModel):
    ghost_id: str = ""
    patient_count: int = 0
    symptom_signature: List[str] = Field(default_factory=list)
    status: str = ""
    first_seen: str = ""
    alert_fired_at: Optional[str] = None
    reported_to: Optional[str] = None


class GhostCasesListResponse(BaseModel):
    total_ghost_cases: int = 0
    alert_fired_count: int = 0
    cases: List[GhostCaseResponse] = Field(default_factory=list)


class ReportGhostResponse(BaseModel):
    ghost_id: str = ""
    status: str = ""
    reported_to: str = ""
    message: str = ""


class HealthResponse(BaseModel):
    status: str = "healthy"
    orphadata_reachable: bool = False
    orphadata_authenticated: bool = False
    demo_fallback_loaded: bool = True
    redis_connected: bool = False
    patient_a_ready: bool = False
    patient_b_ready: bool = False
    ghost_seed_exists: bool = False


# ==========================================================================
# Endpoints
# ==========================================================================


@router.post("/analyze/{patient_id}", response_model=AnalyzeResponse)
async def analyze_patient(
    patient_id: str,
    language: str = "en",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Run full ZebraHunter rare disease analysis for a patient.

    This is a POST because it triggers a computation, not just a read.
    Calls extract_symptoms → search_orphadata → reconstruct_missed_clues
    or ghost_protocol, stores result, and returns.
    """
    agent = _get_agent()
    try:
        result = await agent.analyze(patient_id, db, language=language)
        return result
    except Exception as exc:
        logger.error("ZebraHunter analysis failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(exc)}",
        )


@router.get("/result/{patient_id}", response_model=AnalyzeResponse)
async def get_result(
    patient_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Fetch the most recent stored analysis for a patient.

    Does NOT re-run the analysis — just fetches stored result.
    Returns 404 if no prior analysis exists.
    """
    row = db.execute(
        text("""
            SELECT full_result FROM zebra_analyses
            WHERE patient_id = :pid
            ORDER BY analyzed_at DESC LIMIT 1
        """),
        {"pid": patient_id},
    ).fetchone()

    if not row or not row[0]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No prior analysis found for this patient.",
        )

    return json.loads(row[0]) if isinstance(row[0], str) else row[0]


@router.get("/ghost-cases", response_model=GhostCasesListResponse)
async def get_ghost_cases(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Return all active ghost cases."""
    rows = db.execute(
        text("""
            SELECT ghost_id, patient_count, symptom_signature,
                   status, first_seen, alert_fired_at, reported_to
            FROM ghost_cases
            ORDER BY last_updated DESC
        """)
    ).fetchall()

    cases = []
    alert_fired_count = 0
    for r in rows:
        sig = r[2]
        if isinstance(sig, str):
            sig = json.loads(sig)
        elif sig is None:
            sig = []

        case = {
            "ghost_id": r[0],
            "patient_count": r[1] or 0,
            "symptom_signature": sig,
            "status": r[3] or "watching",
            "first_seen": str(r[4] or ""),
            "alert_fired_at": str(r[5]) if r[5] else None,
            "reported_to": r[6],
        }
        cases.append(case)
        if case["status"] == "alert_fired":
            alert_fired_count += 1

    return {
        "total_ghost_cases": len(cases),
        "alert_fired_count": alert_fired_count,
        "cases": cases,
    }


@router.post("/report-ghost/{ghost_id}", response_model=ReportGhostResponse)
async def report_ghost(
    ghost_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Report a ghost case to ICMR/CDC."""
    row = db.execute(
        text("SELECT id, status FROM ghost_cases WHERE ghost_id = :gid"),
        {"gid": ghost_id},
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ghost case {ghost_id} not found.",
        )

    db.execute(
        text("""
            UPDATE ghost_cases
            SET status = 'reported', reported_to = 'ICMR', last_updated = NOW()
            WHERE ghost_id = :gid
        """),
        {"gid": ghost_id},
    )
    db.commit()

    return {
        "ghost_id": ghost_id,
        "status": "reported",
        "reported_to": "ICMR",
        "message": f"Ghost case {ghost_id} reported to ICMR successfully.",
    }


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Public health endpoint for ZebraHunter."""
    result: Dict[str, Any] = {
        "status": "healthy",
        "orphadata_reachable": False,
        "orphadata_authenticated": False,
        "demo_fallback_loaded": True,  # Always True — hardcoded library
        "redis_connected": False,
        "patient_a_ready": False,
        "patient_b_ready": False,
        "ghost_seed_exists": False,
    }

    # Check Orphadata
    if v5_settings.orphadata.is_configured():
        try:
            import httpx

            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    f"{v5_settings.orphadata.base_url}/rd-phenotypes",
                    params={"lang": "en", "limit": 1},
                    headers={"apiKey": v5_settings.orphadata.api_key},
                )
                result["orphadata_reachable"] = resp.status_code < 500
                result["orphadata_authenticated"] = resp.status_code == 200
        except Exception:
            pass

    # Check Redis (non-blocking via executor to avoid blocking event loop)
    try:
        import asyncio
        import redis as redis_sync

        def _check_redis():
            r = redis_sync.Redis(socket_connect_timeout=1, socket_timeout=1)
            r.ping()
            keys = r.keys("ghost:cluster:*")
            r.close()
            return True, len(keys) > 0

        loop = asyncio.get_event_loop()
        connected, has_seed = await asyncio.wait_for(
            loop.run_in_executor(None, _check_redis), timeout=2.0
        )
        result["redis_connected"] = connected
        result["ghost_seed_exists"] = has_seed
    except Exception:
        pass

    # Check Patient A visits
    try:
        count_a = db.execute(
            text("SELECT COUNT(*) FROM patient_visits WHERE patient_id = :pid"),
            {"pid": PATIENT_A_ID},
        ).scalar()
        result["patient_a_ready"] = (count_a or 0) >= 6
    except Exception:
        pass

    # Check Patient B visits
    try:
        count_b = db.execute(
            text("SELECT COUNT(*) FROM patient_visits WHERE patient_id = :pid"),
            {"pid": PATIENT_B_ID},
        ).scalar()
        result["patient_b_ready"] = (count_b or 0) >= 4
    except Exception:
        pass

    return result
