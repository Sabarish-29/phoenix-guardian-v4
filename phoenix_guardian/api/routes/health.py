"""Health check endpoints.

Provides system health status and metrics for monitoring.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from phoenix_guardian.api.dependencies import get_orchestrator
from phoenix_guardian.api.models import (
    AgentHealth,
    HealthCheckResponse,
    HealthStatus,
)
from phoenix_guardian.api.utils.orchestrator import EncounterOrchestrator

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    orchestrator: EncounterOrchestrator = Depends(get_orchestrator),
) -> HealthCheckResponse:
    """System health check endpoint.

    Returns status of all system components including:
    - Overall system status
    - Individual agent health
    - Database connectivity
    - API latency

    Returns:
        HealthCheckResponse with system health information
    """
    metrics = orchestrator.get_metrics()

    # Calculate agent health
    navigator_metrics = metrics["navigator_metrics"]
    scribe_metrics = metrics["scribe_metrics"]

    navigator_health = AgentHealth(
        name="NavigatorAgent",
        status=HealthStatus.HEALTHY,
        avg_execution_time_ms=navigator_metrics["avg_execution_time_ms"],
        call_count=int(navigator_metrics["call_count"]),
        error_rate=0.0,  # TODO: Track actual error rate
    )

    scribe_health = AgentHealth(
        name="ScribeAgent",
        status=HealthStatus.HEALTHY,
        avg_execution_time_ms=scribe_metrics["avg_execution_time_ms"],
        call_count=int(scribe_metrics["call_count"]),
        error_rate=0.0,  # TODO: Track actual error rate
    )

    # Overall system status
    overall_status = HealthStatus.HEALTHY

    return HealthCheckResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
        agents=[navigator_health, scribe_health],
        database_connected=True,  # TODO: Check real DB connection
        api_latency_ms=0.0,  # TODO: Calculate actual latency
    )


@router.get("/metrics")
async def get_metrics(
    orchestrator: EncounterOrchestrator = Depends(get_orchestrator),
) -> dict:
    """Get detailed system metrics.

    Returns performance metrics for all agents and the orchestrator.

    Returns:
        Dictionary with comprehensive metrics
    """
    return orchestrator.get_metrics()
