"""
Silent Voice API routes — Phoenix Guardian V5 Phase 2.

Endpoints:
  GET  /silent-voice/monitor/{patient_id}     — full monitoring result
  POST /silent-voice/baseline/{patient_id}    — force baseline recalculation
  POST /silent-voice/acknowledge/{alert_id}   — acknowledge an alert
  GET  /silent-voice/icu-overview             — all ICU patients with alerts
  GET  /silent-voice/health                   — public health check
  WS   /silent-voice/stream/{patient_id}      — real-time vitals WebSocket
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from phoenix_guardian.api.auth.utils import get_current_active_user
from phoenix_guardian.database.connection import get_db
from phoenix_guardian.agents.silent_voice_agent import SilentVoiceAgent
from phoenix_guardian.config.v5_agent_config import v5_settings
from phoenix_guardian.models import User

logger = logging.getLogger("phoenix_guardian.api.routes.silent_voice")

router = APIRouter(tags=["Silent Voice"])

# ── Shared agent instance ─────────────────────────────────────────────────
_agent: Optional[SilentVoiceAgent] = None


def _get_agent() -> SilentVoiceAgent:
    global _agent
    if _agent is None:
        _agent = SilentVoiceAgent()
    return _agent


# ── Redis helpers (graceful degradation — same as treatment_shadow) ───────

def _redis_get(key: str) -> Optional[Dict]:
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0, socket_timeout=1)
        data = r.get(key)
        if data:
            return json.loads(data)
    except Exception:
        pass
    return None


def _redis_set(key: str, value: Any, ex: int = 300) -> None:
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0, socket_timeout=1)
        r.set(key, json.dumps(value, default=str), ex=ex)
    except Exception:
        pass


def _redis_delete(key: str) -> None:
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0, socket_timeout=1)
        r.delete(key)
    except Exception:
        pass


# ==========================================================================
# Pydantic response models
# ==========================================================================


class SignalDetail(BaseModel):
    vital: str
    label: str = ""
    current: float = 0.0
    baseline_mean: float = 0.0
    baseline_std: float = 0.0
    z_score: float = 0.0
    deviation_pct: float = 0.0
    direction: str = ""


class BaselineVital(BaseModel):
    mean: float = 0.0
    std: float = 1.0


class BaselineResponse(BaseModel):
    patient_id: str
    established_at: str = ""
    vitals_count: int = 0
    baseline_window_minutes: int = 120
    baselines: Dict[str, BaselineVital] = {}


class LatestVitals(BaseModel):
    hr: Optional[float] = None
    bp_sys: Optional[float] = None
    bp_dia: Optional[float] = None
    spo2: Optional[float] = None
    rr: Optional[float] = None
    hrv: Optional[float] = None
    recorded_at: str = ""


class MonitorResponse(BaseModel):
    patient_id: str
    patient_name: str = "Unknown Patient"
    alert_level: str = "clear"
    distress_active: bool = False
    distress_duration_minutes: int = 0
    signals_detected: List[SignalDetail] = []
    latest_vitals: Dict[str, Any] = {}
    baseline: Dict[str, Any] = {}
    last_analgesic_hours: Optional[float] = None
    clinical_output: str = ""
    recommended_action: str = ""
    timestamp: str = ""


class AcknowledgeResponse(BaseModel):
    success: bool
    acknowledged_by: str
    at: str


class ICUOverviewResponse(BaseModel):
    total_patients: int = 0
    patients_with_alerts: int = 0
    results: List[MonitorResponse] = []


class HealthResponse(BaseModel):
    status: str = "healthy"
    baseline_algorithm: str = "personal_zscore"
    zscore_threshold: float = 2.5
    demo_patient_ready: bool = False
    demo_patient_has_baseline: bool = False


# ==========================================================================
# Endpoints
# ==========================================================================


@router.get(
    "/monitor/{patient_id}",
    response_model=MonitorResponse,
    summary="Monitor a patient for non-verbal distress",
)
async def monitor_patient(
    patient_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Run SilentVoiceAgent monitoring for a specific patient.

    Compares latest vitals against the patient's personal baseline
    and returns z-score signals, clinical output, and alert level.
    """
    agent = _get_agent()

    # Optional Redis cache (short TTL — 30s for near-real-time)
    cached = _redis_get(f"silent_voice:monitor:{patient_id}")
    if cached:
        return cached

    try:
        result = await agent.monitor(patient_id, db)
    except Exception as exc:
        logger.error("SilentVoice monitoring failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Monitoring failed: {str(exc)}",
        )

    _redis_set(f"silent_voice:monitor:{patient_id}", result, ex=30)
    return result


@router.post(
    "/baseline/{patient_id}",
    response_model=BaselineResponse,
    summary="Force baseline recalculation for a patient",
)
async def establish_baseline(
    patient_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Force recalculation of a patient's personal vitals baseline.

    Useful when the patient's condition changes and baseline needs reset.
    """
    agent = _get_agent()

    try:
        result = await agent.establish_baseline(patient_id, db)
    except Exception as exc:
        logger.error("Baseline establishment failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Baseline failed: {str(exc)}",
        )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    # Invalidate monitor cache
    _redis_delete(f"silent_voice:monitor:{patient_id}")

    return result


@router.post(
    "/acknowledge/{alert_id}",
    response_model=AcknowledgeResponse,
    summary="Acknowledge a silent voice alert",
)
async def acknowledge_alert(
    alert_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Mark a silent voice alert as acknowledged."""
    now = datetime.now(timezone.utc)

    try:
        # Get the user's display name
        user_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
        if not user_name:
            user_name = current_user.email

        result = db.execute(
            text("""
                UPDATE silent_voice_alerts
                SET acknowledged = true,
                    acknowledged_by = :by,
                    acknowledged_at = :at
                WHERE id = :aid AND acknowledged = false
                RETURNING id
            """),
            {"aid": alert_id, "by": user_name, "at": now},
        ).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found or already acknowledged",
            )

        db.commit()

        return {
            "success": True,
            "acknowledged_by": user_name,
            "at": now.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Failed to acknowledge alert: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Acknowledge failed: {str(exc)}",
        )


@router.get(
    "/icu-overview",
    response_model=ICUOverviewResponse,
    summary="Get all ICU patients with active alerts",
)
async def icu_overview(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return monitoring results for all ICU patients with active alerts."""
    agent = _get_agent()

    try:
        # Count total admitted patients
        total_row = db.execute(
            text("SELECT COUNT(DISTINCT patient_id) FROM admissions WHERE discharged_at IS NULL")
        ).fetchone()
        total_patients = total_row[0] if total_row else 0

        results = await agent.monitor_all_icu_patients(db)

        return {
            "total_patients": total_patients,
            "patients_with_alerts": len(results),
            "results": results,
        }
    except Exception as exc:
        logger.error("ICU overview failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ICU overview failed: {str(exc)}",
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Silent Voice health check",
)
async def health_check():
    """Public health check for the SilentVoice subsystem."""
    demo_ready = False
    has_baseline = False

    try:
        from phoenix_guardian.database.connection import get_db as _get_db
        db = next(_get_db())
        try:
            # Check if Patient C exists with vitals
            row = db.execute(
                text("""
                    SELECT COUNT(*) FROM vitals
                    WHERE patient_id = 'a1b2c3d4-0003-4000-8000-000000000003'
                """)
            ).fetchone()
            demo_ready = row is not None and row[0] > 0

            # Check if baseline exists
            bl_row = db.execute(
                text("""
                    SELECT COUNT(*) FROM patient_baselines
                    WHERE patient_id = 'a1b2c3d4-0003-4000-8000-000000000003'
                """)
            ).fetchone()
            has_baseline = bl_row is not None and bl_row[0] > 0
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Health check DB query failed: %s", exc)

    return {
        "status": "healthy",
        "baseline_algorithm": "personal_zscore",
        "zscore_threshold": v5_settings.silent_voice.zscore_threshold,
        "demo_patient_ready": demo_ready,
        "demo_patient_has_baseline": has_baseline,
    }


# ==========================================================================
# WebSocket — Real-time vitals stream
# ==========================================================================


@router.websocket("/stream/{patient_id}")
async def stream_vitals(websocket: WebSocket, patient_id: str):
    """Real-time vitals stream. Sends monitoring result every 10 seconds.

    Falls back gracefully if DB session errors occur.
    """
    await websocket.accept()
    agent = _get_agent()

    try:
        while True:
            try:
                # Get a fresh DB session for each iteration
                db_gen = get_db()
                db = next(db_gen)
                try:
                    result = await agent.monitor(patient_id, db)
                    await websocket.send_text(json.dumps(result, default=str))
                finally:
                    try:
                        next(db_gen, None)  # close generator
                    except StopIteration:
                        pass
                    db.close()
            except WebSocketDisconnect:
                raise
            except Exception as exc:
                logger.warning("WebSocket monitor error: %s", exc)
                error_msg = json.dumps({"error": str(exc), "alert_level": "clear"})
                try:
                    await websocket.send_text(error_msg)
                except Exception:
                    break

            await asyncio.sleep(10)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for patient %s", patient_id)
    except Exception as exc:
        logger.error("WebSocket fatal error: %s", exc)
        try:
            await websocket.close(code=1011, reason=str(exc)[:120])
        except Exception:
            pass
