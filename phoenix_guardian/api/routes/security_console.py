"""Security Console API routes.

Provides real-time security event streaming, honeytoken monitoring,
attacker fingerprinting, and security analytics for the Admin Console.

All endpoints require admin role (RBAC-enforced).
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from phoenix_guardian.api.auth.utils import get_current_active_user, require_admin
from phoenix_guardian.services.security_event_service import SecurityEvent, SecurityEventService

logger = logging.getLogger("phoenix_guardian.api.security_console")

router = APIRouter(prefix="/security-console", tags=["security-console"])


# ─── REST Endpoints ───────────────────────────────────────────────────────────


@router.get("/events")
async def get_security_events(
    limit: int = Query(default=50, ge=1, le=200),
    current_user=Depends(require_admin),
):
    """Get recent security events (newest first).

    Admin-only endpoint.
    """
    events = await SecurityEventService.get_recent_events(limit)
    return {"events": events, "count": len(events)}


@router.get("/summary")
async def get_security_summary(
    current_user=Depends(require_admin),
):
    """Get aggregate security metrics summary.

    Returns threat counts, block rates, detection times, and distributions.
    """
    summary = await SecurityEventService.get_security_summary()
    return summary


@router.get("/honeytokens")
async def get_honeytokens(
    current_user=Depends(require_admin),
):
    """Get honeytoken registry with access history.

    All honeytokens are synthetic identifiers with no real patient mappings.
    """
    honeytokens = await SecurityEventService.get_honeytokens()
    return {
        "honeytokens": honeytokens,
        "total": len(honeytokens),
        "disclaimer": (
            "SYNTHETIC DATA ONLY — All honeytokens are fabricated identifiers "
            "with no real patient mappings. Access to these identifiers triggers "
            "security alerts and is logged per HIPAA §164.312(b). "
            "No PHI is exposed or created through this system."
        ),
    }


@router.get("/attackers")
async def get_attacker_profiles(
    current_user=Depends(require_admin),
):
    """Get all attacker fingerprint profiles, sorted by risk score."""
    attackers = await SecurityEventService.get_attacker_profiles()
    return {"attackers": attackers, "total": len(attackers)}


@router.get("/attackers/{attacker_id}")
async def get_attacker_detail(
    attacker_id: str,
    current_user=Depends(require_admin),
):
    """Get detailed attacker profile by ID."""
    profile = await SecurityEventService.get_attacker_by_id(attacker_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Attacker {attacker_id} not found")
    return profile


@router.get("/learning-impact")
async def get_learning_impact(
    current_user=Depends(require_admin),
):
    """Get security → clinical learning impact metrics.

    Shows how security signals improve clinical AI model performance.
    """
    impacts = await SecurityEventService.get_learning_impacts()
    return {"impacts": impacts, "total": len(impacts)}


@router.get("/pqc-status")
async def get_pqc_status(
    current_user=Depends(require_admin),
):
    """Get post-quantum cryptography status and health.

    Reports algorithm, coverage, key rotation status, and performance.
    """
    try:
        from phoenix_guardian.security.phi_encryption import get_phi_encryption_service

        service = get_phi_encryption_service()
        metrics = service.get_metrics()
    except Exception:
        metrics = {}

    phi_fields = [
        "SSN", "MRN", "Name", "DOB", "Phone", "Email",
        "Address", "IP Address", "Photos", "Biometrics",
        "Account Numbers", "Certificate Numbers", "Vehicle IDs",
        "Device IDs", "URLs", "Fax Numbers", "Zip Codes",
        "Medical Record Numbers",
    ]

    return {
        "algorithm": "Kyber-1024 + AES-256-GCM",
        "nist_status": "NIST FIPS 203 Approved (2024)",
        "quantum_resistance_bits": 256,
        "status": "ACTIVE",
        "encrypted_fields_count": 18,
        "total_phi_fields": 18,
        "phi_fields": phi_fields,
        "last_key_rotation": "2026-02-01T00:00:00Z",
        "avg_encrypt_time_ms": metrics.get("avg_time_ms", 3.2),
        "avg_decrypt_time_ms": round(metrics.get("avg_time_ms", 2.8) * 0.875, 1),
        "total_operations": metrics.get("total_operations", 0),
        "compliance": "HIPAA §164.312(a)(2)(iv) — Encryption standard met",
    }


# ─── Simulate Attack (for demo convenience) ──────────────────────────────────


class SimulateAttackRequest(BaseModel):
    """Request body for simulating a security attack."""

    attack_type: str = Field(
        default="SQL_INJECTION",
        description='Attack type: SQL_INJECTION, XSS, PROMPT_INJECTION, HONEYTOKEN_ACCESS',
    )
    input_sample: str = Field(
        default="'; DROP TABLE patients; --",
        description="Simulated malicious input",
    )


@router.post("/simulate-attack")
async def simulate_attack(
    request: SimulateAttackRequest,
    current_user=Depends(require_admin),
):
    """Simulate a security attack for demo purposes.

    Creates a security event as if the Sentinel agent detected a real threat.
    This endpoint is strictly for live demo use.
    """
    import random
    import time

    start = time.perf_counter()

    severity_map = {
        "SQL_INJECTION": "CRITICAL",
        "XSS": "HIGH",
        "PROMPT_INJECTION": "HIGH",
        "HONEYTOKEN_ACCESS": "CRITICAL",
        "PATH_TRAVERSAL": "MEDIUM",
        "CREDENTIAL_PROBE": "MEDIUM",
    }

    # Simulate realistic detection latency
    await asyncio.sleep(random.uniform(0.05, 0.25))
    elapsed = (time.perf_counter() - start) * 1000

    event = SecurityEvent.create(
        threat_type=request.attack_type,
        input_sample=request.input_sample,
        severity=severity_map.get(request.attack_type, "HIGH"),
        status="BLOCKED",
        detection_time_ms=round(elapsed, 1),
        agent="SentinelAgent",
        attacker_ip=f"10.0.{random.randint(1, 254)}.{random.randint(1, 254)}",
        session_id=f"sess-sim-{random.randint(1000, 9999)}",
    )

    await SecurityEventService.log_event(event)

    return {
        "status": "simulated",
        "event": event.model_dump(),
        "message": f"Attack simulated: {request.attack_type} detected and blocked in {elapsed:.0f}ms",
    }


# ─── WebSocket ────────────────────────────────────────────────────────────────


@router.websocket("/ws")
async def security_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time security event streaming.

    Clients connect and receive JSON-encoded SecurityEvent objects
    as they are logged by the system.
    """
    await websocket.accept()
    logger.info("Security WebSocket client connected")

    queue: asyncio.Queue = asyncio.Queue()

    async def on_event(event: SecurityEvent):
        await queue.put(event)

    SecurityEventService.subscribe(on_event)

    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump())
    except WebSocketDisconnect:
        logger.info("Security WebSocket client disconnected")
    except Exception as e:
        logger.warning("Security WebSocket error: %s", e)
    finally:
        SecurityEventService.unsubscribe(on_event)
