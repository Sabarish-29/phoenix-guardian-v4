"""
Treatment Shadow API routes — Phoenix Guardian V5 Phase 1.

Endpoints:
  GET  /treatment-shadow/patient/{patient_id}  — full shadow analysis
  GET  /treatment-shadow/alerts                — all fired alerts
  POST /treatment-shadow/dismiss/{shadow_id}   — dismiss a shadow
  GET  /treatment-shadow/health                — public health-check
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from phoenix_guardian.api.auth.utils import get_current_active_user
from phoenix_guardian.database.connection import get_db
from phoenix_guardian.agents.treatment_shadow_agent import TreatmentShadowAgent
from phoenix_guardian.config.v5_agent_config import v5_settings
from phoenix_guardian.models import User

logger = logging.getLogger("phoenix_guardian.api.routes.treatment_shadow")

router = APIRouter(tags=["Treatment Shadow"])

# ── Shared agent instance ─────────────────────────────────────────────────
_agent: Optional[TreatmentShadowAgent] = None


def _get_agent() -> TreatmentShadowAgent:
    global _agent
    if _agent is None:
        _agent = TreatmentShadowAgent()
    return _agent


# ==========================================================================
# Pydantic response models
# ==========================================================================


class TrendResponse(BaseModel):
    slope: float = 0.0
    pct_change: float = 0.0
    direction: str = "insufficient_data"
    r_squared: float = 0.0
    trend_summary: str = ""


class HarmTimelineResponse(BaseModel):
    harm_started_estimate: str = ""
    current_stage: str = ""
    projection_90_days: str = ""
    days_until_irreversible: int = -1


class ShadowDetail(BaseModel):
    shadow_id: Optional[str] = None
    drug: str
    prescribed_since: Optional[str] = None
    shadow_type: str
    watch_lab: str
    alert_fired: bool = False
    severity: str = "watching"
    trend: TrendResponse = TrendResponse()
    lab_values: List[Any] = []
    lab_dates: List[str] = []
    harm_timeline: HarmTimelineResponse = HarmTimelineResponse()
    clinical_output: str = ""
    recommended_action: str = ""


class PatientAnalysisResponse(BaseModel):
    patient_id: str
    patient_name: str = "Unknown Patient"
    analysis_timestamp: str
    total_shadows: int = 0
    fired_count: int = 0
    active_shadows: List[ShadowDetail] = []


class AlertItem(BaseModel):
    patient_id: str
    patient_name: str = ""
    drug: str
    shadow_type: str
    severity: str
    fired_at: Optional[str] = None


class AlertsResponse(BaseModel):
    total_alerts: int = 0
    alerts: List[AlertItem] = []


class HealthResponse(BaseModel):
    status: str = "healthy"
    openfda_reachable: bool = False
    shadow_library_loaded: bool = True
    demo_patient_ready: bool = False


class DismissResponse(BaseModel):
    success: bool
    shadow_id: str
    dismissed_by: str
    dismissed_at: str


# ==========================================================================
# Endpoints
# ==========================================================================


@router.get(
    "/patient/{patient_id}",
    response_model=PatientAnalysisResponse,
    summary="Analyze a patient's treatment shadows",
)
async def analyze_patient(
    patient_id: str,
    language: str = "en",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Run TreatmentShadowAgent analysis for a specific patient.

    Returns all active treatment shadows with trend analysis,
    harm timeline estimates, and AI-generated clinical output.
    """
    agent = _get_agent()

    # Optional Redis cache (include language in key)
    cached = _redis_get(f"treatment_shadow:patient:{patient_id}:{language}")
    if cached:
        return cached

    try:
        result = await agent.analyze_patient(patient_id, db, language=language)
    except Exception as exc:
        logger.error("TreatmentShadow analysis failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(exc)}",
        )

    # Cache for 5 minutes (include language in key)
    _redis_set(f"treatment_shadow:patient:{patient_id}:{language}", result, ex=300)

    return result


@router.get(
    "/alerts",
    response_model=AlertsResponse,
    summary="Get all fired treatment shadow alerts",
)
async def get_all_alerts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return all patients with active (fired) treatment shadow alerts."""
    try:
        rows = db.execute(
            text("""
                SELECT patient_id, drug_name, shadow_type,
                       severity, alert_fired_at
                FROM treatment_shadows
                WHERE alert_fired = true AND dismissed = false
                ORDER BY alert_fired_at DESC NULLS LAST
            """)
        ).fetchall()

        alerts = []
        for row in rows:
            alerts.append({
                "patient_id": str(row[0]),
                "patient_name": "",  # No patients table — left blank
                "drug": row[1],
                "shadow_type": row[2],
                "severity": row[3],
                "fired_at": str(row[4]) if row[4] else None,
            })

        return {
            "total_alerts": len(alerts),
            "alerts": alerts,
        }
    except Exception as exc:
        logger.error("Failed to fetch alerts: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch alerts: {str(exc)}",
        )


@router.post(
    "/dismiss/{shadow_id}",
    response_model=DismissResponse,
    summary="Dismiss a treatment shadow alert",
)
async def dismiss_shadow(
    shadow_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Mark a specific shadow as dismissed by the current user."""
    now = datetime.now(timezone.utc)
    user_email = getattr(current_user, "email", "unknown")

    try:
        result = db.execute(
            text("""
                UPDATE treatment_shadows
                SET dismissed = true,
                    dismissed_by = :user,
                    dismissed_at = :now,
                    updated_at = :now
                WHERE id = :sid
                RETURNING id
            """),
            {"user": user_email, "now": now, "sid": shadow_id},
        )
        db.commit()

        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shadow {shadow_id} not found",
            )

        # Invalidate cache
        _redis_delete(f"treatment_shadow:patient:*")

        return {
            "success": True,
            "shadow_id": shadow_id,
            "dismissed_by": user_email,
            "dismissed_at": now.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Failed to dismiss shadow %s: %s", shadow_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dismiss shadow: {str(exc)}",
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Treatment Shadow health check (public)",
)
async def health_check():
    """Public health endpoint — no auth required.

    Checks: OpenFDA reachable, library loaded, demo patient exists.
    """
    import httpx

    # Check OpenFDA reachability
    openfda_ok = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{v5_settings.openfda.base_url}/drug/label.json",
                params={"limit": 1},
            )
            openfda_ok = resp.status_code == 200
    except Exception:
        openfda_ok = False

    # Check demo patient
    demo_patient_ready = False
    try:
        from phoenix_guardian.database.connection import db as _db
        with _db.session_scope() as sess:
            row = sess.execute(
                text("""
                    SELECT count(*) FROM treatment_shadows
                    WHERE patient_id = 'a1b2c3d4-0004-4000-8000-000000000004'
                """)
            ).scalar()
            demo_patient_ready = (row or 0) > 0
    except Exception as exc:
        logger.warning("Demo patient check failed: %s", exc)

    from phoenix_guardian.agents.treatment_shadow_agent import SHADOW_LIBRARY

    return {
        "status": "healthy",
        "openfda_reachable": openfda_ok,
        "shadow_library_loaded": len(SHADOW_LIBRARY) > 0,
        "demo_patient_ready": demo_patient_ready,
    }


# ==========================================================================
# Redis helpers (graceful degradation if Redis unavailable)
# ==========================================================================


def _redis_get(key: str) -> Optional[Dict]:
    """Try to get cached value from Redis. Returns None on any error."""
    try:
        import redis
        r = redis.from_url(
            __import__("os").getenv("REDIS_URL", "redis://localhost:6379"),
            socket_connect_timeout=1,
        )
        data = r.get(key)
        if data:
            return json.loads(data)
    except Exception:
        pass  # Redis unavailable — no cache
    return None


def _redis_set(key: str, value: Any, ex: int = 300) -> None:
    """Try to cache value in Redis. Silently fails if unavailable."""
    try:
        import redis
        r = redis.from_url(
            __import__("os").getenv("REDIS_URL", "redis://localhost:6379"),
            socket_connect_timeout=1,
        )
        r.set(key, json.dumps(value, default=str), ex=ex)
    except Exception:
        pass


def _redis_delete(key: str) -> None:
    """Try to delete cache key(s) from Redis."""
    try:
        import redis
        r = redis.from_url(
            __import__("os").getenv("REDIS_URL", "redis://localhost:6379"),
            socket_connect_timeout=1,
        )
        if "*" in key:
            for k in r.scan_iter(match=key):
                r.delete(k)
        else:
            r.delete(key)
    except Exception:
        pass
