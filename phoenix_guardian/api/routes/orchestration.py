"""
API Routes for Agent Orchestration.

Provides endpoints for:
- Processing encounters through all 10 agents
- Agent health monitoring
- Circuit breaker management
- Agent capabilities listing
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from phoenix_guardian.api.auth import get_current_user

router = APIRouter(prefix="/orchestration", tags=["agent-orchestration"])


# ═══════════════════════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════════════════════


class OrchestrateRequest(BaseModel):
    """Request model for full encounter orchestration."""
    patient_mrn: str = Field(..., description="Patient MRN")
    transcript: str = Field(default="", description="Encounter transcript")
    chief_complaint: str = Field(default="", description="Chief complaint")
    symptoms: List[str] = Field(default_factory=list)
    vitals: Dict[str, str] = Field(default_factory=dict)
    medications: List[str] = Field(default_factory=list)
    exam_findings: str = Field(default="")
    patient_age: int = Field(default=0)
    diagnosis: str = Field(default="")
    duration: int = Field(default=15, description="Encounter duration (min)")
    agents: Optional[List[str]] = Field(None, description="Specific agents to run (null=all)")
    skip_agents: Optional[List[str]] = Field(None, description="Agents to skip")


class OrchestrateResponse(BaseModel):
    """Response model for orchestration result."""
    id: str
    status: str
    total_time_ms: float
    agents_called: int
    agents_succeeded: int
    agents_failed: int
    results: Dict[str, Any]
    errors: Dict[str, str]
    phases_executed: int


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/process", response_model=OrchestrateResponse)
async def orchestrate_encounter(
    request: OrchestrateRequest,
    current_user=Depends(get_current_user),
):
    """
    Process an encounter through all 10 AI agents.

    Executes agents in dependency-aware phases with parallel execution:
    1. **Safety Gate**: Sentinel + Safety (critical - aborts on failure)
    2. **Core Processing**: Scribe + Coding + ClinicalDecision
    3. **Supplementary**: Fraud + Orders + Pharmacy + Deception
    4. **Coordination**: Navigator

    Use `agents` to run specific agents only, or `skip_agents` to exclude some.

    **Circuit Breaker**: Agents with 5+ consecutive errors are automatically skipped.
    """
    from phoenix_guardian.orchestration.agent_orchestrator import get_orchestrator

    orchestrator = get_orchestrator()

    result = await orchestrator.process_encounter(
        encounter_data=request.model_dump(),
        agents=request.agents,
        skip_agents=request.skip_agents,
    )

    return OrchestrateResponse(
        id=result.id,
        status=result.status,
        total_time_ms=result.total_time_ms,
        agents_called=result.agents_called,
        agents_succeeded=result.agents_succeeded,
        agents_failed=result.agents_failed,
        results=result.results,
        errors=result.errors,
        phases_executed=result.phases_executed,
    )


@router.get("/health")
async def get_agent_health(
    current_user=Depends(get_current_user),
):
    """
    Get health status of all 10 agents.

    Returns status, error rates, circuit breaker state, and
    capabilities for each agent.
    """
    from phoenix_guardian.orchestration.agent_orchestrator import get_orchestrator

    orchestrator = get_orchestrator()
    return {
        "agents": orchestrator.get_agent_health(),
        "total_agents": 10,
    }


@router.get("/agents")
async def list_agents(
    current_user=Depends(get_current_user),
):
    """
    List all registered agents with their capabilities.

    Returns agent name, class, status, capabilities, and dependencies.
    """
    from phoenix_guardian.orchestration.agent_orchestrator import get_orchestrator

    orchestrator = get_orchestrator()
    return {
        "agents": orchestrator.get_agent_list(),
        "total": 10,
        "execution_phases": orchestrator.EXECUTION_PHASES,
    }


@router.post("/reset-circuit-breaker/{agent_name}")
async def reset_circuit_breaker(
    agent_name: str,
    current_user=Depends(get_current_user),
):
    """
    Reset the circuit breaker for a specific agent.

    Use this after fixing an agent issue to re-enable it.

    **Path Parameters:**
    - `agent_name`: Agent to reset (e.g., scribe, safety, fraud)
    """
    from phoenix_guardian.orchestration.agent_orchestrator import get_orchestrator

    orchestrator = get_orchestrator()

    valid_agents = {info.name for info in orchestrator._agents.values()}
    if agent_name not in valid_agents:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Valid: {sorted(valid_agents)}",
        )

    orchestrator.reset_circuit_breaker(agent_name)
    return {"status": "reset", "agent": agent_name}
